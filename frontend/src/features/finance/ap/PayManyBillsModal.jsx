/**
 * PayManyBillsModal (S5, pelatihan keuangan 18 Nov) — **Bayar beberapa tagihan pemasok sekaligus** dari Hutang per
 * Pemasok. Permintaan pemilik: "di klik muncul semua hutang … dan bisa aksi bayar juga".
 *
 * Satu form untuk tagihan yang dicentang (satu pemasok, satu PT): Rekening sumber · Tanggal bayar · Cara bayar · Catatan,
 * lalu tabel nominal per tagihan (terisi sisa; boleh diubah, tidak boleh melebihi sisa). Tombol "Bayar n tagihan" →
 * SATU konfirmasi N5 menyebut total, pemasok, rekening, dan PT → tiap tagihan dibayar lewat pintu yang SUDAH ADA
 * (`POST /vendor-bills/{id}/pay`, PK-05) berurutan, satu kunci idempoten per tagihan (`useBatchKeys`): klik ulang /
 * jaringan putus tidak menggandakan kas. Hasil per tagihan tampil di form (Lunas · Dibayar sebagian · galat server);
 * yang gagal bisa diulang dengan kunci yang sama. Tidak ada aturan bisnis baru: selisih, toleransi, kontrabon pemegang,
 * periode tertutup — semuanya diputus pintu bayar itu.
 */
import { useMemo, useRef, useState } from "react";
import { Banknote, Building2, AlertTriangle } from "lucide-react";
import { API } from "../../../services/apiClient";
import FormModal from "../../../components/FormModal";
import KNDatePicker from "../../../components/KNDatePicker";
import KNSelect from "../../../components/KNSelect";
import MoneyInput from "../../../components/MoneyInput";
import ErrorNotice from "../../../components/ErrorNotice";
import StatusBadge from "../../../components/StatusBadge";
import { formatDate, todayWib } from "../../../utils/formatters";
import { parseDecimal } from "../../../utils/decimalInput";
import { apiErrorText } from "../../../utils/apiError";
import { moneyPost } from "../../../utils/moneyRequest";
import { usePaymentMethods } from "../../../config/paymentMethods";
import { askConfirm } from "../../../services/confirmService";
import { NO_ACCOUNT_TEXT, accountLabel, useApPayment } from "../../purchasing/apPayment";
import { rpSen } from "../payments/PaySupplierModal";
import { bayarBanyakConfirmText, bayarBerurutan, cekBayarBanyak, ringkasHasil, useBatchKeys } from "./apPartyApi";

