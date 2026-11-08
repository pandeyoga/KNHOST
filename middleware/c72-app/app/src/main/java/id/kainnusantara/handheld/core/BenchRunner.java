package id.kainnusantara.handheld.core;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Random;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Uji meja C72 (mode diagnostik ber-PIN): init SDK, kemampuan, daya set+baca ulang, session, baca massal (laju,
 * RSSI mentah & hasil parse), baca tunggal, tulis + baca ulang (+ kembalikan EPC asal), barcode, cari tag, baterai.
 * Setiap langkah = PASS/FAIL/SKIP + data mentah → ekspor JSON untuk laporan uji meja. Tidak mengirim apa pun ke ERP.
 */
public final class BenchRunner {
    public static final class Step {
        public final String id, title;
        public String status = "INFO", detail = "";
        public final JSONObject data = new JSONObject();
        public long ms;
        Step(String id, String title) { this.id = id; this.title = title; }
        public JSONObject toJson() { return Json.obj("id", id, "title", title, "status", status, "detail", detail, "ms", ms, "data", data); }
        public String line() { return mark(status) + " " + title + (detail.isEmpty() ? "" : " — " + detail); }
        static String mark(String s) { return "PASS".equals(s) ? "✓" : "FAIL".equals(s) ? "✕" : "SKIP".equals(s) ? "–" : "i"; }
    }

    private final C72HardwareAdapter hw;
    private final Profile p;
    private final WriteFlow.Sleeper sleeper;
    private final Random random = new Random();

    public BenchRunner(C72HardwareAdapter hw, Profile p, WriteFlow.Sleeper sleeper) { this.hw = hw; this.p = p; this.sleeper = sleeper; }

    private Step timed(Step s, long t0) { s.ms = System.currentTimeMillis() - t0; return s; }

    public Step init() {
        Step s = new Step("init", "Init SDK RFIDWithUHFUART + profil");
        long t0 = System.currentTimeMillis();
        try {
            hw.initialize(p);
            s.status = "PASS";
            s.detail = hw.name();
            Json.put(s.data, "setup", hw.setupReport());
        } catch (C72HardwareAdapter.HardwareException e) {
            s.status = "FAIL";
            s.detail = e.getMessage();
        }
        return timed(s, t0);
    }

    public Step capabilities() {
        Step s = new Step("capabilities", "Kemampuan & versi");
        C72HardwareAdapter.Capabilities c = hw.capabilities();
        Json.put(s.data, "capabilities", c.toJson());
        s.status = c.rfid ? "PASS" : "FAIL";
        s.detail = c.model + " · SDK " + c.sdkVersion + " · HW " + c.hardwareVersion + (c.simulated ? " · SIMULASI" : "");
        return s;
    }

    public Step power(int[] levels) {
        Step s = new Step("power", "Daya: set lalu baca ulang");
        if (!hw.ready()) { s.status = "SKIP"; s.detail = "SDK belum siap"; return s; }
        long t0 = System.currentTimeMillis();
        int before = hw.getPower();
        JSONArray rows = new JSONArray();
        boolean all = true;
        for (int dbm : levels) {
            boolean set = hw.setPower(dbm);
            int back = hw.getPower();
            boolean ok = set && back == dbm;
            all &= ok;
            rows.put(Json.obj("set_dbm", dbm, "set_ok", set, "readback_dbm", back, "match", ok));
        }
        if (before > 0) hw.setPower(before);
        Json.put(s.data, "levels", rows);
        Json.put(s.data, "restored_dbm", hw.getPower());
        s.status = all ? "PASS" : "FAIL";
        s.detail = all ? "semua cocok" : "ada nilai yang tidak cocok — lihat data";
        return timed(s, t0);
    }

    public Step session() {
        Step s = new Step("session", "Session Gen2: set lalu baca ulang");
        if (!hw.ready()) { s.status = "SKIP"; s.detail = "SDK belum siap"; return s; }
        int before = hw.getSession();
        boolean set = hw.setSession(p.session);
        int back = hw.getSession();
        Json.put(s.data, "before", before);
        Json.put(s.data, "set", p.session);
        Json.put(s.data, "readback", back);
        s.status = set && back == p.session ? "PASS" : "FAIL";
        s.detail = "S" + back;
        return s;
    }

