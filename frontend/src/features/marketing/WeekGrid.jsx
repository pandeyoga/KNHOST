/** WeekGrid — tampilan mingguan kalender konten: 7 kolom Senin–Minggu, konten terurut jam tayang. */
import { useMemo, useState } from "react";
import { GripVertical, Plus } from "lucide-react";
import { dayKey, PlatformChip, StatusPill, weekDays } from "./marketingShared";

const DOW = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"];

export default function WeekGrid({ week, posts, multi, canCreate, onCreate, onOpen, onMove }) {
  const [dragId, setDragId] = useState("");
  const [overDay, setOverDay] = useState("");
  const movable = (p) => !!onMove && p.status !== "published";
  const drop = (day) => {
    const p = posts.find((x) => x.id === dragId);
    setDragId(""); setOverDay("");
    if (p && p.publish_at.slice(0, 10) !== day) onMove(p, day);
  };
  const days = weekDays(week);
  const today = dayKey(new Date());
  const byDay = useMemo(() => {
    const map = {};
    posts.filter((p) => p.publish_at).forEach((p) => { (map[p.publish_at.slice(0, 10)] ||= []).push(p); });
    Object.values(map).forEach((l) => l.sort((a, b) => a.publish_at.localeCompare(b.publish_at)));
    return map;
  }, [posts]);

  return (
    <div className="grid gap-1">
    {onMove && <p className="text-[10.5px] text-[#8E8E93]" data-testid="mkt-week-drag-hint">Seret kartu ke hari lain untuk memindah jadwal (jam tayang tetap). Konten yang sudah tayang tidak bisa dipindah.</p>}
    <div className="overflow-x-auto rounded-xl border border-[#E5E5EA] bg-white" data-testid="mkt-week-grid">
      <div className="grid min-w-[840px] grid-cols-7">
        {days.map((day, i) => (
          <div key={day} data-testid={`mkt-week-day-${day}`}
            onDragOver={(e) => { if (!dragId) return; e.preventDefault(); e.dataTransfer.dropEffect = "move"; setOverDay(day); }}
            onDragLeave={() => setOverDay((d) => (d === day ? "" : d))}
            onDrop={(e) => { e.preventDefault(); drop(day); }}
            className={`flex min-h-[320px] flex-col border-r border-[#F2F2F7] transition-colors last:border-r-0 ${overDay === day ? "bg-[#EEF4FF] ring-2 ring-inset ring-[#0058CC]/40" : day === today ? "bg-[#F8FAFF]" : ""}`}>
            <div className="flex items-center justify-between border-b border-[#EFF0F2] bg-[#FAFBFC] px-2 py-1.5">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">{DOW[i]}</p>
                <p className={`text-[15px] font-bold leading-none ${day === today ? "text-[#0058CC]" : "text-[#1C1C1E]"}`}>{Number(day.slice(8))}<span className="ml-1 text-[10px] font-semibold text-[#8E8E93]">{(byDay[day] || []).length || ""}</span></p>
              </div>
              {canCreate && <button type="button" onClick={() => onCreate(day)} className="rounded-full p-1 text-[#0058CC] hover:bg-[#EEF4FF]" title="Konten baru di hari ini" data-testid={`mkt-week-add-${day}`}><Plus size={13} /></button>}
            </div>
            <div className="grid content-start gap-1.5 p-1.5">
              {(byDay[day] || []).map((p) => (
                <button key={p.id} type="button" onClick={() => onOpen(p.id)} data-testid={`mkt-week-card-${p.id}`}
                  draggable={movable(p)} onDragStart={(e) => { e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", p.id); setDragId(p.id); }}
                  onDragEnd={() => { setDragId(""); setOverDay(""); }}
                  className={`grid gap-1 rounded-lg border border-[#EFF0F2] bg-white p-1.5 text-left shadow-[0_1px_0_rgba(0,0,0,0.02)] transition-[border-color,opacity] hover:border-[#0058CC] ${movable(p) ? "cursor-grab active:cursor-grabbing" : ""} ${dragId === p.id ? "opacity-40" : ""}`}>
                  <span className="flex items-center justify-between font-mono text-[10.5px] font-bold text-[#0058CC]">{p.publish_at.slice(11, 16)} WIB{movable(p) && <GripVertical size={11} className="text-[#C7C7CC]" />}</span>
                  <span className="line-clamp-2 text-[11.5px] font-semibold leading-snug">{p.title}</span>
                  <span className="flex flex-wrap gap-0.5">{(p.platforms || []).map((c) => <PlatformChip key={c} code={c} small />)}</span>
                  <span className="flex items-center justify-between gap-1">
                    <StatusPill status={p.status} />
                    <span className="truncate text-[9.5px] text-[#8E8E93]">{p.pic_name || "tanpa PIC"}</span>
                  </span>
                  {multi && p.entity_name && <span className="w-fit rounded bg-[#E0F2FE] px-1 text-[9px] font-bold text-[#0369A1]">{p.entity_name}</span>}
                </button>
              ))}
              {!(byDay[day] || []).length && <p className="py-4 text-center text-[10.5px] text-[#B5B5BC]">kosong</p>}
            </div>
          </div>
        ))}
      </div>
    </div>
    </div>
  );
}
