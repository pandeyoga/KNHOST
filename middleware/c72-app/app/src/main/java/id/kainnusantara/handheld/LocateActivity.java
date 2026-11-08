package id.kainnusantara.handheld;

import android.os.Bundle;
import android.text.InputType;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import org.json.JSONObject;

import id.kainnusantara.handheld.core.Epc;
import id.kainnusantara.handheld.core.Json;
import id.kainnusantara.handheld.core.LocateMeter;
import id.kainnusantara.handheld.core.Parse;
import id.kainnusantara.handheld.core.ScanController;

/**
 * Cari tag lewat sinyal: angka RELATIF 0–100 + kata (Jauh/Mendekat/Dekat/Sangat dekat) + bunyi makin rapat — bukan
 * jarak/posisi rak (spesifikasi Kubus 02 §2.1). Sumber nilai: {@code startLocation} SDK bila profil mengizinkan, cadangan
 * RSSI pindai terfilter. Target = EPC dari daftar "Belum terbaca", nomor roll (dicari ke ERP), atau ketik.
 */
public final class LocateActivity extends BaseActivity {
    private EditText target;
    private TextView value, label, msg;
    private ProgressBar bar;
    private Button run;
    private volatile boolean active;
    private final LocateMeter meter = new LocateMeter(0.35);
    private long lastBeep;
    private final Runnable tick = new Runnable() {
        public void run() {
            int v = meter.value(System.currentTimeMillis());
            show(v);
            long iv = LocateMeter.beepIntervalMs(v);
            if (active && iv > 0 && System.currentTimeMillis() - lastBeep > iv) { beep(true); lastBeep = System.currentTimeMillis(); }
            if (active) app.main.postDelayed(this, 60);
        }
    };

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        LinearLayout p = Ui.page(this);
        Ui.title(p, "◎  Cari tag");
        Ui.muted(p, "Bantuan RELATIF: makin besar makin dekat. Bukan jarak sebenarnya.");
        target = Ui.field(p, "EPC (24 hex) atau nomor roll", getIntent().getStringExtra("epc"), InputType.TYPE_CLASS_TEXT);
        value = Ui.text(p, "0", 64, Ui.INK, true);
        value.setGravity(android.view.Gravity.CENTER);
        label = Ui.text(p, "Tidak terbaca", 22, Ui.MUTED, true);
        label.setGravity(android.view.Gravity.CENTER);
        bar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        bar.setMax(100);
        bar.setMinimumHeight(Ui.dp(this, 28));
        p.addView(bar);
        run = Ui.button(p, "◉  MULAI CARI  (atau pemicu)", true, v -> toggle());
        msg = Ui.muted(p, "");
    }

    @Override boolean usesTrigger() { return true; }
    @Override void onTriggerDown() { toggle(); }

    @Override
    protected void onPause() {
        stopLocate();
        super.onPause();
    }

    private void toggle() { if (active) stopLocate(); else resolveAndStart(); }

    private void resolveAndStart() {
        String t = target.getText().toString().trim();
        String epc = Epc.canonical(t);
        if (epc != null) { startLocate(epc); return; }
        if (t.isEmpty()) { toast("Isi EPC atau nomor roll."); return; }
        bg(() -> app.api.lookup(t), res -> {
            JSONObject tag = res.optJSONObject("tag");
            String e = tag == null ? null : Epc.canonical(Json.str(tag, "epc"));
            if (e == null) { toast("Roll ini belum bertag aktif."); return; }
            target.setText(e);
            startLocate(e);
        }, ex -> toast("Cari roll butuh sambungan: " + ex.getMessage()));
    }

    private void startLocate(String epc) {
        ScanController sc = app.scanner;
        active = true;
        run.setText("■  BERHENTI");
        Ui.tint(run, Ui.BAD);
        msg.setText("Sasaran " + Epc.display(epc));
        app.main.post(tick);
        app.radio.execute(() -> {
            if (!sc.acquire(ScanController.Mode.LOCATING)) { runOnUiThread(() -> { toast("Radio sedang dipakai."); stopUi(); }); return; }
            int before = app.hardware.getPower();
            app.hardware.setPower(app.profile.locatePowerDbm);
            boolean sdk = app.profile.useSdkLocate && app.hardware.startLocate(epc, (v, valid) -> meter.offer(v, valid, System.currentTimeMillis()));
            if (!sdk) {   // cadangan: pindai terfilter, RSSI tag sasaran → 0–100
                app.hardware.beginInventory((e, tid, rssi, mono, wall) -> {
                    if (epc.equals(Epc.normalizeRead(e))) meter.offer(LocateMeter.fromRssi(Parse.rssi(rssi)), true, System.currentTimeMillis());
                });
            }
            String mode = sdk ? "startLocation SDK" : "cadangan RSSI";
            runOnUiThread(() -> msg.setText(msg.getText() + " · " + mode));
            while (active) { try { Thread.sleep(100); } catch (InterruptedException ie) { break; } }
            if (sdk) app.hardware.stopLocate(); else app.hardware.stopInventory();
            if (before > 0) app.hardware.setPower(before);
            sc.release(ScanController.Mode.LOCATING);
        });
    }

    private void stopLocate() { active = false; stopUi(); }

    private void stopUi() {
        active = false;
        run.setText("◉  MULAI CARI  (atau pemicu)");
        Ui.tint(run, Ui.BRAND);
    }

    private void show(int v) {
        value.setText(String.valueOf(v));
        label.setText((v >= 85 ? "★ " : v > 0 ? "▲ " : "○ ") + LocateMeter.label(v));
        bar.setProgress(v);
    }
}
