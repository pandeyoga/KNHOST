/**
 * ViewPresetContext (fase 3 · P1, pola "gabung" §1.1) — preset layar yang dibawa navigasi.
 *
 * KENAPA ADA: layar duplikat menjadi alias ke layar utama + PRESET (tab, mode, saringan), mis.
 * `my-approvals` → Pusat Persetujuan tab "Matriks divisi". App.js menyimpan preset terakhir
 * (`{ view, nonce, ...field }`) saat navigasi; layar utama membacanya sekali lewat
 * `useViewPreset("<view>")` — pola yang sama dengan `focusDoc`, tetapi TANPA prop drilling dan
 * TANPA menyentuh AppViewRouter untuk setiap layar.
 *
 * Nilai: `null` atau `{ view, nonce, ...preset }`. `nonce` berubah tiap navigasi ber-preset,
 * sehingga layar bisa menerapkan ulang preset yang sama bila pengguna mengklik tautan lagi.
 */
import { createContext, useContext } from "react";

const ViewPresetContext = createContext(null);

export function ViewPresetProvider({ preset = null, children }) {
  return <ViewPresetContext.Provider value={preset}>{children}</ViewPresetContext.Provider>;
}

/** Preset mentah (semua view). Layar sebaiknya memakai `useViewPreset(view)` dari hooks/useViewPreset. */
export const useRawViewPreset = () => useContext(ViewPresetContext);

export default ViewPresetContext;
