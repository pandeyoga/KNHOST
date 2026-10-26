import { AskKnButton } from "../../components/AskKnButton";
import MoneyInput from "../../components/MoneyInput";
import { useState } from "react";
import axios, { API } from "../../services/apiClient";
import { X, CheckCircle2, AlertTriangle, Wallet, Send, XCircle, Ban } from "lucide-react";
import { formatCurrency, formatQty } from "../../utils/formatters";
import KNSelect from "../../components/KNSelect";
import DocumentActionsBar from "../documents/DocumentActionsBar";
import DocRefsPanel from "../documents/trace/DocRefsPanel";
import GrnDocVariance from "./GrnDocVariance";
import VendorBillPayments from "./VendorBillPayments";
import { can } from "../../config/roles";
import ErrorNotice from "../../components/ErrorNotice";
import { isZeroMetric } from "../../components/ListPageParts";

/**
 * VendorBillDetailPanel (Fase 5.2) — detail bill: 3-way match, keuangan, aksi.
 */
function StatusPill({ status }) {
  const map = {
    draft: ["pill-muted", "Draft"], pending_approval: ["pill-warning", "Menunggu Approval"],
    posted: ["pill-info", "Terposting"], paid: ["pill-success", "Lunas"], cancelled: ["pill-danger", "Dibatalkan"],
  };
  const [cls, label] = map[status] || ["pill-muted", status];
  return <span className={`status-pill ${cls}`} data-testid="vb-detail-status">{label}</span>;
}
function MatchPill({ status }) {
  const map = {
    matched: ["pill-success", "Match Bersih"], warning: ["pill-warning", "Ada Selisih"], blocked: ["pill-danger", "Over-billing"],
  };
  const [cls, label] = map[status] || ["pill-muted", status];
  return <span className={`status-pill ${cls}`} data-testid="vb-detail-match">{label}</span>;
}

