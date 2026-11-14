/**
 * JournalEntryModal (EPIC7-C) — buat jurnal manual double-entry seimbang.
 * Dipakai oleh GeneralLedger. Validasi balance di sisi klien + server.
 *
 * Fase 4 · R2 (L-03) — `div fixed inset-0` buatan sendiri → `FormModal` baku (Esc/klik latar seragam, kepala &
 * kaki menempel, layar penuh di HP). Isian & testid tetap (`je-modal`, `je-modal-close`, `je-submit`, `je-error`).
 *
 * PK-16 (UX-07) — kepala pop-up menyebut buku PT tujuan ("Dicatat di buku …", PT di kepala aplikasi); mode Semua PT
 * → "hanya untuk melihat". Banner = `subtitle` FormModal supaya ikut menempel saat isi digulir.
 *
 * PK-36 (IC-06) — pilihan akun tanpa akun kontrol yang ditolak pengaturan PT (`manual_allowed === false`) + kalimat
 * keterangan di bawah tabel baris (hanya bila ada akun yang disembunyikan).
 *
 * PK-42 — (UX-11) pita periode tertutup mengatakan yang sebenarnya: server MENOLAK jurnal ke periode tertutup
 * (`gl_service.enforce_closed_period_guard`) kecuali ada jendela Buka Periode; dulu "tetap dapat diposting". Pita merah +
 * tautan "Ajukan Buka Periode" (hanya bila layar itu boleh dibuka). (UX-18) Debit/Kredit = `MoneyInput` (pratinjau
 * "Rp 1.250.000"); nilai yang dikirim tetap angka.
 */
import { apiErrorText } from "../../utils/apiError";
import KNDatePicker from "@/components/KNDatePicker";
import { useEffect, useMemo, useState } from "react";
import { Plus, Trash2, Scale, AlertTriangle, ArrowRight } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import FormModal from "../../components/FormModal";
import { formatCurrency, todayWib } from "../../utils/formatters";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyPost } from "../../utils/moneyRequest";
import EntityScopeBanner from "../../components/EntityScopeBanner";
import MoneyInput from "../../components/MoneyInput";
import { parseDecimal } from "../../utils/decimalInput";
import { useAppNav } from "../../context/AppNavContext";

// PK-42 — nilai isian rupiah (teks `MoneyInput`, koma desimal boleh) → angka; kosong/tak sah → 0.
const amt = (v) => { const n = parseDecimal(v); return Number.isFinite(n) ? n : 0; };

const emptyLine = () => ({ account_code: "", debit: "", credit: "", description: "" });

