/**
 * LeaveRequestFields — isian pengajuan cuti/izin yang SAMA untuk HRD (Cuti & Izin › "Ajukan untuk Karyawan")
 * dan karyawan sendiri (Profil Saya › Cuti & Lembur Saya). Fase 3 · P6 (L-03): dulu dua salinan isian dengan
 * label & susunan berbeda; kini satu komponen di dalam `FormModal` masing-masing.
 *
 * Props: nilai `type` · `from` · `to` · `reason` + setter `onChange(field, value)` · `testPrefix`
 *   ("leave-form" untuk HRD, "ess-leave" untuk ESS — testid lama dipertahankan) · `reasonPlaceholder`.
 */
import KNDatePicker from "@/components/KNDatePicker";
import KNSelect from "../../components/KNSelect";
import { LEAVE_TYPES, countWorkdays } from "./leaveUtils";

export const LEAVE_TYPE_OPTIONS = LEAVE_TYPES.map((t) => ({ value: t.value, label: t.label + (t.deduct ? " · potong saldo" : "") }));

export default function LeaveRequestFields({ type, from, to, reason, onChange, testPrefix = "leave-form", reasonPlaceholder = "mis. acara keluarga" }) {
  return (
    <div className="grid gap-2.5">
      <label className="grid gap-1"><span className="field-label">Tipe <span className="req">*</span></span>
        <KNSelect data-testid={`${testPrefix}-type`} value={type} onValueChange={(v) => onChange("type", v)} className="field"
          options={LEAVE_TYPE_OPTIONS} /></label>
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="grid gap-1"><span className="field-label">Dari <span className="req">*</span></span>
          <KNDatePicker data-testid={`${testPrefix}-from`} value={from} onChange={(v) => onChange("from", v)} /></div>
        <div className="grid gap-1"><span className="field-label">Sampai <span className="req">*</span></span>
          <KNDatePicker data-testid={`${testPrefix}-to`} value={to} onChange={(v) => onChange("to", v)} min={from} /></div>
      </div>
      <p className="text-[11px] text-[#6B6B73]">Estimasi <b>{countWorkdays(from, to)}</b> hari kerja.</p>
      <label className="grid gap-1"><span className="field-label">Alasan (opsional)</span>
        <textarea data-testid={`${testPrefix}-reason`} className="form-input" rows="2" value={reason}
          onChange={(e) => onChange("reason", e.target.value)} placeholder={reasonPlaceholder} /></label>
    </div>
  );
}
