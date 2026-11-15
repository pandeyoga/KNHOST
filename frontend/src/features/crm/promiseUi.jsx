/**
 * promiseUi (CR-T5) — janji bayar: lencana status, isian "Tanggal janji" + "Nominal janji", dan pop-up baku
 * "Catat janji bayar" (dipakai daftar kerja Kredit & Plafon dan kartu pelanggan).
 *
 * Status janji dihitung server saat dibaca (`credit_desk_service.promise_status`): menunggu · ditepati · ingkar.
 * Lencana = ikon + teks + warna (`status-pill` berkelas yang ada). Tanggal lewat `KNDatePicker` (bukan isian tanggal
 * peramban), tidak boleh sebelum hari ini (WIB) — server menolak tanggal lampau dengan kalimat yang sama.
 */
import { useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, HandCoins } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import FormModal from "../../components/FormModal";
import KNDatePicker from "../../components/KNDatePicker";
import MoneyInput from "../../components/MoneyInput";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, todayWib } from "../../utils/formatters";

export const PROMISE_STATUS = {
  menunggu: { label: "Menunggu", cls: "status-pending", Icon: Clock3 },
  ditepati: { label: "Ditepati", cls: "status-done", Icon: CheckCircle2 },
  ingkar: { label: "Ingkar", cls: "status-rejected", Icon: AlertTriangle },
};

export function PromiseStatusPill({ status, testId }) {
  const m = PROMISE_STATUS[status];
  if (!m) return null;
  const { Icon } = m;
  return (
    <span className={`status-pill ${m.cls} inline-flex items-center gap-1`} data-testid={testId}>
      <Icon size={12} aria-hidden="true" />{m.label}
    </span>
  );
}

/** Teks satu janji: "Janji Rp 500.000 · 10 Nov 2026". */
export function promiseText(fu, fmtDate) {
  if (!fu?.promise_date) return "";
  return `Janji ${formatCurrency(fu.promise_amount)} · ${fmtDate ? fmtDate(fu.promise_date) : fu.promise_date}`;
}

/** Isian wajib janji bayar (tampil saat hasil = "Dijanjikan bayar"). */
export function PromiseFields({ date, amount, onDate, onAmount, testIdPrefix = "promise", touch = false }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2" data-testid={`${testIdPrefix}-fields`}>
      <div>
        <label className="field-label">Tanggal janji <span className="text-kn-danger-text">*</span></label>
        <KNDatePicker value={date} onChange={onDate} min={todayWib()} clearable={false}
          className={touch ? "kn-input-touch" : ""} data-testid={`${testIdPrefix}-date`} />
      </div>
      <div>
        <label className="field-label">Nominal janji <span className="text-kn-danger-text">*</span></label>
        <MoneyInput testId={`${testIdPrefix}-amount`} value={amount} onChange={onAmount} placeholder="Rp 0"
          className={touch ? "field kn-input-touch" : "field"} />
      </div>
    </div>
  );
}

/** Pemeriksaan sisi layar (server tetap memutus): pesan sama dengan server. */
export function promiseError(date, amount) {
  if (!date) return "Tanggal janji bayar wajib diisi.";
  if (!(Number(amount) > 0)) return "Nominal janji bayar wajib lebih dari nol.";
  if (date < todayWib()) return "Tanggal janji bayar tidak boleh di masa lalu.";
  return "";
}

/** Pop-up "Catat janji bayar" — `POST /api/customers/{id}/followups` hasil `promised`. */
export function PromiseModal({ open, customer, defaultAmount = "", onClose, onDone }) {
  const [date, setDate] = useState("");
  const [amount, setAmount] = useState(defaultAmount ? String(defaultAmount) : "");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function simpan() {
    const pesan = promiseError(date, amount);
    if (pesan) { setError(pesan); return; }
    setBusy(true); setError("");
    try {
      await axios.post(`${API}/customers/${customer.id}/followups`, {
        customer_id: customer.id, outcome: "promised", note: note.trim() || "Janji bayar",
        promise_date: date, promise_amount: Number(amount) });
      onDone?.(`Janji bayar ${customer.name || ""} dicatat.`);
    } catch (e) {
      setError(apiErrorText(e, "Janji bayar belum bisa dicatat."));
    } finally { setBusy(false); }
  }
  return (
    <FormModal open={open} onClose={onClose} title="Catat janji bayar" subtitle={customer?.name || ""} icon={HandCoins}
      size="sm" testId="promise-modal" onSubmit={simpan} submitLabel="Simpan janji" busy={busy} error={error}>
      <PromiseFields date={date} amount={amount} onDate={setDate} onAmount={setAmount} />
      <div className="mt-3">
        <label className="field-label">Catatan <span className="font-normal text-kn-text-2">(opsional)</span></label>
        <textarea className="field" rows={2} value={note} data-testid="promise-note" placeholder="mis. transfer Jumat"
          onChange={(e) => setNote(e.target.value)} />
      </div>
    </FormModal>
  );
}
