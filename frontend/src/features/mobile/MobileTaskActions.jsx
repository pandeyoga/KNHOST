import { useState, useRef, useEffect } from "react";
import { Loader2, Printer } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { printSampleLabel, printInboundRollLabels, reprintRollLabel } from "../../utils/rollLabels";
import useReceivingMode from "../../hooks/useReceivingMode";
import useReceivingUom from "../../hooks/useReceivingUom";
import useDomainEnums from "../../hooks/useDomainEnums";
import { offlinePost } from "../../utils/offlineQueue";
import { parseDecimal } from "../../utils/decimalInput";
import KNSelect from "../../components/KNSelect";
import BinSelect from "../../components/BinSelect";
import ReceiveUomPanel from "../wms/inbound/ReceiveUomPanel";
import GRCatchWeightModal from "../wms/inbound/GRCatchWeightModal";
import PickListPanel from "../wms/PickListPanel";

export { printSampleLabel, printInboundRollLabels, reprintRollLabel };

const errText = (e, fb) => { const d = e.response?.data?.detail; return (d && (d.message || (typeof d === "string" ? d : JSON.stringify(d)))) || fb; };

/** Tombol cetak ulang label QR untuk roll yang sudah terikat ke tugas (label rusak/hilang). */
export function ReprintRollButton({ task }) {
  const [busy, setBusy] = useState(false);
  if (!task?.roll_id) return null;
  const go = async (e) => {
    e.stopPropagation(); setBusy(true);
    try { const { data } = await axios.get(`${API}/rfid/lookup`, { params: { code: task.roll_id } }); if (data?.roll) await reprintRollLabel(data.roll, data.product_name || task.product_name); }
    catch (_) { /* roll belum ada / tidak ditemukan */ } finally { setBusy(false); }
  };
  return <button className="secondary-button btn-touch w-full" disabled={busy} onClick={go} data-testid={`mw-reprint-${task.id}`}><Printer size={18} /> Cetak ulang label QR roll</button>;
}

/** Aksi tugas gudang di mobile (Tahap 2): satu tombol besar per langkah, hasil = ikon + teks. */

// FIX-3a (B3b FRM-02, keputusan pemilik "form HP LENGKAP sama dengan desktop"; B2a FLW-IN-04) — Terima di HP kini
// memakai isian yang SAMA dengan desktop: satuan & qty surat jalan supplier (pratinjau konversi server), batch, lot,
// dye lot, grade (master), Roll ID, bin (terikat struktur gudang). Selesai memakai form rincian roll desktop
// (GRCatchWeightModal: panjang/berat/dye lot/grade PER ROLL + lot supplier + no. SJ) — dulu HP hanya qty →
// satu roll data untuk banyak roll fisik. Tombol Terima/Selesai hanya tampil di status yang memang diizinkan server.
const RECEIVABLE = ["waiting_goods", "pending", "receiving", "in_progress", "qc_check"];
const EMPTY_RECEIVE = { doc_uom: "", doc_qty: "", batch: "", lot: "", dye_lot: "", grade: "A", roll_id: "", bin_id: "" };

