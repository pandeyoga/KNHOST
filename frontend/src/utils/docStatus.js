// 23 Okt — label status dokumen UMUM (retur jual/beli/antar-PT, transfer gudang, roll) untuk layar lintas dokumen
// seperti Jejak/Rantai Retur. Dulu kode status mentah ("approved", "pending_approval", "completed") tampil apa adanya.
// Layar satu modul tetap boleh memakai labelnya sendiri; ini cadangan agar tak ada kode mentah yang bocor ke pengguna.
export const DOC_STATUS_LABEL = {
  draft: "Draf",
  pending: "Menunggu",
  pending_approval: "Menunggu persetujuan",
  waiting_approval: "Menunggu persetujuan",
  approved: "Disetujui",
  rejected: "Ditolak",
  cancelled: "Dibatalkan",
  inspecting: "Sedang diinspeksi",
  inspected: "Selesai inspeksi",
  refund_settled: "Selesai · refund",
  credit_settled: "Selesai · store credit",
  nego_settled: "Selesai · nego",
  settled: "Selesai · per roll (campuran)",
  completed: "Selesai",
  done: "Selesai",
  closed: "Ditutup",
  in_progress: "Sedang berjalan",
  in_transit: "Dalam perjalanan",
  received: "Diterima",
  shipped: "Dikirim",
  delivered: "Terkirim",
  available: "Tersedia",
  quarantine: "Karantina",
  hold: "Ditahan",
  reserved: "Dipesan",
  returned_supplier: "Diretur ke supplier",
  requested_supplier: "Diajukan ke supplier",
  shipped_supplier: "Dikirim ke supplier",
  accepted_supplier: "Diterima supplier",
  rejected_supplier: "Ditolak supplier",
  goods_back: "Barang kembali",
};

/** Label status; kode tak dikenal dirapikan ("some_code" → "Some code") alih-alih ditampilkan mentah. */
export function docStatusLabel(status) {
  if (!status) return "";
  const s = String(status);
  if (DOC_STATUS_LABEL[s]) return DOC_STATUS_LABEL[s];
  const t = s.replace(/_/g, " ");
  return t.charAt(0).toUpperCase() + t.slice(1);
}
