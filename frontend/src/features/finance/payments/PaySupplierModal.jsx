/**
 * PaySupplierModal (MN-T3) — SATU form "Bayar pemasok" untuk tagihan pemasok dan kontrabon, dari titik masuk mana pun
 * (detail tagihan, detail kontrabon, Rekonsiliasi Bank, Perlu Tindakan, kartu pemasok). Diturunkan dari
 * `purchasing/contrabon/PayModal.jsx` (isian paling lengkap); memanggil pintu bayar hutang PK-05 yang sama.
 *
 * Tanda tangan: `{ target: { type: "vendor_bill" | "contra_bon", id }, bankLineId?, onClose, onPaid }`
 * (+ `preset` = { amount, date, accountId } dari baris mutasi, `onError`).
 *  · Isian: Pemasok · Dokumen (hanya-baca) · Sisa hutang (hanya-baca) · Nominal dibayar · Tanggal bayar · Cara bayar ·
 *    Rekening sumber (rekening AKTIF milik PT dokumen, `GET /ap-payments/accounts`) · Catatan.
 *  · Tombol "Bayar" → konfirmasi "Bayar Rp {nominal} ke {pemasok} dari {rekening} untuk {nama PT}?" ("Ya, bayar" /
 *    "Batal"). Mode Semua PT: tombol mati + "Pilih satu PT untuk mencatat pembayaran.". Kunci `useIntentKey`; galat
 *    server di dalam pop-up; niat bayar menggantung → Lanjutkan / Batalkan (`ApPaymentPending`, PK-05).
 *  · `bankLineId`: nominal, tanggal, dan rekening = baris mutasi (hanya-baca). Kontrabon → `pay-from-bank-line`
 *    (server membuat kas dan menautkan baris); tagihan → `pay` lalu kas pembayarannya ditautkan ke baris itu.
 *  · Selisih bayar: bayar sebagian = sisa tetap hutang (perilaku pintu PK-05); keputusan selisih pemasok lain
 *    belum ditawarkan (tidak ada endpoint takar selisih pemasok — dicatat di laporan MN-T3).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Banknote, Building2, Info } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import KNDatePicker from "../../../components/KNDatePicker";
import KNSelect from "../../../components/KNSelect";
import MoneyInput from "../../../components/MoneyInput";
import ErrorNotice from "../../../components/ErrorNotice";
import FormModal from "../../../components/FormModal";
import { formatCurrency, formatDate } from "../../../utils/formatters";
import { apiErrorText } from "../../../utils/apiError";
import { moneyPost } from "../../../utils/moneyRequest";
import useIntentKey from "../../../hooks/useIntentKey";
import { canonicalMethod, usePaymentMethods } from "../../../config/paymentMethods";
import { useEntityScope } from "../../../context/EntityScopeContext";
import { askConfirm } from "../../../services/confirmService";
import { entityShortById } from "../../../utils/entityLabel";
import { ApPaymentPending, NEED_ACCOUNT_TEXT, NO_ACCOUNT_TEXT, accountLabel, useApPayment } from "../../purchasing/apPayment";
import { TEKS_PILIH_PT } from "./ReceivePaymentModal";

const pad = (n) => String(n).padStart(2, "0");
function today() { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; }

export const JENIS_DOKUMEN = { vendor_bill: "Tagihan pemasok", contra_bon: "Kontrabon" };

/** Isi `POST /vendor-bills/{id}/pay` dan `POST /contra-bons/{id}/pay` — bentuk sama untuk keduanya (U4). */
export function payBody({ amount, method, paidAt, accountId, notes = "" }) {
  return { amount: Number(amount), method, paid_at: paidAt, bank_account_id: accountId, notes: String(notes || "").trim() };
}

/** Kalimat konfirmasi N5 (persis spesifikasi). */
export const payConfirmText = ({ amount, supplier, account, pt }) =>
  `Bayar ${formatCurrency(amount)} ke ${supplier || "pemasok"} dari ${account} untuk ${pt}?`;

/** Ringkasan dokumen untuk kepala form: pemasok, nomor, sisa, PT. */
export function docSummary(type, doc) {
  if (!doc) return null;
  if (type === "contra_bon") {
    const t = doc.totals || {};
    return { supplier: doc.supplier_name, number: doc.number, outstanding: Number(t.outstanding ?? 0),
      entityId: doc.entity_id, firstPayment: !(doc.payments || []).length, deductions: Number(t.deductions_total || 0),
      defaultMethod: (doc.schedule || {}).method, defaultAccount: (doc.schedule || {}).bank_account_id || "" };
  }
  const fin = doc.financials || {};
  return { supplier: doc.supplier_name, number: doc.bill_number, outstanding: Number(fin.outstanding ?? doc.outstanding ?? 0),
    entityId: doc.entity_id, firstPayment: false, deductions: 0, defaultMethod: "", defaultAccount: "" };
}

