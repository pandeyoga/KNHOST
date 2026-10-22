import { formatQty } from "./formatters";

/**
 * EPIC-VAR — Pengelompokan produk berdasarkan template_id untuk tampilan katalog.
 * PRINSIP: 1 varian = 1 SKU (product_id). Pengelompokan ini HANYA presentation
 * (katalog POS). Inventory/WMS/receiving tetap per-SKU.
 *
 * Produk tanpa template_id → grup tunggal (key = product.id).
 */

/** L01 — POV tanpa grade/asal (field disembunyikan server): varian yang tampak kembar (beda grade/asal
 *  saja) digabung jadi SATU varian per warna. Stok = jumlah anggota; anggota disimpan di `merged_members`
 *  (urut stok terbanyak) supaya keranjang memecah qty ke SKU nyata. Tampilan saja — SO tetap per-SKU. */
export function mergeHiddenTwins(products = []) {
  const map = new Map();
  for (const p of products) {
    if (p.grade || p.origin) { map.set(`id:${p.id}`, [p]); continue; }
    const key = [p.template_id || p.id, JSON.stringify(p.variant_attrs || {}), p.color || "", p.name || ""].join("|");
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(p);
  }
  return Array.from(map.values()).map((members) => {
    if (members.length === 1) return members[0];
    const sorted = [...members].sort((a, b) => Number(b.available_qty || 0) - Number(a.available_qty || 0));
    const prices = members.map((m) => Number(m.price || 0));
    return {
      ...sorted[0],
      available_qty: members.reduce((s, m) => s + Number(m.available_qty || 0), 0),
      roll_count: members.reduce((s, m) => s + Number(m.roll_count || 0), 0),
      price_min: Math.min(...prices), price_max: Math.max(...prices),
      merged_members: sorted,
    };
  });
}

export function groupByTemplate(products = []) {
  products = mergeHiddenTwins(products);
  const map = new Map();
  for (const p of products) {
    const key = p.template_id || p.id;
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(p);
  }
  return Array.from(map.entries()).map(([key, variants]) => {
    const prices = variants.flatMap((v) => (v.merged_members || [v]).map((m) => Number(m.price || 0)));
    const totalAvailable = variants.reduce((s, v) => s + Number(v.available_qty || 0), 0);
    // F2 (UoM SSOT) — total roll tersedia lintas varian (1 produk = 1 base_unit; roll beda panjang)
    const totalRolls = variants.reduce((s, v) => s + Number(v.roll_count || 0), 0);
    // Trial 22 Okt (B6) — stok milik PT penjual (aktif) terpisah dari stok grup; null = tidak ada rincian per PT.
    const stockEntityName = (variants.find((v) => v.stock_entity_name) || {}).stock_entity_name || "";
    const totalOwn = stockEntityName ? variants.reduce((s, v) => s + Number(v.entity_available_qty || 0), 0) : null;
    const totalOwnRolls = stockEntityName ? variants.reduce((s, v) => s + Number(v.entity_roll_count || 0), 0) : null;
    // Representatif: varian dengan stok tertinggi (fallback varian pertama).
    const rep =
      [...variants].sort((a, b) => Number(b.available_qty || 0) - Number(a.available_qty || 0))[0] ||
      variants[0];
    return {
      key,
      base: rep,
      name: rep.template_name || rep.name,
      category: rep.category,
      image: rep.image,
      description: rep.description || "",  // F3 — deskripsi representatif (fallback popup)
      variants,
      isMulti: variants.length > 1,
      priceMin: prices.length ? Math.min(...prices) : 0,
      priceMax: prices.length ? Math.max(...prices) : 0,
      totalAvailable,
      totalRolls,
      stockEntityName,
      totalOwn,
      totalOwnRolls,
      anyAvailable: variants.some((v) => Number(v.available_qty || 0) > 0),
    };
  });
}

/** Label varian yang mudah dibaca: pakai variant_label bila ada, fallback warna · grade. */
// Nilai sumbu "kosong" (XX) tidak ditampilkan; kode pendek diberi awalan agar terbaca.
const NONE_LABELS = new Set(["tidak ada", "xx", "-", "—"]);
const ATTR_PREFIX = { color: "Warna ", grade: "Grade " };

export function variantLabel(p) {
  if (!p) return "";
  return (
    Object.entries(p.variant_attrs || {})
      .filter(([, v]) => v !== null && v !== "" && !NONE_LABELS.has(String(v).trim().toLowerCase()))
      .map(([k, v]) => (ATTR_PREFIX[k] && /^[\w.-]{1,6}$/.test(String(v)) && !String(v).toLowerCase().startsWith(ATTR_PREFIX[k].toLowerCase().trim()) ? `${ATTR_PREFIX[k]}${v}` : v))
      .join(" · ") ||
    p.variant_label ||
    [p.color, p.grade ? `Grade ${p.grade}` : ""].filter(Boolean).join(" · ") ||
    p.sku ||
    ""
  );
}

export function variantAttributes(product) {
  if (!product) return {};
  const attrs = product.variant_attrs || {};
  if (Object.keys(attrs).length) return attrs;
  return Object.fromEntries(Object.entries({ color: product.color, grade: product.grade, origin: product.origin, lebar: product.lebar, quality: product.variant }).filter(([k, v]) => v !== undefined && v !== null && v !== "" && !(k === "quality" && ["Regular", "Standard"].includes(v))));
}

/** L01 — total harga kartu gabungan mengikuti pecahan qty ke SKU nyata (stok terbanyak dulu). */
export function mergedLineTotal(product, qty, unitPrice) {
  const members = product?.merged_members;
  if (!(members?.length > 1)) return unitPrice * (Number(qty) || 0);
  let left = Number(qty) || 0;
  let total = 0;
  members.forEach((m, i) => {
    if (left <= 0) return;
    const take = i === members.length - 1 ? left : Math.min(left, Number(m.available_qty || 0));
    total += take * Number(m.price || 0);
    left -= take;
  });
  return total;
}

/** Trial 22 Okt (B6) — teks stok PT penjual vs grup untuk kartu/quickview sales.
 *  `own` null → tidak ada rincian per PT (cakupan gabungan) → hanya angka grup. */
export function ownStockText(own, ownRolls, unit) {
  if (own == null) return "";
  return Number(own) > 0 ? `${formatQty(own)} ${unit} · ${ownRolls || 0} roll` : "kosong";
}
