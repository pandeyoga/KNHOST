/**
 * cashCategories — kategori kas manual (Kas & Bank › Transaksi Kas) dan label kategori kas lama.
 *
 * Satu sumber untuk form Catat Transaksi (`CashManagementView`), bagian "Menunggu persetujuan" dan pratinjau pengajuan
 * kas keluar (`features/finance/cashout/`). Berkas data tanpa React supaya isi pratinjau bisa memakainya tanpa
 * mengimpor layar (registri pratinjau ↔ layar tidak boleh saling impor).
 *
 * Kas & Bank 1 (Tugas 5/6) — kategori "Transfer / Top-up" DITUTUP untuk kas manual baru (setor tunai, isi kas kecil, dan
 * pindah antar rekening lewat Pindah Dana). Kas & Bank 2 (Tugas 1/4, C5) — "Pembelian" dan "Gaji / Upah" DITUTUP
 * (`cash_ledger.PESAN_KATEGORI_PEMBELIAN_GAJI_DITUTUP`): barang lewat PO/tagihan pemasok, gaji lewat Proses Gaji, belanja
 * kecil kebutuhan kantor pakai Operasional. Labelnya tetap untuk kas LAMA berkategori itu (daftar, CSV, pratinjau).
 */
export const CATEGORIES = [
  { value: "operasional", label: "Operasional" },
  { value: "modal", label: "Setoran Modal" },
  { value: "lain", label: "Lain-lain" },
];

export const CATEGORY_LABEL = {
  ...Object.fromEntries(CATEGORIES.map((c) => [c.value, c.label])),
  pembelian: "Pembelian", gaji: "Gaji / Upah", penagihan: "Penagihan", transfer: "Transfer / Top-up",
  "pindah dana": "Pindah Dana", "biaya bank": "Biaya bank",
};

export const categoryLabel = (c) => {
  if (!c) return "—";
  const s = String(c);
  return CATEGORY_LABEL[s] || (s.charAt(0).toUpperCase() + s.slice(1)).replace(/_/g, " ");
};
