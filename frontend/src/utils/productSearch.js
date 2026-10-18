/**
 * MD-08 — kode/nama produk GANDA (KN ↔ supplier) untuk pencarian.
 * `supplier_codes` datang dari GET /api/products (katalog versi supplier).
 */
export function supplierKeywords(p) {
  // L01 — warna supplier & warna customer ikut dicari (tiga sisi warna).
  return [...(p?.supplier_codes || []).flatMap((c) => [c.supplier_sku, c.supplier_item_name, c.supplier_name,
    c.supplier_color, c.supplier_color_code]), p?.customer_color, p?.color].filter(Boolean);
}

export function supplierCodesLabel(p) {
  const codes = (p?.supplier_codes || []).map((c) => c.supplier_sku).filter(Boolean);
  return codes.length ? ` · pabrik: ${codes.join(", ")}` : "";
}

/** Opsi KNSelect produk: label KN + kata kunci supplier (dicari di kedua sisi). */
export function productOption(p, label) {
  return { value: p.id, label: label ?? `${p.sku} · ${p.name}`, keywords: supplierKeywords(p) };
}

export function productMatches(p, q) {
  const s = (q || "").trim().toLowerCase();
  if (!s) return true;
  return `${p.sku || ""} ${p.name || ""} ${p.category || ""} ${supplierKeywords(p).join(" ")}`.toLowerCase().includes(s);
}
