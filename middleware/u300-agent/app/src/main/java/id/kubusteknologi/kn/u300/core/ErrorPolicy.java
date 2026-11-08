package id.kubusteknologi.kn.u300.core;

/**
 * Penanganan galat ERP berdasarkan {@code detail.code} (AUD-MW-06, kontrak 2.1 {@code x-error-codes}), bukan
 * hanya status HTTP. Hanya autentikasi sungguhan (AUTH_REQUIRED/AUTH_INVALID, atau 401) yang memblokir sampai
 * provisioning ulang. Perangkat dinonaktifkan admin / profil belum terbit / 403 tanpa kode (mis. proxy) =
 * polling lambat yang pulih sendiri.
 */
public final class ErrorPolicy {
    private ErrorPolicy() {}

    public enum Action {
        RETRY, ADMIN_DISABLED, CONFIG_REQUIRED, FORBIDDEN_UNKNOWN, AUTH_BLOCK, CONTRACT_BLOCK,
        SPLIT_BATCH, EVIDENCE_PENDING, PASSAGE_FROZEN
    }

    public static final long SLOW_POLL_MS = 60_000;

    public static Action classify(int status, String code, Boolean retryable) {
        String c = code == null ? "" : code;
        switch (c) {
            case "AUTH_REQUIRED":
            case "AUTH_INVALID":
                return Action.AUTH_BLOCK;
            case "ADMIN_DISABLED":
                return Action.ADMIN_DISABLED;
            case "CONFIG_REQUIRED":
                return Action.CONFIG_REQUIRED;
            case "BATCH_TOO_LARGE":
                return Action.SPLIT_BATCH;
            case "EVIDENCE_PENDING":
                return Action.EVIDENCE_PENDING;
            case "PASSAGE_FROZEN":
                return Action.PASSAGE_FROZEN;
            case "EVENT_ID_CONFLICT":
            case "CLOSE_CONFLICT":
            case "PASSAGE_CONTEXT_CHANGED":
            case "DEVICE_MOVED":
            case "GATE_NOT_BOUND":
            case "READER_REQUIRED":
            case "GATE_CONTEXT_REQUIRED":
            case "IDEMPOTENCY_KEY_REQUIRED":
                return Action.CONTRACT_BLOCK;
            default:
                break;
        }
        if (c.startsWith("INVALID_")) return Action.CONTRACT_BLOCK;
        if (status == 401) return Action.AUTH_BLOCK;
        if (status == 413) return Action.SPLIT_BATCH;
        if (status == 403) return Action.FORBIDDEN_UNKNOWN;
        if (status == 404) return Action.FORBIDDEN_UNKNOWN;
        if (status == 408 || status == 425 || status == 429 || status >= 500) return Action.RETRY;
        if (Boolean.TRUE.equals(retryable)) return Action.RETRY;
        if (status >= 400 && status < 500) return Action.CONTRACT_BLOCK;
        return Action.RETRY;
    }

    /** Jeda sebelum mencoba lagi. Polling lambat memakai {@code details.poll_after_seconds} bila ada. */
    public static long delayMs(Action a, long pollAfterMs, long retryAfterMs, long backoffMs) {
        long wait;
        switch (a) {
            case ADMIN_DISABLED:
            case CONFIG_REQUIRED:
            case FORBIDDEN_UNKNOWN:
                wait = pollAfterMs > 0 ? pollAfterMs : SLOW_POLL_MS;
                break;
            default:
                wait = backoffMs;
                break;
        }
        return Math.max(wait, Math.max(0, retryAfterMs));
    }

    /** Teks status transport untuk layar & telemetry (Bahasa Indonesia). */
    public static String label(Action a) {
        switch (a) {
            case ADMIN_DISABLED: return "dinonaktifkan admin ERP — cek ulang berkala";
            case CONFIG_REQUIRED: return "profil V2 belum terbit — cek ulang berkala";
            case FORBIDDEN_UNKNOWN: return "ditolak tanpa kode (proxy/rute?) — cek ulang berkala";
            case AUTH_BLOCK: return "device key ditolak — provisioning ulang";
            case CONTRACT_BLOCK: return "kontrak/konteks ditolak — perlu pemulihan ber-PIN";
            default: return "gangguan sementara — coba ulang";
        }
    }
}
