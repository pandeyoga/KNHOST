package id.kubusteknologi.kn.u300;

import id.kubusteknologi.kn.u300.core.*;
import org.json.*;

import java.util.*;

/**
 * Uji integrasi agent 0.5 → ERP lokal NYATA (router/service rfid_v2 + MongoDB uji), dijalankan oleh
 * tests/run_erp_local_v2.py. Memakai kelas agent asli: Api (HTTP lokal), Config (profil commissioned, non-simulasi),
 * GatePipeline + BeamDebouncer (linimasa photo-eye & bacaan buatan), Batcher/Envelope (multi-batch seq/boot_id),
 * ClockSync, DecisionPolicy. Tidak memakai radio/GPIO. Argumen: baseUrl gateId epcDokumen(koma).
 * Env KN_TEST_DEVICE_KEY. Tidak pernah dipaketkan ke APK.
 */
public final class ErpLocalV2Test {
    static int passed;
    static void check(boolean ok, String label) { if (!ok) throw new AssertionError(label); passed++; System.out.println("PASS " + label); }
    static long mono() { return System.nanoTime() / 1_000_000L; }

    static final class Mem implements GatePipeline.Store {
        int n; final String prefix = "e-int-" + UUID.randomUUID().toString().substring(0, 8) + "-";
        final Map<String, List<JSONObject>> edges = new LinkedHashMap<>(), sums = new LinkedHashMap<>();
        final Map<String, PassageMachine.Closing> closings = new LinkedHashMap<>(); final Map<String, Boolean> ok = new LinkedHashMap<>();
        public String newPassageId() { return prefix + (++n); }
        public void opened(String id, PassageMachine.Opening o) {}
        public void edge(String id, JSONObject e) { edges.computeIfAbsent(id, k -> new ArrayList<>()).add(e); }
        public void checkpoint(String id, List<JSONObject> d) {}
        public void closed(String id, PassageMachine.Closing c, List<JSONObject> s, boolean complete) { closings.put(id, c); sums.put(id, s); ok.put(id, complete); }
        public void health(String h, String d, long t) { System.out.println("  sensor " + h + ": " + d); }
        String last() { String l = null; for (String k : closings.keySet()) l = k; return l; }
    }

    static Config cfg; static Api api; static ClockSync clock; static GatePipeline gp; static Mem mem = new Mem();
    static BeamDebouncer da, db; static long seq = 0; static final String BOOT = "boot-int-" + UUID.randomUUID().toString().substring(0, 8);
    static final TreeMap<Long, List<RawRead>> reads = new TreeMap<>(); static final TreeMap<Long, boolean[]> beams = new TreeMap<>(); static long cursor;

    static String rssi(double v) { return String.format(new Locale("in", "ID"), "%.2f", v); }
    static void read(long at, String epc, String ant, double r) { reads.computeIfAbsent(at, k -> new ArrayList<>()).add(new RawRead(epc, "TID", ant, rssi(r), at * 1_000_000L, System.currentTimeMillis())); }
    static boolean beamAt(long t, int i) { Map.Entry<Long, boolean[]> e = beams.floorEntry(t); return e != null && e.getValue()[i]; }
    static void beam(long at, Boolean a, Boolean b) { beams.put(at, new boolean[]{a == null ? beamAt(at, 0) : a, b == null ? beamAt(at, 1) : b}); }
    /** Proses linimasa sampai {@code until} seperti loop kontrol agent (poll gpi_poll_ms, urut waktu). */
    static void run(long until) throws InterruptedException {
        while (mono() < until) Thread.sleep(50);          // linimasa selaras jam nyata (closing_captured_at segar)
        for (; cursor <= until; cursor += cfg.gpiPollMs) {
            List<Object> ev = new ArrayList<>();
            for (List<RawRead> l : reads.subMap(cursor - cfg.gpiPollMs, false, cursor, true).values()) for (RawRead r : l) ev.add(gp.parse(r));
            BeamDebouncer.Edge ea = da.sample(beamAt(cursor, 0), cursor), eb = db.sample(beamAt(cursor, 1), cursor);
            if (ea != null) ev.add(ea); if (eb != null) ev.add(eb);
            ev.sort(Comparator.comparingLong(o -> o instanceof Sample ? ((Sample) o).tMono : ((BeamDebouncer.Edge) o).tMono));
            for (Object o : ev) { if (o instanceof Sample) gp.onSample((Sample) o); else gp.onEdge((BeamDebouncer.Edge) o); }
            gp.tick(cursor);
        }
    }

