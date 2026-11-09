package id.kainnusantara.handheld;

import android.content.Intent;
import android.os.Bundle;
import android.provider.MediaStore;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Spinner;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import id.kainnusantara.handheld.core.C72HardwareAdapter;
import id.kainnusantara.handheld.core.Epc;
import id.kainnusantara.handheld.core.Json;
import id.kainnusantara.handheld.core.Outbox;
import id.kainnusantara.handheld.core.OutboxItem;
import id.kainnusantara.handheld.core.ReadAggregator;
import id.kainnusantara.handheld.core.RegistrationForm;
import id.kainnusantara.handheld.core.ScanController;
import id.kainnusantara.handheld.core.Snapshot;
import id.kainnusantara.handheld.core.WriteFlow;

/**
 * Daftar Awal (pendaftaran ulang roll fisik + tag). Form LENGKAP sama dengan HP/desktop. Mode EPC sistem (K-OPN-05):
 * EPC dari CADANGAN perangkat (diminta saat online) → ditulis ke tag terdekat + baca ulang → baris masuk antrean
 * (offline boleh) berstatus "tag sudah ditulis". Mode EPC bawaan: EPC tag terkuat dibaca. Bin, produk, satuan, PT & lot
 * tetap terisi untuk roll berikutnya (satu rak biasanya produk sama).
 */
