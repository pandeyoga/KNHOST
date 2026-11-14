/**
 * PK-31 (IC-07) — **Catat Refund antar-PT**: retur atas transaksi yang sudah lunas membuat PT penjual berutang refund
 * kepada PT pembeli. Dialog ini mencatat pengembaliannya lewat kas/bank: satu kas keluar di PT penjual, satu kas masuk di
 * PT pembeli, jurnal di kedua PT (`POST /api/interco/refunds`, izin `interco.settle`).
 *
 * Isian: PT penjual (yang mengembalikan) · PT pembeli · transaksi bersisa refund · tanggal · cara bayar (daftar induk,
 * arah keluar) · rekening PT penjual. Konfirmasi menyebut nominal dan kedua PT (`02` N5); satu niat = satu
 * Idempotency-Key (N4).
 */
import { useEffect, useMemo, useState } from "react";
import { Undo2 } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import FormModal from "../../../components/FormModal";
import { KNSelect } from "../../../components/KNSelect";
import KNDatePicker from "../../../components/KNDatePicker";
import ErrorNotice from "../../../components/ErrorNotice";
import { formatCurrency } from "../../../utils/formatters";
import { apiErrorText } from "../../../utils/apiError";
import { moneyPost } from "../../../utils/moneyRequest";
import useIntentKey from "../../../hooks/useIntentKey";
import { askConfirm } from "../../../services/confirmService";
import { usePaymentMethods } from "../../../config/paymentMethods";
import { fmtDate } from "./intercoApi";

const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** Sisa refund satu dokumen penjual — rumus server `refund_due − refund_paid` (dokumen lama tanpa `refund_due`:
 *  max(0, retur + lunas − nilai)). */
export function refundLeft(doc) {
  const due = Number(doc?.refund_due ?? Math.max(0, (Number(doc?.returned_amount) || 0)
    + (Number(doc?.settled_amount) || 0) - (Number(doc?.grand_total) || 0)));
  return Math.max(0, Math.round((due - (Number(doc?.refund_paid) || 0)) * 100) / 100);
}

