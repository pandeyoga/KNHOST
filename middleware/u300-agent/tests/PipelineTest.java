package id.kubusteknologi.kn.u300;

import id.kubusteknologi.kn.u300.core.*;
import org.json.*;

import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/**
 * Uji ujung-ke-ujung agent 0.5 di host (tanpa perangkat): profil simulasi 2.1 → debounce photo-eye → GatePipeline →
 * TagSummary → multi-batch (seq/boot_id) → simulator ERP → close 2.1 → keputusan (hijau trip parsial, kuning, batal,
 * cadangan RF) → aturan hijau/kuning agent. Payload hasilnya ditambahkan ke tests/contract-fixtures.json untuk divalidasi
 * terhadap kontrak 2.1 oleh validate_contract.py.
 */
public final class PipelineTest {
    static int checks;
    static void check(boolean v, String label) { checks++; if (!v) throw new AssertionError("check " + checks + ": " + label); }
    static final long W0 = 1_800_000_000_000L;

    static final class Mem implements GatePipeline.Store {
        int n;
        final Map<String, List<JSONObject>> edges = new LinkedHashMap<>(), drafts = new LinkedHashMap<>(), summaries = new LinkedHashMap<>();
        final Map<String, PassageMachine.Closing> closings = new LinkedHashMap<>();
        final Map<String, Boolean> complete = new LinkedHashMap<>();
        final Map<String, PassageMachine.Opening> openings = new LinkedHashMap<>();
        final List<String> health = new ArrayList<>();
        public String newPassageId() { return "pass-" + (++n); }
        public void opened(String id, PassageMachine.Opening o) { openings.put(id, o); }
        public void edge(String id, JSONObject e) { edges.computeIfAbsent(id, k -> new ArrayList<>()).add(e); }
        public void checkpoint(String id, List<JSONObject> d) { drafts.computeIfAbsent(id, k -> new ArrayList<>()).addAll(d); }
        public void closed(String id, PassageMachine.Closing c, List<JSONObject> s, boolean ok) { closings.put(id, c); summaries.put(id, s); complete.put(id, ok); }
        public void health(String h, String d, long t) { health.add(h + ":" + d); }
        String last() { String l = null; for (String k : closings.keySet()) l = k; return l; }
    }

    /** Linimasa simulasi: bacaan & level sinar, diproses seperti loop kontrol (poll tiap 20 ms, urut waktu). */
    static final class Rig {
        final Config cfg; final Mem mem = new Mem(); final GatePipeline gp; final BeamDebouncer da, db;
        final TreeMap<Long, List<RawRead>> reads = new TreeMap<>();
        final TreeMap<Long, boolean[]> beams = new TreeMap<>();   // t → {A terhalang, B terhalang}
        boolean a, b; boolean gpiBroken; long t;
        Rig(Config cfg, long start) {
            this.cfg = cfg; t = start;
            gp = new GatePipeline(cfg.pipeline, mem, mono -> mono + W0, mono -> true);
            da = new BeamDebouncer("A", cfg.minBlockMs, cfg.minClearMs); db = new BeamDebouncer("B", cfg.minBlockMs, cfg.minClearMs);
        }
        void read(long at, String epc, String ant, String rssi) { reads.computeIfAbsent(at, k -> new ArrayList<>()).add(new RawRead(epc, "TID", ant, rssi, at * 1_000_000L, W0 + at)); }
        void beam(long at, Boolean blockA, Boolean blockB) { beams.put(at, new boolean[]{blockA == null ? beamAt(at, 0) : blockA, blockB == null ? beamAt(at, 1) : blockB}); }
        boolean beamAt(long at, int i) { Map.Entry<Long, boolean[]> e = beams.floorEntry(at); return e != null && e.getValue()[i]; }
        void run(long until) {
            for (; t <= until; t += cfg.gpiPollMs) {
                List<Object> ev = new ArrayList<>();
                for (List<RawRead> list : reads.subMap(t - cfg.gpiPollMs, false, t, true).values()) for (RawRead r : list) ev.add(gp.parse(r));
                if (gpiBroken) gp.sensorUnavailable(t, "uji");
                else {
                    BeamDebouncer.Edge ea = da.sample(beamAt(t, 0), t), eb = db.sample(beamAt(t, 1), t);
                    if (ea != null) ev.add(ea); if (eb != null) ev.add(eb);
                }
                ev.sort(Comparator.comparingLong(o -> o instanceof Sample ? ((Sample) o).tMono : ((BeamDebouncer.Edge) o).tMono));
                for (Object o : ev) { if (o instanceof Sample) gp.onSample((Sample) o); else gp.onEdge((BeamDebouncer.Edge) o); }
                gp.tick(t);
            }
        }
    }

