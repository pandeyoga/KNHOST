// Trial 22 Okt (B3) — bantuan memilih Target baris SJ (isi manual): label yang bisa dicari dengan kode/nama
// versi supplier, isian otomatis dari target, dan saran target dari kode/nama yang diketik.

export const targetLabel = (t) => {
  const sup = [t.supplier_sku, t.supplier_item_name].filter(Boolean).join(" ");
  const base = t.type === "po_task" ? `${t.po_number} · ${t.product_name}` : `${t.mko_number} langkah ${t.step_seq} · ${t.product_name}`;
  return `${base}${t.unit ? ` (${t.unit})` : ""}${sup ? ` · supplier: ${sup}` : ""}`;
};

/** Isi kolom yang MASIH KOSONG dari target terpilih (yang sudah diketik dari SJ tidak ditimpa). */
export const fillFromTarget = (f, t) => ({
  item_code: f.item_code || t.supplier_sku || t.sku || "",
  description: f.description || t.supplier_item_name || t.product_name || "",
  unit: f.unit || t.unit || "",
  po_ref: f.po_ref || t.po_number || t.mko_number || "",
});

const norm = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");

/** Saran target dari kode/nama yang diketik — cocok dengan kode/nama versi supplier atau kode/nama KN. */
export function suggestTargets(targets, code, desc) {
  const c = norm(code);
  const d = norm(desc);
  if (!c && d.length < 3) return [];
  return (targets || []).map((t) => {
    if (c && [t.supplier_sku, t.sku].some((x) => norm(x) && norm(x) === c)) return { t, why: "kode cocok" };
    if (d.length >= 3 && [t.supplier_item_name, t.product_name].some((x) => {
      const n = norm(x);
      return n.length >= 3 && (n.includes(d) || d.includes(n));
    })) return { t, why: "nama cocok" };
    return null;
  }).filter(Boolean).slice(0, 3);
}
