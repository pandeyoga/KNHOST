package id.kainnusantara.handheld.core;

import java.util.Locale;
import java.util.regex.Pattern;

/**
 * Kontrak EPC KNHOST yang SAMA dengan server ({@code backend/services/epc.py}, RF-01/RF-11): disimpan & dicocokkan
 * sebagai 24 hex HURUF BESAR tanpa pemisah. Tampilan berkelompok (E200-47AF-…) hanya untuk mata manusia.
 */
public final class Epc {
    private Epc() {}

    public static final int HEX_LEN = 24;
    private static final Pattern SEP = Pattern.compile("[\\s\\-:_.]");
    private static final Pattern HEX = Pattern.compile("^[0-9A-F]{24}$");

    /** Bentuk kanonik atau null bila bukan EPC-96 hex. */
    public static String canonical(String raw) {
        if (raw == null) return null;
        String s = SEP.matcher(raw).replaceAll("").toUpperCase(Locale.ROOT);
        return HEX.matcher(s).matches() ? s : null;
    }

    public static boolean valid(String raw) { return canonical(raw) != null; }

    /** Bacaan reader → kanonik, atau teks mentah huruf besar (EPC rusak tetap tercatat, tampil sebagai "asing"). */
    public static String normalizeRead(String raw) {
        if (raw == null) return null;
        String t = raw.trim();
        if (t.isEmpty()) return null;
        String c = canonical(t);
        return c != null ? c : Parse.clip(t.toUpperCase(Locale.ROOT), 128);
    }

    public static String display(String epc) {
        String s = canonical(epc);
        if (s == null) return epc == null ? "" : epc;
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < HEX_LEN; i += 4) {
            if (b.length() > 0) b.append('-');
            b.append(s, i, i + 4);
        }
        return b.toString();
    }

    /** 4 karakter terakhir — penanda singkat di layar kecil. */
    public static String tail(String epc) {
        String s = epc == null ? "" : epc;
        return s.length() <= 6 ? s : "…" + s.substring(s.length() - 6);
    }
}
