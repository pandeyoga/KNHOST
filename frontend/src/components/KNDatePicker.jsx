// KNDatePicker — pemilih tanggal aplikasi (Popover + Calendar), nilai ISO `YYYY-MM-DD`,
// tampilan Indonesia ("Rab, 03 Sep 2026"). Menggantikan <input type="date"> native yang
// tampil berbeda per browser & memakai format lokal OS.
import { useState } from "react";
import { format, parseISO, isValid } from "date-fns";
import { id as localeId } from "date-fns/locale";
import { CalendarDays, X } from "lucide-react";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export const formatDateId = (iso, pattern = "EEE, dd MMM yyyy") => {
  if (!iso) return "";
  const d = parseISO(String(iso).slice(0, 10));
  return isValid(d) ? format(d, pattern, { locale: localeId }) : String(iso);
};

export default function KNDatePicker({ value, onChange, placeholder = "Pilih tanggal", disabled = false, clearable = true, className = "", min, max, "data-testid": testId }) {
  const [open, setOpen] = useState(false);
  const selected = value ? parseISO(String(value).slice(0, 10)) : undefined;
  const minD = min ? parseISO(String(min).slice(0, 10)) : null;
  const maxD = max ? parseISO(String(max).slice(0, 10)) : null;
  const disabledDays = [
    ...(minD && isValid(minD) ? [{ before: minD }] : []),
    ...(maxD && isValid(maxD) ? [{ after: maxD }] : []),
  ];
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <div className={`relative ${className}`}>
        <PopoverTrigger asChild>
          <button type="button" disabled={disabled} data-testid={testId}
            className={`form-input flex w-full items-center gap-2 text-left ${!value ? "text-[#9A9BA3]" : ""} ${clearable && value && !disabled ? "pr-7" : ""}`}>
            <CalendarDays size={14} className="shrink-0 text-[#0058CC]" />
            <span className="flex-1 truncate">{value ? formatDateId(value) : placeholder}</span>
          </button>
        </PopoverTrigger>
        {clearable && value && !disabled && (
          <button type="button" aria-label="Hapus tanggal" data-testid={testId ? `${testId}-clear` : undefined}
            className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-[#9A9BA3] hover:bg-[#F2F3F5] hover:text-[#C0341D]"
            onClick={(e) => { e.preventDefault(); onChange(""); setOpen(false); }}><X size={12} /></button>
        )}
      </div>
      {/* UAT 24 Okt (audit UI tahap 2) — G0-13: di HP kalender menutupi judul/× pop-up atau tombol kaki, di desktop
          menjulur keluar pop-up. Kini dijaga di dalam layar (collisionPadding), tinggi dibatasi & bisa digulir,
          dan lebih rapat di layar sempit. */}
      <PopoverContent className="w-auto max-h-[min(22rem,70dvh)] overflow-auto p-0" align="start" side="bottom"
        avoidCollisions collisionPadding={12} sticky="partial"
        data-testid={testId ? `${testId}-popover` : undefined}>
        <Calendar className="p-2 sm:p-3" mode="single" locale={localeId} selected={isValid(selected) ? selected : undefined}
          defaultMonth={isValid(selected) ? selected : undefined} initialFocus
          disabled={disabledDays.length ? disabledDays : undefined}
          onSelect={(d) => { onChange(d ? format(d, "yyyy-MM-dd") : ""); setOpen(false); }} />
      </PopoverContent>
    </Popover>
  );
}