export default function PayManyBillsModal({ supplierName, entityId, ptName, bills, allPt = false, onClose, onDone }) {
  const [amounts, setAmounts] = useState(() => Object.fromEntries((bills || []).map((b) => [b.bill_id,
    String(Math.round(Number(b.outstanding || 0) * 100) / 100)])));
  const [paidAt, setPaidAt] = useState(todayWib());
  const [method, setMethod] = useState("transfer");
  const [accountId, setAccountId] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [results, setResults] = useState(null);
  const inFlight = useRef(false);
  const keys = useBatchKeys("vbpay");
  const first = bills?.[0]?.bill_id || "";
  const ap = useApPayment("vendor_bill", first, Boolean(first));
  const accounts = useMemo(() => ap.accounts || [], [ap.accounts]);
  const accountOptions = useMemo(() => accounts.map((a) => ({ value: a.id, label: accountLabel(a) })), [accounts]);
  const accLabel = (() => { const a = accounts.find((x) => x.id === accountId); return a ? accountLabel(a) : "rekening terpilih"; })();
  const payMethods = usePaymentMethods("keluar", entityId);

  // Tagihan yang tersisa untuk dibayar: semua (awal) atau yang gagal pada putaran sebelumnya.
  const pending = useMemo(() => {
    if (!results) return bills || [];
    const gagal = new Set(results.filter((r) => !r.ok).map((r) => r.bill_id));
    return (bills || []).filter((b) => gagal.has(b.bill_id));
  }, [bills, results]);
  const parsed = useMemo(() => Object.fromEntries(pending.map((b) => {
    const v = parseDecimal(amounts[b.bill_id]);
    return [b.bill_id, Number.isFinite(v) ? v : 0];
  })), [pending, amounts]);
  const cek = cekBayarBanyak(pending, parsed, { accountId, allPt });
  const selesai = results && !pending.length;

  async function bayar() {
    if (inFlight.current || saving) return;
    if (cek.blok) { setErr(cek.blok); return; }
    inFlight.current = true;
    try {
      const info = cek.items.map((it) => it.info).filter(Boolean).join(" ");
      const ok = await askConfirm({
        title: "Bayar beberapa tagihan",
        message: bayarBanyakConfirmText({ count: cek.items.length, total: cek.total, supplier: supplierName,
          account: accLabel, pt: ptName }) + (info ? ` ${info}` : ""),
        confirmLabel: "Ya, bayar", cancelLabel: "Batal", testId: "pay-many-confirm",
      });
      if (!ok) return;
      setSaving(true); setErr("");
      const out = await bayarBerurutan({ items: cek.items, base: { method, paidAt, accountId, notes }, keys,
        post: moneyPost, api: API, errText: (e) => apiErrorText(e, "Pembayaran belum bisa dicatat.") });
      const prev = (results || []).filter((r) => r.ok);
      const all = [...prev, ...out];
      setResults(all);
      onDone?.(all, ringkasHasil(all));
    } finally { setSaving(false); inFlight.current = false; }
  }

  const footer = (
    <div className="flex flex-wrap items-center justify-end gap-2">
      {!selesai && cek.blok && <span className="text-fs-12 text-kn-text-2" data-testid="pay-many-reason">{cek.blok}</span>}
      <button type="button" className="secondary-button btn-sm whitespace-nowrap" onClick={onClose} disabled={saving}
        data-testid="pay-many-close">{results ? "Tutup" : "Batal"}</button>
      {!selesai && (
        <button type="button" className="primary-button btn-sm whitespace-nowrap" data-testid="pay-many-submit"
          disabled={saving || Boolean(cek.blok)} onClick={bayar}>
          {saving ? "Memproses…" : results ? `Ulangi ${pending.length} yang gagal` : `Bayar ${pending.length} tagihan · ${rpSen(cek.total)}`}
        </button>
      )}
    </div>
  );

  return (
    <FormModal open onClose={onClose} title="Bayar beberapa tagihan" icon={Banknote} size="lg" testId="pay-many-modal"
      busy={saving} subtitle={`${supplierName || "Pemasok"} · ${(bills || []).length} tagihan`} footer={footer}>
      <div className="space-y-3">
        <p className="notice-bar info text-fs-12" data-testid="pay-many-pt">
          <Building2 size={13} aria-hidden="true" />PT: {allPt ? "Semua PT" : ptName}
        </p>
        <ErrorNotice message={err || ap.loadErr} onDismiss={() => setErr("")} testId="pay-many-error" />
        {ap.accounts && ap.accounts.length === 0 && (
          <p className="text-fs-12 text-kn-danger-text" data-testid="pay-many-no-account">{NO_ACCOUNT_TEXT}</p>
        )}
        {results && (
          <div className="table-wrap" data-testid="pay-many-results">
            <table className="data-table head-wrap">
              <thead><tr><th>Tagihan</th><th className="text-right">Dibayar</th><th className="text-right">Sisa</th><th>Hasil</th></tr></thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.bill_id} data-testid={`pay-many-result-${r.bill_id}`}>
                    <td className="whitespace-nowrap font-semibold">{r.bill_number}</td>
                    <td className="whitespace-nowrap text-right tabular-nums">{r.ok ? rpSen(r.amount) : "—"}</td>
                    <td className="whitespace-nowrap text-right tabular-nums">{rpSen(r.outstanding)}</td>
                    <td>
                      {r.ok ? (
                        <StatusBadge tone="success" icon="check" label={r.message} />
                      ) : (
                        <span className="inline-flex items-start gap-1 text-fs-12 text-kn-danger-text"><AlertTriangle size={12} className="mt-0.5 shrink-0" aria-hidden="true" />{r.message}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-1 text-fs-12 text-kn-text-2" data-testid="pay-many-summary">{ringkasHasil(results)}</p>
          </div>
        )}
        {!selesai && (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="field-label">Rekening sumber</label>
                <KNSelect data-testid="pay-many-account" value={accountId} onValueChange={setAccountId} options={accountOptions}
                  className="field" placeholder="Pilih rekening" />
              </div>
              <div>
                <label className="field-label">Tanggal bayar</label>
                <KNDatePicker data-testid="pay-many-date" value={paidAt} onChange={setPaidAt} clearable={false} />
              </div>
              <div>
                <label className="field-label">Cara bayar</label>
                <KNSelect data-testid="pay-many-method" value={method} onValueChange={setMethod} options={payMethods.options} className="field" />
              </div>
              <div>
                <label className="field-label">Catatan</label>
                <input data-testid="pay-many-notes" className="field" value={notes} onChange={(e) => setNotes(e.target.value)}
                  placeholder="Opsional — mis. nomor bukti transfer" />
              </div>
            </div>
            <div className="table-wrap">
              <table className="data-table head-wrap" data-testid="pay-many-table">
                <thead><tr><th>Tagihan</th><th>Jatuh tempo</th><th className="text-right">Sisa hutang</th><th className="text-right">Nominal dibayar</th></tr></thead>
                <tbody>
                  {pending.map((b) => (
                    <tr key={b.bill_id} data-testid={`pay-many-row-${b.bill_id}`}>
                      <td className="whitespace-nowrap"><span className="font-semibold">{b.bill_number}</span>
                        {b.supplier_invoice_no && <span className="block text-fs-12 text-kn-text-2">{b.supplier_invoice_no}</span>}</td>
                      <td className="whitespace-nowrap">{b.due_date ? formatDate(b.due_date) : "—"}</td>
                      <td className="whitespace-nowrap text-right tabular-nums">{rpSen(b.outstanding)}</td>
                      <td className="text-right">
                        <MoneyInput testId={`pay-many-amount-${b.bill_id}`} className="field w-40" value={amounts[b.bill_id] ?? ""}
                          onChange={(v) => setAmounts((a) => ({ ...a, [b.bill_id]: v }))} showPreview={false} />
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="font-bold">
                    <td colSpan={3} className="text-right">Total dibayar</td>
                    <td className="whitespace-nowrap text-right tabular-nums" data-testid="pay-many-total">{rpSen(cek.total)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
            {cek.items.some((it) => it.info) && (
              <p className="text-fs-12 text-kn-warning-text" data-testid="pay-many-variance-note">
                {cek.items.map((it) => it.info).filter(Boolean).join(" ")}
              </p>
            )}
            <p className="text-fs-12 text-kn-text-2">Bayar sebagian diizinkan; sisanya tetap hutang. Tiap tagihan menjadi satu kas
              keluar dan satu jurnal (Hutang Usaha di debit, rekening di kredit).</p>
          </>
        )}
      </div>
    </FormModal>
  );
}
