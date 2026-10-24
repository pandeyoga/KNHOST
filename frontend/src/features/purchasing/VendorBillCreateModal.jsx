import { useEffect, useMemo, useState } from "react";
import KNDatePicker from "@/components/KNDatePicker";
import MoneyInput from "@/components/MoneyInput";
import axios, { API } from "../../services/apiClient";
import { Scale, AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import FormModal from "@/components/FormModal";
import { formatCurrency, formatQty } from "../../utils/formatters";
import KNSelect from "../../components/KNSelect";
import GrnDocVariance from "./GrnDocVariance";
import POReceiptVariancePanel from "../admin/po/POReceiptVariancePanel";

/**
 * VendorBillCreateModal (Fase 5.2) — buat Tagihan Supplier dari PO + 3-way match LIVE.
 * Preview match dihitung client-side (panduan); kebenaran final = server.
 *
 * Audit UI 24 Okt (031): modal dulu TANPA kaki tombol sebelum PO dipilih (hanya ✕).
 * Sekarang memakai FormModal — kaki Batal / Simpan Draf / Kirim selalu terlihat
 * (nonaktif sampai PO & minimal satu baris tagih terisi) dan galat tampil di dalam modal.
 */
const MATCH_MODES = [
  { value: "received", label: "Barang Diterima (3-way ketat)" },
  { value: "ordered", label: "Jumlah Dipesan (longgar)" },
];

function MatchBadge({ status }) {
  const map = {
    ok: ["pill-success", "Cocok"],
    warning: ["pill-warning", "Selisih"],
    blocked: ["pill-danger", "Lebih tagih"],
  };
  const [cls, label] = map[status] || ["pill-muted", status];
  return <span className={`status-pill ${cls}`} data-testid="vb-row-match">{label}</span>;
}

export default function VendorBillCreateModal({ open, pos, selectedEntity, onClose, onCreated, onError }) {
  const [poId, setPoId] = useState("");
  const [ctx, setCtx] = useState(null);
  const [loadingCtx, setLoadingCtx] = useState(false);
  const [matchMode, setMatchMode] = useState("received");
  const [invNo, setInvNo] = useState("");
  const [billDate, setBillDate] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [notes, setNotes] = useState("");
  const [items, setItems] = useState([]);
  const [priceTol, setPriceTol] = useState(5);
  const [qtyTol, setQtyTol] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const fail = (m) => { setErr(m); onError?.(m); };

  useEffect(() => {
    if (!open) { reset(); return; }
    (async () => {
      try {
        const params = (selectedEntity && selectedEntity !== "all") ? { entity_id: selectedEntity } : {};
        const r = await axios.get(`${API}/settings/effective`, { params });
        const pur = r.data?.purchasing || {};
        setPriceTol(Number(pur.bill_price_tolerance_percent ?? 5));
        setQtyTol(Number(pur.bill_qty_tolerance_percent ?? 0));
      } catch { /* pakai default */ }
    })();
  }, [open, selectedEntity]);

  function reset() {
    setPoId(""); setCtx(null); setItems([]); setInvNo("");
    setBillDate(""); setDueDate(""); setNotes(""); setMatchMode("received"); setErr("");
  }

  async function onSelectPO(id) {
    setPoId(id);
    setErr("");
    if (!id) { setCtx(null); setItems([]); return; }
    setLoadingCtx(true);
    try {
      const r = await axios.get(`${API}/purchase-orders/${id}/billing-context`);
      setCtx(r.data);
      setItems((r.data.items || []).map((it) => ({
        ...it,
        billed_qty: it.billable_received > 0 ? String(it.billable_received) : "",
        price: String(it.po_price || ""),
        include: it.billable_received > 0,
      })));
    } catch (e) {
      fail(e.response?.data?.detail || "Gagal memuat konteks penagihan PO.");
    } finally { setLoadingCtx(false); }
  }

  function updateItem(i, patch) {
    setItems((arr) => arr.map((it, idx) => (idx === i ? { ...it, ...patch } : it)));
  }

  const rows = useMemo(() => items.map((it) => {
    const billed = Number(it.billed_qty || 0);
    const price = Number(it.price || 0);
    const remaining = matchMode === "received" ? it.billable_received : it.billable_ordered;
    const overQty = billed > remaining + Math.abs(remaining) * (qtyTol / 100) + 1e-6;
    const pvar = it.po_price > 0 ? ((price - it.po_price) / it.po_price) * 100 : 0;
    const priceVar = Math.abs(pvar) > priceTol + 1e-6;
    const subtotal = billed * price;
    let status = "ok";
    if (overQty) status = "blocked";
    else if (priceVar || billed > remaining + 1e-6) status = "warning";
    return { ...it, billed, price, remaining, overQty, pvar, priceVar, subtotal, status };
  }), [items, matchMode, priceTol, qtyTol]);

  const active = rows.filter((r) => r.include && r.billed > 0);
  const grossTotal = active.reduce((s, r) => s + r.subtotal, 0);
  const hasBlocked = active.some((r) => r.status === "blocked");
  const hasWarning = active.some((r) => r.status === "warning");
  const overall = hasBlocked ? "blocked" : hasWarning ? "warning" : "matched";

  async function submit(now) {
    if (!poId) { fail("Pilih PO terlebih dahulu."); return; }
    const payloadItems = active.map((r) => ({
      product_id: r.product_id, po_line_id: r.po_line_id || undefined,
      billed_qty: r.billed, price: r.price, discount_percent: 0,
    }));
    if (payloadItems.length === 0) { fail("Minimal 1 item dengan qty tagih > 0."); return; }
    if (now && hasBlocked) { fail("Ada item yang ditagih melebihi toleransi. Perbaiki qty dulu."); return; }
    setBusy(true);
    try {
      const body = {
        po_id: poId, supplier_invoice_no: invNo, match_mode: matchMode,
        bill_date: billDate || undefined, due_date: dueDate || undefined,
        notes, items: payloadItems, submit_now: now,
        entity_id: ctx?.entity_id || (selectedEntity !== "all" ? selectedEntity : undefined),
      };
      const r = await axios.post(`${API}/vendor-bills`, body);
      onCreated?.(r.data, now);
      reset();
    } catch (e) {
      fail(e.response?.data?.detail || "Gagal membuat tagihan supplier.");
    } finally { setBusy(false); }
  }

  if (!open) return null;
  const overallMap = {
    matched: ["pill-success", "Cocok bersih", CheckCircle2],
    warning: ["pill-warning", "Ada selisih (perlu persetujuan)", AlertTriangle],
    blocked: ["pill-danger", "Lebih tagih (tidak bisa dikirim)", AlertTriangle],
  };
  const [oCls, oLabel, OIcon] = overallMap[overall];

  const canSave = !!poId && !loadingCtx && active.length > 0;
  const submitLabel = hasBlocked ? "Perbaiki Kelebihan Tagih Dulu"
    : overall === "warning" ? "Kirim (minta persetujuan)" : "Kirim & Posting";
  const footer = (
    <div className="flex flex-wrap items-center justify-end gap-2">
      {!poId && <span className="mr-auto text-[11px] text-[#6B6B73]">Pilih PO dulu untuk memuat baris tagihan.</span>}
      <button type="button" data-testid="vb-create-close" onClick={onClose} disabled={busy}
        className="secondary-button">Batal</button>
      <button type="button" data-testid="vb-save-draft" onClick={() => submit(false)} disabled={busy || !canSave}
        className="secondary-button">Simpan Draf</button>
      <button type="button" data-testid="vb-submit-now" onClick={() => submit(true)} disabled={busy || !canSave || hasBlocked}
        className="primary-button">
        {busy && <Loader2 size={13} className="animate-spin" />} {submitLabel}
      </button>
    </div>
  );

  return (
    <FormModal open={open} onClose={onClose} size="lg" icon={Scale} busy={busy}
      testId="vendor-bill-create-modal"
      title="Buat Tagihan Supplier"
      subtitle="Tagihan dicocokkan dengan PO dan penerimaan barang (3-way matching) sebelum menjadi hutang."
      error={err} footer={footer}>
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Field label="Pesanan Pembelian" req>
              <KNSelect data-testid="vb-po-select" value={poId} onValueChange={onSelectPO} className="field"
                placeholder="Pilih PO yang akan ditagih"
                options={pos.map((p) => ({ value: p.id, label: `${p.po_number} · ${p.supplier_name}` }))} />
            </Field>
            <Field label="No. Faktur Supplier">
              <input data-testid="vb-invoice-input" value={invNo} onChange={(e) => setInvNo(e.target.value)}
                className="field" placeholder="mis. INV/2026/0456" />
            </Field>
            <Field label="Basis Pencocokan">
              <KNSelect data-testid="vb-match-mode-select" value={matchMode} onValueChange={setMatchMode}
                className="field" options={MATCH_MODES} />
            </Field>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Field label="Tanggal Tagihan">
              <KNDatePicker data-testid="vb-bill-date" value={billDate} onChange={setBillDate} />
            </Field>
            <Field label="Jatuh Tempo">
              <KNDatePicker data-testid="vb-due-date" value={dueDate} onChange={setDueDate} />
            </Field>
            <Field label="Catatan">
              <input value={notes} onChange={(e) => setNotes(e.target.value)} className="field" placeholder="opsional" />
            </Field>
          </div>

          {loadingCtx && <div className="py-6 text-center text-[12px] text-[#6B6B73]">Memuat item PO...</div>}

          {ctx && !loadingCtx && (
            <>
              {/* FASE SL — catatan selisih penerimaan dari gudang: finance membacanya SEBELUM menagih */}
              <POReceiptVariancePanel variances={ctx.receipt_variances} testId="vb-receipt-variances" />
              <GrnDocVariance poId={poId} testId="vb-create-grn-variance" />
              {/* HP: grid baris lebar → gulir samping di dalam kotak, bukan memecah halaman. */}
              <div className="rounded-md border border-[#EFF0F2] overflow-x-auto">
               <div className="min-w-[760px]">
                <div className="grid grid-cols-[26px_1.6fr_82px_82px_92px_104px_120px_84px] whitespace-nowrap px-2.5 py-1.5 bg-[#FAFBFC] text-[11px] font-bold uppercase text-[#6B6B73] border-b border-[#EFF0F2]">
                  <span></span><span>Baris PO · Produk</span><span className="text-right">Dipesan</span>
                  <span className="text-right">Diterima</span><span className="text-right">Sisa Tagih</span>
                  <span className="text-right">Qty Tagih</span><span className="text-right">Harga</span><span>Cocok?</span>
                </div>
                {rows.map((r, i) => (
                  <div key={r.po_line_id || `line-${r.line_no}`} data-testid={`vb-item-row-${i}`}
                       className={`grid grid-cols-[26px_1.6fr_82px_82px_92px_104px_120px_84px] gap-1 items-center px-2.5 py-1.5 border-b border-[#EFF0F2] last:border-0 ${!r.include ? "opacity-50" : ""}`}>
                    <input type="checkbox" data-testid={`vb-item-include-${i}`} checked={r.include}
                      onChange={(e) => updateItem(i, { include: e.target.checked })} />
                    <div className="min-w-0">
                      <p className="text-[11.5px] font-semibold truncate">
                        <span data-testid={`vb-item-line-${i}`} className="mr-1 rounded bg-[#EEF4FF] px-1 text-[10px] font-bold text-[#0058CC]">
                          Baris #{r.line_no}</span>
                        {r.product_name}</p>
                      <p className="text-[10px] text-[#9A9BA3] truncate">{r.sku}{r.line_code ? ` · lini ${r.line_code}` : ""} · harga PO {formatCurrency(r.po_price)} · sudah ditagih {formatQty(r.already_billed_qty)}</p>
                      {r.same_product_lines > 1 && (
                        <p data-testid={`vb-item-dup-${i}`} className="text-[10px] font-semibold text-amber-600">
                          Produk ini ada di {r.same_product_lines} baris PO — tagihan dicocokkan ke baris #{r.line_no}</p>)}
                    </div>
                    <span className="text-[11px] tabular-nums text-right">{formatQty(r.ordered_qty)}</span>
                    <span className="text-[11px] tabular-nums text-right">{formatQty(r.received_qty)}</span>
                    <span data-testid={`vb-item-remaining-${i}`} className="text-[11px] tabular-nums text-right font-semibold">{formatQty(r.remaining)}</span>
                    <input data-testid={`vb-item-billed-${i}`} type="number" value={r.billed_qty}
                      onChange={(e) => updateItem(i, { billed_qty: e.target.value })}
                      className="field !py-1 text-right" placeholder="0" disabled={!r.include} />
                    <MoneyInput testId={`vb-item-price-${i}`} value={r.price}
                      onChange={(v) => updateItem(i, { price: v })}
                      className="field !py-1 text-right" placeholder="harga" disabled={!r.include} />
                    <div className="flex flex-col gap-0.5">
                      <MatchBadge status={r.include && r.billed > 0 ? r.status : "ok"} />
                      {r.include && r.priceVar && <span className="text-[9px] text-amber-600 tabular-nums">{r.pvar > 0 ? "+" : ""}{r.pvar.toFixed(1)}%</span>}
                    </div>
                  </div>
                ))}
               </div>
              </div>

              {/* Match summary + totals */}
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-[#EFF0F2] px-3 py-2.5 bg-[#FAFBFC]">
                <div className="flex flex-wrap items-center gap-2" data-testid="vb-overall-match">
                  <OIcon size={15} className={overall === "matched" ? "text-green-600" : overall === "warning" ? "text-amber-500" : "text-red-500"} />
                  <span className={`status-pill ${oCls}`}>{oLabel}</span>
                  <span className="text-[11px] text-[#6B6B73]">toleransi qty {qtyTol}% · harga ±{priceTol}%</span>
                </div>
                <div className="text-right">
                  <p className="text-[11px] uppercase font-bold text-[#6B6B73]">Subtotal (sebelum PPN)</p>
                  <p className="text-[16px] font-bold tabular-nums" data-testid="vb-gross-total">{formatCurrency(grossTotal)}</p>
                </div>
              </div>
            </>
          )}
        </div>
    </FormModal>
  );
}

function Field({ label, req, children }) {
  return (
    <div>
      <label className="field-label">{label} {req && <span className="req">*</span>}</label>
      {children}
    </div>
  );
}
