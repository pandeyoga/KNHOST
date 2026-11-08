package id.kainnusantara.handheld;

import android.app.Application;
import android.net.ConnectivityManager;
import android.net.Network;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;

import org.json.JSONArray;
import org.json.JSONObject;

import java.security.SecureRandom;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

import id.kainnusantara.handheld.core.ApiClient;
import id.kainnusantara.handheld.core.C72HardwareAdapter;
import id.kainnusantara.handheld.core.ClockSync;
import id.kainnusantara.handheld.core.Json;
import id.kainnusantara.handheld.core.Outbox;
import id.kainnusantara.handheld.core.OutboxItem;
import id.kainnusantara.handheld.core.Profile;
import id.kainnusantara.handheld.core.ReadAggregator;
import id.kainnusantara.handheld.core.ScanController;
import id.kainnusantara.handheld.core.SimulatedHardware;
import id.kainnusantara.handheld.core.SyncEngine;

/**
 * Wadah tunggal aplikasi: penyimpanan, kredensial, klien API, radio (satu pemilik), mesin sinkron. Utas:
 * {@link #io} (HTTP & SQLite berat), {@link #radio} (panggilan SDK yang bisa memblok), {@link #sync} (antrean berkala).
 * UI thread tidak pernah memanggil HTTP atau loop radio.
 */
public final class App extends Application {
    private static App instance;

    public SqliteStore store;
    public SecureStore secure;
    public ClockSync clock;
    public ApiClient api;
    public SyncEngine syncEngine;
    public volatile C72HardwareAdapter hardware;
    public volatile ScanController scanner;
    public volatile Profile profile = Profile.defaults();
    public final Handler main = new Handler(Looper.getMainLooper());
    public final ExecutorService io = Executors.newSingleThreadExecutor(r -> new Thread(r, "kn-io"));
    public final ExecutorService radio = Executors.newSingleThreadExecutor(r -> new Thread(r, "kn-radio"));
    public final ScheduledExecutorService sync = Executors.newSingleThreadScheduledExecutor(r -> new Thread(r, "kn-sync"));
    public volatile boolean online = true;
    public volatile String hardwareError = "";

    public static App get() { return instance; }

    @Override
    public void onCreate() {
        super.onCreate();
        instance = this;
        store = new SqliteStore(this);
        secure = new SecureStore(this);
        clock = new ClockSync(new ClockSync.Source() {
            public long mono() { return SystemClock.elapsedRealtime(); }
            public long deviceWall() { return System.currentTimeMillis(); }
        }, 5000, 15 * 60_000L);
        api = new ApiClient(new ApiClient.HttpTransport(8000, 30000, BuildConfig.DEBUG), new ApiClient.Credentials() {
            public String baseUrl() { return store.kv("server.url", ""); }
            public String deviceKey() { return secure.get("device_key"); }
            public String userToken() { return secure.get("user_token"); }
        }, clock, SystemClock::elapsedRealtime);
        api.appVersion = BuildConfig.VERSION_NAME;
        String cfg = store.kv("device.config", "");
        if (!cfg.isEmpty()) profile = mergedProfile(Json.parseOrEmpty(cfg).optJSONObject("profile"));
        syncEngine = new SyncEngine(store, api, System::currentTimeMillis, profile.backoffMaxMs, new SecureRandom());
        syncEngine.hook = this::afterResult;
        setupHardware();
        watchNetwork();
        sync.scheduleWithFixedDelay(this::syncNow, 5, Math.max(5, profile.syncIntervalMs / 1000), TimeUnit.SECONDS);
    }

    /** Profil ERP + penimpaan lokal ber-PIN (daya/session/mode pemicu) — tetap dibatasi rentang aman Profile. */
    public Profile mergedProfile(JSONObject server) {
        JSONObject p = server == null ? new JSONObject() : Json.parseOrEmpty(server.toString());
        JSONObject local = Json.parseOrEmpty(store.kv("profile.local", ""));
        JSONObject rf = p.optJSONObject("rfid") == null ? new JSONObject() : p.optJSONObject("rfid");
        JSONObject tr = p.optJSONObject("trigger") == null ? new JSONObject() : p.optJSONObject("trigger");
        for (String k : new String[]{"power_dbm", "write_power_dbm", "locate_power_dbm", "session"}) if (local.has(k)) Json.put(rf, k, local.opt(k));
        if (local.has("trigger_mode")) Json.put(tr, "mode", local.optString("trigger_mode"));
        Json.put(p, "rfid", rf);
        Json.put(p, "trigger", tr);
        return new Profile(p);
    }

    public boolean simulation() { return "1".equals(store.kv("hw.simulation", isChainway() ? "0" : "1")); }

