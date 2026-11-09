package id.kainnusantara.handheld.core;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/** Tes host logika inti (tanpa perangkat/Android): EPC, RSSI, agregasi, pencocokan dokumen, profil, PIN, form, cari. */
public final class CoreTest {
    static int passed;

    static void check(boolean ok, String label) {
        if (!ok) throw new AssertionError("GAGAL: " + label);
        passed++;
        System.out.println("PASS " + label);
    }

    static final String E1 = "E2000000000000000000AAA1", E2 = "E2000000000000000000AAA2", E3 = "E2000000000000000000AAA3", EX = "E2FFFFFFFFFFFFFFFFFF0001";

    public static void main(String[] a) throws Exception {
        epc(); rssi(); aggregator(); matcher(); profile(); pin(); form(); locate(); errors(); clock();
        System.out.println("CoreTest: " + passed + " PASS");
    }

    static void epc() {
        check("E200000000000000000AAAA1".equals(Epc.canonical("e200-0000-0000-0000-000a-aaa1")), "EPC: pemisah & huruf kecil → kanonik 24 hex");
        check(Epc.canonical("E2000000") == null && Epc.canonical("E2000000000000000000AAAZ") == null, "EPC: panjang/karakter salah ditolak");
        check("E200-0000-0000-0000-0000-AAA1".equals(Epc.display(E1)), "EPC: tampilan berkelompok");
        check("RUSAK-123".equals(Epc.normalizeRead(" rusak-123 ")) && Epc.normalizeRead("  ") == null, "EPC: bacaan rusak tetap tercatat apa adanya, kosong dibuang");
    }

    static void rssi() {
        check(Parse.rssi("-58,30") == -58.3, "RSSI locale id-ID '-58,30' → -58.3");
        check(Parse.rssi("−58.3 dBm") == -58.3, "RSSI tanda minus unicode + satuan");
        check(Parse.rssi("N/A") == null && Parse.rssiKind("N/A") == Parse.RSSI_MISSING, "RSSI N/A = tidak ada (bukan 0)");
        check(Parse.rssi("-1.234,5") == null && Parse.rssiKind("abc") == Parse.RSSI_INVALID, "RSSI rusak = tidak valid");
        check(Parse.decimal("12,5") == 12.5 && Parse.decimal("x") == null, "angka desimal ketikan operator (koma)");
    }

    static void aggregator() {
        ReadAggregator g = new ReadAggregator(3);
        check(g.offer(E1, "T1", "-60,00", 1, 1000), "agregator: EPC baru");
        check(!g.offer(E1, "T1", "-50,00", 2, 1100), "agregator: bacaan ulang bukan EPC baru");
        g.offer(E2, null, "N/A", 3, 1200);
        g.offer("rusak", null, "-40", 4, 1300);
        check(g.unique() == 3 && g.totalReads() == 4, "agregator: unik 3 ≠ total bacaan 4");
        check(!g.offer(E3, null, "-30", 5, 1400) && g.full(), "agregator: kapasitas penuh → EPC baru ditolak (tidak menimpa diam-diam)");
        ReadAggregator.Tag t = g.get(E1);
        check(t.count == 2 && t.rssiMax == -50.0 && t.firstWall == 1000 && t.lastWall == 1100, "agregator: RSSI maks, hitungan & waktu pertama/terakhir");
        List<ReadAggregator.Tag> s = g.byStrength();
        check(s.get(0).epc.equals("RUSAK") && !s.get(0).valid, "agregator: urut sinyal terkuat (EPC rusak ditandai tidak valid)");
        check(g.rssiMissing() == 1, "agregator: RSSI hilang dihitung");
        ReadAggregator r = new ReadAggregator(10);
        r.restore(E1, -55.0, 4, 10, 20, "TID");
        check(r.unique() == 1 && r.get(E1).count == 4, "agregator: pulihkan draf");
    }

