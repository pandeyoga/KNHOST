/** transferConstants — status transfer (label dari kosakata tunggal) + lencana status transfer. */
import BaseStatusBadge from "../../../components/StatusBadge";
import { statusLabel as vocabLabel } from "../../../utils/statusVocab";

// FIX-8 (KN_37 §8) — label status transfer dipindah ke `utils/statusVocab.js` (ranah "transfer"; istilah sama persis:
// FIX-3a "Dikembalikan", FIX-3b "Batal — kembali ke asal", D-16 "Ditolak").

// Saringan status di daftar transfer (D-16: satu daftar untuk antar gudang & antar PT; "Ditolak" dulu hanya
// ada di daftar antar-PT).
export const TRANSFER_STATUS_FILTERS = [
  "all", "waiting_approval", "approved", "picking", "staging", "dispatched", "completed", "rejected",
];

export function statusLabel(status) {
  return vocabLabel(status, "transfer");
}

// P03 — status aktual per roll di penerimaan transfer
export const STATE_TXT = {
  in_transit: "Dalam perjalanan", received: "Diterima", received_damaged: "Diterima rusak", received_hold: "Diterima ditahan",
  returned: "Kembali ke asal", waiting_dispatch: "Belum dikirim", legacy_completed: "Selesai (data lama)", released: "Dilepas",
};

/** Lencana status transfer = `StatusBadge` baku (ikon + teks + warna token; dulu pil Tailwind 12 px tanpa ikon). */
export function StatusBadge({ status }) {
  return <BaseStatusBadge status={status} domain="transfer" testId="transfer-status-badge" />;
}
