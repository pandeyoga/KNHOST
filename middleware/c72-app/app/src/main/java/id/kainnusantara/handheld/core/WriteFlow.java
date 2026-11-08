package id.kainnusantara.handheld.core;

import java.util.List;

/**
 * Tulis EPC buatan sistem ke tag TERDEKAT lalu BACA ULANG (K-OPN-05). Langkah:
 * <ol>
 *   <li>Turunkan daya ke {@code write_power_dbm} (hanya tag terdekat yang menjawab), pindai {@code scan_ms}.</li>
 *   <li>Pilih RSSI terkuat; bila tag kedua terlalu dekat kuatnya (selisih &lt; {@code min_rssi_gap_db}) → AMBIGUOUS
 *       (minta jauhkan tag lain) — tidak menebak.</li>
 *   <li>Tulis dengan filter EPC lama; ulang s.d. {@code max_attempts}.</li>
 *   <li>Verifikasi: pindai lagi; EPC baru harus terbaca & EPC lama hilang dari medan dekat. "SDK bilang sukses" saja
 *       TIDAK cukup.</li>
 * </ol>
 * Bila EPC baru sudah ada di tag terdekat (ulang setelah aplikasi mati di tengah) → langsung verifikasi.
 * Daya dikembalikan ke nilai semula di akhir. Radio harus sudah dipegang eksklusif (ScanController.acquire).
 */
public final class WriteFlow {
    public interface Sleeper { void sleep(long ms) throws InterruptedException; }

    public enum Code { OK, NO_TAG, AMBIGUOUS, WRITE_FAILED, VERIFY_FAILED, HARDWARE, INVALID_EPC }

    public static final class Result {
        public Code code;
        public String oldEpc = "", newEpc = "", verifiedEpc = "", tid = "", message = "";
        public Double rssi;
        public int attempts, powerDbm;
        public boolean ok() { return code == Code.OK; }
    }

    public static final String DEFAULT_ACCESS_PASSWORD = "00000000";

    private final C72HardwareAdapter hw;
    private final Profile p;
    private final Sleeper sleeper;

    public WriteFlow(C72HardwareAdapter hw, Profile p, Sleeper sleeper) { this.hw = hw; this.p = p; this.sleeper = sleeper; }

    List<ReadAggregator.Tag> scan(long ms) throws InterruptedException {
        ReadAggregator agg = new ReadAggregator(200);
        if (!hw.beginInventory((epc, tid, rssi, mono, wall) -> agg.offer(epc, tid, rssi, mono, wall))) return null;
        try { sleeper.sleep(ms); } finally { hw.stopInventory(); }
        return agg.byStrength();
    }

    public Result write(String newEpc, String accessPassword) {
        Result r = new Result();
        r.newEpc = Epc.canonical(newEpc) == null ? "" : Epc.canonical(newEpc);
        if (r.newEpc.isEmpty()) { r.code = Code.INVALID_EPC; r.message = "EPC sasaran tidak valid."; return r; }
        String pwd = accessPassword == null || accessPassword.isEmpty() ? DEFAULT_ACCESS_PASSWORD : accessPassword;
        int before = hw.getPower();
        r.powerDbm = p.writePowerDbm;
        try {
            if (!hw.setPower(p.writePowerDbm)) { r.code = Code.HARDWARE; r.message = "Gagal menurunkan daya tulis."; return r; }
            List<ReadAggregator.Tag> tags = scan(p.writeScanMs);
            if (tags == null) { r.code = Code.HARDWARE; r.message = "SDK menolak memulai pindai."; return r; }
            if (tags.isEmpty()) { r.code = Code.NO_TAG; r.message = "Tidak ada tag terbaca — dekatkan C72 ke tag (±5–10 cm)."; return r; }
            ReadAggregator.Tag best = tags.get(0);
            if (tags.size() > 1 && !clearlyStrongest(best, tags.get(1))) {
                r.code = Code.AMBIGUOUS;
                r.message = "Ada " + tags.size() + " tag berdekatan dengan sinyal mirip — jauhkan tag/roll lain lalu ulangi.";
                return r;
            }
            r.oldEpc = best.epc; r.rssi = best.rssiMax; r.tid = best.tid == null ? "" : best.tid;
            if (best.epc.equals(r.newEpc)) return verify(r);   // sudah tertulis (ulang setelah gangguan)
            String target = best.epc;
            boolean verifyFailed = false;
            for (int i = 1; i <= p.writeMaxAttempts; i++) {
                r.attempts = i;
                C72HardwareAdapter.WriteOutcome w = hw.writeEpc(target, r.newEpc, pwd);
                if (w.ok) {
                    if (verify(r).ok()) return r;
                    verifyFailed = true;
                } else {
                    r.message = "SDK gagal menulis (kode " + w.errCode + (w.message.isEmpty() ? "" : ", " + w.message) + ").";
                }
                sleeper.sleep(150);
                List<ReadAggregator.Tag> now = scan(Math.max(300, p.writeScanMs / 2));   // apa isi chip sekarang?
                if (now != null && !now.isEmpty()) {
                    if (now.get(0).epc.equals(r.newEpc) && verify(r).ok()) return r;
                    if (now.size() == 1 || clearlyStrongest(now.get(0), now.get(1))) target = now.get(0).epc;
                }
            }
            r.code = verifyFailed ? Code.VERIFY_FAILED : Code.WRITE_FAILED;
            r.verifiedEpc = "";
            if (r.message.isEmpty() || verifyFailed) r.message = (verifyFailed ? "Baca ulang tidak mengonfirmasi EPC baru" : "Tulis gagal")
                    + " setelah " + r.attempts + " percobaan — ganti posisi/tag lalu ulangi.";
            return r;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            r.code = Code.HARDWARE; r.message = "Dibatalkan.";
            return r;
        } finally {
            if (before > 0) hw.setPower(before);
        }
    }

    private boolean clearlyStrongest(ReadAggregator.Tag a, ReadAggregator.Tag b) {
        if (a.rssiMax == null) return false;
        if (b.rssiMax == null) return true;
        return a.rssiMax - b.rssiMax >= p.minRssiGapDb;
    }

    /** Baca ulang {@code verify_reads} kali; EPC baru wajib terbaca sebagai terkuat dan EPC lama tidak muncul lagi. */
    Result verify(Result r) throws InterruptedException {
        int seen = 0;
        for (int i = 0; i < p.writeVerifyReads; i++) {
            List<ReadAggregator.Tag> tags = scan(Math.max(300, p.writeScanMs / 2));
            if (tags == null || tags.isEmpty()) continue;
            boolean oldStill = false;
            for (ReadAggregator.Tag t : tags) if (!r.oldEpc.isEmpty() && t.epc.equals(r.oldEpc) && !r.oldEpc.equals(r.newEpc)) oldStill = true;
            if (tags.get(0).epc.equals(r.newEpc) && !oldStill) {
                seen++;
                r.verifiedEpc = r.newEpc;
                if (tags.get(0).rssiMax != null) r.rssi = tags.get(0).rssiMax;
            }
        }
        if (seen == p.writeVerifyReads) { r.code = Code.OK; r.message = "EPC tertulis & terverifikasi baca ulang (" + seen + "×)."; }
        else { r.code = Code.VERIFY_FAILED; r.verifiedEpc = ""; r.message = "Baca ulang tidak mengonfirmasi EPC baru (" + seen + "/" + p.writeVerifyReads + ") — ulangi tulis."; }
        return r;
    }
}
