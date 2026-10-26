/**
 * PriceCorrectionsView — Produk & Harga › **Koreksi Harga** (fase 3 · P2, keputusan pemilik P16-K1).
 *
 * Dulu tab "Koreksi Harga & Daftar Dampak" di Pusat Pengaturan — padahal ini bukan aturan sistem, melainkan
 * koreksi HARGA MASTER produk + pilihan dokumen terbuka mana yang ikut dikoreksi. Rumahnya kini di Produk & Harga.
 * Isi & mesinnya tetap `ImpactPicker` (tanpa salinan). Manajer: pratinjau daftar dampak (server: product.view);
 * menerapkan koreksi tetap butuh product.update (server menolak bila tidak).
 */
import { Wand2 } from "lucide-react";
import ImpactPicker from "./ImpactPicker";
import DesktopOnlyNotice from "../../../components/DesktopOnlyNotice";
import { PageHeader } from "../../../components/ListPageParts";
import { can } from "../../../config/roles";

export default function PriceCorrectionsView({ currentUser, selectedEntity }) {
  // Admin = semua izin; peran lain dibaca dari izin efektif yang dikirim server saat login.
  const canApply = currentUser?.role === "admin" || can(currentUser?.permissions || {}, "product", "update");
  return (
    <div className="cfg-hub" data-testid="price-corrections-view">
      <DesktopOnlyNotice testId="price-corrections-desktop-notice" what="Koreksi Harga" />
      <PageHeader icon={Wand2} title="Koreksi Harga & Daftar Dampak" testId="price-corrections-head"
        subtitle="Koreksi harga master satu produk, lalu pilih sendiri dokumen terbuka mana yang ikut dikoreksi." />
      <ImpactPicker selectedEntity={selectedEntity} canApply={canApply} />
    </div>
  );
}
