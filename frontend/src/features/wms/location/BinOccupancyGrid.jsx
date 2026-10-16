import { Boxes } from "lucide-react";
import { fmtUnits, FUNCTION_LABEL } from "./locUtils";

function UtilBar({ util }) {
  if (util == null) return <span className="text-[11px] text-[#8E8E93]">kapasitas belum diatur</span>;
  const color = util > 100 ? "#C0341D" : util >= 90 ? "#E8590C" : util >= 70 ? "#FF9500" : "#34C759";
  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="flex-1 h-1.5 rounded-full bg-[#EFF0F2] overflow-hidden">
        <div className="h-full rounded-full transition-[width] duration-500" style={{ width: `${Math.min(util, 100)}%`, background: color }} />
      </div>
      <span className="text-[11px] tabular-nums" style={{ color }}>{util}%</span>
    </div>
  );
}

// Okupansi per bin: jumlah roll vs kapasitas roll; isi ditampilkan per satuan (tidak dijumlah lintas satuan).
export default function BinOccupancyGrid({ bins }) {
  if (!bins?.length) {
    return <div className="flex flex-col items-center gap-2 py-10 text-[12px] text-[#6B6B73]"><Boxes size={22} className="text-[#8E8E93]" />Belum ada bin.</div>;
  }
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2" data-testid="lp-bin-grid">
      {bins.map((b) => (
        <div key={b.bin_id} data-testid={`lp-bin-card-${b.bin_id}`} className="rounded-lg border border-[#EFF0F2] p-2 hover:border-[#C7D8F5] transition-colors">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[12px] font-mono font-semibold">{b.code || b.bin_id}</span>
            <span className="text-[10px] text-[#6B6B73] tabular-nums" data-testid={`lp-bin-card-count-${b.bin_id}`}>
              {b.roll_count || 0}{b.capacity_rolls ? ` / ${b.capacity_rolls}` : ""} roll
            </span>
          </div>
          <p className="text-[10px] text-[#8E8E93] mb-1 truncate" title={b.path}>{b.path}</p>
          <UtilBar util={b.utilization} />
          <div className="mt-1 flex flex-wrap items-center gap-1 text-[10px]">
            <span className="text-[#6B6B73]">{fmtUnits(b.occupied_by_unit)}</span>
            {b.mixed_units && <span className="rounded bg-[#FFF4E5] px-1 text-[#B45309]">satuan campur</span>}
            {b.function && b.function !== "storage" && <span className="rounded bg-[#EEF4FF] px-1 text-[#0058CC]">{FUNCTION_LABEL[b.function]}</span>}
            {b.single_lot ? <span className="rounded bg-[#F3E9FA] px-1 text-[#6B219A]">1 lot</span> : b.single_sku ? <span className="rounded bg-[#F3E9FA] px-1 text-[#6B219A]">1 SKU</span> : null}
          </div>
        </div>
      ))}
    </div>
  );
}
