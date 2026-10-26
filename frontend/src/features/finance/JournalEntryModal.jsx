/**
 * JournalEntryModal (EPIC7-C) — buat jurnal manual double-entry seimbang.
 * Dipakai oleh GeneralLedger. Validasi balance di sisi klien + server.
 *
 * Fase 4 · R2 (L-03) — `div fixed inset-0` buatan sendiri → `FormModal` baku (Esc/klik latar seragam, kepala &
 * kaki menempel, layar penuh di HP). Isian & testid tetap (`je-modal`, `je-modal-close`, `je-submit`, `je-error`).
 */
import { apiErrorText } from "../../utils/apiError";
import KNDatePicker from "@/components/KNDatePicker";
import { useEffect, useMemo, useState } from "react";
import { Plus, Trash2, Scale, AlertTriangle } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import FormModal from "../../components/FormModal";
import { formatCurrency, todayWib } from "../../utils/formatters";

const emptyLine = () => ({ account_code: "", debit: "", credit: "", description: "" });

export default function JournalEntryModal({ accounts, onClose, onSaved }) {
  const today = todayWib();
  const [date, setDate] = useState(today);
  const [description, setDescription] = useState("");
  const [lines, setLines] = useState([emptyLine(), emptyLine()]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [periodWarning, setPeriodWarning] = useState(null);

  // Soft-lock: peringatkan (tanpa memblokir) bila tanggal berada di periode tertutup.
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const res = await axios.get(`${API}/finance/closing/status`, { params: { date } });
        if (active) setPeriodWarning(res.data?.closed ? res.data : null);
      } catch {
        if (active) setPeriodWarning(null);
      }
    })();
    return () => { active = false; };
  }, [date]);

  const accountOptions = useMemo(
    () => accounts.filter((a) => a.is_postable && a.is_active !== false)
      .map((a) => ({ value: a.code, label: `${a.code} — ${a.name}` })),
    [accounts]);

  const totals = useMemo(() => {
    const d = lines.reduce((s, l) => s + (Number(l.debit) || 0), 0);
    const c = lines.reduce((s, l) => s + (Number(l.credit) || 0), 0);
    return { debit: d, credit: c, diff: Math.round((d - c) * 100) / 100 };
  }, [lines]);

  // KN-D22 — gerbang "seimbang" juga menolak baris yang mengisi debit DAN kredit sekaligus
  // (server menolaknya per baris; dulu layar meloloskannya karena hanya membanding total kolom).
  const twoSidedLines = lines.filter((l) => (Number(l.debit) || 0) > 0 && (Number(l.credit) || 0) > 0).length;
  const balanced = Math.abs(totals.diff) < 0.01 && totals.debit > 0 && twoSidedLines === 0;

  const setLine = (i, patch) => setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  const addLine = () => setLines((prev) => [...prev, emptyLine()]);
  const removeLine = (i) => setLines((prev) => (prev.length > 2 ? prev.filter((_, idx) => idx !== i) : prev));

  const submit = async () => {
    setError("");
    if (twoSidedLines > 0) { setError("Satu baris tidak boleh berisi debit dan kredit sekaligus — pisahkan menjadi dua baris."); return; }
    if (!balanced) { setError("Jurnal belum seimbang (total debit harus sama dengan kredit dan > 0)."); return; }
    const payloadLines = lines
      .filter((l) => l.account_code && (Number(l.debit) > 0 || Number(l.credit) > 0))
      .map((l) => ({ account_code: l.account_code, debit: Number(l.debit) || 0, credit: Number(l.credit) || 0, description: l.description }));
    if (payloadLines.length < 2) { setError("Minimal 2 baris terisi (debit & kredit)."); return; }
    setSaving(true);
    try {
      await axios.post(`${API}/gl/journal`, { date, description, lines: payloadLines });
      await onSaved();
    } catch (err) {
      setError(apiErrorText(err, "Gagal menyimpan jurnal."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <FormModal open onClose={onClose} title="Jurnal Manual Baru" icon={Scale} size="lg"
      testId="je-modal" busy={saving}
      footer={(
        <div className="flex items-center justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose} disabled={saving}>Batal</button>
          <button type="button" data-testid="je-submit" className="primary-button" onClick={submit}
            disabled={saving || !balanced}>{saving ? "Menyimpan..." : "Posting Jurnal"}</button>
        </div>
      )}>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-3">
        <div>
          <label className="text-[10px] font-bold uppercase text-[#8E8E93]">Tanggal</label>
          <KNDatePicker data-testid="je-date" className="text-[12px]" clearable={false} value={date} onChange={setDate} />
        </div>
        <div className="md:col-span-2">
          <label className="text-[10px] font-bold uppercase text-[#8E8E93]">Keterangan</label>
          <input data-testid="je-description" className="field py-1.5 text-[12px]" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="mis. Penyesuaian beban sewa" />
        </div>
      </div>

      {periodWarning && (
        <div data-testid="je-period-warning" className="mb-3 rounded-md bg-[#FDF3E7] border border-[#F5D9A8] text-[#B26B00] text-[12px] px-3 py-2 flex items-center gap-2">
          <AlertTriangle size={14} />
          Perhatian: periode <b>{periodWarning.period_label}</b> sudah ditutup. Jurnal tetap dapat diposting, namun sebaiknya buka kembali (reopen) periode bila ini koreksi resmi.
        </div>
      )}

      <div className="overflow-x-auto rounded-md border border-[#EFF0F2]">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="text-left text-[10px] font-bold uppercase text-[#8E8E93] bg-[#FAFBFC] border-b border-[#EFF0F2]">
              <th className="px-2 py-2 min-w-[220px]">Akun</th>
              <th className="px-2 py-2 text-right w-[140px]">Debit</th>
              <th className="px-2 py-2 text-right w-[140px]">Kredit</th>
              <th className="px-2 py-2 w-[40px]"></th>
            </tr>
          </thead>
          <tbody>
            {lines.map((l, i) => (
              <tr key={i} data-testid={`je-line-${i}`} className="border-b border-[#F5F5F7] last:border-0">
                <td className="px-2 py-1.5">
                  <KNSelect data-testid={`je-line-account-${i}`} className="field py-1 text-[12px]" value={l.account_code}
                    onValueChange={(v) => setLine(i, { account_code: v })} options={accountOptions} placeholder="Pilih akun" searchable />
                </td>
                <td className="px-2 py-1.5">
                  <input data-testid={`je-line-debit-${i}`} type="number" min="0" className="field py-1 text-[12px] tabular-nums text-right" value={l.debit}
                    onChange={(e) => setLine(i, { debit: e.target.value, credit: e.target.value ? "" : l.credit })} placeholder="0" />
                </td>
                <td className="px-2 py-1.5">
                  <input data-testid={`je-line-credit-${i}`} type="number" min="0" className="field py-1 text-[12px] tabular-nums text-right" value={l.credit}
                    onChange={(e) => setLine(i, { credit: e.target.value, debit: e.target.value ? "" : l.debit })} placeholder="0" />
                </td>
                <td className="px-2 py-1.5 text-center">
                  <button type="button" data-testid={`je-line-remove-${i}`} className="icon-button text-[#C0392B]" onClick={() => removeLine(i)} aria-label="Hapus baris" disabled={lines.length <= 2}><Trash2 size={13} /></button>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="bg-[#FAFBFC] border-t border-[#EFF0F2] font-semibold">
              <td className="px-2 py-2 text-right text-[11px] text-[#6B6B73]">Total</td>
              <td className="px-2 py-2 text-right tabular-nums" data-testid="je-total-debit">{formatCurrency(totals.debit)}</td>
              <td className="px-2 py-2 text-right tabular-nums" data-testid="je-total-credit">{formatCurrency(totals.credit)}</td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button type="button" data-testid="je-add-line" className="secondary-button" onClick={addLine}><Plus size={13} /> Tambah Baris</button>
        {/* G1-46 — jurnal masih kosong (Σ debit = Σ kredit = 0) tampil netral, bukan "Selisih Rp 0" merah. */}
        {(() => {
          const empty = !balanced && twoSidedLines === 0 && Math.abs(totals.diff) < 0.005;
          const cls = balanced ? "bg-[#E6F6EC] text-[#1B7F4B]" : empty ? "bg-[#F2F2F5] text-[#6B6B73]" : "bg-[#FDEDE7] text-[#C0392B]";
          return (
            <span data-testid="je-balance-indicator" className={`ml-auto text-[12px] font-semibold inline-flex items-center gap-1 rounded-full px-3 py-1 ${cls}`}>
              <Scale size={13} />{balanced ? "Seimbang" : twoSidedLines > 0 ? "Baris berisi debit & kredit" : empty ? "Belum ada nominal" : `Selisih ${formatCurrency(Math.abs(totals.diff))}`}
            </span>
          );
        })()}
      </div>

      {error && (
        <div className="mt-2">
          <ErrorNotice message={error} onDismiss={() => setError("")} testId="je-error" />
        </div>
      )}
    </FormModal>
  );
}
