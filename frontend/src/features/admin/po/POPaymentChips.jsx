/** POPaymentChips — chip filter status bayar PO (disaring SERVER lewat ?payment=). */
import { Wallet } from "lucide-react";

const CHIPS = [
  { key: "", label: "Semua" },
  { key: "unpaid", label: "Belum Bayar", on: "bg-red-600 text-white", off: "border-red-200 bg-red-50 text-red-600" },
  { key: "partial", label: "Sebagian", on: "bg-amber-600 text-white", off: "border-amber-200 bg-amber-50 text-amber-700" },
  { key: "paid", label: "Lunas", on: "bg-green-600 text-white", off: "border-green-200 bg-green-50 text-green-700" },
  { key: "settled_by_return", label: "Lunas lewat retur", on: "bg-teal-600 text-white", off: "border-teal-200 bg-teal-50 text-teal-700" },
];

export function POPaymentChips({ value, onChange, counts = {} }) {
  const total = Object.values(counts).reduce((a, n) => a + (n || 0), 0);
  return (
    <div className="flex flex-wrap items-center gap-1.5" data-testid="po-payment-filter">
      <span className="mr-1 flex items-center gap-1 text-[11px] font-semibold text-[#6B6B73]"><Wallet size={13} /> Status bayar</span>
      {CHIPS.map((c) => {
        const active = value === c.key;
        const n = c.key ? counts[c.key] || 0 : total;
        const cls = active ? (c.on || "bg-[#1C1C1E] text-white") : `border ${c.off || "border-[#E5E5EA] bg-white text-[#3C3C43]"} hover:opacity-80`;
        return (
          <button key={c.key || "all"} type="button" data-testid={`po-payment-chip-${c.key || "all"}`}
            onClick={() => onChange(c.key)} aria-pressed={active}
            className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold transition-colors ${cls}`}>
            {c.label}
            <span data-testid={`po-payment-chip-count-${c.key || "all"}`} className={`tabular-nums ${active ? "opacity-90" : "opacity-70"}`}>{n}</span>
          </button>
        );
      })}
    </div>
  );
}

export default POPaymentChips;
