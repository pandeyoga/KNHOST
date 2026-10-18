import { useState } from "react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";

const DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"];
const errText = (e) => e.response?.data?.detail?.message || e.response?.data?.detail || e.message;

export function scheduleLabel(s) {
  if (!s) return "";
  const when = s.frequency === "weekly" ? `tiap ${DAYS[s.weekday || 0]}` : `tiap tanggal ${s.day_of_month}`;
  return `${s.active ? "" : "(nonaktif) "}${when} ${s.time} WIB · ${s.period === "previous" ? (s.frequency === "weekly" ? "minggu lalu" : "bulan lalu") : "periode tersimpan"}`;
}

export default function ScheduleForm({ tpl, onSaved, onCancel }) {
  const s = tpl.schedule || {};
  const [f, setF] = useState({ active: s.active ?? true, frequency: s.frequency || "monthly", weekday: s.weekday ?? 0,
    day_of_month: s.day_of_month || 1, time: s.time || "07:00", period: s.period || "previous" });
  const [err, setErr] = useState("");
  const save = async () => {
    setErr("");
    try { await axios.put(`${API}/export-center/templates/${tpl.id}/schedule`, { ...f, day_of_month: Number(f.day_of_month) || 1 }); onSaved(); }
    catch (e) { setErr(errText(e)); }
  };
  return (
    <div data-testid={`export-schedule-form-${tpl.id}`} className="w-full mt-2 rounded-lg border border-[#E5E5EA] bg-[#FAFAFB] p-3 flex flex-wrap items-end gap-2 text-[12px]">
      <div className="w-36 flex flex-col gap-1">Frekuensi
        <KNSelect data-testid="export-schedule-frequency" value={f.frequency} searchable={false}
          options={[{ value: "weekly", label: "Mingguan" }, { value: "monthly", label: "Bulanan" }]} onValueChange={(v) => setF({ ...f, frequency: v })} /></div>
      {f.frequency === "weekly"
        ? <div className="w-32 flex flex-col gap-1">Hari
            <KNSelect data-testid="export-schedule-weekday" value={String(f.weekday)} searchable={false}
              options={DAYS.map((d, i) => ({ value: String(i), label: d }))} onValueChange={(v) => setF({ ...f, weekday: Number(v) })} /></div>
        : <label className="flex flex-col gap-1">Tanggal (1–28)
            <input data-testid="export-schedule-day" type="number" min={1} max={28} value={f.day_of_month}
                   onChange={(e) => setF({ ...f, day_of_month: e.target.value })} className="field w-20" /></label>}
      <label className="flex flex-col gap-1">Jam (WIB)
        <input data-testid="export-schedule-time" value={f.time} placeholder="07:00" onChange={(e) => setF({ ...f, time: e.target.value })} className="field w-20" /></label>
      <div className="w-56 flex flex-col gap-1">Periode data
        <KNSelect data-testid="export-schedule-period" value={f.period} searchable={false}
          options={[{ value: "previous", label: f.frequency === "weekly" ? "Minggu lalu (Sen–Min)" : "Bulan lalu penuh" },
                    { value: "as_saved", label: "Sesuai periode tersimpan" }]} onValueChange={(v) => setF({ ...f, period: v })} /></div>
      <label className="flex items-center gap-1.5"><input data-testid="export-schedule-active" type="checkbox" checked={f.active}
             onChange={(e) => setF({ ...f, active: e.target.checked })} /> Aktif</label>
      <button type="button" data-testid="export-schedule-save" onClick={save} className="rounded-full bg-[#0058CC] text-white px-4 py-1.5 font-semibold">Simpan jadwal</button>
      <button type="button" data-testid="export-schedule-cancel" onClick={onCancel} className="text-[#6B6B73] font-semibold">Batal</button>
      {err && <p className="w-full text-[#C0341D]" data-testid="export-schedule-error">{err}</p>}
      <p className="w-full text-[11px] text-[#8E8E93]">Dijalankan dengan hak akses Anda saat jadwal tiba (izin dicabut → tidak berjalan). File siap di tab Pekerjaan dan Anda menerima notifikasi.</p>
    </div>
  );
}
