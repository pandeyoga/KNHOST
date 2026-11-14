/**
 * BudgetDialogs — PK-39 (FY-12) · pop-up pagu anggaran (dipisah dari BudgetParts supaya berkas < 500 baris).
 *
 *  · `BudgetHistoryModal` — "Riwayat Pagu": GET /finance/budgets/{id}/history (terbaru dulu). Kolom Waktu · Oleh ·
 *    Perubahan · Alasan. Memuat / galat / kosong ("Belum ada perubahan.") dibedakan.
 *  · `BudgetEditModal` — ubah nominal pagu + "Alasan perubahan" (opsional) → masuk riwayat pagu (sebelum/sesudah).
 * Warna lewat token `kn-*`, huruf ≥ 12 px, tabel baku `data-table` di `table-wrap`.
 */
import { useCallback, useEffect, useState } from "react";
import { History, Pencil, X } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import DetailModal from "../../components/DetailModal";
import FormModal from "../../components/FormModal";
import MoneyInput from "../../components/MoneyInput";
import ErrorNotice from "../../components/ErrorNotice";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatDateTime } from "../../utils/formatters";

const BULAN = ["Tahunan", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September",
  "Oktober", "November", "Desember"];
const periodeText = (s) => `${BULAN[Number(s?.month) || 0] || "—"} ${s?.year || ""}`.trim();

/** Kalimat perubahan satu baris riwayat (nominal, periode, catatan). */
export function historyChange(h) {
  const b = h?.before || {};
  const a = h?.after || {};
  if (h?.action === "created") return `Dibuat · ${formatCurrency(a.amount)} · ${periodeText(a)}`;
  if (h?.action === "deleted") return `Dihapus · ${formatCurrency(b.amount)} · ${periodeText(b)}`;
  const parts = [];
  if (Number(b.amount) !== Number(a.amount)) parts.push(`Nominal ${formatCurrency(b.amount)} → ${formatCurrency(a.amount)}`);
  if (Number(b.month) !== Number(a.month) || Number(b.year) !== Number(a.year)) {
    parts.push(`Periode ${periodeText(b)} → ${periodeText(a)}`);
  }
  if ((b.note || "") !== (a.note || "")) parts.push("Catatan diubah");
  return parts.join(" · ") || "Disimpan tanpa perubahan nilai";
}

export function BudgetHistoryModal({ row, onClose }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setError(""); setRows(null);
    try {
      const r = await axios.get(`${API}/finance/budgets/${row.id}/history`);
      setRows(Array.isArray(r.data) ? r.data : []);
    } catch (e) { setError(apiErrorText(e, "Gagal memuat riwayat pagu.")); setRows([]); }
  }, [row.id]);
  useEffect(() => { load(); }, [load]);

  return (
    <DetailModal onClose={onClose} framed showClose={false} size="lg" label="Riwayat Pagu" testId="budget-history">
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <h3 className="modal-title flex items-center gap-1.5"><History size={16} /> Riwayat Pagu</h3>
          <p className="modal-subtitle">
            {row.label || row.key} ({row.key}) · {periodeText({ month: row.month, year: row.year || "" })}
            {row.entity_name ? ` · ${row.entity_name}` : ""}
          </p>
        </div>
        <button type="button" data-testid="budget-history-close" className="icon-button" onClick={onClose}
          aria-label="Tutup"><X size={15} /></button>
      </div>
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="budget-history-error" />
      {rows === null ? (
        <div className="grid gap-2" data-testid="budget-history-loading">
          {[0, 1, 2].map((i) => <div key={i} className="h-8 rounded bg-kn-neutral-soft animate-pulse" />)}
        </div>
      ) : rows.length === 0 ? (
        !error && <p className="py-6 text-center text-fs-12 text-kn-text-2" data-testid="budget-history-empty">
          Belum ada perubahan.</p>
      ) : (
        <div className="table-wrap max-h-[50vh] overflow-auto">
          <table className="data-table head-wrap" data-testid="budget-history-table">
            <thead>
              <tr><th>Waktu</th><th>Oleh</th><th>Perubahan</th><th>Alasan</th></tr>
            </thead>
            <tbody>
              {rows.map((h) => (
                <tr key={h.id} data-testid={`budget-history-row-${h.action}`}>
                  <td className="whitespace-nowrap">{formatDateTime(h.at)}</td>
                  <td>{h.by || "—"}</td>
                  <td className="tabular-nums">{historyChange(h)}</td>
                  <td>{h.reason || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </DetailModal>
  );
}

export function BudgetEditModal({ row, busy = false, error = "", onSubmit, onCancel }) {
  const [amount, setAmount] = useState(String(row?.budget ?? ""));
  const [reason, setReason] = useState("");
  return (
    <FormModal open onClose={onCancel} size="md" icon={Pencil} testId="budget-edit-form"
      title={`Ubah pagu · ${row?.label || row?.key || ""}`}
      subtitle={`${row?.key || ""} · ${periodeText({ month: row?.month, year: row?.year || "" })}${row?.entity_name ? ` · ${row.entity_name}` : ""}`}
      onSubmit={() => onSubmit(row, Number(amount), reason.trim())} busy={busy} error={error} submitLabel="Simpan"
      submitDisabled={!amount || Number(amount) <= 0}
      submitTestId="budget-edit-submit" cancelTestId="budget-edit-cancel">
      <div className="grid gap-3">
        <div>
          <label className="field-label" htmlFor="budget-edit-amount">Nominal pagu (Rp) *</label>
          <MoneyInput testId="budget-edit-amount" className="field" value={amount} onChange={(v) => setAmount(v)} />
          <p className="mt-1 text-fs-12 text-kn-text-2">Sebelumnya {formatCurrency(row?.budget)}.</p>
        </div>
        <div>
          <label className="field-label" htmlFor="budget-edit-reason">Alasan perubahan (opsional)</label>
          <textarea id="budget-edit-reason" data-testid="budget-edit-reason" className="field" rows={2}
            value={reason} placeholder="Mis. revisi triwulan" onChange={(e) => setReason(e.target.value)} />
        </div>
      </div>
    </FormModal>
  );
}
