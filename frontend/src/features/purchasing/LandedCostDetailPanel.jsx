import MoneyInput from "../../components/MoneyInput";
import { useState } from "react";
import axios, { API } from "../../services/apiClient";
import { X, CheckCircle2, Wallet, Send, XCircle, Ban, Layers, Warehouse, Factory, Truck, Info } from "lucide-react";
import { formatCurrency, formatQty } from "../../utils/formatters";
import KNSelect from "../../components/KNSelect";
import { isZeroMetric } from "../../components/ListPageParts";
import ErrorNotice from "../../components/ErrorNotice";
import { JournalStatusBar } from "../../components/JournalStatusBadge";   // PK-18 — status jurnal kapitalisasi
import { usePaymentMethods } from "../../config/paymentMethods";   // PM-T1 — daftar induk cara bayar
import CashAccountField, { cashAccountBlocked, cashAccountBlockReason } from "../../components/CashAccountField";   // PK-20

/**
 * LandedCostDetailPanel (Fase 5.4) — detail voucher: biaya, alokasi HPP roll, aksi.
 * PK-26 (IV-01, K-05) — kolom Perlakuan (golongan roll dari server `treatment`), ringkasan pembukuan dari
 * `capitalization` sesudah disetujui, dan kalimat peringatan sebelum disetujui bila ada roll yang sudah keluar.
 */

/** PK-26 — golongan roll saat voucher disetujui (`allocations[].treatment`; pratinjau: `allocation_preview[].treatment`). */
export const PERLAKUAN = {
  persediaan: { label: "Persediaan", Icon: Warehouse },
  wip: { label: "Di makloon", Icon: Factory },
  keluar: { label: "Sudah keluar", Icon: Truck },
};
export const KALIMAT_KELUAR =
  "Roll yang sudah terkirim ke pelanggan tidak menambah nilai persediaan; bagiannya langsung menjadi beban.";

/** PK-26 — baris ringkas pembukuan voucher yang sudah disetujui; baris bernilai 0 disembunyikan. */
export function capitalizationRows(cap) {
  if (!cap) return [];
  const beban = cap.expensed_to === "varians" ? "Dicatat sebagai biaya masuk pembelian" : "Dibebankan ke HPP";
  return [
    { key: "inventory", label: "Menambah nilai persediaan", value: Number(cap.inventory_amount || 0) },
    { key: "wip", label: "Menambah nilai barang di makloon", value: Number(cap.wip_amount || 0) },
    { key: "expensed", label: beban, value: Number(cap.expensed_amount || 0) },
  ].filter((r) => Math.abs(r.value) >= 0.005);
}

function Perlakuan({ treatment }) {
  const t = PERLAKUAN[treatment];
  if (!t) return <span className="text-kn-text-2">—</span>;
  const { Icon, label } = t;
  return (
    <span className="inline-flex items-center gap-1 min-w-0" data-treatment={treatment}>
      <Icon size={12} aria-hidden="true" className="shrink-0 text-kn-text-2" />
      <span className="truncate">{label}</span>
    </span>
  );
}
function StatusPill({ status }) {
  const map = {
    draft: ["pill-muted", "Draft"], pending_approval: ["pill-warning", "Menunggu Approval"],
    applied: ["pill-info", "Diterapkan ke HPP"], paid: ["pill-success", "Lunas"], cancelled: ["pill-danger", "Dibatalkan"],
  };
  const [cls, label] = map[status] || ["pill-muted", status];
  return <span className={`status-pill ${cls}`} data-testid="lc-detail-status">{label}</span>;
}

