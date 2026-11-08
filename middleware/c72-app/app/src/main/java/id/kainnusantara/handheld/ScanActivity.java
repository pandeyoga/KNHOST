package id.kainnusantara.handheld;

import android.content.Intent;
import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.BaseAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.Spinner;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

import id.kainnusantara.handheld.core.C72HardwareAdapter;
import id.kainnusantara.handheld.core.DocMatcher;
import id.kainnusantara.handheld.core.Epc;
import id.kainnusantara.handheld.core.Json;
import id.kainnusantara.handheld.core.Outbox;
import id.kainnusantara.handheld.core.OutboxItem;
import id.kainnusantara.handheld.core.Parse;
import id.kainnusantara.handheld.core.ReadAggregator;
import id.kainnusantara.handheld.core.ScanController;
import id.kainnusantara.handheld.core.Snapshot;
import id.kainnusantara.handheld.core.SyncEngine;
import id.kainnusantara.handheld.core.TaskKind;

/**
 * Layar pindai PER DOKUMEN (keluhan pemilik: pindai satu per satu → kini per dokumen): buka dokumen → baca massal
 * (tombol besar / pemicu fisik) → Diharapkan / Terbaca / Kurang / Lebih → konfirmasi SEKALI. Bacaan dijadikan draf
 * tahan-mati selama layar dibuka; konfirmasi = batch antrean (offline boleh). Potong sampel memakai mode identifikasi.
 */
