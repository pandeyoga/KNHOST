/** Shared helpers & components for the Special Order feature. */
import { CheckCircle2, Clock, Package, XCircle } from "lucide-react";
import { formatDate, formatDateTime } from "../../utils/formatters";

export function fmtNum(n, d = 0) {
  return new Intl.NumberFormat("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d }).format(n || 0);
}

// 23 Okt — tanggal/jam baku WIB (dulu zona perangkat, tanpa keterangan zona).
export const fmtDate = formatDateTime;

// Tanggal saja (tanpa jam) — untuk tenggat/perkiraan kirim.
export const fmtDay = formatDate;

// Label status dokumen tertaut (PR/PO/SO/permintaan desain) — jangan tampilkan kode mentah.
const DOC_STATUS = {
  draft: "Draf", submitted: "Diajukan", pending_approval: "Menunggu persetujuan", approved: "Disetujui",
  rejected: "Ditolak", converted: "Jadi PO", partially_received: "Diterima sebagian", received: "Diterima",
  closed: "Ditutup", cancelled: "Dibatalkan", sent: "Terkirim", confirmed: "Terkonfirmasi",
  assigned: "Ditugaskan", in_progress: "Dikerjakan", revision: "Minta revisi", done: "Selesai",
  shipped: "Dikirim", delivered: "Diterima pelanggan", ready: "Siap", in_production: "Produksi",
  pending: "Belum diterima", partial: "Diterima sebagian", completed: "Diterima lengkap",   // status PO
  waiting_stock: "Menunggu stok", reserved: "Dicadangkan", waiting_approval: "Menunggu persetujuan",
};
export const docStatus = (s) => DOC_STATUS[s] || (s ? String(s).replace(/_/g, " ") : "—");

export const STATUS_STYLE = {
  draft:             { cls: "pill-muted",   label: "Draf", icon: Clock },
  pending_approval:  { cls: "pill-warning", label: "Menunggu Persetujuan", icon: Clock },
  confirmed:         { cls: "pill-info",    label: "Terkonfirmasi", icon: CheckCircle2 },
  in_production:     { cls: "pill-purple",  label: "Dalam Produksi", icon: Package },
  ready:             { cls: "pill-success", label: "Siap", icon: CheckCircle2 },
  shipped:           { cls: "pill-primary", label: "Dikirim", icon: Package },
  done:              { cls: "pill-success", label: "Selesai", icon: CheckCircle2 },
  cancelled:         { cls: "pill-danger",  label: "Dibatalkan", icon: XCircle },
};

// 23 Okt — fase OD terstruktur (lini masa). Status teknis "confirmed" berlaku sejak OD disetujui, padahal
// pesanan masih di tahap desain/sample → kepala halaman menulis "Terkonfirmasi" sementara lini masa menulis
// "Desain berjalan". Lencana kini mengikuti fase bila fase lebih rinci daripada status.
const PHASE_STYLE = {
  design: { cls: "pill-info", label: "Desain berjalan", icon: Clock },
  sampling: { cls: "pill-info", label: "Sampling berjalan", icon: Clock },
  sample_ready: { cls: "pill-info", label: "Sample siap", icon: CheckCircle2 },
  customer_review: { cls: "pill-warning", label: "Menunggu ACC pelanggan", icon: Clock },
  pricing: { cls: "pill-warning", label: "Harga final", icon: Clock },
  approved: { cls: "pill-info", label: "Disetujui", icon: CheckCircle2 },
};

export function StatusPill({ status, phase }) {
  const s = (status === "confirmed" && PHASE_STYLE[phase]) || STATUS_STYLE[status] || { cls: "pill-muted", label: status, icon: Clock };
  const Icon = s.icon;
  return (
    <span className={`status-pill ${s.cls}`} data-testid={`so-status-pill-${status}`}>
      <Icon size={11} /> {s.label}
    </span>
  );
}
