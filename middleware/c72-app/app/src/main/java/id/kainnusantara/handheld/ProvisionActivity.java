package id.kainnusantara.handheld;

import android.content.Intent;
import android.os.Bundle;
import android.text.InputType;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import id.kainnusantara.handheld.core.C72HardwareAdapter;
import id.kainnusantara.handheld.core.Json;
import id.kainnusantara.handheld.core.Pin;

/**
 * Provisioning perangkat (teknisi): alamat server ERP + device key (QR dari ERP "Perangkat handheld" atau ketik) →
 * uji {@code GET /api/handheld/device/config} → simpan terenkripsi. PIN pemeliharaan dibuat di sini bila belum ada.
 * Provisioning ulang (ganti server/key) hanya lewat PIN dan TIDAK menghapus antrean.
 */
public final class ProvisionActivity extends BaseActivity {
    private EditText url, key;
    private TextView msg;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        LinearLayout p = Ui.page(this);
        Ui.title(p, "Provisioning C72");
        Ui.muted(p, "KN Handheld " + BuildConfig.VERSION_NAME + " · LAB — perilaku perangkat belum terbukti uji meja.");
        LinearLayout c = Ui.card(this);
        p.addView(c);
        Ui.body(c, "1. Di ERP: Perangkat handheld → buat/rotasi key → tampil QR provisioning (sekali).");
        Ui.body(c, "2. Pindai QR itu, atau ketik alamat server & device key.");
        url = Ui.field(c, "Alamat server ERP (https://…)", app.store.kv("server.url", ""), InputType.TYPE_TEXT_VARIATION_URI);
        key = Ui.field(c, "Device key (dk_…)", "", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        Ui.button(c, "▣  Pindai QR provisioning", false, v -> scanQr());
        Ui.button(c, "✓  Uji & simpan", true, v -> save());
        msg = Ui.body(p, "");
        Ui.button(p, "Mode diagnostik (uji meja, PIN)", false, v -> startActivity(new Intent(this, DiagnosticsActivity.class)));
        if (app.store.kv("pin.hash", null) == null) Ui.muted(p, "PIN pemeliharaan belum dibuat — akan diminta saat menyimpan.");
    }

    private void scanQr() {
        C72HardwareAdapter hw = app.hardware;
        if (hw == null) { toast("Pemindai belum siap."); return; }
        app.radio.execute(() -> {
            boolean ok = hw.openBarcode(new C72HardwareAdapter.BarcodeListener() {
                public void onBarcode(String data, String sym) { runOnUiThread(() -> applyQr(data)); hw.stopBarcode(); }
                public void onBarcodeError(String reason) { runOnUiThread(() -> toast("Barcode: " + reason)); }
            });
            if (!ok || !hw.startBarcode()) runOnUiThread(() -> toast("Pemindai barcode tidak bisa dibuka — ketik manual atau pakai keyboard emulator."));
        });
    }

    private void applyQr(String data) {
        try {
            JSONObject o = Json.parse(data);
            if (!"c72".equals(Json.str(o, "kn"))) throw new IllegalArgumentException("bukan QR provisioning C72");
            if (!Json.str(o, "url").isEmpty()) url.setText(Json.str(o, "url"));
            key.setText(Json.str(o, "key"));
            Ui.notice(msg, "✓", "QR terbaca untuk perangkat " + Json.str(o, "code") + ". Tekan Uji & simpan.", Ui.OK);
        } catch (RuntimeException e) {
            Ui.notice(msg, "✕", "QR tidak dikenali: " + e.getMessage(), Ui.BAD);
        }
    }

    private void save() {
        String u = url.getText().toString().trim().replaceAll("/+$", ""), k = key.getText().toString().trim();
        if (u.isEmpty() || k.isEmpty()) { Ui.notice(msg, "!", "Alamat server & device key wajib.", Ui.WARN); return; }
        if (app.store.kv("pin.hash", null) == null) { askNewPin(() -> save()); return; }
        String oldUrl = app.store.kv("server.url", ""), oldKey = app.secure.get("device_key");
        app.store.set("server.url", u);
        app.secure.put("device_key", k);
        Ui.notice(msg, "⟳", "Menguji ke ERP…", Ui.MUTED);
        bg(() -> app.api.deviceConfig(), cfg -> {
            app.store.set("device.config", cfg.toString());
            app.applyProfile(app.mergedProfile(cfg.optJSONObject("profile")));
            JSONObject d = cfg.optJSONObject("device");
            app.store.audit("Provisioning OK: " + Json.str(d, "code") + " @ " + u);
            Ui.notice(msg, "✓", "Terhubung: " + Json.str(d, "name") + " · " + Json.str(d, "warehouse_name"), Ui.OK);
            startActivity(new Intent(this, LoginActivity.class));
            finish();
        }, e -> {
            if (oldKey != null) { app.store.set("server.url", oldUrl); app.secure.put("device_key", oldKey); }
            else { app.store.set("server.url", null); app.secure.remove("device_key"); }
            Ui.notice(msg, "✕", "Gagal: " + e.getMessage(), Ui.BAD);
        });
    }

    private void askNewPin(Runnable then) {
        LinearLayout box = Ui.col(this);
        EditText a = Ui.field(box, "PIN baru (6–12 angka)", "", InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        EditText b2 = Ui.field(box, "Ulangi PIN", "", InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        new android.app.AlertDialog.Builder(this).setTitle("Buat PIN pemeliharaan").setView(box)
                .setPositiveButton("Simpan", (d, w) -> {
                    String x = a.getText().toString(), y = b2.getText().toString();
                    String bad = Pin.validate(x);
                    if (bad != null || !x.equals(y)) { toast(bad != null ? bad : "PIN tidak sama."); return; }
                    app.store.set("pin.hash", Pin.hash(x));
                    app.store.audit("PIN pemeliharaan dibuat");
                    then.run();
                }).setNegativeButton("Batal", null).show();
    }
}
