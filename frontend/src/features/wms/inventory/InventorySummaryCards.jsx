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

// K-04 (keputusan pemilik 26 Okt) — `lowHint` menyebut cakupan "Stok Rendah" (definisi tunggal server, per produk),
// `availHint` definisi "Tersedia" (tooltip) supaya angka beda cakupan tidak dibaca sebagai angka yang sama.
export default function InventorySummaryCards({ onHandByUnit, availByUnit, reservedByUnit, lowCount, lowHint = "", availHint = "" }) {
  // Fase 4 · R3 (L-06/L-08) — kartu KPI tab Stok memakai gaya `metric-card` baku (dulu latar hijau/oranye/merah per kartu
  // dan angka berwarna — termasuk "0" merah). Nilai 0 netral; satuan tetap satu baris per satuan (tidak dijumlahkan).
  const isZero = (byUnit) => !Object.values(byUnit || {}).some((q) => Math.abs(Number(q) || 0) > 0.0001);
  const cards = [
    { label: "Total Stok Fisik", value: <UnitLines byUnit={onHandByUnit} />, icon: Layers, zero: isZero(onHandByUnit) },
    { label: "Tersedia", value: <UnitLines byUnit={availByUnit} />, icon: TrendingUp, title: availHint, zero: isZero(availByUnit) },
    { label: "Dipesan", value: <UnitLines byUnit={reservedByUnit} />, icon: TrendingDown, zero: isZero(reservedByUnit) },
    { label: "Stok Rendah", value: lowCount, icon: AlertTriangle, hint: lowHint, zero: !Number(lowCount) },
  ];
  return (
    <div data-testid="inventory-summary-cards" className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {cards.map(({ label, value, icon: Icon, hint, title, zero }) => (
        <div key={label} data-testid={`summary-card-${label.toLowerCase().replace(/\s+/g, "-")}`} title={title || undefined}
          className="metric-card !cursor-default !items-start">
          <div className="metric-icon"><Icon size={16} /></div>
          <div className="metric-body">
            <div className="metric-label">{label}</div>
            <div className={`metric-value tabular-nums !text-[16px] leading-tight ${zero ? "metric-zero" : ""}`.trim()}>{value}</div>
            {hint && <p className="text-[10px] leading-tight text-[#6B6B73]" data-testid="summary-card-hint">{hint}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}
