package id.kubusteknologi.kn.u300.core;

/**
 * Debounce sinar photo-eye dari polling GPI (AUD-MW-19). Perubahan level diterima bila bertahan
 * {@code minBlockMs} (bebas → terhalang) atau {@code minClearMs} (terhalang → bebas; lebih panjang agar celah
 * kaki stacker/garpu tidak memecah lintasan). Cap waktu tepi = saat level mentah pertama kali berubah.
 * Sampel pertama hanya menjadi baseline (tanpa tepi).
 */
public final class BeamDebouncer {
    /** Tepi sinar yang sudah di-debounce. */
    public static final class Edge {
        public final String sensor;      // "A" (mulut masuk) | "B" (mulut keluar)
        public final boolean blocked;
        public final long tMono;
        public Edge(String sensor, boolean blocked, long tMono) {
            this.sensor = sensor;
            this.blocked = blocked;
            this.tMono = tMono;
        }
        @Override public String toString() { return sensor + (blocked ? "↓" : "↑") + "@" + tMono; }
    }

    private final String sensor;
    private final long minBlockMs, minClearMs;
    private boolean known, stable, raw;
    private long rawSince, stableSince;

    public BeamDebouncer(String sensor, long minBlockMs, long minClearMs) {
        this.sensor = sensor;
        this.minBlockMs = Math.max(0, minBlockMs);
        this.minClearMs = Math.max(0, minClearMs);
    }

    /** @return tepi bila level stabil berubah, selain itu null. */
    public Edge sample(boolean blocked, long tMono) {
        if (!known) {
            known = true;
            stable = raw = blocked;
            rawSince = stableSince = tMono;
            return null;
        }
        if (blocked != raw) { raw = blocked; rawSince = tMono; }
        if (raw != stable && tMono - rawSince >= (raw ? minBlockMs : minClearMs)) {
            stable = raw;
            stableSince = rawSince;
            return new Edge(sensor, stable, rawSince);
        }
        return null;
    }

    public boolean known() { return known; }

    public boolean blocked() { return stable; }

    /** Waktu level stabil saat ini dimulai (untuk deteksi sinar macet). */
    public long since() { return stableSince; }

    public void reset() { known = false; }
}
