package id.kainnusantara.handheld.core;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Agregasi bacaan RF per EPC selama satu jendela pindai (callback SDK hanya menyalin string ke sini — tanpa I/O).
 * Bacaan berulang dibedakan dari EPC unik (spesifikasi Kubus 02 §2.10): {@link #totalReads()} vs {@link #unique()}.
 * EPC tidak kanonik TIDAK dibuang — dicatat apa adanya (tampil sebagai asing).
 */
public final class ReadAggregator {
    public static final class Tag {
        public final String epc;
        public final boolean valid;
        public String tid;
        public Double rssiMax, rssiLast;
        public int count;
        public long firstWall, lastWall, firstMono, lastMono;

        Tag(String epc, boolean valid) { this.epc = epc; this.valid = valid; }

        Tag copy() {
            Tag t = new Tag(epc, valid);
            t.tid = tid; t.rssiMax = rssiMax; t.rssiLast = rssiLast; t.count = count;
            t.firstWall = firstWall; t.lastWall = lastWall; t.firstMono = firstMono; t.lastMono = lastMono;
            return t;
        }
    }

    public static final Comparator<Tag> STRONGEST = (a, b) -> {
        double ra = a.rssiMax == null ? -999 : a.rssiMax, rb = b.rssiMax == null ? -999 : b.rssiMax;
        int c = Double.compare(rb, ra);
        return c != 0 ? c : Integer.compare(b.count, a.count);
    };

    private final Map<String, Tag> tags = new LinkedHashMap<>();
    private long total, rssiMissing, rssiInvalid, blank;
    private final int cap;

    public ReadAggregator(int cap) { this.cap = Math.max(1, cap); }

    /** @return true bila EPC ini baru di jendela ini. Di atas kapasitas, EPC baru ditolak (bukan menimpa diam-diam). */
    public synchronized boolean offer(String rawEpc, String tid, String rawRssi, long monoMs, long wallMs) {
        String epc = Epc.normalizeRead(rawEpc);
        if (epc == null) { blank++; return false; }
        total++;
        int kind = Parse.rssiKind(rawRssi);
        if (kind == Parse.RSSI_MISSING) rssiMissing++;
        else if (kind == Parse.RSSI_INVALID) rssiInvalid++;
        Double r = Parse.rssi(rawRssi);
        Tag t = tags.get(epc);
        boolean fresh = t == null;
        if (fresh) {
            if (tags.size() >= cap) return false;
            t = new Tag(epc, Epc.valid(epc));
            t.firstWall = wallMs; t.firstMono = monoMs;
            tags.put(epc, t);
        }
        t.count++;
        t.lastWall = wallMs; t.lastMono = monoMs;
        if (tid != null && !tid.isEmpty()) t.tid = Parse.clip(tid, 64);
        if (r != null) {
            t.rssiLast = r;
            if (t.rssiMax == null || r > t.rssiMax) t.rssiMax = r;
        }
        return fresh;
    }

    public synchronized List<Tag> snapshot() {
        List<Tag> out = new ArrayList<>();
        for (Tag t : tags.values()) out.add(t.copy());
        return out;
    }

    public synchronized List<Tag> byStrength() {
        List<Tag> out = snapshot();
        Collections.sort(out, STRONGEST);
        return out;
    }

    public synchronized Set<String> epcs() { return new LinkedHashSet<>(tags.keySet()); }
    public synchronized Tag get(String epc) { Tag t = tags.get(epc); return t == null ? null : t.copy(); }
    public synchronized int unique() { return tags.size(); }
    public synchronized long totalReads() { return total; }
    public synchronized long rssiMissing() { return rssiMissing; }
    public synchronized long rssiInvalid() { return rssiInvalid; }
    public synchronized long blankReads() { return blank; }
    public synchronized boolean full() { return tags.size() >= cap; }

    public synchronized void clear() {
        tags.clear();
        total = rssiMissing = rssiInvalid = blank = 0;
    }

    /** Pulihkan draf pindai tersimpan (layar dibuka ulang / aplikasi mati sebelum konfirmasi). */
    public synchronized void restore(String epc, Double rssiMax, int count, long firstWall, long lastWall, String tid) {
        String e = Epc.normalizeRead(epc);
        if (e == null || tags.containsKey(e) || tags.size() >= cap) return;
        Tag t = new Tag(e, Epc.valid(e));
        t.rssiMax = rssiMax; t.rssiLast = rssiMax; t.count = Math.max(1, count); t.firstWall = firstWall; t.lastWall = lastWall; t.tid = tid;
        tags.put(e, t);
        total += t.count;
    }

    /** Hapus EPC tertentu (sudah dikirim dalam batch sebelumnya) tanpa mengosongkan statistik. */
    public synchronized void removeAll(Iterable<String> epcs) { for (String e : epcs) tags.remove(e); }
}
