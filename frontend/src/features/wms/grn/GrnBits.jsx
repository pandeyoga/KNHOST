import { Check } from "lucide-react";
import { STATUS, STEPS } from "./grnApi";
import { docStatusLabel } from "../../../utils/docStatus";

export function GrnStatusBadge({ status, testId }) {
  const s = STATUS[status] || { label: docStatusLabel(status) || "—", cls: "bg-[#F2F2F7] text-[#3C3C43]" };
  return (
    <span data-testid={testId} className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${s.cls}`}>
      {s.label}
    </span>
  );
}

// UAT 24 Okt (audit UI tahap 2) — dokumen Ditutup dulu menampilkan langkah "5 Ditutup" sebagai langkah AKTIF (bukan
// selesai); dokumen Dibatalkan/Ditolak tidak bertanda apa pun di stepper. Kini Ditutup = semua langkah selesai,
// Dibatalkan/Ditolak = lencana merah/abu di ujung stepper.
const TERMINAL = { cancelled: "Dibatalkan", rejected: "Ditolak" };
export function GrnStepper({ status }) {
  const idx = status === "closed" ? STEPS.length
    : STEPS.indexOf(status === "closing" ? "reconcile" : status === "reading" ? "draft" : status);
  return (
    <ol data-testid="grn-stepper" className="flex max-w-full items-center gap-1 overflow-x-auto whitespace-nowrap text-[10.5px] font-semibold">
      {STEPS.map((s, i) => {
        const done = idx > i, cur = idx === i;
        return (
          <li key={s} className="flex items-center gap-1">
            <span className={`flex h-5 w-5 items-center justify-center rounded-full border ${done ? "border-[#0F766E] bg-[#0F766E] text-white" : cur ? "border-[#0058CC] bg-[#EEF4FF] text-[#0058CC]" : "border-[#E5E5EA] text-[#8E8E93]"}`}>
              {done ? <Check size={11} /> : i + 1}
            </span>
            <span className={cur ? "text-[#0058CC]" : done ? "text-[#0F766E]" : "text-[#8E8E93]"}>{STATUS[s].label}</span>
            {i < STEPS.length - 1 && <span className="mx-1 h-px w-5 bg-[#E5E5EA]" />}
          </li>
        );
      })}
      {TERMINAL[status] && (
        <li className="ml-1 flex items-center" data-testid="grn-stepper-terminal">
          <span className={`rounded-full px-2 py-0.5 ${status === "rejected" ? "bg-[#FDECEC] text-[#B4231F]" : "bg-[#F2F2F7] text-[#6B6B73]"}`}>
            {TERMINAL[status]}
          </span>
        </li>
      )}
    </ol>
  );
}

export function Field({ label, children, hint }) {
  return (
    <label className="block text-[11px] font-semibold text-[#3C3C43]">
      <span className="mb-1 block">{label}</span>
      {children}
      {hint && <span className="mt-0.5 block text-[10px] font-normal text-[#6B6B73]">{hint}</span>}
    </label>
  );
}

export function ErrorBox({ text, testId = "grn-error" }) {
  if (!text) return null;
  return <p data-testid={testId} className="rounded-lg border border-[#F5C2C0] bg-[#FDECEC] px-3 py-2 text-[11px] text-[#B4231F]">{text}</p>;
}

// UAT 24 Okt (P16.1) — isian GRN = `.field` design-system (dulu kelas 12px buatan sendiri).
export const inputCls = "field";
