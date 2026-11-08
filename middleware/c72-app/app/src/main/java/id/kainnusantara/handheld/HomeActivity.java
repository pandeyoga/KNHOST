package id.kainnusantara.handheld;

import android.content.Intent;
import android.os.Bundle;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.HashMap;
import java.util.Map;

import id.kainnusantara.handheld.core.Json;
import id.kainnusantara.handheld.core.TaskKind;

/**
 * Beranda: satu tombol besar per JENIS tugas (dibedakan jelas, hanya dari lokasi kerja operator & perangkat) + jumlah
 * dokumen terbuka; alat (tulis/ganti tag, cari tag, antrean, diagnostik); ganti operator.
 */
public final class HomeActivity extends BaseActivity {
    private TextView status, who;
    private final Map<String, Button> tiles = new HashMap<>();

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        LinearLayout p = Ui.page(this);
        who = Ui.title(p, "");
        status = Ui.muted(p, "");
        JSONObject me = Json.parseOrEmpty(app.store.kv("me", ""));
        JSONArray kinds = me.optJSONArray("kinds");
        Map<String, Boolean> allowed = new HashMap<>();
        for (int i = 0; kinds != null && i < kinds.length(); i++) allowed.put(Json.str(kinds.optJSONObject(i), "code"), kinds.optJSONObject(i).optBoolean("allowed"));
        for (TaskKind k : TaskKind.values()) {
            boolean ok = allowed.isEmpty() || Boolean.TRUE.equals(allowed.get(k.code));
            Button t = Ui.button(p, k.glyph + "  " + k.label + "\n" + k.hint, ok, v -> open(k));
            t.setEnabled(ok);
            if (!ok) t.setText(k.glyph + "  " + k.label + "\n✕ tanpa izin (" + k.hint + ")");
            tiles.put(k.code, t);
        }
        LinearLayout tools = Ui.card(this);
        p.addView(tools);
        Ui.text(tools, "Alat", 15, Ui.INK, true);
        Ui.button(tools, "✎  Tulis / ganti tag roll", false, v -> startActivity(new Intent(this, TagWriteActivity.class)));
        Ui.button(tools, "◎  Cari tag (sinyal)", false, v -> startActivity(new Intent(this, LocateActivity.class)));
        Ui.button(tools, "⟳  Antrean sinkron", false, v -> startActivity(new Intent(this, OutboxActivity.class)));
        Ui.button(tools, "⚙  Diagnostik (PIN)", false, v -> startActivity(new Intent(this, DiagnosticsActivity.class)));
        Ui.button(tools, "⇦  Ganti operator / keluar", false, v -> logout());
    }

    @Override
    protected void onResume() {
        super.onResume();
        JSONObject me = Json.parseOrEmpty(app.store.kv("me", ""));
        JSONObject u = me.optJSONObject("user"), d = me.optJSONObject("device");
        StringBuilder whs = new StringBuilder();
        JSONArray w = me.optJSONArray("warehouses");
        for (int i = 0; w != null && i < w.length(); i++) whs.append(i == 0 ? "" : ", ").append(Json.str(w.optJSONObject(i), "code"));
        who.setText(Json.str(u, "name") + " · " + Json.str(d, "code"));
        status.setText("Gudang: " + (whs.length() == 0 ? "—" : whs) + (app.simulation() ? "\n! MODE SIMULASI — tanpa radio" : "")
                + (app.hardwareError.isEmpty() ? "" : "\n✕ Radio: " + app.hardwareError));
        TextView sync = status;
        bg(() -> app.api.summary(), s -> {
            JSONArray ks = s.optJSONArray("kinds");
            for (int i = 0; ks != null && i < ks.length(); i++) {
                JSONObject k = ks.optJSONObject(i);
                Button t = tiles.get(Json.str(k, "code"));
                TaskKind tk = TaskKind.of(Json.str(k, "code"));
                if (t != null && tk != null && k.optBoolean("allowed")) t.setText(tk.glyph + "  " + tk.label + "  (" + k.optInt("open_count") + ")\n" + tk.hint);
            }
            app.store.set("summary", s.toString());
        }, e -> {
            TextView line = new TextView(this);
            syncLine(line);
            sync.setText(sync.getText() + "\n" + line.getText() + " · daftar tugas dari cache");
        });
    }

    private void open(TaskKind k) {
        Intent i = new Intent(this, TaskListActivity.class);
        i.putExtra("kind", k.code);
        startActivity(i);
    }

    private void logout() {
        int mine = app.store.pendingByUser().getOrDefault(app.userId(), 0);
        String warn = mine > 0 ? "Masih ada " + mine + " antrean milik Anda yang belum terkirim. Antrean TETAP tersimpan dan dikirim saat Anda login lagi.\n\n" : "";
        Ui.confirm(this, "Keluar", warn + "Keluar dari perangkat ini?", "Keluar", () -> bg(() -> {
            try { app.api.sessionEnd(app.opSessionId(), "logout"); } catch (Exception ignored) { }
            try { app.api.logout(); } catch (Exception ignored) { }
            return true;
        }, ok -> finishLogout(), e -> finishLogout()));
    }

    private void finishLogout() {
        app.store.audit("Logout operator " + app.store.kv("user.name", ""));
        app.secure.remove("user_token");
        app.store.set("user.id", null);
        app.store.set("op.session", null);
        app.store.set("me", null);
        startActivity(new Intent(this, LoginActivity.class));
        finish();
    }
}