    static Snapshot snap() {
        JSONArray rows = new JSONArray()
                .put(Json.obj("roll_id", "r1", "roll_no", "RL-1", "epc", E1, "state", "pending", "qty", 30.0, "unit", "meter"))
                .put(Json.obj("roll_id", "r2", "roll_no", "RL-2", "epc", E2, "state", "done"))
                .put(Json.obj("roll_id", "r3", "roll_no", "RL-3", "epc", E3, "state", "pending"))
                .put(Json.obj("roll_id", "r4", "roll_no", "QR-4", "epc", "QR-4", "state", "pending"));
        return new Snapshot(Json.obj("kind", "putaway_in", "doc_id", "pa1", "number", "PA-1", "version", "v1", "rows", rows,
                "snapshot_at", Json.now(), "labels_allowed", true));
    }

    static void matcher() {
        Snapshot s = snap();
        DocMatcher.Result r = DocMatcher.match(s, Arrays.asList(E1, EX), Collections.singletonList("qr-4"), null);
        check(r.expected == 4 && r.read == 3 && r.missing == 1, "cocok: diharapkan 4, terbaca 3 (1 sudah di server), kurang 1");
        check(r.extra.equals(Collections.singletonList(EX)), "cocok: EPC asing = lebih");
        check(r.toSend.containsAll(Arrays.asList(E1, EX)) && r.labelsToSend.equals(Collections.singletonList("QR-4")), "cocok: yang dikirim = bacaan baru + label");
        DocMatcher.Local l = new DocMatcher.Local();
        l.queued.add(E1);
        l.conflicts.put(E3, "roll berubah");
        DocMatcher.Result r2 = DocMatcher.match(s, Arrays.asList(E1, E3), Collections.<String>emptyList(), l);
        check(r2.rows.get(0).status == DocMatcher.Status.QUEUED && r2.rows.get(2).status == DocMatcher.Status.CONFLICT, "cocok: antre & konflik tampil per baris");
        check(r2.toSend.isEmpty() && r2.conflict == 1, "cocok: kode yang sudah antre/konflik tidak dikirim ulang");
        check(r2.summary().contains("Konflik 1"), "cocok: ringkasan teks (bukan warna saja)");
        JSONObject p1 = Json.obj("version", "v1", "total_rows", 3, "rows", new JSONArray().put(1).put(2));
        Snapshot.merge(p1, Collections.singletonList(Json.obj("version", "v1", "rows", new JSONArray().put(3))));
        check(p1.getJSONArray("rows").length() == 3, "snapshot: halaman digabung");
        boolean threw = false;
        try { Snapshot.merge(Json.obj("version", "v1", "total_rows", 2, "rows", new JSONArray().put(1)), Collections.singletonList(Json.obj("version", "v2", "rows", new JSONArray().put(2)))); }
        catch (IllegalStateException e) { threw = true; }
        check(threw, "snapshot: versi berubah saat unduh → ditolak");
    }

    static void profile() {
        Profile d = Profile.defaults();
        check(d.powerDbm == 20 && d.writePowerDbm == 10 && !d.commissioned && d.triggerHold, "profil bawaan aman (belum commissioning)");
        check(d.isTrigger(293) && !d.isTrigger(4), "profil: kode pemicu bawaan C72 (belum terbukti) & tombol kembali bukan pemicu");
        Profile p = new Profile(Json.obj("rfid", Json.obj("power_dbm", 99, "session", 7), "trigger", Json.obj("keycodes", new JSONArray().put(500), "mode", "toggle")));
        check(p.powerDbm == 30 && p.session == 3 && p.isTrigger(500) && !p.triggerHold, "profil: nilai di luar rentang dibatasi; pemicu & mode dari ERP");
    }

    static void pin() {
        MemoryStore st = new MemoryStore();
        check(Pin.validate("12345") != null && Pin.validate("111111") != null && Pin.validate("123456") != null && Pin.validate("482913") == null, "PIN: aturan 6–12 angka, tidak trivial");
        st.set("pin.hash", Pin.hash("482913"));
        check(Pin.check(st, "482913", 1000) == null, "PIN: benar");
        for (int i = 0; i < 4; i++) Pin.check(st, "000000", 1000);
        check(Pin.check(st, "000000", 1000).contains("terkunci"), "PIN: 5 salah → terkunci");
        check(Pin.check(st, "482913", 2000).contains("terkunci") && Pin.check(st, "482913", 1000 + Pin.LOCK_MS + 1) == null, "PIN: terkunci 5 menit lalu pulih");
        check(!st.kv("pin.hash", "").contains("482913"), "PIN: tidak disimpan polos");
    }

