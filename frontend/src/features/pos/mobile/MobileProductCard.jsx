import { Plus, Info, Layers } from "lucide-react";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import { blocksOrder, lifecycleLabel } from "../../../utils/lifecycle";
import { onImageError, productImage } from "../../../utils/productImage";
import { variantLabel } from "../../../utils/variants";
import { displaySku, maskedSkuTitle } from "../skuDisplay";
import StockFigures, { figuresForGroup } from "../../../components/StockFigures";

/** EPIC-VAR — Kartu produk MOBILE (group-aware, kompak). Klik membuka MobileQuickView. */
export function MobileProductCard({ group, onOpen, specialMap = {}, rndEnforcement = "block", siteStock = null, siteName = "", siteId = "" }) {
  const rep = group.base;
  // FIX-2 (B1 UI-06 "kartu HP sales angka besar salah konteks", B3a STK-10/STK-13) — dua angka {LOKAL, GLOBAL}:
  // angka pertama = lokasi jualan × PT penjual, kedua = semua PT; ambang stok rendah dari server (dulu ≤ 40 di sini).
  const fig = figuresForGroup(group, { siteStock, siteName, entityName: group.stockEntityName });
  const availState = fig.badge.key === "habis" ? "habis" : "ready";
  const availLabel = fig.badge.text;
  const availPill = fig.badge.pill;
  const anySpecial = group.variants.some((v) => specialMap[v.id]?.has_special);
  const makloonQty = group.variants.reduce((s, v) => s + Number(v.makloon_reserved_qty || 0), 0);
  const incRestock = group.variants.reduce((s, v) => s + Number(v.incoming_restock_qty || 0), 0);
  const incSo = group.variants.reduce((s, v) => s + Number(v.incoming_so_qty || 0), 0);
  const blockedVariants = group.variants.filter((v) => blocksOrder(v, rndEnforcement));
  const allBlocked = blockedVariants.length > 0 && blockedVariants.length === group.variants.length;
  // F1b — harga efektif pelanggan (harga langganan/khusus) bila sudah dipilih.
  const effPrices = group.variants
    .map((v) => (specialMap[v.id]?.price != null ? Number(specialMap[v.id].price) : null))
    .filter((v) => v != null && v > 0);
  const hasEff = effPrices.length === group.variants.length && effPrices.length > 0;
  const effMin = hasEff ? Math.min(...effPrices) : group.priceMin;
  const effMax = hasEff ? Math.max(...effPrices) : group.priceMax;
  const priceText = group.isMulti && effMin !== effMax
    ? `${formatCurrency(effMin)}+`
    : formatCurrency(effMin);

  return (
    <article data-testid={`mobile-product-${rep.id}`} className="flex flex-col overflow-hidden rounded-xl border border-[#E5E5EA] bg-white">
      <button data-testid={`mobile-product-image-${rep.id}`} className="relative block w-full text-left" onClick={() => onOpen(group)}>
        <img src={productImage(rep)} onError={onImageError} alt={group.name} className="h-28 w-full object-cover" />
        {/* Audit UI 24 Okt (HP Katalog) — lencana grade hanya bila ada nilainya (dulu kotak hitam kosong bagi sales). */}
        {rep.grade && !String(rep.grade).includes("•") && (
          <span className="absolute right-1.5 top-1.5 rounded-md bg-black/85 px-1.5 py-0.5 text-[10px] font-bold text-white">{rep.grade}</span>
        )}
        {group.isMulti
          ? <span className="absolute left-1.5 top-1.5 inline-flex items-center gap-0.5 rounded-full bg-[#0058CC] px-1.5 py-0.5 text-[8.5px] font-bold text-white"><Layers size={9} /> {group.variants.length} varian</span>
          : <span className={`status-pill ${availPill} absolute left-1.5 top-1.5 scale-90`}>{availLabel}</span>}
        {anySpecial && <span className="absolute left-1.5 bottom-1.5 rounded-full bg-[#6B219A] px-1.5 py-0.5 text-[8.5px] font-bold text-white">Harga khusus</span>}
        {allBlocked && (
          <span data-testid={`mobile-product-lifecycle-${rep.id}`}
            className="absolute inset-x-1.5 top-1/2 -translate-y-1/2 rounded-md bg-[#8C4A00]/92 px-1.5 py-1 text-center text-[8.5px] font-bold uppercase text-white">
            {lifecycleLabel(rep)} · belum boleh dijual
          </span>
        )}
      </button>
      <div className="flex flex-1 flex-col p-2.5">
        <p data-testid={`mobile-product-sku-${rep.id}`} className="truncate text-[10px] font-bold uppercase tracking-wide text-[#0058CC]" title={group.isMulti ? undefined : maskedSkuTitle(rep.sku)}>{group.isMulti ? rep.category : displaySku(rep.sku)}</p>
        <h3 data-testid={`mobile-product-name-${rep.id}`} className="mt-0.5 line-clamp-2 text-[12.5px] font-semibold leading-tight">{group.name}</h3>
        <p className="mt-0.5 line-clamp-1 text-[10.5px] text-[#6B6B73]">{group.isMulti ? `${group.variants.length} ${group.variants.some((v) => v.grade) ? "warna/grade" : "warna"}` : rep.color}</p>
        <p data-testid={`mobile-product-price-${rep.id}`} className="mt-1.5 text-[14px] font-bold tabular-nums text-[#1C1C1E]">{priceText}<span className="text-[9.5px] font-medium text-[#8E8E93]">/{rep.base_unit || "meter"}</span></p>
        {/* UAT 24 Okt (P8) + FIX-2 — dua angka (roll lalu panjang), ketuk → rincian. Dulu tiga baris 10 px. */}
        <StockFigures size="lg" className="mt-1" testId={`mobile-product-stock-figures-${rep.id}`} unit={fig.unit}
          local={fig.local} global={fig.global} localLabel={fig.localLabel} globalLabel="Total grup (semua PT)"
          productIds={group.variants.map((v) => v.id)} siteId={siteId}
          productLabels={Object.fromEntries(group.variants.map((v) => [v.id, variantLabel(v)]))} />
        {incRestock > 0 && <p data-testid={`mobile-product-incoming-restock-${rep.id}`} className="text-[10px] font-semibold text-[#0058CC]">Datang restock: {formatQty(incRestock)}</p>}
        {incSo > 0 && <p data-testid={`mobile-product-incoming-so-${rep.id}`} className="text-[10px] text-[#6B6B73]">Datang utk SO: {formatQty(incSo)}</p>}
        {makloonQty > 0 && (
          <p data-testid={`mobile-product-makloon-reserved-${rep.id}`} className="text-[10px] font-semibold text-[#9A5B00]">
            Dicadangkan makloon: {formatQty(makloonQty)}
          </p>
        )}
        <div className="mt-2 flex gap-1.5">
          {/* FASE F — jangan jadi jalan buntu: kartu terkunci tetap bisa diklik agar
              MobileQuickView menampilkan alasan + langkah (Spesifikasi → Sample → Rilis). */}
          <button data-testid={`mobile-add-${rep.id}`} className={`flex-1 justify-center py-2 text-[12px] ${allBlocked ? "secondary-button" : "primary-button"}`}
            data-orderable={allBlocked ? "false" : "true"}
            aria-disabled={allBlocked ? "true" : undefined}
            disabled={!allBlocked && availState === "habis"} onClick={() => onOpen(group)}>
            <Plus size={13} /> {allBlocked ? "Belum boleh dijual" : availState === "habis" ? "Habis" : (group.isMulti ? "Pilih" : "Tambah")}
          </button>
          <button data-testid={`mobile-detail-${rep.id}`} className="secondary-button px-2.5 py-2" onClick={() => onOpen(group)} aria-label="Detail"><Info size={14} /></button>
        </div>
      </div>
    </article>
  );
}
