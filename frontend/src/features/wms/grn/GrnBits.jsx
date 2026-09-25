import { Check } from "lucide-react";
import { STATUS, STEPS } from "./grnApi";

export function GrnStatusBadge({ status, testId }) {
  const s = STATUS[status] || { label: status, cls: "bg-[#F2F2F7] text-[#3C3C43]" };
  return (
    <span data-testid={testId} className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${s.cls}`}>
      {s.label}
    </span>
  );
}

export function GrnStepper({ status }) {
  const idx = STEPS.indexOf(status === "closing" ? "reconcile" : status === "reading" ? "draft" : status);
  return (
    <ol data-testid="grn-stepper" className="flex items-center gap-1 text-[10.5px] font-semibold">
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

export const inputCls = "w-full rounded-lg border border-[#E5E5EA] bg-white px-2.5 py-1.5 text-[12px] focus:border-[#0058CC] focus:outline-none";
