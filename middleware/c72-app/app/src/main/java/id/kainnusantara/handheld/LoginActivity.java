package id.kainnusantara.handheld;

import android.content.Intent;
import android.os.Bundle;
import android.text.InputType;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.util.Arrays;
import java.util.Map;

import id.kainnusantara.handheld.core.Json;

/**
 * Login operator memakai akun ERP biasa (`/api/auth/login`) lalu mengikat operator ke perangkat
 * (`/api/handheld/session/start` — menutup sesi operator sebelumnya = ganti operator). Sandi hanya di memori.
 * Antrean milik operator lain tidak dikirim atas nama operator ini.
 */
public final class LoginActivity extends BaseActivity {
    private EditText email, password;
    private TextView msg;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        LinearLayout p = Ui.page(this);
        JSONObject cfg = Json.parseOrEmpty(app.store.kv("device.config", "")).optJSONObject("device");
        Ui.title(p, "Login operator");
        Ui.muted(p, "Perangkat " + Json.str(cfg, "code") + " · " + Json.str(cfg, "name") + "\n" + Json.str(cfg, "site_name")
                + " · " + Json.str(cfg, "warehouse_name") + (app.profile.commissioned ? "" : "\n! Profil belum commissioning — nilai radio = titik awal uji meja."));
        LinearLayout c = Ui.card(this);
        p.addView(c);
        email = Ui.field(c, "Email ERP", app.store.kv("last.email", ""), InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        password = Ui.field(c, "Password", "", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        Ui.button(c, "→  Masuk", true, v -> login());
        msg = Ui.body(p, "");
        Map<String, Integer> others = app.store.pendingByUser();
        if (!others.isEmpty()) {
            StringBuilder s = new StringBuilder("Antrean belum terkirim di HP ini:");
            for (Map.Entry<String, Integer> e : others.entrySet())
                s.append("\n⟳ ").append(e.getValue()).append(" item milik ").append(app.store.kv("user.name." + e.getKey(), e.getKey()));
            s.append("\nTiap antrean hanya dikirim saat pemiliknya login.");
            Ui.muted(p, s.toString());
        }
        Ui.button(p, "Mode diagnostik (PIN)", false, v -> startActivity(new Intent(this, DiagnosticsActivity.class)));
    }

    private void login() {
        String e = email.getText().toString().trim();
        char[] pw = password.getText().toString().toCharArray();
        password.setText("");
        if (e.isEmpty() || pw.length == 0) { Ui.notice(msg, "!", "Email & password wajib.", Ui.WARN); return; }
        Ui.notice(msg, "⟳", "Masuk…", Ui.MUTED);
        bg(() -> {
            JSONObject res = app.api.login(e, pw);
            Arrays.fill(pw, '\0');
            String token = Json.str(res, "token");
            if (token.isEmpty()) throw new IllegalStateException("ERP tidak mengembalikan token sesi.");
            app.secure.put("user_token", token);
            return app.api.sessionStart();
        }, me -> {
            JSONObject u = me.optJSONObject("user"), op = me.optJSONObject("operator_session");
            app.store.set("last.email", e);
            app.store.set("user.id", Json.str(u, "id"));
            app.store.set("user.name", Json.str(u, "name"));
            app.store.set("user.name." + Json.str(u, "id"), Json.str(u, "name"));
            app.store.set("op.session", Json.str(op, "id"));
            app.store.set("me", me.toString());
            app.store.audit("Login operator " + Json.str(u, "email") + " (sesi " + Json.str(op, "id") + ")");
            app.requestSync();
            startActivity(new Intent(this, HomeActivity.class));
            finish();
        }, ex -> {
            app.secure.remove("user_token");
            Ui.notice(msg, "✕", "Gagal masuk: " + ex.getMessage(), Ui.BAD);
        });
    }
}
