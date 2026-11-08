package id.kubusteknologi.kn.u300.core;

/**
 * Pemetaan jam server ↔ jam monotonik perangkat (AUD-MW-12): disinkronkan dari SETIAP respons ERP yang
 * membawa {@code server_time} (bukan hanya config tiap 60 s). Koreksi setengah RTT; sampel dengan RTT jauh
 * lebih buruk dari sampel terakhir diabaikan kecuali sinkron sudah lama. Jam dinding Android tidak dipakai
 * untuk keputusan — hanya cadangan tampilan bila belum pernah sinkron.
 */
public final class ClockSync {
    public interface Source { long mono(); long deviceWall(); }

    private final Source source;
    private final long maxRttMs, staleMs;
    private long base, monoBase, syncedAt = -1, lastRtt = -1, samples, rejected;

    public ClockSync(Source source, long maxRttMs, long staleMs) {
        this.source = source;
        this.maxRttMs = maxRttMs;
        this.staleMs = staleMs;
    }

    /** @return true bila sampel dipakai. */
    public synchronized boolean offer(long remoteMs, long startMono, long endMono) {
        samples++;
        long rtt = endMono - startMono;
        if (remoteMs <= 0 || rtt < 0 || rtt > maxRttMs) { rejected++; return false; }
        boolean old = syncedAt < 0 || endMono - syncedAt > 30_000;
        if (!old && lastRtt >= 0 && rtt > lastRtt + 150) { rejected++; return false; }
        base = remoteMs;
        monoBase = startMono + rtt / 2;
        syncedAt = endMono;
        lastRtt = rtt;
        return true;
    }

    public synchronized boolean good(long nowMono) { return syncedAt >= 0 && nowMono - syncedAt < staleMs; }

    /** Jam server (perkiraan) pada waktu monotonik {@code mono}. */
    public synchronized long wallAt(long mono) {
        if (syncedAt < 0) return source.deviceWall() + (mono - source.mono());
        return base + (mono - monoBase);
    }

    public long now() { return wallAt(source.mono()); }

    public synchronized long ageMs(long nowMono) { return syncedAt < 0 ? -1 : nowMono - syncedAt; }
    public synchronized long lastRttMs() { return lastRtt; }
    public synchronized long samples() { return samples; }
    public synchronized long rejected() { return rejected; }
}
