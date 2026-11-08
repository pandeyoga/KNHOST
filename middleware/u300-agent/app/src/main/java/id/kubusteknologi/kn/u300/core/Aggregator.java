package id.kubusteknologi.kn.u300.core;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Ringkasan bacaan per lintasan × EPC × antena (AUD-MW-01, kontrak 2.1 {@code TagSummary}): jumlah baca,
 * RSSI puncak & rata-rata, waktu pertama/terakhir/puncak (monotonik + jam dinding), dan bucket
 * {@code bucket_ms} (bentuk sinyal naik–puncak–turun). Bukan dedup yang membuang bukti: setiap bacaan
 * terhitung. Satu {@code summary_id} stabil per kombinasi.
 */
public final class Aggregator {
    public static final int MAX_BUCKETS = 400;

    public static final class Acc {
        public final String key, rawEpc, epc, antenna;
        long firstMono, lastMono, firstWall, lastWall, tPeakMono, tPeakWall;
        Double peak;
        int count, nRssi;
        double sumRssi;
        boolean allSynced = true, dirty = true;
        final TreeMap<Integer, double[]> buckets = new TreeMap<>();

        Acc(Sample s) {
            key = s.key();
            rawEpc = s.rawEpc;
            epc = s.epc;
            antenna = s.antenna;
            firstMono = lastMono = s.tMono;
            firstWall = lastWall = s.tWall;
        }

        public Double peak() { return peak; }
        public int count() { return count; }
    }

    private final String passageId;
    private final long windowStartMono;
    private final int bucketMs, maxAccs;
    private final Map<String, Acc> accs = new LinkedHashMap<>();
    private boolean overflowed, bucketOverflow;
    private long reads;

    public Aggregator(String passageId, long windowStartMono, int bucketMs, int maxAccs) {
        this.passageId = passageId;
        this.windowStartMono = windowStartMono;
        this.bucketMs = Math.max(1, bucketMs);
        this.maxAccs = Math.max(1, maxAccs);
    }

    public long windowStartMono() { return windowStartMono; }

    public void add(Sample s) {
        Acc a = accs.get(s.key());
        if (a == null) {
            if (accs.size() >= maxAccs) { overflowed = true; return; }
            a = new Acc(s);
            accs.put(a.key, a);
        }
        reads++;
        a.count++;
        a.dirty = true;
        if (s.tMono < a.firstMono) { a.firstMono = s.tMono; a.firstWall = s.tWall; }
        if (s.tMono >= a.lastMono) { a.lastMono = s.tMono; a.lastWall = s.tWall; }
        a.allSynced &= s.synced;
        if (s.rssi != null) {
            a.sumRssi += s.rssi;
            a.nRssi++;
            if (a.peak == null || s.rssi > a.peak) { a.peak = s.rssi; a.tPeakMono = s.tMono; a.tPeakWall = s.tWall; }
        }
        int off = (int) (Math.max(0, s.tMono - windowStartMono) / bucketMs) * bucketMs;
        double[] b = a.buckets.get(off);
        if (b == null) {
            if (a.buckets.size() >= MAX_BUCKETS) { bucketOverflow = true; return; }
            b = new double[]{0, Double.NaN};
            a.buckets.put(off, b);
        }
        b[0]++;
        if (s.rssi != null && (Double.isNaN(b[1]) || s.rssi > b[1])) b[1] = s.rssi;
    }

    public Collection<Acc> all() { return accs.values(); }

    public List<Acc> takeDirty() {
        List<Acc> out = new ArrayList<>();
        for (Acc a : accs.values()) if (a.dirty) { a.dirty = false; out.add(a); }
        return out;
    }

    /** Kombinasi EPC×antena melebihi kapasitas RAM → capture tidak lengkap. */
    public boolean overflowed() { return overflowed; }
    public boolean bucketOverflow() { return bucketOverflow; }
    public int size() { return accs.size(); }
    public long reads() { return reads; }

    public String summaryId(Acc a) { return passageId + ":" + a.key; }

    static String iso(long ms) { return Instant.ofEpochMilli(ms).toString(); }

    private static Object num(Double v) {
        if (v == null || Double.isNaN(v) || Double.isInfinite(v)) return JSONObject.NULL;
        return Math.round(v * 100.0) / 100.0;
    }

    /** {@code TagSummary} kontrak 2.1 (semua field wajib terisi; nullable = JSON null). */
    public JSONObject summary(Acc a, Boolean inBackground, int readsBeforeWindow) {
        try {
            JSONArray buckets = new JSONArray();
            for (Map.Entry<Integer, double[]> e : a.buckets.entrySet()) {
                buckets.put(new JSONObject().put("t_off", e.getKey()).put("n", (int) e.getValue()[0])
                        .put("max_rssi", Double.isNaN(e.getValue()[1]) ? JSONObject.NULL : num(e.getValue()[1])));
            }
            JSONObject o = new JSONObject()
                    .put("summary_id", summaryId(a))
                    .put("raw_epc", Parse.clip(a.rawEpc, 1024))
                    .put("epc", a.epc == null ? JSONObject.NULL : a.epc)
                    .put("antenna", a.antenna)
                    .put("first_seen", iso(a.firstWall))
                    .put("last_seen", iso(a.lastWall))
                    .put("first_seen_mono", a.firstMono)
                    .put("last_seen_mono", a.lastMono)
                    .put("peak_rssi", num(a.peak))
                    .put("t_peak", a.peak == null ? JSONObject.NULL : iso(a.tPeakWall))
                    .put("t_peak_mono", a.peak == null ? JSONObject.NULL : (Object) a.tPeakMono)
                    .put("count", a.count)
                    .put("mean_rssi", a.nRssi == 0 ? JSONObject.NULL : num(a.sumRssi / a.nRssi))
                    .put("buckets", buckets)
                    .put("in_background", inBackground == null ? JSONObject.NULL : inBackground)
                    .put("reads_before_window", Math.max(0, readsBeforeWindow))
                    .put("time_quality", a.allSynced ? "synced" : "unsynced");
            return o;
        } catch (JSONException e) {
            throw new IllegalStateException(e);
        }
    }
}
