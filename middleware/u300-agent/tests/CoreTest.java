import id.kubusteknologi.kn.u300.core.*;
import org.json.JSONArray;
import org.json.JSONObject;

import java.net.ServerSocket;
import java.util.*;

/** Kelas inti 0.5 tanpa Android: parse tahan-locale, buffer, daftar latar, ringkasan, batch, galat, jam, indikator, radio. */
public class CoreTest {
    static int checks;
    static void check(boolean v, String label) { checks++; if (!v) throw new AssertionError("check " + checks + ": " + label); }
    static final long W = 1_800_000_000_000L;
    static Sample s(String epc, String ant, Double rssi, long t) { return new Sample(epc, epc, ant, true, rssi, String.valueOf(rssi), t, W + t, true); }

    public static void main(String[] args) throws Exception {
        // ---- AUD-MW-23: RSSI tahan locale
        check(Parse.rssi("-58,30") == -58.3, "RSSI koma (locale id-ID)");
        check(Parse.rssi("-58.30") == -58.3 && Parse.rssi(" -61 ") == -61.0, "RSSI titik/spasi");
        check(Parse.rssi("−58.3 dBm") == -58.3, "RSSI minus unicode + satuan");
        check(Parse.rssi("N/A") == null && Parse.rssiKind("N/A") == Parse.RSSI_MISSING, "RSSI N/A → null, missing");
        check(Parse.rssi(null) == null && Parse.rssiKind("") == Parse.RSSI_MISSING, "RSSI kosong");
        check(Parse.rssiKind("-1.058,3") == Parse.RSSI_INVALID && Parse.rssiKind("abc") == Parse.RSSI_INVALID, "RSSI rusak");
        check(Parse.rssiKind("-58,3,1") == Parse.RSSI_INVALID && Parse.rssiKind("-999") == Parse.RSSI_INVALID, "RSSI koma ganda / luar rentang");
        check(Parse.rssiKind("NaN") == Parse.RSSI_MISSING, "RSSI NaN");
        // ---- format antena
        for (String raw : new String[]{"1", "01", "ANT1", "ant1", "Ant 01", "ANT_1", "port1", " 1 ", "ANTENNA1"}) check("1".equals(Parse.antenna(raw)), "antena " + raw);
        check("16".equals(Parse.antenna("ANT16")) && Parse.antenna("17") == null && Parse.antenna("0") == null, "antena batas 1..16");
        check("1".equals(Parse.antenna("0", 0)) && "4".equals(Parse.antenna("ANT3", 0)), "antena 0-based");
        check(Parse.antenna("X1") == null && Parse.antenna(null) == null && Parse.antenna("") == null, "antena rusak");
        check(Parse.rawKey("zz").startsWith("raw-") && Parse.rawKey("zz").length() == 20, "kunci EPC mentah pendek");
        // ---- EPC kanonik sama dengan server (services/epc.try_canonical)
        check("E20034120123456789ABCDEF".equals(Safety.canonicalEpc("e200-3412-0123-4567-89ab-cdef")), "EPC pemisah");
        check(Safety.canonicalEpc("E2003412") == null, "EPC pendek");

        // ---- ReadQueue: penuh → dropped_reads (AUD-MW-24)
        ReadQueue<Integer> q = new ReadQueue<>(16);
        for (int i = 0; i < 20; i++) q.offer(i);
        List<Integer> drained = new ArrayList<>(); q.drainTo(drained, 100);
        check(q.dropped() == 4 && q.offered() == 20 && drained.size() == 16 && drained.get(0) == 0, "antrean RAM: 4 dibuang & dihitung");

        // ---- RingBuffer
        RingBuffer ring = new RingBuffer(10_000, 100);
        for (int i = 0; i < 150; i++) ring.add(s("E20000000000000000000001", "1", -50.0, i * 100));
        check(ring.size() == 100 && ring.evicted() == 50, "ring: batas jumlah");
        ring.prune(14_900 + 10_000 - 4000); check(ring.between(0, Long.MAX_VALUE).get(0).tMono >= 10_900, "ring: batas umur");
        check(ring.countBefore("E20000000000000000000001:1", 12_000) == 11, "ring: hitung sebelum jendela");

        // ---- BackgroundLearner (daftar latar)
        BackgroundLearner.Params bp = new BackgroundLearner.Params(); bp.warmupMs = 3000;
        BackgroundLearner bl = new BackgroundLearner(bp);
        String rack = "E20000000000000000000AAA";
        check(bl.inBackground(rack, "3", -70.0, 10_000) == null, "latar: belum hangat → null");
        for (long t = 0; t <= 6000; t += 200) { bl.tick(t, true); bl.observeIdle(s(rack, "3", -70.0, t)); }
        check(bl.warm() && bl.size() == 1, "latar: hangat & terisi");
        check(Boolean.TRUE.equals(bl.inBackground(rack, "3", -68.0, 12_000)), "latar: RSSI biasa → true");
        check(Boolean.FALSE.equals(bl.inBackground(rack, "3", -55.0, 12_000)), "latar: melonjak ≥ 10 dB → false");
        check(Boolean.FALSE.equals(bl.inBackground(rack, "1", -70.0, 12_000)), "latar: antena lain → false");
        check(Boolean.FALSE.equals(bl.inBackground("E20000000000000000000BBB", "3", -70.0, 12_000)), "latar: EPC baru → false");
        check(Boolean.FALSE.equals(bl.inBackground(rack, "3", -70.0, 1500)), "latar: baru muncul < min_span sebelum jendela (muatan mendekat) → false");
        check(bl.isBackgroundSample(s(rack, "3", -71.0, 12_000)) && !bl.isBackgroundSample(s(rack, "3", -50.0, 12_000)), "latar: sampel untuk cadangan RF");
        check(bl.chronic(5).getJSONObject(0).getString("epc").equals(rack), "latar: laporan kronis");
        bl.release(rack); check(bl.size() == 0 && bl.released() == 1, "latar: dilepas");
        bl.observeIdle(s(rack, "3", -70.0, 7000)); bl.prune(7000 + bp.retentionMs + 1); check(bl.size() == 0, "latar: retensi");

        // ---- Aggregator → TagSummary
        Aggregator ag = new Aggregator("p-1", 1000, 250, 10);
        double[] shape = {-70, -62, -55, -49, -46, -48, -55, -63};
        for (int i = 0; i < shape.length; i++) ag.add(s("E20000000000000000000001", "1", shape[i], 1000 + i * 260));
        ag.add(s("E20000000000000000000001", "1", null, 1000 + 8 * 260));
        ag.add(new Sample("bad-epc", null, "2", true, -50.0, "-50", 1500, W + 1500, false));
        check(ag.size() == 2 && ag.reads() == 10, "ringkasan: 2 kombinasi, 10 bacaan");
        Aggregator.Acc acc = null; for (Aggregator.Acc x : ag.all()) if (x.epc != null) acc = x;
        JSONObject sm = ag.summary(acc, false, 4);
        check(sm.getString("summary_id").equals("p-1:E20000000000000000000001:1") && sm.getInt("count") == 9, "ringkasan: id & count (termasuk tanpa RSSI)");
        check(sm.getDouble("peak_rssi") == -46.0 && sm.getLong("t_peak_mono") == 1000 + 4 * 260, "ringkasan: puncak & t_peak monotonik");
        check(sm.getLong("first_seen_mono") == 1000 && sm.getLong("last_seen_mono") == 1000 + 8 * 260, "ringkasan: first/last mono");
        check(Math.abs(sm.getDouble("mean_rssi") - (-56.0)) < 0.01, "ringkasan: rata-rata RSSI tanpa null");
        JSONArray bk = sm.getJSONArray("buckets");
        check(bk.length() == 9 && bk.getJSONObject(0).getInt("t_off") == 0 && bk.getJSONObject(4).getInt("t_off") == 1000, "ringkasan: bucket 250 ms");
        check(bk.getJSONObject(8).isNull("max_rssi") && bk.getJSONObject(8).getInt("n") == 1, "ringkasan: bucket tanpa RSSI = null");
        check(sm.getInt("reads_before_window") == 4 && "synced".equals(sm.getString("time_quality")) && !sm.getBoolean("in_background"), "ringkasan: before/time/bg");
        JSONObject bad = null; for (Aggregator.Acc x : ag.all()) if (x.epc == null) bad = ag.summary(x, null, 0);
        check(bad.isNull("epc") && bad.getString("raw_epc").equals("bad-epc") && bad.isNull("in_background") && "unsynced".equals(bad.getString("time_quality")), "ringkasan: EPC rusak tetap dikirim");
        check(ag.takeDirty().size() == 2 && ag.takeDirty().isEmpty(), "ringkasan: draf kotor sekali");
        Aggregator small = new Aggregator("p-2", 0, 250, 1); small.add(s("E20000000000000000000001", "1", -50.0, 0)); small.add(s("E20000000000000000000002", "1", -50.0, 0));
        check(small.overflowed(), "ringkasan: kapasitas RAM → overflow");

        // ---- Batcher (multi-batch, batas kontrak)
        JSONObject base = new JSONObject().put("schema_version", 2).put("batch_id", "b").put("mode", "live").put("config_version", "v")
                .put("context", new JSONObject().put("kind", "gate").put("logical_gate_id", "g").put("local_passage_id", "p")).put("events", new JSONArray());
        List<Batcher.Item> items = new ArrayList<>();
        for (int i = 0; i < 250; i++) items.add(new Batcher.Item(Batcher.EDGE, "e" + i, new JSONObject().put("edge_id", "e" + i)));
        for (int i = 0; i < 700; i++) items.add(new Batcher.Item(Batcher.SUMMARY, "s" + i, new JSONObject().put("summary_id", "s" + i)));
        List<Batcher.Item> fit = Batcher.fit(items, base, 100, 1_000_000);
        check(fit.size() == 200, "batch: tepi ≤ 200 per envelope");
        List<Batcher.Item> sums = items.subList(250, 950);
        check(Batcher.fit(sums, base, 100, 1_000_000).size() == 500, "batch: ringkasan ≤ 500 per envelope");
        List<Batcher.Item> tight = Batcher.fit(sums, base, 100, 2000);
        JSONObject built = Batcher.build(base, tight);
        check(!tight.isEmpty() && Batcher.size(built) <= 2000 && built.getJSONArray("tag_summaries").length() == tight.size(), "batch: ukuran ringkas ≤ max_body");
        check(built.getJSONArray("events").length() == 0 && !built.has("gpi_edges"), "batch: events wajib ada, tepi kosong tidak dikirim");
        List<Batcher.Item> big = Collections.singletonList(new Batcher.Item(Batcher.SUMMARY, "x", new JSONObject().put("pad", new String(new char[5000]).replace('\0', 'x'))));
        check(Batcher.fit(big, base, 100, 2048).isEmpty(), "batch: satu item terlalu besar → kosong (pemanggil memblokir)");

        // ---- ErrorPolicy (AUD-MW-06): dari detail.code, bukan status saja
        check(ErrorPolicy.classify(401, "AUTH_INVALID", false) == ErrorPolicy.Action.AUTH_BLOCK, "galat: AUTH_INVALID blokir");
        check(ErrorPolicy.classify(401, "AUTH_REQUIRED", false) == ErrorPolicy.Action.AUTH_BLOCK, "galat: AUTH_REQUIRED blokir");
        check(ErrorPolicy.classify(403, "ADMIN_DISABLED", true) == ErrorPolicy.Action.ADMIN_DISABLED, "galat: ADMIN_DISABLED polling lambat");
        check(ErrorPolicy.classify(409, "CONFIG_REQUIRED", true) == ErrorPolicy.Action.CONFIG_REQUIRED, "galat: CONFIG_REQUIRED polling lambat");
        check(ErrorPolicy.classify(403, "", null) == ErrorPolicy.Action.FORBIDDEN_UNKNOWN, "galat: 403 tanpa kode (proxy) tidak memblokir");
        check(ErrorPolicy.classify(413, "BATCH_TOO_LARGE", false) == ErrorPolicy.Action.SPLIT_BATCH, "galat: 413 pecah");
        check(ErrorPolicy.classify(503, "EVIDENCE_PENDING", true) == ErrorPolicy.Action.EVIDENCE_PENDING, "galat: EVIDENCE_PENDING");
        check(ErrorPolicy.classify(409, "PASSAGE_FROZEN", false) == ErrorPolicy.Action.PASSAGE_FROZEN, "galat: PASSAGE_FROZEN");
        check(ErrorPolicy.classify(409, "EVENT_ID_CONFLICT", false) == ErrorPolicy.Action.CONTRACT_BLOCK, "galat: konflik ID blokir kontrak");
        check(ErrorPolicy.classify(400, "INVALID_EVENTSREQUEST", false) == ErrorPolicy.Action.CONTRACT_BLOCK, "galat: INVALID_* blokir kontrak");
        check(ErrorPolicy.classify(409, "LATCH_BUSY", true) == ErrorPolicy.Action.RETRY, "galat: kode tak dikenal retryable → coba ulang");
        check(ErrorPolicy.classify(409, "", null) == ErrorPolicy.Action.CONTRACT_BLOCK && ErrorPolicy.classify(500, "", null) == ErrorPolicy.Action.RETRY, "galat: tanpa kode");
        check(ErrorPolicy.classify(429, "", null) == ErrorPolicy.Action.RETRY, "galat: 429");
        check(ErrorPolicy.delayMs(ErrorPolicy.Action.ADMIN_DISABLED, 0, 0, 2000) == 60_000, "galat: polling lambat bawaan 60 s");
        check(ErrorPolicy.delayMs(ErrorPolicy.Action.CONFIG_REQUIRED, 30_000, 0, 2000) == 30_000, "galat: poll_after_seconds dihormati");
        check(ErrorPolicy.delayMs(ErrorPolicy.Action.RETRY, 0, 5000, 2000) == 5000, "galat: Retry-After dihormati");

        // ---- ClockSync (AUD-MW-12)
        long[] mono = {10_000}; long[] dev = {W - 99_000};
        ClockSync cs = new ClockSync(new ClockSync.Source() { public long mono() { return mono[0]; } public long deviceWall() { return dev[0]; } }, 2000, 120_000);
        check(!cs.good(10_000) && cs.wallAt(10_000) == W - 99_000, "jam: belum sinkron → jam perangkat");
        check(cs.offer(W, 10_000, 10_200), "jam: sampel diterima");
        check(cs.wallAt(10_100) == W && cs.good(10_300), "jam: koreksi setengah RTT");
        check(!cs.offer(W + 5000, 11_000, 13_500), "jam: RTT > batas ditolak");
        check(!cs.offer(W + 5000, 11_000, 11_600), "jam: RTT jauh lebih buruk ditolak");
        check(cs.offer(W + 1000, 11_000, 11_150), "jam: RTT baik diterima");
        check(!cs.good(11_150 + 120_000), "jam: basi setelah 120 s");

        // ---- Indicator (AUD-MW-14, K-RFID-09)
        check(Indicator.signal(true, false, 5, 100, 100).equals(Indicator.RED), "indikator: kunci = merah menang");
        check(Indicator.signal(false, false, 5, 100, 0).equals(Indicator.GREEN) && Indicator.signal(false, false, 5, 0, 100).equals(Indicator.YELLOW), "indikator: hijau/kuning");
        check(Indicator.signal(false, true, 5, 100, 100).equals(Indicator.UNKNOWN) && Indicator.signal(false, false, 200, 100, 100).equals(Indicator.UNKNOWN), "indikator: jeda/kedaluwarsa = padam");
        boolean[] out = Indicator.outputs(Indicator.YELLOW, true); check(!out[0] && out[1] && !out[2] && out[3], "indikator: 4 GPO");

        // ---- RadioSetup (AUD-MW-04): set + baca ulang, fail-closed
        FakeRadio fr = new FakeRadio();
        JSONObject radio = new JSONObject().put("apply", true).put("region_code", 63).put("antenna_power_dbm", new JSONObject().put("1", 15).put("2", 16))
                .put("gen2", new JSONObject().put("query_session", 0).put("query_target", 0)).put("tag_focus", false).put("fast_id", false);
        JSONArray rep = RadioSetup.apply(fr, radio, Arrays.asList("1", "2"));
        check(fr.region == 63 && fr.power.get("1") == 15 && fr.power.get("2") == 16 && fr.gen2.get("query_session") == 0 && fr.tagFocus == 0, "radio: diterapkan");
        check(rep.length() == 6 && rep.getJSONObject(0).getBoolean("ok"), "radio: laporan per butir");
        FakeRadio stubborn = new FakeRadio(); stubborn.ignoreSets = true;
        check(fails(() -> RadioSetup.apply(stubborn, radio, Arrays.asList("1", "2"))), "radio: baca-balik beda → gagal (tidak mulai)");
        JSONObject verify = new JSONObject(radio.toString()).put("apply", false);
        check(fails(() -> RadioSetup.apply(new FakeRadio(), verify, Arrays.asList("1", "2"))), "radio: verifikasi saja + beda → gagal");
        FakeRadio ok = new FakeRadio(); RadioSetup.apply(ok, radio, Arrays.asList("1", "2"));
        check(RadioSetup.apply(ok, verify, Arrays.asList("1", "2")).length() == 6, "radio: verifikasi saja + sama → lolos");
        check(fails(() -> RadioSetup.apply(new FakeRadio(), new JSONObject().put("apply", true).put("gen2", new JSONObject().put("bogus", 1)), Arrays.asList("1"))), "radio: kunci Gen2 asing");
        check(fails(() -> RadioSetup.apply(new FakeRadio(), new JSONObject().put("apply", false).put("filter", new JSONObject().put("bank", 1).put("ptr", 32).put("len", 16).put("data", "E200")), Arrays.asList("1"))), "radio: filter tanpa apply");
        FakeRadio broken = new FakeRadio(); broken.tagFocus = -1;
        check(fails(() -> RadioSetup.apply(broken, new JSONObject().put("apply", true).put("tag_focus", false), Arrays.asList("1"))), "radio: TagFocus -1 → gagal");
        check(fails(() -> RadioSetup.apply(new FakeRadio(), new JSONObject().put("apply", true).put("antenna_power_dbm", new JSONObject().put("1", 15)), Arrays.asList("1", "3"))), "radio: daya port hilang");

        // ---- PortProbe (layanan UHF bawaan)
        try (ServerSocket server = new ServerSocket(0)) {
            int port = server.getLocalPort();
            List<Integer> open = PortProbe.open("127.0.0.1", new int[]{port, 1}, 200);
            check(open.size() == 1 && open.get(0) == port, "probe: port terbuka terdeteksi, tertutup tidak");
        }
        System.out.println("PASS: " + checks + " core (parse/buffer/latar/ringkasan/batch/galat/jam/indikator/radio) assertions");
    }

