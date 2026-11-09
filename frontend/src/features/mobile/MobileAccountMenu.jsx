/**
 * MobileAccountMenu — isi baku tab terakhir "Lainnya" di SEMUA aplikasi HP (fase 3 · P7, L-09 + D-26).
 *
 * Dulu tiap aplikasi HP punya bagian akun sendiri: Sales (kartu profil, pengalih PT, push/pasang, "Tampilan Desktop",
 * Keluar), MD (salinan dengan testid lain + baris desktop kedua), Ops/Gudang (ikon monitor & keluar di app bar,
 * tombol "Buka Tampilan Desktop" di tab Ringkas, tanpa pengalih PT/push). Kini satu komponen:
 *   profil → kartu push & pasang aplikasi → pengalih badan usaha → [isi khusus aplikasi] → SATU "Tampilan desktop"
 *   (D-26) → Keluar.
 *
 * Props: `user` · `entities` · `selectedEntity` · `onSelectEntity` · `onForceDesktop` · `onLogout`
 *   · `header` (di atas kartu profil, mis. antrean offline Sales) · `children` (menu khusus aplikasi)
 *   · `entityNote` (kalimat mode "Semua") · `footer` (teks kecil paling bawah).
 * Testid baku: `mobile-account-menu`, `mobile-account-profile`, `mobile-entity-switch`, `mobile-entity-all`,
 *   `mobile-entity-<id>`, `mobile-entity-all-note`, `mobile-force-desktop`, `mobile-logout`.
 */
import { ChevronRight, LogOut, Monitor, UserCircle } from "lucide-react";
import { roleLabel } from "../../config/roles";
import { entityShortById } from "../../utils/entityLabel";
import { MobileInstallCard, MobilePushCard, dropPushSubscription } from "../sales/mobile/MobilePwa";

const DEFAULT_ENTITY_NOTE = "Mode \"Semua\" hanya untuk melihat — pilih satu badan usaha untuk membuat dokumen baru.";

export function EntitySwitchCard({ user, entities, selectedEntity, onSelectEntity, note = DEFAULT_ENTITY_NOTE }) {
  const allowed = user?.allowed_entity_ids || [];
  const switchable = (entities || []).filter((e) => allowed.includes(e.id));
  if (!onSelectEntity || switchable.length < 2) return null;
  const pill = (on) => `kn-chip-touch${on ? " is-active" : ""}`;   // FIX-4 — chip sentuh baku (≥ 48 px)
  return (
    <div className="m-card p-3" data-testid="mobile-entity-switch">
      <p className="mb-2 kn-hp-support font-bold">Badan usaha aktif</p>
      {selectedEntity === "all" && <p className="mb-2 text-fs-14 text-kn-warning-text" data-testid="mobile-entity-all-note">{note}</p>}
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => onSelectEntity("all")} data-testid="mobile-entity-all" className={pill(selectedEntity === "all")}>Semua</button>
        {switchable.map((e) => (
          <button type="button" key={e.id} onClick={() => onSelectEntity(e.id)} data-testid={`mobile-entity-${e.id}`} className={pill(selectedEntity === e.id)}>
            {entityShortById(entities, e.id)}
          </button>
        ))}
      </div>
    </div>
  );
}

function ProfileCard({ user }) {
  const display = user?.name || "Pengguna";
  return (
    <div className="m-card flex items-center gap-3 p-4" data-testid="mobile-account-profile">
      <span className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-kn-action text-fs-16 font-bold text-white">
        {display.slice(0, 1).toUpperCase()}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate kn-hp-title">{display}</p>
        <p className="truncate kn-hp-support">{user?.email}</p>
        {/* FASE E-8 — label peran dari registry (id mentah `sales_admin` tampil buruk). */}
        <p className="text-fs-14 font-semibold text-kn-action">{user?.role_label || roleLabel(user?.role)}</p>
      </div>
      <UserCircle size={22} className="text-kn-field-border" />
    </div>
  );
}

export default function MobileAccountMenu({
  user, entities, selectedEntity, onSelectEntity, onForceDesktop, onLogout,
  header = null, children = null, entityNote, footer = "",
}) {
  return (
    <div className="space-y-3" data-testid="mobile-account-menu">
      {header}
      <ProfileCard user={user} />
      <MobilePushCard />
      <MobileInstallCard />
      <EntitySwitchCard user={user} entities={entities} selectedEntity={selectedEntity} onSelectEntity={onSelectEntity} note={entityNote} />
      {children}
      <div className="m-card px-4" data-testid="mobile-account-actions">
        {/* D-26 — SATU pintu ke tampilan desktop untuk semua aplikasi HP (dulu ikon app bar, panel Ringkas & baris MD). */}
        {onForceDesktop && (
          <button type="button" data-testid="mobile-force-desktop" onClick={onForceDesktop} className="m-list-row m-press min-h-touch w-full text-left">
            <span className="inline-flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-kn-neutral-soft"><Monitor size={17} className="text-kn-neutral" /></span>
            <div className="min-w-0 flex-1">
              <p className="kn-hp-info font-semibold">Tampilan desktop</p>
              <p className="truncate kn-hp-support">Beralih ke antarmuka penuh; kembali lewat tombol "Kembali ke aplikasi HP"</p>
            </div>
            <ChevronRight size={16} className="text-kn-field-border" />
          </button>
        )}
        <button type="button" data-testid="mobile-logout" onClick={async () => { await dropPushSubscription(); onLogout?.(); }} className="m-list-row m-press min-h-touch w-full text-left">
          <span className="inline-flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-kn-danger-soft"><LogOut size={17} className="text-kn-danger-text" /></span>
          <div className="min-w-0 flex-1"><p className="kn-hp-info font-semibold text-kn-danger-text">Keluar</p></div>
        </button>
      </div>
      {footer && <p className="pt-1 text-center kn-hp-support" data-testid="mobile-account-footer">{footer}</p>}
    </div>
  );
}