    static String epc(int i) { return String.format(Locale.ROOT, "E20034120123456789AB%04X", i); }
    static String rssi(double v) { return String.format(new Locale("in", "ID"), "%.2f", v); }   // "-48,50" (locale Indonesia)

    static JSONObject meta(Config c, String id, String mode, String basis) {
        return Json.obj("config_version", c.version, "logical_gate_id", c.gateId, "completion_basis", basis, "direction", c.direction,
                "profile_id", c.raw.optString("hardware_profile_id"), "opened_at", Json.now(), "sensor_mode", c.sensorMode, "boot_id", "boot-uji");
    }

    /** Kirim seluruh bukti lintasan lewat beberapa envelope (multi-batch); @return {body pertama, respons pertama, jumlah batch}. */
    static Object[] transmit(Api api, Config c, String pid, JSONObject meta, List<JSONObject> edges, List<JSONObject> sums, int maxBody, long[] seq) throws Exception {
        List<Batcher.Item> pending = new ArrayList<>();
        for (JSONObject e : edges) pending.add(new Batcher.Item(Batcher.EDGE, e.getString("edge_id"), e));
        for (JSONObject s : sums) pending.add(new Batcher.Item(Batcher.SUMMARY, s.getString("summary_id"), s));
        JSONObject firstBody = null, firstResponse = null; int batches = 0; Set<String> acked = new HashSet<>();
        while (!pending.isEmpty()) {
            String batchId = UUID.randomUUID().toString();
            JSONObject base = Envelope.eventsBase(batchId, pid, meta, "live", 0, "boot-uji", Json.now());
            List<Batcher.Item> fit = Batcher.fit(pending, base, c.maxEvents, maxBody);
            check(!fit.isEmpty(), "multi-batch: tiap putaran memuat item");
            base.put("seq", seq[0]++).put("boot_id", "boot-uji");
            JSONObject body = Batcher.build(base, fit);
            check(Batcher.size(body) <= maxBody, "multi-batch: body ≤ max_body_bytes");
            JSONObject res = api.call("POST", "/events", body, null);
            check(res.getLong("last_seq") == body.getLong("seq") && !res.getBoolean("seq_gap"), "multi-batch: seq berurut tanpa celah");
            for (String k : new String[]{"summary_acks", "edge_acks"}) {
                JSONArray a = res.optJSONArray(k);
                if (a != null) for (int i = 0; i < a.length(); i++) {
                    JSONObject x = a.getJSONObject(i);
                    boolean received = Safety.durableAck(x.getString("status"), x.getBoolean("durable")) || ("quarantined".equals(x.getString("status")) && x.getBoolean("durable"));
                    if (received) acked.add(x.getString("item_id"));
                }
            }
            if (firstBody == null) { firstBody = body; firstResponse = res; }
            pending.removeAll(fit);
            batches++;
        }
        check(acked.size() == edges.size() + sums.size(), "multi-batch: semua item ACK durable");
        return new Object[]{firstBody, firstResponse, batches};
    }

    static JSONObject close(Config c, Rig rig, String pid, JSONObject meta) throws Exception {
        PassageMachine.Closing cl = rig.mem.closings.get(pid);
        JSONObject body = Envelope.close(meta, cl, mono -> mono + W0, rig.mem.complete.get(pid), "live", "boot-uji", Json.obj("a", c.pinA, "b", c.pinB), c.activeState);
        body.put("observed_summary_count", rig.mem.summaries.get(pid).size()).put("observed_edge_count", rig.mem.edges.getOrDefault(pid, Collections.emptyList()).size());
        // closing_captured_at dari jam uji (W0 + mono) jauh di masa depan bagi simulator — pakai sekarang agar keputusan segar.
        body.put("closing_captured_at", Json.now());
        return body;
    }