export default function IntercoRefundModal({ entities = [], presetPayerEntityId = "", presetPayeeEntityId = "",
  onClose, onCreated }) {
  const [payer, setPayer] = useState(presetPayerEntityId);
  const [payee, setPayee] = useState(presetPayeeEntityId);
  const [date, setDate] = useState(() => ymd(new Date()));
  const [method, setMethod] = useState("transfer");
  const [account, setAccount] = useState("");
  const [accounts, setAccounts] = useState([]);
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [picked, setPicked] = useState({});
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const intent = useIntentKey("ic-refund");
  const payMethods = usePaymentMethods("keluar", payer);
  const methodOptions = payMethods.methods.filter((m) => m.needs_account === "bank" || m.needs_account === "kas")
    .map((m) => ({ value: m.code, label: m.name }));

  const nameOf = (id) => {
    const e = entities.find((x) => x.id === id) || {};
    return e.short_name || e.legal_name || e.name || id || "";
  };
  const entOptions = entities.map((e) => ({ value: e.id, label: e.short_name || e.legal_name || e.name || e.id }));

  useEffect(() => {
    let alive = true;
    setPicked({}); setDocs([]); setAccounts([]); setAccount("");
    if (!payer) return () => { alive = false; };
    setLoading(true);
    Promise.all([
      axios.get(`${API}/interco/transactions`, { params: { entity_id: payer, role: "seller", refund_open: true } }),
      axios.get(`${API}/bank-accounts`, { params: { entity_id: payer } }),
    ]).then(([t, b]) => {
      if (!alive) return;
      setDocs(Array.isArray(t.data) ? t.data : []);
      const acc = (Array.isArray(b.data) ? b.data : [])
        .filter((a) => a.entity_id === payer && a.is_active !== false && a.status !== "inactive");
      setAccounts(acc);
      setAccount(acc[0]?.id || "");
    }).catch((e) => { if (alive) setErr(apiErrorText(e, "Gagal memuat transaksi bersisa pengembalian dana.")); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [payer]);

  const candidates = useMemo(() => docs.filter((d) => d.role === "seller" && d.seller_entity_id === payer
    && (!payee || d.buyer_entity_id === payee) && refundLeft(d) > 0.005), [docs, payer, payee]);
  const total = candidates.filter((d) => picked[d.id]).reduce((s, d) => s + refundLeft(d), 0);
  const reason = !payer || !payee ? "Pilih PT yang mengembalikan dana dan PT penerima."
    : payer === payee ? "PT yang mengembalikan dan PT penerima harus berbeda."
      : total <= 0 ? "Centang minimal satu transaksi yang punya sisa pengembalian dana."
        : !account ? "PT ini belum punya rekening kas/bank aktif — tambahkan di Keuangan › Kas & Bank." : "";

  const submit = async () => {
    if (reason || busy) return;
    const ok = await askConfirm({
      title: "Catat pengembalian dana antar-PT?",
      message: `Pengembalian dana ${formatCurrency(total)} dari ${nameOf(payer)} kepada ${nameOf(payee)} akan dicatat dan `
        + "dijurnal di kedua PT.",
      confirmLabel: "Catat Pengembalian Dana",
      testId: "interco-refund-confirm",
    });
    if (!ok) return;
    setBusy(true); setErr("");
    const body = {
      payer_entity_id: payer, payee_entity_id: payee, settle_date: date, method, bank_account_id: account, notes,
      transactions: candidates.filter((d) => picked[d.id]).map((d) => ({ interco_id: d.id, applied_amount: refundLeft(d) })),
    };
    try {
      const r = await intent.send(body, (k) => moneyPost(`${API}/interco/refunds`, body, k));
      onCreated?.(r?.data || {});
    } catch (e) { setErr(apiErrorText(e, "Pengembalian dana gagal dicatat.")); }
    finally { setBusy(false); }
  };

  return (
    <FormModal open onClose={onClose} size="lg" icon={Undo2} testId="interco-refund-modal" busy={busy}
      title="Catat Pengembalian Dana Antar-PT"
      subtitle="Retur atas transaksi yang sudah lunas: PT penjual mengembalikan kelebihan bayar lewat kas/bank."
      footer={(
        <div className="flex flex-wrap items-center justify-end gap-2">
          {reason && <span className="text-fs-12 text-kn-text-2" data-testid="interco-refund-reason">{reason}</span>}
          <button type="button" className="secondary-button" onClick={onClose} disabled={busy}
            data-testid="interco-refund-cancel">Batal</button>
          <button type="button" className="primary-button" onClick={submit} disabled={busy || Boolean(reason)}
            data-testid="interco-refund-submit">{busy ? "Mencatat…" : "Catat Pengembalian Dana"}</button>
        </div>
      )}>
      <div className="space-y-4">
        {err && <ErrorNotice message={err} onDismiss={() => setErr("")} testId="interco-refund-error" />}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <label className="block">
            <span className="field-label">PT yang mengembalikan (penjual) <span className="text-kn-danger-text">*</span></span>
            <KNSelect value={payer} onValueChange={setPayer} options={entOptions.filter((o) => o.value !== payee)}
              placeholder="Pilih PT penjual" data-testid="interco-refund-payer" />
          </label>
          <label className="block">
            <span className="field-label">PT penerima (pembeli) <span className="text-kn-danger-text">*</span></span>
            <KNSelect value={payee} onValueChange={setPayee} options={entOptions.filter((o) => o.value !== payer)}
              placeholder="Pilih PT pembeli" data-testid="interco-refund-payee" />
          </label>
          <label className="block">
            <span className="field-label">Tanggal <span className="text-kn-danger-text">*</span></span>
            <KNDatePicker value={date} onChange={setDate} clearable={false} data-testid="interco-refund-date" />
          </label>
          <label className="block">
            <span className="field-label">Cara bayar <span className="text-kn-danger-text">*</span></span>
            <KNSelect value={method} onValueChange={setMethod} options={methodOptions} data-testid="interco-refund-method" />
          </label>
          <label className="block md:col-span-2">
            <span className="field-label">Rekening {nameOf(payer) || "PT penjual"} <span className="text-kn-danger-text">*</span></span>
            <KNSelect value={account} onValueChange={setAccount} data-testid="interco-refund-account"
              options={accounts.map((a) => ({ value: a.id, label: a.name || a.account_name || a.id }))}
              placeholder={accounts.length ? "Pilih rekening" : "Belum ada rekening aktif"} />
          </label>
        </div>

        <div className="table-wrap">
          <table className="data-table" data-testid="interco-refund-candidates">
            <thead>
              <tr>
                <th className="w-10"><span className="sr-only">Pilih</span></th>
                <th>Transaksi</th>
                <th>Tanggal</th>
                <th className="text-right">Sisa pengembalian dana</th>
              </tr>
            </thead>
            <tbody>
              {loading && <tr><td colSpan={4} className="py-6 text-center text-kn-text-2">Memuat transaksi…</td></tr>}
              {!loading && candidates.length === 0 && (
                <tr><td colSpan={4} className="py-6 text-center text-kn-text-2" data-testid="interco-refund-empty">
                  {payer && payee ? "Tidak ada transaksi bersisa pengembalian dana untuk pasangan PT ini." : "Pilih kedua PT dulu."}
                </td></tr>
              )}
              {!loading && candidates.map((d) => (
                <tr key={d.id} data-testid={`interco-refund-row-${d.id}`}>
                  <td>
                    <input type="checkbox" checked={Boolean(picked[d.id])} aria-label={`Pilih ${d.number}`}
                      onChange={() => setPicked((p) => ({ ...p, [d.id]: !p[d.id] }))}
                      data-testid={`interco-refund-check-${d.id}`} />
                  </td>
                  <td className="font-semibold text-kn-text">{d.number}</td>
                  <td>{fmtDate(d.doc_date)}</td>
                  <td className="text-right tabular-nums">{formatCurrency(refundLeft(d))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between rounded-md bg-kn-neutral-soft px-3 py-2 text-fs-13">
          <span className="text-kn-text-2">Dibayar penuh per transaksi</span>
          <span className="text-kn-text">Total pengembalian dana <b className="tabular-nums" data-testid="interco-refund-total">{formatCurrency(total)}</b></span>
        </div>
        <label className="block">
          <span className="field-label">Catatan</span>
          <textarea className="field" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)}
            data-testid="interco-refund-notes" />
        </label>
      </div>
    </FormModal>
  );
}
