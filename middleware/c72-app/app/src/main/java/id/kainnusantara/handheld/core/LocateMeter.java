package id.kainnusantara.handheld.core;

/**
 * Cari tag lewat sinyal = BANTUAN RELATIF (spesifikasi Kubus 02 §2.1): angka 0–100 makin besar makin dekat, bukan jarak.
 * Sumber: nilai {@code startLocation} SDK (0–100, belum terbukti di C72) atau cadangan RSSI pindai terfilter
 * (−80 dBm → 0, −30 dBm → 100). Dihaluskan EMA; jeda bunyi makin pendek makin dekat.
 */
public final class LocateMeter {
    private double ema = -1;
    private long lastSeenMs;
    private final double alpha;

    public LocateMeter(double alpha) { this.alpha = Math.max(0.05, Math.min(1, alpha)); }

    public static int fromRssi(Double dbm) {
        if (dbm == null) return 0;
        return (int) Math.round(Math.max(0, Math.min(100, (dbm + 80) * 2)));
    }

    public synchronized int offer(int raw, boolean valid, long nowMs) {
        if (!valid) return value(nowMs);
        int v = Math.max(0, Math.min(100, raw));
        ema = ema < 0 ? v : ema + alpha * (v - ema);
        lastSeenMs = nowMs;
        return (int) Math.round(ema);
    }

    /** Nilai turun ke 0 bila tag tidak terbaca > 1,5 dtk. */
    public synchronized int value(long nowMs) {
        if (ema < 0 || nowMs - lastSeenMs > 1500) return 0;
        return (int) Math.round(ema);
    }

    public static long beepIntervalMs(int value) {
        if (value <= 0) return 0;
        return Math.max(80, 1200 - value * 11L);
    }

    public static String label(int value) {
        if (value <= 0) return "Tidak terbaca";
        if (value < 30) return "Jauh";
        if (value < 60) return "Mendekat";
        if (value < 85) return "Dekat";
        return "Sangat dekat";
    }
}
