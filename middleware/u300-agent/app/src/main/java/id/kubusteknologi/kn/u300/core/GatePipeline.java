package id.kubusteknologi.kn.u300.core;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Rantai pemrosesan gate di thread kontrol (audit §8.3): bacaan mentah → parse tahan-locale → RingBuffer →
 * BackgroundLearner (saat IDLE) → PassageMachine (photo-eye utama + cadangan RF) → Aggregator (TagSummary).
 * Persistensi lewat {@link Store} (Android: SQLite; tes host: memori). Tidak ada HTTP di sini.
 */
public final class GatePipeline implements PassageMachine.Listener {

    public interface Store {
        String newPassageId();
        /** Lintasan dibuka (tulis baris OPEN). */
        void opened(String passageId, PassageMachine.Opening o);
        /** Tepi sinar milik lintasan (item final, langsung siap kirim). */
        void edge(String passageId, JSONObject gpiEdge);
        /** Draf ringkasan (pemulihan bila proses mati di tengah lintasan). */
        void checkpoint(String passageId, List<JSONObject> drafts);
        /** Lintasan ditutup: ringkasan final + data batas lintasan. */
        void closed(String passageId, PassageMachine.Closing c, List<JSONObject> summaries, boolean captureComplete);
        void health(String health, String detail, long tMono);
    }

    public static final class Settings {
        public PassageMachine.Mode mode = PassageMachine.Mode.ONE_WAY_BEAM;
        public PassageMachine.Params machine = new PassageMachine.Params();
        public BackgroundLearner.Params learner = new BackgroundLearner.Params();
        public Set<String> antennas = new HashSet<>();
        public Map<String, Double> strongDbm = new HashMap<>();
        public double defaultStrongDbm = -65;
        public int bucketMs = 250, antennaBase = 1, maxAggregates = 20000, ringMaxCount = 200_000;
        public long ringMs = 10_000, checkpointMs = 1000;
    }

    private final Settings s;
    private final Store store;
    private final Envelope.Wall wall;
    private final ClockSyncView clock;
    private final RingBuffer ring;
    private final BackgroundLearner learner;
    private final PassageMachine machine;
    private String currentId;
    private Aggregator agg;
    private Map<String, Integer> readsBefore = new HashMap<>();
    private boolean complete;
    private int edgeSeq;
    private long lastCheckpoint, lastPrune;
    private final ArrayDeque<String> recentEdges = new ArrayDeque<>();
    // telemetry (AUD-MW-23)
    private long reads, rssiMissing, rssiInvalid, antennaInvalid, antennaUnmapped, epcInvalid, passages, orphanEdges;
    private String lastClose = "";

    /** Sumber status sinkron jam untuk menandai {@code time_quality} tiap bacaan. */
    public interface ClockSyncView { boolean synced(long mono); }

    public GatePipeline(Settings settings, Store store, Envelope.Wall wall, ClockSyncView clock) {
        this.s = settings;
        this.store = store;
        this.wall = wall;
        this.clock = clock;
        this.ring = new RingBuffer(settings.ringMs, settings.ringMaxCount);
        this.learner = new BackgroundLearner(settings.learner);
        this.machine = new PassageMachine(settings.mode, settings.machine, this);
    }

    public PassageMachine machine() { return machine; }
    public BackgroundLearner learner() { return learner; }
    public RingBuffer ring() { return ring; }
    public String currentPassage() { return currentId; }

    public double threshold(String antenna) {
        Double v = s.strongDbm.get(antenna);
        return v != null ? v : s.defaultStrongDbm;
    }

    /** Parse bacaan mentah SDK. Cap waktu utama = monotonik saat callback (ms). */
    public Sample parse(RawRead r) {
        reads++;
        long mono = r.monoNanos / 1_000_000L;
        String raw = r.epc == null ? "" : r.epc;
        String epc = Safety.canonicalEpc(raw);
        if (epc == null) epcInvalid++;
        int kind = Parse.rssiKind(r.rssi);
        if (kind == Parse.RSSI_MISSING) rssiMissing++;
        else if (kind == Parse.RSSI_INVALID) rssiInvalid++;
        String ant = Parse.antenna(r.antenna, s.antennaBase);
        boolean known = ant != null && s.antennas.contains(ant);
        if (ant == null) { antennaInvalid++; ant = "raw:" + Parse.clip(r.antenna, 24); }
        else if (!known) antennaUnmapped++;
        return new Sample(raw, epc, ant, known, Parse.rssi(r.rssi), r.rssi, mono, wall.at(mono), clock.synced(mono));
    }

    public void onRead(RawRead r) { onSample(parse(r)); }

    public void onSample(Sample smp) {
        boolean strong = smp.rssi == null || smp.rssi >= threshold(smp.antenna);
        boolean background = learner.isBackgroundSample(smp);
        machine.rf(smp, strong, background);      // bisa membuka (benih dari ring) atau menutup (timeout) lintasan
        if (agg != null) agg.add(smp);
        else learner.observeIdle(smp);
        ring.add(smp);
    }

