/** L01 LN-011 — tiga sisi warna SKU berdampingan: internal (KN) · supplier · customer. */
import { canSeeSourcing } from "../utils/sourcingVisibility";

export default function ProductColorTriad({ product, compact = false, showSupplier }) {
  if (!product) return null;
  const withSup = showSupplier ?? canSeeSourcing();
  const internal = product.color_ref ? `${product.color_ref.code || ""} ${product.color_ref.name || ""}`.trim()
    : (product.variant_attrs?.color || product.color || "");
  const sup = (product.supplier_codes || []).filter((c) => c.supplier_color || c.supplier_color_code)
    .map((c) => `${c.supplier_color || ""}${c.supplier_color_code ? ` (${c.supplier_color_code})` : ""}${c.supplier_name ? ` — ${c.supplier_name}` : ""}`);
  const cells = [
    ["Warna internal", internal || "—", "internal"],
    ...(withSup ? [["Warna supplier", sup.length ? sup.join(" · ") : "—", "supplier"]] : []),
    ["Warna customer", product.customer_color || "—", "customer"],
  ];
  return (
    <div className={`grid ${withSup ? "grid-cols-3" : "grid-cols-2"} gap-1.5 ${compact ? "mt-1" : "mt-1.5"}`} data-testid={`product-color-triad-${product.id}`}>
      {cells.map(([label, val, key]) => (
        <div key={key} className="rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] px-2 py-1.5">
          <p className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p>
          <p className="truncate text-[11px] font-semibold" title={val} data-testid={`product-color-${key}-${product.id}`}>{val}</p>
        </div>
      ))}
    </div>
  );
}
