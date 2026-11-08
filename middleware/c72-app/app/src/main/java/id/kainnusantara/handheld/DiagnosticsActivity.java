package id.kainnusantara.handheld;

import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.view.KeyEvent;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

import id.kainnusantara.handheld.core.BenchRunner;
import id.kainnusantara.handheld.core.Json;
import id.kainnusantara.handheld.core.Pin;
import id.kainnusantara.handheld.core.ScanController;

/**
 * Mode diagnostik uji meja (ber-PIN): init SDK, baca, tulis (+kembalikan), barcode, daya, session, cari tag, baterai,
 * kode tombol pemicu, ekspor JSON hasil. Juga: mode simulasi, penimpaan daya/mode pemicu lokal, provisioning ulang
 * (antrean TIDAK dihapus). Uji tulis mengubah EPC tag uji — pakai tag cadangan, bukan tag roll.
 */
public final class DiagnosticsActivity extends BaseActivity {
    private LinearLayout page;
    private TextView out, keys;
    private final List<BenchRunner.Step> steps = new ArrayList<>();
    private boolean unlocked;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        page = Ui.page(this);
        Ui.title(page, "⚙  Diagnostik & uji meja");
        if (app.store.kv("pin.hash", null) == null) setPin(); else askPin();
    }

    private void askPin() {
        LinearLayout box = Ui.col(this);
        EditText pin = Ui.field(box, "PIN pemeliharaan", "", InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        new android.app.AlertDialog.Builder(this).setTitle("PIN diperlukan").setView(box).setCancelable(false)
                .setPositiveButton("Buka", (d, w) -> {
                    String err = Pin.check(app.store, pin.getText().toString(), System.currentTimeMillis());
                    if (err != null) { toast(err); finish(); return; }
                    build();
                }).setNegativeButton("Batal", (d, w) -> finish()).show();
    }

    private void setPin() {
        LinearLayout box = Ui.col(this);
        EditText a = Ui.field(box, "PIN baru (6–12 angka)", "", InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        EditText c = Ui.field(box, "Ulangi PIN", "", InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        new android.app.AlertDialog.Builder(this).setTitle("Buat PIN pemeliharaan").setView(box).setCancelable(false)
                .setPositiveButton("Simpan", (d, w) -> {
                    String bad = Pin.validate(a.getText().toString());
                    if (bad != null || !a.getText().toString().equals(c.getText().toString())) { toast(bad != null ? bad : "PIN tidak sama."); finish(); return; }
                    app.store.set("pin.hash", Pin.hash(a.getText().toString()));
                    app.store.audit("PIN pemeliharaan dibuat (diagnostik)");
                    build();
                }).setNegativeButton("Batal", (d, w) -> finish()).show();
    }

    private void build() {
        unlocked = true;
        app.store.audit("Mode diagnostik dibuka");
        Ui.muted(page, Build.MANUFACTURER + " " + Build.MODEL + " · Android " + Build.VERSION.RELEASE + " · build " + Build.DISPLAY
                + "\nAplikasi " + BuildConfig.VERSION_NAME + " · radio: " + (app.hardware == null ? "-" : app.hardware.name())
                + (app.hardwareError.isEmpty() ? "" : "\n✕ " + app.hardwareError)
                + "\nProfil: " + app.profile.profileId + (app.profile.commissioned ? " (commissioned)" : " (BELUM commissioning)")
                + " · daya " + app.profile.powerDbm + " dBm · tulis " + app.profile.writePowerDbm + " dBm · S" + app.profile.session);
        LinearLayout t = Ui.card(this);
        page.addView(t);
        Ui.text(t, "Uji meja (langkah)", 16, Ui.INK, true);
        CheckBox withWrite = Ui.check(t, "Sertakan uji TULIS (pakai tag uji cadangan)", false);
        CheckBox restore = Ui.check(t, "Kembalikan EPC asal setelah uji tulis", true);
        CheckBox withBarcode = Ui.check(t, "Sertakan uji barcode (arahkan ke QR/barcode)", true);
        Ui.button(t, "▶  Jalankan semua langkah", true, v -> runSteps(r -> r.runAll(withWrite.isChecked(), withBarcode.isChecked(), restore.isChecked())));
        Ui.button(t, "Init SDK ulang", false, v -> { app.setupHardware(); toast("Init radio dijadwalkan."); });
        Ui.button(t, "Baca 5 detik", false, v -> runSteps(r -> one(r.inventory(5000))));
        Ui.button(t, "Baca tunggal", false, v -> runSteps(r -> one(r.single())));
        Ui.button(t, "Tulis + baca ulang (tag uji)", false, v -> Ui.confirm(this, "Uji tulis", "EPC tag terdekat akan DIUBAH. Pakai tag uji, bukan tag roll.", "Tulis", () -> runSteps(r -> one(r.write(restore.isChecked())))));
        Ui.button(t, "Barcode (10 dtk)", false, v -> runSteps(r -> one(r.barcode(10000))));
        Ui.button(t, "Daya set/baca ulang", false, v -> runSteps(r -> one(r.power(new int[]{app.profile.minPower, app.profile.writePowerDbm, app.profile.powerDbm, app.profile.maxPower}))));
        Ui.button(t, "Session set/baca ulang", false, v -> runSteps(r -> one(r.session())));
        Ui.button(t, "Cari tag (3 dtk)", false, v -> runSteps(r -> one(r.locate(3000))));
        Ui.button(t, "Baterai", false, v -> runSteps(r -> one(r.battery())));
        Ui.button(t, "⇩  Ekspor JSON hasil", false, v -> export());
        keys = Ui.body(t, "Tekan tombol pemicu/samping: kode tombol tampil di sini.");
        out = Ui.body(page, "");
        settings();
    }

    interface Plan { List<BenchRunner.Step> run(BenchRunner r); }

    private static List<BenchRunner.Step> one(BenchRunner.Step s) { List<BenchRunner.Step> l = new ArrayList<>(); l.add(s); return l; }

    private void runSteps(Plan plan) {
        ScanController sc = app.scanner;
        out.setText("⟳ Menjalankan…");
        app.radio.execute(() -> {
            if (!sc.acquire(ScanController.Mode.DIAGNOSTIC)) { runOnUiThread(() -> toast("Radio sedang dipakai.")); return; }
            List<BenchRunner.Step> got;
            try { got = plan.run(new BenchRunner(app.hardware, app.profile, Thread::sleep)); }
            finally { sc.release(ScanController.Mode.DIAGNOSTIC); }
            runOnUiThread(() -> {
                steps.addAll(got);
                StringBuilder s = new StringBuilder();
                for (BenchRunner.Step st : steps) s.append(st.line()).append('\n');
                out.setText(s.toString());
            });
        });
    }

    private void export() {
        JSONObject dev = Json.obj("manufacturer", Build.MANUFACTURER, "model", Build.MODEL, "android", Build.VERSION.RELEASE, "sdk_int", Build.VERSION.SDK_INT,
                "build", Build.DISPLAY, "device_config", Json.parseOrEmpty(app.store.kv("device.config", "")).optJSONObject("device"),
                "capabilities", app.hardware == null ? null : app.hardware.capabilities().toJson(), "setup", app.hardware == null ? null : app.hardware.setupReport(),
                "trigger_keys_seen", app.store.kv("diag.keys", ""));
        JSONObject rep = BenchRunner.report(steps, dev, BuildConfig.VERSION_NAME, app.profile);
        app.store.bench(rep.toString());
        try {
            String code = Json.str(Json.parseOrEmpty(app.store.kv("device.config", "")).optJSONObject("device"), "code");
            File f = new File(getExternalFilesDir("ujimeja"), "uji-meja-" + (code.isEmpty() ? "belum-provisioning" : code.replaceAll("[^A-Za-z0-9_-]", "_"))
                    + "-" + System.currentTimeMillis() + ".json");
            try (FileOutputStream o = new FileOutputStream(f)) { o.write(rep.toString(2).getBytes(StandardCharsets.UTF_8)); }
            Ui.alert(this, "Ekspor selesai", f.getAbsolutePath() + "\nAmbil lewat USB/adb lalu lampirkan ke laporan uji meja.");
        } catch (Exception e) {
            toast("Ekspor gagal: " + e.getMessage());
        }
    }

    private void settings() {
        LinearLayout s = Ui.card(this);
        page.addView(s);
        Ui.text(s, "Setelan lokal (ber-PIN)", 16, Ui.INK, true);
        CheckBox sim = Ui.check(s, "Mode simulasi (tanpa radio; bukti berlabel simulasi, mutasi stok ditolak)", app.simulation());
        sim.setOnCheckedChangeListener((v, on) -> { app.store.set("hw.simulation", on ? "1" : "0"); app.setupHardware(); app.store.audit("Mode simulasi " + (on ? "ON" : "OFF")); });
        JSONObject local = Json.parseOrEmpty(app.store.kv("profile.local", ""));
        EditText power = Ui.field(s, "Daya baca dBm (kosong = profil ERP)", local.optString("power_dbm", ""), InputType.TYPE_CLASS_NUMBER);
        EditText wpower = Ui.field(s, "Daya tulis dBm (kosong = profil ERP)", local.optString("write_power_dbm", ""), InputType.TYPE_CLASS_NUMBER);
        EditText session = Ui.field(s, "Session 0–3 (kosong = profil ERP)", local.optString("session", ""), InputType.TYPE_CLASS_NUMBER);
        CheckBox toggle = Ui.check(s, "Pemicu mode toggle (tekan sekali mulai, sekali berhenti)", "toggle".equals(local.optString("trigger_mode")));
        Ui.button(s, "Simpan setelan lokal", true, v -> {
            JSONObject o = new JSONObject();
            putInt(o, "power_dbm", power); putInt(o, "write_power_dbm", wpower); putInt(o, "session", session);
            if (toggle.isChecked()) Json.put(o, "trigger_mode", "toggle");
            app.store.set("profile.local", o.toString());
            app.applyProfile(app.mergedProfile(Json.parseOrEmpty(app.store.kv("device.config", "")).optJSONObject("profile")));
            app.store.audit("Setelan lokal diubah: " + o);
            toast("Tersimpan (dibatasi rentang aman profil).");
        });
        Ui.button(s, "Ambil ulang profil dari ERP", false, v -> bg(() -> app.api.deviceConfig(), cfg -> {
            app.store.set("device.config", cfg.toString());
            app.applyProfile(app.mergedProfile(cfg.optJSONObject("profile")));
            toast("Profil " + Json.str(cfg, "profile_version") + " diterapkan.");
        }, e -> toast(e.getMessage())));
        Ui.button(s, "Provisioning ulang (antrean tetap)", false, v -> Ui.confirm(this, "Provisioning ulang",
                "Alamat server & device key dihapus dari HP ini. Antrean & bukti TIDAK dihapus.", "Lanjut", () -> {
                    app.secure.remove("device_key");
                    app.store.audit("Provisioning ulang dimulai");
                    startActivity(new Intent(this, ProvisionActivity.class));
                    finish();
                }));
        Ui.muted(s, "Log audit terbaru:\n" + String.join("\n", app.store.auditTail(15)));
    }

    private static void putInt(JSONObject o, String k, EditText e) {
        String t = e.getText().toString().trim();
        if (!t.isEmpty()) try { Json.put(o, k, Integer.parseInt(t)); } catch (NumberFormatException ignored) { }
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (unlocked && keys != null && event.getRepeatCount() == 0) {
            keys.setText("Tombol: keyCode=" + keyCode + " (" + KeyEvent.keyCodeToString(keyCode) + ")" + (app.profile.isTrigger(keyCode) ? " ✓ pemicu profil" : " ✕ bukan pemicu profil"));
            String seen = app.store.kv("diag.keys", "");
            if (!(("," + seen + ",").contains("," + keyCode + ","))) app.store.set("diag.keys", seen.isEmpty() ? String.valueOf(keyCode) : seen + "," + keyCode);
            if (keyCode != KeyEvent.KEYCODE_BACK) return true;
        }
        return super.onKeyDown(keyCode, event);
    }
}