    public Step inventory(long ms) {
        Step s = new Step("inventory", "Baca massal " + ms / 1000.0 + " dtk");
        if (!hw.ready()) { s.status = "SKIP"; s.detail = "SDK belum siap"; return s; }
        ReadAggregator agg = new ReadAggregator(5000);
        List<String> rawRssi = new ArrayList<>(), rawAnt = new ArrayList<>();
        long t0 = System.currentTimeMillis();
        boolean began = hw.beginInventory((epc, tid, rssi, mono, wall) -> {
            agg.offer(epc, tid, rssi, mono, wall);
            synchronized (rawRssi) { if (rawRssi.size() < 10) rawRssi.add(String.valueOf(rssi)); }
        });
        if (!began) { s.status = "FAIL"; s.detail = "SDK menolak mulai inventori"; return s; }
        try { sleeper.sleep(ms); } catch (InterruptedException e) { Thread.currentThread().interrupt(); } finally { hw.stopInventory(); }
        double secs = Math.max(0.001, (System.currentTimeMillis() - t0) / 1000.0);
        JSONArray tags = new JSONArray();
        for (ReadAggregator.Tag t : agg.byStrength()) {
            if (tags.length() >= 50) break;
            tags.put(Json.obj("epc", t.epc, "valid", t.valid, "count", t.count, "rssi_max", t.rssiMax, "tid", t.tid));
        }
        Json.put(s.data, "unique", agg.unique());
        Json.put(s.data, "total_reads", agg.totalReads());
        Json.put(s.data, "reads_per_s", Math.round(agg.totalReads() / secs * 10) / 10.0);
        Json.put(s.data, "rssi_missing", agg.rssiMissing());
        Json.put(s.data, "rssi_invalid", agg.rssiInvalid());
        Json.put(s.data, "raw_rssi_samples", new JSONArray(rawRssi));
        Json.put(s.data, "raw_antenna_samples", new JSONArray(rawAnt));
        Json.put(s.data, "tags", tags);
        Json.put(s.data, "locale", Locale.getDefault().toString());
        s.status = agg.unique() > 0 ? "PASS" : "FAIL";
        s.detail = agg.unique() + " tag unik · " + agg.totalReads() + " bacaan · RSSI tak terbaca " + (agg.rssiMissing() + agg.rssiInvalid());
        return timed(s, t0);
    }

    public Step single() {
        Step s = new Step("single", "Baca tunggal (inventorySingleTag)");
        if (!hw.ready()) { s.status = "SKIP"; s.detail = "SDK belum siap"; return s; }
        String[] r = hw.readSingle();
        if (r == null) { s.status = "FAIL"; s.detail = "tidak ada tag"; return s; }
        Json.put(s.data, "epc", r[0]);
        Json.put(s.data, "tid", r.length > 1 ? r[1] : null);
        Json.put(s.data, "rssi_raw", r.length > 2 ? r[2] : null);
        Json.put(s.data, "rssi_parsed", r.length > 2 ? Parse.rssi(r[2]) : null);
        s.status = "PASS";
        s.detail = Epc.display(r[0]);
        return s;
    }

    /** Tulis EPC uji ke tag terdekat, verifikasi, lalu (opsional) kembalikan EPC asal & verifikasi lagi. */
    public Step write(boolean restore) {
        Step s = new Step("write", "Tulis EPC + baca ulang" + (restore ? " + kembalikan" : ""));
        if (!hw.ready()) { s.status = "SKIP"; s.detail = "SDK belum siap"; return s; }
        long t0 = System.currentTimeMillis();
        String testEpc = String.format(Locale.ROOT, "E2BE7C%018X", random.nextLong() & 0x0FFFFFFFFFFFFFFFL).substring(0, 24);
        WriteFlow f = new WriteFlow(hw, p, sleeper);
        WriteFlow.Result r = f.write(testEpc, null);
        Json.put(s.data, "first", result(r));
        if (!r.ok()) { s.status = "FAIL"; s.detail = r.code + ": " + r.message; return timed(s, t0); }
        if (restore && !r.oldEpc.isEmpty()) {
            WriteFlow.Result back = f.write(r.oldEpc, null);
            Json.put(s.data, "restore", result(back));
            if (!back.ok()) { s.status = "FAIL"; s.detail = "tulis OK, kembalikan EPC asal GAGAL — tag kini " + testEpc; return timed(s, t0); }
        }
        s.status = "PASS";
        s.detail = r.attempts + " percobaan, daya " + r.powerDbm + " dBm";
        return timed(s, t0);
    }

    static JSONObject result(WriteFlow.Result r) {
        return Json.obj("code", String.valueOf(r.code), "old_epc", r.oldEpc, "new_epc", r.newEpc, "verified_epc", r.verifiedEpc,
                "rssi", r.rssi, "attempts", r.attempts, "power_dbm", r.powerDbm, "message", r.message);
    }

