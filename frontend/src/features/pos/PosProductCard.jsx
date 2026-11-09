import { Plus, Layers, Repeat, FlaskConical, Lock } from "lucide-react";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { blocksOrder, lifecycleLabel } from "../../utils/lifecycle";
import { onImageError, productImage } from "../../utils/productImage";
import { displaySku, maskedSkuTitle } from "./skuDisplay";
import StockFigures, { figuresForGroup } from "../../components/StockFigures";
import { variantLabel } from "../../utils/variants";

/**
 * EPIC-VAR — kartu produk POS (group-aware & ringkas).
 * Kartu menampilkan grup produk (1+ varian). Klik gambar / "Tambah"("Pilih Varian")
 * / "Detail" semuanya membuka ProductQuickView (popup) — qty, satuan, varian, dan
 * detail stok dipindahkan ke popup.
 *
 * FASE F — varian yang masih di alur R&D (lifecycle ≠ produksi) ditandai jelas
 * "Belum boleh dijual" supaya sales tidak menabrak penolakan di ujung checkout.
 */
export function PosProductCard({ group, specialMap = {}, onOpen, reorder, rndEnforcement = "block", siteStock = null, siteName = "", siteId = "" }) {
  const rep = group.base;
  const makloonQty = group.variants.reduce((s, v) => s + Number(v.makloon_reserved_qty || 0), 0);
  const incRestock = group.variants.reduce((s, v) => s + Number(v.incoming_restock_qty || 0), 0);
  const incSo = group.variants.reduce((s, v) => s + Number(v.incoming_so_qty || 0), 0);
  // FIX-2 (B1 UI-06/UI-40, B3a STK-10/STK-13) — dua angka {LOKAL, GLOBAL} dari satu layanan; ambang "stok rendah"
  // dari server (dulu ≤ 40 diketik di sini, server < 100). Tombol jual mati hanya bila GLOBAL habis.
  const fig = figuresForGroup(group, { siteStock, siteName, entityName: group.stockEntityName });
  const availState = fig.badge.key === "habis" ? "habis" : "ready";
  const availLabel = fig.badge.text;
  const availPill = fig.badge.pill;
  const anySpecial = group.variants.some((v) => specialMap[v.id]?.has_special);
  // F1b — kartu juga menandai harga LANGGANAN pelanggan (bukan cuma harga khusus),
  // supaya sales tahu kenapa angka di kartu berbeda dari daftar harga umum.
  const anyCustomer = !anySpecial
    && group.variants.some((v) => specialMap[v.id]?.source === "customer");
  const isExclusive = group.variants.some((v) => v.exclusivity === "sales_tertentu");
  const customerExclusive = group.variants.find((v) => v.exclusive_customer_id);
  const blockedVariants = group.variants.filter((v) => blocksOrder(v, rndEnforcement));
  const allBlocked = blockedVariants.length > 0 && blockedVariants.length === group.variants.length;
  // F1b — kartu WAJIB menampilkan harga yang benar-benar akan dipakai. Dulu kartu
  // memasang lencana "Harga pelanggan" tetapi angkanya tetap harga UMUM, jadi layar
  // menjanjikan satu harga dan pesanan menyimpan harga lain.
  const effPrices = group.variants
    .map((v) => (specialMap[v.id]?.price != null ? Number(specialMap[v.id].price) : null))
    .filter((v) => v != null && v > 0);
  const hasEff = effPrices.length === group.variants.length && effPrices.length > 0;
  const effMin = hasEff ? Math.min(...effPrices) : group.priceMin;
  const effMax = hasEff ? Math.max(...effPrices) : group.priceMax;
  const listChanged = hasEff && (effMin !== group.priceMin || effMax !== group.priceMax);
  const priceText = group.isMulti && effMin !== effMax
    ? `${formatCurrency(effMin)} – ${formatCurrency(effMax)}`
    : formatCurrency(effMin);
  const listText = group.isMulti && group.priceMin !== group.priceMax
    ? `${formatCurrency(group.priceMin)} – ${formatCurrency(group.priceMax)}`
    : formatCurrency(group.priceMin);
  const open = (expand = false) => onOpen(group, expand);

  return (
    <article data-testid={`product-card-${rep.id}`} className="product-card flex flex-col">
      <button data-testid={`product-image-button-${rep.id}`} className="relative block w-full text-left" onClick={() => open(true)}>
        <img data-testid={`product-image-${rep.id}`} src={productImage(rep)} onError={onImageError} alt={group.name} className="product-image" loading="lazy" decoding="async" />
        {rep.grade && <span data-testid={`product-grade-${rep.id}`} className="absolute right-2 top-2 rounded-md bg-black/85 px-1.5 py-0.5 text-[10px] font-bold text-white">{rep.grade}</span>}
        {group.isMulti && (
          <span data-testid={`product-variant-count-${rep.id}`} className="absolute left-2 top-2 inline-flex items-center gap-1 rounded-full bg-[#0058CC] px-2 py-0.5 text-[9.5px] font-bold text-white"><Layers size={10} /> {group.variants.length} varian</span>
        )}
        {anySpecial && (
          <span data-testid={`product-special-badge-${rep.id}`} className="absolute left-2 bottom-2 rounded-full bg-[#6B219A] px-2 py-0.5 text-[9.5px] font-bold text-white">Harga khusus</span>
        )}
        {anyCustomer && (
          <span data-testid={`product-customer-price-badge-${rep.id}`} className="absolute left-2 bottom-2 rounded-full bg-[#0058CC] px-2 py-0.5 text-[9.5px] font-bold text-white">Harga pelanggan</span>
        )}
        {allBlocked && (
          <span data-testid={`product-lifecycle-badge-${rep.id}`}
            className="absolute inset-x-2 top-1/2 -translate-y-1/2 rounded-md bg-[#8C4A00]/92 px-2 py-1 text-center text-[10px] font-bold uppercase tracking-wide text-white">
            {lifecycleLabel(rep)} · belum boleh dijual
          </span>
        )}
        {reorder && (
          <span className="absolute right-2 bottom-2 inline-flex items-center gap-1 rounded-full bg-black/80 px-2 py-0.5 text-[9.5px] font-bold text-white"><Repeat size={10} /> {reorder.reorder_count}×</span>
        )}
      </button>
      <div className="flex flex-1 flex-col p-3">
        <p data-testid={`product-sku-${rep.id}`} className="text-[10.5px] font-bold uppercase tracking-wide text-[#0058CC]" title={group.isMulti ? undefined : maskedSkuTitle(rep.sku)}>{group.isMulti ? rep.category : displaySku(rep.sku)}</p>
        {isExclusive && (
          <span data-testid={`product-exclusive-badge-${rep.id}`}
            className="mt-1 inline-flex w-fit items-center gap-1 rounded-full bg-[#6D4AC0] px-2 py-0.5 text-[9.5px] font-bold text-white">
            <Lock size={10} /> Eksklusif — PO sendiri
          </span>
        )}
        {customerExclusive && (
          <span data-testid={`product-customer-exclusive-badge-${rep.id}`} title="SKU hasil pesanan khusus — hanya boleh dijual ke pelanggan ini"
            className="mt-1 inline-flex w-fit items-center gap-1 rounded-full bg-[#B45309] px-2 py-0.5 text-[9.5px] font-bold text-white">
            <Lock size={10} /> Eksklusif: {customerExclusive.exclusive_customer_name || "pelanggan OD"}
          </span>
        )}
        <h3 data-testid={`product-name-${rep.id}`} className="mt-0.5 text-[14px] font-semibold leading-tight line-clamp-2">{group.name}</h3>
        <p className="mt-0.5 text-[11px] text-[#6B6B73] line-clamp-1">{group.isMulti ? `${group.variants.length} pilihan ${rep.grade ? "warna/grade" : "warna"}` : `${rep.category} • ${rep.color}`}</p>

        <div className="mt-2 flex items-center justify-between gap-2">
          <p data-testid={`product-price-${rep.id}`} className="text-[14px] font-bold tabular-nums text-[#1C1C1E]">
            {priceText}<span className="text-[10px] font-medium text-[#8E8E93]">/{rep.base_unit || "meter"}</span>
            {listChanged && (
              <span data-testid={`product-list-price-${rep.id}`} className="ml-1 block text-[10px] font-normal text-[#8E8E93] line-through">{listText}</span>
            )}
          </p>
          <span data-testid={`product-stock-badge-${rep.id}`} className={`status-pill ${availPill}`}>{availLabel}</span>
        </div>
        {/* UAT 24 Okt (P8) + FIX-2 — dua angka: LOKAL (lokasi jualan × PT penjual) lalu GLOBAL (semua PT); klik → rincian
            per lokasi/PT/status/akan datang/ATP. Dulu tiga baris (Di {site} · PT · Grup) dengan rumus berbeda. */}
        <StockFigures className="mt-1.5" testId={`product-stock-figures-${rep.id}`} unit={fig.unit}
          local={fig.local} global={fig.global} localLabel={fig.localLabel} globalLabel="Total grup (semua PT)"
          productIds={group.variants.map((v) => v.id)} siteId={siteId}
          productLabels={Object.fromEntries(group.variants.map((v) => [v.id, variantLabel(v)]))} />
        {(incRestock > 0 || incSo > 0) && (
          <div className="mt-1 flex flex-wrap gap-1">
            {incRestock > 0 && <span data-testid={`product-incoming-restock-${rep.id}`} title="Barang datang untuk stok — boleh dijanjikan ke pelanggan" className="inline-flex rounded-full bg-[#E8F1FF] px-2 py-0.5 text-[10px] font-semibold text-[#0058CC]">Datang restock: {formatQty(incRestock)} {rep.base_unit || "meter"}</span>}
            {incSo > 0 && <span data-testid={`product-incoming-so-${rep.id}`} title="Barang datang yang sudah terikat pesanan — tidak bisa dijanjikan lagi" className="inline-flex rounded-full bg-[#F2F2F7] px-2 py-0.5 text-[10px] font-semibold text-[#6B6B73]">Datang utk SO: {formatQty(incSo)} {rep.base_unit || "meter"}</span>}
          </div>
        )}
        {makloonQty > 0 && (
          <p data-testid={`product-makloon-reserved-${rep.id}`} className="mt-1 inline-flex rounded-full bg-[#FFF4E5] px-2 py-0.5 text-[10px] font-semibold text-[#9A5B00]"
             title="Bahan ini sudah dicadangkan untuk order makloon dan tidak bisa dijanjikan ke pelanggan">
            Dicadangkan makloon: {formatQty(makloonQty)} {rep.base_unit || "meter"}
          </p>
        )}

        <div className="mt-2">
          {allBlocked ? (
            <>
              <p data-testid={`product-not-orderable-${rep.id}`}
                className="mb-1.5 flex items-start gap-1 rounded-md bg-[#FFF6E5] px-2 py-1.5 text-[10.5px] font-semibold leading-snug text-[#8C4A00]">
                <FlaskConical size={12} className="mt-[1px] shrink-0" />
                Belum boleh dijual — {lifecycleLabel(rep)}. Selesaikan alur R&D
                (Spesifikasi → Sample → Rilis ke Produksi) di menu R&D & Desain.
              </p>
              {/* Tombol TIDAK dimatikan: pengguna harus bisa tahu ALASAN & LANGKAHNYA
                  (jalan buntu tanpa penjelasan = UX buruk). Klik → popup berisi
                  alasan lengkap + jalan keluar; keranjang tetap tidak bisa diisi. */}
              <button data-testid={`add-to-cart-button-${rep.id}`} className="secondary-button w-full"
                aria-disabled="true" data-orderable="false"
                title="Produk ini belum boleh dijual — klik untuk melihat alasan & langkah selanjutnya"
                onClick={() => open(true)}>
                Belum boleh dijual — lihat alasan
              </button>
            </>
          ) : (
            <button data-testid={`add-to-cart-button-${rep.id}`} className="primary-button w-full" data-orderable="true" disabled={availState === "habis"} onClick={() => open(true)}>
              <Plus size={13} /> {group.isMulti ? "Pilih Varian & Detail" : "Lihat Detail & Tambah"}
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