    static JSONObject meta() {
        return Json.obj("config_version", cfg.version, "logical_gate_id", cfg.gateId, "completion_basis", cfg.basis, "direction", cfg.direction,
                "profile_id", cfg.raw.optString("hardware_profile_id"), "sensor_mode", cfg.sensorMode, "boot_id", BOOT);
    }

    /** Kirim bukti lintasan (multi-batch, body dibatasi) lalu close; kembalikan {keputusan, gate-state}. */
    static JSONObject[] deliver(String pid, int maxBody) throws Exception {
        JSONObject meta = meta();
        List<Batcher.Item> pending = new ArrayList<>();
        for (JSONObject e : mem.edges.getOrDefault(pid, Collections.emptyList())) pending.add(new Batcher.Item(Batcher.EDGE, e.getString("edge_id"), e));
        for (JSONObject s : mem.sums.get(pid)) pending.add(new Batcher.Item(Batcher.SUMMARY, s.getString("summary_id"), s));
        int received = 0, batches = 0;
        while (!pending.isEmpty()) {
            String id = UUID.randomUUID().toString();
            JSONObject base = Envelope.eventsBase(id, pid, meta, "live", 0, BOOT, Envelope.iso(clock.now()));
            List<Batcher.Item> fit = Batcher.fit(pending, base, cfg.maxEvents, Math.min(maxBody, cfg.maxBody));
            base.put("seq", seq++).put("boot_id", BOOT);
            JSONObject res = api.call("POST", "/events", Batcher.build(base, fit), null);
            check(id.equals(res.getString("batch_id")) && !res.optBoolean("seq_gap"), pid + ": batch " + batches + " ACK, seq " + (seq - 1) + " tanpa celah");
            for (String k : new String[]{"summary_acks", "edge_acks"}) {
                JSONArray a = res.optJSONArray(k);
                if (a != null) for (int i = 0; i < a.length(); i++) { JSONObject x = a.getJSONObject(i); if (x.getBoolean("durable") && !"retry".equals(x.getString("status"))) received++; }
            }
            pending.removeAll(fit); batches++;
        }
        check(received == mem.edges.getOrDefault(pid, Collections.emptyList()).size() + mem.sums.get(pid).size(), pid + ": semua item durable (" + batches + " batch)");
        JSONObject close = Envelope.close(meta, mem.closings.get(pid), clock::wallAt, mem.ok.get(pid), "live", BOOT, Json.obj("a", cfg.pinA, "b", cfg.pinB), cfg.activeState);
        close.put("observed_summary_count", mem.sums.get(pid).size()).put("observed_edge_count", mem.edges.getOrDefault(pid, Collections.emptyList()).size());
        JSONObject d = api.call("POST", "/passages/" + pid + "/close", close, "close-" + pid);
        JSONObject again = api.call("POST", "/passages/" + pid + "/close", close, "close-" + pid);
        check(again.getString("decision_id").equals(d.getString("decision_id")), pid + ": close idempoten");
        JSONObject gs = api.call("GET", "/device/gate-state?logical_gate_id=" + java.net.URLEncoder.encode(cfg.gateId, "UTF-8") + "&local_passage_id=" + pid, null, null);
        System.out.println("  " + pid + " → " + d.getString("verdict") + " " + d.optJSONArray("reason_codes") + " counts=" + d.optJSONObject("counts") + " latched=" + gs.getBoolean("latched"));
        return new JSONObject[]{d, gs};
    }

