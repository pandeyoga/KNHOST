/**
 * SampleTypeGalleryView — PEMBUNGKUS TIPIS (fase 3 · P6, D-24b).
 *
 * Dulu: layar galeri sendiri per jenis (Labdip · Handfeel · Proofing) dengan KPI, saringan & tombol
 * "Sample <Jenis> Baru". Keputusan pemilik 26 Okt: Labdip/Handfeel/Proofing → SATU layar Sample R&D dengan
 * chip jenis; galeri per jenis tetap ada sebagai mode tampilan. Isinya kini `RndSamplesView` mode Galeri
 * dengan chip jenis terpilih dan tujuan "Semua" (sama dengan cakupan galeri lama: produk baru + uji ulang).
 *
 * Berkas ini dipertahankan karena rute cadangan `activeView === "rnd-labdip"` dkk. (deep link, notifikasi,
 * akses peran lama) masih merendernya sampai P8 mengaktifkan alias `rnd-labdip` → `rnd-samples`
 * `{ mode: "gallery", type: "labdip", purpose: "all" }`.
 */
import RndSamplesView from "./RndSamplesView";

export default function SampleTypeGalleryView({ code, currentUser, selectedEntity }) {
  return (
    <div data-testid={`sample-gallery-${code}`}>
      <RndSamplesView currentUser={currentUser} selectedEntity={selectedEntity} purpose=""
        view={`rnd-${code}`} initialMode="gallery" initialType={code} />
    </div>
  );
}
