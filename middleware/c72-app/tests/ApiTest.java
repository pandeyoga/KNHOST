package id.kainnusantara.handheld.core;

import com.sun.net.httpserver.HttpServer;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * Tes host transport HTTP nyata (HttpURLConnection → server lokal JDK): header dua identitas, galat terstruktur,
 * unduhan "yang diharapkan" berhalaman + versi stabil, sinkron jam dari server_time, HTTPS-wajib di luar mode LAB.
 */
public final class ApiTest {
    static int passed;

    static void check(boolean ok, String label) {
        if (!ok) throw new AssertionError("GAGAL: " + label);
        passed++;
        System.out.println("PASS " + label);
    }

    public static void main(String[] a) throws Exception {
        HttpServer srv = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        List<String> log = new ArrayList<>();
        String serverTime = "2030-01-01T00:00:00Z";
        srv.createContext("/", ex -> {
            String path = ex.getRequestURI().toString();
            log.add(ex.getRequestMethod() + " " + path + " dk=" + ex.getRequestHeaders().getFirst("X-Device-Key")
                    + " auth=" + ex.getRequestHeaders().getFirst("Authorization") + " idem=" + ex.getRequestHeaders().getFirst("Idempotency-Key"));
            int status = 200;
            String body;
            if (path.startsWith("/api/handheld/device/config")) body = Json.obj("server_time", serverTime, "device", Json.obj("code", "C72-01")).toString();
            else if (path.contains("/expected") && path.contains("offset=0")) body = page("v1", 0, 3, 2).toString();
            else if (path.contains("/expected") && path.contains("offset=2")) body = page("v1", 2, 3, 1).toString();
            else if (path.startsWith("/api/handheld/tasks?")) { status = 403; body = Json.obj("detail", Json.obj("code", "PERMISSION_DENIED", "message", "Izin wms.update", "retryable", false)).toString(); }
            else if (path.startsWith("/api/handheld/me")) { status = 401; body = "{\"detail\":\"Session tidak valid\"}"; }
            else if (path.startsWith("/api/handheld/batches")) { status = 429; body = "{\"detail\":\"pelan\"}"; ex.getResponseHeaders().add("Retry-After", "7"); }
            else body = "{}";
            byte[] b = body.getBytes(StandardCharsets.UTF_8);
            ex.getResponseHeaders().add("Content-Type", "application/json");
            ex.sendResponseHeaders(status, b.length);
            try (OutputStream o = ex.getResponseBody()) { o.write(b); }
        });
        srv.start();
        String base = "http://127.0.0.1:" + srv.getAddress().getPort();
        long[] mono = {0};
        ClockSync clock = new ClockSync(new ClockSync.Source() { public long mono() { return mono[0]; } public long deviceWall() { return 0; } }, 5000, 60000);
        ApiClient.Credentials creds = new ApiClient.Credentials() {
            public String baseUrl() { return base; }
            public String deviceKey() { return "dk_uji"; }
            public String userToken() { return "tok"; }
        };
        try {
            ApiClient lab = new ApiClient(new ApiClient.HttpTransport(3000, 5000, true), creds, clock, () -> mono[0]);
            JSONObject cfg = lab.deviceConfig();
            check("C72-01".equals(cfg.getJSONObject("device").getString("code")) && log.get(0).contains("dk=dk_uji") && log.get(0).contains("auth=null"),
                    "config perangkat: hanya X-Device-Key (tanpa token operator)");
            check(clock.everSynced() && clock.now() == Json.time(serverTime), "jam disinkronkan dari server_time");
            JSONObject snap = lab.expected("putaway_in", "pa 1", false, 2);
            check(snap.getJSONArray("rows").length() == 3 && log.get(1).contains("pa%201") && log.get(2).contains("offset=2"), "yang diharapkan: 2 halaman digabung (3 baris), ID di-encode");
            check(log.get(1).contains("auth=Bearer tok"), "endpoint kerja: Bearer operator + device key");
            try { lab.tasks("putaway_in", ""); check(false, "403 harus melempar"); }
            catch (ApiClient.ApiException e) { check(e.status == 403 && "PERMISSION_DENIED".equals(e.code) && e.action == ErrorPolicy.Action.REJECTED, "galat terstruktur detail.code → ditolak"); }
            try { lab.me(); check(false, "401 harus melempar"); }
            catch (ApiClient.ApiException e) { check(e.action == ErrorPolicy.Action.LOGIN_REQUIRED && e.getMessage().contains("Session"), "galat teks 401 → login ulang"); }
            try { lab.call("POST", "/api/handheld/batches", Json.obj("x", 1), "b-1", true); check(false, "429 harus melempar"); }
            catch (ApiClient.ApiException e) { check(e.action == ErrorPolicy.Action.RETRY && e.retryAfterMs == 7000 && log.get(log.size() - 1).contains("idem=b-1"), "429 + Retry-After → ulang; Idempotency-Key terkirim"); }
            ApiClient prod = new ApiClient(new ApiClient.HttpTransport(3000, 5000, false), creds, clock, () -> mono[0]);
            try { prod.deviceConfig(); check(false, "http harus ditolak"); }
            catch (ApiClient.ApiException e) { check(e.status == 0 && e.getMessage().contains("HTTPS"), "rilis: hanya HTTPS (http ditolak sebelum kirim)"); }
            ApiClient down = new ApiClient(new ApiClient.HttpTransport(500, 500, true), new ApiClient.Credentials() {
                public String baseUrl() { return "http://127.0.0.1:1"; }
                public String deviceKey() { return "dk"; }
                public String userToken() { return "t"; }
            }, null, () -> 0);
            try { down.deviceConfig(); check(false, "harus gagal"); }
            catch (ApiClient.ApiException e) { check(e.status == 0 && e.action == ErrorPolicy.Action.RETRY, "server mati → galat jaringan, diulang"); }
        } finally {
            srv.stop(0);
        }
        System.out.println("ApiTest: " + passed + " PASS");
    }

    static JSONObject page(String version, int offset, int total, int n) {
        JSONArray rows = new JSONArray();
        for (int i = 0; i < n; i++) rows.put(Json.obj("roll_id", "r" + (offset + i), "epc", String.format("E2%022d", offset + i), "state", "pending"));
        return Json.obj("kind", "putaway_in", "doc_id", "pa 1", "version", version, "total_rows", total, "offset", offset, "rows", rows,
                "server_time", "2030-01-01T00:00:00Z");
    }
}
