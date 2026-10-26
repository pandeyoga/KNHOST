/**
 * FASE G-7 · US1 — modal **atur jadwal tukar faktur** satu supplier.
 *
 * INV-UI-03 aturan C: modal ini menulis lewat axios, jadi WAJIB punya bilah error
 * sendiri (bilah error layar induk berada di belakang lapisan modal).
 *
 * Fase 3 · P4 (L-03) — `.modal-card` buatan sendiri → `FormModal` baku (Esc/klik latar aman, kepala & tombol
 * Simpan menempel, layar penuh 1 kolom di HP). Isian tidak berubah.
 */
import { useMemo, useState } from "react";
import { CalendarClock } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import ErrorNotice from "../../../components/ErrorNotice";
import FormModal from "../../../components/FormModal";
import { KNSelect } from "../../../components/KNSelect";
import { apiErrorText } from "../../../utils/apiError";
import { fmtDate } from "./contraBonApi";

export default function ExchangeScheduleModal({ row, meta, onClose, onSaved, onError }) {
  const cur = row?.invoice_exchange || {};
  // Supplier yang BELUM punya jadwal datang dengan mode "none". Kalau nilai itu dipakai
  // sebagai isian awal, petugas menekan "Simpan" dan… tidak terjadi apa-apa yang terlihat:
  // jadwalnya tetap "belum dijadwalkan" dan nama PIC yang sudah diketik tidak pernah
  // tampil di tabel (terukur saat uji layar). Isian awal karena itu jatuh ke ritme yang
  // paling sering dipakai supplier tekstil — mingguan — dan "Tidak terjadwal" tetap bisa
  // dipilih sadar-sadar bila memang mau dilepas.
  const [mode, setMode] = useState(cur.mode && cur.mode !== "none" ? cur.mode : "weekly");
  const [weekday, setWeekday] = useState(String(cur.weekday ?? 1));
  const [dayOfMonth, setDayOfMonth] = useState(String(cur.day_of_month ?? 25));
  const [pic, setPic] = useState(cur.pic_name || "");
  const [notes, setNotes] = useState(cur.notes || "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const modeOptions = useMemo(
    () => (meta?.schedule_modes || []).map((m) => ({ value: m.value, label: m.label })), [meta]);
  const weekdayOptions = useMemo(
    () => (meta?.weekdays || []).map((w) => ({ value: String(w.value), label: w.label })), [meta]);

  async function save() {
    setSaving(true); setErr("");
    try {
      const r = await axios.put(`${API}/suppliers/${row.supplier_id}/invoice-exchange`, {
        mode,
        weekday: Number(weekday) || 0,
        day_of_month: Number(dayOfMonth) || 25,
        pic_name: pic.trim(),
        notes: notes.trim(),
      });
      onSaved(r.data);
    } catch (e) {
      setErr(apiErrorText(e));
      onError?.(e);
    } finally { setSaving(false); }
  }

  // Fase 3 · P4 — sengaja TANPA `onSubmit` (bukan <form>): tombol × di ErrorNotice tidak ber-`type`, jadi di
  // dalam <form> ia ikut mengirim. Aksi lewat `footer`.
  return (
    <FormModal open onClose={onClose} title="Jadwal tukar faktur" icon={CalendarClock}
      subtitle={`${row?.supplier_name || ""} — hari tetap supplier datang menukar faktur dengan tanda terima kita.`}
      testId="cb-exchange-modal" busy={saving}
      footer={(
        <div className="flex items-center justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose} disabled={saving}>Batal</button>
          <button type="button" className="primary-button" data-testid="cb-exchange-save"
            disabled={saving} onClick={save}>
            {saving ? "Menyimpan…" : "Simpan jadwal"}
          </button>
        </div>
      )}>
      {err && (
        <ErrorNotice message={err} onDismiss={() => setErr("")} testId="cb-exchange-error" />
      )}

      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Ritme siklus</label>
          <KNSelect data-testid="cb-exchange-mode" value={mode} onValueChange={setMode}
            options={modeOptions} className="field" />
        </div>

        {(mode === "weekly" || mode === "biweekly") && (
          <div>
            <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Hari</label>
            <KNSelect data-testid="cb-exchange-weekday" value={weekday}
              onValueChange={setWeekday} options={weekdayOptions} className="field" />
            <p className="mt-1 text-[10px] text-[#8E8E93]">
              {mode === "biweekly"
                ? "Dua pekan sekali dihitung dari tanggal acuan hari ini."
                : "Berulang setiap pekan pada hari ini."}
            </p>
          </div>
        )}

        {mode === "monthly" && (
          <div>
            <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">
              Tanggal dalam bulan (1–28)
            </label>
            <input data-testid="cb-exchange-dom" type="number" min={1} max={28}
              className="input-field w-full" value={dayOfMonth}
              onChange={(e) => setDayOfMonth(e.target.value)} />
            <p className="mt-1 text-[10px] text-[#8E8E93]">
              Dibatasi 28 supaya jadwal tidak pernah hilang di bulan Februari.
            </p>
          </div>
        )}

        <div>
          <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">
            PIC dari pihak supplier
          </label>
          <input data-testid="cb-exchange-pic" className="input-field w-full" value={pic}
            onChange={(e) => setPic(e.target.value)}
            placeholder="Nama orang yang biasa mengantar faktur" />
        </div>

        <div>
          <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Catatan</label>
          <textarea data-testid="cb-exchange-notes" className="textarea w-full" rows={2}
            value={notes} onChange={(e) => setNotes(e.target.value)}
            placeholder="Mis. datang pagi sebelum jam 11, bawa nota debit sekalian." />
        </div>

        {row?.next_exchange_date && (
          <p className="rounded-md bg-[#F2F7FF] px-2 py-1.5 text-[11px] text-[#1C1C1E]">
            Siklus tersimpan saat ini: <b>{row.schedule_label}</b> · berikutnya{" "}
            {fmtDate(row.next_exchange_date)}.
          </p>
        )}
      </div>
    </FormModal>
  );
}