export function InboundActions({ task, onDone, onCompleted }) {
  const { isGrn } = useReceivingMode();
  const uom = useReceivingUom(task.id);
  const { options: enumOptions } = useDomainEnums();
  // GRN Fase 0.5 — kotak qty KOSONG: petugas wajib menghitung, bukan menekan Terima dengan qty PO penuh.
  const [f, setF] = useState(EMPTY_RECEIVE);
  const [more, setMore] = useState(false);
  const [msg, setMsg] = useState(null); const [busy, setBusy] = useState(false);
  const [gr, setGr] = useState(null);   // {rolls, product, lotSettings} saat form Selesai terbuka
  const [lotFields, setLotFields] = useState({ supplier_lot: "", lot_number: "", shade_ref: "", supplier_dn: "" });
  // KN-E49 — satu niat "Terima" = satu Idempotency-Key; isian dikosongkan setelah terkirim/antre (tak bisa dobel).
  const intent = useRef(null);
  const set = (k, v) => { setF((p) => ({ ...p, [k]: v })); intent.current = null; };
  useEffect(() => {
    const def = uom.options?.default_uom || uom.options?.task_uom;
    if (def) setF((p) => (p.doc_uom ? p : { ...p, doc_uom: def }));
  }, [uom.options]);
  useEffect(() => { uom.runPreview(f.doc_uom, parseDecimal(f.doc_qty)); }, [f.doc_uom, f.doc_qty]);
  const run = async (fn, ok) => { setBusy(true); setMsg(null); try { const r = await fn(); setMsg(r?.queued ? { ok: true, text: "Offline — tersimpan di HP, akan dikirim saat sinyal kembali (tanpa dobel)." } : { ok: true, text: ok }); if (!r?.queued) onDone?.(); } catch (e) { setMsg({ ok: false, text: errText(e, "Gagal.") }); } finally { setBusy(false); } };
  const qtyOk = parseDecimal(f.doc_qty) > 0;
  const receive = () => {
    intent.current = intent.current || `rcv-${task.id}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    return run(async () => {
      const body = { product_id: task.product_id, doc_uom: f.doc_uom || uom.options?.task_uom || "", doc_qty: f.doc_qty,
        batch: f.batch, lot: f.lot, dye_lot: f.dye_lot, grade: f.grade, roll_id: f.roll_id, bin_id: f.bin_id };
      const r = await offlinePost(`${API}/inbound/tasks/${task.id}/scan-receive`, body, { label: `Terima ${task.product_name || task.sku || "tugas"} ${f.doc_qty} ${body.doc_uom}`, idempotencyKey: intent.current });
      setF((p) => ({ ...EMPTY_RECEIVE, doc_uom: p.doc_uom })); intent.current = null;
      uom.reload?.();
      return r;
    }, "Diterima. Lanjut Selesai bila semua sudah dihitung.");
  };
  const openComplete = async () => {
    setMsg(null);
    const recv = Number(task.received_qty) || 0;
    const plan = Number(task.expected_rolls) || 0;
    let product = {};
    let lotSettings = null;
    try { product = (await axios.get(`${API}/products/${task.product_id}`)).data || {}; } catch (_) { /* opsional */ }
    try { lotSettings = (await axios.get(`${API}/lots/settings`)).data; } catch (_) { lotSettings = { enforcement_mode: "warn" }; }
    const n = plan > 1 ? plan : 1;
    const per = Math.round((recv / n) * 100) / 100;
    const isKg = (task.unit || "").toLowerCase() === "kg";
    const rolls = Array.from({ length: n }, (_, i) => {
      const len = i === n - 1 ? Math.round((recv - per * (n - 1)) * 100) / 100 : per;
      return { length: isKg ? 0 : len, weight: isKg ? len : 0, dye_lot: task.dye_lot || "", grade: "A" };
    });
    setGr({ rolls, product, lotSettings });
  };
  const complete = async () => {
    setBusy(true); setMsg(null);
    try {
      const rolls = (gr?.rolls || []).map((r) => ({ length: Number(r.length) || 0, weight: Number(r.weight) || 0,
        dye_lot: r.dye_lot || "", grade: r.grade || "A" }));
      const r = await offlinePost(`${API}/inbound/tasks/${task.id}/complete`, { rolls, ...lotFields }, { label: `Selesai barang masuk ${task.product_name || task.sku || "tugas"}` });
      if (r.queued) { setGr(null); setMsg({ ok: true, text: "Offline — penyelesaian tersimpan di HP; label roll bisa dicetak setelah sinkron." }); return; }
      setGr(null);
      // Hasil + tombol cetak label diangkat ke induk (bertahan setelah kartu hilang dari daftar).
      onCompleted?.({ task, rolls: r.data.created_rolls || [], warnings: r.data.placement_warnings || [] });
    } catch (e) { setMsg({ ok: false, text: errText(e, "Gagal.") }); } finally { setBusy(false); }
  };
  if (isGrn(task.entity_id) && !task.legacy_in_flight) {
    return (
      <a data-testid={`mw-inbound-grn-${task.id}`} href="?view=goods-receipts" className="mt-2 block min-h-touch rounded-lg border border-kn-divider bg-kn-success-soft p-3 text-fs-14 font-semibold text-kn-success-text">
        Penerimaan memakai Kedatangan Barang — buka layar Kedatangan untuk foto surat jalan & hitung fisik.
      </a>
    );
  }
  if (!RECEIVABLE.includes(task.status)) {
    return (
      <div className="mt-2 space-y-2" data-testid={`mw-inbound-actions-${task.id}`}>
        <div className="notice-bar text-fs-14" data-testid={`mw-inbound-locked-${task.id}`}>
          {task.status === "escalated" ? "Menunggu keputusan manajer atas eskalasi — belum bisa menerima barang."
            : "Barang tugas ini sudah masuk stok/karantina (keputusan QC di layar QC) — tidak ada aksi terima di sini."}
        </div>
        <ReprintRollButton task={task} />
      </div>
    );
  }
  const canComplete = task.status === "qc_check" || ((Number(task.received_qty) || 0) >= (Number(task.expected_qty) || 0) && (Number(task.received_qty) || 0) > 0);
  return (
    <div className="mt-2 space-y-2" data-testid={`mw-inbound-actions-${task.id}`}>
      {task.status !== "qc_check" && (
        <div className="space-y-2">
          <ReceiveUomPanel uom={uom} docUom={f.doc_uom} docQty={f.doc_qty}
            onUomChange={(v) => set("doc_uom", v)} onQtyChange={(v) => set("doc_qty", v)} disabled={busy} />
          <button type="button" className="ghost-button btn-touch w-full justify-start text-kn-action" onClick={() => setMore((x) => !x)} data-testid={`mw-receive-more-${task.id}`}>
            {more ? "Sembunyikan" : "Batch, lot, dye lot, grade, Roll ID, bin"}
          </button>
          {more && (
            <div className="grid grid-cols-2 gap-2">
              <input className="kn-input-touch" placeholder="Batch" value={f.batch} onChange={(e) => set("batch", e.target.value)} data-testid={`mw-batch-${task.id}`} />
              <input className="kn-input-touch" placeholder="Lot" value={f.lot} onChange={(e) => set("lot", e.target.value)} data-testid={`mw-lot-in-${task.id}`} />
              <input className="kn-input-touch" placeholder="Dye lot" value={f.dye_lot} onChange={(e) => set("dye_lot", e.target.value)} data-testid={`mw-dye-in-${task.id}`} />
              <KNSelect className="kn-input-touch text-left" value={f.grade} onValueChange={(v) => set("grade", v)} options={enumOptions("grade")} data-testid={`mw-grade-${task.id}`} />
              <input className="kn-input-touch" placeholder="Roll ID" value={f.roll_id} onChange={(e) => set("roll_id", e.target.value)} data-testid={`mw-rollid-${task.id}`} />
              <BinSelect className="kn-input-touch text-left" warehouseId={task.warehouse_id} value={f.bin_id} onChange={(v) => set("bin_id", v)} data-testid={`mw-bin-${task.id}`} />
            </div>
          )}
          <button className="primary-button btn-touch btn-primary-cta w-full" disabled={busy || !qtyOk} onClick={receive} data-testid={`mw-receive-btn-${task.id}`}>Terima</button>
        </div>
      )}
      {canComplete && (
        <button className="secondary-button btn-touch w-full" disabled={busy} onClick={openComplete} data-testid={`mw-complete-btn-${task.id}`}>{busy ? <Loader2 size={14} className="animate-spin inline" /> : null} Selesai (rincian roll → masuk stok)</button>
      )}
      {gr && (
        <GRCatchWeightModal task={task} product={gr.product} rolls={gr.rolls} setRolls={(rs) => setGr((g) => ({ ...g, rolls: rs }))}
          onSubmit={complete} onClose={() => setGr(null)} submitting={busy} error={msg && !msg.ok ? msg.text : ""}
          lotFields={lotFields} setLotFields={setLotFields} lotSettings={gr.lotSettings}
          tolPct={uom.options?.line_qty_tolerance_pct ?? 2} sjMode={uom.options?.supplier_dn_mode || "warn"}
          sjKnown={uom.options?.supplier_dn_known || []} />
      )}
      <ReprintRollButton task={task} />
      {msg && <div className={`notice-bar ${msg.ok ? "success" : "danger"}`} data-testid={`mw-action-msg-${task.id}`}>{msg.text}</div>}
    </div>
  );
}

// FIX-3b (K-B1-05 / K-B3b-01, B3b FRM-03) — AMBIL WAJIB PINDAI ROLL di HP (sama dengan desktop): kode roll (QR /
// nomor roll / EPC) → server menurunkan panjang dari roll (roll UTUH). Ketik qty tanpa pindai = JALUR DARURAT
// supervisor (izin wms.approve) dengan alasan ≥ 5 huruf — tercatat di riwayat tugas. Tugas yang dieskalasi tidak
// menampilkan aksi (menunggu keputusan supervisor).
const PICKABLE = ["pending", "created", "picking", "in_progress", "released", "partially_shipped"];
const SHIPPABLE = ["picking", "picked", "packing", "packed", "ready", "staging", "partially_shipped"];

export function OutboundActions({ task, onDone }) {
  const [code, setCode] = useState("");
  const [emergency, setEmergency] = useState(false);
  const [qty, setQty] = useState("");   // KN-E51 — jalur darurat: jumlah wajib dihitung, tidak terisi otomatis
  const [reason, setReason] = useState("");
  const [msg, setMsg] = useState(null); const [busy, setBusy] = useState(false);
  const run = async (fn, ok) => { setBusy(true); setMsg(null); try { const r = await fn(); setMsg(r?.queued ? { ok: true, text: "Offline — tersimpan di HP, akan dikirim saat sinyal kembali (tanpa dobel)." } : { ok: true, text: ok }); if (!r?.queued) { setCode(""); setQty(""); setReason(""); onDone?.(); } } catch (e) { setMsg({ ok: false, text: errText(e, "Gagal.") }); } finally { setBusy(false); } };
  const pick = () => run(() => offlinePost(`${API}/outbound/tasks/${task.id}/scan-pick`, null, {
    params: emergency ? { actual_qty: parseDecimal(qty) || 0, reason } : { roll_id: code.trim() },
    label: emergency ? `Ambil darurat ${task.product_name || task.sku || "tugas"} ${qty}` : `Ambil roll ${code.trim()}` }),
  "Roll diambil. Lanjut pindai roll berikutnya atau Berangkatkan.");
  const dispatch = () => run(() => offlinePost(`${API}/outbound/tasks/${task.id}/dispatch`, null, { label: `Berangkatkan ${task.order_number || "tugas"}` }), "Diberangkatkan — surat jalan dibuat.");
  const picked = Number(task.picked_qty || 0); const shipped = Number(task.shipped_qty || 0); const total = Number(task.quantity || 0);
  if (task.status === "escalated") {
    return (
      <div className="mt-2 space-y-2" data-testid={`mw-outbound-actions-${task.id}`}>
        <div className="notice-bar text-fs-14" data-testid={`mw-outbound-escalated-${task.id}`}>Menunggu keputusan supervisor atas eskalasi — belum bisa diambil/dikirim.</div>
      </div>
    );
  }
  const reasonOk = reason.replace(/[^A-Za-zÀ-ÿ]/g, "").length >= 5;
  return (
    <div className="mt-2 space-y-2" data-testid={`mw-outbound-actions-${task.id}`}>
      {PICKABLE.includes(task.status) && picked < total - 0.001 && (
        <div className="space-y-2">
          <PickListPanel task={task} onPick={(no) => { setEmergency(false); setCode(no); }} />
          {!emergency ? (
            <div className="flex gap-2">
              <input className="kn-input-touch min-h-touch-primary flex-1" value={code} placeholder="Pindai label/QR/RFID atau ketik no. roll"
                onChange={(e) => setCode(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && code.trim()) pick(); }}
                data-testid={`mw-pick-code-${task.id}`} />
              <button className="primary-button btn-touch btn-primary-cta" disabled={busy || !code.trim()} onClick={pick} data-testid={`mw-pick-btn-${task.id}`}>Ambil</button>
            </div>
          ) : (
            <div className="rounded-lg border border-kn-field-border bg-kn-warning-soft p-2 space-y-2" data-testid={`mw-pick-emergency-${task.id}`}>
              <div className="text-fs-14 text-kn-warning-text">Jalur darurat (izin supervisor): qty tanpa pindai roll — tercatat beserta alasan.</div>
              <input type="text" inputMode="decimal" className="kn-input-touch" value={qty} placeholder={`Hitung ambil (${task.unit || "qty"})`} onChange={(e) => setQty(e.target.value)} data-testid={`mw-pick-qty-${task.id}`} />
              <input className="kn-input-touch" value={reason} placeholder="Alasan (min. 5 huruf), mis. label rusak & scanner mati" onChange={(e) => setReason(e.target.value)} data-testid={`mw-pick-reason-${task.id}`} />
              <button className="primary-button btn-touch w-full" disabled={busy || !(parseDecimal(qty) > 0) || !reasonOk} onClick={pick} data-testid={`mw-pick-emergency-btn-${task.id}`}>Ambil (darurat)</button>
            </div>
          )}
          <button type="button" className="ghost-button btn-touch w-full justify-start text-kn-warning-text" onClick={() => setEmergency((x) => !x)} data-testid={`mw-pick-emergency-toggle-${task.id}`}>
            {emergency ? "Kembali ke pindai roll" : "Tidak bisa memindai? Jalur darurat supervisor"}
          </button>
        </div>
      )}
      {SHIPPABLE.includes(task.status) && picked - shipped > 0.001 && (
        <button className="secondary-button btn-touch w-full" disabled={busy} onClick={dispatch} data-testid={`mw-dispatch-btn-${task.id}`}>Berangkatkan</button>
      )}
      <ReprintRollButton task={task} />
      {msg && <div className={`notice-bar ${msg.ok ? "success" : "danger"}`} data-testid={`mw-action-msg-${task.id}`}>{msg.text}</div>}
    </div>
  );
}

export function SampleCutActions({ task, onCut, onDone }) {
  const [epc, setEpc] = useState(""); const [reason, setReason] = useState(""); const [length, setLength] = useState(String(task.quantity ?? ""));
  const [msg, setMsg] = useState(null); const [busy, setBusy] = useState(false);
  // Sudah dipotong (picked_qty > 0) → sisa langkahnya identik barang keluar (berangkatkan).
  if (Number(task.picked_qty || 0) > 0 || !["pending", "created", "picking"].includes(task.status)) {
    return (
      <div className="mt-2 space-y-2" data-testid={`mw-sample-actions-${task.id}`}>
        <div className="text-fs-14 text-kn-success-text font-semibold">Dipotong dari {task.parent_roll_no} → {task.child_roll_no} · {task.picked_qty} {task.unit}</div>
        <OutboundActions task={task} onDone={onDone} />
      </div>
    );
  }
  const cut = async (useSuggested) => {
    setBusy(true); setMsg(null);
    try {
      const body = useSuggested ? { roll_id: task.suggested_roll_id, actual_length: parseFloat(length) || undefined } : { epc, actual_length: parseFloat(length) || undefined, reason };
      const r = await offlinePost(`${API}/outbound/tasks/${task.id}/cut-sample`, body, { label: `Potong sample ${task.order_number || "tugas"}` });
      if (r.queued) { setMsg({ ok: true, text: "Offline — potongan tersimpan di HP; label bisa dicetak setelah sinkron." }); return; }
      // Hasil + tombol cetak diangkat ke induk (TaskList) supaya tetap tampil setelah kartu tugas hilang dari daftar.
      onCut?.(r.data.cut);
    } catch (e) { setMsg({ ok: false, text: errText(e, "Potong gagal.") }); } finally { setBusy(false); }
  };
  return (
    <div className="mt-2 space-y-2" data-testid={`mw-sample-actions-${task.id}`}>
      <div className="kn-hp-info">Untuk {task.customer_name} · diminta {task.quantity} {task.unit} · saran FIFO: <b>{task.suggested_roll_no || "tidak ada"}</b></div>
      <label className="block kn-hp-support">Panjang aktual dipotong ({task.unit})
        <input type="number" step="0.1" className="kn-input-touch" value={length} onChange={(e) => setLength(e.target.value)} data-testid={`mw-sample-length-${task.id}`} /></label>
      {task.suggested_roll_id && <button className="primary-button btn-touch btn-primary-cta w-full" disabled={busy} onClick={() => cut(true)} data-testid={`mw-sample-cut-suggested-${task.id}`}>Potong roll saran ({task.suggested_roll_no})</button>}
      <div className="rounded-lg border p-2 space-y-2">
        <div className="kn-hp-support">Roll lain (pindai EPC / QR atau ketik nomor roll) — wajib alasan bila bukan saran:</div>
        <input className="kn-input-touch" placeholder="EPC tag / nomor roll" value={epc} onChange={(e) => setEpc(e.target.value)} data-testid={`mw-sample-epc-${task.id}`} />
        <input className="kn-input-touch" placeholder="Alasan (mis. roll saran tidak ditemukan)" value={reason} onChange={(e) => setReason(e.target.value)} data-testid={`mw-sample-reason-${task.id}`} />
        <button className="secondary-button btn-touch w-full" disabled={busy || !epc} onClick={() => cut(false)} data-testid={`mw-sample-cut-other-${task.id}`}>Potong roll ini</button>
      </div>
      {msg && <div className={`notice-bar ${msg.ok ? "success" : "danger"}`} data-testid={`mw-action-msg-${task.id}`}>{msg.text}</div>}
    </div>
  );
}