    public void onEdge(BeamDebouncer.Edge e) {
        machine.tick(e.tMono);
        String before = currentId;
        if (before != null) recordEdge(before, e);
        machine.edge(e);
        if (before == null && currentId != null) recordEdge(currentId, e);
        if (before == null && currentId == null) {
            orphanEdges++;
            remember("di luar lintasan " + e);
        }
    }

    private void recordEdge(String pid, BeamDebouncer.Edge e) {
        remember(e.toString());
        store.edge(pid, Envelope.edge(pid, edgeSeq++, e, wall.at(e.tMono), clock.synced(e.tMono)));
    }

    private void remember(String text) {
        if (recentEdges.size() >= 40) recentEdges.pollFirst();
        recentEdges.addLast(text);
    }

    public void tick(long now) {
        machine.tick(now);
        learner.tick(now, currentId == null);
        if (now - lastPrune >= 1000) {
            ring.prune(now);
            if (now - lastPrune >= 60_000 || lastPrune == 0) learner.prune(now);
            lastPrune = now;
        }
        if (agg != null && now - lastCheckpoint >= s.checkpointMs) {
            lastCheckpoint = now;
            List<JSONObject> drafts = new ArrayList<>();
            for (Aggregator.Acc a : agg.takeDirty()) drafts.add(agg.summary(a, null, readsBefore.getOrDefault(a.key, 0)));
            if (!drafts.isEmpty()) store.checkpoint(currentId, drafts);
        }
    }

    /** Bukti lintasan aktif hilang (antrean RAM penuh, gagal simpan, offline di tengah) → capture tidak lengkap. */
    public void markIncomplete() { if (currentId != null) complete = false; }

    public void manualClose(long now) { machine.manualClose(now); }

    public void sensorUnavailable(long now, String why) { machine.sensorUnavailable(now, why); }

    // ------------------------------------------------------------------ PassageMachine.Listener

    @Override public void opened(PassageMachine.Opening o) {
        currentId = store.newPassageId();
        agg = new Aggregator(currentId, o.windowStartMono, s.bucketMs, s.maxAggregates);
        complete = true;
        edgeSeq = 0;
        lastCheckpoint = o.tOpenMono;
        readsBefore = new HashMap<>();
        for (Sample old : ring.between(Long.MIN_VALUE, o.windowStartMono - 1)) readsBefore.merge(old.key(), 1, Integer::sum);
        for (Sample old : ring.between(o.windowStartMono, Long.MAX_VALUE)) agg.add(old);
        passages++;
        store.opened(currentId, o);
    }

    @Override public void closed(PassageMachine.Closing c) {
        String pid = currentId;
        Aggregator a = agg;
        currentId = null;
        agg = null;
        List<JSONObject> out = new ArrayList<>();
        Set<String> notBackground = new HashSet<>();
        for (Aggregator.Acc acc : a.all()) {
            Boolean bg = learner.inBackground(acc.epc, acc.antenna, acc.peak(), a.windowStartMono());
            if (acc.epc != null && Boolean.FALSE.equals(bg)) notBackground.add(acc.epc);
            out.add(a.summary(acc, bg, readsBefore.getOrDefault(acc.key, 0)));
        }
        for (String epc : notBackground) learner.release(epc);   // melonjak / antena lain → lepas dari daftar latar
        boolean ok = complete && !a.overflowed() && !c.merged;
        lastClose = c.closeReason != null ? c.closeReason : c.boundaryReason;
        store.closed(pid, c, out, ok);
    }

    @Override public void health(String health, String detail, long tMono) {
        remember("sensor " + health + ": " + detail);
        store.health(health, detail, tMono);
    }

    // ------------------------------------------------------------------ telemetry

    public JSONObject stats(long now) {
        JSONObject o = new JSONObject();
        try {
            o.put("reads", reads).put("rssi_missing", rssiMissing).put("rssi_invalid", rssiInvalid)
                    .put("antenna_invalid", antennaInvalid).put("antenna_unmapped", antennaUnmapped).put("epc_invalid", epcInvalid)
                    .put("passages_opened", passages).put("orphan_edges", orphanEdges)
                    .put("ring_size", ring.size()).put("ring_evicted", ring.evicted()).put("ring_age_ms", ring.oldestAgeMs(now))
                    .put("background_size", learner.size()).put("background_warm", learner.warm())
                    .put("background_released", learner.released()).put("background_chronic", learner.chronic(5))
                    .put("machine_mode", machine.mode().name()).put("machine_state", machine.state().name())
                    .put("sensor_health", machine.health()).put("sensor_fault_detail", machine.faultDetail())
                    .put("sensor_anomalies", machine.anomalies()).put("last_close", lastClose)
                    .put("recent_edges", new JSONArray(new ArrayList<>(recentEdges)));
        } catch (JSONException e) {
            throw new IllegalStateException(e);
        }
        return o;
    }
}