export default function JournalEntryModal({ accounts, onClose, onSaved }) {
  const today = todayWib();
  const [date, setDate] = useState(today);
  const [description, setDescription] = useState("");
  const [lines, setLines] = useState([emptyLine(), emptyLine()]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [periodWarning, setPeriodWarning] = useState(null);
  // PK-12 — kirim ulang isi yang sama (koneksi putus) memakai kunci yang sama → server memutar ulang, bukan jurnal kedua.
  const intent = useIntentKey("je");
  const { go, canOpen } = useAppNav();

  // Periode tertutup: server menolak jurnal bertanggal di dalamnya (kecuali jendela Buka Periode) — beri tahu sebelum
  // pengguna menekan Posting.
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

  // PK-36 (IC-06) — akun kontrol (piutang, hutang, persediaan, antar-PT) tidak ditawarkan bila pengaturan PT menolak
  // jurnal manual ke akun itu (`manual_allowed` dari server; server tetap menolak dengan 422).
  const usable = useMemo(() => accounts.filter((a) => a.is_postable && a.is_active !== false), [accounts]);
  const accountOptions = useMemo(
    () => usable.filter((a) => a.manual_allowed !== false)
      .map((a) => ({ value: a.code, label: `${a.code} — ${a.name}` })),
    [usable]);
  const hiddenControl = usable.some((a) => a.manual_allowed === false);

  const totals = useMemo(() => {
    const d = lines.reduce((s, l) => s + amt(l.debit), 0);
    const c = lines.reduce((s, l) => s + amt(l.credit), 0);
    return { debit: d, credit: c, diff: Math.round((d - c) * 100) / 100 };
  }, [lines]);

  // KN-D22 — gerbang "seimbang" juga menolak baris yang mengisi debit DAN kredit sekaligus
  // (server menolaknya per baris; dulu layar meloloskannya karena hanya membanding total kolom).
  const twoSidedLines = lines.filter((l) => amt(l.debit) > 0 && amt(l.credit) > 0).length;
  const balanced = Math.abs(totals.diff) < 0.01 && totals.debit > 0 && twoSidedLines === 0;

  const setLine = (i, patch) => setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  const addLine = () => setLines((prev) => [...prev, emptyLine()]);
  const removeLine = (i) => setLines((prev) => (prev.length > 2 ? prev.filter((_, idx) => idx !== i) : prev));

  const submit = async () => {
    setError("");
    if (twoSidedLines > 0) { setError("Satu baris tidak boleh berisi debit dan kredit sekaligus — pisahkan menjadi dua baris."); return; }
    if (!balanced) { setError("Jurnal belum seimbang (total debit harus sama dengan kredit dan > 0)."); return; }
    const payloadLines = lines
      .filter((l) => l.account_code && (amt(l.debit) > 0 || amt(l.credit) > 0))
      .map((l) => ({ account_code: l.account_code, debit: amt(l.debit), credit: amt(l.credit), description: l.description }));
    if (payloadLines.length < 2) { setError("Minimal 2 baris terisi (debit & kredit)."); return; }
    setSaving(true);
    try {
      const body = { date, description, lines: payloadLines };
      const res = await intent.send(body, (k) => moneyPost(`${API}/gl/journal`, body, k));
      await onSaved(res?.data);   // KF-T6 — 202 `menunggu_orang_kedua` = usulan, belum diposting
    } catch (err) {
      setError(apiErrorText(err, "Gagal menyimpan jurnal."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <FormModal open onClose={onClose} title="Jurnal Manual Baru" icon={Scale} size="lg"
      subtitle={<EntityScopeBanner variant="form" testId="je-scope" className="mt-1" />}
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
          <label className="field-label">Tanggal</label>
          <KNDatePicker data-testid="je-date" className="text-[12px]" clearable={false} value={date} onChange={setDate} />
        </div>
        <div className="md:col-span-2">
          <label className="field-label">Keterangan</label>
          <input data-testid="je-description" className="field py-1.5 text-[12px]" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="mis. Penyesuaian beban sewa" />
        </div>
      </div>

      {periodWarning && (
        <div data-testid="je-period-warning" role="alert"
          className="mb-3 flex flex-wrap items-start gap-x-2 gap-y-1 rounded-md border border-kn-danger bg-kn-danger-soft px-3 py-2 text-fs-12 text-kn-danger-text">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span className="min-w-0 flex-1">
            Periode <b>{periodWarning.period_label}</b> sudah ditutup. Jurnal bertanggal ini akan ditolak, kecuali ada izin
            Buka Periode yang masih berlaku. Ganti tanggalnya, atau ajukan Buka Periode.
          </span>
          {canOpen("period-unlock") && (
            <button type="button" className="link-button font-semibold" data-testid="je-period-unlock-link"
              onClick={() => go("period-unlock")}>
              Ajukan Buka Periode <ArrowRight size={12} aria-hidden="true" />
            </button>
          )}
        </div>
      )}

      <div className="overflow-x-auto rounded-md border border-[#EFF0F2]">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="text-left text-fs-12 font-bold uppercase text-kn-text-2 bg-[#FAFBFC] border-b border-[#EFF0F2]">
              <th className="px-2 py-2 min-w-[220px]">Akun</th>
              <th className="px-2 py-2 text-right w-[160px]">Debit</th>
              <th className="px-2 py-2 text-right w-[160px]">Kredit</th>
              <th className="px-2 py-2 w-[40px]"></th>
            </tr>
          </thead>
          <tbody>
            {lines.map((l, i) => (
              <tr key={i} data-testid={`je-line-${i}`} className="border-b border-[#F5F5F7] last:border-0">
                <td className="px-2 py-1.5 align-top">
                  <KNSelect data-testid={`je-line-account-${i}`} className="field py-1 text-[12px]" value={l.account_code}
                    onValueChange={(v) => setLine(i, { account_code: v })} options={accountOptions} placeholder="Pilih akun" searchable />
                </td>
                <td className="px-2 py-1.5 align-top">
                  <MoneyInput testId={`je-line-debit-${i}`} className="field py-1 text-fs-13 text-right" value={l.debit}
                    aria-label={`Debit baris ${i + 1}`}
                    onChange={(v) => setLine(i, { debit: v, credit: v ? "" : l.credit })} placeholder="0" />
                </td>
                <td className="px-2 py-1.5 align-top">
                  <MoneyInput testId={`je-line-credit-${i}`} className="field py-1 text-fs-13 text-right" value={l.credit}
                    aria-label={`Kredit baris ${i + 1}`}
                    onChange={(v) => setLine(i, { credit: v, debit: v ? "" : l.debit })} placeholder="0" />
                </td>
                <td className="px-2 py-1.5 text-center align-top">
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

      {hiddenControl && (
        <p data-testid="je-control-note" className="mt-2 text-fs-12 text-kn-text-2">
          Akun piutang, hutang, persediaan, dan antar-PT tidak ada di daftar ini karena saldonya dijaga dokumen. Koreksi
          lewat dokumennya.
        </p>
      )}

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