    public static boolean isChainway() {
        String m = (Build.MANUFACTURER + " " + Build.MODEL + " " + Build.BRAND).toUpperCase(java.util.Locale.ROOT);
        return m.contains("CHAINWAY") || m.contains("C72") || m.contains("RSCJA");
    }

    /** Radio dipilih sekali per proses: SDK Chainway pada unit C72, simulasi pada perangkat lain / bila dipilih (PIN). */
    public synchronized void setupHardware() {
        if (scanner != null && scanner.mode() != ScanController.Mode.IDLE) return;
        if (hardware != null) { final C72HardwareAdapter old = hardware; radio.execute(old::release); }
        hardware = simulation() ? new SimulatedHardware(true) : new ChainwayC72Adapter(this);
        scanner = new ScanController(hardware, new ReadAggregator(profile.maxReads), profile);
        final C72HardwareAdapter hw = hardware;
        radio.execute(() -> {
            try { hw.initialize(profile); hardwareError = ""; }
            catch (Exception e) { hardwareError = e.getMessage() == null ? e.toString() : e.getMessage(); store.audit("Init radio gagal: " + hardwareError); }
        });
    }

    public void applyProfile(Profile p) {
        profile = p;
        ScanController sc = scanner;
        if (sc != null) sc.profile(p);
        final C72HardwareAdapter hw = hardware;
        if (hw != null) radio.execute(() -> { if (hw.ready()) { hw.setPower(p.powerDbm); hw.setSession(p.session); } });
    }

    private void watchNetwork() {
        ConnectivityManager cm = getSystemService(ConnectivityManager.class);
        if (cm == null) return;
        cm.registerDefaultNetworkCallback(new ConnectivityManager.NetworkCallback() {
            @Override public void onAvailable(Network n) { online = true; sync.execute(App.this::syncNow); }
            @Override public void onLost(Network n) { online = false; }
        });
    }

    public String userId() { return store.kv("user.id", ""); }
    public String opSessionId() { return store.kv("op.session", ""); }
    public Outbox.Who who() { return new Outbox.Who(userId(), opSessionId()); }
    public boolean loggedIn() { return !userId().isEmpty() && secure.get("user_token") != null; }
    public boolean provisioned() { return !store.kv("server.url", "").isEmpty() && secure.get("device_key") != null; }

    public final Object syncLock = new Object();
    public volatile SyncEngine.Pass lastPass;

    public void syncNow() {
        if (!provisioned() || !loggedIn()) return;
        synchronized (syncLock) {
            try {
                lastPass = syncEngine.runOnce(userId(), 50);
                if (lastPass.sent > 0 || lastPass.blockedBy != null) store.audit("Sinkron: " + lastPass);
            } catch (RuntimeException e) {
                store.audit("Sinkron galat: " + e);
            }
        }
    }

    public void requestSync() { sync.execute(this::syncNow); }

    /** Hasil batch Daftar Awal → status baris lokal; baris tersimpan yang punya foto → antrean unggah foto. */
    void afterResult(OutboxItem it, JSONObject res) {
        if (!"registration".equals(it.kind) || !"batch".equals(it.type)) return;
        JSONArray items = res.optJSONArray("items");
        if (items == null || items.length() == 0) {
            JSONArray lines = Json.parseOrEmpty(it.body).optJSONArray("lines");
            JSONObject e = res.optJSONObject("error");
            for (int i = 0; lines != null && i < lines.length(); i++)
                store.regLineResult(Json.str(lines.optJSONObject(i), "client_line_id"), "conflict", null, e == null ? Json.str(res, "status") : Json.str(e, "message"));
            return;
        }
        for (int i = 0; i < items.length(); i++) {
            JSONObject o = items.optJSONObject(i);
            String cid = Json.str(o, "ref"), lineId = Json.str(o, "line_id"), result = Json.str(o, "result");
            store.regLineResult(cid, result, lineId.isEmpty() ? null : lineId, Json.str(o, "message"));
            if (!"saved".equals(result) || lineId.isEmpty()) continue;
            JSONObject line = Json.parseOrEmpty(store.regLineJson(cid));
            String photo = Json.str(line, "photo_path");
            if (photo.isEmpty() || !new java.io.File(photo).exists() || store.get("p-" + cid) != null) continue;
            OutboxItem p = new OutboxItem("p-" + cid, "photo", "POST", "/api/registration/sessions/" + it.docId + "/lines/" + lineId + "/photo",
                    Json.obj("file", photo, "client_line_id", cid).toString(), "registration_photo", it.docId, it.userId, it.opSessionId,
                    System.currentTimeMillis());
            p.label = "Foto baris " + Json.str(o, "epc");
            store.enqueue(p);
        }
    }
}
