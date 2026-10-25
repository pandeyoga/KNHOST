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
  // UAT 24 Okt (audit UI tahap 2) — G0-15 · P-02: kode yang masih bocor ke layar (gudang/WMS, QC, jurnal, antar-PT).
  waiting_goods: "Menunggu barang",
  receiving: "Sedang diterima",
  qc_check: "Cek QC",
  qc_pending: "Menunggu QC",
  qc_rejected: "Ditolak QC",
  put_away: "Disimpan ke rak",
  putaway: "Disimpan ke rak",
  escalated: "Dieskalasi",
  created: "Dibuat",
  confirmed: "Dikonfirmasi",
  waiting_stock: "Menunggu stok",
  siap_disahkan: "Siap disahkan",
  posted: "Terposting",
  staging: "Disiapkan",
  picked: "Diambil",
  packed: "Dikemas",
  committed: "Terikat",
  expired: "Kedaluwarsa",
  partial: "Sebagian",
  submitted: "Diajukan",
  verified: "Diverifikasi",
  dispatched: "Dikirim",
  open: "Terbuka",
  active: "Aktif",
  inactive: "Nonaktif",
  paid: "Lunas",
  unpaid: "Belum lunas",
  partially_paid: "Sebagian dibayar",
  overdue: "Lewat jatuh tempo",
  void: "Dianulir",
  voided: "Dianulir",
  failed: "Gagal",
  released: "Dilepas",
  on_hold: "Ditahan",
  processing: "Diproses",
  ready: "Siap",
  archived: "Diarsipkan",
  reversed: "Dibalik",
  disputed: "Disengketakan",
  scheduled: "Dijadwalkan",
  waiting: "Menunggu",
  new: "Baru",
};

const _own = (map, k) => (map && Object.prototype.hasOwnProperty.call(map, k) ? map[k] : undefined);
const _statusKey = (s) => s.trim().toLowerCase().replace(/[\s-]+/g, "_");

/** Label status; kode tak dikenal dirapikan ("some_code" → "Some code") alih-alih ditampilkan mentah.
 *  UAT 24 Okt (audit UI tahap 2) — G0-15: pencarian kebal huruf besar & spasi ("CANCELLED", "Waiting Approval",
 *  "qc-pending" → label yang sama). `extra` = peta lokal layar yang didahulukan sebelum peta bersama. */
export function docStatusLabel(status, extra) {
  if (!status) return "";
  const s = String(status);
  const key = _statusKey(s);
  const hit = _own(extra, s) || _own(DOC_STATUS_LABEL, s) || _own(extra, key) || _own(DOC_STATUS_LABEL, key);
  if (hit) return hit;
  const t = s.replace(/_/g, " ");
  return t.charAt(0).toUpperCase() + t.slice(1);
}
/** true bila status punya label Indonesia di peta bersama (bukan hasil rapikan generik). */
export const hasDocStatusLabel = (status) => {
  if (!status) return false;
  const s = String(status);
  return Boolean(_own(DOC_STATUS_LABEL, s) || _own(DOC_STATUS_LABEL, _statusKey(s)));
};
