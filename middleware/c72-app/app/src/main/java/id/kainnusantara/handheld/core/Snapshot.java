package id.kainnusantara.handheld.core;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * "Yang diharapkan" satu dokumen (cache read-only dari server, BUKAN replika stok): baris roll + EPC + status server,
 * versi struktur, sesi. Disimpan utuh (JSON gabungan semua halaman) supaya bisa dipakai offline.
 */
public final class Snapshot {
    public static final class Row {
        public final String rollId, rollNo, epc, state, sku, productName, unit, lot, binCode;
        public final Double qty;
        public final boolean suggested;

        Row(JSONObject o) {
            rollId = Json.str(o, "roll_id"); rollNo = Json.str(o, "roll_no");
            String e = Epc.canonical(Json.str(o, "epc"));
            epc = e != null ? e : Json.str(o, "epc").toUpperCase(java.util.Locale.ROOT);
            state = Json.str(o, "state"); sku = Json.str(o, "sku"); productName = Json.str(o, "product_name");
            unit = Json.str(o, "unit"); lot = Json.str(o, "lot"); binCode = Json.str(o, "bin_code");
            qty = o.has("qty") && !o.isNull("qty") ? o.optDouble("qty") : null;
            suggested = o.optBoolean("suggested", false);
        }

        public boolean done() { return "done".equals(state); }
        public boolean pending() { return "pending".equals(state); }
    }

    public final JSONObject raw;
    public final String kind, docId, number, title, version, sessionId, status, statusLabel, warehouseId, snapshotAt;
    public final boolean closed, needsStart, labelsAllowed, completeSupported, offlineAllowed;
    public final List<Row> rows;
    public final List<JSONObject> untagged;
    private final Map<String, Row> byEpc = new HashMap<>(), byLabel = new HashMap<>();

    public Snapshot(JSONObject raw) {
        this.raw = raw;
        kind = Json.str(raw, "kind"); docId = Json.str(raw, "doc_id"); number = Json.str(raw, "number");
        title = Json.str(raw, "title"); version = Json.str(raw, "version"); sessionId = Json.str(raw, "session_id");
        status = Json.str(raw, "status"); statusLabel = Json.str(raw, "status_label");
        warehouseId = Json.str(raw, "warehouse_id"); snapshotAt = Json.str(raw, "snapshot_at");
        closed = raw.optBoolean("closed", false); needsStart = raw.optBoolean("needs_start", false);
        labelsAllowed = raw.optBoolean("labels_allowed", false);
        completeSupported = raw.optBoolean("complete_supported", false);
        offlineAllowed = raw.optBoolean("offline_allowed", true);
        List<Row> rs = new ArrayList<>();
        JSONArray a = raw.optJSONArray("rows");
        for (int i = 0; a != null && i < a.length(); i++) {
            Row r = new Row(a.optJSONObject(i));
            rs.add(r);
            if (!r.epc.isEmpty()) byEpc.put(r.epc, r);
            if (!r.rollNo.isEmpty()) byLabel.put(r.rollNo.toUpperCase(java.util.Locale.ROOT), r);
        }
        rows = Collections.unmodifiableList(rs);
        List<JSONObject> un = new ArrayList<>();
        JSONArray u = raw.optJSONArray("untagged");
        for (int i = 0; u != null && i < u.length(); i++) un.add(u.optJSONObject(i));
        untagged = Collections.unmodifiableList(un);
    }

    public Row byEpc(String epc) { return byEpc.get(epc); }
    public Row byLabel(String label) { return label == null ? null : byLabel.get(label.trim().toUpperCase(java.util.Locale.ROOT)); }
    public TaskKind taskKind() { return TaskKind.of(kind); }
    public JSONObject registration() { return raw.optJSONObject("registration"); }
    public JSONObject task() { return raw.optJSONObject("task"); }

    /** Umur snapshot (jam) terhadap jam server perkiraan. */
    public double ageHours(long nowMs) {
        long at = Json.time(snapshotAt);
        return at <= 0 ? 999 : (nowMs - at) / 3_600_000.0;
    }

    /** Gabungkan halaman lanjutan (offset/limit) ke halaman pertama; total harus cocok. */
    public static JSONObject merge(JSONObject first, List<JSONObject> more) {
        JSONArray rows = first.optJSONArray("rows");
        if (rows == null) { rows = new JSONArray(); Json.put(first, "rows", rows); }
        for (JSONObject p : more) {
            if (!Json.str(p, "version").equals(Json.str(first, "version")))
                throw new IllegalStateException("Dokumen berubah saat diunduh — unduh ulang.");
            JSONArray r = p.optJSONArray("rows");
            for (int i = 0; r != null && i < r.length(); i++) rows.put(r.opt(i));
        }
        int total = first.optInt("total_rows", rows.length());
        if (rows.length() != total) throw new IllegalStateException("Unduhan tidak lengkap: " + rows.length() + " dari " + total + " baris.");
        return first;
    }
}
