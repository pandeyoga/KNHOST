import { AskKnButton } from "../../components/AskKnButton";
import { useState, useEffect } from "react";
import { X, FileText, Send, CheckCircle2, XCircle, ReceiptText, RotateCcw, Trash2,
         Truck, PackageCheck, Undo2, Link2, Coins, Loader2, AlertTriangle, Clock } from "lucide-react";
import { formatCurrency, formatQty } from "../../utils/formatters";
import axios, { API } from "../../services/apiClient";
import DocumentActionsBar from "../documents/DocumentActionsBar";
import { Panel, Cell } from "../../components/DetailParts";
import ReturnChainPanel from "../sales/ReturnChainPanel";
import KNSelect from "../../components/KNSelect";
import ReturnRollsPanel from "../sales/ReturnRollsPanel";   // 23 Okt — detail & keputusan PER ROLL (sama dgn retur jual)

const STATUS_PILL = {
  draft: ["pill-muted", "Draf"],
  pending_approval: ["pill-warning", "Menunggu Persetujuan"],
  approved: ["pill-success", "Disetujui"],
  rejected: ["pill-danger", "Ditolak"],
  cancelled: ["pill-danger", "Dibatalkan (Reversal)"],
};

// R4 — supplier RMA lifecycle badge
const SUP_PILL = {
  requested_supplier: ["pill-warning", "Diajukan ke Supplier"],
  shipped_supplier: ["pill-warning", "Dikirim ke Supplier"],
  accepted_supplier: ["pill-success", "Diterima Supplier"],
  rejected_supplier: ["pill-danger", "Ditolak Supplier"],
  goods_back: ["pill-muted", "Barang Kembali (regrade)"],
};
const GRADES = ["A", "B", "C"];

const REASON_LABEL = { cacat: "Barang Cacat", salah_kirim: "Salah Kirim", kelebihan: "Kelebihan Kirim", lain: "Lain-lain" };

/** Baris retur supplier → bentuk baris panel roll (sama dengan retur pelanggan). */
const toPanelItems = (ret) => (ret.items || []).map((it) => ({
  ...it, quantity_returned: it.quantity, unit_price_est: it.price, line_total_est: it.subtotal,
  roll_nos: Object.fromEntries((it.rolls || []).map((r) => [r.roll_id, r.roll_no || r.roll_id])),
  roll_qtys: it.roll_qtys || Object.fromEntries((it.rolls || []).map((r) => [r.roll_id, r.length_remaining])),
  reason: REASON_LABEL[it.reason] || it.reason,
}));

