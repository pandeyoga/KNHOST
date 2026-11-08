package id.kubusteknologi.kn.u300.core;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.time.Instant;

/**
 * Pembangun payload kontrak 2.1 (murni): GpiEdge, dasar EventsRequest, PassageClose. Struktur sama dengan
 * acuan server {@code backend/services/rfid_v2_envelope.py} (hanya dibaca).
 */
public final class Envelope {
    private Envelope() {}

    public interface Wall { long at(long mono); }

    public static String iso(long ms) { return Instant.ofEpochMilli(ms).toString(); }

    static JSONObject obj(Object... kv) {
        JSONObject o = new JSONObject();
        try {
            for (int i = 0; i < kv.length; i += 2) o.put((String) kv[i], kv[i + 1] == null ? JSONObject.NULL : kv[i + 1]);
        } catch (JSONException e) {
            throw new IllegalArgumentException(e);
        }
        return o;
    }

    public static JSONObject edge(String passageId, int n, BeamDebouncer.Edge e, long wallMs, boolean synced) {
        return obj("edge_id", passageId + ":g:" + n, "sensor", e.sensor, "state", e.blocked ? "blocked" : "clear",
                "t_mono", Math.max(0, e.tMono), "t_wall", iso(wallMs), "time_quality", synced ? "synced" : "unsynced");
    }

    /** Dasar EventsRequest tanpa item; konteks gate dari meta lintasan. */
    public static JSONObject eventsBase(String batchId, String passageId, JSONObject meta, String mode, long seq, String bootId,
                                        String sentAt) {
        String direction = meta.optString("direction", "unknown");
        JSONObject ctx = obj("kind", "gate", "logical_gate_id", meta.optString("logical_gate_id"), "local_passage_id", passageId,
                "direction", direction, "direction_evidence", directionEvidence(meta, null));
        JSONObject o = obj("schema_version", 2, "batch_id", batchId, "mode", mode, "config_version", meta.optString("config_version"),
                "context", ctx, "events", new JSONArray());
        try {
            if (bootId != null) o.put("seq", seq).put("boot_id", bootId).put("sent_at", sentAt);
        } catch (JSONException e) {
            throw new IllegalStateException(e);
        }
        return o;
    }

    /** Bukti arah: gate satu arah = profil tetap; gate dua arah lama = urutan dua tepi aktivasi pertama. */
    public static JSONObject directionEvidence(JSONObject meta, JSONArray sensorSequence) {
        String direction = meta.optString("direction", "unknown");
        String profile = meta.optString("profile_id", "");
        Object binding = profile.isEmpty() ? JSONObject.NULL : profile;
        if (sensorSequence != null) return obj("source", "sensor_sequence", "profile_binding_id", binding, "sensor_sequence", sensorSequence);
        if ("unknown".equals(direction)) return obj("source", "unknown", "profile_binding_id", binding, "sensor_sequence", new JSONArray());
        return obj("source", "fixed_profile", "profile_binding_id", binding, "sensor_sequence", new JSONArray());
    }

    /**
     * PassageClose 2.1. {@code observed_*_count} diisi 0 di sini dan diganti dengan jumlah item ber-ACK tepat
     * sebelum close dikirim (setelah itu body tetap sama untuk retry idempoten).
     */
    public static JSONObject close(JSONObject meta, PassageMachine.Closing c, Wall wall, boolean captureComplete,
                                   String mode, String bootId, JSONObject sensorPins, int activeState) {
        boolean legacy = "legacy_bidirectional".equals(meta.optString("sensor_mode"));
        String direction = legacy ? (c.direction == null ? "unknown" : c.direction) : meta.optString("direction", "unknown");
        JSONArray seq = null;
        if (legacy) {
            seq = new JSONArray();
            for (BeamDebouncer.Edge e : c.legacySequence) {
                seq.put(obj("sensor_id", sensorPins == null ? e.sensor : sensorPins.optString(e.sensor.toLowerCase(java.util.Locale.ROOT), e.sensor),
                        "captured_at", iso(wall.at(e.tMono)), "state", String.valueOf(activeState)));
            }
        }
        JSONObject m = Batcher.copy(meta);
        try { m.put("direction", direction); } catch (JSONException e) { throw new IllegalStateException(e); }
        JSONObject o = obj("logical_gate_id", meta.optString("logical_gate_id"), "config_version", meta.optString("config_version"),
                "mode", mode, "closing_captured_at", iso(wall.at(c.tCloseMono)), "boundary_reason", c.boundaryReason,
                "last_event_id", null, "observed_event_count", 0, "capture_complete", captureComplete, "direction", direction,
                "direction_evidence", directionEvidence(m, seq), "window_start", iso(wall.at(c.windowStartMono)),
                "beam_times", obj("a_blocked", c.aBlocked == null ? null : iso(wall.at(c.aBlocked)),
                        "b_blocked", c.bBlocked == null ? null : iso(wall.at(c.bBlocked)),
                        "a_cleared", c.aCleared == null ? null : iso(wall.at(c.aCleared)),
                        "b_cleared", c.bCleared == null ? null : iso(wall.at(c.bCleared))),
                "pre_buffer_ms", c.preBufferMs, "tail_ms", c.tailMs, "observed_summary_count", 0, "observed_edge_count", 0,
                "sensor_health", c.sensorHealth);
        try {
            if (c.openReason != null) o.put("open_reason", c.openReason);
            if (c.closeReason != null) o.put("close_reason", c.closeReason);
            if (bootId != null) o.put("boot_id", bootId);
        } catch (JSONException e) {
            throw new IllegalStateException(e);
        }
        return o;
    }
}
