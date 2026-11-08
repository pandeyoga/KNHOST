package id.kainnusantara.handheld;

import android.app.Activity;
import android.media.AudioManager;
import android.media.ToneGenerator;
import android.os.Bundle;
import android.view.KeyEvent;
import android.widget.TextView;
import android.widget.Toast;

import id.kainnusantara.handheld.core.ApiClient;
import id.kainnusantara.handheld.core.ErrorPolicy;
import id.kainnusantara.handheld.core.OutboxItem;

/**
 * Dasar layar: akses {@link App}, kerja latar (HTTP/radio di luar UI thread), tombol pemicu fisik, bunyi, garis status
 * sinkron. Layar yang memakai radio meneruskan pemicu ke {@link #onTriggerDown()} / {@link #onTriggerUp()}.
 */
abstract class BaseActivity extends Activity {
    App app;
    private ToneGenerator tone;

    interface Work<T> { T run() throws Exception; }
    interface Done<T> { void ok(T value); }
    interface Fail { void fail(Exception e); }

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        app = App.get();
        try { tone = new ToneGenerator(AudioManager.STREAM_NOTIFICATION, 70); } catch (RuntimeException e) { tone = null; }
    }

    @Override
    protected void onDestroy() {
        if (tone != null) tone.release();
        super.onDestroy();
    }

    /** Jalankan di utas io lalu kembali ke UI. Galat API diterjemahkan (login ulang / perangkat dicabut). */
    <T> void bg(Work<T> work, Done<T> done, Fail fail) {
        app.io.execute(() -> {
            try {
                T v = work.run();
                runOnUiThread(() -> { if (!isFinishing()) done.ok(v); });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    if (isFinishing()) return;
                    if (e instanceof ApiClient.ApiException && ((ApiClient.ApiException) e).action == ErrorPolicy.Action.LOGIN_REQUIRED) onLoginRequired();
                    if (fail != null) fail.fail(e); else toast(e.getMessage());
                });
            }
        });
    }

    void onLoginRequired() { toast("Sesi login habis — login ulang (antrean tetap tersimpan)."); }

    void toast(String s) { Toast.makeText(this, s == null ? "" : s, Toast.LENGTH_LONG).show(); }

    void beep(boolean good) {
        if (tone == null) return;
        try { tone.startTone(good ? ToneGenerator.TONE_PROP_BEEP : ToneGenerator.TONE_SUP_ERROR, good ? 60 : 250); } catch (RuntimeException ignored) { }
    }

    boolean usesTrigger() { return false; }
    void onTriggerDown() { }
    void onTriggerUp() { }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (usesTrigger() && app.profile.isTrigger(keyCode)) {
            if (event.getRepeatCount() == 0) onTriggerDown();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    public boolean onKeyUp(int keyCode, KeyEvent event) {
        if (usesTrigger() && app.profile.isTrigger(keyCode)) { onTriggerUp(); return true; }
        return super.onKeyUp(keyCode, event);
    }

    /** Garis status: koneksi + antrean (ikon + teks). */
    void syncLine(TextView t) {
        int pending = app.store.count(OutboxItem.PENDING), conflict = app.store.count(OutboxItem.CONFLICT) + app.store.count(OutboxItem.REJECTED),
                blocked = app.store.count(OutboxItem.BLOCKED);
        StringBuilder b = new StringBuilder(app.online ? "● Online" : "○ OFFLINE — hasil disimpan di HP");
        b.append(pending == 0 ? " · ✓ antrean kosong" : " · ⟳ " + pending + " antre");
        if (conflict > 0) b.append(" · ! ").append(conflict).append(" konflik/ditolak");
        if (blocked > 0) b.append(" · ⏸ ").append(blocked).append(" tertahan");
        if (app.lastPass != null && app.lastPass.blockedBy != null && app.lastPass.blockedBy != ErrorPolicy.Action.RETRY)
            b.append("\n! ").append(ErrorPolicy.label(app.lastPass.blockedBy));
        t.setText(b.toString());
        t.setTextColor(!app.online || conflict > 0 ? Ui.WARN : Ui.MUTED);
    }
}
