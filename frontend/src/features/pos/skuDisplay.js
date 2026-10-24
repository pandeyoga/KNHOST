/**
 * Audit UI 24 Okt (143 / HP Katalog & Stok) — SKU untuk tampilan kartu.
 *
 * Server menyamarkan segmen SKU yang tidak boleh dilihat peran tertentu (asal/grade/lot →
 * "•"/"••", services/field_visibility.py `_mask_sku`). Ditampilkan mentah hasilnya
 * "KNWVN0015-•-TAUX-••-XX-••" — terlihat seperti data rusak. Di kartu, segmen yang disamarkan
 * cukup dilewati: "KNWVN0015-TAUX-XX". Nilai asli (bersamar) tetap dipakai untuk pencarian & data.
 */
export function displaySku(sku) {
  const s = String(sku ?? "");
  if (!s.includes("•")) return s;
  return s.split("-").map((x) => x.trim()).filter((x) => x && !/^[•\s]+$/.test(x)).join("-");
}

/** Judul (tooltip) untuk SKU yang sebagian disembunyikan. */
export function maskedSkuTitle(sku) {
  return String(sku ?? "").includes("•") ? "Sebagian kode (asal/grade/lot) disembunyikan untuk peran Anda" : undefined;
}
