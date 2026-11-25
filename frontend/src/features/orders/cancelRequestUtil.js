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

/** I3 (tinjauan akhir) — rincian hasil eksekusi batal / tutup sisa dari jawaban server (eksekusi langsung, disetujui
 *  sendiri, atau `result` sesudah Setujui di bilah): nominal yang jadi titipan, galat pemindahan titipan (Finance sudah
 *  diberi tahu server), dan dokumen pemenuhan yang tidak ikut ditutup. Teks diawali spasi; kosong bila tidak ada. */
export function rincianHasil(data, action) {
  const d = data || {};
  const titip = Number(d.advance_to_deposit || 0);
  const refs = d.open_fulfillment_refs || [];
  const awal = action === "close_remaining" ? "" : "Uang muka ";
  return (titip > 0 ? ` ${awal}${formatCurrency(titip)} menjadi titipan pelanggan.` : "")
    + (d.advance_to_deposit_error ? ` ${d.advance_to_deposit_error}` : "")
    + (refs.length ? ` Tindak lanjuti dokumen pemenuhan: ${refs.join(", ")}.` : "");
}

/** Pesan layar untuk jawaban 200 (aksi sudah dijalankan): kalimat utama + `rincianHasil`. */
export function pesanHasil(order, action, data) {
  const nomor = order?.number || "Pesanan";
  const utama = action === "close_remaining" ? `${nomor}: sisa pesanan ditutup, stok dilepas.` : `${nomor} dibatalkan, stok dilepas.`;
  return utama + rincianHasil(data, action);
}
