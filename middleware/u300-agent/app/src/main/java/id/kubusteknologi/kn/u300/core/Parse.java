package id.kubusteknologi.kn.u300.core;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Parse nilai mentah SDK yang formatnya bergantung locale/firmware (AUD-MW-23, uji meja K-RFID-03 butir 1–2).
 * SDK membentuk RSSI dengan {@code "-" + new DecimalFormat("##0.00")} TANPA Locale [AAR]: locale id-ID
 * menghasilkan {@code "-58,30"}; di luar rentang SDK mengirim {@code "N/A"}. Format antena belum pasti
 * ("1", "01", "ANT1"). Tidak ada nilai yang dibuang diam-diam: yang gagal di-parse dihitung di telemetry.
 */
public final class Parse {
    private Parse() {}

    public static final int RSSI_OK = 0;
    public static final int RSSI_MISSING = 1;
    public static final int RSSI_INVALID = 2;
    /** Rentang wajar dBm untuk reader UHF; di luar ini dianggap rusak (bukan sinyal). */
    public static final double RSSI_MIN = -150, RSSI_MAX = 30;

    private static final Pattern NUMBER = Pattern.compile("^[+-]?\\d{1,3}(\\.\\d+)?$");
    private static final Pattern ANTENNA = Pattern.compile("^(?:ANTENNA|ANT|PORT|A)?[\\s_\\-#:]*0*(\\d{1,3})$");

    /** Klasifikasi RSSI mentah: {@link #RSSI_OK}, {@link #RSSI_MISSING} (kosong/N/A) atau {@link #RSSI_INVALID}. */
    public static int rssiKind(String raw) {
        String s = normalizeRssi(raw);
        if (s == null) return RSSI_MISSING;
        if (!NUMBER.matcher(s).matches()) return RSSI_INVALID;
        double v = Double.parseDouble(s);
        return Double.isFinite(v) && v >= RSSI_MIN && v <= RSSI_MAX ? RSSI_OK : RSSI_INVALID;
    }

    /** RSSI dBm atau null bila kosong/N/A/tidak valid. "-58,30" → -58.3; "−58.3 dBm" → -58.3. */
    public static Double rssi(String raw) {
        if (rssiKind(raw) != RSSI_OK) return null;
        return Double.parseDouble(normalizeRssi(raw));
    }

    private static String normalizeRssi(String raw) {
        if (raw == null) return null;
        String s = raw.trim().replace('\u2212', '-').replace('\u00a0', ' ');
        String upper = s.toUpperCase(Locale.ROOT);
        if (upper.endsWith("DBM")) s = s.substring(0, s.length() - 3).trim();
        s = s.replace(" ", "");
        if (s.isEmpty()) return null;
        upper = s.toUpperCase(Locale.ROOT);
        if (upper.equals("N/A") || upper.equals("NA") || upper.equals("NULL") || upper.equals("NAN") || upper.equals("-")) return null;
        boolean comma = s.indexOf(',') >= 0, dot = s.indexOf('.') >= 0;
        if (comma && dot) return s + "#";            // pemisah ribuan tidak mungkin pada RSSI → tidak valid
        if (comma) {
            if (s.indexOf(',') != s.lastIndexOf(',')) return s + "#";
            s = s.replace(',', '.');
        }
        return s;
    }

    /**
     * Nomor port antena kanonik "1".."16" atau null. Menerima "1", "01", "ANT1", "Ant 01", "ANT_2", "port3".
     * {@code base} = indeks port pertama yang dilaporkan firmware (1 bila 1-based; 0 bila firmware 0-based —
     * ditetapkan dari uji meja butir 1).
     */
    public static String antenna(String raw, int base) {
        if (raw == null) return null;
        String s = raw.trim().toUpperCase(Locale.ROOT);
        Matcher m = ANTENNA.matcher(s);
        if (!m.matches()) return null;
        int n = Integer.parseInt(m.group(1)) - base + 1;
        return n >= 1 && n <= 16 ? String.valueOf(n) : null;
    }

    public static String antenna(String raw) { return antenna(raw, 1); }

    /** Kunci pendek & stabil untuk EPC mentah yang tidak kanonik (summary_id ≤ 160 karakter). */
    public static String rawKey(String raw) {
        try {
            byte[] d = MessageDigest.getInstance("SHA-256").digest((raw == null ? "" : raw).getBytes(StandardCharsets.UTF_8));
            StringBuilder b = new StringBuilder("raw-");
            for (int i = 0; i < 8; i++) b.append(String.format(Locale.ROOT, "%02x", d[i]));
            return b.toString();
        } catch (Exception e) {
            throw new IllegalStateException(e);
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
