package id.kainnusantara.handheld.core;

import java.util.Locale;
import java.util.regex.Pattern;

/**
 * Parse nilai mentah SDK yang formatnya bergantung locale/firmware. DISALIN dari agent U300 0.5
 * ({@code id.kubusteknologi.kn.u300.core.Parse}, AUD-MW-23): SDK Chainway membentuk RSSI dengan
 * {@code "-" + new DecimalFormat("##0.00")} TANPA Locale — locale id-ID menghasilkan {@code "-58,30"}; di luar
 * rentang SDK mengirim {@code "N/A"}. Berlaku juga untuk {@code RFIDWithUHFUART} (C72) — belum terbukti di unit.
 */
public final class Parse {
    private Parse() {}

    public static final int RSSI_OK = 0;
    public static final int RSSI_MISSING = 1;
    public static final int RSSI_INVALID = 2;
    public static final double RSSI_MIN = -150, RSSI_MAX = 30;

    private static final Pattern NUMBER = Pattern.compile("^[+-]?\\d{1,3}(\\.\\d+)?$");

    public static int rssiKind(String raw) {
        String s = normalizeRssi(raw);
        if (s == null) return RSSI_MISSING;
        if (!NUMBER.matcher(s).matches()) return RSSI_INVALID;
        double v = Double.parseDouble(s);
        return !Double.isNaN(v) && !Double.isInfinite(v) && v >= RSSI_MIN && v <= RSSI_MAX ? RSSI_OK : RSSI_INVALID;
    }

    /** RSSI dBm atau null bila kosong/N/A/tidak valid. "-58,30" → -58.3; "−58.3 dBm" → -58.3. */
    public static Double rssi(String raw) {
        if (rssiKind(raw) != RSSI_OK) return null;
        return Double.parseDouble(normalizeRssi(raw));
    }

    private static String normalizeRssi(String raw) {
        if (raw == null) return null;
        String s = raw.trim().replace('−', '-').replace(' ', ' ');
        String upper = s.toUpperCase(Locale.ROOT);
        if (upper.endsWith("DBM")) s = s.substring(0, s.length() - 3).trim();
        s = s.replace(" ", "");
        if (s.isEmpty()) return null;
        upper = s.toUpperCase(Locale.ROOT);
        if (upper.equals("N/A") || upper.equals("NA") || upper.equals("NULL") || upper.equals("NAN") || upper.equals("-")) return null;
        boolean comma = s.indexOf(',') >= 0, dot = s.indexOf('.') >= 0;
        if (comma && dot) return s + "#";
        if (comma) {
            if (s.indexOf(',') != s.lastIndexOf(',')) return s + "#";
            s = s.replace(',', '.');
        }
        return s;
    }

    /** Angka desimal ketikan operator ("12,5" atau "12.5"); null bila bukan angka. */
    public static Double decimal(String raw) {
        if (raw == null) return null;
        String s = raw.trim().replace(" ", "");
        if (s.isEmpty()) return null;
        if (s.indexOf(',') >= 0 && s.indexOf('.') < 0) s = s.replace(',', '.');
        try {
            double v = Double.parseDouble(s);
            return Double.isNaN(v) || Double.isInfinite(v) ? null : v;
        } catch (NumberFormatException e) {
            return null;
        }
    }

    /** Teks aman untuk dikirim/ditampilkan: dipotong, karakter kontrol dibuang. */
    public static String clip(String raw, int max) {
        if (raw == null) return "";
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < raw.length() && b.length() < max; i++) {
            char c = raw.charAt(i);
            if (c >= 0x20 && c != 0x7f) b.append(c);
        }
        return b.toString();
    }
}
