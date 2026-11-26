/** Dokumen cetak turunan pesanan penjualan — satu sumber untuk rincian pesanan dan pop-up Cetak di meja. */
export const ORDER_PRINT_DOCS = [
  { docType: "picking_list", label: "Surat Pengambilan Barang" },
  { docType: "packing_list", label: "Daftar Kemasan" },
  { docType: "delivery_note", label: "Surat Jalan Pengiriman" },
  { docType: "invoice", label: "Faktur Komersial" },
];

/** Status pesanan yang menampilkan seluruh dokumen gudang & penagihan (sudah dilepas ke gudang). */
export const ORDER_PRINT_STATUSES = ["confirmed", "partially_picked", "picked", "partially_shipped", "shipped", "done"];

/** Lapor Bayar (LB-T7) — pesanan disetujui yang ditahan bayar sebelum gudang: Faktur Komersial (berinstruksi bayar) sudah
 *  boleh dicetak/dikirim ke pelanggan; surat gudang belum ada. Konfirmasi Pesanan ada di bilah dokumen pesanan. */
export const ORDER_PRINT_DOCS_TAHAN = ORDER_PRINT_DOCS.filter((d) => d.docType === "invoice");

/** Dokumen cetak turunan yang boleh tampil untuk pesanan ini (kosong = panel Cetak Dokumen tidak tampil). */
export function printDocsForOrder(order) {
  if (!order) return [];
  if (ORDER_PRINT_STATUSES.includes(order.status)) return ORDER_PRINT_DOCS;
  if (order.status === "approved" && order.pay_hold) return ORDER_PRINT_DOCS_TAHAN;
  return [];
}
