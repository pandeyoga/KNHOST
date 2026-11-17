/**
 * Pola UI 16 Nov (M20, `docs/blueprint/04_POLA_UI.md` §4) — "Alat data master": alat admin/teknis data master produk
 * DIPINDAH dari layar kerja katalog. Dulu empat alat (Data SKU & impor, tata kelola master/preview legacy, lembar kerja
 * perbaikan, sumber restock) tampil terbuka di atas daftar katalog untuk siapa pun yang membuka Produk & Varian.
 *
 * Kini: tombol kecil "Alat data master ▾" di bilah daftar katalog → halaman admin tersendiri (satu alat sekaligus,
 * pilih alat lewat dropdown). Hanya untuk pemegang izinnya — syarat SAMA dengan yang dulu dipakai layar; server tetap
 * menegakkan izinnya sendiri:
 *  · Data SKU & impor, Tata kelola master → ubah produk (`product.update`, kemampuan katalog `update`)
 *  · Perbaikan master (lembar kerja) → ubah produk ATAU ekspor produk (`product.export`: unduh lembar saja)
 *  · Sumber restock → ubah produk (mengubah) ATAU ekspor produk (melihat saja). Dulu daftar ini terbuka (baca saja) bagi
 *    semua peran berizin lihat produk; kini tertutup bagi peran tanpa izin ubah/ekspor produk (arah pemilik M20).
 */
import { ArrowLeft, Factory, FileSpreadsheet, ShieldCheck, Table2, Wrench } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import { PageHeader } from "../../components/ListPageParts";
import { MasterGovernancePanel } from "./MasterGovernancePanel";
import MasterCleanupPanel from "./MasterCleanupPanel";
import RestockSourcePanel from "./RestockSourcePanel";

export const MASTER_TOOLS = [
  { key: "legacy", label: "Data SKU & impor", testId: "catalog-legacy", icon: Table2,
    hint: "Tabel SKU lama · impor massal",
    help: "Tabel SKU lengkap dan impor massal (tampilan master lama). Perubahan di sini langsung berlaku di katalog.",
    allowed: ({ canUpdate, hasLegacy }) => canUpdate && hasLegacy },
  { key: "governance", label: "Tata kelola master", testId: "catalog-tool-governance", icon: ShieldCheck,
    hint: "Pratinjau data lama · eksekusi batch · rollback",
    help: "Pratinjau data master lama (isian kosong, tidak baku, konflik, kandidat duplikat SKU) tanpa mengubah data. "
      + "Usulan yang dicentang dieksekusi sebagai satu batch yang bisa di-rollback. SKU tidak pernah diubah.",
    allowed: ({ canUpdate }) => canUpdate },
  { key: "cleanup", label: "Perbaikan master (lembar kerja)", testId: "catalog-tool-cleanup", icon: FileSpreadsheet,
    hint: "Unduh lembar · unggah untuk pratinjau · terapkan/batalkan",
    help: "Perbaikan nama/kode/penggabungan produk lewat lembar kerja: unduh, isi kolom tindakan, unggah untuk pratinjau, "
      + "lalu terapkan sebagai batch yang bisa dibatalkan. Unduh butuh izin ekspor produk; unggah & terapkan butuh izin ubah.",
    allowed: ({ canUpdate, canExport }) => canUpdate || canExport },
  { key: "restock", label: "Sumber restock artikel", testId: "catalog-tool-restock", icon: Factory,
    hint: "Supplier / makloon — dipakai bila artikel belum punya rute",
    help: "Sumber restock per artikel barang jadi (supplier, makloon, atau keduanya). Dipakai PR/PO/Order Makloon bila "
      + "artikel belum punya rute produk di PT aktif. Mengubah butuh izin ubah produk; pemegang izin ekspor melihat saja.",
    allowed: ({ canUpdate, canExport }) => canUpdate || canExport },
];

/** Alat yang boleh dibuka akun ini (urutan tetap). `access` = { canUpdate, canExport, hasLegacy }. */
export const availableTools = (access) => MASTER_TOOLS.filter((t) => t.allowed(access));

export default function MasterDataTools({ tool, access, legacyView, onTool, onBack }) {
  const tools = availableTools(access);
  const t = tools.find((x) => x.key === tool);
  if (!t) return null;
  return (
    <div className="kn-catalog" data-testid="catalog-tools-view">
      <button type="button" className="back-button" data-testid="catalog-tools-back" onClick={onBack}>
        <ArrowLeft size={14} aria-hidden="true" /> Kembali ke katalog
      </button>
      <PageHeader icon={Wrench} testId="catalog-tools-heading" title="Alat data master" help={t.help}
        actions={tools.length > 1 && (
          <KNSelect data-testid="catalog-tools-select" aria-label="Pilih alat" value={t.key}
            onValueChange={(v) => v && onTool(v)}
            className="!h-auto !w-auto min-w-[220px] rounded-lg border border-kn-field-border bg-white !px-2 !py-1.5 text-fs-13"
            options={tools.map((x) => ({ value: x.key, label: x.label }))} />
        )} />
      {t.key === "legacy" && <div data-testid="catalog-legacy-view">{legacyView}</div>}
      {t.key === "governance" && <MasterGovernancePanel />}
      {t.key === "cleanup" && <MasterCleanupPanel canExport={!!access.canExport} canUpdate={!!access.canUpdate} />}
      {t.key === "restock" && <RestockSourcePanel canEdit={!!access.canUpdate} />}
    </div>
  );
}
