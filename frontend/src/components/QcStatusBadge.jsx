import { ShieldCheck, ShieldAlert, ShieldX } from "lucide-react";

const META = {
  required: { label: "Menunggu QC", cls: "bg-[#FFF4E0] text-[#A15C00] border-[#F5D9A8]", Icon: ShieldAlert },
  passed: { label: "Lulus QC", cls: "bg-[#E8F7EE] text-[#1E7B46] border-[#BFE6CE]", Icon: ShieldCheck },
  failed: { label: "Ditolak QC", cls: "bg-[#FDECEA] text-[#B3261E] border-[#F4C3BE]", Icon: ShieldX },
};

// L05 — status QC pesanan yang diminta di checkout. Kosong bila pesanan tidak minta QC.
export function QcStatusBadge({ status, testId = "qc-status-badge" }) {
  const m = META[status];
  if (!m) return null;
  const { Icon } = m;
  return (
    <span data-testid={testId} data-status={status}
      className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-semibold whitespace-nowrap ${m.cls}`}>
      <Icon size={11} />{m.label}
    </span>
  );
}

export const soQcStatus = (order) => {
  const qr = order?.qc_request || {};
  return ["full", "sampling"].includes(qr.mode) ? qr.status : "";
};
