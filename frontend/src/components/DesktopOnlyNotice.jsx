/**
 * DesktopOnlyNotice — banner "Layar ini paling nyaman di desktop" di HP (fase 3 · P1, L-04 kelas C).
 *
 * Keputusan pemilik 26 Okt (L-04): layar yang dibuka dari aplikasi HP wajib layak 390 px (kelas B), sedangkan
 * Pengaturan, akuntansi, master data, konsolidasi, Desainer PDF, Registri Domain, Impor Dataset (kelas C)
 * cukup diberi banner ini. Layar TETAP bisa dipakai — banner hanya memberi tahu, tidak menutup apa pun.
 * Hanya tampil di ≤640 px (CSS `.desktop-only-notice`), bisa disembunyikan untuk sesi ini.
 *
 *   <DesktopOnlyNotice testId="coa-desktop-notice" />                     // "Layar ini paling nyaman di desktop."
 *   <DesktopOnlyNotice what="Konsolidasi grup" hint="Tabel eliminasi lebar; geser ke samping." />
 *
 * Props: `what` (bawaan "Layar ini") · `hint` · `testId` (bawaan "desktop-only-notice"; juga kunci sesi
 *   penyembunyian) · `className`.
 */
import { useState } from "react";
import { Monitor, X } from "lucide-react";

const KEY = (id) => `kn_desktop_notice_hidden:${id}`;

export default function DesktopOnlyNotice({ what = "Layar ini", hint = "", testId = "desktop-only-notice", className = "" }) {
  const [hidden, setHidden] = useState(() => {
    try { return sessionStorage.getItem(KEY(testId)) === "1"; } catch (_) { return false; }
  });
  if (hidden) return null;
  const hide = () => {
    try { sessionStorage.setItem(KEY(testId), "1"); } catch (_) { /* noop */ }
    setHidden(true);
  };
  return (
    <div className={`desktop-only-notice ${className}`.trim()} role="note" data-testid={testId}>
      <Monitor size={14} aria-hidden="true" className="desktop-only-icon" />
      <p className="desktop-only-text">
        <b>{what} paling nyaman di desktop.</b>{" "}
        {hint || "Semua fungsi tetap bisa dipakai di HP; tabel lebar bisa digeser ke samping."}
      </p>
      <button type="button" className="desktop-only-close" aria-label="Sembunyikan pemberitahuan"
        data-testid={`${testId}-close`} onClick={hide}>
        <X size={13} aria-hidden="true" />
      </button>
    </div>
  );
}