    public Step barcode(long waitMs) {
        Step s = new Step("barcode", "Pemindai barcode 2D (BarcodeDecoder)");
        long t0 = System.currentTimeMillis();
        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<String[]> got = new AtomicReference<>();
        boolean open = hw.openBarcode(new C72HardwareAdapter.BarcodeListener() {
            public void onBarcode(String data, String sym) { got.set(new String[]{data, sym}); done.countDown(); }
            public void onBarcodeError(String reason) { got.set(new String[]{null, reason}); done.countDown(); }
        });
        if (!open) { s.status = "FAIL"; s.detail = "open() gagal"; return timed(s, t0); }
        try {
            hw.startBarcode();
            done.await(waitMs, TimeUnit.MILLISECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            hw.stopBarcode();
            hw.closeBarcode();
        }
        String[] g = got.get();
        if (g == null) { s.status = "FAIL"; s.detail = "tidak ada hasil dalam " + waitMs / 1000 + " dtk"; }
        else if (g[0] == null) { s.status = "FAIL"; s.detail = g[1]; }
        else { s.status = "PASS"; s.detail = Parse.clip(g[0], 60) + " (" + g[1] + ")"; Json.put(s.data, "data", Parse.clip(g[0], 500)); Json.put(s.data, "symbology", g[1]); }
        return timed(s, t0);
    }

    public Step locate(long ms) {
        Step s = new Step("locate", "Cari tag (nilai relatif 0–100)");
        if (!hw.ready()) { s.status = "SKIP"; s.detail = "SDK belum siap"; return s; }
        String[] one = hw.readSingle();
        if (one == null) { s.status = "SKIP"; s.detail = "tidak ada tag sasaran"; return s; }
        JSONArray vals = new JSONArray();
        long t0 = System.currentTimeMillis();
        boolean ok = hw.startLocate(one[0], (v, valid) -> { synchronized (vals) { if (vals.length() < 200) vals.put(Json.obj("v", v, "valid", valid)); } });
        try { sleeper.sleep(ms); } catch (InterruptedException e) { Thread.currentThread().interrupt(); } finally { hw.stopLocate(); }
        Json.put(s.data, "target", one[0]);
        Json.put(s.data, "values", vals);
        s.status = ok && vals.length() > 0 ? "PASS" : "FAIL";
        s.detail = ok ? vals.length() + " nilai" : "startLocation ditolak SDK";
        return timed(s, t0);
    }

    public Step battery() {
        Step s = new Step("battery", "Baterai");
        JSONObject b = hw.battery();
        Json.put(s.data, "battery", b);
        s.status = b.length() > 0 ? "PASS" : "FAIL";
        s.detail = b.optString("level_pct", "?") + "%";
        return s;
    }

    public List<Step> runAll(boolean withWrite, boolean withBarcode, boolean restoreWrite) {
        List<Step> out = new ArrayList<>();
        out.add(init());
        out.add(capabilities());
        out.add(power(new int[]{p.minPower, p.writePowerDbm, p.powerDbm, p.maxPower}));
        out.add(session());
        out.add(inventory(5000));
        out.add(single());
        out.add(withWrite ? write(restoreWrite) : skipped("write", "Tulis EPC + baca ulang", "tidak dipilih"));
        out.add(withBarcode ? barcode(10000) : skipped("barcode", "Pemindai barcode 2D", "tidak dipilih"));
        out.add(locate(3000));
        out.add(battery());
        return out;
    }

    static Step skipped(String id, String title, String why) { Step s = new Step(id, title); s.status = "SKIP"; s.detail = why; return s; }

    public static JSONObject report(List<Step> steps, JSONObject device, String appVersion, Profile p) {
        JSONArray a = new JSONArray();
        int pass = 0, fail = 0;
        for (Step s : steps) { a.put(s.toJson()); if ("PASS".equals(s.status)) pass++; if ("FAIL".equals(s.status)) fail++; }
        return Json.obj("report", "KN-C72-uji-meja", "app_version", appVersion, "generated_at", Json.now(), "device", device,
                "profile", p.raw, "profile_commissioned", p.commissioned, "summary", Json.obj("pass", pass, "fail", fail, "steps", steps.size()),
                "steps", a, "note", "Hasil uji meja — perilaku SDK dianggap terbukti hanya untuk unit, firmware & versi aplikasi ini.");
    }
}
