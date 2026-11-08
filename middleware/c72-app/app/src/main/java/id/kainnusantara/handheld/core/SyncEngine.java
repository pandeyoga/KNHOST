package id.kainnusantara.handheld.core;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.HashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;

/**
 * Pengirim antrean offline. Urutan per dokumen dijaga (batch dokumen X tidak disalip "Selesaikan" X); kegagalan satu
 * dokumen tidak menahan dokumen lain. HTTP 200 = hasil final ERP (diterima ATAU konflik bisnis) → tidak diulang.
 * Galat sementara → ulang dengan ID & isi SAMA (backoff). Login/perangkat ditolak → berhenti, antrean tetap utuh.
 * Hanya item milik operator yang sedang login yang dikirim (bukti tidak pindah pemilik).
 */
public final class SyncEngine {
    public interface Clock { long now(); }

    public interface Listener { void onResult(OutboxItem item, JSONObject response); }

    public static final class Pass {
        public int sent, done, conflict, rejected, retry;
        public ErrorPolicy.Action blockedBy;
        public String message = "";
        @Override public String toString() {
            return "terkirim " + sent + " · diterima " + done + " · konflik " + conflict + " · ditolak " + rejected + " · ulang " + retry
                    + (blockedBy == null ? "" : " · berhenti: " + ErrorPolicy.label(blockedBy));
        }
    }

    private final Store store;
    private final ApiClient api;
    private final Clock clock;
    private final long backoffMaxMs;
    private final Random random;
    private volatile Listener listener;
    /** Kait tingkat aplikasi (selalu dipanggil, layar apa pun yang terbuka): mis. hasil baris Daftar Awal → foto. */
    public volatile Listener hook;
    public volatile String lastStatus = "";
    public volatile long lastSuccessMs;

    public SyncEngine(Store store, ApiClient api, Clock clock, long backoffMaxMs, Random random) {
        this.store = store; this.api = api; this.clock = clock; this.backoffMaxMs = backoffMaxMs; this.random = random;
    }

    public void listener(Listener l) { listener = l; }

    public synchronized Pass runOnce(String currentUserId, int limit) {
        Pass p = new Pass();
        if (currentUserId == null || currentUserId.isEmpty()) { p.message = "belum login"; return p; }
        List<OutboxItem> due = store.due(clock.now(), currentUserId, limit);
        Set<String> blockedDocs = new HashSet<>();
        for (OutboxItem it : due) {
            String doc = it.kind + "|" + it.docId;
            if (blockedDocs.contains(doc)) continue;
            p.sent++;
            it.attempts++;
            try {
                JSONObject res = api.send(it);
                String st = Json.str(res, "status");
                it.response = clip(res.toString());
                if ("conflict".equals(st)) { it.status = OutboxItem.CONFLICT; p.conflict++; it.lastError = errorText(res); }
                else if ("rejected".equals(st)) { it.status = OutboxItem.REJECTED; p.rejected++; it.lastError = errorText(res); }
                else { it.status = OutboxItem.DONE; p.done++; it.lastError = ""; }
                store.update(it);
                applyCodes(it, res);
                lastSuccessMs = clock.now();
                Listener h = hook;
                if (h != null) h.onResult(it, res);
                Listener l = listener;
                if (l != null) l.onResult(it, res);
                if (!OutboxItem.DONE.equals(it.status)) blockedDocs.add(doc);
            } catch (ApiClient.ApiException e) {
                it.lastError = e.getMessage();
                switch (e.action) {
                    case RETRY:
                        it.nextDueMs = clock.now() + ErrorPolicy.backoffMs(it.attempts, backoffMaxMs, e.retryAfterMs, random.nextDouble());
                        p.retry++;
                        store.update(it);
                        blockedDocs.add(doc);
                        if (e.status == 0) { p.blockedBy = ErrorPolicy.Action.RETRY; p.message = e.getMessage(); lastStatus = p.toString(); return p; }
                        break;
                    case LOGIN_REQUIRED:
                    case DEVICE_BLOCKED:
                        it.attempts--;   // bukan kegagalan item — identitas yang ditolak
                        store.update(it);
                        p.blockedBy = e.action;
                        p.message = e.getMessage();
                        lastStatus = p.toString();
                        return p;
                    case OTHER_OPERATOR:
                        it.status = OutboxItem.BLOCKED;
                        store.update(it);
                        blockedDocs.add(doc);
                        break;
                    case IDEMPOTENCY:
                        it.status = OutboxItem.BLOCKED;
                        p.rejected++;
                        store.update(it);
                        blockedDocs.add(doc);
                        store.audit("Antrean " + it.id + " IDEMPOTENCY_CONFLICT — butuh peninjauan");
                        break;
                    default:
                        it.status = OutboxItem.REJECTED;
                        p.rejected++;
                        store.update(it);
                        markCodes(it, "conflict", e.getMessage());
                        blockedDocs.add(doc);
                        Listener l = listener;
                        if (l != null) l.onResult(it, Json.obj("status", "rejected", "error", Json.obj("code", e.code, "message", e.getMessage())));
                        break;
                }
            }
        }
        lastStatus = p.toString();
        return p;
    }

    /** Status per kode di layar dokumen: hasil server per item (diterima / konflik + pesan). */
    void applyCodes(OutboxItem it, JSONObject res) {
        if (!"batch".equals(it.type)) return;
        JSONArray items = res.optJSONArray("items");
        boolean docConflict = "conflict".equals(Json.str(res, "status")) || "rejected".equals(Json.str(res, "status"));
        if (docConflict && (items == null || items.length() == 0)) { markCodes(it, "conflict", errorText(res)); return; }
        for (int i = 0; items != null && i < items.length(); i++) {
            JSONObject o = items.optJSONObject(i);
            String ref = Json.str(o, "ref");
            if (ref.isEmpty()) continue;
            boolean c = o.optBoolean("conflict", false);
            String result = Json.str(o, "result");
            String state = c ? "conflict" : ("extra".equals(result) ? "extra" : "acked");
            store.docCode(it.kind, it.docId, ref, state, Json.str(o, "message"));
        }
    }

    void markCodes(OutboxItem it, String state, String message) {
        if (!"batch".equals(it.type) || it.body == null) return;
        JSONObject b = Json.parseOrEmpty(it.body);
        JSONArray r = b.optJSONArray("reads"), l = b.optJSONArray("labels");
        for (int i = 0; r != null && i < r.length(); i++) store.docCode(it.kind, it.docId, Json.str(r.optJSONObject(i), "epc"), state, message);
        for (int i = 0; l != null && i < l.length(); i++) store.docCode(it.kind, it.docId, l.optString(i), state, message);
    }

    /** Dipanggil saat batch DISIMPAN (sebelum kirim): kode tampil "antre" walau offline. */
    public void markQueued(OutboxItem it) { markCodes(it, "queued", ""); }

    public static DocMatcher.Local localState(Store store, String kind, String docId) {
        DocMatcher.Local l = new DocMatcher.Local();
        for (String[] c : store.docCodes(kind, docId)) {
            if ("queued".equals(c[1])) l.queued.add(c[0]);
            else if ("acked".equals(c[1])) l.acked.add(c[0]);
            else if ("conflict".equals(c[1])) l.conflicts.put(c[0], c[2]);
            else if ("extra".equals(c[1])) l.acked.add(c[0]);
        }
        return l;
    }

    static String errorText(JSONObject res) {
        JSONObject e = res.optJSONObject("error");
        return e == null ? "" : Json.str(e, "message");
    }

    static String clip(String s) { return s.length() > 60000 ? s.substring(0, 60000) : s; }
}
