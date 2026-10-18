import { useMemo, useState } from "react";
import { Search, Database, Lock } from "lucide-react";

export default function DatasetPicker({ datasets, unavailable, value, onChange }) {
  const [q, setQ] = useState("");
  const groups = useMemo(() => {
    const term = q.trim().toLowerCase();
    const out = {};
    datasets
      .filter((d) => !term || `${d.label} ${d.group}`.toLowerCase().includes(term))
      .forEach((d) => { (out[d.group] = out[d.group] || []).push(d); });
    return out;
  }, [datasets, q]);

  return (
    <div data-testid="export-dataset-picker" className="rounded-xl border border-[#EFF0F2] bg-white p-3 space-y-3">
      <div className="relative">
        <Search size={14} className="absolute left-2.5 top-2.5 text-[#8E8E93]" />
        <input data-testid="export-dataset-search" value={q} onChange={(e) => setQ(e.target.value)}
               placeholder="Cari dataset…" className="field w-full pl-8 text-[12.5px]" />
      </div>
      {Object.entries(groups).map(([g, list]) => (
        <div key={g}>
          <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93] mb-1">{g}</p>
          <div className="space-y-0.5">
            {list.map((d) => (
              <button key={d.id} type="button" data-testid={`export-dataset-${d.id}`} onClick={() => onChange(d.id)}
                      className={`w-full text-left flex items-start gap-2 rounded-lg px-2 py-1.5 text-[12.5px] transition-colors ${
                        value === d.id ? "bg-[#0058CC]/10 text-[#0058CC] font-semibold" : "hover:bg-[#F5F5F7] text-[#1C1C1E]"}`}>
                <Database size={13} className="mt-0.5 shrink-0" />
                <span>{d.label}</span>
              </button>
            ))}
          </div>
        </div>
      ))}
      {unavailable.length > 0 && (
        <div data-testid="export-dataset-unavailable" className="border-t border-[#EFF0F2] pt-2">
          <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93] mb-1">Tidak tersedia untuk peran Anda</p>
          {unavailable.map((d) => (
            <p key={d.id} title={d.reason} className="flex items-center gap-1.5 text-[11.5px] text-[#8E8E93] py-0.5">
              <Lock size={11} /> {d.label}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
