// Kontrol tingkat per modul: Tidak ada · Lihat saja · Semua aksi (+ Konfigurasi lanjutan per halaman).
// PR-T5 — hanya tingkat yang berlaku untuk modul ini yang ditawarkan (`levels_available` dari server); modul sakelar
// (tanpa aksi lihat) memakai Mati · Nyala. Tingkat sebagian tidak menyalakan tombol apa pun: lencananya menyebut jumlah
// aksi ("Sebagian (7 dari 13 aksi)").
import { Eye, EyeOff, Pencil, AlertTriangle, SlidersHorizontal, ChevronUp } from "lucide-react";

import { levelsAvailable } from "./roleAccessUtil";

export const LEVELS = [
  { id: "none",   label: "Tidak ada",  icon: EyeOff,  on: "border-[#1C1C1E] bg-[#1C1C1E] text-white" },
  { id: "view",   label: "Lihat saja", icon: Eye,     on: "border-[#0058CC] bg-[#EAF2FF] text-[#0058CC]" },
  { id: "manage", label: "Semua aksi", icon: Pencil,  on: "border-[#1B7F4B] bg-[#EEF9F1] text-[#1B7F4B]" },
];
const TOGGLE_LABEL = { none: "Mati", manage: "Nyala" };

/** Modul sakelar = tidak punya tingkat "Lihat saja" (tidak ada aksi lihat di sumber dayanya). */
export const isToggleModule = (module) => !levelsAvailable(module).includes("view");

export const levelLabel = (id, module) =>
  (module && isToggleModule(module) && TOGGLE_LABEL[id]) || LEVELS.find((l) => l.id === id)?.label || id;

export const partialLabel = (held, total) => `Sebagian (${held} dari ${total} aksi)`;

export default function RoleModuleRow({ module, value, partial, held, total, original, dirty, originalLabel, disabled, onChange, advanced, onToggleAdvanced, children }) {
  // PR-T5 — "diubah" juga bila hanya aksi rincinya yang berubah (dulu pembanding hanya tingkat).
  const changed = dirty !== undefined ? dirty : (original !== undefined && original !== value);
  const avail = levelsAvailable(module);
  const shown = LEVELS.filter((l) => avail.includes(l.id));
  const excludes = value === "view" && !partial ? (module.view_excludes || []) : [];
  return (
    <div data-testid={`role-module-row-${module.id}`}
         className={`rounded-md border bg-white px-3 py-2 ${changed ? "border-[#F0C88A]" : "border-[#EFF0F2]"}`}>
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
      <div className="min-w-0 flex-1">
        <p className="text-[12px] font-bold text-[#1C1C1E]">
          {module.label}
          {partial && (
            <span className="ml-1.5 rounded-full bg-kn-warning-soft px-1.5 py-0.5 text-fs-12 font-semibold text-kn-warning-text"
                  data-testid={`role-module-partial-${module.id}`}>
              {partialLabel(held, total)}
            </span>
          )}
          {module.sensitive && (
            <span className="ml-1.5 inline-flex items-center gap-0.5 text-[9.5px] font-semibold text-[#B45309]"
                  data-testid={`role-module-sensitive-${module.id}`}>
              <AlertTriangle size={9} /> sensitif
            </span>
          )}
          {changed && (
            <span className="ml-1.5 text-[9.5px] font-semibold text-[#8C4A00]"
                  data-testid={`role-module-changed-${module.id}`}>
              diubah · sebelumnya {originalLabel || levelLabel(original, module)}
            </span>
          )}
        </p>
        <p className="text-[10.5px] text-[#6B6B73]">{module.description}</p>
        {excludes.length > 0 && (
          <p className="text-fs-12 text-kn-text-2" data-testid={`role-module-view-excludes-${module.id}`}>
            Tidak termasuk pada Lihat saja: {excludes.join(", ")}.
          </p>
        )}
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-1" role="radiogroup" aria-label={`Tingkat akses ${module.label}`}>
        {shown.map((l) => {
          const Icon = l.icon;
          const on = !partial && value === l.id;
          return (
            <button key={l.id} type="button" disabled={disabled}
                    data-testid={`role-level-${module.id}-${l.id}`}
                    aria-pressed={on}
                    onClick={() => onChange(l.id)}
                    className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[10.5px] font-semibold transition-colors disabled:opacity-50 ${
                      on ? l.on : "border-[#E5E5EA] bg-white text-[#6B6B73] hover:border-[#1C1C1E]/40"}`}>
              <Icon size={11} /> {levelLabel(l.id, module)}
            </button>
          );
        })}
        {onToggleAdvanced && (
          <button type="button" disabled={disabled} data-testid={`role-module-advanced-${module.id}`}
                  aria-expanded={advanced} title="Atur aksi rinci per halaman (buat / ubah / hapus / setujui …)"
                  onClick={onToggleAdvanced}
                  className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[10.5px] font-semibold transition-colors disabled:opacity-50 ${
                    advanced ? "border-[#6B219A] bg-[#F3E9FA] text-[#6B219A]" : "border-[#E5E5EA] bg-white text-[#6B6B73] hover:border-[#6B219A]/50"}`}>
            {advanced ? <ChevronUp size={11} /> : <SlidersHorizontal size={11} />} Atur rinci{/* PR-T6 — dulu "Menu, tab & aktivitas" */}
          </button>
        )}
      </div>
    </div>
    {advanced && children}
    </div>
  );
}
