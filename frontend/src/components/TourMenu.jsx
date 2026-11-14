import { useEffect, useRef } from "react";
import { Lightbulb } from "lucide-react";
import { roleLabel as registryRoleLabel } from "../config/roles";
import { getToursForRole } from "../data/tourDefinitions";
import { useEscapeClose } from "../utils/escapeLayers";

/**
 * Help & Tours button + role-aware tour list panel.
 * Self-contained — parent only needs to provide handler when a tour is selected.
 *
 * Penempatan (perapian Meja Finance 14 Nov 2026, keputusan pemilik):
 *  · `placement="topbar"` — layar desktop (> 768 px): tombol ikon baku di topbar, panel turun dari atas.
 *    Dulu tombol MELAYANG kanan-bawah menutupi angka & kontrol di tepi kanan bawah layar (terukur: "NILAI"
 *    kartu antrean Meja Finance, pemilih urutan "Tertua dulu"; catatan serupa P6/P18/P19). Ruang aman
 *    104 px di bawah konten hanya menolong di AKHIR halaman, bukan saat halaman baru dibuka/sedang digulir.
 *    Di topbar tombol ini tidak pernah menutupi isi.
 *  · `placement="floating"` (bawaan) — layar ≤ 768 px (tampilan desktop di HP): tombol bulat kecil
 *    mengapung seperti sebelumnya; ruang aman bawah (`#main-content`) tetap berlaku.
 * Esc menutup panel lewat tumpukan lapisan bersama (`useEscapeClose`, INV-UI-10). Klik di luar panel menutupnya:
 * mode mengapung memakai lapisan `fixed inset-0`; mode topbar TIDAK bisa (topbar ber-`backdrop-filter` menjadi
 * wadah elemen `fixed`, jadi lapisan itu hanya selebar topbar) — maka pendengar `mousedown` dokumen, seperti
 * `NotificationCenter`.
 */
export default function TourMenu({
  userRole,
  showMenu,
  onToggleMenu,
  onSelectTour,
  placement = "floating",
}) {
  const inTopbar = placement === "topbar";
  useEscapeClose(!!showMenu, onToggleMenu);
  const anchorRef = useRef(null);
  const toggleRef = useRef(onToggleMenu);
  toggleRef.current = onToggleMenu;
  useEffect(() => {
    if (!inTopbar || !showMenu) return undefined;
    const onDown = (e) => { if (anchorRef.current && !anchorRef.current.contains(e.target)) toggleRef.current?.(); };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [inTopbar, showMenu]);
  const availableTours = getToursForRole(userRole);
  // FASE E-8 — lencana peran memakai REGISTRY. Pembesaran huruf pertama membuat
  // `sales_admin` tampil sebagai "Sales_admin" di layar.
  const roleLabel = userRole ? registryRoleLabel(userRole) : "Tamu";

  const backdrop = showMenu && (
    <button
      type="button"
      aria-label="Tutup panduan"
      className="fixed inset-0 -z-10 cursor-default bg-transparent"
      onClick={onToggleMenu}
      data-testid="tour-menu-backdrop"
    />
  );

  const panel = showMenu && (
    <div
      className={`${inTopbar ? "top-full z-50 mt-2" : "bottom-16 mb-2"} absolute right-0 w-72 rounded-xl border border-kn-divider bg-white shadow-2xl`}
      data-testid="tour-menu-panel"
    >
      <div className="border-b border-kn-divider p-3">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-fs-13 font-bold">Smart Guidelines</h3>
          <span
            className="rounded-full bg-kn-action-soft px-2 py-0.5 text-fs-12 font-semibold uppercase tracking-wide text-kn-action"
            data-testid="tour-menu-role-badge"
          >
            {roleLabel}
          </span>
        </div>
        <p className="mt-0.5 text-fs-12 text-kn-text-2">
          Tutorial relevan untuk peran Anda · {availableTours.length} panduan
        </p>
      </div>
      <div className="p-2 max-h-96 overflow-y-auto">
        {availableTours.length === 0 ? (
          <div
            className="px-3 py-6 text-center"
            data-testid="tour-menu-empty-state"
          >
            <p className="text-fs-13 font-semibold text-kn-text">
              Belum ada tutorial
            </p>
            <p className="mt-1 text-fs-12 text-kn-text-2">
              Tidak ada panduan yang tersedia untuk peran <b>{roleLabel}</b> saat ini.
            </p>
          </div>
        ) : (
          availableTours.map((tour) => (
            <button
              key={tour.key}
              onClick={() => onSelectTour(tour)}
              className="w-full text-left px-3 py-2 rounded-lg hover:bg-kn-action-soft transition-colors mb-1"
              data-testid={`tour-menu-item-${tour.id}`}
            >
              <p className="text-fs-13 font-semibold text-kn-text">{tour.name}</p>
              <p className="mt-0.5 text-fs-12 text-kn-text-2">{tour.description}</p>
            </button>
          ))
        )}
      </div>
    </div>
  );

  if (inTopbar) {
    return (
      <div className="relative inline-flex" data-testid="tour-anchor" ref={anchorRef}>
        <button
          type="button"
          onClick={onToggleMenu}
          className="icon-button"
          aria-label="Bantuan & Panduan"
          aria-expanded={!!showMenu}
          aria-haspopup="true"
          title="Bantuan & Panduan"
          data-testid="help-tours-button"
        >
          <Lightbulb size={15} />
        </button>
        {panel}
      </div>
    );
  }

  return (
    <div className="tour-fab fixed bottom-4 right-4 z-50 md:bottom-6 md:right-6" data-testid="tour-fab">
      {backdrop}
      {panel}
      <button
        type="button"
        onClick={onToggleMenu}
        className="flex items-center gap-2 rounded-full bg-kn-action p-3 text-white shadow-lg transition-opacity hover:opacity-90"
        aria-label="Bantuan & Panduan"
        aria-expanded={!!showMenu}
        title="Bantuan & Panduan"
        data-testid="help-tours-button"
      >
        <Lightbulb size={20} />
      </button>
    </div>
  );
}
