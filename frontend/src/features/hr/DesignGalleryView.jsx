/**
 * DesignGalleryView — PEMBUNGKUS TIPIS (fase 3 · P6, D-09).
 *
 * Dulu: layar showcase sendiri ("Galeri Desain ACC", `cs-design-gallery`) yang membaca data SAMA dengan
 * Desain & Pattern (`/design-gallery`) dengan saringan & pop-up rincian sendiri (`DesignShowcaseModal`).
 * Keputusan pemilik 26 Okt: satu galeri desain — kini `RndDesignsView` mode **Galeri** (hanya desain ACC,
 * saringan kepemilikan/diproduksi), klik kartu membuka rincian desain yang sama dengan mode Master
 * (kepemilikan & klaim = tab "Kepemilikan & Pemakaian" di rincian).
 *
 * Berkas ini dipertahankan karena rute cadangan `activeView === "cs-design-gallery"` (deep link, antrean
 * backend `design_gallery` yang menarget `cs-design-gallery`, ROLE_NAV desainer) masih merendernya sampai P8
 * mengaktifkan alias `cs-design-gallery` → `rnd-designs` `{ mode: "gallery", status: "acc" }`.
 */
import RndDesignsView from "../rnd/RndDesignsView";

export default function DesignGalleryView({ selectedEntity, currentUser }) {
  return (
    <div data-testid="design-gallery-view">
      <RndDesignsView currentUser={currentUser} selectedEntity={selectedEntity} initialMode="gallery" />
    </div>
  );
}
