package id.kubusteknologi.kn.u300.core;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;

/**
 * Daftar latar per gate (dokumen keputusan §4.1, usulan riset #9): EPC × antena yang terbaca saat gate KOSONG
 * (IDLE) beserta RSSI biasanya. Tag latar tidak membuka lintasan cadangan RF dan ditandai {@code in_background}
 * di ringkasan; ERP yang memutuskan. Lepas dari daftar bila sinyal melonjak jauh atau terlihat di antena yang
 * biasanya tidak melihatnya. Semua ambang = titik awal kalibrasi.
 */
public final class BackgroundLearner {
    public static final class Params {
        public long retentionMs = 86_400_000L;
        public int minReads = 3;
        public long minSpanMs = 2000;
        public double jumpDb = 10;
        public long warmupMs = 5000;
        public int maxEntries = 5000;
    }

    static final class Stat {
        int reads;
        long firstMono, lastMono;
        double maxRssi = Double.NEGATIVE_INFINITY, sumRssi;
        int nRssi;
    }

    private final Params p;
    private final Map<String, Map<String, Stat>> byEpc = new HashMap<>();
    private long idleObservedMs, lastIdleMono = -1;
    private long released;

    public BackgroundLearner(Params p) { this.p = p; }

    /** Panggil tiap tick; waktu IDLE kumulatif menentukan apakah daftar sudah "hangat" (warmup). */
    public void tick(long nowMono, boolean idle) {
        if (idle && lastIdleMono >= 0 && nowMono > lastIdleMono) idleObservedMs += Math.min(1000, nowMono - lastIdleMono);
        lastIdleMono = idle ? nowMono : -1;
    }

    public boolean warm() { return idleObservedMs >= p.warmupMs; }

    /** Bacaan saat gate kosong (tidak ada lintasan terbuka). */
    public void observeIdle(Sample s) {
        if (s.epc == null || !s.antennaKnown) return;
        Map<String, Stat> ants = byEpc.get(s.epc);
        if (ants == null) {
            if (byEpc.size() >= p.maxEntries) return;
            ants = new HashMap<>();
            byEpc.put(s.epc, ants);
        }
        Stat st = ants.get(s.antenna);
        if (st == null) { st = new Stat(); st.firstMono = s.tMono; ants.put(s.antenna, st); }
        st.reads++;
        st.lastMono = Math.max(st.lastMono, s.tMono);
        if (s.rssi != null) { st.maxRssi = Math.max(st.maxRssi, s.rssi); st.sumRssi += s.rssi; st.nRssi++; }
    }

    private Stat established(String epc, String antenna, long windowStartMono) {
        Map<String, Stat> ants = byEpc.get(epc);
        Stat st = ants == null ? null : ants.get(antenna);
        if (st == null || st.reads < p.minReads || st.lastMono - st.firstMono < p.minSpanMs) return null;
        // Sudah ada jauh sebelum jendela lintasan (bukan muatan yang sedang mendekat).
        if (st.firstMono > windowStartMono - p.minSpanMs) return null;
        if (windowStartMono - st.lastMono > p.retentionMs) return null;
        return st;
    }

    /**
     * Nilai {@code in_background} untuk ringkasan lintasan: null = belum punya info (belum hangat);
     * true = EPC×antena ini penghuni latar dan puncaknya tidak melonjak; false = bukan latar.
     */
    public Boolean inBackground(String epc, String antenna, Double peakRssi, long windowStartMono) {
        if (!warm()) return null;
        if (epc == null) return false;
        Stat st = established(epc, antenna, windowStartMono);
        if (st == null) return false;
        if (peakRssi == null || st.nRssi == 0) return true;
        return peakRssi < st.maxRssi + p.jumpDb;
    }

    /** Untuk cadangan RF: bacaan dari penghuni latar yang tidak melonjak tidak ikut rombongan pembuka. */
    public boolean isBackgroundSample(Sample s) {
        if (!warm() || s.epc == null) return false;
        Stat st = established(s.epc, s.antenna, s.tMono);
        if (st == null) return false;
        return s.rssi == null || st.nRssi == 0 || s.rssi < st.maxRssi + p.jumpDb;
    }

    /** Lepas EPC dari daftar latar (sinyal melonjak / terlihat di antena lain saat lintasan). */
    public void release(String epc) {
        if (byEpc.remove(epc) != null) released++;
    }

    public void prune(long nowMono) {
        for (Iterator<Map.Entry<String, Map<String, Stat>>> it = byEpc.entrySet().iterator(); it.hasNext(); ) {
            Map<String, Stat> ants = it.next().getValue();
            ants.values().removeIf(st -> nowMono - st.lastMono > p.retentionMs);
            if (ants.isEmpty()) it.remove();
        }
    }

    public int size() { return byEpc.size(); }

    public long released() { return released; }

    /** Penghuni latar "kronis" (paling sering terbaca) untuk dilaporkan ke supervisor (rak/barang dipindah). */
    public JSONArray chronic(int limit) {
        List<Object[]> rows = new ArrayList<>();
        for (Map.Entry<String, Map<String, Stat>> e : byEpc.entrySet()) {
            int reads = 0;
            double max = Double.NEGATIVE_INFINITY;
            JSONArray ants = new JSONArray();
            for (Map.Entry<String, Stat> a : e.getValue().entrySet()) {
                reads += a.getValue().reads;
                max = Math.max(max, a.getValue().maxRssi);
                ants.put(a.getKey());
            }
            rows.add(new Object[]{e.getKey(), reads, max, ants});
        }
        Collections.sort(rows, (x, y) -> Integer.compare((Integer) y[1], (Integer) x[1]));
        JSONArray out = new JSONArray();
        try {
            for (int i = 0; i < Math.min(limit, rows.size()); i++) {
                Object[] r = rows.get(i);
                double max = (Double) r[2];
                out.put(new JSONObject().put("epc", r[0]).put("reads", r[1])
                        .put("max_rssi", Double.isInfinite(max) ? JSONObject.NULL : max).put("antennas", r[3]));
            }
        } catch (JSONException e) {
            throw new IllegalStateException(e);
        }
        return out;
    }
}