    static void form() {
        RegistrationForm f = new RegistrationForm();
        List<String> e = f.validate(true, null);
        check(e.size() >= 4, "form Daftar Awal: bin, PT, produk, panjang, EPC wajib");
        f.binId = "b1"; f.ownerEntityId = "ent"; f.productId = "p1"; f.qty = "12,5"; f.unit = "yard"; f.grade = "b"; f.lot = " L1 ";
        check(f.validate(true, E1).isEmpty(), "form: lengkap → valid");
        JSONObject line = f.toLine("cl1", E1, true, "2026-11-09T00:00:00Z");
        check(line.getDouble("qty") == 12.5 && "B".equals(line.getString("grade")) && "L1".equals(line.getString("lot")) && line.getBoolean("written"),
                "form: baris batch (panjang, grade, lot, tertulis)");
        f.unrecognized = true; f.productId = ""; f.note = "ab"; f.qty = "";
        check(f.validate(false, null).size() == 1, "form: produk belum dikenali wajib keterangan ≥3 huruf");
        f.note = "motif bunga biru";
        check(f.validate(false, null).isEmpty() && f.toLine("c2", E2, false, "").getBoolean("unrecognized"), "form: belum dikenali tanpa panjang boleh");
        f.qty = "5"; f.oldRollNo = "OLD"; f.nextRoll();
        check(f.qty.isEmpty() && f.oldRollNo.isEmpty() && "b1".equals(f.binId) && "yard".equals(f.unit), "form: roll berikutnya — bin & satuan tetap");
    }

    static void locate() {
        check(LocateMeter.fromRssi(-80.0) == 0 && LocateMeter.fromRssi(-30.0) == 100 && LocateMeter.fromRssi(null) == 0, "cari: RSSI → 0–100");
        LocateMeter m = new LocateMeter(0.5);
        m.offer(80, true, 0);
        check(m.offer(40, true, 100) == 60 && m.value(2000) == 0, "cari: dihaluskan & turun ke 0 bila hilang");
        check(LocateMeter.beepIntervalMs(100) < LocateMeter.beepIntervalMs(10) && "Sangat dekat".equals(LocateMeter.label(90)), "cari: bunyi makin rapat & label teks");
    }

    static void errors() {
        check(ErrorPolicy.classify(0, "NETWORK", true) == ErrorPolicy.Action.RETRY, "galat: jaringan → ulang");
        check(ErrorPolicy.classify(401, "", null) == ErrorPolicy.Action.LOGIN_REQUIRED, "galat: 401 sesi → login ulang");
        check(ErrorPolicy.classify(401, "DEVICE_KEY_INVALID", false) == ErrorPolicy.Action.DEVICE_BLOCKED, "galat: device key → perangkat diblokir");
        check(ErrorPolicy.classify(409, "IDEMPOTENCY_CONFLICT", false) == ErrorPolicy.Action.IDEMPOTENCY, "galat: isi berubah → peninjauan");
        check(ErrorPolicy.classify(409, "REQUEST_IN_PROGRESS", true) == ErrorPolicy.Action.RETRY, "galat: sedang diproses → ulang");
        check(ErrorPolicy.classify(403, "SCOPE_DENIED", false) == ErrorPolicy.Action.REJECTED, "galat: di luar cakupan → ditolak, tidak diulang");
        check(ErrorPolicy.backoffMs(1, 300000, 0, 0.5) == 2000 && ErrorPolicy.backoffMs(20, 300000, 0, 0.5) == 300000, "galat: backoff 2 dtk → maks");
        check(ErrorPolicy.backoffMs(1, 300000, 9000, 0) == 9000, "galat: Retry-After dihormati");
    }

    static void clock() {
        long[] mono = {1000};
        ClockSync c = new ClockSync(new ClockSync.Source() { public long mono() { return mono[0]; } public long deviceWall() { return 5_000; } }, 5000, 60000);
        check(!c.everSynced() && c.offsetMs() == 0, "jam: belum sinkron");
        c.offer(1_000_000, 1000, 1200);
        mono[0] = 1100;
        check(c.everSynced() && c.wallAt(1100) == 1_000_000 && c.offsetMs() == 1_000_000 - 5_000, "jam: koreksi setengah RTT & selisih jam perangkat");
    }
}
