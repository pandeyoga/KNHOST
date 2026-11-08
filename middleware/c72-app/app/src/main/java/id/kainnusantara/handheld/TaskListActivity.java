package id.kainnusantara.handheld;

import android.content.Intent;
import android.os.Bundle;
import android.text.InputType;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import id.kainnusantara.handheld.core.Json;
import id.kainnusantara.handheld.core.OutboxItem;
import id.kainnusantara.handheld.core.TaskKind;

/** Daftar dokumen satu jenis tugas (server; cache bila offline). Ketuk → layar pindai per dokumen. */
public final class TaskListActivity extends BaseActivity {
    private TaskKind kind;
    private LinearLayout list;
    private TextView status;
    private EditText search;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        kind = TaskKind.of(getIntent().getStringExtra("kind"));
        if (kind == null) { finish(); return; }
        LinearLayout p = Ui.page(this);
        Ui.title(p, kind.glyph + "  " + kind.label);
        Ui.muted(p, kind.hint);
        status = Ui.muted(p, "");
        search = Ui.field(p, "Cari nomor dokumen / gudang", "", InputType.TYPE_CLASS_TEXT);
        Ui.button(p, "⟳  Muat ulang", false, v -> load());
        list = Ui.col(this);
        p.addView(list);
    }

    @Override
    protected void onResume() { super.onResume(); load(); }

    private void load() {
        syncLine(status);
        String q = search.getText().toString().trim();
        bg(() -> app.api.tasks(kind.code, q), res -> {
            app.store.set("tasks." + kind.code, res.toString());
            render(res, false);
        }, e -> {
            render(Json.parseOrEmpty(app.store.kv("tasks." + kind.code, "")), true);
            status.setText("○ Tidak tersambung (" + e.getMessage() + ") — daftar terakhir dari HP.");
        });
    }

    private void render(JSONObject res, boolean cached) {
        list.removeAllViews();
        JSONArray rows = res.optJSONArray("tasks");
        if (rows == null || rows.length() == 0) { Ui.body(list, cached ? "Belum ada daftar tersimpan untuk jenis ini." : "Tidak ada dokumen terbuka di lokasi kerja Anda."); return; }
        for (int i = 0; i < rows.length(); i++) {
            JSONObject t = rows.optJSONObject(i);
            String doc = Json.str(t, "doc_id");
            int pending = app.store.countForDoc(kind.code, doc, OutboxItem.PENDING);
            boolean snap = app.store.snapshot(kind.code, doc) != null;
            String line = Json.str(t, "number") + "  ·  " + Json.str(t, "status_label") + "\n" + Json.str(t, "title")
                    + "\n" + Json.str(t, "warehouse_name") + " · " + Json.str(t, "subtitle")
                    + (snap ? "\n✓ tersimpan di HP (bisa offline)" : "") + (pending > 0 ? "  ⟳ " + pending + " antre" : "");
            Ui.button(list, line, false, v -> open(t));
        }
    }

    private void open(JSONObject t) {
        Intent i = new Intent(this, kind == TaskKind.REGISTRATION ? RegistrationActivity.class : ScanActivity.class);
        i.putExtra("kind", kind.code);
        i.putExtra("doc_id", Json.str(t, "doc_id"));
        i.putExtra("title", Json.str(t, "number"));
        startActivity(i);
    }
}
