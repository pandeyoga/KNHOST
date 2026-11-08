package id.kubusteknologi.kn.u300.core;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * Pemilihan item bukti (event 0.4 / TagSummary / GpiEdge) ke satu {@code EventsRequest} dalam batas
 * kontrak: event ≤ {@code max_events}, ringkasan ≤ 500, tepi ≤ 200, body ≤ {@code max_body_bytes} (ukuran
 * ringkas — sama dengan server, AUD-MW-18). Ukuran dihitung inkremental (tanpa serialisasi ulang per item).
 */
public final class Batcher {
    private Batcher() {}

    public static final int MAX_SUMMARIES = 500, MAX_EDGES = 200;
    public static final String EVENT = "event", SUMMARY = "summary", EDGE = "edge";

    public static final class Item {
        public final String kind, id;
        public final JSONObject body;
        public final int bytes;
        public Item(String kind, String id, JSONObject body) {
            this.kind = kind;
            this.id = id;
            this.body = body;
            this.bytes = size(body);
        }
    }

    public static int size(Object json) { return json.toString().getBytes(StandardCharsets.UTF_8).length; }

    private static String arrayKey(String kind) {
        return EVENT.equals(kind) ? "events" : SUMMARY.equals(kind) ? "tag_summaries" : "gpi_edges";
    }

    /** Item yang muat (urutan dipertahankan; berhenti di item pertama yang tidak muat). */
    public static List<Item> fit(List<Item> candidates, JSONObject base, int maxEvents, int maxBody) {
        JSONObject probe = copy(base);
        try {
            probe.put("events", new JSONArray()).put("tag_summaries", new JSONArray()).put("gpi_edges", new JSONArray());
        } catch (JSONException e) {
            throw new IllegalStateException(e);
        }
        long running = size(probe);
        int events = 0, summaries = 0, edges = 0;
        List<Item> out = new ArrayList<>();
        for (Item it : candidates) {
            int n = EVENT.equals(it.kind) ? events : SUMMARY.equals(it.kind) ? summaries : edges;
            int limit = EVENT.equals(it.kind) ? Math.min(500, maxEvents) : SUMMARY.equals(it.kind) ? MAX_SUMMARIES : MAX_EDGES;
            long add = it.bytes + (n > 0 ? 1 : 0);
            if (n >= limit || running + add > maxBody) break;
            running += add;
            out.add(it);
            if (EVENT.equals(it.kind)) events++; else if (SUMMARY.equals(it.kind)) summaries++; else edges++;
        }
        return out;
    }

    /** Envelope akhir: {@code events} selalu ada (wajib skema); ringkasan/tepi hanya bila tidak kosong. */
    public static JSONObject build(JSONObject base, List<Item> items) {
        JSONObject o = copy(base);
        try {
            JSONArray ev = new JSONArray(), su = new JSONArray(), ed = new JSONArray();
            for (Item it : items) {
                (EVENT.equals(it.kind) ? ev : SUMMARY.equals(it.kind) ? su : ed).put(it.body);
            }
            o.put("events", ev);
            if (su.length() > 0) o.put("tag_summaries", su);
            if (ed.length() > 0) o.put("gpi_edges", ed);
        } catch (JSONException e) {
            throw new IllegalStateException(e);
        }
        return o;
    }

    public static String ackArray(String kind) { return EVENT.equals(kind) ? "event_acks" : SUMMARY.equals(kind) ? "summary_acks" : "edge_acks"; }
    public static String ackId(String kind) { return EVENT.equals(kind) ? "event_id" : "item_id"; }
    public static String bodyArray(String kind) { return arrayKey(kind); }
    public static String idField(String kind) { return EVENT.equals(kind) ? "event_id" : SUMMARY.equals(kind) ? "summary_id" : "edge_id"; }

    static JSONObject copy(JSONObject o) {
        try {
            return new JSONObject(o.toString());
        } catch (JSONException e) {
            throw new IllegalStateException(e);
        }
    }
}
