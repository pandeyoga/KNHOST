package id.kainnusantara.handheld.core;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.time.Instant;
import java.util.Iterator;
import java.util.TreeSet;
import java.util.UUID;

/**
 * Pembantu JSON (org.json). Disalin & diperluas dari agent U300 0.5 ({@code id.kubusteknologi.kn.u300.Json},
 * PT Kubus Teknologi Indonesia): obj/parse/now/time/canonical.
 */
public final class Json {
    private Json() {}

    public static JSONObject obj(Object... pairs) {
        JSONObject o = new JSONObject();
        try {
            for (int i = 0; i < pairs.length; i += 2) o.put((String) pairs[i], pairs[i + 1] == null ? JSONObject.NULL : pairs[i + 1]);
        } catch (JSONException e) {
            throw new IllegalArgumentException(e);
        }
        return o;
    }

    public static JSONObject parse(String s) {
        try {
            return new JSONObject(s);
        } catch (JSONException e) {
            throw new IllegalArgumentException("JSON tidak valid", e);
        }
    }

    public static JSONObject parseOrEmpty(String s) {
        if (s == null || s.trim().isEmpty()) return new JSONObject();
        try {
            return new JSONObject(s);
        } catch (JSONException e) {
            return new JSONObject();
        }
    }

    public static void put(JSONObject o, String k, Object v) {
        try {
            o.put(k, v == null ? JSONObject.NULL : v);
        } catch (JSONException e) {
            throw new IllegalArgumentException(e);
        }
    }

    /** String opsional: null/JSON-null → "" (org.json optString mengembalikan "null" untuk JSONObject.NULL). */
    public static String str(JSONObject o, String k) {
        if (o == null || !o.has(k) || o.isNull(k)) return "";
        return o.optString(k, "");
    }

    public static String now() { return Instant.now().toString(); }

    public static String iso(long epochMs) { return Instant.ofEpochMilli(epochMs).toString(); }

    public static long time(String s) {
        try {
            return Instant.parse(s).toEpochMilli();
        } catch (Exception e) {
            try {
                return java.time.OffsetDateTime.parse(s).toInstant().toEpochMilli();
            } catch (Exception e2) {
                return 0;
            }
        }
    }

    public static String uuid() { return UUID.randomUUID().toString(); }

    /** Bentuk kanonik (kunci terurut) — untuk sidik isi kiriman. */
    public static String canonical(Object value) {
        if (value instanceof JSONObject) {
            JSONObject o = (JSONObject) value;
            TreeSet<String> keys = new TreeSet<>();
            Iterator<String> it = o.keys();
            while (it.hasNext()) keys.add(it.next());
            StringBuilder b = new StringBuilder("{");
            for (String k : keys) {
                if (b.length() > 1) b.append(',');
                b.append(JSONObject.quote(k)).append(':').append(canonical(o.opt(k)));
            }
            return b.append('}').toString();
        }
        if (value instanceof JSONArray) {
            JSONArray a = (JSONArray) value;
            StringBuilder b = new StringBuilder("[");
            for (int i = 0; i < a.length(); i++) {
                if (i > 0) b.append(',');
                b.append(canonical(a.opt(i)));
            }
            return b.append(']').toString();
        }
        if (value instanceof String) return JSONObject.quote((String) value);
        return String.valueOf(value);
    }
}
