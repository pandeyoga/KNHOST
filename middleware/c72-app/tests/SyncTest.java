package id.kainnusantara.handheld.core;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Deque;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Random;

/**
 * Tes host antrean offline + mesin sinkron dengan transport tiruan: persist-before-send, ID & isi SAMA saat diulang,
 * offline → antre, 5xx/429 → ulang dengan backoff, 401 → login ulang tanpa membuang antrean, konflik bisnis final,
 * urutan per dokumen, antrean milik operator lain tidak dikirim, idempotensi berubah → ditahan.
 */
public final class SyncTest {
    static int passed;

    static void check(boolean ok, String label) {
        if (!ok) throw new AssertionError("GAGAL: " + label);
        passed++;
        System.out.println("PASS " + label);
    }

    static final class Fake implements ApiClient.Transport {
        final Deque<Object> script = new ArrayDeque<>();
        final List<String[]> seen = new ArrayList<>();   // {method, url, idem, body, deviceKey, auth}

        public ApiClient.Response send(String method, String url, Map<String, String> h, byte[] body) throws IOException {
            seen.add(new String[]{method, url, h.get("Idempotency-Key"), body == null ? "" : new String(body, StandardCharsets.UTF_8),
                    h.get("X-Device-Key"), h.get("Authorization")});
            Object next = script.isEmpty() ? new ApiClient.Response(200, "{\"status\":\"accepted\",\"items\":[]}", new HashMap<>()) : script.poll();
            if (next instanceof IOException) throw (IOException) next;
            return (ApiClient.Response) next;
        }
    }

    static ApiClient.Response resp(int s, String body) { return new ApiClient.Response(s, body, new HashMap<>()); }

    static long now = 1_000_000;