export default function LandedCostDetailPanel({ voucher, canApprove, decideHint = "", currentUser, onClose, onAction, onError }) {
  const [payAmount, setPayAmount] = useState("");
  const [cashType, setCashType] = useState("kas_besar");
  const [method, setMethod] = useState("transfer");
  const payMethods = usePaymentMethods("keluar", voucher?.entity_id);
  const [showPay, setShowPay] = useState(false);
  const [busy, setBusy] = useState(false);
  // PK-20 — rekening sumber pembayaran (rekening aktif PT voucher) wajib; tunggal → terisi otomatis.
  const [accountId, setAccountId] = useState("");
  const [accState, setAccState] = useState("memuat");
  // Fase 4 · R3 — galat aksi juga tampil DI DALAM pop-up (bilah halaman `onError` tertutup lapisan DetailModal).
  const [err, setErr] = useState("");
  const fail = (m) => { setErr(m); onError?.(m); };

  if (!voucher) return null;
  const fin = voucher.financials || { total_cost: voucher.total_cost, outstanding: 0, amount_paid: voucher.amount_paid };
  const allocs = (voucher.allocations && voucher.allocations.length) ? voucher.allocations : (voucher.allocation_preview || []);
  const isApplied = voucher.status === "applied" || voucher.status === "paid";
  const capRows = isApplied ? capitalizationRows(voucher.capitalization) : [];
  const adaKeluar = !isApplied && voucher.status !== "cancelled" && allocs.some((a) => a.treatment === "keluar");

  async function act(action, body) {
    setBusy(true); setErr("");
    try {
      const urls = {
        submit: `${API}/landed-costs/${voucher.id}/submit`,
        approve: `${API}/landed-costs/${voucher.id}/approve`,
        reject: `${API}/landed-costs/${voucher.id}/reject`,
        cancel: `${API}/landed-costs/${voucher.id}/cancel`,
        pay: `${API}/landed-costs/${voucher.id}/pay`,
      };
      const r = await axios.post(urls[action], body || {});
      onAction?.(action, r.data);
      if (r.data?.payment_gl_status === "failed") {   // PK-20 — pembayaran tercatat, jurnal kasnya menunggu diulang
        setErr(`Pembayaran tercatat, tetapi jurnal kasnya gagal: ${r.data.payment_gl_error || "galat"}. `
          + "Ulangi dari Keuangan › Posting Gagal.");
      }
    } catch (e) {
      fail(e.response?.data?.detail || `Gagal ${action}.`);
    } finally { setBusy(false); }
  }

  async function doPay() {
    const amt = Number(payAmount || 0);
    if (amt <= 0) { fail("Nominal pembayaran harus > 0."); return; }
    await act("pay", { amount: amt, cash_type: cashType, method, ...(accountId ? { account_id: accountId } : {}) });
    setShowPay(false); setPayAmount("");
  }

  return (
    // Fase 4 · R3 (L-03) — panel ini SUDAH dibungkus DetailModal oleh LandedCostView, tetapi dulu merakit lagi
    // `modal-overlay` + `.modal-card` sendiri (dua latar, dua penutup). Kini kartu saja: lapisan, Esc, klik latar &
    // layar penuh HP milik DetailModal. Testid `landed-cost-detail-panel` tetap (pada kartu).
    <div data-testid="landed-cost-detail-panel"
      className="mx-auto w-full max-w-[900px] rounded-2xl bg-white shadow-2xl max-h-[calc(100dvh-2rem)] overflow-y-auto">
      <div>
        <div className="flex items-start justify-between px-4 py-3 border-b border-[#EFF0F2] sticky top-0 bg-white z-10">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-[15px] font-bold" data-testid="lc-detail-number">{voucher.voucher_number}</h2>
              <StatusPill status={voucher.status} />
              <span className="status-pill pill-muted capitalize">basis {voucher.effective_basis || voucher.basis}</span>
            </div>
            <p className="text-[11.5px] text-[#6B6B73] mt-0.5">
              {voucher.provider_name || "—"} · PO {(voucher.po_numbers || []).join(", ") || "—"}
              {voucher.supplier_invoice_no ? ` · Inv: ${voucher.supplier_invoice_no}` : ""}
            </p>
          </div>
          <button type="button" data-testid="lc-detail-close" onClick={onClose} className="icon-button" aria-label="Tutup"><X size={16} /></button>
        </div>

        <div className="p-4 space-y-3">
          <ErrorNotice message={err} onDismiss={() => setErr("")} testId="lc-detail-error" />
          <JournalStatusBar doc={voucher} testId="lc-journal-status" />
          {/* Financial cards */}
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            <Card label="Total Biaya" value={formatCurrency(fin.total_cost)} testId="lc-fin-total" />
            <Card label="Sudah Dibayar" value={formatCurrency(fin.amount_paid)} testId="lc-fin-paid" tone="text-green-700" />
            {/* Fase 3 · P4 (L-08) — merah hanya bila ADA sisa; Rp 0 netral (dulu selalu merah, terbaca sebagai tunggakan). */}
            <Card label="Sisa" value={formatCurrency(fin.outstanding)} testId="lc-fin-outstanding" tone={Number(fin.outstanding) > 0.005 ? "text-red-600" : undefined} />
            <Card label="Roll Terbeban" value={String(voucher.target_roll_count || allocs.length || 0)} testId="lc-fin-rolls" />
          </div>

          {/* Cost lines */}
          <div className="rounded-md border border-[#EFF0F2] overflow-hidden">
            <div className="grid grid-cols-[150px_1fr_140px] px-2.5 py-1.5 bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73] border-b border-[#EFF0F2]">
              <span>Kategori</span><span>Deskripsi</span><span className="text-right">Nominal</span>
            </div>
            {(voucher.cost_lines || []).map((c, i) => (
              <div key={i} data-testid={`lc-cost-line-${i}`} className="grid grid-cols-[150px_1fr_140px] items-center px-2.5 py-1.5 border-b border-[#EFF0F2] last:border-0">
                <span className="text-[11.5px] font-semibold capitalize">{c.category}</span>
                <span className="text-[11px] text-[#6B6B73] truncate">{c.description || "—"}</span>
                <span className="text-[11.5px] tabular-nums text-right">{formatCurrency(c.amount)}</span>
              </div>
            ))}
            <div className="grid grid-cols-[150px_1fr_140px] px-2.5 py-1.5 bg-[#FAFBFC] border-t border-[#EFF0F2]">
              <span className="text-[10.5px] font-bold uppercase text-[#6B6B73] col-span-2 text-right pr-2">Total Biaya</span>
              <span className="text-[12px] font-bold tabular-nums text-right">{formatCurrency(voucher.total_cost)}</span>
            </div>
          </div>

          {/* Allocation table */}
          <div className="rounded-md border border-[#EFF0F2] overflow-hidden">
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-[#FAFBFC] border-b border-[#EFF0F2]">
              <Layers size={13} className="text-[#0058CC]" />
              <span className="text-[10.5px] font-bold uppercase text-[#6B6B73]">
                {isApplied ? "Alokasi ke HPP Roll (diterapkan)" : "Preview Alokasi ke HPP Roll"}
              </span>
            </div>
            {allocs.length === 0 ? (
              <div className="py-5 text-center text-[11.5px] text-[#9A9BA3]">Belum ada alokasi.</div>
            ) : (
              <div className="max-h-[260px] overflow-auto">
                {/* PK-26 — 7 kolom (+ Perlakuan) = 720 px ⊂ kartu 900 px; di HP bergulir di wadahnya. Huruf 12 px (KN_37). */}
                <div className="min-w-[720px]">
                  <div className="grid grid-cols-[90px_1.4fr_120px_80px_100px_100px_110px] gap-x-1 px-2.5 py-1 bg-white text-fs-12 font-bold uppercase text-kn-text-2 border-b border-kn-divider sticky top-0">
                    <span>Roll</span><span>Produk</span><span>Perlakuan</span><span className="text-right">Panjang</span><span className="text-right">Biaya</span><span className="text-right">+ /unit</span><span className="text-right">HPP Baru</span>
                  </div>
                  {allocs.map((a, i) => (
                    <div key={a.roll_id || i} data-testid={`lc-detail-alloc-${i}`} className="grid grid-cols-[90px_1.4fr_120px_80px_100px_100px_110px] gap-x-1 items-center px-2.5 py-1 border-b border-kn-divider last:border-0 text-fs-12">
                      <span className="font-mono">{a.roll_no}</span>
                      <span className="truncate">{a.product_name || a.sku || "—"}</span>
                      <span data-testid={`lc-detail-alloc-${i}-treatment`}><Perlakuan treatment={a.treatment} /></span>
                      <span className="tabular-nums text-right">{formatQty(a.length)}</span>
                      <span className="tabular-nums text-right">{formatCurrency(a.alloc_amount)}</span>
                      <span className="tabular-nums text-right text-[#0058CC]">+{formatCurrency(a.per_unit)}</span>
                      <span className="tabular-nums text-right font-semibold">{formatCurrency(a.new_unit_cost)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {capRows.length > 0 && (
              <dl className="border-t border-kn-divider px-3 py-2 space-y-1 text-fs-12" data-testid="lc-capitalization">
                {capRows.map((r) => (
                  <div key={r.key} className="flex items-center justify-between gap-3" data-testid={`lc-cap-${r.key}`}>
                    <dt className="text-kn-text-2">{r.label}</dt>
                    <dd className="tabular-nums font-semibold text-kn-text">{formatCurrency(r.value)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>

          {/* Timeline */}
          {(voucher.timeline || []).length > 0 && (
            <div className="rounded-md border border-[#EFF0F2] overflow-hidden">
              <div className="px-3 py-1.5 bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73]">Riwayat</div>
              <ol className="p-2.5 space-y-1.5" data-testid="lc-timeline">
                {voucher.timeline.map((t, i) => (
                  <li key={i} className="flex gap-2 text-[11px]">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#0058CC] mt-1.5 shrink-0" />
                    <div><span className="font-semibold">{t.label}</span> <span className="text-[#9A9BA3]">· {t.actor}</span>{t.note ? <span className="text-[#6B6B73]"> — {t.note}</span> : null}</div>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* Pay panel */}
          {showPay && voucher.status === "applied" && (
            <div className="rounded-md border border-[#EFF0F2] p-3 space-y-2.5" data-testid="lc-pay-panel">
              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
                <Field label="Nominal Bayar">
                  <MoneyInput testId="lc-pay-amount" className="field" value={payAmount} onChange={(v) => setPayAmount(v)} />
                </Field>
                <Field label="Sumber Kas">
                  <KNSelect data-testid="lc-pay-cashtype" value={cashType} onValueChange={setCashType} className="field"
                    options={[{ value: "kas_besar", label: "Bank (transfer)" }, { value: "kas_kecil", label: "Kas Kecil (tunai)" }]} />
                </Field>
                <Field label="Cara bayar">
                  <KNSelect data-testid="lc-pay-method" value={method} onValueChange={setMethod} className="field"
                    options={payMethods.options} />
                </Field>
              </div>
              <CashAccountField entityId={voucher.entity_id} cashType={cashType} value={accountId} onChange={setAccountId}
                onState={setAccState} testId="lc-pay-account" className="sm:max-w-md" />
              <div className="flex flex-wrap items-center gap-2">
                <button data-testid="lc-pay-confirm" onClick={doPay} disabled={busy || cashAccountBlocked(accState, accountId)}
                  className="primary-button btn-sm whitespace-nowrap">Catat Pembayaran</button>
                <button onClick={() => setShowPay(false)} className="secondary-button btn-sm">Batal</button>
                {cashAccountBlocked(accState, accountId) && accState !== "kosong" && (
                  <span className="text-fs-12 text-kn-text-2" data-testid="lc-pay-account-reason">
                    {cashAccountBlockReason(accState)}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Actions footer — PK-26: kalimat roll keluar di bilahnya sendiri, di atas tombol Setujui */}
        <div className="px-4 py-3 border-t border-kn-divider sticky bottom-0 bg-white space-y-2">
          {adaKeluar && (
            <p className="flex items-start gap-1.5 text-fs-12 text-kn-text-2" data-testid="lc-keluar-note">
              <Info size={14} aria-hidden="true" className="shrink-0 mt-px" /><span>{KALIMAT_KELUAR}</span>
            </p>
          )}
          <div className="flex items-center justify-end gap-2 flex-wrap">
            {voucher.status === "draft" && (
              <>
                <button data-testid="lc-action-cancel" onClick={() => act("cancel", { notes: "" })} disabled={busy} className="secondary-button"><Ban size={13} /> Batalkan</button>
                <button data-testid="lc-action-submit" onClick={() => act("submit")} disabled={busy} className="primary-button"><Send size={13} /> Kirim</button>
              </>
            )}
            {voucher.status === "pending_approval" && canApprove && (
              <>
                <button data-testid="lc-action-reject" onClick={() => act("reject", { notes: "Ditolak dari detail" })} disabled={busy} className="danger-button"><XCircle size={13} /> Tolak</button>
                <button data-testid="lc-action-approve" onClick={() => act("approve")} disabled={busy} className="primary-button"><CheckCircle2 size={13} /> Setujui & Alokasikan HPP</button>
              </>
            )}
            {voucher.status === "pending_approval" && !canApprove && (   /* KP-T4 — petunjuk dari Aturan Persetujuan */
              <span className="text-[11px] text-[#9A9BA3]" data-testid="lc-decide-hint">{decideHint || "Menunggu persetujuan."}</span>
            )}
            {voucher.status === "applied" && (
              <button data-testid="lc-action-pay" onClick={() => setShowPay((s) => !s)} disabled={busy} className="primary-button"><Wallet size={13} /> Bayar</button>
            )}
            {voucher.status === "paid" && <span className="text-[11.5px] font-semibold text-green-700 flex items-center gap-1"><CheckCircle2 size={14} /> Biaya lunas.</span>}
            {voucher.status === "cancelled" && <span className="text-[11.5px] text-[#9A9BA3]">Voucher dibatalkan.</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

function Card({ label, value, tone, testId }) {
  const zero = isZeroMetric(value);   // L-08 — "Rp 0" netral (mis. "Sudah Dibayar" Rp 0 dulu hijau)
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
