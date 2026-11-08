package id.kubusteknologi.kn.u300.core;

import java.util.List;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Antrean RAM terbatas antara callback SDK dan thread kontrol (AUD-MW-24). {@link #offer} tidak pernah
 * memblok: bila penuh, bacaan dihitung sebagai {@code dropped_reads} (telemetry) dan lintasan aktif ditandai
 * capture tidak lengkap oleh pemanggil.
 */
public final class ReadQueue<T> {
    private final ArrayBlockingQueue<T> queue;
    private final AtomicLong offered = new AtomicLong(), dropped = new AtomicLong();

    public ReadQueue(int capacity) {
        queue = new ArrayBlockingQueue<>(Math.max(16, capacity));
    }

    public boolean offer(T item) {
        offered.incrementAndGet();
        if (queue.offer(item)) return true;
        dropped.incrementAndGet();
        return false;
    }

    public int drainTo(List<T> out, int max) { return queue.drainTo(out, max); }

    public int size() { return queue.size(); }

    public long offered() { return offered.get(); }

    public long dropped() { return dropped.get(); }

    public void clear() { queue.clear(); }
}
