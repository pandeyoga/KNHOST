/** transferConstants — status badge map + StatusBadge component for transfers. */
import { docStatusLabel } from "../../../utils/docStatus";

const STATUS_MAP = {
  draft: { label: "Draf", className: "bg-gray-200 text-gray-700" },
  waiting_approval: { label: "Menunggu Persetujuan", className: "bg-yellow-100 text-yellow-700" },
  approved: { label: "Disetujui", className: "bg-blue-100 text-blue-700" },
  picking: { label: "Pengambilan", className: "bg-purple-100 text-purple-700" },
  staging: { label: "Disiapkan", className: "bg-indigo-100 text-indigo-700" },
  dispatched: { label: "Dalam Perjalanan", className: "bg-orange-100 text-orange-700" },
  partially_received: { label: "Diterima Sebagian", className: "bg-amber-100 text-amber-800" },
  completed: { label: "Selesai", className: "bg-green-100 text-green-700" },
  rejected: { label: "Ditolak", className: "bg-red-100 text-red-700" },
  cancelled: { label: "Dibatalkan", className: "bg-gray-300 text-gray-600" },
};

// Saringan status di daftar transfer (D-16: satu daftar untuk antar gudang & antar PT; "Ditolak" dulu hanya
// ada di daftar antar-PT).
export const TRANSFER_STATUS_FILTERS = [
  "all", "waiting_approval", "approved", "picking", "staging", "dispatched", "completed", "rejected",
];

export function statusLabel(status) {
  return STATUS_MAP[status]?.label || docStatusLabel(status) || "—";
}

// P03 — status aktual per roll di penerimaan transfer
export const STATE_TXT = {
  in_transit: "Dalam perjalanan", received: "Diterima", received_damaged: "Diterima rusak", received_hold: "Diterima ditahan",
  returned: "Kembali ke asal", waiting_dispatch: "Belum dikirim", legacy_completed: "Selesai (data lama)", released: "Dilepas",
};

export function StatusBadge({ status }) {
  const badge = STATUS_MAP[status] || { label: docStatusLabel(status) || "—", className: "bg-gray-200 text-gray-700" };
  return (
    <span data-testid="transfer-status-badge" className={`rounded-full px-3 py-1 text-xs font-semibold ${badge.className}`}>
      {badge.label}
    </span>
  );
}