    public static void main(String[] args) throws Exception {
        Config cfg = new Config(Config.simulation(), "SIM-GATE", true);
        check(cfg.pipeline.mode == PassageMachine.Mode.ONE_WAY_BEAM && "one_way_beam".equals(cfg.sensorMode), "profil: photo-eye satu arah");
        check(cfg.antennas.size() == 3 && "atas".equals(cfg.positions.get("1")) && "kanan".equals(cfg.positions.get("3")), "profil: peta port → atas/kiri/kanan");
        check(cfg.pipeline.machine.preBufferMs == 3000 && cfg.pipeline.bucketMs == 250 && cfg.gpiPollMs == 20 && cfg.minBlockMs == 50, "profil: parameter titik awal");
        check(cfg.yellowOut == 2 && cfg.buzzerOut == 4 && cfg.indicatorsEnabled, "profil: 4 GPO hijau/kuning/merah/buzzer");

        // ============ Lintasan 1: muatan lewat (photo-eye), label depan sebelum A↓, tag rak latar, RSSI koma, N/A, antena tak terpetakan
        long T = 100_000;
        Rig rig = new Rig(cfg, T);
        String bg = epc(0xFFF), front = epc(0x100);
        for (long k = 0; k <= 16_000; k += 300) rig.read(T + k, bg, "ANT3", rssi(-70.1 - (k % 900) / 300.0));
        for (long k = 6_000; k <= 10_600; k += 150) rig.read(T + k, front, "01", rssi(-66 + (k - 6000) / 400.0));
        for (int i = 1; i <= 5; i++) for (long k = -1200; k <= 1200; k += 120) {
            long at = T + 11_200 + k + i * 10; double r = -45 - Math.abs(k) / 100.0 - i * 0.3;
            rig.read(at, epc(i), i % 2 == 0 ? "2" : "1", rssi(r));
            if (k % 360 == 0) rig.read(at + 5, epc(i), "ANT3", rssi(r - 7));
        }
        rig.read(T + 11_000, epc(9), "1", "N/A");
        rig.read(T + 11_050, epc(10), "ANT9", rssi(-50));
        rig.read(T + 11_100, "XYZ-RUSAK", "2", rssi(-49));
        rig.beam(T + 10_000, true, false); rig.beam(T + 11_100, null, true); rig.beam(T + 11_800, false, null); rig.beam(T + 12_600, null, false);
        rig.run(T + 16_000);
        check(rig.mem.closings.size() == 1, "lintasan 1: satu lintasan");
        String p1 = rig.mem.last(); PassageMachine.Closing c1 = rig.mem.closings.get(p1);
        check("BEAM_A".equals(c1.openReason) && "EXITED".equals(c1.closeReason) && "sensor".equals(c1.boundaryReason), "lintasan 1: BEAM_A → EXITED");
        check(c1.preBufferMs == 3000 && Math.abs(c1.tailMs - 1500) <= cfg.gpiPollMs && "ok".equals(c1.sensorHealth), "lintasan 1: pre_buffer/tail/kesehatan");
        check(rig.mem.complete.get(p1), "lintasan 1: capture lengkap");
        check(rig.mem.edges.get(p1).size() == 4, "lintasan 1: 4 tepi sinar tercatat");
        check(rig.mem.drafts.containsKey(p1) && !rig.mem.drafts.get(p1).isEmpty(), "lintasan 1: draf ringkasan tersimpan (pemulihan crash)");
        Map<String, JSONObject> byId = new HashMap<>();
        for (JSONObject s : rig.mem.summaries.get(p1)) byId.put(s.getString("summary_id"), s);
        check(byId.size() == rig.mem.summaries.get(p1).size(), "lintasan 1: summary_id unik");
        long aDown = c1.aBlocked, bUp = c1.bCleared, windowStart = c1.windowStartMono;
        JSONObject fs = byId.get(p1 + ":" + front + ":1");
        check(fs != null && fs.getLong("first_seen_mono") < aDown && fs.getLong("first_seen_mono") >= windowStart, "lintasan 1: label depan dari pre-buffer (sebelum A↓)");
        check(fs.getInt("reads_before_window") > 0 && Boolean.FALSE.equals(fs.get("in_background")), "lintasan 1: label depan bukan latar");
        JSONObject bs = byId.get(p1 + ":" + bg + ":3");
        check(bs != null && Boolean.TRUE.equals(bs.get("in_background")), "lintasan 1: tag rak = latar (in_background true)");
        JSONObject l1 = byId.get(p1 + ":" + epc(1) + ":1");
        check(l1 != null && l1.getDouble("peak_rssi") > -47 && l1.getLong("t_peak_mono") >= aDown && l1.getLong("t_peak_mono") <= bUp, "lintasan 1: puncak RSSI di antara A↓ dan B↑");
        check(l1.getJSONArray("buckets").length() >= 8 && l1.getJSONArray("buckets").length() <= 400 && "synced".equals(l1.getString("time_quality")), "lintasan 1: bucket 250 ms");
        check(byId.containsKey(p1 + ":" + epc(1) + ":3"), "lintasan 1: antena atas (port 3) terpisah per antena");
        check(byId.get(p1 + ":" + epc(9) + ":1").isNull("peak_rssi"), "lintasan 1: RSSI N/A → null, bacaan tetap terhitung");
        check(byId.containsKey(p1 + ":" + epc(10) + ":9"), "lintasan 1: antena tak terpetakan tetap dikirim (server mengkarantina)");
        boolean rawBad = false; for (JSONObject s : rig.mem.summaries.get(p1)) if (s.isNull("epc") && "XYZ-RUSAK".equals(s.getString("raw_epc"))) rawBad = true;
        check(rawBad, "lintasan 1: EPC rusak tetap dikirim mentah");
        JSONObject st = rig.gp.stats(T + 16_000);
        check(st.getLong("rssi_missing") == 1 && st.getLong("antenna_unmapped") == 1 && st.getLong("epc_invalid") == 1 && st.getLong("rssi_invalid") == 0, "telemetry: penghitung parse");
        check(st.getBoolean("background_warm") && st.getInt("background_size") >= 1, "telemetry: daftar latar hangat");

        // Transport: multi-batch dengan body kecil, seq/boot_id, simulator ERP 2.1
        Api api = new Api(new Api.Settings() { public boolean simulation() { return true; } public String url() { return ""; } public String token() { return ""; } });
        long[] seq = {0};
        JSONObject m1 = meta(cfg, p1, "live", "document_session");
        Object[] tx = transmit(api, cfg, p1, m1, rig.mem.edges.get(p1), rig.mem.summaries.get(p1), 4000, seq);
        check((Integer) tx[2] >= 3, "multi-batch: beberapa envelope per lintasan (" + tx[2] + ")");
        JSONObject firstBatch = (JSONObject) tx[0];
        check(firstBatch.has("gpi_edges") && firstBatch.getString("boot_id").equals("boot-uji") && firstBatch.getLong("seq") == 0, "multi-batch: tepi di envelope pertama, seq mulai 0");
        JSONObject close1 = close(cfg, rig, p1, m1);
        check("BEAM_A".equals(close1.getString("open_reason")) && "EXITED".equals(close1.getString("close_reason")) && close1.getJSONObject("beam_times").has("b_cleared"), "close 2.1: open/close_reason & beam_times");
        check("fixed_profile".equals(close1.getJSONObject("direction_evidence").getString("source")) && "out".equals(close1.getString("direction")), "close 2.1: arah dari profil");
        api.simulationPending = 3;
        JSONObject d1 = api.call("POST", "/passages/" + p1 + "/close", close1, "key-1");
        check("GREEN".equals(d1.getString("verdict")) && "document_session".equals(d1.getString("completion_basis")) && d1.getJSONObject("counts").getInt("pending") == 3, "keputusan: hijau trip parsial (sisa 3)");
        JSONObject gs = api.call("GET", "/device/gate-state?logical_gate_id=SIM-GATE&local_passage_id=" + p1, null, null);
        long now = Json.time(gs.getString("server_time"));
        check(DecisionPolicy.validGreen(gs, d1, m1, p1, "live", now, 5000), "agent: hijau document_session walau sisa > 0 (K-RFID-10)");
        check(!DecisionPolicy.validGreen(gs, d1, meta(cfg, p1, "live", "manifest_full"), p1, "live", now, 5000), "agent: basis profil ≠ keputusan → tidak hijau");
        JSONObject fullPending = Json.parse(d1.toString()); fullPending.put("completion_basis", "manifest_full");
        check(!DecisionPolicy.validGreen(gs, fullPending, meta(cfg, p1, "live", "manifest_full"), p1, "live", now, 5000), "agent: manifest_full + sisa > 0 → tidak hijau (aturan 0.4)");
        check(!DecisionPolicy.validYellow(gs, d1, m1, p1, "live", now, 5000), "agent: hijau bukan kuning");
        check(api.call("POST", "/passages/" + p1 + "/close", close1, "key-1").getString("decision_id").equals(d1.getString("decision_id")), "close idempoten");

        // ============ Lintasan 2: kuning (REVIEW) — barang jalan, tanpa kunci
        rig.beam(T + 20_000, true, false); rig.beam(T + 21_000, null, true); rig.beam(T + 21_700, false, null); rig.beam(T + 22_400, null, false);
        for (int i = 20; i < 23; i++) for (long k = 20_000; k <= 22_400; k += 200) rig.read(T + k, epc(i), "1", rssi(-48));
        rig.run(T + 25_000);
        String p2 = rig.mem.last(); JSONObject m2 = meta(cfg, p2, "live", "document_session");
        transmit(api, cfg, p2, m2, rig.mem.edges.get(p2), rig.mem.summaries.get(p2), cfg.maxBody, seq);
        api.verdict = "REVIEW";
        JSONObject d2 = api.call("POST", "/passages/" + p2 + "/close", close(cfg, rig, p2, m2), "key-2");
        JSONObject gs2 = api.call("GET", "/device/gate-state?logical_gate_id=SIM-GATE&local_passage_id=" + p2, null, null);
        long now2 = Json.time(gs2.getString("server_time"));
        check("REVIEW".equals(d2.getString("verdict")) && !d2.getBoolean("latched") && "YELLOW".equals(d2.getString("indicator")), "keputusan: REVIEW kuning tanpa kunci");
        check(DecisionPolicy.validYellow(gs2, d2, m2, p2, "live", now2, 5000) && !DecisionPolicy.validGreen(gs2, d2, m2, p2, "live", now2, 5000), "agent: kuning, bukan hijau");
        check(!DecisionPolicy.validYellow(gs2, d2, m2, p2, "backfill", now2, 5000), "agent: kuning hanya untuk lintasan live");

        // ============ Lintasan 3: mundur dengan roll → REVERSED (cancelled)
        api.verdict = "GREEN";
        rig.beam(T + 30_000, true, false); rig.beam(T + 31_100, null, true); rig.beam(T + 31_700, null, false); rig.beam(T + 32_300, false, null);
        for (long k = 30_000; k <= 32_300; k += 200) rig.read(T + k, epc(30), "2", rssi(-50));
        rig.run(T + 34_000);
        String p3 = rig.mem.last(); JSONObject m3 = meta(cfg, p3, "live", "document_session");
        check("REVERSED".equals(rig.mem.closings.get(p3).closeReason), "lintasan 3: REVERSED");
        transmit(api, cfg, p3, m3, rig.mem.edges.get(p3), rig.mem.summaries.get(p3), cfg.maxBody, seq);
        JSONObject close3 = close(cfg, rig, p3, m3);
        check("cancelled".equals(close3.getString("boundary_reason")), "close: mundur = boundary cancelled");
        JSONObject d3 = api.call("POST", "/passages/" + p3 + "/close", close3, "key-3");
        check("CANCELLED".equals(d3.getString("verdict")) && "OFF".equals(d3.getString("indicator")), "keputusan (simulator): mundur → CANCELLED");

        // ============ Lintasan 4: orang lewat tanpa tag → lintasan kosong (CANCELLED tanpa alarm)
        rig.beam(T + 40_000, true, false); rig.beam(T + 40_900, null, true); rig.beam(T + 41_300, false, null); rig.beam(T + 41_900, null, false);
        rig.run(T + 44_000);
        String p4 = rig.mem.last(); JSONObject m4 = meta(cfg, p4, "live", "document_session");
        List<JSONObject> s4 = new ArrayList<>(); for (JSONObject s : rig.mem.summaries.get(p4)) if (!Boolean.TRUE.equals(s.get("in_background"))) s4.add(s);
        check(s4.isEmpty(), "lintasan 4: hanya tag latar");
        transmit(api, cfg, p4, m4, rig.mem.edges.get(p4), Collections.emptyList(), cfg.maxBody, seq);
        JSONObject close4 = close(cfg, rig, p4, m4); close4.put("observed_summary_count", 0);
        check("CANCELLED".equals(api.call("POST", "/passages/" + p4 + "/close", close4, "key-4").getString("verdict")), "keputusan (simulator): kosong → CANCELLED");

        // ============ Lintasan 5: sinar A macet → SENSOR_FAULT → cadangan RF (bukan berhenti)
        rig.beam(T + 50_000, true, false); rig.beam(T + 51_000, null, true);   // stacker berhenti di dalam gate
        rig.run(T + 50_000 + 30_000 + 100);          // TIMEOUT dulu
        check("TIMEOUT".equals(rig.mem.closings.get(rig.mem.last()).closeReason), "macet: lintasan TIMEOUT");
        rig.run(T + 50_000 + cfg.pipeline.machine.sensorStuckMs + 100);
        check(rig.mem.health.size() == 1 && rig.mem.health.get(0).startsWith("fault:BEAM_STUCK") && rig.gp.machine().rfLogicActive(), "macet: fault → cadangan RF");
        long r0 = T + 100_000;
        for (int i = 50; i < 54; i++) for (long k = 0; k <= 1800; k += 150) rig.read(r0 + k + i, epc(i), "1", rssi(-47));
        rig.run(r0 + 6000);
        String p5 = rig.mem.last(); PassageMachine.Closing c5 = rig.mem.closings.get(p5);
        check("RF_FALLBACK".equals(c5.openReason) && "SENSOR_FAULT".equals(c5.closeReason) && "fault".equals(c5.sensorHealth), "cadangan RF: RF_FALLBACK → SENSOR_FAULT");
        JSONObject m5 = meta(cfg, p5, "live", "document_session");
        transmit(api, cfg, p5, m5, rig.mem.edges.getOrDefault(p5, Collections.emptyList()), rig.mem.summaries.get(p5), cfg.maxBody, seq);
        JSONObject close5 = close(cfg, rig, p5, m5);
        JSONObject d5 = api.call("POST", "/passages/" + p5 + "/close", close5, "key-5");
        check("REVIEW".equals(d5.getString("verdict")), "keputusan (simulator): cadangan RF → kuning sampai terkalibrasi");

        // ============ GPI tidak terbaca → fault (bukan berhenti)
        Rig rig2 = new Rig(cfg, 500_000); rig2.gpiBroken = true; rig2.run(500_100);
        check(rig2.gp.machine().rfLogicActive() && rig2.mem.health.get(0).startsWith("fault:GPI_UNAVAILABLE"), "GPI hilang: cadangan RF");

        // ============ Galat terstruktur dari simulator → ErrorPolicy
        for (String[] sc : new String[][]{{"admin-disabled", "ADMIN_DISABLED"}, {"config-required", "CONFIG_REQUIRED"}, {"auth-invalid", "AUTH_BLOCK"}}) {
            api.scenario = sc[0]; Api.Failure f = null;
            try { api.call("GET", "/device/config", null, null); } catch (Api.Failure e) { f = e; }
            check(f != null && ErrorPolicy.classify(f.status, f.code, f.retryable).name().equals(sc[1]), "galat terstruktur: " + sc[0]);
            if (!"auth-invalid".equals(sc[0])) check(f.pollAfter == 60_000 && Boolean.TRUE.equals(f.retryable), "galat terstruktur: poll_after & retryable " + sc[0]);
        }
        Api.Failure parsed = Api.failure(403, 0, Json.obj("detail", Json.obj("code", "ADMIN_DISABLED", "message", "x", "retryable", true, "details", Json.obj("poll_after_seconds", 30))));
        check("ADMIN_DISABLED".equals(parsed.code) && parsed.pollAfter == 30_000 && parsed.retryable, "galat: parse detail.code/details");
        check(Api.failure(403, 0, Json.obj("detail", "Forbidden")).code.isEmpty() && Api.failure(502, 0, null).status == 502, "galat: detail teks / tanpa body");
        api.scenario = "overflow";
        JSONObject ov = api.call("POST", "/events", Json.obj("batch_id", "ov", "context", Json.obj("local_passage_id", "pov"), "events", new JSONArray(), "tag_summaries", new JSONArray().put(Json.obj("summary_id", "pov:x", "epc", epc(1)))), null);
        JSONObject ovAck = ov.getJSONArray("summary_acks").getJSONObject(0);
        check("quarantined".equals(ovAck.getString("status")) && ovAck.getBoolean("durable") && "CAPTURE_OVERFLOW".equals(ovAck.getJSONObject("error").getString("code")), "luapan: ACK quarantined durable CAPTURE_OVERFLOW");

        // ============ Telemetry 0.5
        Telemetry.Values tv = new Telemetry.Values();
        tv.eventId = UUID.randomUUID().toString(); tv.capturedAt = Json.now(); tv.configVersion = cfg.version; tv.appBuild = "0.5.0-lab"; tv.radioState = "ready"; tv.transport = "online"; tv.timeQuality = "synced";
        tv.pendingCount = 0; tv.pendingBytes = 0; tv.freeStorage = 1_000_000; tv.uptimeSeconds = 100; tv.lastErrorMessage = "";
        tv.health = Json.obj("mode", "simulation", "dropped_reads", 0, "pipeline", rig.gp.stats(T + 60_000), "boot_id", "boot-uji", "transport_state", "online", "config", cfg.summary());
        JSONObject telemetry = Telemetry.body(tv);
        check(telemetry.isNull("last_error") && telemetry.getJSONObject("platform_health").getJSONObject("pipeline").has("rssi_missing"), "telemetry: penghitung 0.5");

        // ============ Fixture untuk validasi skema kontrak 2.1
        Path fx = Paths.get(args[0]);
        JSONObject fixtures = Json.parse(new String(Files.readAllBytes(fx), StandardCharsets.UTF_8));
        fixtures.put("DeviceConfig#sim_050", Config.simulation())
                .put("EventsRequest#ringkasan_photo_eye", firstBatch).put("EventsResponse#ringkasan", tx[1])
                .put("PassageClose#photo_eye_exited", close1).put("PassageClose#mundur", close3).put("PassageClose#kosong", close4).put("PassageClose#cadangan_rf", close5)
                .put("GateDecision#sesi_dokumen_parsial", d1).put("GateDecision#kuning", d2).put("GateDecision#batal", d3).put("GateState#sesudah_lintasan", gs)
                .put("TagSummary#latar", bs).put("TagSummary#label_depan", fs).put("GpiEdge#a_blocked", rig.mem.edges.get(p1).get(0)).put("Telemetry#agent_050", telemetry);
        Files.write(fx, fixtures.toString(2).getBytes(StandardCharsets.UTF_8));
        System.out.println("PASS: " + checks + " end-to-end pipeline/transport/decision assertions; 2.1 fixtures exported.");
    }
}
