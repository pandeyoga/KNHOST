/**
 * EntityGatedButton (PK-42 · UX-05) — tombol BUAT di layar uang yang mati saat kepala aplikasi di mode "Semua PT".
 *
 * Kenapa ada: di mode "Semua PT" server menolak setiap pembuatan data di rute akar (409, `entity_write_guard.py`) —
 * tetapi baru SESUDAH form diisi. Tombol ini mati lebih dulu dan alasannya TERTULIS (bukan hanya tooltip, yang tak
 * terbaca di layar sentuh — Standar UI KN_37), jadi tidak ada kerja yang hilang.
 *
 *   <EntityGatedButton selectedEntity={selectedEntity} what="membuat jurnal" data-testid="gl-new-journal"
 *     className="primary-button" onClick={…}><Plus size={14} /> Jurnal Baru</EntityGatedButton>
 *
 * Props: `selectedEntity` (PT di kepala aplikasi; `"all"` = Semua PT) · `what` (tujuan, mis. "membuat jurnal") ·
 * `hint` (bawaan true: "Pilih satu PT dulu" di samping tombol; false bila kepala kartu sudah padat — pasang
 * `EntityGateNote` di bilah sendiri dan rujuk lewat `aria-describedby`) · sisanya diteruskan ke `<button>`.
 * Selain mode "Semua PT" berperilaku seperti tombol biasa. Wewenang (izin) tetap urusan pemanggil.
 */
import { Building2 } from "lucide-react";

export const entityGateTitle = (what) => `Pilih satu PT dulu (kanan atas) untuk ${what}.`;
export const isAllEntities = (selectedEntity) => selectedEntity === "all";

export default function EntityGatedButton({
  selectedEntity, what = "membuat data", hint = true, disabled = false, title, type = "button", children, ...rest
}) {
  if (!isAllEntities(selectedEntity)) {
    return <button type={type} disabled={disabled} title={title} {...rest}>{children}</button>;
  }
  const testId = rest["data-testid"];
  const hintId = testId ? `${testId}-scope-hint` : undefined;
  const button = (
    <button type={type} {...rest} onClick={undefined} disabled aria-disabled="true" title={entityGateTitle(what)}
      aria-describedby={hint ? hintId : rest["aria-describedby"]}>
      {children}
    </button>
  );
  if (!hint) return button;
  return (
    <span className="entity-gated">
      {button}
      <span id={hintId} data-testid={hintId} className="entity-gated-hint">Pilih satu PT dulu</span>
    </span>
  );
}

/** Bilah alasan sendiri (untuk kepala kartu yang sudah padat): tampil hanya di mode "Semua PT". */
export function EntityGateNote({ selectedEntity, what = "membuat data", testId = "entity-gate-note", className = "" }) {
  if (!isAllEntities(selectedEntity)) return null;
  return (
    <p id={testId} data-testid={testId} role="note" className={`entity-gated-note ${className}`.trim()}>
      <Building2 size={14} aria-hidden="true" className="shrink-0" />
      <span>{entityGateTitle(what)}</span>
    </p>
  );
}