export default function PaySupplierModal({ target, bankLineId = "", preset = null, onClose, onPaid, onError }) {
  const type = target?.type === "contra_bon" ? "contra_bon" : "vendor_bill";
  const id = target?.id || "";
  const [doc, setDoc] = useState(null);
  const [loadErr, setLoadErr] = useState("");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);
  const inFlight = useRef(false);
  const { selectedEntity, entities } = useEntityScope();
  const allPt = !selectedEntity || selectedEntity === "all";
  const fromLine = Boolean(bankLineId);
  const [amount, setAmount] = useState(preset?.amount ? String(preset.amount) : "");
  const [paidAt, setPaidAt] = useState(preset?.date ? String(preset.date).slice(0, 10) : today());
  const [accountId, setAccountId] = useState(preset?.accountId || "");
  const [method, setMethod] = useState("transfer");
  const [notes, setNotes] = useState("");
  const intent = useIntentKey(type === "contra_bon" ? "cbpay" : "vbpay");
  const matchIntent = useIntentKey("vbbank");

  const load = useCallback(async () => {
    if (!id) return;
    setLoadErr("");
    try {
      const r = await axios.get(`${API}/${type === "contra_bon" ? "contra-bons" : "vendor-bills"}/${id}`);
      setDoc(r.data || null);
    } catch (e) { setLoadErr(apiErrorText(e, "Dokumen yang akan dibayar belum bisa dimuat.")); }
  }, [type, id]);
  useEffect(() => { load(); }, [load]);

  const sum = useMemo(() => docSummary(type, doc), [type, doc]);
  useEffect(() => {
    if (!sum) return;
    if (!fromLine && amount === "" && sum.outstanding > 0) setAmount(String(sum.outstanding));
    if (sum.defaultMethod) setMethod(canonicalMethod(sum.defaultMethod, "transfer"));
    if (!accountId && sum.defaultAccount) setAccountId(sum.defaultAccount);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sum]);
  const payMethods = usePaymentMethods("keluar", sum?.entityId);
  const ap = useApPayment(type, id, Boolean(id));
  const accounts = ap.accounts || [];
  const accountOptions = useMemo(() => accounts.map((a) => ({ value: a.id, label: accountLabel(a) })), [accounts]);
  const accLabel = (accounts.find((a) => a.id === accountId) && accountLabel(accounts.find((a) => a.id === accountId)))
    || "rekening terpilih";
  const ptName = entityShortById(entities, sum?.entityId || selectedEntity, "PT dokumen");
  const amt = Number(amount) || 0;
  const reason = allPt ? TEKS_PILIH_PT : (!doc ? "" : amt <= 0 ? "Isi nominal dibayar." : !accountId ? NEED_ACCOUNT_TEXT : "");

  async function linkLine(data) {
    if (!fromLine || type !== "vendor_bill") return "";
    const pid = data?.payment_intent?.id;
    const entry = (data?.payments || []).find((p) => p.payment_intent_id === pid && p.cash_txn_id);
    if (!entry) return " Mutasi bank belum tertaut: kas pembayaran tidak ditemukan.";
    try {
      const b = { txn_id: entry.cash_txn_id };
      await matchIntent.send({ line: bankLineId, ...b },
        (k) => moneyPost(`${API}/bank-reconciliation/lines/${bankLineId}/match`, b, k));
      return " Baris mutasi ditautkan ke kas pembayarannya.";
    } catch (e) { return ` Mutasi bank belum tertaut: ${apiErrorText(e, "tautkan di Rekonsiliasi.")}`; }
  }

  async function pay() {
    if (inFlight.current || saving) return;
    if (reason) { setErr(reason); return; }
    const body = payBody({ amount: amt, method, paidAt, accountId, notes });
    inFlight.current = true;
    try {
      const ok = await askConfirm({
        title: "Bayar pemasok",
        message: payConfirmText({ amount: amt, supplier: sum?.supplier, account: accLabel, pt: ptName }),
        confirmLabel: "Ya, bayar", cancelLabel: "Batal", testId: "pay-supplier-confirm",
      });
      if (!ok) return;
      setSaving(true); setErr("");
      let r;
      if (fromLine && type === "contra_bon") {
        const b = { note: notes.trim() || "Dibayar dari baris mutasi bank" };
        r = await intent.send({ id, line: bankLineId, ...b },
          (k) => moneyPost(`${API}/contra-bons/${id}/pay-from-bank-line/${bankLineId}`, b, k));
      } else {
        const url = type === "contra_bon" ? `${API}/contra-bons/${id}/pay` : `${API}/vendor-bills/${id}/pay`;
        r = await intent.send(body, (k) => moneyPost(url, body, k));
      }
      const data = r.data || {};
      const bank = await linkLine(data);
      const lunas = data.status === "paid" ? " — LUNAS." : ".";
      const warn = data.warning ? ` ${data.warning}` : "";
      onPaid?.(data, `${JENIS_DOKUMEN[type]} ${sum?.number || ""} dibayar ${formatCurrency(fromLine ? preset?.amount || amt : amt)}${lunas}${warn}${bank}`);
    } catch (e) {
      const msg = apiErrorText(e, "Pembayaran belum bisa dicatat.");
      setErr(msg); onError?.(e);
      ap.reload();
    } finally { setSaving(false); inFlight.current = false; }
  }

  return (
    <FormModal open onClose={onClose} title="Bayar pemasok" icon={Banknote} size="md" testId="pay-supplier-modal" busy={saving}
      subtitle={sum ? `${JENIS_DOKUMEN[type]} ${sum.number || ""} · ${sum.supplier || ""}` : ""}
      footer={(
        <div className="flex flex-wrap items-center justify-end gap-2">
          {reason && doc && <span className="text-fs-12 text-kn-text-2" data-testid={allPt ? "pay-supplier-scope-note" : "pay-supplier-reason"}>{reason}</span>}
          <button type="button" className="secondary-button btn-sm whitespace-nowrap" onClick={onClose} disabled={saving}
            data-testid="pay-supplier-cancel">Batal</button>
          <button type="button" className="primary-button btn-sm whitespace-nowrap" data-testid="pay-supplier-submit"
            disabled={saving || !doc || Boolean(reason) || Boolean(ap.pending)} onClick={pay}>
            {saving ? "Memproses…" : "Bayar"}
          </button>
        </div>
      )}>
      <div className="space-y-3">
        <p className="notice-bar info text-fs-12" data-testid="pay-supplier-pt">
          <Building2 size={13} aria-hidden="true" />PT: {allPt ? "Semua PT" : ptName}
        </p>
        <ErrorNotice message={loadErr || err} onRetry={loadErr ? load : undefined}
          onDismiss={loadErr ? undefined : () => setErr("")} testId="pay-supplier-error" />
        <ApPaymentPending pending={ap.pending} testId="pay-supplier-pending"
          onDone={(d) => { ap.reload(); if (d) onPaid?.(d, "Pembayaran yang tertunda dilanjutkan."); }} onError={setErr} />
        {ap.accounts && ap.accounts.length === 0 && (
          <p className="text-fs-12 text-kn-danger-text" data-testid="pay-supplier-no-account">{NO_ACCOUNT_TEXT}</p>
        )}
        {!doc && !loadErr ? (
          <p className="py-4 text-center text-fs-12 text-kn-text-2" data-testid="pay-supplier-loading">Memuat dokumen…</p>
        ) : doc && (
          <>
            <dl className="grid grid-cols-1 gap-2 text-fs-13 sm:grid-cols-3" data-testid="pay-supplier-doc">
              <div><dt className="field-label">Pemasok</dt><dd data-testid="pay-supplier-supplier">{sum.supplier || "—"}</dd></div>
              <div><dt className="field-label">Dokumen</dt><dd data-testid="pay-supplier-number">{JENIS_DOKUMEN[type]} {sum.number}</dd></div>
              <div><dt className="field-label">Sisa hutang</dt>
                <dd className="whitespace-nowrap font-semibold tabular-nums" data-testid="pay-supplier-outstanding">{formatCurrency(sum.outstanding)}</dd></div>
            </dl>
            {type === "contra_bon" && sum.firstPayment && sum.deductions > 0 && (
              <p className="flex items-start gap-1 rounded-md bg-kn-action-soft px-2 py-1.5 text-fs-12" data-testid="pay-supplier-deduction-note">
                <Info size={12} className="mt-0.5 shrink-0" aria-hidden="true" />
                Pada pembayaran pertama, potongan {formatCurrency(sum.deductions)} ikut diterapkan sebagai pelunasan non-kas;
                uang yang keluar hanya nilai bersihnya.
              </p>
            )}
            {fromLine && (
              <p className="notice-bar info text-fs-12" data-testid="pay-supplier-bank-line">
                Dari mutasi bank {preset?.date ? formatDate(preset.date) : ""}: nominal, tanggal, dan rekening mengikuti mutasi.
              </p>
            )}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="field-label">Nominal dibayar</label>
                {fromLine ? <p className="field flex items-center tabular-nums" data-testid="pay-supplier-amount-fixed">{formatCurrency(amt)}</p>
                  : <MoneyInput testId="pay-supplier-amount" className="field" value={amount} onChange={(v) => setAmount(v)} />}
                {!fromLine && <p className="mt-1 text-fs-12 text-kn-text-2">Bayar sebagian diizinkan; sisanya tetap hutang.</p>}
              </div>
              <div>
                <label className="field-label">Tanggal bayar</label>
                <KNDatePicker data-testid="pay-supplier-date" value={paidAt} onChange={setPaidAt} clearable={false} disabled={fromLine} />
              </div>
              <div>
                <label className="field-label">Cara bayar</label>
                <KNSelect data-testid="pay-supplier-method" value={method} onValueChange={setMethod} options={payMethods.options} className="field" />
              </div>
              <div>
                <label className="field-label">Rekening sumber</label>
                <KNSelect data-testid="pay-supplier-account" value={accountId} onValueChange={setAccountId} options={accountOptions}
                  className="field" placeholder="Pilih rekening" disabled={fromLine} />
              </div>
            </div>
            <div>
              <label className="field-label">Catatan</label>
              <textarea data-testid="pay-supplier-notes" className="textarea w-full" rows={2} value={notes}
                onChange={(e) => setNotes(e.target.value)} placeholder="Opsional — mis. nomor bukti transfer" />
            </div>
          </>
        )}
      </div>
    </FormModal>
  );
}
