/** Shared components for the Returns feature. */
import { docStatusLabel } from "../../utils/docStatus";
const RETURN_TYPE_LABEL = {
  retur:       "Retur",
  bs:          "Barang Sisa (BS)",
  penggantian: "Penggantian",
  komplain:    "Komplain",
  garansi:     "Garansi",
};
const STATUS_STYLE = {
  draft:            { cls: "pill-muted",   label: "Draf" },
  pending_approval: { cls: "pill-warning", label: "Menunggu Persetujuan" },
  // Audit UI 24 Okt (034) — "Disetujui" hijau seperti di Retur ke Supplier; tahap inspeksi biru/ungu
  // supaya tidak sewarna dengan "Menunggu Persetujuan" (kuning = perlu keputusan).
  approved:         { cls: "pill-success", label: "Disetujui" },
  inspecting:       { cls: "pill-info",    label: "Inspeksi" },
  inspected:        { cls: "pill-purple",  label: "Selesai Inspeksi" },
  // UAT 24 Okt (audit UI tahap 2) — G2-16: kolom STATUS berisi status ("Selesai"); jenis penyelesaian jadi
  // lencana kecil di sampingnya (dulu "Store Credit" menggantikan status).
  refund_settled:   { cls: "pill-success", label: "Selesai", kind: "refund" },
  credit_settled:   { cls: "pill-success", label: "Selesai", kind: "store credit" },
  nego_settled:     { cls: "pill-success", label: "Selesai", kind: "nego" },
  settled:          { cls: "pill-success", label: "Selesai", kind: "per roll (campuran)" },   // UAT 23 Okt — penyelesaian per roll
  rejected:         { cls: "pill-danger",  label: "Ditolak" },
  cancelled:        { cls: "pill-muted",   label: "Dibatalkan" },
};
export const OUTCOME_LABEL = {
  refund: "Refund", store_credit: "Store Credit (potong bon)",
  nego: "Nego (diskon)", reject: "Tolak", mixed: "per roll (campuran)",
};
export function fmtNum(n, d = 1) {
  return new Intl.NumberFormat("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d }).format(n || 0);
}
// 23 Okt — tanggal retur memakai formatter baku berzona WIB (dulu zona perangkat → tenggat beda sehari antar-layar).
export { formatDate as fmtDate, formatDateTime as fmtDateTime } from "../../utils/formatters";
export function ReturnStatusPill({ status }) {
  const s = STATUS_STYLE[status] || { cls: "pill-muted", label: docStatusLabel(status) };
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      <span className={`status-pill ${s.cls}`} data-testid={`return-status-pill-${status}`}>{s.label}</span>
      {s.kind && (
        <span className="rounded bg-[#F2F3F5] px-1.5 py-0.5 text-[10px] font-semibold text-[#3C3C43]" data-testid={`return-settle-kind-${status}`}>{s.kind}</span>
      )}
    </span>
  );
}
export function ReturnTypeBadge({ type }) {
  const colors = {
    retur: "badge-blue", bs: "badge-orange", penggantian: "badge-purple",
    komplain: "badge-red", garansi: "badge-teal",
  };
  return (
    <span className={`feature-badge ${colors[type] || "badge-muted"}`} data-testid={`return-type-badge-${type}`}>
      {RETURN_TYPE_LABEL[type] || type}
    </span>
  );
}
