/**
 * FASE G-7 · US7 — modal **BAYAR KONTRABON**: satu kas keluar melunasi banyak faktur.
 *
 * Potongan diterapkan sebagai pelunasan NON-KAS pada pembayaran pertama, sehingga
 * subledger hutang (`vendor_bills`) dan buku besar akhirnya rekonsiliasi — celah
 * nyata yang ada sebelum fase ini.
 *
 * Fase 4 · R2 (L-03) — `.modal-card` buatan sendiri → `FormModal` baku (layar penuh 1 kolom di HP). Isian & testid
 * tetap; galat tetap di DALAM pop-up.
 */
import MoneyInput from "../../../components/MoneyInput";
import KNDatePicker from "@/components/KNDatePicker";
import { useEffect, useMemo, useState } from "react";
import { Banknote, Info } from "lucide-react";
import { API } from "../../../services/apiClient";
import { moneyPost } from "../../../utils/moneyRequest";
import ErrorNotice from "../../../components/ErrorNotice";
import FormModal from "../../../components/FormModal";
import { KNSelect } from "../../../components/KNSelect";
import { formatCurrency } from "../../../utils/formatters";
import { apiErrorText } from "../../../utils/apiError";
import { METHOD_OPTIONS, todayISO } from "./contraBonApi";
import useIntentKey from "../../../hooks/useIntentKey";
import { ApPaymentPending, NEED_ACCOUNT_TEXT, NO_ACCOUNT_TEXT, accountLabel, useApPayment } from "../apPayment";

export default function PayModal({ cb, onClose, onPaid, onError }) {
  const t = cb.totals || {};
  const firstPayment = !(cb.payments || []).length;
  const [amount, setAmount] = useState(String(t.outstanding ?? ""));
  const [method, setMethod] = useState((cb.schedule || {}).method || "transfer");
  const [accountId, setAccountId] = useState((cb.schedule || {}).bank_account_id || "");
  const [paidAt, setPaidAt] = useState(todayISO());
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  // PK-05 — rekening dari PT kontrabon (wajib bila ada kas keluar), satu niat = satu Idempotency-Key.
  const intent = useIntentKey("cbpay");
  const ap = useApPayment("contra_bon", cb.id);
  const accounts = ap.accounts || [];
  useEffect(() => { if (ap.loadErr) setErr(ap.loadErr); }, [ap.loadErr]);

  const accountOptions = useMemo(() => accounts.map((a) => ({ value: a.id, label: accountLabel(a) })), [accounts]);

  async function pay() {
    const willPayCash = amount === "" ? Number(t.outstanding) > 0 : Number(amount) > 0;
    if (willPayCash && !accountId) { setErr(NEED_ACCOUNT_TEXT); return; }
    const body = { amount: amount === "" ? null : Number(amount), method, bank_account_id: accountId,
      paid_at: paidAt, notes: notes.trim() };
    setSaving(true); setErr("");
    try {
      const r = await intent.send(body, (key) => moneyPost(`${API}/contra-bons/${cb.id}/pay`, body, key));
      onPaid(r.data);
    } catch (e) {
      setErr(apiErrorText(e));
      onError?.(e);
      ap.reload();
    } finally { setSaving(false); }
  }

  return (
    <FormModal open onClose={onClose} title="Bayar kontrabon" icon={Banknote} size="lg"
      subtitle={`${cb.number} · ${cb.supplier_name} — ${(cb.bills || []).length} faktur dilunasi oleh SATU transaksi kas.`}
      testId="cb-pay-modal" busy={saving}
      footer={(
        <div className="flex items-center justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose} disabled={saving}>Batal</button>
          <button type="button" className="primary-button" data-testid="cb-pay-submit"
            disabled={saving} onClick={pay}>
            {saving ? "Memproses…" : "Catat pembayaran"}
          </button>
        </div>
      )}>
      {err && <ErrorNotice message={err} onDismiss={() => setErr("")} testId="cb-pay-error" />}
      <ApPaymentPending pending={ap.pending} testId="cb-pay-pending"
        onDone={(d) => { ap.reload(); if (d) onPaid(d); }} onError={setErr} />
      {ap.accounts && ap.accounts.length === 0 && (
        <p className="mb-2 text-[11.5px] text-[#A8221A]" data-testid="cb-pay-no-account">{NO_ACCOUNT_TEXT}</p>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <div className="stat-card">
          <p className="stat-label">Nilai faktur</p>
          <p className="stat-value tabular-nums">{formatCurrency(t.bills_total)}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Potongan</p>
          <p className="stat-value text-[#B26A00] tabular-nums">{formatCurrency(t.deductions_total)}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Nilai bersih</p>
          <p className="stat-value text-[#0058CC] tabular-nums">{formatCurrency(t.net_payable)}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Sisa dibayar</p>
          <p className="stat-value text-[#C0392B]" data-testid="cb-pay-outstanding">
            {formatCurrency(t.outstanding)}
          </p>
        </div>
      </div>

      {firstPayment && Number(t.deductions_total) > 0 && (
        <p className="mt-2 flex items-start gap-1 rounded-md bg-[#F2F7FF] px-2 py-1.5 text-[11px] text-[#1C1C1E]"
          data-testid="cb-pay-deduction-note">
          <Info size={11} className="mt-[2px] shrink-0" />
          Pada pembayaran pertama, potongan {formatCurrency(t.deductions_total)} ikut diterapkan
          sebagai pelunasan non-kas pada faktur-faktur di kontrabon ini — uang yang keluar dari
          kas hanya nilai bersihnya.
        </p>
      )}

      <div className="mt-3 space-y-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">
              Nominal dibayar (Rp)
            </label>
            <MoneyInput testId="cb-pay-amount" className="input-field w-full" value={amount} onChange={(v) => setAmount(v)} />
            <p className="mt-1 text-[10px] text-[#8E8E93]">
              Kosongkan untuk melunasi seluruh sisa bersih. Pembayaran sebagian diizinkan.
            </p>
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">
              Tanggal pembayaran
            </label>
            <KNDatePicker data-testid="cb-pay-date" value={paidAt} onChange={setPaidAt} clearable={false} />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Cara bayar</label>
            <KNSelect data-testid="cb-pay-method" value={method} onValueChange={setMethod}
              options={METHOD_OPTIONS} className="field" />
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">
              Rekening / kas
            </label>
            <KNSelect data-testid="cb-pay-account" value={accountId} onValueChange={setAccountId}
              options={accountOptions} className="field" placeholder="Pilih rekening" />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Catatan</label>
          <textarea data-testid="cb-pay-notes" className="textarea w-full" rows={2}
            value={notes} onChange={(e) => setNotes(e.target.value)}
            placeholder="Mis. transfer BCA jam 14:10, bukti dikirim ke WhatsApp supplier." />
        </div>

        <p className="text-[10.5px] text-[#9A9BA3]">
          Transaksi kas yang lahir memuat nomor kontrabon di keterangannya, sehingga langsung
          menjadi kandidat pada Rekonsiliasi Bank.
        </p>
      </div>
    </FormModal>
  );
}
