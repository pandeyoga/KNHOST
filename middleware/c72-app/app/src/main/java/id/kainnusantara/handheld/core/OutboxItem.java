package id.kainnusantara.handheld.core;

/**
 * Satu kiriman yang DISIMPAN SEBELUM dikirim (persist-before-send). {@link #id} = ID idempotensi klien
 * (client_batch_id / client_request_id) yang sama di setiap pengulangan; {@link #body} tidak pernah diubah.
 */
public final class OutboxItem {
    public static final String PENDING = "pending";      // menunggu kirim / dicoba ulang
    public static final String DONE = "done";            // diterima ERP (ACK final)
    public static final String CONFLICT = "conflict";    // ERP menolak secara bisnis (dokumen berubah/roll konflik)
    public static final String REJECTED = "rejected";    // ditolak permanen (izin/validasi) — tidak diulang
    public static final String BLOCKED = "blocked";      // butuh tindakan (login/provisioning/peninjauan ber-PIN)
    public static final String ARCHIVED = "archived";    // ditinjau & diarsipkan (bukti tetap tersimpan)

    public final String id, type, method, path, body, kind, docId, userId, opSessionId;
    public final long createdMs;
    public String status = PENDING, lastError = "", response = "", label = "";
    public int attempts;
    public long nextDueMs, updatedMs;

    public OutboxItem(String id, String type, String method, String path, String body, String kind, String docId,
                      String userId, String opSessionId, long createdMs) {
        this.id = id; this.type = type; this.method = method; this.path = path; this.body = body; this.kind = kind;
        this.docId = docId; this.userId = userId; this.opSessionId = opSessionId; this.createdMs = createdMs;
        this.updatedMs = createdMs;
    }

    public boolean finished() { return DONE.equals(status) || CONFLICT.equals(status) || REJECTED.equals(status) || ARCHIVED.equals(status); }

    public String statusText() {
        switch (status) {
            case PENDING: return attempts == 0 ? "⟳ Antre kirim" : "⟳ Dicoba ulang (" + attempts + "×)";
            case DONE: return "✓ Diterima ERP";
            case CONFLICT: return "! Konflik";
            case REJECTED: return "✕ Ditolak";
            case BLOCKED: return "⏸ Tertahan";
            case ARCHIVED: return "☐ Diarsipkan";
            default: return status;
        }
    }
}
