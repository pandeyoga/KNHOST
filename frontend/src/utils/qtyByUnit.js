import { formatQty } from "./formatters";

// L02 LN-020-T03 — qty per satuan (yard dan kg tidak pernah dijumlahkan) + jumlah roll.
export function qtyByUnit(items = []) {
  const map = new Map();
  items.forEach((it) => {
    const unit = it.unit || "";
    const row = map.get(unit) || { unit, qty: 0, rolls: 0 };
    row.qty += Number(it.qty ?? it.quantity ?? 0);
    row.rolls += (it.roll_lines || []).length || Number(it.qty_rolls || 0);
    map.set(unit, row);
  });
  return [...map.values()];
}

export function formatQtyByUnit(items = []) {
  return qtyByUnit(items)
    .map((r) => `${formatQty(r.qty)} ${r.unit}${r.rolls ? ` (${r.rolls} roll)` : ""}`.trim())
    .join(" · ");
}

/**
 * F-04 (uji pra-UAT 2026-10-21) — total PER SATUAN dari server ({ yard: 1250, kg: 340 }) → "340 kg · 1.250 yard"
 * (KPI POS dulu menjumlahkan yard + kg menjadi satu angka). Tanpa rincian → angka lama (`fallback`).
 */
export function formatUnitTotals(byUnit, fallback) {
  const parts = Object.entries(byUnit || {})
    .filter(([, q]) => Number(q) > 0)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([u, q]) => `${formatQty(q)} ${u}`.trim());
  if (parts.length) return parts.join(" · ");
  return byUnit ? "0" : formatQty(fallback);
}