    public static void main(String[] a) throws Exception {
        MemoryStore store = new MemoryStore();
        Fake t = new Fake();
        String[] token = {"tok-A"};
        ApiClient api = new ApiClient(t, new ApiClient.Credentials() {
            public String baseUrl() { return "https://erp.uji"; }
            public String deviceKey() { return "dk_uji"; }
            public String userToken() { return token[0]; }
        }, null, () -> now);
        SyncEngine eng = new SyncEngine(store, api, () -> now, 300000, new Random(1));
        List<String> heard = new ArrayList<>();
        eng.listener((it, res) -> heard.add(it.id + ":" + Json.str(res, "status")));
        Outbox.Who A = new Outbox.Who("usr_A", "hos_A"), B = new Outbox.Who("usr_B", "hos_B");

        Snapshot s = CoreTest.snap();
        ReadAggregator g = new ReadAggregator(100);
        g.offer(CoreTest.E1, null, "-50,0", 1, now);
        g.offer(CoreTest.EX, null, "-70,0", 2, now);

        // 1) offline: tersimpan dulu, gagal kirim → tetap antre + backoff, ID tetap
        OutboxItem b1 = Outbox.batch(s, g.snapshot(), new LinkedHashSet<>(Arrays.asList(CoreTest.E1, CoreTest.EX)), Collections.<String>emptyList(),
                "", "", false, A, null, now, now, now);
        store.enqueue(b1);
        eng.markQueued(b1);
        check(SyncEngine.localState(store, "putaway_in", "pa1").queued.contains(CoreTest.E1), "antrean: kode tampil 'antre' sebelum terkirim");
        t.script.add(new IOException("putus"));
        SyncEngine.Pass p1 = eng.runOnce("usr_A", 10);
        OutboxItem after = store.get(b1.id);
        check(p1.retry == 1 && OutboxItem.PENDING.equals(after.status) && after.nextDueMs > now, "offline: kirim gagal → tetap antre dengan jadwal ulang");
        check(eng.runOnce("usr_A", 10).sent == 0, "offline: belum jatuh tempo → tidak dikirim");
        // 2) 503 lalu sukses — ID & isi identik
        now = after.nextDueMs + 1;
        t.script.add(resp(503, "{\"detail\":\"sibuk\"}"));
        eng.runOnce("usr_A", 10);
        now = store.get(b1.id).nextDueMs + 1;
        t.script.add(resp(200, Json.obj("status", "accepted", "items", new JSONArray()
                .put(Json.obj("ref", CoreTest.E1, "result", "arrived", "conflict", false))
                .put(Json.obj("ref", CoreTest.EX, "result", "extra", "conflict", false)), "summary", Json.obj("arrived", 1)).toString()));
        eng.runOnce("usr_A", 10);
        check(OutboxItem.DONE.equals(store.get(b1.id).status) && store.get(b1.id).attempts == 3, "ulang: 2× gagal lalu diterima (3 percobaan)");
        check(t.seen.size() == 3 && t.seen.get(0)[2].equals(b1.id) && t.seen.get(2)[2].equals(b1.id) && t.seen.get(0)[3].equals(t.seen.get(2)[3]),
                "idempoten: Idempotency-Key & isi kiriman SAMA di setiap percobaan");
        check("dk_uji".equals(t.seen.get(0)[4]) && "Bearer tok-A".equals(t.seen.get(0)[5]), "dua identitas: X-Device-Key + Bearer operator");
        check(SyncEngine.localState(store, "putaway_in", "pa1").acked.contains(CoreTest.E1), "ACK: kode jadi 'sudah' dari hasil server");
        JSONObject body = Json.parse(t.seen.get(2)[3]);
        check(body.getJSONArray("reads").length() == 2 && "hos_A".equals(body.getString("operator_session_id")) && body.has("device_time"),
                "batch: bacaan + sesi operator + cap waktu perangkat");

        // 3) konflik bisnis final + urutan per dokumen (complete tidak menyalip batch yang konflik)
        OutboxItem b2 = Outbox.batch(s, g.snapshot(), Collections.singleton(CoreTest.E1), Collections.<String>emptyList(), "", "", false, A, null, now, 0, 0);
        store.enqueue(b2);
        now += 1;
        OutboxItem c2 = Outbox.complete(s, A, now);
        store.enqueue(c2);
        t.script.add(resp(200, Json.obj("status", "conflict", "error", Json.obj("code", "DOC_CLOSED", "message", "sudah ditutup"), "items", new JSONArray()).toString()));
        SyncEngine.Pass p3 = eng.runOnce("usr_A", 10);
        check(OutboxItem.CONFLICT.equals(store.get(b2.id).status) && p3.conflict == 1 && "sudah ditutup".equals(store.get(b2.id).lastError), "konflik: HTTP 200 conflict = final, tidak diulang");
        check(OutboxItem.PENDING.equals(store.get(c2.id).status) && store.get(c2.id).attempts == 0, "urutan: Selesaikan tidak dikirim mendahului batch dokumen yang sama");
        check(SyncEngine.localState(store, "putaway_in", "pa1").conflicts.containsKey(CoreTest.E1), "konflik: kode ditandai konflik di layar");

        // 4) 401 sesi habis → berhenti, antrean utuh, percobaan tidak dihitung
        t.script.add(resp(401, "{\"detail\":\"Session kedaluwarsa\"}"));
        SyncEngine.Pass p4 = eng.runOnce("usr_A", 10);
        check(p4.blockedBy == ErrorPolicy.Action.LOGIN_REQUIRED && OutboxItem.PENDING.equals(store.get(c2.id).status) && store.get(c2.id).attempts == 0,
                "401: minta login ulang; antrean tidak dibuang");

        // 5) device key dicabut
        t.script.add(resp(403, Json.obj("detail", Json.obj("code", "DEVICE_DISABLED", "message", "dicabut")).toString()));
        check(eng.runOnce("usr_A", 10).blockedBy == ErrorPolicy.Action.DEVICE_BLOCKED, "perangkat dicabut → berhenti (provisioning ulang)");

        // 6) ditolak permanen (izin) → rejected
        t.script.add(resp(403, Json.obj("detail", Json.obj("code", "SCOPE_DENIED", "message", "di luar cakupan")).toString()));
        eng.runOnce("usr_A", 10);
        check(OutboxItem.REJECTED.equals(store.get(c2.id).status), "403 cakupan → ditolak, tidak diulang");

        // 7) milik operator lain tidak dikirim atas nama operator ini
        OutboxItem b3 = Outbox.batch(s, g.snapshot(), Collections.singleton(CoreTest.E3), Collections.<String>emptyList(), "", "", false, B, null, now, 0, 0);
        store.enqueue(b3);
        int before = t.seen.size();
        eng.runOnce("usr_A", 10);
        check(t.seen.size() == before && OutboxItem.PENDING.equals(store.get(b3.id).status), "antrean operator B tidak dikirim saat operator A login");
        token[0] = "tok-B";
        t.script.add(resp(409, Json.obj("detail", Json.obj("code", "IDEMPOTENCY_CONFLICT", "message", "isi berbeda")).toString()));
        eng.runOnce("usr_B", 10);
        check(OutboxItem.BLOCKED.equals(store.get(b3.id).status), "IDEMPOTENCY_CONFLICT → ditahan untuk peninjauan (ID tidak diganti)");
        check(heard.contains(b1.id + ":accepted") && heard.contains(b2.id + ":conflict"), "pendengar layar menerima hasil final");

        // 8) ID antrean ganda ditolak penyimpanan
        boolean dup = false;
        try { store.enqueue(b1); } catch (IllegalStateException e) { dup = true; }
        check(dup, "penyimpanan: ID antrean ganda ditolak");
        System.out.println("SyncTest: " + passed + " PASS");
    }
}
