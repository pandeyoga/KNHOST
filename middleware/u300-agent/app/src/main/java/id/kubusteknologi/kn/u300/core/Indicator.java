package id.kubusteknologi.kn.u300.core;

/**
 * Indikator gate 4 GPO (AUD-MW-14, K-RFID-09): hijau / kuning / merah / buzzer. Merah = kunci gate dari ERP
 * (pelanggaran) dan selalu menang; hijau & kuning hanya untuk keputusan segar lintasan terakhir dan dibatasi
 * waktu monotonik; tanpa izin = semua padam (UNKNOWN bukan izin bergerak).
 */
public final class Indicator {
    private Indicator() {}

    public static final String GREEN = "GREEN", YELLOW = "YELLOW", RED = "RED", UNKNOWN = "UNKNOWN";

    public static String signal(boolean latched, boolean halted, long nowMono, long greenUntil, long yellowUntil) {
        if (latched) return RED;
        if (halted) return UNKNOWN;
        if (nowMono < greenUntil) return GREEN;
        if (nowMono < yellowUntil) return YELLOW;
        return UNKNOWN;
    }

    /** @return {hijau, kuning, merah, buzzer}. */
    public static boolean[] outputs(String signal, boolean buzzer) {
        return new boolean[]{GREEN.equals(signal), YELLOW.equals(signal), RED.equals(signal), buzzer};
    }

    public static String label(String signal) {
        switch (signal) {
            case GREEN: return "HIJAU — loloskan";
            case YELLOW: return "KUNING — jalan, masuk antrean periksa";
            case RED: return "MERAH — tahan, gate terkunci";
            default: return "PADAM — belum ada izin";
        }
    }
}
