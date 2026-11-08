package id.kubusteknologi.kn.u300.core;

import java.util.Locale;

/** Pure policy: transport acceptance is never clearance. No Android or vendor dependency. */
public final class Safety {
    private Safety() {}

    /** Sama dengan server {@code services/epc.try_canonical}: buang spasi/-/:/_/., huruf besar, tepat 24 hex. */
    public static String canonicalEpc(String raw) {
        if (raw == null) return null;
        String s = raw.replaceAll("[\\s\\-:_.]", "").toUpperCase(Locale.ROOT);
        return s.matches("[0-9A-F]{24}") ? s : null;
    }

    public static boolean durableAck(String status, boolean durable) {
        return durable && ("accepted".equals(status) || "duplicate".equals(status));
    }

    public static long retryMillis(int attempts, long initial, long maximum) {
        long n = Math.max(1000, initial), cap = Math.max(n, maximum);
        for (int i = 0; i < Math.min(30, Math.max(0, attempts)); i++) n = n > cap / 2 ? cap : Math.min(cap, n * 2);
        return n;
    }

    /** Basis yang boleh menghasilkan hijau untuk seluruh lintasan. */
    public static boolean clearanceBasis(String basis) {
        return "manifest_full".equals(basis) || "document_session".equals(basis);
    }

    public static boolean greenAllowed(boolean live, boolean current, boolean complete,
            boolean allDurable, boolean finalDecision, boolean allow, boolean latched,
            boolean fresh, boolean matchingContext, String verdict, String basis) {
        // A per-EPC result does not clear an entire vehicle/passage. document_session (K-RFID-10) = trip parsial
        // hijau bila semua roll kuat milik dokumen aktif; sisa dinilai saat dokumen ditutup.
        return live && current && complete && allDurable && finalDecision && allow && !latched
                && fresh && matchingContext && "GREEN".equals(verdict)
                && clearanceBasis(basis);
    }

    public static final class Direction {
        private String first;
        private long firstAt;
        private boolean ambiguous;
        public void invalidate(){ambiguous=true;}
        public String edge(String sensor, long now, long window) {
            if(ambiguous)return "unknown";
            if (!"A".equals(sensor) && !"B".equals(sensor)) return "unknown";
            if (first == null) { first=sensor; firstAt=now; return "unknown"; }
            if (now-firstAt>window || now<firstAt) { ambiguous=true; return "unknown"; }
            if (first.equals(sensor)) return "unknown";
            if (ambiguous) return "unknown";
            String result="A".equals(first)?"out":"in";
            ambiguous=true; return result;
        }
    }
}
