package id.kubusteknologi.kn.u300.core;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

/**
 * Bacaan mentah ±N detik terakhir di RAM (audit §8.3). Inventory menyala terus, sehingga saat sinar A
 * terpotong lintasan bisa mengambil bacaan {@code pre_buffer_ms} sebelumnya (label depan terbaca sebelum
 * muatan masuk). Satu thread (kontrol); dibatasi umur dan jumlah.
 */
public final class RingBuffer {
    private final ArrayDeque<Sample> items = new ArrayDeque<>();
    private final long maxAgeMs;
    private final int maxCount;
    private long evicted;

    public RingBuffer(long maxAgeMs, int maxCount) {
        this.maxAgeMs = maxAgeMs;
        this.maxCount = Math.max(100, maxCount);
    }

    public void add(Sample s) {
        if (items.size() >= maxCount) { items.pollFirst(); evicted++; }
        items.addLast(s);
    }

    public void prune(long nowMono) {
        while (!items.isEmpty() && nowMono - items.peekFirst().tMono > maxAgeMs) items.pollFirst();
    }

    /** Bacaan dengan {@code from ≤ t ≤ to} (urutan masuk). */
    public List<Sample> between(long fromMono, long toMono) {
        List<Sample> out = new ArrayList<>();
        for (Sample s : items) if (s.tMono >= fromMono && s.tMono <= toMono) out.add(s);
        return out;
    }

    /** Jumlah bacaan kunci EPC×antena sebelum {@code beforeMono} yang masih ada di buffer. */
    public int countBefore(String key, long beforeMono) {
        int n = 0;
        for (Iterator<Sample> it = items.iterator(); it.hasNext(); ) {
            Sample s = it.next();
            if (s.tMono >= beforeMono) break;
            if (s.key().equals(key)) n++;
        }
        return n;
    }

    public int size() { return items.size(); }

    /** Bacaan yang terbuang karena buffer penuh (bukan karena umur). */
    public long evicted() { return evicted; }

    public long oldestAgeMs(long nowMono) { return items.isEmpty() ? 0 : nowMono - items.peekFirst().tMono; }
}
