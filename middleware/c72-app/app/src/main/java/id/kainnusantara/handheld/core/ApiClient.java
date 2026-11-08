package id.kainnusantara.handheld.core;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Adaptor API ERP untuk handheld ({@code /api/handheld/*} + login ERP). Dua identitas di setiap panggilan kerja:
 * {@code X-Device-Key} (perangkat) + {@code Authorization: Bearer} (operator). Token pengguna = kredensial opaque
 * (tidak di-parse); sandi tidak pernah disimpan. Semua respons ber-{@code server_time} menyinkronkan {@link ClockSync}.
 * Lapisan tugas hanya memanggil metode di kelas ini — bila model tugas ERP berubah, cukup kelas ini yang disesuaikan.
 */
public final class ApiClient {
    public interface Credentials { String baseUrl(); String deviceKey(); String userToken(); }
    public interface Mono { long now(); }

    public static final class Response {
        public final int status;
        public final String body;
        public final Map<String, String> headers;
        public Response(int status, String body, Map<String, String> headers) { this.status = status; this.body = body; this.headers = headers; }
    }

    public interface Transport { Response send(String method, String url, Map<String, String> headers, byte[] body) throws IOException; }

    /** Galat terstruktur ERP ({@code detail.code/message/retryable}) atau jaringan (status 0). */
    public static final class ApiException extends Exception {
        public final int status;
        public final String code;
        public final Boolean retryable;
        public final long retryAfterMs;
        public final ErrorPolicy.Action action;

        public ApiException(int status, String code, String message, Boolean retryable, long retryAfterMs) {
            super(message == null || message.isEmpty() ? ("ERP HTTP " + status) : message);
            this.status = status; this.code = code == null ? "" : code; this.retryable = retryable; this.retryAfterMs = retryAfterMs;
            this.action = ErrorPolicy.classify(status, this.code, retryable);
        }
    }

    private final Transport transport;
    private final Credentials creds;
    private final ClockSync clock;
    private final Mono mono;
    public volatile String appVersion = "0.1.0-lab";

    public ApiClient(Transport transport, Credentials creds, ClockSync clock, Mono mono) {
        this.transport = transport; this.creds = creds; this.clock = clock; this.mono = mono;
    }

    // ── HTTP dasar ──────────────────────────────────────────────────────────
    public JSONObject call(String method, String path, JSONObject body, String idempotencyKey, boolean user) throws ApiException {
        Map<String, String> h = new LinkedHashMap<>();
        h.put("Accept", "application/json");
        String dk = creds.deviceKey();
        if (dk != null && !dk.isEmpty()) h.put("X-Device-Key", dk);
        if (user) {
            String t = creds.userToken();
            if (t == null || t.isEmpty()) throw new ApiException(401, "LOGIN_REQUIRED", "Belum login operator.", false, 0);
            h.put("Authorization", "Bearer " + t);
        }
        if (idempotencyKey != null) h.put("Idempotency-Key", idempotencyKey);
        byte[] b = null;
        if (body != null) { b = body.toString().getBytes(StandardCharsets.UTF_8); h.put("Content-Type", "application/json"); }
        String base = creds.baseUrl() == null ? "" : creds.baseUrl().replaceAll("/+$", "");
        long start = mono.now();
        Response r;
        try {
            r = transport.send(method, base + path, h, b);
        } catch (IOException e) {
            throw new ApiException(0, "NETWORK", "Tidak tersambung ke ERP: " + e.getMessage(), true, 0);
        }
        JSONObject json = Json.parseOrEmpty(r.body);
        long remote = Json.time(Json.str(json, "server_time"));
        if (clock != null && remote > 0 && r.status < 500) clock.offer(remote, start, mono.now());
        if (r.status < 200 || r.status >= 300) throw failure(r, json);
        return json;
    }

    static ApiException failure(Response r, JSONObject json) {
        long retry = 0;
        String ra = r.headers == null ? null : r.headers.get("retry-after");
        try { if (ra != null) retry = Long.parseLong(ra.trim()) * 1000L; } catch (NumberFormatException ignored) { }
        Object d = json.opt("detail");
        if (d instanceof JSONObject) {
            JSONObject o = (JSONObject) d;
            Boolean rt = o.opt("retryable") instanceof Boolean ? o.optBoolean("retryable") : null;
            return new ApiException(r.status, Json.str(o, "code"), Parse.clip(Json.str(o, "message"), 500), rt, retry);
        }
        if (d instanceof String) return new ApiException(r.status, "", Parse.clip((String) d, 500), null, retry);
        if (d instanceof JSONArray) return new ApiException(r.status, "VALIDATION", "Isi permintaan tidak valid: " + Parse.clip(d.toString(), 300), false, retry);
        return new ApiException(r.status, "", "ERP HTTP " + r.status, null, retry);
    }

    static String q(String s) {
        try { return URLEncoder.encode(s == null ? "" : s, "UTF-8"); } catch (java.io.UnsupportedEncodingException e) { throw new IllegalStateException(e); }
    }

    /** Segmen path (spasi = %20, bukan '+'). */
    public static String seg(String s) { return q(s).replace("+", "%20"); }

    // ── Perangkat & operator ────────────────────────────────────────────────
    public JSONObject deviceConfig() throws ApiException { return call("GET", "/api/handheld/device/config?app_version=" + q(appVersion), null, null, false); }

    /** Login ERP biasa → token sesi. Sandi hanya lewat memori, tidak disimpan. */
    public JSONObject login(String email, char[] password) throws ApiException {
        JSONObject body = Json.obj("email", email, "password", new String(password));
        return call("POST", "/api/auth/login", body, null, false);
    }

    public void logout() throws ApiException { call("POST", "/api/auth/logout", new JSONObject(), null, true); }
    public JSONObject sessionStart() throws ApiException { return call("POST", "/api/handheld/session/start", Json.obj("app_version", appVersion), null, true); }
    public JSONObject sessionEnd(String opSessionId, String reason) throws ApiException {
        return call("POST", "/api/handheld/session/end", Json.obj("operator_session_id", opSessionId, "reason", reason), null, true);
    }
    public JSONObject me() throws ApiException { return call("GET", "/api/handheld/me", null, null, true); }

    // ── Tugas ───────────────────────────────────────────────────────────────
    public JSONObject summary() throws ApiException { return call("GET", "/api/handheld/tasks/summary", null, null, true); }
    public JSONObject tasks(String kind, String query) throws ApiException {
        return call("GET", "/api/handheld/tasks?kind=" + q(kind) + "&q=" + q(query) + "&limit=200", null, null, true);
    }

    /** Unduh SELURUH halaman yang diharapkan (offset/limit) lalu gabungkan; versi harus tetap selama unduhan. */
    public JSONObject expected(String kind, String docId, boolean start, int pageSize) throws ApiException {
        String base = "/api/handheld/tasks/" + seg(kind) + "/" + seg(docId) + "/expected?limit=" + pageSize;
        JSONObject first = call("GET", base + "&offset=0" + (start ? "&start=true" : ""), null, null, true);
        int total = first.optInt("total_rows", 0), got = first.optJSONArray("rows") == null ? 0 : first.optJSONArray("rows").length();
        List<JSONObject> more = new ArrayList<>();
        for (int off = got; off < total; ) {
            JSONObject p = call("GET", base + "&offset=" + off, null, null, true);
            int n = p.optJSONArray("rows") == null ? 0 : p.optJSONArray("rows").length();
            if (n == 0) break;
            more.add(p);
            off += n;
        }
        try {
            return Snapshot.merge(first, more);
        } catch (IllegalStateException e) {
            throw new ApiException(409, "SNAPSHOT_CHANGED", e.getMessage(), true, 0);
        }
    }

    public JSONObject send(OutboxItem item) throws ApiException {
        if ("photo".equals(item.type)) return sendPhoto(item);
        return call(item.method, item.path, item.body == null ? null : Json.parse(item.body), item.id, true);
    }

    /** Foto "produk belum dikenali" → endpoint unggah Daftar Awal yang sudah ada (multipart, field `file`). */
    JSONObject sendPhoto(OutboxItem item) throws ApiException {
        JSONObject b = Json.parse(item.body);
        java.io.File f = new java.io.File(Json.str(b, "file"));
        byte[] data;
        try {
            data = java.nio.file.Files.readAllBytes(f.toPath());
        } catch (IOException e) {
            throw new ApiException(400, "PHOTO_MISSING", "Berkas foto hilang dari HP: " + f.getName(), false, 0);
        }
        String boundary = "kn" + Long.toHexString(System.nanoTime());
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try {
            out.write(("--" + boundary + "\r\nContent-Disposition: form-data; name=\"file\"; filename=\"" + f.getName()
                    + "\"\r\nContent-Type: image/jpeg\r\n\r\n").getBytes(StandardCharsets.UTF_8));
            out.write(data);
            out.write(("\r\n--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8));
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
        Map<String, String> h = new LinkedHashMap<>();
        h.put("Accept", "application/json");
        h.put("Authorization", "Bearer " + creds.userToken());
        h.put("Content-Type", "multipart/form-data; boundary=" + boundary);
        String base = creds.baseUrl() == null ? "" : creds.baseUrl().replaceAll("/+$", "");
        Response r;
        try {
            r = transport.send("POST", base + item.path, h, out.toByteArray());
        } catch (IOException e) {
            throw new ApiException(0, "NETWORK", "Tidak tersambung ke ERP: " + e.getMessage(), true, 0);
        }
        JSONObject json = Json.parseOrEmpty(r.body);
        if (r.status < 200 || r.status >= 300) throw failure(r, json);
        return json;
    }

    public JSONObject lookup(String code) throws ApiException { return call("GET", "/api/handheld/lookup?code=" + q(code), null, null, true); }
    public JSONObject untagged(String warehouseId) throws ApiException {
        return call("GET", "/api/handheld/untagged?warehouse_id=" + q(warehouseId == null ? "" : warehouseId), null, null, true);
    }
    public JSONObject tagWrite(String clientId, String code, String opSession, String userId, String reason) throws ApiException {
        return call("POST", "/api/handheld/tag-writes", Json.obj("client_request_id", clientId, "code", code, "reason", reason,
                "operator_session_id", opSession, "user_id", userId), clientId, true);
    }
    public JSONObject epcPool(String sessionId, int count) throws ApiException {
        return call("POST", "/api/handheld/registration/" + seg(sessionId) + "/epc-pool", Json.obj("count", count), null, true);
    }
    public JSONObject catalog() throws ApiException { return call("GET", "/api/handheld/registration/catalog?limit=5000", null, null, true); }
    public JSONObject labelDecode(String sessionId, String raw) throws ApiException {
        return call("POST", "/api/handheld/registration/" + seg(sessionId) + "/label-decode", Json.obj("raw", raw, "supplier_id", ""), null, true);
    }
    public JSONObject rackDone(String sessionId, String rackId) throws ApiException {
        return call("POST", "/api/handheld/registration/" + seg(sessionId) + "/racks/" + seg(rackId), Json.obj("done", true), null, true);
    }

    // ── Transport HttpURLConnection (Android & JVM) ─────────────────────────
    public static final class HttpTransport implements Transport {
        private final int connectMs, readMs;
        private final boolean allowCleartext;

        public HttpTransport(int connectMs, int readMs, boolean allowCleartext) { this.connectMs = connectMs; this.readMs = readMs; this.allowCleartext = allowCleartext; }

        @Override
        public Response send(String method, String url, Map<String, String> headers, byte[] body) throws IOException {
            URL u = new URL(url);
            if (!"https".equalsIgnoreCase(u.getProtocol()) && !(allowCleartext && "http".equalsIgnoreCase(u.getProtocol())))
                throw new IOException("Hanya HTTPS yang diizinkan (" + u.getProtocol() + ")");
            HttpURLConnection c = (HttpURLConnection) u.openConnection();
            try {
                c.setConnectTimeout(connectMs); c.setReadTimeout(readMs); c.setInstanceFollowRedirects(false); c.setRequestMethod(method);
                for (Map.Entry<String, String> e : headers.entrySet()) c.setRequestProperty(e.getKey(), e.getValue());
                if (body != null) {
                    c.setDoOutput(true); c.setFixedLengthStreamingMode(body.length);
                    try (OutputStream o = c.getOutputStream()) { o.write(body); }
                }
                int status = c.getResponseCode();
                Map<String, String> hs = new LinkedHashMap<>();
                for (Map.Entry<String, List<String>> e : c.getHeaderFields().entrySet()) {
                    if (e.getKey() != null && e.getValue() != null && !e.getValue().isEmpty()) hs.put(e.getKey().toLowerCase(java.util.Locale.ROOT), e.getValue().get(0));
                }
                InputStream in = status >= 400 ? c.getErrorStream() : c.getInputStream();
                String text = "";
                if (in != null) {
                    try (InputStream i = in; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                        byte[] buf = new byte[8192];
                        int n;
                        while ((n = i.read(buf)) != -1) {
                            if (out.size() + n > 16 * 1024 * 1024) throw new IOException("Respons ERP terlalu besar");
                            out.write(buf, 0, n);
                        }
                        text = out.toString("UTF-8");
                    }
                }
                return new Response(status, text, hs);
            } finally {
                c.disconnect();
            }
        }
    }
}
