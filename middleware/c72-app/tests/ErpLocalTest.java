package id.kainnusantara.handheld.core;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;

/**
 * Uji integrasi klien Java C72 → ERP lokal NYATA (router/service handheld + MongoDB uji), dijalankan oleh
 * tests/run-erp-local.ps1. Memakai kelas aplikasi ASLI (ApiClient/HttpTransport, MemoryStore, Outbox, SyncEngine,
 * Snapshot, DocMatcher, ScanController, WriteFlow) dengan radio TIRUAN (SimulatedHardware). Tidak pernah dipaketkan ke APK.
 * Argumen: baseUrl seed.json (hasil seed_erp_local.py; berisi key & sandi acak uji — tidak di-commit).
 */
public final class ErpLocalTest {
    static int passed;

    static void check(boolean ok, String label) {
        if (!ok) throw new AssertionError("GAGAL: " + label);
        passed++;
        System.out.println("PASS " + label);
    }

    static long now = System.currentTimeMillis();

    /** Transport yang bisa "diputus" untuk mensimulasikan offline gudang. */
    static final class Switchable implements ApiClient.Transport {
        final ApiClient.HttpTransport real = new ApiClient.HttpTransport(5000, 60000, true);
        volatile boolean offline;
        public ApiClient.Response send(String m, String u, Map<String, String> h, byte[] b) throws IOException {
            if (offline) throw new IOException("simulasi internet gudang ↔ VPS putus");
            return real.send(m, u, h, b);
        }
    }

