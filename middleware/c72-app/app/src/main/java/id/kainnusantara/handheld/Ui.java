package id.kainnusantara.handheld;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.text.InputType;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;

/**
 * Pembentuk UI programatik (tanpa pustaka tambahan — build offline). Aturan layar handheld: tombol ≥ 56 dp, teks ≥ 16 sp
 * untuk angka utama, hasil SELALU ikon/tanda + teks (warna hanya penguat, bukan satu-satunya isyarat).
 */
final class Ui {
    private Ui() {}

    static final int INK = Color.rgb(20, 33, 51), MUTED = Color.rgb(90, 98, 110), BG = Color.rgb(246, 247, 249),
            OK = Color.rgb(18, 110, 44), WARN = Color.rgb(150, 92, 0), BAD = Color.rgb(176, 32, 32), BRAND = Color.rgb(0, 88, 204),
            CARD = Color.WHITE, LINE = Color.rgb(222, 226, 232);

    static int dp(Context c, float v) { return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, c.getResources().getDisplayMetrics()); }

    static LinearLayout page(Activity a) {
        ScrollView s = new ScrollView(a);
        s.setBackgroundColor(BG);
        s.setFillViewport(true);
        LinearLayout l = col(a);
        int p = dp(a, 12);
        l.setPadding(p, p, p, dp(a, 24));
        s.addView(l);
        a.setContentView(s);
        return l;
    }

    static LinearLayout col(Context c) { LinearLayout l = new LinearLayout(c); l.setOrientation(LinearLayout.VERTICAL); return l; }

    static LinearLayout row(Context c) {
        LinearLayout l = new LinearLayout(c);
        l.setOrientation(LinearLayout.HORIZONTAL);
        l.setGravity(Gravity.CENTER_VERTICAL);
        return l;
    }

    static LinearLayout card(Context c) {
        LinearLayout l = col(c);
        GradientDrawable g = new GradientDrawable();
        g.setColor(CARD);
        g.setCornerRadius(dp(c, 10));
        g.setStroke(dp(c, 1), LINE);
        l.setBackground(g);
        int p = dp(c, 12);
        l.setPadding(p, p, p, p);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, dp(c, 6), 0, dp(c, 6));
        l.setLayoutParams(lp);
        return l;
    }

    static TextView text(ViewGroup parent, String s, float sp, int color, boolean bold) {
        TextView t = new TextView(parent.getContext());
        t.setText(s);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(color);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setPadding(0, dp(parent.getContext(), 3), 0, dp(parent.getContext(), 3));
        parent.addView(t);
        return t;
    }

    static TextView title(ViewGroup p, String s) { return text(p, s, 20, INK, true); }
    static TextView body(ViewGroup p, String s) { return text(p, s, 15, INK, false); }
    static TextView muted(ViewGroup p, String s) { return text(p, s, 13, MUTED, false); }

    /** Tombol besar (tinggi 56 dp) — primer berwarna, sekunder bergaris. */
    static Button button(ViewGroup parent, String label, boolean primary, View.OnClickListener l) {
        Context c = parent.getContext();
        Button b = new Button(c);
        b.setText(label);
        b.setAllCaps(false);
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 17);
        b.setMinHeight(dp(c, 56));
        b.setMinimumHeight(dp(c, 56));
        GradientDrawable g = new GradientDrawable();
        g.setCornerRadius(dp(c, 10));
        if (primary) { g.setColor(BRAND); b.setTextColor(Color.WHITE); }
        else { g.setColor(Color.WHITE); g.setStroke(dp(c, 2), BRAND); b.setTextColor(BRAND); }
        b.setBackground(g);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, dp(c, 5), 0, dp(c, 5));
        b.setLayoutParams(lp);
        b.setOnClickListener(l);
        parent.addView(b);
        return b;
    }

    static void tint(Button b, int color) {
        GradientDrawable g = new GradientDrawable();
        g.setCornerRadius(dp(b.getContext(), 10));
        g.setColor(color);
        b.setBackground(g);
        b.setTextColor(Color.WHITE);
    }

    static EditText field(ViewGroup parent, String hint, String value, int inputType) {
        EditText e = new EditText(parent.getContext());
        e.setHint(hint);
        e.setText(value == null ? "" : value);
        e.setSingleLine(true);
        e.setTextSize(TypedValue.COMPLEX_UNIT_SP, 17);
        e.setMinHeight(dp(parent.getContext(), 52));
        e.setInputType(inputType == 0 ? InputType.TYPE_CLASS_TEXT : inputType);
        parent.addView(e);
        return e;
    }

    static Spinner spinner(ViewGroup parent, String[] labels) {
        Spinner s = new Spinner(parent.getContext());
        ArrayAdapter<String> a = new ArrayAdapter<>(parent.getContext(), android.R.layout.simple_spinner_dropdown_item, labels);
        s.setAdapter(a);
        s.setMinimumHeight(dp(parent.getContext(), 52));
        parent.addView(s);
        return s;
    }

    static CheckBox check(ViewGroup parent, String label, boolean checked) {
        CheckBox c = new CheckBox(parent.getContext());
        c.setText(label);
        c.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        c.setChecked(checked);
        c.setMinHeight(dp(parent.getContext(), 48));
        parent.addView(c);
        return c;
    }

    /** Kotak angka: tanda + angka besar + label (dipakai panel Diharapkan/Terbaca/Kurang/Lebih). */
    static TextView counter(LinearLayout row, String glyph, String label) {
        Context c = row.getContext();
        LinearLayout box = col(c);
        box.setGravity(Gravity.CENTER);
        int p = dp(c, 6);
        box.setPadding(p, p, p, p);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        box.setLayoutParams(lp);
        TextView n = new TextView(c);
        n.setText(glyph + " 0");
        n.setTextSize(TypedValue.COMPLEX_UNIT_SP, 24);
        n.setTypeface(Typeface.DEFAULT_BOLD);
        n.setTextColor(INK);
        n.setGravity(Gravity.CENTER);
        TextView l = new TextView(c);
        l.setText(label);
        l.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
        l.setTextColor(MUTED);
        l.setGravity(Gravity.CENTER);
        box.addView(n);
        box.addView(l);
        row.addView(box);
        return n;
    }

    static void alert(Activity a, String title, String msg) {
        if (a.isFinishing()) return;
        new AlertDialog.Builder(a).setTitle(title).setMessage(msg).setPositiveButton("OK", null).show();
    }

    static void confirm(Activity a, String title, String msg, String yes, Runnable onYes) {
        if (a.isFinishing()) return;
        new AlertDialog.Builder(a).setTitle(title).setMessage(msg).setPositiveButton(yes, (d, w) -> onYes.run()).setNegativeButton("Batal", null).show();
    }

    static void notice(TextView t, String glyph, String msg, int color) {
        t.setText(glyph + "  " + msg);
        t.setTextColor(color);
    }
}