public final class ScanActivity extends BaseActivity implements ScanController.Listener {
    private TaskKind kind;
    private String docId;
    private Snapshot snap;
    private final Set<String> labels = new LinkedHashSet<>();
    private TextView head, info, cExp, cRead, cMiss, cExtra, notice, sync;
    private Button scanBtn, sendBtn, completeBtn, startBtn;
    private Spinner filter;
    private final RowsAdapter adapter = new RowsAdapter();
    private DocMatcher.Result last;
    private boolean dirty;
    private long lastDraftSave;
    private EditText lengthField, reasonField;
    private TextView pickedView;
    private final Runnable tick = new Runnable() {
        public void run() {
            refresh();
            if (!isFinishing()) app.main.postDelayed(this, 500);
        }
    };

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        kind = TaskKind.of(getIntent().getStringExtra("kind"));
        docId = getIntent().getStringExtra("doc_id");
        if (kind == null || docId == null) { finish(); return; }
        LinearLayout root = Ui.col(this);
        root.setBackgroundColor(Ui.BG);
        int pad = Ui.dp(this, 10);
        root.setPadding(pad, pad, pad, pad);
        setContentView(root);
        head = Ui.title(root, kind.glyph + " " + kind.label + " · " + getIntent().getStringExtra("title"));
        info = Ui.muted(root, "Memuat dokumen…");
        LinearLayout counters = Ui.row(this);
        root.addView(counters);
        cExp = Ui.counter(counters, "≡", "Diharapkan");
        cRead = Ui.counter(counters, "✓", "Terbaca");
        cMiss = Ui.counter(counters, "○", "Kurang");
        cExtra = Ui.counter(counters, "+", "Lebih");
        notice = Ui.body(root, "");
        startBtn = Ui.button(root, "▶  MULAI SESI", true, v -> loadSnapshot(true));
        startBtn.setVisibility(View.GONE);
        scanBtn = Ui.button(root, "◉  MULAI PINDAI  (atau tahan tombol pemicu)", true, v -> toggleScan());
        if (kind.flow == TaskKind.Flow.IDENTIFY) buildCutPanel(root);
        LinearLayout tools = Ui.row(this);
        root.addView(tools);
        Button labelBtn = smallButton(tools, "▣ Pindai label", v -> scanLabel());
        smallButton(tools, "⟳ Muat ulang", v -> loadSnapshot(false));
        filter = new Spinner(this);
        filter.setAdapter(new android.widget.ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item,
                new String[]{"Semua", "Belum terbaca", "Terbaca", "Lebih (bukan dokumen)", "Konflik"}));
        tools.addView(filter, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.2f));
        filter.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            public void onItemSelected(AdapterView<?> a, View v, int i, long id) { adapter.rebuild(); }
            public void onNothingSelected(AdapterView<?> a) { }
        });
        labelBtn.setTag("label");
        ListView list = new ListView(this);
        list.setAdapter(adapter);
        list.setOnItemLongClickListener((a, v, i, id) -> { locate(adapter.epcAt(i)); return true; });
        root.addView(list, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        if (kind.flow != TaskKind.Flow.IDENTIFY) {
            sendBtn = Ui.button(root, kind.sendLabel(), true, v -> send());
            if (kind.needsComplete) completeBtn = Ui.button(root, "✔  SELESAIKAN DOKUMEN", false, v -> complete());
        }
        sync = Ui.muted(root, "");
        loadCached();
        restoreDraft();
        loadSnapshot(false);
    }

    private Button smallButton(LinearLayout row, String label, View.OnClickListener l) {
        Button b = Ui.button(row, label, false, l);
        b.setLayoutParams(new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        b.setTextSize(14);
        return b;
    }

    @Override boolean usesTrigger() { return true; }
    @Override void onTriggerDown() { ScanController sc = app.scanner; app.radio.execute(() -> { if (app.profile.triggerHold) sc.start(); else sc.toggle(); }); }
    @Override void onTriggerUp() { ScanController sc = app.scanner; if (app.profile.triggerHold) app.radio.execute(sc::stop); }

    @Override
    protected void onResume() {
        super.onResume();
        app.scanner.listener(this);
        app.syncEngine.listener(this::onSynced);
        app.main.post(tick);
    }

    @Override
    protected void onPause() {
        app.main.removeCallbacks(tick);
        ScanController sc = app.scanner;
        app.radio.execute(sc::stop);
        sc.listener(null);
        app.syncEngine.listener(null);
        saveDraft();
        super.onPause();
    }

    // ── snapshot ────────────────────────────────────────────────────────────
    private void loadCached() {
        String j = app.store.snapshot(kind.code, docId);
        if (j != null) apply(new Snapshot(Json.parse(j)), true);
    }

    private void loadSnapshot(boolean start) {
        bg(() -> app.api.expected(kind.code, docId, start, 5000), raw -> {
            app.store.putSnapshot(kind.code, docId, raw.toString(), System.currentTimeMillis());
            apply(new Snapshot(raw), false);
        }, e -> {
            if (snap == null) Ui.notice(notice, "✕", "Dokumen belum tersimpan di HP dan ERP tidak terjangkau: " + e.getMessage(), Ui.BAD);
            else Ui.notice(notice, "○", "Offline — memakai daftar tersimpan (" + Math.round(snap.ageHours(app.clock.now()) * 10) / 10.0 + " jam). " + e.getMessage(), Ui.WARN);
        });
    }

    private void apply(Snapshot s, boolean cached) {
        snap = s;
        head.setText(kind.glyph + " " + kind.label + " · " + (s.number.isEmpty() ? docId : s.number));
        info.setText(s.title + " · " + s.statusLabel + (cached ? " · dari HP" : " · terbaru") + (s.untagged.isEmpty() ? "" : " · " + s.untagged.size() + " roll tanpa tag"));
        startBtn.setVisibility(s.needsStart ? View.VISIBLE : View.GONE);
        if (s.needsStart) Ui.notice(notice, "!", "Sesi belum dimulai. Tekan MULAI SESI (butuh sambungan) — sesi lama yang selesai tidak dibuka ulang otomatis.", Ui.WARN);
        else if (s.closed) Ui.notice(notice, "✕", "Dokumen sudah ditutup di ERP (" + s.statusLabel + ") — pindaian tidak akan diterapkan.", Ui.BAD);
        else if (s.ageHours(app.clock.now()) > app.profile.snapshotMaxAgeHours) Ui.notice(notice, "!", "Daftar di HP sudah tua — muat ulang saat tersambung.", Ui.WARN);
        else if (!cached) Ui.notice(notice, "✓", "Siap memindai " + s.rows.size() + " roll.", Ui.OK);
        dirty = true;
        refresh();
    }

    // ── pindai ──────────────────────────────────────────────────────────────
    private void toggleScan() {
        if (snap == null || snap.needsStart) { toast("Muat/mulai dokumen dulu."); return; }
        ScanController sc = app.scanner;
        app.radio.execute(sc::toggle);
    }

    @Override public void onState(ScanController.Mode mode, String message) {
        runOnUiThread(() -> {
            boolean on = mode == ScanController.Mode.SCANNING;
            scanBtn.setText(on ? "■  BERHENTI  (lepas pemicu)" : "◉  MULAI PINDAI  (atau tahan tombol pemicu)");
            Ui.tint(scanBtn, on ? Ui.BAD : Ui.BRAND);
            if (!on) saveDraft();
            if (message != null && !message.isEmpty() && !on) sync.setText("Radio: " + message);
        });
    }

    @Override public void onNewTag(String epc) { dirty = true; }

    private void scanLabel() {
        C72HardwareAdapter hw = app.hardware;
        app.radio.execute(() -> {
            boolean ok = hw.openBarcode(new C72HardwareAdapter.BarcodeListener() {
                public void onBarcode(String data, String sym) { hw.stopBarcode(); runOnUiThread(() -> addLabel(data)); }
                public void onBarcodeError(String reason) { runOnUiThread(() -> toast("Barcode: " + reason)); }
            });
            if (!ok || !hw.startBarcode()) runOnUiThread(this::typeLabel);
        });
    }

    private void typeLabel() {
        LinearLayout box = Ui.col(this);
        EditText e = Ui.field(box, "Nomor roll / isi label", "", InputType.TYPE_CLASS_TEXT);
        new android.app.AlertDialog.Builder(this).setTitle("Pemindai tidak tersedia — ketik label").setView(box)
                .setPositiveButton("Tambah", (d, w) -> addLabel(e.getText().toString())).setNegativeButton("Batal", null).show();
    }

    private void addLabel(String raw) {
        String code = Parse.clip(raw == null ? "" : raw.trim(), 120).toUpperCase(java.util.Locale.ROOT);
        if (code.isEmpty()) return;
        if (Epc.valid(code)) { app.scanner.aggregator().restore(code, null, 1, System.currentTimeMillis(), System.currentTimeMillis(), null); }
        else labels.add(code);
        Snapshot.Row r = snap == null ? null : snap.byLabel(code);
        beep(r != null);
        Ui.notice(notice, r != null ? "✓" : "?", r != null ? "Label " + code + " = roll dokumen." : "Label " + code + " bukan roll dokumen ini.", r != null ? Ui.OK : Ui.WARN);
        dirty = true;
        saveDraft();
    }

    // ── tampilan ────────────────────────────────────────────────────────────
    private void refresh() {
        if (snap == null) { syncLine(sync); return; }
        if (!dirty && app.scanner.mode() != ScanController.Mode.SCANNING) { syncLine(sync); return; }
        dirty = false;
        ReadAggregator agg = app.scanner.aggregator();
        DocMatcher.Local local = SyncEngine.localState(app.store, kind.code, docId);
        last = DocMatcher.match(snap, agg.epcs(), labels, local);
        cExp.setText("≡ " + last.expected);
        cRead.setText("✓ " + last.read);
        cMiss.setText("○ " + last.missing);
        cExtra.setText("+ " + last.extra.size());
        int toSend = last.toSend.size() + last.labelsToSend.size();
        if (sendBtn != null) {
            sendBtn.setText(kind.sendLabel() + (toSend > 0 ? "  (" + toSend + " baru)" : ""));
            sendBtn.setEnabled(toSend > 0 && !snap.needsStart);
        }
        if (completeBtn != null) {
            int pend = app.store.countForDoc(kind.code, docId, OutboxItem.PENDING);
            completeBtn.setEnabled(toSend == 0 && pend == 0 && !snap.closed && !snap.needsStart && !snap.sessionId.isEmpty());
            completeBtn.setText("✔  SELESAIKAN DOKUMEN" + (pend > 0 ? "  (tunggu " + pend + " antre)" : toSend > 0 ? "  (kirim dulu)" : ""));
        }
        if (pickedView != null) updatePicked();
        adapter.rebuild();
        syncLine(sync);
        if (System.currentTimeMillis() - lastDraftSave > 3000) saveDraft();
    }

    private void onSynced(OutboxItem it, JSONObject res) {
        if (!docId.equals(it.docId) || !kind.code.equals(it.kind)) return;
        runOnUiThread(() -> {
            dirty = true;
            String st = Json.str(res, "status");
            JSONObject sum = res.optJSONObject("summary");
            if ("conflict".equals(st) || "rejected".equals(st)) {
                JSONObject e = res.optJSONObject("error");
                Ui.notice(notice, "!", "ERP: " + (e == null ? st : Json.str(e, "message")), Ui.BAD);
                beep(false);
            } else if ("complete".equals(it.type)) {
                Ui.notice(notice, "✔", "Dokumen diselesaikan ERP — hasil: " + Json.str(res, "result"), Ui.OK);
                loadSnapshot(false);
            } else {
                Ui.notice(notice, "✓", "Diterima ERP: " + (sum == null ? "" : sum.toString().replace("\"", "")), Ui.OK);
                if (res.optBoolean("snapshot_stale")) loadSnapshot(false);
            }
        });
    }

    // ── kirim & selesaikan ──────────────────────────────────────────────────
    private void send() {
        if (snap == null || last == null) return;
        if (app.simulation() && !kind.simulationAllowed()) {
            Ui.alert(this, "Mode simulasi", "Bacaan simulasi tidak boleh memindah stok (" + kind.label + "). Matikan mode simulasi di Diagnostik.");
            return;
        }
        int miss = last.missing;
        String msg = last.summary() + (kind.mutatesOnSend ? "\n\nRoll terbaca akan dicatat " + (kind == TaskKind.PUTAWAY_IN ? "TIBA" : "DITERIMA")
                + " di ERP saat terkirim. Roll yang belum terbaca tetap menunggu (bisa trip berikutnya)." : "")
                + (miss > 0 && !kind.mutatesOnSend ? "\n\n" + miss + " roll belum terbaca — boleh dikirim bertahap." : "");
        Ui.confirm(this, kind.sendLabel(), msg, "Kirim", this::enqueueBatch);
    }

    private void enqueueBatch() {
        ReadAggregator agg = app.scanner.aggregator();
        List<ReadAggregator.Tag> tags = agg.snapshot();
        List<String> epcs = new ArrayList<>(last.toSend), lbls = new ArrayList<>(last.labelsToSend);
        String reason = "";
        if (!lbls.isEmpty() && (kind == TaskKind.OUTBOUND_SO || kind == TaskKind.OUTBOUND_SAMPLE)) { askLabelReason(epcs, lbls, tags); return; }
        doEnqueue(tags, epcs, lbls, reason);
    }

    private void askLabelReason(List<String> epcs, List<String> lbls, List<ReadAggregator.Tag> tags) {
        LinearLayout box = Ui.col(this);
        Ui.muted(box, "Roll tanpa tag hanya lolos lewat pengecualian supervisor (izin wms.untagged_override).");
        EditText e = Ui.field(box, "Alasan (min. 5 huruf)", "", InputType.TYPE_CLASS_TEXT);
        new android.app.AlertDialog.Builder(this).setTitle(lbls.size() + " label roll tanpa tag").setView(box)
                .setPositiveButton("Kirim", (d, w) -> doEnqueue(tags, epcs, lbls, e.getText().toString().trim()))
                .setNegativeButton("Tanpa label", (d, w) -> doEnqueue(tags, epcs, new ArrayList<>(), "")).show();
    }

    private void doEnqueue(List<ReadAggregator.Tag> tags, List<String> epcs, List<String> lbls, String reason) {
        int max = app.profile.maxReads;
        long now = System.currentTimeMillis();
        Outbox.Who who = app.who();
        ScanController sc = app.scanner;
        boolean sim = app.simulation();
        List<List<String>> chunks = new ArrayList<>();
        for (int i = 0; i < epcs.size(); i += max) chunks.add(new ArrayList<>(epcs.subList(i, Math.min(i + max, epcs.size()))));
        if (chunks.isEmpty()) chunks.add(new ArrayList<>());
        int made = 0;
        for (int c = 0; c < chunks.size(); c++) {
            List<String> lchunk = c == 0 ? lbls : new ArrayList<>();
            if (chunks.get(c).isEmpty() && lchunk.isEmpty()) continue;
            OutboxItem it = Outbox.batch(snap, tags, new LinkedHashSet<>(chunks.get(c)), lchunk, reason, "", sim, who, app.clock, now,
                    sc.firstWall(), sc.lastWall());
            app.store.enqueue(it);
            app.syncEngine.markQueued(it);
            made++;
        }
        app.store.audit("Batch " + kind.code + " " + docId + ": " + epcs.size() + " tag, " + lbls.size() + " label (" + made + " kiriman)");
        labels.removeAll(lbls);
        app.store.set(draftKey(), null);
        Ui.notice(notice, "⟳", made + " kiriman disimpan di HP" + (app.online ? " — mengirim…" : " — terkirim otomatis saat tersambung."), Ui.MUTED);
        dirty = true;
        app.requestSync();
    }

    private void complete() {
        if (snap == null || last == null) return;
        String msg = last.summary() + (last.missing > 0 ? "\n\n" + last.missing + " roll BELUM terbaca → hasil ERP 'bermasalah'." : "")
                + (last.extra.size() > 0 ? "\n" + last.extra.size() + " EPC lebih (bukan dokumen) tercatat." : "")
                + "\n\nHasil final ditentukan ERP.";
        Ui.confirm(this, "Selesaikan " + snap.number, msg, "Selesaikan", () -> {
            OutboxItem it = Outbox.complete(snap, app.who(), System.currentTimeMillis());
            app.store.enqueue(it);
            Ui.notice(notice, "⟳", "Permintaan selesai disimpan — dikirim setelah semua pindaian diterima ERP.", Ui.MUTED);
            app.requestSync();
        });
    }

    // ── draf tahan-mati ─────────────────────────────────────────────────────
    private String draftKey() { return "draft." + kind.code + "." + docId; }

    private void saveDraft() {
        lastDraftSave = System.currentTimeMillis();
        List<ReadAggregator.Tag> tags = app.scanner.aggregator().snapshot();
        if (tags.isEmpty() && labels.isEmpty()) { app.store.set(draftKey(), null); return; }
        JSONArray a = new JSONArray();
        for (ReadAggregator.Tag t : tags) a.put(Json.obj("epc", t.epc, "rssi", t.rssiMax, "count", t.count, "first", t.firstWall, "last", t.lastWall, "tid", t.tid));
        app.store.set(draftKey(), Json.obj("tags", a, "labels", new JSONArray(labels)).toString());
    }

    private void restoreDraft() {
        app.scanner.resetWindow();
        JSONObject d = Json.parseOrEmpty(app.store.kv(draftKey(), ""));
        JSONArray a = d.optJSONArray("tags"), l = d.optJSONArray("labels");
        ReadAggregator agg = app.scanner.aggregator();
        for (int i = 0; a != null && i < a.length(); i++) {
            JSONObject t = a.optJSONObject(i);
            agg.restore(Json.str(t, "epc"), t.isNull("rssi") ? null : t.optDouble("rssi"), t.optInt("count", 1), t.optLong("first"), t.optLong("last"), Json.str(t, "tid"));
        }
        for (int i = 0; l != null && i < l.length(); i++) labels.add(l.optString(i));
        if ((a != null && a.length() > 0) || !labels.isEmpty()) Ui.notice(notice, "↺", "Draf pindai sebelumnya dipulihkan (" + agg.unique() + " tag).", Ui.MUTED);
    }

    private void locate(String epc) {
        if (epc == null || epc.isEmpty()) return;
        Intent i = new Intent(this, LocateActivity.class);
        i.putExtra("epc", epc);
        startActivity(i);
    }

    // ── potong sampel (identifikasi) ────────────────────────────────────────
    private void buildCutPanel(LinearLayout root) {
        LinearLayout c = Ui.card(this);
        root.addView(c);
        pickedView = Ui.body(c, "Pindai roll induk (tag terkuat / label).");
        lengthField = Ui.field(c, "Panjang aktual dipotong", "", InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL);
        reasonField = Ui.field(c, "Alasan bila bukan roll saran FIFO", "", InputType.TYPE_CLASS_TEXT);
        Ui.button(c, "✂  POTONG (butuh sambungan)", true, v -> cut());
    }

    private String[] picked() {
        if (snap == null) return null;
        for (ReadAggregator.Tag t : app.scanner.aggregator().byStrength()) {
            Snapshot.Row r = snap.byEpc(t.epc);
            if (r != null) return new String[]{r.rollId, r.rollNo, t.epc, r.suggested ? "1" : "0"};
        }
        for (String l : labels) {
            Snapshot.Row r = snap.byLabel(l);
            if (r != null) return new String[]{r.rollId, r.rollNo, "", r.suggested ? "1" : "0"};
        }
        return null;
    }

    private void updatePicked() {
        JSONObject task = snap.task();
        if (lengthField.getText().length() == 0 && task != null) lengthField.setText(task.optString("quantity", ""));
        String[] p = picked();
        if (p == null) pickedView.setText("Pindai roll induk (tag terkuat / label). Saran FIFO: " + (task == null ? "-" : Json.str(task, "suggested_roll_no")));
        else pickedView.setText("✓ Roll terpilih: " + p[1] + ("1".equals(p[3]) ? " (saran FIFO)" : " (bukan saran — isi alasan)"));
    }

    private void cut() {
        String[] p = picked();
        if (p == null) { toast("Belum ada roll calon yang terbaca."); return; }
        Double len = Parse.decimal(lengthField.getText().toString());
        if (len == null || len <= 0) { toast("Panjang potong wajib > 0."); return; }
        String reason = reasonField.getText().toString().trim();
        String id = "k-" + Json.uuid();
        JSONObject body = Json.obj("client_request_id", id, "operator_session_id", app.opSessionId(), "user_id", app.userId(),
                "roll_id", p[0], "epc", p[2], "actual_length", len, "reason", reason);
        Ui.confirm(this, "Potong " + p[1], "Potong " + len + " dari roll " + p[1] + "?", "Potong", () -> bg(
                () -> app.api.call("POST", "/api/handheld/tasks/cutting/" + docId + "/cut", body, id, true), res -> {
                    if (!"accepted".equals(Json.str(res, "status"))) { Ui.alert(this, "Ditolak ERP", Json.str(res.optJSONObject("error"), "message")); return; }
                    JSONObject cut = res.optJSONObject("cut");
                    Ui.confirm(this, "Dipotong", "Roll potongan " + Json.str(cut, "child_roll_no") + " lahir TANPA tag.\nTempel tag baru lalu tulis EPC sekarang?",
                            "Tulis tag", () -> {
                                Intent i = new Intent(this, TagWriteActivity.class);
                                i.putExtra("code", Json.str(cut, "child_roll_id"));
                                startActivity(i);
                                finish();
                            });
                }, e -> Ui.alert(this, "Potong gagal", e.getMessage())));
    }

    // ── daftar baris ────────────────────────────────────────────────────────
    private final class RowsAdapter extends BaseAdapter {
        final List<Object> items = new ArrayList<>();

        void rebuild() {
            items.clear();
            if (last != null) {
                int f = filter == null ? 0 : filter.getSelectedItemPosition();
                if (f == 0 || f == 3) for (String e : last.extra) items.add(e);
                for (DocMatcher.RowView v : last.rows) {
                    if (f == 1 && v.status != DocMatcher.Status.MISSING) continue;
                    if (f == 2 && (v.status == DocMatcher.Status.MISSING || v.status == DocMatcher.Status.CONFLICT)) continue;
                    if (f == 3) continue;
                    if (f == 4 && v.status != DocMatcher.Status.CONFLICT) continue;
                    items.add(v);
                }
                if (f == 0 && snap != null) for (JSONObject u : snap.untagged) items.add(u);
            }
            notifyDataSetChanged();
        }

        String epcAt(int i) {
            Object o = items.get(i);
            if (o instanceof String) return (String) o;
            if (o instanceof DocMatcher.RowView) return ((DocMatcher.RowView) o).row.epc;
            return null;
        }

        @Override public int getCount() { return items.size(); }
        @Override public Object getItem(int i) { return items.get(i); }
        @Override public long getItemId(int i) { return i; }

        @Override
        public View getView(int i, View convert, ViewGroup parent) {
            TextView t = convert instanceof TextView ? (TextView) convert : new TextView(ScanActivity.this);
            int p = Ui.dp(ScanActivity.this, 8);
            t.setPadding(p, p, p, p);
            t.setTextSize(15);
            Object o = items.get(i);
            if (o instanceof String) {
                t.setText("+  LEBIH · " + Epc.display((String) o) + "\n   bukan roll dokumen ini (tahan untuk cari)");
                t.setTextColor(Ui.WARN);
            } else if (o instanceof DocMatcher.RowView) {
                DocMatcher.RowView v = (DocMatcher.RowView) o;
                Snapshot.Row r = v.row;
                String qty = r.qty == null ? "" : " · " + r.qty + " " + r.unit;
                t.setText(v.status.glyph + "  " + v.status.text.toUpperCase(java.util.Locale.ROOT) + " · " + (r.rollNo.isEmpty() ? Epc.tail(r.epc) : r.rollNo)
                        + (r.suggested ? " (saran)" : "") + "\n   " + (r.sku.isEmpty() ? r.productName : r.sku) + qty + (r.binCode.isEmpty() ? "" : " · " + r.binCode)
                        + (v.note.isEmpty() ? "" : "\n   ! " + v.note));
                t.setTextColor(v.status == DocMatcher.Status.CONFLICT ? Ui.BAD : v.status == DocMatcher.Status.MISSING ? Ui.INK : Ui.OK);
            } else {
                JSONObject u = (JSONObject) o;
                t.setText("▢  TANPA TAG · " + Json.str(u, "roll_no") + (u.optBoolean("resolved") ? " (pengecualian tercatat)" : "") + "\n   " + Json.str(u, "reason"));
                t.setTextColor(Ui.MUTED);
            }
            return t;
        }
    }
}
