import { useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import KNSelect from "../../../components/KNSelect";
import { FUNCTION_OPTIONS, ruleSummary } from "./locUtils";
import useDomainEnums from "../../../hooks/useDomainEnums";
const FABRICS = ["woven", "knit"];

// Fungsi area + rules satu node. Rules anak digabung AND dengan induk (tidak bisa membuka larangan induk).
export default function NodeRulesEditor({ node, onChange, testId }) {
  const [open, setOpen] = useState(false);
  const r = node.rules || {};
  const { options } = useDomainEnums();
  const active = options("grade").map((o) => o.value);
  const GRADES = [...active, ...(r.grades || []).filter((g) => !active.includes(g))];
  const set = (patch) => onChange({ ...node, rules: { ...r, ...patch } });
  const toggle = (key, v) => {
    const cur = r[key] || [];
    set({ [key]: cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v] });
  };
  const summary = ruleSummary(r);
  return (
    <div className="inline-flex flex-col">
      <button type="button" data-testid={`${testId}-rules-toggle`} onClick={() => setOpen(!open)}
        className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10.5px] font-semibold transition-colors ${
          summary || node.function ? "bg-[#EEF4FF] text-[#0058CC]" : "text-[#8E8E93] hover:bg-[#F5F5F7]"}`}>
        <SlidersHorizontal size={11} /> {node.function === "qc" ? "QC · " : ""}{summary || (node.function ? "" : "Aturan")}
      </button>
      {open && (
        <div data-testid={`${testId}-rules-panel`} className="mt-1 w-[300px] rounded-lg border border-[#E5E5EA] bg-white p-2.5 shadow-lg space-y-2 z-10">
          <label className="block text-[10px] font-semibold uppercase text-[#6B6B73]">Fungsi area
            <KNSelect data-testid={`${testId}-function`} value={node.function || ""} options={FUNCTION_OPTIONS}
              onValueChange={(v) => onChange({ ...node, function: v })} className="field !py-1 text-[11px] mt-0.5" />
          </label>
          <label className="block text-[10px] font-semibold uppercase text-[#6B6B73]">Kategori boleh (pisah koma)
            <input data-testid={`${testId}-categories`} defaultValue={(r.categories || []).join(", ")}
              onBlur={(e) => set({ categories: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) })}
              placeholder="Kosong = semua" className="mt-0.5 w-full rounded border border-[#E5E5EA] px-1.5 py-1 text-[11px] normal-case" />
          </label>
          <Chips label="Grade boleh" items={GRADES} active={r.grades || []} onToggle={(g) => toggle("grades", g)} testId={`${testId}-grade`} />
          <Chips label="Jenis kain boleh" items={FABRICS} active={r.fabric_types || []} onToggle={(f) => toggle("fabric_types", f)} testId={`${testId}-fabric`} />
          <div className="flex gap-3 text-[11px]">
            <label className="flex items-center gap-1"><input type="checkbox" data-testid={`${testId}-single-sku`} checked={!!r.single_sku} onChange={(e) => set({ single_sku: e.target.checked })} /> 1 SKU per bin</label>
            <label className="flex items-center gap-1"><input type="checkbox" data-testid={`${testId}-single-lot`} checked={!!r.single_lot} onChange={(e) => set({ single_lot: e.target.checked })} /> 1 lot per bin</label>
          </div>
          <p className="text-[10px] text-[#8E8E93]">Berlaku juga untuk semua isi di bawahnya, digabung dengan aturan induk.</p>
        </div>
      )}
    </div>
  );
}

function Chips({ label, items, active, onToggle, testId }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase text-[#6B6B73]">{label}</p>
      <div className="mt-0.5 flex flex-wrap gap-1">
        {items.map((g) => (
          <button key={g} type="button" data-testid={`${testId}-${g}`} onClick={() => onToggle(g)}
            className={`rounded border px-2 py-0.5 text-[11px] font-semibold ${active.includes(g) ? "border-[#0058CC] bg-[#EEF4FF] text-[#0058CC]" : "border-[#E5E5EA] text-[#6B6B73]"}`}>{g}</button>
        ))}
      </div>
    </div>
  );
}