    public static void main(String[] args) throws Exception {
        String base = args[0];
        JSONObject seed = Json.parse(new String(Files.readAllBytes(Paths.get(args[1])), StandardCharsets.UTF_8));
        String[] token = {null};
        Switchable net = new Switchable();
        ClockSync clock = new ClockSync(new ClockSync.Source() {
            public long mono() { return System.nanoTime() / 1_000_000L; }
            public long deviceWall() { return System.currentTimeMillis(); }
        }, 5000, 600000);
        ApiClient api = new ApiClient(net, new ApiClient.Credentials() {
            public String baseUrl() { return base; }
            public String deviceKey() { return seed.getString("device_key"); }
            public String userToken() { return token[0]; }
        }, clock, () -> System.nanoTime() / 1_000_000L);

        // 1. perangkat
        JSONObject cfg = api.deviceConfig();
        Set<String> whs = new LinkedHashSet<>();
        JSONArray w = cfg.getJSONObject("device").getJSONArray("warehouses");
        for (int i = 0; i < w.length(); i++) whs.add(w.getJSONObject(i).getString("id"));
        check(whs.contains(seed.getString("warehouse_id")) && clock.everSynced(), "config perangkat (device key) + jam disinkronkan server_time");
        Profile profile = new Profile(cfg.getJSONObject("profile"));
        check(!profile.commissioned && profile.powerDbm == 20, "profil ERP terbaca (belum commissioning)");

        // 2. login operator ERP + ikat ke perangkat
        JSONObject login = api.login(seed.getString("email"), seed.getString("password").toCharArray());
        token[0] = login.getString("token");
        JSONObject me = api.sessionStart();
        String userId = me.getJSONObject("user").getString("id"), opId = me.getJSONObject("operator_session").getString("id");
        Outbox.Who who = new Outbox.Who(userId, opId);
        check(!opId.isEmpty(), "login ERP + sesi operator perangkat");

        // 3. tugas & yang diharapkan
        String pa = seed.getString("pa_id");
        JSONArray tasks = api.tasks("putaway_in", "").getJSONArray("tasks");
        boolean listed = false;
        for (int i = 0; i < tasks.length(); i++) listed |= pa.equals(tasks.getJSONObject(i).getString("doc_id"));
        check(listed, "daftar Masuk · Putaway memuat PA uji");
        Snapshot snap = new Snapshot(api.expected("putaway_in", pa, false, 2));
        check(snap.rows.size() == 4 && !snap.version.isEmpty(), "unduh yang diharapkan berhalaman (halaman 2 baris) → 4 roll");

        // 4. baca massal (radio tiruan) → cocokkan di perangkat
        JSONArray epcs = seed.getJSONArray("epcs");
        SimulatedHardware hw = new SimulatedHardware(false);
        for (int i = 0; i < 3; i++) hw.add(epcs.getString(i), -50 - i);
        hw.add("E2FFFFFFFFFFFFFFFF00C7AA", -70);   // tag rak tetangga (bukan dokumen)
        hw.initialize(profile);
        ScanController sc = new ScanController(hw, new ReadAggregator(profile.maxReads), profile);
        sc.onKeyDown(293, 0);
        sc.onKeyUp(293);
        MemoryStore store = new MemoryStore();
        DocMatcher.Result m = DocMatcher.match(snap, sc.aggregator().epcs(), Collections.<String>emptyList(), SyncEngine.localState(store, "putaway_in", pa));
        check(m.read == 3 && m.missing == 1 && m.extra.size() == 1, "perangkat: diharapkan 4 · terbaca 3 · kurang 1 · lebih 1 (offline-mampu)");

        // 5. offline → antre → tersambung → terkirim (ID sama)
        SyncEngine eng = new SyncEngine(store, api, () -> now, 60000, new Random(3));
        OutboxItem b1 = Outbox.batch(snap, sc.aggregator().snapshot(), new LinkedHashSet<>(m.toSend), Collections.<String>emptyList(), "", "", false,
                who, clock, clock.now(), sc.firstWall(), sc.lastWall());
        store.enqueue(b1);
        eng.markQueued(b1);
        net.offline = true;
        SyncEngine.Pass p1 = eng.runOnce(userId, 10);
        check(p1.retry == 1 && OutboxItem.PENDING.equals(store.get(b1.id).status), "offline: batch tersimpan & dijadwalkan ulang");
        net.offline = false;
        now = store.get(b1.id).nextDueMs + 1;
        List<JSONObject> results = new ArrayList<>();
        eng.listener((it, res) -> results.add(res));
        eng.runOnce(userId, 10);
        JSONObject r1 = results.get(0);
        int arrived = 0, extra = 0;
        JSONArray items = r1.getJSONArray("items");
        for (int i = 0; i < items.length(); i++) {
            String res = items.getJSONObject(i).getString("result");
            if ("arrived".equals(res)) arrived++;
            if ("extra".equals(res)) extra++;
        }
        check(OutboxItem.DONE.equals(store.get(b1.id).status) && arrived == 3 && extra == 1 && "partially_received".equals(r1.getJSONObject("doc").getString("status")),
                "tersambung: 3 roll TIBA (trip 1), tag tetangga diabaikan, PA tiba sebagian");
        JSONObject replay = api.send(store.get(b1.id));
        check(replay.getBoolean("replay") && replay.getJSONArray("items").length() == 4, "kirim ulang ID sama → hasil tersimpan (tidak dobel)");
        check(SyncEngine.localState(store, "putaway_in", pa).acked.contains(epcs.getString(0)), "layar: roll jadi 'Sudah' dari ACK server");

        // 6. trip 2 menutup PA; kiriman sesudahnya = konflik final
        ReadAggregator trip2 = new ReadAggregator(10);
        trip2.offer(epcs.getString(3), null, "-52,5", 1, clock.now());
        OutboxItem b2 = Outbox.batch(snap, trip2.snapshot(), null, Collections.<String>emptyList(), "", "", false, who, clock, clock.now(), 0, 0);
        store.enqueue(b2);
        now += 1;
        eng.runOnce(userId, 10);
        JSONObject r2 = results.get(results.size() - 1);
        check("completed".equals(r2.getJSONObject("doc").getString("status")), "trip 2: roll terakhir tiba → PA selesai");
        OutboxItem b3 = Outbox.batch(snap, sc.aggregator().snapshot(), Collections.singleton(epcs.getString(0)), Collections.<String>emptyList(), "", "", false,
                who, clock, clock.now(), 0, 0);
        store.enqueue(b3);
        now += 1;
        eng.runOnce(userId, 10);
        check(OutboxItem.CONFLICT.equals(store.get(b3.id).status) && store.get(b3.id).lastError.contains("Dokumen"), "dokumen sudah tertutup → konflik final, tidak diulang");

        // 7. tulis EPC sistem ke tag baru (radio tiruan) → konfirmasi lewat antrean
        String roll = seed.getString("untagged_roll");
        JSONObject wr = api.tagWrite("w-" + Json.uuid(), roll, opId, userId, "uji integrasi");
        JSONObject write = wr.getJSONObject("write");
        String newEpc = write.getString("epc");
        SimulatedHardware tagHw = new SimulatedHardware(false);
        tagHw.add("E2000000000000000000BEEF", -38);       // tag pabrik (EPC tidak unik) sudah ditempel di roll
        tagHw.add("E2000000000000000000BEE0", -72);       // tag lain jauh
        tagHw.initialize(profile);
        WriteFlow.Result res = new WriteFlow(tagHw, profile, ms -> { }).write(newEpc, null);
        check(res.ok() && newEpc.equals(tagHw.field.get(0).epc), "tulis EPC sistem ke tag TERDEKAT + baca ulang");
        OutboxItem tc = Outbox.tagConfirm(write.getString("id"), "uji", res.verifiedEpc, res.tid, res.rssi, res.attempts, res.powerDbm, who, clock.now());
        store.enqueue(tc);
        now += 1;
        eng.runOnce(userId, 10);
        JSONObject lk = api.lookup(roll);
        check(OutboxItem.DONE.equals(store.get(tc.id).status) && newEpc.equals(lk.getJSONObject("tag").getString("epc")), "konfirmasi diterima ERP → tag aktif ber-EPC baru");

        // 8. opname RFID gudang (sesi bukti) → selesaikan lewat antrean
        Snapshot cc = new Snapshot(api.expected("cycle_count", seed.getString("warehouse_id"), true, 5000));
        List<ReadAggregator.Tag> all = new ArrayList<>();
        ReadAggregator agg = new ReadAggregator(100);
        for (Snapshot.Row r : cc.rows) agg.offer(r.epc, null, "-60,0", 1, clock.now());
        all.addAll(agg.snapshot());
        OutboxItem cb = Outbox.batch(cc, all, null, Collections.<String>emptyList(), "", "", false, who, clock, clock.now(), 0, 0);
        store.enqueue(cb);
        store.enqueue(Outbox.complete(cc, who, clock.now() + 1));
        now += 1;
        eng.runOnce(userId, 10);
        JSONObject done = results.get(results.size() - 1);
        check(cc.rows.size() == 5 && OutboxItem.DONE.equals(store.get(cb.id).status) && done.getJSONObject("cycle_count").getDouble("accuracy_pct") == 100.0,
                "opname RFID: 5 roll terbaca, selesai (akurasi 100 %) — urutan batch → selesai dijaga");

        // 9. keluar
        api.sessionEnd(opId, "uji selesai");
        api.logout();
        token[0] = null;
        check(store.count(OutboxItem.PENDING) == 0, "antrean kosong; logout");
        System.out.println("ErpLocalTest: " + passed + " PASS");
    }
}
