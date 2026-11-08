package id.kainnusantara.handheld.core;

/**
 * Penanganan galat ERP berdasarkan {@code detail.code} lalu status HTTP. Pola dari agent U300 0.5
 * ({@code id.kubusteknologi.kn.u300.core.ErrorPolicy}, AUD-MW-06) disesuaikan untuk handheld: dua identitas
 * (perangkat & pengguna) diblokir terpisah; konflik bisnis TIDAK diulang; galat sementara diulang dengan ID sama.
 */
public final class ErrorPolicy {
    private ErrorPolicy() {}

    public enum Action {
        /** Gangguan sementara (jaringan, 5xx, 429, permintaan sama sedang diproses) → ulang dengan ID SAMA. */
        RETRY,
        /** Sesi pengguna habis/ditolak → login ulang operator yang sama; antrean tetap. */
        LOGIN_REQUIRED,
        /** Device key ditolak/perangkat dicabut → provisioning ulang (ber-PIN); antrean tetap. */
        DEVICE_BLOCKED,
        /** Antrean milik operator lain → tunggu operator itu login. */
        OTHER_OPERATOR,
        /** ID sama dengan isi berbeda → kerusakan data lokal; perlu peninjauan ber-PIN (jangan ganti ID). */
        IDEMPOTENCY,
        /** Ditolak permanen (izin/cakupan/validasi) → tampilkan, jangan ulang. */
        REJECTED
    }

    public static Action classify(int status, String code, Boolean retryable) {
        String c = code == null ? "" : code;
        switch (c) {
            case "DEVICE_KEY_REQUIRED":
            case "DEVICE_KEY_INVALID":
            case "DEVICE_DISABLED":
            case "DEVICE_NOT_HANDHELD":
                return Action.DEVICE_BLOCKED;
            case "OPERATOR_MISMATCH":
                return Action.OTHER_OPERATOR;
            case "IDEMPOTENCY_CONFLICT":
                return Action.IDEMPOTENCY;
            case "REQUEST_IN_PROGRESS":
            case "SAGA_IN_PROGRESS":
            case "EPC_GENERATION_FAILED":
                return Action.RETRY;
            default:
                break;
        }
        if (status <= 0) return Action.RETRY;                   // jaringan putus / timeout
        if (status == 401) return Action.LOGIN_REQUIRED;        // sesi ERP pengguna (device key punya kode sendiri)
        if (status == 408 || status == 425 || status == 429 || status >= 500) return Action.RETRY;
        if (Boolean.TRUE.equals(retryable)) return Action.RETRY;
        return Action.REJECTED;
    }

    /** Jeda ulang eksponensial (2 dtk … maks) dengan jitter ±20 %; menghormati Retry-After server. */
    public static long backoffMs(int attempts, long maxMs, long retryAfterMs, double jitter01) {
        long base = 2000L << Math.min(Math.max(attempts - 1, 0), 10);
        long capped = Math.min(maxMs, base);
        long withJitter = (long) (capped * (0.8 + 0.4 * Math.max(0, Math.min(1, jitter01))));
        return Math.max(withJitter, Math.max(0, retryAfterMs));
    }

    public static String label(Action a) {
        switch (a) {
            case RETRY: return "gangguan sementara — dicoba ulang otomatis";
            case LOGIN_REQUIRED: return "sesi login habis — login ulang";
            case DEVICE_BLOCKED: return "perangkat ditolak/dicabut ERP — hubungi admin";
            case OTHER_OPERATOR: return "milik operator lain — terkirim saat operator itu login";
            case IDEMPOTENCY: return "isi antrean berubah — perlu peninjauan (PIN)";
            default: return "ditolak ERP — lihat pesan";
        }
    }
}