export default function VendorBillDetailPanel({ bill, canApprove, currentUser, onClose, onAction, onError }) {
  const [payAmount, setPayAmount] = useState("");
  const [cashType, setCashType] = useState("kas_besar");
  const [method, setMethod] = useState("transfer");
  const [showPay, setShowPay] = useState(false);
  const [busy, setBusy] = useState(false);
  // Fase 4 · R3 — galat aksi juga tampil DI DALAM pop-up (bilah halaman `onError` tertutup lapisan DetailModal).
  const [err, setErr] = useState("");
  const fail = (m) => { setErr(m); onError?.(m); };

  if (!bill) return null;
  const fin = bill.financials || { grand_total: bill.grand_total, outstanding: bill.outstanding, amount_paid: bill.amount_paid, payment_status: bill.payment_status };

  async function act(action, body) {
    setBusy(true); setErr("");
    try {
      const urls = {
        submit: `${API}/vendor-bills/${bill.id}/submit`,
        approve: `${API}/vendor-bills/${bill.id}/approve`,
        reject: `${API}/vendor-bills/${bill.id}/reject`,
        cancel: `${API}/vendor-bills/${bill.id}/cancel`,
        pay: `${API}/vendor-bills/${bill.id}/pay`,
      };
      const r = await axios.post(urls[action], body || {});
      onAction?.(action, r.data);
    } catch (e) {
      fail(e.response?.data?.detail || `Gagal ${action}.`);
    } finally { setBusy(false); }
  }

  async function doPay() {
    const amt = Number(payAmount || 0);
    if (amt <= 0) { fail("Nominal pembayaran harus > 0."); return; }
    await act("pay", { amount: amt, cash_type: cashType, method });
    setShowPay(false); setPayAmount("");
  }

  const exceptions = bill.match_exceptions || [];

  return (
    // Fase 4 · R3 (L-03) — panel ini SUDAH dibungkus DetailModal oleh VendorBillsView, tetapi dulu merakit lagi
    // `modal-overlay` + `.modal-card` sendiri (dua latar, dua penutup). Kini kartu saja: lapisan, Esc, klik latar &
    // layar penuh HP milik DetailModal. Testid `vendor-bill-detail-panel` tetap (pada kartu).
    <div data-testid="vendor-bill-detail-panel"
      className="mx-auto w-full max-w-[880px] rounded-2xl bg-white shadow-2xl max-h-[calc(100dvh-2rem)] overflow-y-auto">
      <div>
        {/* Header */}
        <div className="flex items-start justify-between px-4 py-3 border-b border-[#EFF0F2] sticky top-0 bg-white z-10">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-[15px] font-bold" data-testid="vb-detail-number">{bill.bill_number}</h2>
              <StatusPill status={bill.status} />
              <MatchPill status={bill.match_status} />
              <AskKnButton type="vendor_bill" id={bill.id} label={bill.bill_number} />
            </div>
            <p className="text-[11.5px] text-[#6B6B73] mt-0.5">
              {bill.supplier_name} · PO {bill.po_number} · {bill.match_mode === "received" ? "basis diterima" : "basis dipesan"}
              {bill.supplier_invoice_no ? ` · Inv: ${bill.supplier_invoice_no}` : ""}
            </p>
          </div>
          <button type="button" data-testid="vb-detail-close" onClick={onClose} className="icon-button" aria-label="Tutup"><X size={16} /></button>
        </div>

        <div className="p-4 space-y-3">
          <ErrorNotice message={err} onDismiss={() => setErr("")} testId="vb-detail-error" />
          <DocumentActionsBar docType="vendor_bill" sourceId={bill.id} entityId={bill.entity_id}
            number={bill.bill_number} label="Vendor Bill" esignable currentUser={currentUser}
            className="rounded-lg border border-[#EDEEF1] bg-[#FAFBFC] px-2.5 py-2" />
          {/* FASE G-4 — 3-way match bisa ditelusuri: tagihan → PO → Penerimaan Barang */}
          <DocRefsPanel docType="vendor_bill" docId={bill.id} />
          {/* Financial cards */}
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            <Card label="Total Tagihan" value={formatCurrency(fin.grand_total)} testId="vb-fin-grand" />
            <Card label="Sudah Dibayar" value={formatCurrency(fin.amount_paid)} testId="vb-fin-paid" tone="text-green-700" />
            <Card label="Sisa Hutang" value={formatCurrency(fin.outstanding)} testId="vb-fin-outstanding" tone="text-red-600" />
            <Card label="PPN Masukan" value={formatCurrency(bill.ppn_amount)} testId="vb-fin-ppn" />
          </div>

          {/* Match exceptions */}
          {exceptions.length > 0 && (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2" data-testid="vb-match-exceptions">
              <div className="flex items-center gap-1.5 mb-1">
                <AlertTriangle size={13} className="text-amber-600" />
                <span className="text-[11.5px] font-bold text-amber-800">Selisih 3-Way Matching ({exceptions.length})</span>
              </div>
              <ul className="space-y-0.5">
                {exceptions.map((ex, i) => (
                  <li key={i} data-testid={`vb-exception-${i}`} className="text-[10.5px] text-amber-800">• <b>{ex.sku || ex.product_name}</b>: {ex.detail}</li>
                ))}
              </ul>
            </div>
          )}
          {exceptions.length === 0 && bill.match_status === "matched" && (
            <div className="flex items-center gap-1.5 text-[11.5px] text-green-700" data-testid="vb-match-clean">
              <CheckCircle2 size={14} /> 3-way match bersih: qty & harga sesuai PO/penerimaan.
            </div>
          )}

          <GrnDocVariance poId={bill.po_id || ""} mkoId={bill.po_id ? "" : bill.makloon_order_id || ""} stepSeq={bill.step_seq ?? null} testId="vb-grn-variance" />
          {/* Items table */}
          {/* Fase 4 · R3 — tabel baris bergulir di dalam kotaknya sendiri di HP (tidak melebarkan pop-up). */}
          <div className="rounded-md border border-[#EFF0F2] overflow-x-auto">
            <div className="min-w-[640px]">
              <div className="grid grid-cols-[1.6fr_78px_78px_82px_84px_110px_110px] px-2.5 py-1.5 bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73] border-b border-[#EFF0F2]">
                <span>Produk</span><span className="text-right">Pesan</span><span className="text-right">Terima</span>
                <span className="text-right">Tagih</span><span className="text-right">Harga PO</span><span className="text-right">Harga Bill</span><span className="text-right">Subtotal</span>
              </div>
              {(bill.items || []).map((it, i) => (
                <div key={i} data-testid={`vb-detail-item-${i}`} className="grid grid-cols-[1.6fr_78px_78px_82px_84px_110px_110px] items-center px-2.5 py-1.5 border-b border-[#EFF0F2] last:border-0">
                  <div className="min-w-0"><p className="text-[11.5px] font-semibold truncate">{it.product_name}</p><p className="text-[10px] text-[#9A9BA3]">{it.sku}</p></div>
                  <span className="text-[11px] tabular-nums text-right">{formatQty(it.ordered_qty)}</span>
                  <span className="text-[11px] tabular-nums text-right">{formatQty(it.received_qty)}</span>
                  <span className="text-[11px] tabular-nums text-right font-semibold">{formatQty(it.billed_qty)}</span>
                  <span className="text-[11px] tabular-nums text-right text-[#6B6B73]">{formatCurrency(it.po_price)}</span>
                  <span className={`text-[11px] tabular-nums text-right ${it.match?.price_status === "price_variance" ? "text-amber-600 font-semibold" : ""}`}>{formatCurrency(it.price)}</span>
                  <span className="text-[11px] tabular-nums text-right">{formatCurrency(it.line_total ?? it.subtotal)}</span>
                </div>
              ))}
              <div className="grid grid-cols-[1.6fr_78px_78px_82px_84px_110px_110px] px-2.5 py-1.5 bg-[#FAFBFC] border-t border-[#EFF0F2]">
                <span className="text-[10.5px] font-bold uppercase text-[#6B6B73] col-span-6 text-right pr-2">Subtotal · PPN {bill.ppn_rate || 0}% · Grand Total</span>
                <span className="text-[11.5px] font-bold tabular-nums text-right">{formatCurrency(bill.grand_total)}</span>
              </div>
            </div>
          </div>

          <VendorBillPayments bill={bill} canVoid={can(currentUser?.permissions, "vendor_bill", "pay")} onAction={onAction} onError={onError} />

          {/* Timeline */}
          {(bill.timeline || []).length > 0 && (
            <div className="rounded-md border border-[#EFF0F2] overflow-hidden">
              <div className="px-3 py-1.5 bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73]">Riwayat</div>
              <ol className="p-2.5 space-y-1.5" data-testid="vb-timeline">
                {bill.timeline.map((t, i) => (
                  <li key={i} className="flex gap-2 text-[11px]">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#0058CC] mt-1.5 shrink-0" />
                    <div><span className="font-semibold">{t.label}</span> <span className="text-[#9A9BA3]">· {t.actor}</span>{t.note ? <span className="text-[#6B6B73]"> — {t.note}</span> : null}</div>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* Pay panel */}
          {showPay && bill.status === "posted" && (
            <div className="rounded-md border border-[#EFF0F2] p-3 space-y-2.5" data-testid="vb-pay-panel">
              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
                <Field label="Nominal Bayar">
                  <MoneyInput testId="vb-pay-amount" className="field" value={payAmount} onChange={(v) => setPayAmount(v)} />
                </Field>
                <Field label="Sumber Kas">
                  <KNSelect data-testid="vb-pay-cashtype" value={cashType} onValueChange={setCashType} className="field"
                    options={[{ value: "kas_besar", label: "Kas Besar" }, { value: "kas_kecil", label: "Kas Kecil" }]} />
                </Field>
                <Field label="Metode">
                  <KNSelect value={method} onValueChange={setMethod} className="field"
                    options={[{ value: "transfer", label: "Transfer" }, { value: "tunai", label: "Tunai" }, { value: "giro", label: "Giro" }]} />
                </Field>
              </div>
              <div className="flex gap-2">
                <button data-testid="vb-pay-confirm" onClick={doPay} disabled={busy} className="primary-button">Catat Pembayaran</button>
                <button onClick={() => setShowPay(false)} className="secondary-button">Batal</button>
              </div>
            </div>
          )}
        </div>

        {/* Actions footer */}
        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-[#EFF0F2] sticky bottom-0 bg-white">
          {bill.status === "draft" && (
            <>
              <button data-testid="vb-action-cancel" onClick={() => act("cancel", { notes: "" })} disabled={busy} className="secondary-button"><Ban size={13} /> Batalkan</button>
              <button data-testid="vb-action-submit" onClick={() => act("submit")} disabled={busy} className="primary-button"><Send size={13} /> Kirim</button>
            </>
          )}
          {bill.status === "pending_approval" && canApprove && (
            <>
              <button data-testid="vb-action-reject" onClick={() => act("reject", { notes: "Ditolak dari detail" })} disabled={busy} className="danger-button"><XCircle size={13} /> Tolak</button>
              <button data-testid="vb-action-approve" onClick={() => act("approve")} disabled={busy} className="primary-button"><CheckCircle2 size={13} /> Setujui & Posting</button>
            </>
          )}
          {bill.status === "pending_approval" && !canApprove && (
            <span className="text-[11px] text-[#9A9BA3]">Menunggu persetujuan {bill.required_approval_role || "manager"}.</span>
          )}
          {bill.status === "posted" && (
            <>
              {bill.bill_type !== "makloon_service" && (
                <button data-testid="vb-action-cancel-posted" onClick={() => act("cancel", { notes: "" })} disabled={busy} className="secondary-button"><Ban size={13} /> Batalkan</button>
              )}
              <button data-testid="vb-action-pay" onClick={() => { setShowPay((s) => !s); if (!payAmount && Number(fin.outstanding) > 0) setPayAmount(String(fin.outstanding)); }} disabled={busy} className="primary-button"><Wallet size={13} /> Bayar</button>
            </>
          )}
          {bill.status === "paid" && <span className="text-[11.5px] font-semibold text-green-700 flex items-center gap-1"><CheckCircle2 size={14} /> Tagihan lunas.</span>}
          {bill.status === "cancelled" && <span className="text-[11.5px] text-[#9A9BA3]">Bill dibatalkan.</span>}
        </div>
      </div>
    </div>
  );
}

function Card({ label, value, tone, testId }) {
  const zero = isZeroMetric(value);   // L-08 — "Rp 0" netral (dulu "Sudah Dibayar" Rp 0 hijau, "Sisa Hutang" Rp 0 merah)
  return (
    <div className="rounded-md border border-[#EFF0F2] px-3 py-2" data-testid={testId}>
      <p className="text-[9.5px] font-bold uppercase text-[#6B6B73]">{label}</p>
      <p className={`text-[14px] font-bold tabular-nums ${zero ? "text-[#8E8E93]" : (tone || "text-[#0F1115]")}`}>{value}</p>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-[10.5px] font-semibold text-[#6B6B73] mb-1">{label}</label>
      {children}
    </div>
  );
}
