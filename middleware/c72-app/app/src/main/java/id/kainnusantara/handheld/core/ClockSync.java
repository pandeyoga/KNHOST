package id.kainnusantara.handheld.core;

/**
 * Pemetaan jam server ↔ jam monotonik perangkat. DISALIN dari agent U300 0.5
 * ({@code id.kubusteknologi.kn.u300.core.ClockSync}, AUD-MW-12): disinkronkan dari SETIAP respons ERP yang membawa
 * {@code server_time}; koreksi setengah RTT; sampel ber-RTT jauh lebih buruk diabaikan kecuali sinkron sudah lama.
 * Di C72 dipakai untuk cap waktu bacaan offline ({@code time_quality} = synced/device).
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

    public synchronized boolean everSynced() { return syncedAt >= 0; }

    public synchronized long wallAt(long mono) {
        if (syncedAt < 0) return source.deviceWall() + (mono - source.mono());
        return base + (mono - monoBase);
    }

    public long now() { return wallAt(source.mono()); }

    /** Perkiraan selisih jam server − jam perangkat (ms); 0 bila belum pernah sinkron. */
    public synchronized long offsetMs() {
        if (syncedAt < 0) return 0;
        long m = source.mono();
        return (base + (m - monoBase)) - source.deviceWall();
    }

    public synchronized long ageMs(long nowMono) { return syncedAt < 0 ? -1 : nowMono - syncedAt; }
    public synchronized long lastRttMs() { return lastRtt; }
    public synchronized long samples() { return samples; }
    public synchronized long rejected() { return rejected; }
}