function fmtDateTime(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("id-ID", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch { return String(iso); }
}

function buildTimeline(r) {
  const out = [];
  out.push({ icon: FileText, tone: "#0058CC", bg: "#EFF4FF", label: "Retur dibuat", actor: r.created_by || "Sistem", at: r.created_at, note: `${(r.items || []).length} item · ${formatCurrency(r.total_amount)}` });
  if (r.origin_sales_return_number) {
    out.push({ icon: Link2, tone: "#6B219A", bg: "#FBF5FF", label: `Berasal dari retur jual ${r.origin_sales_return_number}`, actor: "Sistem", at: r.created_at, note: "Barang cacat dari pelanggan diteruskan ke supplier" });
  }
  if (["pending_approval", "approved", "rejected"].includes(r.status)) {
    out.push({ icon: Send, tone: "#9A5B00", bg: "#FFF7EC", label: "Diajukan untuk persetujuan", actor: r.created_by || "Sistem", at: r.submitted_at || "", note: "" });
  }
  if (r.status === "approved") {
    out.push({ icon: CheckCircle2, tone: "#15803D", bg: "#E9F7EF", label: "Disetujui", actor: r.approved_by || "", at: r.approved_at, note: r.decision_notes || "" });
  }
  // R4 — supplier RMA milestones
  if (r.shipped_at) out.push({ icon: Truck, tone: "#0058CC", bg: "#EFF4FF", label: "Dikirim ke supplier", actor: r.shipped_by || "", at: r.shipped_at, note: [r.carrier, r.tracking_no].filter(Boolean).join(" · ") });
  if (r.supplier_status === "accepted_supplier" && r.accepted_at) out.push({ icon: PackageCheck, tone: "#15803D", bg: "#E9F7EF", label: `Supplier terima (${r.supplier_outcome === "refund" ? "refund" : "potong hutang"})`, actor: r.accepted_by || "", at: r.accepted_at, note: r.debit_note_number ? `Nota debit ${r.debit_note_number}` : "" });
  if (r.supplier_status === "rejected_supplier" || r.supplier_rejected_at) out.push({ icon: XCircle, tone: "#B91C1C", bg: "#FEF3F2", label: "Supplier tolak retur", actor: r.supplier_rejected_by || "", at: r.supplier_rejected_at, note: r.supplier_reject_reason || "" });
  if (r.goods_back_at) out.push({ icon: Undo2, tone: "#6B219A", bg: "#FBF5FF", label: "Barang kembali ke gudang", actor: r.goods_back_by || "", at: r.goods_back_at, note: r.goods_back_regraded ? `${r.goods_back_regraded} roll di-regrade` : "" });
  if (r.supplier_partial) out.push({ icon: XCircle, tone: "#9A5B00", bg: "#FFF7EC", label: `Supplier menolak ${(r.supplier_rejected_rolls || []).length} roll (terima sebagian)`, actor: r.accepted_by || "", at: r.accepted_at, note: (r.supplier_rejected_rolls || []).map((x) => `${x.roll_no}: ${x.reason}`).join("; ") });
  if (r.partial_goods_back_at) out.push({ icon: Undo2, tone: "#6B219A", bg: "#FBF5FF", label: "Roll tolakan supplier kembali ke gudang", actor: r.partial_goods_back_by || "", at: r.partial_goods_back_at, note: r.partial_goods_back_notes || "" });
  if (r.status === "approved" && r.debit_note_number && !r.supplier_flow) {
    out.push({ icon: ReceiptText, tone: "#15803D", bg: "#E9F7EF", label: `Nota debit diterbitkan (${r.debit_note_number})`, actor: "Sistem", at: r.approved_at, note: "Stok roll dikurangi & AP berkurang" });
  }
  if (r.status === "rejected") {
    out.push({ icon: XCircle, tone: "#B91C1C", bg: "#FEF3F2", label: "Ditolak", actor: r.rejected_by || "", at: r.rejected_at, note: r.reject_reason || r.decision_notes || "" });
  }
  return out;
}

export default function ReturnDetailPanel({ ret, supName, canApprove, canDelete, canDecideRolls, onClose, onChanged,
  onSubmit, onApprove, onReject, onDelete,
  onShip, onSupplierAccept, onSupplierReject, onGoodsBack, onPartialGoodsBack, onReverse }) {
  const [outcome, setOutcome] = useState("ap_credit");
  // 23 Okt — supplier menerima SEBAGIAN: roll yang ia tolak (+ alasan) tidak ikut Nota Debit.
  const [supRejected, setSupRejected] = useState({});   // roll_id -> alasan
  useEffect(() => { setSupRejected({}); }, [ret?.id]);
  const [rejectReason, setRejectReason] = useState("");
  const [regradeMap, setRegradeMap] = useState({});   // roll_id -> grade
  const [cashAccounts, setCashAccounts] = useState([]);
  const [refundAccount, setRefundAccount] = useState("");
  // R5.4b — reversal/koreksi retur beli terfinalisasi
  const [showReverse, setShowReverse] = useState(false);
  const [reverseReason, setReverseReason] = useState("");
  const [reversing, setReversing] = useState(false);
  const [reverseErr, setReverseErr] = useState(null);
  async function doReverse() {
    if (!reverseReason.trim()) return;
    setReversing(true); setReverseErr(null);
    try {
      const res = await axios.post(`${API}/purchase-returns/${ret.id}/reverse`, { notes: reverseReason.trim() });
      setShowReverse(false); setReverseReason("");
      onReverse && onReverse(res.data);
    } catch (e) {
      setReverseErr(e.response?.data?.detail || "Gagal reversal");
    } finally { setReversing(false); }
  }
  // R5.3 — akun Kas/Bank untuk outcome refund (supplier kembalikan dana tunai)
  // AUDIT PERAN (2026-08-15): hanya diambil bila pemakainya memang boleh memakainya.
  // Pemilih akun refund hanya dirender untuk `canApprove`; sebelumnya panggilan ini
  // jalan untuk SEMUA peran yang membuka detail retur beli — peran Gudang (yang
  // sengaja tanpa `sales_return.view`) selalu menabrak 403 yang lalu ditelan `catch`.
  useEffect(() => {
    if (!canApprove) { setCashAccounts([]); return undefined; }
    let active = true;
    (async () => {
      try {
        const res = await axios.get(`${API}/gl/cash-accounts`);
        if (active) setCashAccounts(Array.isArray(res.data) ? res.data : []);
      } catch { if (active) setCashAccounts([]); }
    })();
    return () => { active = false; };
  }, [canApprove]);
  if (!ret) return null;
  const [cls, label] = STATUS_PILL[ret.status] || ["pill-muted", ret.status];
  const timeline = buildTimeline(ret);
  const sup = ret.supplier_flow ? (SUP_PILL[ret.supplier_status] || ["pill-muted", ret.supplier_status || "—"]) : null;
  const ss = ret.supplier_status;
  const allRolls = (ret.items || []).flatMap((it) => (it.rolls || []).map((r) => ({ ...r, unit: it.unit })));
  const pendingBack = (ret.supplier_rejected_rolls || []).filter((r) => !r.goods_back_at);
  const supRejList = Object.entries(supRejected).map(([roll_id, reason]) => ({ roll_id, reason: (reason || "").trim() }));
  const supRejBad = supRejList.some((r) => r.reason.length < 5) || (allRolls.length > 0 && supRejList.length >= allRolls.length);
  // R5.4b — kelayakan reversal
  const isReversed = ret.reversed === true || ret.status === "cancelled";
  const isFinalized = ret.stock_adjusted && ret.supplier_status === "accepted_supplier";
  const canReverse = canApprove && isFinalized && !isReversed;

  return (
    <div className="modal-overlay" data-testid="return-detail-panel" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-card" style={{ maxWidth: 880, width: "94vw", maxHeight: "90vh", overflowY: "auto" }}>
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2 min-w-0">
            <RotateCcw size={16} className="text-[#0058CC]" />
            <div className="min-w-0">
              <p className="text-[14px] font-bold truncate" data-testid="return-detail-number">{ret.number}</p>
              <p className="text-[11px] text-[#6B6B73]">{ret.po_number ? `dari ${ret.po_number}` : "Tanpa PO"}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap justify-end">
            <AskKnButton type="purchase_return" id={ret.id} label={ret.number} />
            <span className={`status-pill ${cls}`}>{label}</span>
            {sup && <span className={`status-pill ${sup[0]}`} data-testid="supplier-status-pill">{sup[1]}</span>}
            {isReversed && ret.reversed && (
              <span className="info-chip danger" data-testid="pr-reversed-chip"
                title={ret.reversal_reason || ""}>
                <RotateCcw size={12} /> Dibatalkan{ret.reversed_by ? ` · ${ret.reversed_by}` : ""}
              </span>
            )}
            <button data-testid="return-detail-close" onClick={onClose} className="text-[#6B6B73] hover:text-[#1C1C1E]"><X size={16} /></button>
          </div>
        </div>

        {/* Meta */}
        <div className="mb-2 grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="return-detail-cells">
          <Cell label="Supplier">{ret.supplier_name || supName?.(ret.supplier_id) || "—"}</Cell>
          <Cell label="Nota debit"><span className="font-mono">{ret.debit_note_number || "—"}</span></Cell>
          <Cell label="Alasan">{REASON_LABEL[ret.reason] || ret.reason || "—"}</Cell>
          <Cell label="Total" tone="#0058CC">{formatCurrency(ret.total_amount)}</Cell>
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[11px] mb-2.5 empty:hidden">
          {ret.supplier_flow ? <Meta label="Alur" value={`RMA Supplier${ret.origin_type === "import" ? " · Impor" : ""}`} /> : null}
          {ret.origin_sales_return_number ? <Meta label="Asal Retur Jual" value={ret.origin_sales_return_number} /> : null}
          {ret.origin_interco_return_number ? (
            <Meta label="Asal Retur Antar-PT" value={ret.origin_interco_return_number} />
          ) : null}
          {ret.notes ? <div className="col-span-2"><Meta label="Catatan" value={ret.notes} /></div> : null}
        </div>

        <DocumentActionsBar docType="purchase_return" sourceId={ret.id} entityId={ret.entity_id}
          number={ret.number} label="Nota Retur Beli" esignable={false}
          className="mb-2.5 rounded-md border border-[#EFF0F2] bg-[#FAFBFC] px-2.5 py-2" />

        {/* Items — 23 Okt: detail & keputusan PER ROLL (panel yang sama dengan retur pelanggan) */}
        <div className="mb-2.5">
          <ReturnRollsPanel ret={ret} items={toPanelItems(ret)} fullView title="Item & roll retur" testId="return-detail-items"
            estimatedValue={ret.total_amount}
            // UAT 24 Okt (audit UI tahap 2) — G4-27: keputusan per roll hanya bila retur memang punya roll
            // (dulu "Simpan keputusan roll (0)" tampil di draf tanpa roll).
            canDecide={["draft", "pending_approval"].includes(ret.status) && !!canDecideRolls && allRolls.length > 0}
            decideUrl={`${API}/purchase-returns/${ret.id}/roll-decisions`}
            attachmentHref={(a) => `${API}/purchase-returns/${ret.id}/attachments/${a.id}/download`}
            hint="Roll yang ditolak keluar dari retur (tetap stok KN). Roll tanpa keputusan ikut disetujui."
            // G4-27 — SATU dasar nilai berlabel (dulu label ini + catatan "Basis nilai retur = WAC…" berdampingan).
            valueLabel={`Nilai retur sebelum PPN = HPP rata-rata (WAC) per roll termasuk biaya masuk${ret.origin_type === "import" ? " (barang impor)" : ""}, bukan harga PO — angka resmi di Nota Debit`}
            onChanged={onChanged} />
        </div>

        {/* FASE E-9 (E9.6 · US29) — jejak rantai retur. Dipasang di SINI juga supaya
            dokumen ketiga dalam rantai bukan jalan buntu: dari retur beli pun
            pengguna melihat rantai yang sama (retur pelanggan → antar-PT → supplier). */}
        <div className="mb-2.5">
          <ReturnChainPanel docId={ret.id} />
        </div>

        {/* Timeline */}
        <Panel icon={Clock} title="Riwayat status" className="mb-1">
          <ol data-testid="return-timeline">
            {timeline.map((t, i) => {
              const Icon = t.icon;
              const last = i === timeline.length - 1;
              return (
                <li key={i} data-testid={`return-timeline-entry-${i}`} className="flex gap-2.5">
                  <div className="flex flex-col items-center">
                    <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full" style={{ background: t.bg, color: t.tone }}><Icon size={13} /></span>
                    {!last && <span className="w-px flex-1 my-0.5" style={{ background: "#E5E7EB", minHeight: 14 }} />}
                  </div>
                  <div className={`min-w-0 flex-1 ${last ? "" : "pb-2.5"}`}>
                    <div className="flex items-baseline justify-between gap-2">
                      <p className="text-[11.5px] font-semibold text-[#1C1C1E] truncate">{t.label}</p>
                      <span className="text-[10px] tabular-nums text-[#8E8E93] whitespace-nowrap">{fmtDateTime(t.at)}</span>
                    </div>
                    <p className="text-[10.5px] text-[#6B6B73]">oleh <span className="font-medium text-[#3C3C43]">{t.actor || "Sistem"}</span></p>
                    {t.note ? <p className="mt-0.5 text-[10.5px] text-[#6B6B73] italic">{t.note}</p> : null}
                  </div>
                </li>
              );
            })}
          </ol>
        </Panel>

        {/* R4 — Supplier RMA lifecycle actions */}
        {ret.supplier_flow && canApprove && ret.status === "approved" && !["accepted_supplier", "goods_back"].includes(ss) && (
          <div className="rounded-md border border-[#E4ECF7] bg-[#F6FAFF] p-2.5 mt-2" data-testid="rma-actions">
            <p className="text-[10px] font-bold uppercase text-[#1B4F9C] mb-1.5">Alur RMA Supplier</p>

            {ss === "requested_supplier" && (
              <button data-testid="rma-ship-btn" className="primary-button w-full justify-center" onClick={() => onShip && onShip(ret)}>
                <Truck size={13} /> Kirim ke Supplier
              </button>
            )}

            {ss === "shipped_supplier" && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <label className="text-[11px] font-semibold text-[#3C3C43]">Hasil:</label>
                  <label className="inline-flex items-center gap-1 text-[11px]"><input type="radio" name="rma-outcome" data-testid="rma-outcome-ap_credit" checked={outcome === "ap_credit"} onChange={() => setOutcome("ap_credit")} /> Potong Hutang (AP)</label>
                  <label className="inline-flex items-center gap-1 text-[11px]"><input type="radio" name="rma-outcome" data-testid="rma-outcome-refund" checked={outcome === "refund"} onChange={() => setOutcome("refund")} /> Pengembalian Dana (kas)</label>
                </div>
                {outcome === "refund" && (
                  <div className="rounded-md border border-[#E7E1F5] bg-[#F8F5FE] p-2" data-testid="rma-refund-account-box">
                    <label className="flex items-center gap-1 text-[10.5px] font-semibold text-[#6B219A] mb-1"><Coins size={12} /> Akun Kas/Bank penerima pengembalian dana</label>
                    <KNSelect data-testid="rma-refund-account" className="field w-full !py-1 text-[12px]"
                      value={refundAccount} onValueChange={setRefundAccount}
                      aria-label="Akun kas/bank untuk pengembalian dana"
                      placeholder="Default — 1-1100 Kas Besar / Bank"
                      options={[
                        { value: "", label: "Default — 1-1100 Kas Besar / Bank" },
                        ...cashAccounts.map((a) => ({ value: a.code, label: `${a.code} — ${a.name}` })),
                      ]} />
                    <p className="text-[10px] text-[#5B6472] mt-1">Pengembalian Dana → <b>Dr Kas/Bank / Cr Persediaan</b> + tercatat kas masuk. AP tidak berubah.</p>
                  </div>
                )}
                {allRolls.length > 1 && (
                  <div className="rounded-md border border-[#EFF0F2] bg-white p-2" data-testid="rma-partial-box">
                    <p className="text-[10.5px] font-semibold text-[#3C3C43] mb-1">Supplier menerima sebagian? Centang roll yang DITOLAK supplier:</p>
                    {allRolls.map((r) => {
                      const on = r.roll_id in supRejected;
                      return (
                        <div key={r.roll_id} className="flex flex-wrap items-center gap-2 py-0.5 text-[11px]">
                          <label className="inline-flex items-center gap-1.5">
                            <input type="checkbox" checked={on} data-testid={`rma-partial-${r.roll_id}`}
                              onChange={() => setSupRejected((m) => { const n = { ...m }; if (on) delete n[r.roll_id]; else n[r.roll_id] = ""; return n; })} />
                            <span className="font-mono text-[#6B219A]">{r.roll_no || r.roll_id}</span>
                            <span className="text-[#8E8E93]">· {formatQty(r.length_remaining)}{r.unit ? ` ${r.unit}` : ""}</span>
                          </label>
                          {on && <input className="field flex-1 !py-0.5 text-[11px]" placeholder="Alasan supplier menolak roll ini (min. 5 huruf)"
                            data-testid={`rma-partial-reason-${r.roll_id}`} value={supRejected[r.roll_id]}
                            onChange={(e) => setSupRejected((m) => ({ ...m, [r.roll_id]: e.target.value }))} />}
                        </div>
                      );
                    })}
                    {supRejList.length > 0 && allRolls.length > 0 && supRejList.length >= allRolls.length && (
                      <p className="mt-1 text-[10.5px] text-[#A8221A]">Semua roll ditolak — pakai tombol "Supplier Tolak".</p>
                    )}
                  </div>
                )}
                <div className="flex gap-2">
                  <button data-testid="rma-accept-btn" className="primary-button flex-1 justify-center" disabled={supRejBad}
                    onClick={() => onSupplierAccept && onSupplierAccept(ret, outcome, refundAccount, supRejList)}>
                    <PackageCheck size={13} /> {supRejList.length ? `Supplier Terima Sebagian (${allRolls.length - supRejList.length} roll) → Nota Debit` : "Supplier Terima → Terbitkan Nota Debit"}
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <input data-testid="rma-reject-reason" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} placeholder="Alasan tolak supplier (opsional)" className="field flex-1 !py-1" />
                  <button data-testid="rma-reject-btn" className="danger-button" onClick={() => onSupplierReject && onSupplierReject(ret, rejectReason)}>
                    <XCircle size={13} /> Supplier Tolak
                  </button>
                </div>
              </div>
            )}

            {ss === "rejected_supplier" && (
              <div className="space-y-2" data-testid="goods-back-block">
                <p className="text-[11px] text-[#3C3C43]">Supplier menolak — kembalikan barang ke gudang & tentukan grade final (regrade):</p>
                {allRolls.map((r) => (
                  <div key={r.roll_id} className="flex items-center justify-between gap-2 text-[11px]">
                    <span className="font-mono text-[#6B219A]">{r.roll_no || r.roll_id} <span className="text-[#8E8E93]">· {formatQty(r.length_remaining)}{r.unit ? ` ${r.unit}` : ""}</span></span>
                    <KNSelect data-testid={`goods-back-grade-${r.roll_id}`}
                      className="field !py-1 min-w-[64px]"
                      value={regradeMap[r.roll_id] || "B"}
                      onValueChange={(v) => setRegradeMap((m) => ({ ...m, [r.roll_id]: v }))}
                      aria-label={`Grade roll ${r.roll_id}`}
                      options={GRADES.map((g) => ({ value: g, label: `Grade ${g}` }))} />
                  </div>
                ))}
                <button data-testid="rma-goods-back-btn" className="primary-button w-full justify-center"
                  onClick={() => onGoodsBack && onGoodsBack(ret, allRolls.map((r) => ({ roll_id: r.roll_id, grade: regradeMap[r.roll_id] || "B" })))}>
                  <Undo2 size={13} /> Barang Kembali ke Gudang (regrade)
                </button>
              </div>
            )}
          </div>
        )}

        {/* 23 Okt — roll yang ditolak supplier pada penerimaan sebagian: menunggu kembali ke gudang KN */}
        {canApprove && pendingBack.length > 0 && (
          <div className="rounded-md border border-[#E4D4F0] bg-[#FBF5FF] p-2.5 mt-2 space-y-2" data-testid="partial-goods-back-block">
            <p className="text-[11px] text-[#3C3C43]">{pendingBack.length} roll ditolak supplier — catat saat barangnya kembali & tentukan grade:</p>
            {pendingBack.map((r) => (
              <div key={r.roll_id} className="flex items-center justify-between gap-2 text-[11px]">
                <span className="min-w-0"><span className="font-mono text-[#6B219A]">{r.roll_no || r.roll_id}</span>
                  <span className="text-[#8E8E93]"> · {formatQty(r.qty)}{r.unit ? ` ${r.unit}` : ""} · {r.reason}</span></span>
                <KNSelect data-testid={`partial-back-grade-${r.roll_id}`} className="field !py-1 min-w-[64px]"
                  value={regradeMap[r.roll_id] || "B"} onValueChange={(v) => setRegradeMap((m) => ({ ...m, [r.roll_id]: v }))}
                  aria-label={`Grade roll ${r.roll_no || r.roll_id}`} options={GRADES.map((g) => ({ value: g, label: `Grade ${g}` }))} />
              </div>
            ))}
            <button data-testid="partial-goods-back-btn" className="primary-button w-full justify-center"
              onClick={() => onPartialGoodsBack && onPartialGoodsBack(ret, pendingBack.map((r) => ({ roll_id: r.roll_id, grade: regradeMap[r.roll_id] || "B" })))}>
              <Undo2 size={13} /> Roll Tolakan Supplier Kembali ke Gudang
            </button>
          </div>
        )}

        {/* R5.4b — Reversal/koreksi retur beli terfinalisasi (admin/manager) */}
        {(canReverse || (isReversed && ret.reversed)) && (
          <div className="rounded-md border border-[#F3C9C7] bg-[#FDF6F5] p-2.5 mt-2" data-testid="pr-reversal-box">
            {isReversed && ret.reversed ? (
              <p className="text-[11px] text-[#8A2A27] flex items-start gap-1.5">
                <RotateCcw size={13} className="mt-0.5 flex-shrink-0" />
                <span>Retur ini telah <b>dibatalkan (pembalikan)</b>{ret.reversed_by ? ` oleh ${ret.reversed_by}` : ""}.
                Jurnal dibalik, barang dikembalikan ke stok, Nota Debit di-void.
                {ret.reversal_reason ? <> Alasan: <i>{ret.reversal_reason}</i></> : null}</span>
              </p>
            ) : (
              <div className="flex items-center justify-between gap-2">
                <p className="text-[11px] text-[#6B4B49]">
                  Retur sudah difinalisasi (barang keluar + Nota Debit + jurnal GL).
                  Reversal akan mengembalikan barang ke stok & membalik jurnal.
                </p>
                <button data-testid="pr-reverse-btn" className="danger-button flex-shrink-0"
                  onClick={() => { setReverseErr(null); setShowReverse(true); }}>
                  <RotateCcw size={13} /> Batal / Pembalikan
                </button>
              </div>
            )}
          </div>
        )}

        {/* Standard approval actions */}
        {(ret.status === "draft" || (ret.status === "pending_approval" && canApprove)) && (
          <div className="modal-actions">
            {ret.status === "draft" && (
              <>
                {canDelete && onDelete && (
                  <button data-testid="return-detail-delete" onClick={() => onDelete(ret)} className="btn-danger"><Trash2 size={13} /> Hapus</button>
                )}
                <button data-testid="return-detail-submit" onClick={() => onSubmit(ret)} className="btn-primary"><Send size={13} /> Ajukan Persetujuan</button>
              </>
            )}
            {ret.status === "pending_approval" && canApprove && (
              <>
                <button data-testid="return-detail-reject" onClick={() => onReject(ret)} className="btn-danger"><XCircle size={13} /> Tolak</button>
                <button data-testid="return-detail-approve" onClick={() => onApprove(ret)} className="btn-primary">
                  <CheckCircle2 size={13} /> {ret.supplier_flow ? "Setujui (lanjut RMA)" : "Setujui & Terbitkan Nota"}
                </button>
              </>
            )}
          </div>
        )}

        {/* R5.4b — modal konfirmasi reversal retur beli */}
        {showReverse && (
          <div className="modal-overlay" data-testid="pr-reverse-modal" style={{ zIndex: 60 }}
            onClick={(e) => { if (e.target === e.currentTarget) setShowReverse(false); }}>
            <div className="modal-card small">
              <h3 className="modal-title flex items-center gap-1.5">
                <RotateCcw size={15} /> Batal / Pembalikan Retur Beli {ret.number}?
              </h3>
              <div className="notice-bar warning" style={{ margin: "8px 0" }}>
                <AlertTriangle size={13} />
                <span>Membalik jurnal ({ret.supplier_outcome === "refund" ? "refund kas di-void" : "potong hutang dipulihkan"}),
                mengembalikan barang ke stok, dan mem-void Nota Debit{ret.debit_note_number ? ` ${ret.debit_note_number}` : ""}.
                Dokumen tetap tersimpan (append-only).</span>
              </div>
              {reverseErr && (
                <div className="notice-bar danger" style={{ marginBottom: 8 }} data-testid="pr-reverse-err">
                  <X size={13} /> {reverseErr}
                </div>
              )}
              <label className="form-label">Alasan pembatalan / koreksi</label>
              <textarea data-testid="pr-reverse-reason" className="textarea" rows={3}
                placeholder="mis. salah input retur / barang tidak jadi diretur..."
                value={reverseReason} onChange={(e) => setReverseReason(e.target.value)} />
              <div className="modal-actions">
                <button className="secondary-button" data-testid="pr-reverse-cancel"
                  onClick={() => { setShowReverse(false); setReverseReason(""); }}>Batal</button>
                <button data-testid="pr-reverse-submit" className="danger-button"
                  disabled={!reverseReason.trim() || reversing} onClick={doReverse}>
                  {reversing ? <Loader2 size={13} className="spin" /> : <RotateCcw size={13} />} Lakukan Pembalikan
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Meta({ label, value, strong }) {
  return (
    <div className="min-w-0">
      <p className="text-[9.5px] font-bold uppercase text-[#9A9BA3]">{label}</p>
      <p className={`truncate ${strong ? "font-bold tabular-nums text-[#1C1C1E]" : "text-[#3C3C43]"}`}>{value || "—"}</p>
    </div>
  );
}
