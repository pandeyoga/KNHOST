import { useCallback, useEffect, useState } from "react";
import { CalendarClock, Loader2, Play, Trash2 } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Switch } from "../../components/ui/switch";
import { toast } from "../../hooks/use-toast";
import { deleteSchedule, fetchScheduleRuns, fetchSchedules, runScheduleNow, updateSchedule } from "./tanyaApi";
import { fmtDateTime, scheduleLabel } from "./tanyaFormat";

function ScheduleRow({ s, onChange, onRun, onDelete }) {
  const [busy, setBusy] = useState(false);
  const run = async () => { setBusy(true); try { await onRun(s); } finally { setBusy(false); } };
  return (
    <div className="tanya-sched" data-testid={`tanya-schedule-${s.id}`}>
      <div className="tanya-sched-head">
        <span className="tanya-tpl-title">{s.title}</span>
        <Switch checked={!!s.active} onCheckedChange={(v) => onChange(s, { active: v })} data-testid={`tanya-schedule-active-${s.id}`} />
      </div>
      <span className="tanya-tpl-prompt">{scheduleLabel(s)}</span>
      <span className="tanya-tpl-prompt">
        {s.active ? `Berikutnya ${fmtDateTime(s.next_run_at)}` : "Dijeda"}
        {s.last_run_at ? ` · terakhir ${fmtDateTime(s.last_run_at)} (${s.last_status === "ok" ? "berhasil" : "gagal"})` : ""}
      </span>
      {s.last_status === "error" && s.last_error && <span className="tanya-sched-err" data-testid={`tanya-schedule-error-${s.id}`}>{s.last_error}</span>}
      <div className="tanya-sched-actions">
        <Button size="sm" variant="outline" onClick={run} disabled={busy} data-testid={`tanya-schedule-run-${s.id}`}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Jalankan sekarang
        </Button>
        <Button size="sm" variant="ghost" onClick={() => onDelete(s)} aria-label="Hapus jadwal" data-testid={`tanya-schedule-delete-${s.id}`}><Trash2 className="h-4 w-4" /></Button>
      </div>
    </div>
  );
}

/** Kelola laporan terjadwal + riwayat kiriman (buka laporan lengkap). */
export function TanyaSchedules({ refreshKey, onOpenRun }) {
  const [items, setItems] = useState(null);
  const [runs, setRuns] = useState([]);
  const load = useCallback(() => {
    fetchSchedules().then(setItems).catch(() => setItems([]));
    fetchScheduleRuns().then(setRuns).catch(() => setRuns([]));
  }, []);
  useEffect(load, [load, refreshKey]);
  const change = async (s, body) => {
    try { await updateSchedule(s.id, body); load(); }
    catch (e) { toast({ title: "Jadwal gagal diubah", description: e?.response?.data?.detail || "", variant: "destructive" }); }
  };
  const run = async (s) => {
    const r = await runScheduleNow(s.id).catch(() => null);
    load();
    if (r?.status === "ok") { toast({ title: "Laporan dikirim ke notifikasi" }); onOpenRun(r.id); }
    else toast({ title: "Laporan gagal dijalankan", description: r?.error || "", variant: "destructive" });
  };
  const remove = async (s) => {
    await deleteSchedule(s.id).catch(() => null);
    toast({ title: "Jadwal dihapus" });
    load();
  };
  return (
    <div className="tanya-schedules" data-testid="tanya-schedules">
      {items === null && <div className="tanya-loading"><Loader2 className="h-4 w-4 animate-spin" /> Memuat jadwal…</div>}
      {items?.length === 0 && (
        <div className="tanya-note" data-testid="tanya-schedules-empty">
          <CalendarClock className="h-4 w-4 inline" /> Belum ada jadwal. Buka laporan di tab Laporan, lalu tekan &ldquo;Jadwalkan&rdquo;.
        </div>
      )}
      {items?.map((s) => <ScheduleRow key={s.id} s={s} onChange={change} onRun={run} onDelete={remove} />)}
      {runs.length > 0 && <div className="tanya-group-title">Kiriman terakhir</div>}
      {runs.slice(0, 10).map((r) => (
        <button key={r.id} type="button" className="tanya-tpl" onClick={() => onOpenRun(r.id)} disabled={r.status !== "ok"} data-testid={`tanya-run-${r.id}`}>
          <span>
            <span className="tanya-tpl-title">{r.title}</span>
            <span className="tanya-tpl-prompt">{fmtDateTime(r.created_at)} · {r.status === "ok" ? (r.trigger === "manual" ? "manual" : "terjadwal") : `gagal: ${r.error || ""}`}</span>
          </span>
        </button>
      ))}
    </div>
  );
}