    interface Action { void run() throws Exception; }
    static boolean fails(Action a) { try { a.run(); return false; } catch (RadioSetup.Failure f) { return f.report.length() > 0; } catch (Exception e) { return false; } }

    static final class FakeRadio implements RadioSetup.Port {
        int region = 2, tagFocus = 1, fastId = 1, rfLink = 0;
        boolean ignoreSets;
        final Map<String, Integer> power = new HashMap<>();
        final Map<String, Integer> gen2 = new LinkedHashMap<>();
        FakeRadio() { power.put("1", 30); power.put("2", 30); power.put("3", 30); for (String k : RadioSetup.GEN2_KEYS) gen2.put(k, 1); }
        public int getRegion() { return region; }
        public boolean setRegion(int c) { if (!ignoreSets) region = c; return true; }
        public int getPower(String a) { return power.get(a); }
        public boolean setPower(String a, int d) { if (!ignoreSets) power.put(a, d); return true; }
        public Map<String, Integer> getGen2() { return new LinkedHashMap<>(gen2); }
        public boolean setGen2(Map<String, Integer> all) { if (!ignoreSets) gen2.putAll(all); return true; }
        public int getTagFocus() { return tagFocus; }
        public boolean setTagFocus(boolean on) { if (!ignoreSets && tagFocus >= 0) tagFocus = on ? 1 : 0; return true; }
        public int getFastId() { return fastId; }
        public boolean setFastId(boolean on) { if (!ignoreSets) fastId = on ? 1 : 0; return true; }
        public int getRfLink() { return rfLink; }
        public boolean setRfLink(int v) { if (!ignoreSets) rfLink = v; return true; }
        public boolean setFilter(int b, int p, int l, String d) { return true; }
    }
}