public final class RegistrationActivity extends BaseActivity {
    private static final int PHOTO = 41;
    private String sid;
    private Snapshot snap;
    private boolean system;
    private final RegistrationForm form = new RegistrationForm();
    private JSONArray bins = new JSONArray(), owners = new JSONArray(), products = new JSONArray();
    private String[] units = {"meter", "yard", "kg"};
    private Spinner binSp, unitSp, gradeSp, ownerSp;
    private EditText search, note, qty, lot, dye, oldNo;
    private CheckBox unrec, fromLabel;
    private TextView productView, epcView, msg, poolView, recentView;
    private LinearLayout results;
    private Button actionBtn;
    private String readEpc;
    private String pendingPhoto;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        sid = getIntent().getStringExtra("doc_id");
        LinearLayout p = Ui.page(this);
        Ui.title(p, "+  Daftar Awal · " + getIntent().getStringExtra("title"));
        msg = Ui.body(p, "Memuat sesi…");
        LinearLayout binCard = Ui.card(this);
        p.addView(binCard);
        Ui.text(binCard, "Bin aktif", 14, Ui.MUTED, true);
        binSp = Ui.spinner(binCard, new String[]{"(memuat bin…)"});
        Ui.button(binCard, "▣  Pindai label bin", false, v -> scanBarcode(true));
        Ui.button(binCard, "Rak bin ini selesai", false, v -> rackDone());
        LinearLayout pc = Ui.card(this);
        p.addView(pc);
        Ui.text(pc, "Produk", 14, Ui.MUTED, true);
        productView = Ui.body(pc, "Belum dipilih");
        search = Ui.field(pc, "Cari SKU / nama produk", "", InputType.TYPE_CLASS_TEXT);
        results = Ui.col(this);
        pc.addView(results);
        Ui.button(pc, "▣  Pindai label supplier", false, v -> scanBarcode(false));
        unrec = Ui.check(pc, "Produk belum dikenali", false);
        note = Ui.field(pc, "Keterangan (warna/motif/kode di kain)", "", InputType.TYPE_CLASS_TEXT);
        Ui.button(pc, "□  Foto kain (produk belum dikenali)", false, v -> takePhoto());
        LinearLayout lc = Ui.card(this);
        p.addView(lc);
        Ui.text(lc, "Panjang & atribut", 14, Ui.MUTED, true);
        qty = Ui.field(lc, "Panjang", "", InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL);
        unitSp = Ui.spinner(lc, units);
        fromLabel = Ui.check(lc, "Panjang dari label (terverifikasi)", false);
        lot = Ui.field(lc, "Lot", "", InputType.TYPE_CLASS_TEXT);
        dye = Ui.field(lc, "Dye lot", "", InputType.TYPE_CLASS_TEXT);
        gradeSp = Ui.spinner(lc, new String[]{"Grade (bawaan A)", "A", "B", "BS", "C"});
        ownerSp = Ui.spinner(lc, new String[]{"(PT pemilik)"});
        oldNo = Ui.field(lc, "Nomor roll lama (label lama, opsional)", "", InputType.TYPE_CLASS_TEXT);
        LinearLayout ec = Ui.card(this);
        p.addView(ec);
        epcView = Ui.body(ec, "");
        poolView = Ui.muted(ec, "");
        actionBtn = Ui.button(ec, "✎  TULIS TAG & SIMPAN", true, v -> act());
        recentView = Ui.muted(p, "");
        search.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int a, int c, int d) { }
            public void onTextChanged(CharSequence s, int a, int c, int d) { }
            public void afterTextChanged(Editable e) { showResults(e.toString()); }
        });
        binSp.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            public void onItemSelected(AdapterView<?> a, View v, int i, long id) { app.store.set("reg.bin." + sid, String.valueOf(i)); }
            public void onNothingSelected(AdapterView<?> a) { }
        });
        String j = app.store.snapshot("registration", sid);
        if (j != null) apply(new Snapshot(Json.parse(j)));
        products = Json.parseOrEmpty(app.store.kv("catalog", "")).optJSONArray("products");
        if (products == null) products = new JSONArray();
        load();
    }

    @Override boolean usesTrigger() { return true; }
    @Override void onTriggerDown() { act(); }

    private void load() {
        bg(() -> app.api.expected("registration", sid, false, 5000), raw -> {
            app.store.putSnapshot("registration", sid, raw.toString(), System.currentTimeMillis());
            apply(new Snapshot(raw));
            refillPool();
        }, e -> msg.setText(snap == null ? "✕ Sesi belum tersimpan & ERP tidak terjangkau: " + e.getMessage() : "○ Offline — memakai data sesi tersimpan."));
        if (products.length() == 0 || System.currentTimeMillis() - Long.parseLong(app.store.kv("catalog.at", "0")) > 6 * 3600_000L) {
            bg(() -> app.api.catalog(), c -> { app.store.set("catalog", c.toString()); app.store.set("catalog.at", String.valueOf(System.currentTimeMillis()));
                products = c.optJSONArray("products") == null ? new JSONArray() : c.optJSONArray("products"); }, e -> { });
        }
    }

    private void apply(Snapshot s) {
        snap = s;
        JSONObject reg = s.registration() == null ? new JSONObject() : s.registration();
        system = "system".equals(Json.str(reg, "epc_mode"));
        bins = reg.optJSONArray("bins") == null ? new JSONArray() : reg.optJSONArray("bins");
        owners = reg.optJSONArray("owners") == null ? new JSONArray() : reg.optJSONArray("owners");
        JSONArray u = reg.optJSONArray("units");
        if (u != null && u.length() > 0) { units = new String[u.length()]; for (int i = 0; i < u.length(); i++) units[i] = u.optString(i); }
        String[] bl = new String[Math.max(1, bins.length())];
        if (bins.length() == 0) bl[0] = "(tidak ada bin di cakupan)";
        for (int i = 0; i < bins.length(); i++) { JSONObject x = bins.optJSONObject(i); bl[i] = Json.str(x, "code") + " · " + Json.str(x, "zone") + " › " + Json.str(x, "rack"); }
        binSp.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, bl));
        int saved = Integer.parseInt(app.store.kv("reg.bin." + sid, "0"));
        if (saved < bl.length) binSp.setSelection(saved);
        unitSp.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, units));
        String[] ol = new String[Math.max(1, owners.length())];
        int def = 0;
        if (owners.length() == 0) ol[0] = "(PT pemilik)";
        for (int i = 0; i < owners.length(); i++) { ol[i] = Json.str(owners.optJSONObject(i), "name"); if (Json.str(owners.optJSONObject(i), "id").equals(Json.str(reg, "default_owner"))) def = i; }
        ownerSp.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, ol));
        ownerSp.setSelection(def);
        msg.setText(s.title + " · " + s.statusLabel + " · EPC " + (system ? "DIBUAT SISTEM (ditulis ke tag)" : "BAWAAN TAG (dibaca)") + " · " + s.rows.size() + " baris di ERP"
                + (s.closed ? "\n✕ Sesi tidak berjalan — baris tidak akan diterima." : ""));
        actionBtn.setText(system ? "✎  TULIS TAG & SIMPAN" : "◉  BACA TAG");
        updateEpc();
        renderRecent();
    }

    private void refillPool() {
        if (!system || app.store.poolFree(sid) >= 20) { updateEpc(); return; }
        bg(() -> app.api.epcPool(sid, 50), r -> {
            JSONArray e = r.optJSONArray("epcs");
            List<String> l = new ArrayList<>();
            for (int i = 0; e != null && i < e.length(); i++) l.add(e.optString(i));
            app.store.poolAdd(sid, l);
            updateEpc();
        }, e -> updateEpc());
    }

    private void updateEpc() {
        if (system) {
            int free = app.store.poolFree(sid);
            epcView.setText("Tempel tag di roll, dekatkan C72, lalu tekan TULIS (atau pemicu).");
            poolView.setText("Cadangan EPC di HP: " + free + (free < 5 ? "  ! hampir habis — sambungkan ke ERP" : "  (cukup untuk kerja offline)"));
        } else {
            epcView.setText(readEpc == null ? "Tekan BACA TAG: EPC tag terkuat dipakai." : "EPC terbaca: " + Epc.display(readEpc));
            poolView.setText("");
            actionBtn.setText(readEpc == null ? "◉  BACA TAG" : "✓  SIMPAN BARIS");
        }
    }

    private void showResults(String term) {
        results.removeAllViews();
        String t = term.trim().toLowerCase(Locale.ROOT);
        if (t.length() < 2) return;
        int n = 0;
        for (int i = 0; i < products.length() && n < 8; i++) {
            JSONObject pr = products.optJSONObject(i);
            if ((Json.str(pr, "sku") + " " + Json.str(pr, "name")).toLowerCase(Locale.ROOT).contains(t)) {
                n++;
                Button bt = Ui.button(results, Json.str(pr, "sku") + " — " + Json.str(pr, "name") + " (" + Json.str(pr, "base_unit") + ")", false, v -> pick(pr));
                bt.setTextSize(14);
            }
        }
        if (n == 0) Ui.muted(results, products.length() == 0 ? "Katalog produk belum terunduh (butuh sambungan sekali)." : "Tidak ada produk cocok.");
    }

    private void pick(JSONObject pr) {
        form.productId = Json.str(pr, "id");
        form.productLabel = Json.str(pr, "sku") + " — " + Json.str(pr, "name");
        productView.setText("✓ " + form.productLabel + (Json.str(pr, "superseded_by").isEmpty() ? "" : "\n! digantikan — ERP mengalihkan ke penggantinya"));
        selectUnit(Json.str(pr, "base_unit"));
        unrec.setChecked(false);
        results.removeAllViews();
        search.setText("");
    }

    private void selectUnit(String u) { for (int i = 0; i < units.length; i++) if (units[i].equalsIgnoreCase(u)) unitSp.setSelection(i); }

    private void scanBarcode(boolean forBin) {
        C72HardwareAdapter hw = app.hardware;
        app.radio.execute(() -> {
            boolean ok = hw.openBarcode(new C72HardwareAdapter.BarcodeListener() {
                public void onBarcode(String data, String sym) { hw.stopBarcode(); runOnUiThread(() -> { if (forBin) bin(data); else label(data); }); }
                public void onBarcodeError(String reason) { runOnUiThread(() -> toast("Barcode: " + reason)); }
            });
            if (!ok || !hw.startBarcode()) runOnUiThread(() -> toast("Pemindai barcode tidak tersedia — pilih manual."));
        });
    }

    private void bin(String code) {
        String c = code.trim();
        for (int i = 0; i < bins.length(); i++) {
            JSONObject x = bins.optJSONObject(i);
            if (Json.str(x, "code").equalsIgnoreCase(c) || Json.str(x, "id").equals(c)) { binSp.setSelection(i); beep(true); toast("Bin " + Json.str(x, "code")); return; }
        }
        beep(false);
        toast("Bin " + c + " di luar cakupan sesi.");
    }

    private void label(String raw) {
        form.labelRaw = raw;
        bg(() -> app.api.labelDecode(sid, raw), d -> {
            JSONObject pr = d.optJSONObject("product");
            if (pr != null) pick(pr);
            if (d.has("length") && !d.isNull("length")) { qty.setText(d.optString("length")); fromLabel.setChecked(true); selectUnit(Json.str(d, "length_unit")); }
            if (!Json.str(d, "lot").isEmpty()) lot.setText(Json.str(d, "lot"));
            if (!Json.str(d, "old_roll_no").isEmpty()) oldNo.setText(Json.str(d, "old_roll_no"));
            toast(Json.str(d, "message").isEmpty() ? "Label terbaca." : Json.str(d, "message"));
        }, e -> {   // offline: cocokkan SKU di katalog lokal
            for (int i = 0; i < products.length(); i++) if (raw.toUpperCase(Locale.ROOT).contains(Json.str(products.optJSONObject(i), "sku").toUpperCase(Locale.ROOT)) && !Json.str(products.optJSONObject(i), "sku").isEmpty()) { pick(products.optJSONObject(i)); return; }
            toast("Label tidak bisa diurai offline — pilih produk manual. (" + e.getMessage() + ")");
        });
    }

    private void takePhoto() {
        String name = "reg-" + System.currentTimeMillis() + ".jpg";
        pendingPhoto = new File(PhotoProvider.dir(this), name).getAbsolutePath();
        Intent i = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
        i.putExtra(MediaStore.EXTRA_OUTPUT, PhotoProvider.uriFor(name));
        i.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION);
        try { startActivityForResult(i, PHOTO); } catch (RuntimeException e) { toast("Aplikasi kamera tidak tersedia."); }
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req == PHOTO && res == RESULT_OK && pendingPhoto != null && new File(pendingPhoto).length() > 0) { form.photoPath = pendingPhoto; toast("Foto tersimpan — diunggah setelah baris diterima ERP."); }
    }

    private void collect() {
        int bi = binSp.getSelectedItemPosition();
        JSONObject bn = bi >= 0 && bi < bins.length() ? bins.optJSONObject(bi) : null;
        form.binId = bn == null ? "" : Json.str(bn, "id");
        form.binCode = bn == null ? "" : Json.str(bn, "code");
        int oi = ownerSp.getSelectedItemPosition();
        form.ownerEntityId = oi >= 0 && oi < owners.length() ? Json.str(owners.optJSONObject(oi), "id") : "";
        form.unrecognized = unrec.isChecked();
        form.note = note.getText().toString();
        form.qty = qty.getText().toString();
        form.unit = units.length == 0 ? "" : units[Math.max(0, unitSp.getSelectedItemPosition())];
        form.lengthFromLabel = fromLabel.isChecked();
        form.lot = lot.getText().toString();
        form.dyeLot = dye.getText().toString();
        form.grade = gradeSp.getSelectedItemPosition() <= 0 ? "" : String.valueOf(gradeSp.getSelectedItem());
        form.oldRollNo = oldNo.getText().toString();
    }

    private void act() {
        if (snap == null) { toast("Sesi belum dimuat."); return; }
        collect();
        if (!system && readEpc == null) { readTag(); return; }
        List<String> errs = form.validate(!system, readEpc);
        if (!errs.isEmpty()) { Ui.alert(this, "Lengkapi form", String.join("\n", errs)); beep(false); return; }
        if (system) writeAndSave(); else save(readEpc, false);
    }

    private void readTag() {
        ScanController sc = app.scanner;
        app.radio.execute(() -> {
            if (!sc.acquire(ScanController.Mode.WRITING)) return;
            List<ReadAggregator.Tag> tags;
            try {
                ReadAggregator agg = new ReadAggregator(50);
                app.hardware.beginInventory((e, tid, r, m, w) -> agg.offer(e, tid, r, m, w));
                try { Thread.sleep(app.profile.writeScanMs); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); }
                app.hardware.stopInventory();
                tags = agg.byStrength();
            } finally { sc.release(ScanController.Mode.WRITING); }
            List<ReadAggregator.Tag> t = tags;
            runOnUiThread(() -> {
                if (t.isEmpty() || !t.get(0).valid) { toast("Tidak ada tag EPC-96 terbaca."); beep(false); return; }
                if (t.size() > 1 && t.get(0).rssiMax != null && t.get(1).rssiMax != null && t.get(0).rssiMax - t.get(1).rssiMax < app.profile.minRssiGapDb) {
                    toast("Beberapa tag berdekatan — jauhkan tag lain."); beep(false); return;
                }
                readEpc = t.get(0).epc;
                beep(true);
                updateEpc();
            });
        });
    }

    private void writeAndSave() {
        String epc = app.store.poolTake(sid);
        if (epc == null) { refillPool(); Ui.alert(this, "Cadangan EPC habis", "Sambungkan ke ERP untuk mengambil cadangan EPC, lalu ulangi."); return; }
        ScanController sc = app.scanner;
        actionBtn.setEnabled(false);
        epcView.setText("⟳ Menulis " + Epc.tail(epc) + " & membaca ulang…");
        app.radio.execute(() -> {
            if (!sc.acquire(ScanController.Mode.WRITING)) { runOnUiThread(() -> actionBtn.setEnabled(true)); return; }
            WriteFlow.Result r;
            try { r = new WriteFlow(app.hardware, app.profile, Thread::sleep).write(epc, null); }
            finally { sc.release(ScanController.Mode.WRITING); }
            WriteFlow.Result res = r;
            runOnUiThread(() -> {
                actionBtn.setEnabled(true);
                if (!res.ok()) {
                    // EPC ini sengaja TIDAK dipakai ulang (chip mungkin sudah tertulis sebagian) — percobaan berikut memakai EPC baru.
                    beep(false);
                    Ui.alert(this, "Tulis tag gagal", res.message + "\nEPC " + Epc.tail(epc) + " tidak dipakai. Ulangi untuk mencoba EPC berikutnya.");
                    updateEpc();
                    return;
                }
                save(epc, true);
            });
        });
    }

    private void save(String epc, boolean written) {
        String cid = "l-" + Json.uuid();
        JSONObject line = form.toLine(cid, epc, written, Json.iso(app.clock.now()));
        JSONObject local = Json.parseOrEmpty(line.toString());
        Json.put(local, "photo_path", form.photoPath);
        Json.put(local, "product_label", form.productLabel);
        Json.put(local, "bin_code", form.binCode);
        app.store.regLine(cid, sid, epc, local.toString(), "queued", null, "");
        if (system) app.store.poolUsed(epc, cid);
        List<JSONObject> lines = new ArrayList<>();
        lines.add(line);
        OutboxItem it = Outbox.registrationLines(sid, snap.number, lines, app.who(), System.currentTimeMillis());
        app.store.enqueue(it);
        app.store.audit("Daftar Awal " + sid + " baris " + cid + " EPC " + epc + (written ? " (ditulis)" : " (dibaca)"));
        beep(true);
        Ui.notice(msg, "✓", "Roll tersimpan di HP (" + Epc.tail(epc) + ")" + (app.online ? " — mengirim…" : " — dikirim saat tersambung") + ". Lanjut roll berikutnya.", Ui.OK);
        form.nextRoll();
        qty.setText(""); fromLabel.setChecked(false); oldNo.setText("");
        if (form.unrecognized) note.setText("");
        readEpc = null;
        updateEpc();
        renderRecent();
        app.requestSync();
        if (system && app.store.poolFree(sid) < 20) refillPool();
    }

    private void rackDone() {
        int bi = binSp.getSelectedItemPosition();
        JSONObject bn = bi >= 0 && bi < bins.length() ? bins.optJSONObject(bi) : null;
        if (bn == null) return;
        String rack = Json.str(bn, "rack_id");
        Ui.confirm(this, "Rak selesai", "Tandai rak " + Json.str(bn, "rack") + " selesai didaftarkan?", "Tandai", () -> bg(() -> app.api.rackDone(sid, rack),
                r -> toast("Rak ditandai selesai (" + r.optInt("racks_done") + "/" + r.optInt("racks_total") + ")."), e -> toast("Butuh sambungan: " + e.getMessage())));
    }

    private void renderRecent() {
        StringBuilder s = new StringBuilder("Baris terakhir di HP ini:");
        List<String[]> rows = app.store.regLines(sid, 10);
        if (rows.isEmpty()) s.append("\n—");
        for (String[] r : rows) {
            JSONObject j = Json.parseOrEmpty(r[2]);
            String st = r[3];
            String mark = "saved".equals(st) ? "✓ diterima ERP" : "queued".equals(st) ? "⟳ antre" : "! " + st + (r[5].isEmpty() ? "" : ": " + r[5]);
            s.append("\n").append(mark).append(" · ").append(Epc.tail(r[1])).append(" · ").append(Json.str(j, "bin_code")).append(" · ")
                    .append(j.optBoolean("unrecognized") ? "belum dikenali" : Json.str(j, "product_label")).append(" · ").append(j.optString("qty", "-"));
        }
        recentView.setText(s.toString());
    }
}
