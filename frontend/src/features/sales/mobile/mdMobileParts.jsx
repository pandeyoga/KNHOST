/**
 * Potongan kecil bersama layar HP MD (`MobileMdViews`, `MobileMdProducts`) — diekstrak fase 3 · P7 (batas 500 baris
 * per berkas). Isi sama persis dengan versi sebelumnya di MobileMdViews.jsx.
 */
import { ArrowLeft } from "lucide-react";
import { badgeClass } from "../../sales_admin/workDeskApi";

export const list = (d) => (Array.isArray(d) ? d : d?.items || []);
export const fmtDate = (s) => (s ? new Date(s).toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" }) : "-");

export function Chips({ items, value, onChange, prefix }) {
  return (
    <div className="flex flex-wrap gap-2 py-1">
      {items.map(([id, label]) => (
        <button key={id || "all"} onClick={() => onChange(id)} data-testid={`${prefix}-${id || "all"}`}
          className={`h-9 shrink-0 whitespace-nowrap rounded-full border px-3 text-[12px] font-semibold ${value === id ? "border-[#0058CC] bg-[#0058CC] text-white" : "border-[#E5E5EA] bg-white text-[#3A3A3C]"}`}>{label}</button>
      ))}
    </div>
  );
}
export const Pill = ({ label, tone = "mute", testId }) => <span className={`shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-bold ${badgeClass(tone)}`} data-testid={testId}>{label}</span>;
export const Back = ({ label, onClick, testId }) => <button className="m-subpage-back" onClick={onClick} data-testid={testId}><ArrowLeft size={17} /> {label}</button>;
// UAT 24 Okt (audit UI tahap 2, G5-59) — form HP berlabel di atas isian (dulu placeholder sebagai label).
export const Field = ({ label, req, hint, children }) => (
  <label className="block space-y-1 text-[11.5px] font-semibold text-[#4A4B53]">
    <span>{label}{req ? <span className="text-[#C0392B]"> *</span> : <span className="font-normal text-[#8E8E93]"> (opsional)</span>}</span>
    {children}
    {hint ? <span className="block text-[10.5px] font-normal text-[#8E8E93]">{hint}</span> : null}
  </label>
);
export const FormHead = ({ title }) => <p className="px-1 text-[15px] font-bold" data-testid="m-form-title">{title}</p>;
export const Notice = ({ msg, testId }) => (msg ? <div className={`notice-bar ${msg.ok ? "success" : "danger"} text-xs`} data-testid={testId}>{msg.text}</div> : null);
