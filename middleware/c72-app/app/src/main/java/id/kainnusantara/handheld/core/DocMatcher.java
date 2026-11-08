package id.kainnusantara.handheld.core;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * "Yang diharapkan vs terbaca" untuk satu dokumen, dihitung di perangkat (bisa offline). Hasil di layar = PERKIRAAN
 * lokal; hasil final tetap dari ERP (ACK batch). Status tiap baris punya ikon + teks (bukan warna saja).
 */
public final class DocMatcher {
    private DocMatcher() {}

    public enum Status {
        CONFLICT("!", "Konflik"), DONE("✓✓", "Sudah"), QUEUED("⟳", "Antre kirim"),
        READ("✓", "Terbaca"), MISSING("○", "Belum terbaca");
        public final String glyph, text;
        Status(String glyph, String text) { this.glyph = glyph; this.text = text; }
    }

    /** Status lokal per kode (EPC/label) dari antrean & ACK server. */
    public static final class Local {
        public final Set<String> queued = new LinkedHashSet<>();
        public final Set<String> acked = new LinkedHashSet<>();
        public final Map<String, String> conflicts = new LinkedHashMap<>();
    }

    public static final class RowView {
        public final Snapshot.Row row;
        public final Status status;
        public final String note;
        RowView(Snapshot.Row row, Status status, String note) { this.row = row; this.status = status; this.note = note; }
    }

    public static final class Result {
        public final List<RowView> rows;
        public final List<String> extra;
        public final List<String> toSend;
        public final List<String> labelsToSend;
        public final List<String> unknownLabels;
        public final int expected, read, missing, conflict, done;

        Result(List<RowView> rows, List<String> extra, List<String> toSend, List<String> labelsToSend, List<String> unknownLabels) {
            this.rows = Collections.unmodifiableList(rows);
            this.extra = Collections.unmodifiableList(extra);
            this.toSend = Collections.unmodifiableList(toSend);
            this.labelsToSend = Collections.unmodifiableList(labelsToSend);
            this.unknownLabels = Collections.unmodifiableList(unknownLabels);
            int r = 0, m = 0, c = 0, d = 0;
            for (RowView v : rows) {
                if (v.status == Status.MISSING) m++;
                else if (v.status == Status.CONFLICT) c++;
                else r++;
                if (v.status == Status.DONE) d++;
            }
            expected = rows.size(); read = r; missing = m; conflict = c; done = d;
        }

        public String summary() {
            return "Diharapkan " + expected + " · Terbaca " + read + " · Kurang " + missing + " · Lebih " + extra.size()
                    + (conflict > 0 ? " · Konflik " + conflict : "");
        }
    }

    public static Result match(Snapshot s, Collection<String> readEpcs, Collection<String> labels, Local local) {
        Local l = local == null ? new Local() : local;
        Set<String> reads = new LinkedHashSet<>(readEpcs == null ? Collections.<String>emptyList() : readEpcs);
        Set<String> labelSet = new LinkedHashSet<>();
        for (String x : labels == null ? Collections.<String>emptyList() : labels) {
            if (x != null && !x.trim().isEmpty()) labelSet.add(x.trim().toUpperCase(java.util.Locale.ROOT));
        }
        List<RowView> views = new ArrayList<>();
        Set<String> rowCodes = new LinkedHashSet<>();
        for (Snapshot.Row r : s.rows) {
            String label = r.rollNo.toUpperCase(java.util.Locale.ROOT);
            if (!r.epc.isEmpty()) rowCodes.add(r.epc);
            String conflict = first(l.conflicts, r.epc, label);
            Status st;
            if (conflict != null) st = Status.CONFLICT;
            else if (r.done() || has(l.acked, r.epc, label)) st = Status.DONE;
            else if (has(l.queued, r.epc, label)) st = Status.QUEUED;
            else if ((!r.epc.isEmpty() && reads.contains(r.epc)) || labelSet.contains(label) || matchesLabelEpc(r, labelSet)) st = Status.READ;
            else st = Status.MISSING;
            views.add(new RowView(r, st, conflict == null ? "" : conflict));
        }
        List<String> extra = new ArrayList<>();
        for (String e : reads) if (!rowCodes.contains(e)) extra.add(e);
        for (String e : l.queued) if (!rowCodes.contains(e) && s.byLabel(e) == null && !extra.contains(e) && Epc.valid(e)) extra.add(e);
        List<String> toSend = new ArrayList<>();
        for (String e : reads) if (!l.queued.contains(e) && !l.acked.contains(e) && !l.conflicts.containsKey(e)) toSend.add(e);
        List<String> labelsToSend = new ArrayList<>(), unknown = new ArrayList<>();
        for (String x : labelSet) {
            if (s.byLabel(x) == null && s.byEpc(x) == null) unknown.add(x);
            if (!l.queued.contains(x) && !l.acked.contains(x) && !l.conflicts.containsKey(x)) labelsToSend.add(x);
        }
        return new Result(views, extra, toSend, labelsToSend, unknown);
    }

    /** PA roll tanpa tag: item.epc = nomor roll (label QR) — label cocok lewat kolom epc juga. */
    private static boolean matchesLabelEpc(Snapshot.Row r, Set<String> labels) { return !r.epc.isEmpty() && labels.contains(r.epc); }

    private static boolean has(Set<String> set, String a, String b) {
        return (!a.isEmpty() && set.contains(a)) || (!b.isEmpty() && set.contains(b));
    }

    private static String first(Map<String, String> m, String a, String b) {
        if (!a.isEmpty() && m.containsKey(a)) return m.get(a);
        if (!b.isEmpty() && m.containsKey(b)) return m.get(b);
        return null;
    }
}
