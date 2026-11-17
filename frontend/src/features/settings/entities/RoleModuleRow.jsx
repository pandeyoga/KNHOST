// Satu baris matriks hak akses: nama modul (?) · Tidak ada · Lihat saja · Semua aksi · Rinci (+ konfigurasi lanjutan
// per halaman yang dibuka di bawah barisnya).
// PR-T5 — hanya tingkat yang berlaku untuk modul ini yang ditawarkan (`levels_available` dari server); modul sakelar
// (tanpa aksi lihat) memakai Mati · Nyala (kolom Tidak ada · Semua aksi). Tingkat sebagian tidak menyalakan tombol apa
// pun: lencananya menyebut jumlah aksi ("Sebagian (7 dari 13 aksi)") dan kolom Semua aksi bertanda setengah.
// Pola UI 16 Nov (M43) — dulu kartu per modul dengan empat pil lebar + keterangan dua baris (jendela bergulir mendatar);
// kini satu baris berkolom tetap, keterangan modul di ikon ?.
import { AlertTriangle, ChevronUp, Circle, CircleCheck, CircleDashed, SlidersHorizontal } from "lucide-react";

import { HelpTip } from "../../../components/ListPageParts";
import { levelsAvailable } from "./roleAccessUtil";

export const LEVELS = [
  { id: "none",   label: "Tidak ada",  tone: "text-kn-text" },
  { id: "view",   label: "Lihat saja", tone: "text-kn-action" },
  { id: "manage", label: "Semua aksi", tone: "text-kn-success-text" },
];
const TOGGLE_LABEL = { none: "Mati", manage: "Nyala" };

/** Modul sakelar = tidak punya tingkat "Lihat saja" (tidak ada aksi lihat di sumber dayanya). */
export const isToggleModule = (module) => !levelsAvailable(module).includes("view");

export const levelLabel = (id, module) =>
  (module && isToggleModule(module) && TOGGLE_LABEL[id]) || LEVELS.find((l) => l.id === id)?.label || id;

export const partialLabel = (held, total) => `Sebagian (${held} dari ${total} aksi)`;

function helpText(module) {
  const sakelar = isToggleModule(module) ? " Modul sakelar: kolom Tidak ada = Mati, Semua aksi = Nyala." : "";
  return `${module.description || ""}${sakelar}`.trim();
}

export default function RoleModuleRow({ module, value, partial, held, total, original, dirty, originalLabel, disabled, onChange, advanced, onToggleAdvanced, children }) {
  // PR-T5 — "diubah" juga bila hanya aksi rincinya yang berubah (dulu pembanding hanya tingkat).
  const changed = dirty !== undefined ? dirty : (original !== undefined && original !== value);
  const avail = levelsAvailable(module);
  const excludes = value === "view" && !partial ? (module.view_excludes || []) : [];
  return (
    <div data-testid={`role-module-row-${module.id}`} className={`cfg-mx-item${changed ? " is-changed" : ""}`}>
      <div className="cfg-mx-row">
        <div className="cfg-mx-name">
          <b>{module.label}</b>
          <HelpTip text={helpText(module)} testId={`role-module-help-${module.id}`} label={`Tentang ${module.label}`} />
          {partial && (
            <span className="badge-orange" data-testid={`role-module-partial-${module.id}`}>
              {partialLabel(held, total)}
            </span>
          )}
          {module.sensitive && (
            <span className="inline-flex items-center gap-0.5 text-fs-12 font-semibold text-kn-warning-text"
                  data-testid={`role-module-sensitive-${module.id}`}>
              <AlertTriangle size={12} /> sensitif
            </span>
          )}
          {changed && (
            <span className="text-fs-12 font-semibold text-kn-warning-text" data-testid={`role-module-changed-${module.id}`}>
              diubah · sebelumnya {originalLabel || levelLabel(original, module)}
            </span>
          )}
          {excludes.length > 0 && (
            <p className="cfg-mx-sub" data-testid={`role-module-view-excludes-${module.id}`}>
              Tidak termasuk pada Lihat saja: {excludes.join(", ")}.
            </p>
          )}
        </div>
        <div className="cfg-mx-levels" role="radiogroup" aria-label={`Tingkat akses ${module.label}`}>
          {LEVELS.map((l) => {
            if (!avail.includes(l.id)) return <span key={l.id} className="cfg-mx-cell" aria-hidden="true" />;
            const on = !partial && value === l.id;
            const half = partial && l.id === "manage";
            const label = levelLabel(l.id, module);
            const Icon = on ? CircleCheck : (half ? CircleDashed : Circle);
            const tone = on ? l.tone : (half ? "text-kn-warning-text" : "text-kn-neutral");
            return (
              <button key={l.id} type="button" disabled={disabled} className="link-button cfg-mx-pick"
                      data-testid={`role-level-${module.id}-${l.id}`} aria-pressed={on}
                      title={half ? `${label} — saat ini ${partialLabel(held, total)}` : label}
                      onClick={() => onChange(l.id)}>
                <Icon size={18} className={tone} aria-hidden="true" />
                <span className="sr-only">{label}</span>
              </button>
            );
          })}
        </div>
        <div className="cfg-mx-cell">
          {onToggleAdvanced && (
            <button type="button" disabled={disabled} data-testid={`role-module-advanced-${module.id}`}
                    aria-expanded={advanced} title="Atur aksi rinci per halaman (buat / ubah / hapus / setujui …)"
                    aria-label={`Atur rinci ${module.label}`} className="link-button cfg-mx-pick"
                    onClick={onToggleAdvanced}>
              {advanced ? <ChevronUp size={16} aria-hidden="true" /> : <SlidersHorizontal size={16} aria-hidden="true" />}
            </button>
          )}
        </div>
      </div>
      {advanced && <div className="cfg-mx-detail">{children}</div>}
    </div>
  );
}
