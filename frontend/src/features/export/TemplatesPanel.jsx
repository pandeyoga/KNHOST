import { useEffect, useState } from "react";
import { Play, Trash2, FolderOpen, CalendarClock } from "lucide-react";
import ScheduleForm, { scheduleLabel } from "./ScheduleForm";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";

const errText = (e) => e.response?.data?.detail?.message || e.response?.data?.detail || e.message;

export default function TemplatesPanel({ onUse, onRan, refreshKey }) {
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState("");
  const [editing, setEditing] = useState("");
  const load = () => axios.get(`${API}/export-center/templates`).then((r) => setItems(r.data.items || [])).catch((e) => setError(errText(e)));
  useEffect(() => { load(); }, [refreshKey]); // eslint-disable-line

  const run = async (t) => {
    setError(null); setMsg("");
    try {
      const r = await axios.post(`${API}/export-center/templates/${t.id}/run`);
      setMsg(`“${t.name}” dijalankan: ${r.data.total_rows.toLocaleString("id-ID")} baris — lihat tab Pekerjaan.`);
      load(); onRan?.();
    } catch (e) { setError(errText(e)); }
  };
  const runSchedule = async (t) => {
    setError(null); setMsg("");
    try {
      const r = await axios.post(`${API}/export-center/templates/${t.id}/schedule/run-now`);
      setMsg(`Uji jadwal “${t.name}”: ${r.data.total_rows.toLocaleString("id-ID")} baris (${r.data.date_text}).`);
      load(); onRan?.();
    } catch (e) { setError(errText(e)); load(); }
  };
  const remove = async (t) => {
    setError(null);
    try { await axios.delete(`${API}/export-center/templates/${t.id}`); load(); } catch (e) { setError(errText(e)); }
  };

  return (
    <div data-testid="export-templates-panel" className="rounded-xl border border-[#EFF0F2] bg-white p-4 space-y-3">
      <div>
        <h3 className="text-[13px] font-bold text-[#1C1C1E]">Template export saya</h3>
        <p className="text-[12px] text-[#6B6B73]">Simpan pilihan dataset, kolom, periode, filter dan urutan, lalu jalankan sekali klik. Hak akses diperiksa ulang setiap dijalankan.</p>
      </div>
      {error && <ErrorNotice message={error} onDismiss={() => setError(null)} testId="export-templates-error" />}
      {msg && <p data-testid="export-templates-notice" className="rounded-lg bg-[#34C759]/10 text-[#1E7B3A] text-[12.5px] px-3 py-2">{msg}</p>}
      {!items.length && <p className="text-[12px] text-[#8E8E93]">Belum ada template. Buat dari tab “Buat export” → “Simpan template”.</p>}
      <div className="divide-y divide-[#F0F0F3]">
        {items.map((t) => (
          <div key={t.id} data-testid={`export-template-${t.id}`} className="py-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px]">
            <span className="font-semibold text-[#1C1C1E]">{t.name}</span>
            <span className="text-[#6B6B73]">{t.dataset_label}</span>
            <span className="uppercase text-[10.5px] font-bold text-[#6B6B73]">{t.format}</span>
            <span className="text-[#8E8E93]">{t.spec?.columns?.length || 0} kolom · dipakai {t.run_count || 0}×</span>
            {t.schedule && (
              <span data-testid={`export-template-schedule-${t.id}`} className="inline-flex items-center gap-1 text-[#0058CC]">
                <CalendarClock size={12} /> {scheduleLabel(t.schedule)}
                {t.schedule.active && t.schedule.next_run_at && ` · berikutnya ${new Date(t.schedule.next_run_at).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" })}`}
              </span>
            )}
            <span className="ml-auto flex items-center gap-3">
              <button type="button" data-testid={`export-template-schedule-edit-${t.id}`} onClick={() => setEditing(editing === t.id ? "" : t.id)}
                      className="inline-flex items-center gap-1 text-[#0058CC] font-semibold"><CalendarClock size={12} /> {t.schedule ? "Ubah jadwal" : "Jadwalkan"}</button>
              {t.schedule && <button type="button" data-testid={`export-template-schedule-test-${t.id}`} onClick={() => runSchedule(t)}
                      className="text-[#0058CC] font-semibold">Uji jadwal</button>}
              <button type="button" data-testid={`export-template-run-${t.id}`} onClick={() => run(t)}
                      className="inline-flex items-center gap-1 rounded-full bg-[#0058CC] text-white px-3 py-1 font-semibold"><Play size={12} /> Export sekarang</button>
              <button type="button" data-testid={`export-template-use-${t.id}`} onClick={() => onUse(t)}
                      className="inline-flex items-center gap-1 text-[#0058CC] font-semibold"><FolderOpen size={12} /> Buka</button>
              <button type="button" data-testid={`export-template-delete-${t.id}`} onClick={() => remove(t)}
                      className="inline-flex items-center gap-1 text-[#C0341D] font-semibold"><Trash2 size={12} /> Hapus</button>
            </span>
            {t.last_schedule_error && <p className="w-full text-[11.5px] text-[#C0341D]" data-testid={`export-template-schedule-error-${t.id}`}>Jadwal terakhir gagal: {t.last_schedule_error}</p>}
            {editing === t.id && <ScheduleForm tpl={t} onCancel={() => setEditing("")} onSaved={() => { setEditing(""); setMsg(`Jadwal “${t.name}” tersimpan.`); load(); }} />}
          </div>
        ))}
      </div>
    </div>
  );
}
