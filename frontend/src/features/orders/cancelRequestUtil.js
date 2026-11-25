import { formatCurrency } from "../../utils/formatters";

/** BTP-6 — kalimat alasan "perlu persetujuan" dari `cancel-check.basis` (paid | excess | prepared). */
export function alasanPersetujuan(basis, order) {
  return (basis || []).map((b) => {
    if (b === "paid") return `sudah ada pembayaran ${formatCurrency(order?.paid_total || 0)}`;
    if (b === "excess") return "ada uang masuk melebihi nilai yang sudah terkirim (akan jadi titipan pelanggan)";
    if (b === "prepared") return "barang sudah disiapkan gudang";
    return String(b);
  });
}

/** Jawaban 202 server = permintaan diajukan (belum dieksekusi). Pemanggil lama jangan menulis "dibatalkan". */
export function diajukan(res) {
  return res?.status === 202 || Boolean(res?.data?.request && res?.data?.message && !res?.data?.status);
}

/** Pesan layar untuk jawaban 202. */
export function pesanDiajukan(order, data) {
  return `${order?.number || "Pesanan"}: ${data?.message || "Permintaan diajukan — menunggu persetujuan."}`;
}
