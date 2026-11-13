/**
 * PK-05 — perlengkapan bersama form BAYAR HUTANG (faktur pemasok & kontrabon).
 *
 *  - `useApPayment(kind, targetId)` memuat rekening/kas aktif MILIK PT DOKUMEN (`/ap-payments/accounts`) dan niat bayar
 *    yang belum selesai (`/ap-payments/pending`).
 *  - `<ApPaymentPending>` menampilkan niat yang menggantung dengan tombol Lanjutkan / Batalkan (alasan diketik di
 *    tempat — dialog bawaan peramban dilarang penjaga INV-UI-06).
 */
import { useCallback, useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { formatCurrency } from "../../utils/formatters";
import { apiErrorText } from "../../utils/apiError";

export const NO_ACCOUNT_TEXT = "PT ini belum punya rekening kas/bank aktif. Tambahkan di Keuangan › Kas & Bank.";
export const NEED_ACCOUNT_TEXT = "Pilih rekening atau kas sumber pembayaran.";

export function accountLabel(a) {
  return `${a.name}${a.bank_name ? ` · ${a.bank_name}` : ""}${a.account_number ? ` · ${a.account_number}` : ""}`;
}

export function useApPayment(kind, targetId, enabled = true) {
  const [accounts, setAccounts] = useState(null);
  const [pending, setPending] = useState(null);
  const [loadErr, setLoadErr] = useState("");
  const reload = useCallback(async () => {
    if (!enabled || !targetId) return;
    setLoadErr("");
    try {
      const params = { kind, target_id: targetId };
      const [acc, pen] = await Promise.all([
        axios.get(`${API}/ap-payments/accounts`, { params }),
        axios.get(`${API}/ap-payments/pending`, { params }),
      ]);
      setAccounts(Array.isArray(acc.data) ? acc.data : []);
      setPending(pen.data || null);
    } catch (e) { setLoadErr(apiErrorText(e)); setAccounts([]); }
  }, [kind, targetId, enabled]);
  useEffect(() => { reload(); }, [reload]);
  return { accounts, pending, loadErr, reload };
}

export function ApPaymentPending({ pending, onDone, onError, testId = "ap-pay-pending" }) {
  const [busy, setBusy] = useState(false);
  const [askReason, setAskReason] = useState(false);
  const [reason, setReason] = useState("");
  if (!pending) return null;
  const run = async (fn) => {
    setBusy(true);
    try { const r = await fn(); onDone?.(r?.data); } catch (e) { onError?.(apiErrorText(e)); } finally { setBusy(false); }
  };
  const resume = () => run(() => axios.post(`${API}/ap-payments/${pending.id}/resume`, {}));
  const cancel = () => run(() => axios.post(`${API}/ap-payments/${pending.id}/cancel`, { reason: reason.trim() }));
  return (
    <div className="notice-bar warning !items-start flex-col gap-1.5" data-testid={testId}>
      <span className="text-[12px]">
        Ada pembayaran <b>{formatCurrency(pending.amount)}</b> yang belum selesai diproses.
      </span>
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="primary-button !py-1" disabled={busy} onClick={resume}
          data-testid={`${testId}-resume`}>Lanjutkan pembayaran</button>
        {pending.step === "intent" && !askReason && (
          <button type="button" className="secondary-button !py-1" disabled={busy} onClick={() => setAskReason(true)}
            data-testid={`${testId}-cancel`}>Batalkan</button>
        )}
        {askReason && (
          <>
            <input className="field !py-1 text-[12px]" placeholder="Alasan membatalkan (min. 5 huruf)" value={reason}
              onChange={(e) => setReason(e.target.value)} data-testid={`${testId}-reason`} />
            <button type="button" className="danger-button !py-1" disabled={busy || reason.trim().length < 5}
              onClick={cancel} data-testid={`${testId}-cancel-confirm`}>Batalkan pembayaran</button>
          </>
        )}
      </div>
    </div>
  );
}
