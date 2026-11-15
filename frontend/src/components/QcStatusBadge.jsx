import StatusBadge from "./StatusBadge";

// FIX-8 (B4 §3.13 · KN_37 §8) — lencana QC pesanan = StatusBadge baku (ikon perisai + teks + warna token AA; dulu
// pil hex 10 px). Label sama persis.
const META = {
  required: { label: "Menunggu QC", tone: "warning", icon: "shield" },
  passed: { label: "Lulus QC", tone: "success", icon: "check" },
  failed: { label: "Ditolak QC", tone: "danger", icon: "x" },
};

// L05 — status QC pesanan yang diminta di checkout. Kosong bila pesanan tidak minta QC.
export function QcStatusBadge({ status, testId = "qc-status-badge" }) {
  const m = META[status];
  if (!m) return null;
  return <StatusBadge status={status} tone={m.tone} icon={m.icon} label={m.label} testId={testId} />;
}

export const soQcStatus = (order) => {
  const qr = order?.qc_request || {};
  return ["full", "sampling"].includes(qr.mode) ? qr.status : "";
};
