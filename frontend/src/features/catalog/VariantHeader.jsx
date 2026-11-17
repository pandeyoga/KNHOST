/**
 * Kepala SKU terpilih di tab "Varian & galeri" (pola UI 16 Nov · M22, templat C): SKU · nama · stok satu baris; aksi di
 * kanan = "Ubah SKU" + menu "Lainnya" (hapus permanen). Dulu tombol merah "Hapus permanen" + teks izin panjang tampil
 * di tengah halaman; kini butir menu bertanda bahaya — nonaktif dengan alasan bila SKU sudah dipakai.
 */
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { formatCurrency, formatQty } from "../../utils/formatters";
import StockFigures from "../../components/StockFigures";
import ProductColorChip from "../../components/ProductColorChip";
import { variantLabel } from "../../utils/variants";
import { CatalogMenu } from "./CatalogMenu";
import { MasterUsageLine, useMasterUsage } from "./MasterUsagePanel";

export function VariantHeader({ family, selected, stock, canUpdate, canPurge, onEdit, onPurged }) {
  const usage = useMasterUsage("product", selected.id, canUpdate);
  const purgeItem = canUpdate && canPurge && usage.info && {
    key: "purge", label: "Hapus permanen SKU", icon: Trash2, danger: true, testId: "master-purge-product",
    disabled: !usage.info.can_delete,
    hint: usage.info.can_delete ? "SKU belum pernah dipakai — dihapus selamanya" : "Sudah dipakai dokumen/stok — nonaktifkan lewat Ubah SKU",
    onSelect: () => usage.purge(onPurged),
  };
  return (
    <div className="catalog-variant-header">
      <div className="flex min-w-0 items-start gap-3">
        {selected.color_hex && <span className="variant-header-dot" style={{ background: selected.color_hex }} />}
        <div className="min-w-0">
          <span data-testid="catalog-selected-sku" className="font-mono text-fs-12 text-kn-text-2">{selected.sku}</span>
          <h2 data-testid="catalog-selected-name">{variantLabel(selected)}</h2>
          {(selected.supplier_codes || []).length > 0 && (
            <p data-testid="catalog-selected-supplier-alias" className="text-fs-12 text-kn-action">
              Versi supplier: {selected.supplier_codes.map((c) => `${c.supplier_sku}${c.supplier_item_name ? ` — ${c.supplier_item_name}` : ""}${c.supplier_name ? ` (${c.supplier_name})` : ""}`).join(" · ")}
            </p>
          )}
          {(selected.color_ref || selected.rnd_supplier) && (
            <div data-testid="catalog-selected-colors" className="mt-1 flex flex-wrap items-center gap-1.5 text-fs-12">
              <ProductColorChip product={selected} />
              {selected.rnd_supplier && <span className="text-kn-text-2">· supplier pemenang R&amp;D <b className="text-kn-text">{selected.rnd_supplier.name}</b>{selected.rnd_supplier.contract_number ? ` (kontrak ${selected.rnd_supplier.contract_number})` : ""}</span>}
            </div>
          )}
          <p data-testid="catalog-selected-stock" className="variant-header-meta">
            {stock ? <><b>{stock.rolls} roll · {formatQty(stock.available)}</b> {family.base_unit} tersedia · dipesan {formatQty(stock.reserved)}</> : "Memuat stok…"}
            <span>·</span><b>{formatCurrency(selected.price)}</b>/{family.base_unit}
          </p>
          {stock?.stock_figures && <StockFigures className="mt-1 max-w-[420px]" testId="catalog-selected-figures" unit={stock.stock_figures.unit || family.base_unit} local={stock.stock_figures.local} global={stock.stock_figures.global} localLabel="Cakupan saya" globalLabel="Total grup (semua PT)" productIds={[selected.id]} />}
          {canUpdate && <MasterUsageLine kind="product" info={usage.info} err={usage.err} />}
        </div>
      </div>
      {canUpdate && (
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" data-testid="catalog-edit-variant" className="secondary-button btn-sm" onClick={onEdit}><Pencil size={13} />Ubah SKU</button>
          <CatalogMenu testId="catalog-variant-more" label="Lainnya" icon={MoreHorizontal} items={[purgeItem]} />
        </div>
      )}
    </div>
  );
}

export default VariantHeader;
