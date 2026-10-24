/**
 * UAT 24 Okt (P12) — strip sorotan POS selain Terlaris:
 *  · PosFeatured     — "Produk Unggulan" (push) yang ditandai MD/Manajer di master produk, tampil sampai tanggal akhirnya.
 *  · PosRecommended  — "Rekomendasi untuk <pelanggan>" (keputusan pemilik P12-K1 b): produk berstok dengan desain /
 *    pattern / kategori yang sama dengan pembelian pelanggan itu.
 * Strip yang dimatikan di Pusat Pengaturan (`pos.*`) tidak dirender (server juga mengembalikan daftar kosong).
 */
import { useEffect, useState } from "react";
import { Plus, Sparkles, Star } from "lucide-react";
import { fetchFeatured, fetchRecommendations, recToProduct } from "./posApi";
import { formatCurrency } from "../../utils/formatters";
import { onImageError, productImage } from "../../utils/productImage";

export function ProductStrip({ title, hint, icon: Icon, tone = "#0058CC", items, loading, onAdd, priceMap = {}, testId, badge }) {
  if (!loading && !(items || []).length) return null;
  return (
    <section data-testid={testId} className="mb-3">
      <header className="mb-2 flex items-center gap-1.5 px-1">
        <Icon size={15} style={{ color: tone }} />
        <h2 className="text-[13px] font-bold text-[#1C1C1E]">{title}</h2>
        {hint && <span className="text-[11px] text-[#8E8E93]">{hint}</span>}
      </header>
      <div className="no-scrollbar flex gap-2.5 overflow-x-auto pb-1">
        {loading
          ? Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-44 w-36 shrink-0 animate-pulse rounded-xl bg-[#ECEDF0]" />)
          : items.map((p) => {
              const oos = Number(p.available_qty || 0) <= 0;
              return (
                <article key={p.product_id} data-testid={`${testId}-${p.product_id}`} className="flex w-36 shrink-0 flex-col overflow-hidden rounded-xl border border-[#E5E5EA] bg-white">
                  <div className="relative">
                    <img src={productImage(p)} onError={onImageError} alt={p.product_name} className="h-20 w-full object-cover" />
                    {badge?.(p) && <span className="absolute left-1.5 top-1.5 max-w-[120px] truncate rounded-md px-1.5 py-0.5 text-[9px] font-bold text-white" style={{ background: tone }}>{badge(p)}</span>}
                  </div>
                  <div className="flex flex-1 flex-col p-2">
                    <p className="text-[9px] font-bold uppercase text-[#0058CC]">{p.sku}</p>
                    <h3 className="line-clamp-2 text-[11.5px] font-semibold leading-tight">{p.product_name}</h3>
                    <p className="mt-auto pt-1 text-[12px] font-bold tabular-nums">
                      {formatCurrency(priceMap[p.product_id]?.price != null ? priceMap[p.product_id].price : p.price)}
                    </p>
                    <button data-testid={`${testId}-add-${p.product_id}`} className="primary-button mt-1.5 justify-center py-1.5 text-[11px]" disabled={oos} onClick={() => onAdd(recToProduct(p), 1, p.base_unit)}>
                      <Plus size={12} /> {oos ? "Habis" : "Tambah"}
                    </button>
                  </div>
                </article>
              );
            })}
      </div>
    </section>
  );
}

function useStrip(loader, deps) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let on = true;
    setLoading(true);
    loader().then((d) => { if (on) setItems(d); }).catch(() => { if (on) setItems([]); }).finally(() => { if (on) setLoading(false); });
    return () => { on = false; };
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  return { items, loading };
}

export function PosFeatured({ entityId, customerId = "", onAdd, priceMap }) {
  const { items, loading } = useStrip(() => fetchFeatured(entityId, customerId), [entityId, customerId]);
  return <ProductStrip title="Produk Unggulan" hint="dipilih MD / Manajer" icon={Star} tone="#B45309" items={items} loading={loading}
    onAdd={onAdd} priceMap={priceMap} testId="pos-featured" badge={(p) => p.featured_note || "Unggulan"} />;
}

export function PosRecommended({ entityId, customer, onAdd, priceMap }) {
  const cid = customer?.id || "";
  const { items, loading } = useStrip(() => (cid ? fetchRecommendations(cid, entityId) : Promise.resolve([])), [entityId, cid]);
  if (!cid) return null;
  return <ProductStrip title={`Rekomendasi untuk ${customer?.name || "pelanggan"}`} hint="dari desain & kategori yang pernah dibeli"
    icon={Sparkles} tone="#6B219A" items={items} loading={loading} onAdd={onAdd} priceMap={priceMap} testId="pos-recommended"
    badge={(p) => p.reason} />;
}
