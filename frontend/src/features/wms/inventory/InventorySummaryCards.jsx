/** InventorySummaryCards — KPI row for the Stock tab.
 *  UAT 24 Okt (audit UI 051) — total PER SATUAN ({ kg: …, yard: … }); kg dan yard tidak pernah dijumlahkan
 *  (dulu "TERSEDIA 1.376.497,37" = kg + yard tanpa satuan). */
import { Layers, TrendingUp, TrendingDown, AlertTriangle } from "lucide-react";
import { formatQty } from "./inventoryConstants";

function UnitLines({ byUnit }) {
  const parts = Object.entries(byUnit || {})
    .filter(([, q]) => Math.abs(Number(q) || 0) > 0.0001)
    .sort(([a], [b]) => a.localeCompare(b));
  if (!parts.length) return <span>0</span>;
  return parts.map(([unit, qty]) => (
    <span key={unit} className="block">{formatQty(qty)} <span className="text-[11px] font-semibold">{unit}</span></span>
  ));
}

export default function InventorySummaryCards({ onHandByUnit, availByUnit, reservedByUnit, lowCount }) {
  const cards = [
    { label: "Total Stok Fisik", value: <UnitLines byUnit={onHandByUnit} />,   icon: Layers,        color: "text-[#007AFF]", bg: "bg-[#EFF4FF]" },
    { label: "Tersedia",     value: <UnitLines byUnit={availByUnit} />,    icon: TrendingUp,    color: "text-[#34C759]", bg: "bg-green-50" },
    { label: "Dipesan",      value: <UnitLines byUnit={reservedByUnit} />, icon: TrendingDown,  color: "text-[#FF9500]", bg: "bg-orange-50" },
    { label: "Stok Rendah",   value: lowCount, icon: AlertTriangle, color: "text-red-500",   bg: "bg-red-50" },
  ];
  return (
    <div data-testid="inventory-summary-cards" className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {cards.map(({ label, value, icon: Icon, color, bg }) => (
        <div key={label} data-testid={`summary-card-${label.toLowerCase().replace(/\s+/g, "-")}`} className={`rounded-xl border border-[#EFF0F2] p-3 flex items-center gap-2.5 ${bg}`}>
          <div className={`rounded-lg p-1.5 ${bg}`}>
            <Icon size={16} className={color} />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] text-[#6B6B73] font-semibold uppercase">{label}</p>
            <p className={`text-[16px] font-bold leading-tight tabular-nums ${color}`}>{value}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
