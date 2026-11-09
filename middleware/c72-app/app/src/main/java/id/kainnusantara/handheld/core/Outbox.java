package id.kainnusantara.handheld.core;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Collection;
import java.util.List;

/**
 * Pembentuk item antrean. Semua kiriman (pindai massal, selesaikan, konfirmasi tulis tag, baris Daftar Awal) lewat
 * antrean yang sama: disimpan dulu (ID klien tetap), dikirim saat tersambung, diulang dengan ID SAMA.
 */
public final class Outbox {
    private Outbox() {}

    public static final class Who {
        public final String userId, opSessionId;
        public Who(String userId, String opSessionId) { this.userId = userId; this.opSessionId = opSessionId; }
    }

    static JSONArray reads(Collection<ReadAggregator.Tag> tags, Collection<String> only) {
        JSONArray a = new JSONArray();
        for (ReadAggregator.Tag t : tags) {
            if (only != null && !only.contains(t.epc)) continue;
            a.put(Json.obj("epc", t.epc, "rssi", t.rssiMax, "count", t.count, "first_seen", Json.iso(t.firstWall),
                    "last_seen", Json.iso(t.lastWall), "tid", t.tid));
        }
        return a;
    }

    /**
     * Satu batch = satu dokumen. {@code tags} = bacaan RF yang dikirim (sudah dibatasi), {@code labels} = label QR/barcode.
     * Waktu bacaan memakai jam terkoreksi server bila sudah sinkron ({@code clock_synced}).
     */
    public static OutboxItem batch(Snapshot s, Collection<ReadAggregator.Tag> tags, Collection<String> only, Collection<String> labels,
                                   String labelReason, String binId, boolean simulated, Who who, ClockSync clock, long nowMs,
                                   long firstMs, long lastMs) {
        String id = "b-" + Json.uuid();
        JSONObject body = Json.obj("client_batch_id", id, "kind", s.kind, "doc_id", s.docId,
                "session_id", s.sessionId.isEmpty() ? null : s.sessionId, "snapshot_version", s.version,
                "operator_session_id", who.opSessionId, "user_id", who.userId, "device_time", Json.iso(nowMs),
                "clock_offset_ms", clock == null ? null : clock.offsetMs(), "clock_synced", clock != null && clock.everSynced(),
                "captured_from", firstMs > 0 ? Json.iso(firstMs) : null, "captured_to", lastMs > 0 ? Json.iso(lastMs) : null,
                "reads", reads(tags, only), "labels", new JSONArray(labels), "label_reason", labelReason == null ? "" : labelReason,
                "bin_id", binId == null ? "" : binId, "simulated", simulated, "lines", new JSONArray());
        OutboxItem it = new OutboxItem(id, "batch", "POST", "/api/handheld/batches", body.toString(), s.kind, s.docId,
                who.userId, who.opSessionId, nowMs);
        it.label = s.number + " · " + (only == null ? tags.size() : only.size()) + " tag" + (labels.isEmpty() ? "" : " + " + labels.size() + " label");
        return it;
    }

    public static OutboxItem registrationLines(String sessionId, String number, List<JSONObject> lines, Who who, long nowMs) {
        String id = "r-" + Json.uuid();
        JSONObject body = Json.obj("client_batch_id", id, "kind", "registration", "doc_id", sessionId,
                "operator_session_id", who.opSessionId, "user_id", who.userId, "device_time", Json.iso(nowMs),
                "reads", new JSONArray(), "labels", new JSONArray(), "lines", new JSONArray(lines), "simulated", false);
        OutboxItem it = new OutboxItem(id, "batch", "POST", "/api/handheld/batches", body.toString(), "registration", sessionId,
                who.userId, who.opSessionId, nowMs);
        it.label = number + " · " + lines.size() + " baris Daftar Awal";
        return it;
    }

    public static OutboxItem complete(Snapshot s, Who who, long nowMs) {
        String id = "c-" + Json.uuid();
        JSONObject body = Json.obj("client_request_id", id, "operator_session_id", who.opSessionId, "user_id", who.userId,
                "session_id", s.sessionId);
        OutboxItem it = new OutboxItem(id, "complete", "POST", "/api/handheld/tasks/" + s.kind + "/" + ApiClient.seg(s.docId) + "/complete",
                body.toString(), s.kind, s.docId, who.userId, who.opSessionId, nowMs);
        it.label = "Selesaikan " + s.number;
        return it;
    }

    public static OutboxItem tagConfirm(String writeId, String rollNo, String verifiedEpc, String tid, Double rssi, int attempts,
                                        int powerDbm, Who who, long nowMs) {
        String id = "t-" + Json.uuid();
        JSONObject body = Json.obj("client_request_id", id, "operator_session_id", who.opSessionId, "user_id", who.userId,
                "verified_epc", verifiedEpc, "tid", tid, "rssi", rssi, "attempts", attempts, "write_power_dbm", powerDbm);
        OutboxItem it = new OutboxItem(id, "tag_confirm", "POST", "/api/handheld/tag-writes/" + writeId + "/confirm", body.toString(),
                "tag_write", writeId, who.userId, who.opSessionId, nowMs);
        it.label = "Tag baru roll " + rollNo + " (" + Epc.tail(verifiedEpc) + ")";
        return it;
    }

    public static OutboxItem tagFail(String writeId, String rollNo, String reason, int attempts, Who who, long nowMs) {
        String id = "f-" + Json.uuid();
        JSONObject body = Json.obj("client_request_id", id, "operator_session_id", who.opSessionId, "user_id", who.userId,
                "reason", reason, "attempts", attempts);
        OutboxItem it = new OutboxItem(id, "tag_fail", "POST", "/api/handheld/tag-writes/" + writeId + "/fail", body.toString(),
                "tag_write", writeId, who.userId, who.opSessionId, nowMs);
        it.label = "Tulis tag gagal · roll " + rollNo;
        return it;
    }
}
