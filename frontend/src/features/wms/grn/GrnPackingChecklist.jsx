import { CheckCircle2, Circle } from "lucide-react";

/** Fase 6 — packing list = daftar centang roll yang diharapkan. Hitung buta: panjang tampil setelah roll diukur. */
export default function PackingChecklist({ ln, unit, picked, editable, onPick }) {
  const rows = ln.expected_rolls || [];
  const done = rows.filter((r) => r.status === "counted").length;
  const n = ln.line_no;
  return (
    <div data-testid={`grn-pl-list-${n}`} className="rounded-lg border border-[#E3E8F2] bg-[#F7F9FC] p-2">
      <div className="mb-1.5 flex items-center justify-between text-[10.5px]">
        <span className="font-bold uppercase tracking-wide text-[#3C3C43]">Packing list · roll diharapkan</span>
        <span data-testid={`grn-pl-progress-${n}`} className="font-semibold text-[#0058CC]">{done}/{rows.length} diukur</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {rows.map((r) => {
          const counted = r.status === "counted";
          const on = picked === r.seq;
          const bad = counted && r.diff != null && Math.abs(r.diff) > Math.max(0.5, (r.length || 0) * 0.01);
          return (
            <button key={r.seq} type="button" data-testid={`grn-pl-roll-${n}-${r.seq}`} disabled={counted || !editable}
              onClick={() => onPick(on ? null : r)}
              className={`flex min-w-[88px] flex-col items-start rounded-md border px-2 py-1 text-left text-[10.5px] transition-colors ${
                counted ? (bad ? "border-[#F1C4C1] bg-[#FDF1F0]" : "border-[#BFE5DC] bg-[#F0FAF7]") : on ? "border-[#0058CC] bg-white ring-2 ring-[#0058CC]/20" : "border-[#E5E5EA] bg-white hover:border-[#0058CC]"}`}>
              <span className="flex items-center gap-1 font-semibold">
                {counted ? <CheckCircle2 size={11} className={bad ? "text-[#B4231F]" : "text-[#0F766E]"} /> : <Circle size={11} className="text-[#8E8E93]" />}
                Roll #{r.seq}{r.lot ? ` · ${r.lot}` : ""}
              </span>
              {counted ? (
                <span data-testid={`grn-pl-result-${n}-${r.seq}`} className="font-mono tabular-nums">
                  {r.measured} {unit}{r.length != null ? ` / PL ${r.length}${r.length_unit ? ` ${r.length_unit}` : ""}` : ""}{r.diff ? ` (${r.diff > 0 ? "+" : ""}${r.diff})` : ""}
                </span>
              ) : <span className="text-[#8E8E93]">{on ? "ukur di bawah" : "belum diukur"}</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}
