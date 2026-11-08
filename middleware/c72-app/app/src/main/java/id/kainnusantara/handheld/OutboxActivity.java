package id.kainnusantara.handheld;

import android.os.Bundle;
import android.text.InputType;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;

import id.kainnusantara.handheld.core.Json;
import id.kainnusantara.handheld.core.OutboxItem;
import id.kainnusantara.handheld.core.Pin;

/**
 * Antrean sinkron: status tiap kiriman (ikon + teks), coba ulang, peninjauan ber-PIN (kirim ulang item tertahan dengan
 * ID SAMA, atau arsipkan konflik setelah ditinjau — bukti TIDAK dihapus), ekspor JSON untuk diagnosis.
 */
public final class OutboxActivity extends BaseActivity {
    private LinearLayout list;
    private TextView status;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        LinearLayout p = Ui.page(this);
        Ui.title(p, "⟳  Antrean sinkron");
        status = Ui.muted(p, "");
        Ui.button(p, "⟳  Sinkron sekarang", true, v -> { app.requestSync(); app.main.postDelayed(this::render, 1500); });
        Ui.button(p, "⇩  Ekspor antrean (JSON)", false, v -> export());
        list = Ui.col(this);
        p.addView(list);
    }

    @Override protected void onResume() { super.onResume(); render(); }

    private void render() {
        syncLine(status);
        if (app.lastPass != null) status.setText(status.getText() + "\nSinkron terakhir: " + app.lastPass);
        list.removeAllViews();
        List<OutboxItem> items = app.store.recent(200);
        if (items.isEmpty()) { Ui.body(list, "Belum ada kiriman."); return; }
        for (OutboxItem it : items) {
            LinearLayout c = Ui.card(this);
            list.addView(c);
            Ui.text(c, it.statusText() + " · " + it.label, 15, OutboxItem.CONFLICT.equals(it.status) || OutboxItem.REJECTED.equals(it.status) ? Ui.BAD : Ui.INK, true);
            Ui.muted(c, it.type + " · " + Json.iso(it.createdMs) + " · operator " + app.store.kv("user.name." + it.userId, it.userId)
                    + (it.lastError.isEmpty() ? "" : "\n" + it.lastError));
            if (OutboxItem.BLOCKED.equals(it.status) || OutboxItem.CONFLICT.equals(it.status) || OutboxItem.REJECTED.equals(it.status)) {
                Ui.button(c, "Tinjau (PIN)…", false, v -> review(it));
            }
        }
    }

    private void review(OutboxItem it) {
        LinearLayout box = Ui.col(this);
        Ui.muted(box, "Kirim ulang memakai ID & isi SAMA (aman, tidak menggandakan). Arsipkan = tandai sudah ditinjau; bukti tetap tersimpan.");
        EditText pin = Ui.field(box, "PIN", "", InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        new android.app.AlertDialog.Builder(this).setTitle(it.label).setView(box)
                .setPositiveButton("Kirim ulang", (d, w) -> act(it, pin.getText().toString(), OutboxItem.PENDING))
                .setNeutralButton("Arsipkan", (d, w) -> act(it, pin.getText().toString(), OutboxItem.ARCHIVED))
                .setNegativeButton("Batal", null).show();
    }

    private void act(OutboxItem it, String pin, String to) {
        String err = Pin.check(app.store, pin, System.currentTimeMillis());
        if (err != null) { toast(err); return; }
        it.status = to;
        it.nextDueMs = 0;
        app.store.update(it);
        app.store.audit("Antrean " + it.id + " → " + to + " (ditinjau ber-PIN)");
        if (OutboxItem.PENDING.equals(to)) app.requestSync();
        render();
    }

    private void export() {
        JSONArray a = new JSONArray();
        for (OutboxItem it : app.store.recent(5000)) {
            a.put(Json.obj("id", it.id, "type", it.type, "status", it.status, "kind", it.kind, "doc_id", it.docId, "user_id", it.userId,
                    "attempts", it.attempts, "created", Json.iso(it.createdMs), "last_error", it.lastError, "label", it.label,
                    "body", Json.parseOrEmpty(it.body), "response", Json.parseOrEmpty(it.response)));
        }
        try {
            File dir = getExternalFilesDir("ekspor");
            File f = new File(dir, "antrean-" + System.currentTimeMillis() + ".json");
            try (FileOutputStream o = new FileOutputStream(f)) { o.write(Json.obj("exported_at", Json.now(), "items", a).toString(2).getBytes(StandardCharsets.UTF_8)); }
            Ui.alert(this, "Ekspor selesai", "Berkas: " + f.getAbsolutePath() + "\n(ambil lewat USB/adb). Berisi bukti pindai — jangan disebar.");
        } catch (Exception e) {
            toast("Ekspor gagal: " + e.getMessage());
        }
    }
}
