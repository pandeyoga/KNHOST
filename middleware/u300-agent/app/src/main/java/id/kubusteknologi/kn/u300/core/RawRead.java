package id.kubusteknologi.kn.u300.core;

/**
 * Salinan mentah satu callback SDK (AUD-MW-24): hanya string + cap waktu, dibuat di thread callback SDK
 * tanpa lock global, tanpa SQLite, tanpa parse. Parse & agregasi dikerjakan thread kontrol.
 */
public final class RawRead {
    public final String epc, tid, antenna, rssi;
    /** {@code SystemClock.elapsedRealtimeNanos()} saat callback (monotonik, AUD-MW-05). */
    public final long monoNanos;
    /** {@code System.currentTimeMillis()} saat callback (jam dinding perangkat, hanya diagnosis). */
    public final long deviceWallMs;

    public RawRead(String epc, String tid, String antenna, String rssi, long monoNanos, long deviceWallMs) {
        this.epc = epc;
        this.tid = tid;
        this.antenna = antenna;
        this.rssi = rssi;
        this.monoNanos = monoNanos;
        this.deviceWallMs = deviceWallMs;
    }
}
