package id.kainnusantara.handheld;

import android.os.Bundle;
import android.text.InputType;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import id.kainnusantara.handheld.core.C72HardwareAdapter;
import id.kainnusantara.handheld.core.Epc;
import id.kainnusantara.handheld.core.Json;
import id.kainnusantara.handheld.core.Outbox;
import id.kainnusantara.handheld.core.OutboxItem;
import id.kainnusantara.handheld.core.ScanController;
import id.kainnusantara.handheld.core.WriteFlow;

/**
 * Tulis / ganti tag roll (K-OPN-05: EPC dibuat SISTEM lalu ditulis). Alur: pilih roll (label/nomor/tag lama/daftar
 * Belum Tag) → ERP membuat niat tulis + EPC baru (butuh sambungan) → TEMPEL tag di roll → tulis ke tag TERDEKAT (RSSI
 * terkuat) → baca ulang → konfirmasi masuk antrean (boleh offline). Tag lama tetap berlaku sampai konfirmasi diterima.
 */
public final class TagWriteActivity extends BaseActivity {
    private EditText code;
    private TextView rollView, msg;
    private Button writeBtn;
    private JSONObject roll, write;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        LinearLayout p = Ui.page(this);
        Ui.title(p, "✎  Tulis / ganti tag");
        Ui.muted(p, "EPC dibuat ERP lalu ditulis ke tag. Tempel tag di roll DULU, lalu tulis — baca ulang membuktikan chip di roll benar.");
        LinearLayout c = Ui.card(this);
        p.addView(c);
        code = Ui.field(c, "Nomor roll / pindai label", getIntent().getStringExtra("code"), InputType.TYPE_CLASS_TEXT);
        LinearLayout r = Ui.row(this);
        c.addView(r);
        half(r, "▣ Pindai label", v -> scanLabel());
        half(r, "◉ Baca tag lama", v -> readNearest());
        Ui.button(c, "⌕  Cari roll", true, v -> lookup());
        Ui.button(c, "▢  Daftar roll belum bertag", false, v -> untagged());
        rollView = Ui.body(p, "");
        writeBtn = Ui.button(p, "✎  TULIS TAG BARU", true, v -> startWrite());
        writeBtn.setEnabled(false);
        msg = Ui.body(p, "");
        if (code.getText().length() > 0) lookup();
    }

    private void half(LinearLayout row, String label, android.view.View.OnClickListener l) {
        Button b = Ui.button(row, label, false, l);
        b.setLayoutParams(new LinearLayout.LayoutParams(0, android.view.ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
    }

    private void scanLabel() {
        C72HardwareAdapter hw = app.hardware;
        app.radio.execute(() -> {
            boolean ok = hw.openBarcode(new C72HardwareAdapter.BarcodeListener() {
                public void onBarcode(String data, String sym) { hw.stopBarcode(); runOnUiThread(() -> { code.setText(data.trim()); lookup(); }); }
                public void onBarcodeError(String reason) { runOnUiThread(() -> toast("Barcode: " + reason)); }
            });
            if (!ok || !hw.startBarcode()) runOnUiThread(() -> toast("Pemindai barcode tidak tersedia — ketik nomor roll."));
        });
    }

    private void readNearest() {
        C72HardwareAdapter hw = app.hardware;
        app.radio.execute(() -> {
            String[] t = hw.ready() ? hw.readSingle() : null;
            runOnUiThread(() -> {
                if (t == null) { toast("Tidak ada tag terbaca."); return; }
                code.setText(Epc.canonical(t[0]) != null ? Epc.canonical(t[0]) : t[0]);
                lookup();
            });
        });
    }

    private void lookup() {
        String c = code.getText().toString().trim();
        if (c.isEmpty()) return;
        Ui.notice(msg, "⟳", "Mencari roll…", Ui.MUTED);
        bg(() -> app.api.lookup(c), res -> {
            roll = res.optJSONObject("roll");
            JSONObject tag = res.optJSONObject("tag"), pend = res.optJSONObject("pending_write");
            rollView.setText("Roll " + Json.str(roll, "roll_no") + " · " + Json.str(res, "sku") + " " + Json.str(res, "product_name")
                    + "\n" + Json.str(res, "warehouse_name") + " · " + Json.str(roll, "bin_code") + " · " + roll.optString("length_remaining") + " " + Json.str(roll, "unit")
                    + "\nTag sekarang: " + (tag == null ? "— (belum bertag)" : Epc.display(Json.str(tag, "epc")) + " [" + Json.str(tag, "status") + "]")
                    + (pend == null ? "" : "\n⟳ Ada niat tulis tertunda dari perangkat ini/lain."));
            writeBtn.setEnabled(true);
            writeBtn.setText(tag == null ? "✎  TULIS TAG BARU" : "✎  GANTI TAG (EPC baru)");
            Ui.notice(msg, "✓", "Roll ditemukan.", Ui.OK);
        }, e -> { writeBtn.setEnabled(false); Ui.notice(msg, "✕", e.getMessage(), Ui.BAD); });
    }

    private void untagged() {
        bg(() -> app.api.untagged(""), res -> {
            JSONArray rows = res.optJSONArray("rolls");
            if (rows == null || rows.length() == 0) { toast("Tidak ada roll belum bertag di gudang Anda."); return; }
            String[] items = new String[Math.min(rows.length(), 300)];
            for (int i = 0; i < items.length; i++) {
                JSONObject r = rows.optJSONObject(i);
                items[i] = Json.str(r, "roll_no") + " · " + Json.str(r, "sku") + " · " + r.optString("length_remaining") + " " + Json.str(r, "unit");
            }
            new android.app.AlertDialog.Builder(this).setTitle("Belum bertag (" + rows.length() + ")").setItems(items, (d, w) -> {
                code.setText(Json.str(rows.optJSONObject(w), "id"));
                lookup();
            }).show();
        }, e -> toast(e.getMessage()));
    }

    private void startWrite() {
        if (roll == null) return;
        writeBtn.setEnabled(false);
        String clientId = app.store.kv("write.intent." + Json.str(roll, "id"), null);
        if (clientId == null) { clientId = "w-" + Json.uuid(); app.store.set("write.intent." + Json.str(roll, "id"), clientId); }
        final String cid = clientId;
        Ui.notice(msg, "⟳", "Meminta EPC baru dari ERP…", Ui.MUTED);
        bg(() -> app.api.tagWrite(cid, Json.str(roll, "id"), app.opSessionId(), app.userId(), ""), res -> {
            if (!"accepted".equals(Json.str(res, "status"))) {
                Ui.notice(msg, "✕", "ERP menolak: " + Json.str(res.optJSONObject("error"), "message"), Ui.BAD);
                app.store.set("write.intent." + Json.str(roll, "id"), null);
                writeBtn.setEnabled(true);
                return;
            }
            write = res.optJSONObject("write");
            Ui.confirm(this, "Tulis EPC " + Epc.tail(Json.str(write, "epc")), "Pastikan tag SUDAH menempel di roll " + Json.str(roll, "roll_no")
                    + " dan hanya tag itu yang dekat dengan C72 (±5–10 cm).", "Tulis sekarang", this::runWrite);
            writeBtn.setEnabled(true);
        }, e -> { Ui.notice(msg, "✕", "Butuh sambungan ke ERP untuk membuat EPC: " + e.getMessage(), Ui.BAD); writeBtn.setEnabled(true); });
    }

    private void runWrite() {
        ScanController sc = app.scanner;
        String epc = Json.str(write, "epc");
        Ui.notice(msg, "⟳", "Menulis & membaca ulang…", Ui.MUTED);
        app.radio.execute(() -> {
            if (!sc.acquire(ScanController.Mode.WRITING)) { runOnUiThread(() -> toast("Radio sedang dipakai.")); return; }
            WriteFlow.Result r;
            try { r = new WriteFlow(app.hardware, app.profile, Thread::sleep).write(epc, null); }
            finally { sc.release(ScanController.Mode.WRITING); }
            WriteFlow.Result res = r;
            runOnUiThread(() -> after(res));
        });
    }

    private void after(WriteFlow.Result r) {
        Outbox.Who who = app.who();
        String rollNo = Json.str(roll, "roll_no"), writeId = Json.str(write, "id");
        if (r.ok()) {
            beep(true);
            OutboxItem it = Outbox.tagConfirm(writeId, rollNo, r.verifiedEpc, r.tid, r.rssi, r.attempts, r.powerDbm, who, System.currentTimeMillis());
            app.store.enqueue(it);
            app.store.set("write.intent." + Json.str(roll, "id"), null);
            app.store.audit("Tag ditulis roll " + rollNo + " EPC " + r.verifiedEpc + " (konfirmasi antre " + it.id + ")");
            Ui.notice(msg, "✓", r.message + "\nKonfirmasi ke ERP " + (app.online ? "dikirim…" : "antre (offline)") + ". Tag lama berhenti berlaku setelah ERP menerima.", Ui.OK);
            writeBtn.setEnabled(false);
            app.requestSync();
            return;
        }
        beep(false);
        Ui.notice(msg, "✕", r.code + ": " + r.message, Ui.BAD);
        Ui.confirm(this, "Tulis gagal", r.message + "\n\nUlangi (EPC sama) atau batalkan niat tulis?", "Ulangi", this::runWrite);
        Button cancel = Ui.button((LinearLayout) msg.getParent(), "Batalkan niat tulis (catat gagal)", false, v -> {
            app.store.enqueue(Outbox.tagFail(writeId, rollNo, r.code + ": " + r.message, r.attempts, who, System.currentTimeMillis()));
            app.store.set("write.intent." + Json.str(roll, "id"), null);
            app.requestSync();
            toast("Dicatat gagal. EPC itu tidak dipakai.");
            finish();
        });
        cancel.setTag("cancel");
    }
}