    public static void main(String[] args) throws Exception {
        String base = args[0], gate = args[1];
        List<String> doc = new ArrayList<>(Arrays.asList(args[2].split(",")));
        api = new Api(new Api.Settings() { public boolean simulation() { return false; } public String url() { return base; } public String token() { return System.getenv("KN_TEST_DEVICE_KEY"); } });
        clock = new ClockSync(new ClockSync.Source() { public long mono() { return ErpLocalV2Test.mono(); } public long deviceWall() { return System.currentTimeMillis(); } }, 2000, 120000);
        api.clock = clock; api.mono = ErpLocalV2Test::mono;
        JSONObject raw = api.call("GET", "/device/config", null, null);
        cfg = new Config(raw, gate, false);
        check("one_way_beam".equals(cfg.sensorMode) && cfg.antennas.size() == 3 && "document_session".equals(cfg.basis), "ERP: profil 2.1 commissioned diterima Config (non-simulasi)");
        check(clock.good(mono()), "ERP: jam tersinkron dari respons config");
        gp = new GatePipeline(cfg.pipeline, mem, clock::wallAt, clock::good);
        da = new BeamDebouncer("A", cfg.minBlockMs, cfg.minClearMs); db = new BeamDebouncer("B", cfg.minBlockMs, cfg.minClearMs);
        long T = mono(); cursor = T;
        String bg = "E2" + "0000000000000000000BEEF".substring(1);
        for (long k = 0; k <= 400_000; k += 300) read(T + k, bg, "3", -71 + (k % 600 == 0 ? 0.5 : 0));   // tag rak, terbaca terus

        // A. Trip 1 sesi dokumen (separuh roll), label depan sebelum A↓, tag rak latar → GREEN, sisa > 0
        int half = Math.max(1, doc.size() / 2);
        List<String> trip1 = doc.subList(0, half), trip2 = doc.subList(half, doc.size());
        long t1 = T + 9_000;
        for (int i = 0; i < trip1.size(); i++) for (long k = -1500; k <= 1200; k += 120) read(t1 + 1200 + k + i * 7, trip1.get(i), i % 2 == 0 ? "1" : "2", -45 - Math.abs(k) / 110.0);
        beam(t1, true, false); beam(t1 + 1100, null, true); beam(t1 + 1800, false, null); beam(t1 + 2600, null, false);
        run(t1 + 5000);
        String pA = mem.last();
        check("EXITED".equals(mem.closings.get(pA).closeReason) && mem.ok.get(pA), "A: lintasan photo-eye EXITED lengkap");
        JSONObject[] a = deliver(pA, 2500);     // batas body kecil → beberapa envelope (multi-batch) ke server nyata
        JSONObject dA = a[0];
        boolean partial = !trip2.isEmpty();
        check("GREEN".equals(dA.getString("verdict")) && "document_session".equals(dA.getString("completion_basis")), "A: ERP GREEN document_session (trip parsial)");
        check(dA.getJSONObject("counts").getInt("background") >= 1 && dA.getJSONObject("counts").getInt("matched") == trip1.size(), "A: tag rak ditandai latar oleh agent & diabaikan ERP; roll trip cocok");
        if (partial) check(dA.getJSONObject("counts").getInt("pending") >= trip2.size(), "A: sisa roll dokumen > 0 (dinilai saat dokumen ditutup)");
        long now = clock.now();
        check(DecisionPolicy.validGreen(a[1], dA, meta(), pA, "live", now, cfg.policy.getInt("gate_decision_validity_seconds") * 1000L), "A: agent menerima hijau trip parsial dari ERP nyata");

        // B. Photo-eye macet → cadangan RF (trip 2) → REVIEW kuning tanpa kunci
        if (partial) {
            long t2 = cursor + 500;
            beam(t2, true, false); beam(t2 + 1000, null, true);                         // stacker berhenti di gate, sinar macet
            run(t2 + cfg.pipeline.machine.sensorStuckMs + 300);
            check(gp.machine().rfLogicActive(), "B: sinar macet → cadangan RF aktif (tidak berhenti)");
            String pS = mem.last();
            check("SENSOR_FAULT".equals(mem.closings.get(pS).closeReason) && "fault".equals(mem.closings.get(pS).sensorHealth), "B: lintasan terbuka ditutup SENSOR_FAULT");
            JSONObject dS = deliver(pS, 64000)[0];
            check("REVIEW".equals(dS.getString("verdict")) || "CANCELLED".equals(dS.getString("verdict")), "B: lintasan sensor rusak dinilai kuning/batal, bukan merah");
            long t3 = cursor + 1000;
            for (int i = 0; i < trip2.size(); i++) for (long k = 0; k <= 1800; k += 150) read(t3 + k + i * 9, trip2.get(i), "1", -47);
            for (int i = 0; i < 3; i++) for (long k = 0; k <= 1800; k += 150) read(t3 + k + 3, "E2000000000000000AAAA00" + i, "2", -85);   // lemah
            run(t3 + 1800 + cfg.pipeline.machine.stableIntervalMs + 200);
            String pB = mem.last();
            if (trip2.size() >= cfg.pipeline.machine.rfGroupSize) {
                check("RF_FALLBACK".equals(mem.closings.get(pB).openReason) && "SENSOR_FAULT".equals(mem.closings.get(pB).closeReason), "B: lintasan RF_FALLBACK → SENSOR_FAULT");
                JSONObject[] b = deliver(pB, 64000);
                check("REVIEW".equals(b[0].getString("verdict")) && !b[1].getBoolean("latched") && "YELLOW".equals(b[0].optString("indicator")), "B: ERP REVIEW kuning tanpa kunci (rf_fallback_review)");
                check(DecisionPolicy.validYellow(b[1], b[0], meta(), pB, "live", clock.now(), cfg.policy.getInt("gate_decision_validity_seconds") * 1000L), "B: agent menyalakan kuning");
            } else System.out.println("  (B dilewati: sisa roll < rf_fallback_group_size)");
            beam(cursor + 100, false, false);
            for (int k = 0; k < 2; k++) { long s = cursor + 1000 + k * 4000; beam(s, true, false); beam(s + 1000, null, true); beam(s + 1700, false, null); beam(s + 2500, null, false); }
            run(cursor + 12_000);
            check("ok".equals(gp.machine().health()), "B: photo-eye pulih setelah 2 urutan sah");
            for (String pid : new ArrayList<>(mem.closings.keySet())) if (pid.compareTo(pB) > 0 && !mem.sums.get(pid).isEmpty()) System.out.println("  (lintasan pemulihan " + pid + " tidak dikirim)");
        }

        // C. Orang lewat tanpa tag (hanya tag latar) → CANCELLED tanpa alarm
        long t4 = cursor + 2000;
        for (long k = 0; k <= 3000; k += 300) read(t4 + k, bg, "3", -71);
        beam(t4, true, false); beam(t4 + 900, null, true); beam(t4 + 1300, false, null); beam(t4 + 1900, null, false);
        run(t4 + 4000);
        String pC = mem.last();
        JSONObject dC = deliver(pC, 64000)[0];
        check("CANCELLED".equals(dC.getString("verdict")) && !dC.getBoolean("latched"), "C: lintasan kosong → CANCELLED tanpa kunci");

        // D. Mundur (B bebas dulu, A terakhir) tanpa roll → CANCELLED
        long t5 = cursor + 2000;
        beam(t5, true, false); beam(t5 + 1100, null, true); beam(t5 + 1700, null, false); beam(t5 + 2300, false, null);
        run(t5 + 3000);
        String pD = mem.last();
        check("REVERSED".equals(mem.closings.get(pD).closeReason), "D: agent menutup REVERSED");
        check("CANCELLED".equals(deliver(pD, 64000)[0].getString("verdict")), "D: ERP mundur tanpa roll → CANCELLED");

        // E. EPC asing bersinyal kuat → RED + kunci gate; agent tidak hijau/kuning
        long t6 = cursor + 2000; String foreign = "E2" + UUID.randomUUID().toString().replace("-", "").substring(0, 22).toUpperCase(Locale.ROOT);
        for (long k = -800; k <= 800; k += 100) read(t6 + 1000 + k, foreign, "1", -44);
        beam(t6, true, false); beam(t6 + 1000, null, true); beam(t6 + 1600, false, null); beam(t6 + 2200, null, false);
        run(t6 + 4000);
        String pE = mem.last();
        JSONObject[] e = deliver(pE, 64000);
        check("RED".equals(e[0].getString("verdict")) && e[1].getBoolean("latched") && e[0].optJSONArray("reason_codes").toString().contains("UNKNOWN_EPC"), "E: ERP RED UNKNOWN_EPC + gate terkunci");
        check(!DecisionPolicy.validGreen(e[1], e[0], meta(), pE, "live", clock.now(), 5000) && !DecisionPolicy.validYellow(e[1], e[0], meta(), pE, "live", clock.now(), 5000), "E: agent tidak hijau/kuning saat merah");

        // F. Telemetry 0.5 diterima ERP
        Telemetry.Values tv = new Telemetry.Values();
        tv.eventId = UUID.randomUUID().toString(); tv.capturedAt = Envelope.iso(clock.now()); tv.configVersion = cfg.version; tv.appBuild = "0.5.0-lab";
        tv.radioState = "ready"; tv.transport = "online"; tv.timeQuality = "synced"; tv.freeStorage = 1_000_000_000L; tv.uptimeSeconds = 100;
        tv.health = Json.obj("mode", "integration-test", "pipeline", gp.stats(cursor), "dropped_reads", 0, "boot_id", BOOT, "transport_state", "online");
        check(api.call("POST", "/device/telemetry", Telemetry.body(tv), null).has("request_id"), "F: telemetry 0.5 diterima");

        // G. Galat terstruktur nyata: key salah → AUTH_INVALID → blokir; tanpa key → AUTH_REQUIRED
        Api bad = new Api(new Api.Settings() { public boolean simulation() { return false; } public String url() { return base; } public String token() { return "dk_salah"; } });
        Api.Failure f = null; try { bad.call("GET", "/device/config", null, null); } catch (Api.Failure x) { f = x; }
        check(f != null && "AUTH_INVALID".equals(f.code) && ErrorPolicy.classify(f.status, f.code, f.retryable) == ErrorPolicy.Action.AUTH_BLOCK, "G: AUTH_INVALID dari ERP → blokir provisioning");
        System.out.println("ERP_V2_AGENT_050_ASSERTIONS=" + passed);
    }
}
