/**
 * MobileMdProducts — master produk versi HP MD: cari, rincian + stok per gudang, ubah SKU.
 * Diekstrak dari MobileMdViews.jsx tanpa perubahan isi (fase 3 · P7, batas 500 baris per berkas).
 *
 * Fase 4 · R1 — form HP "Ubah nama / harga dasar" (2 isian TANPA label) DIGANTI form desktop Katalog › "Ubah SKU"
 * (`catalog/VariantEditor`): kode SKU (terkunci), nama varian, nama & warna versi supplier, harga jual dasar, status,
 * produk unggulan (urutan · tampil sampai · label), deskripsi — semua berlabel. Induk + varian dibaca dari
 * `/product-templates/{id}` SAMA dengan desktop, jadi isian harga = harga DASAR (dulu HP memakai `price` daftar
 * `/products` yang bisa berupa harga efektif PT → tersimpan sebagai harga dasar). Sesudah simpan daftar dimuat ulang.
 */
import ProductColorTriad from "../../../components/ProductColorTriad";
import { useEffect, useMemo, useState } from "react";
import { Package, Pencil, Search } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import ErrorNotice from "../../../components/ErrorNotice";
import { Back, Chips, Notice, list } from "./mdMobileParts";
import { VariantEditor } from "../../catalog/VariantEditor";
import { catalogApi, catalogError } from "../../catalog/catalogApi";

// Daftar ratusan varian dirender bertahap (bukan 283 baris sekaligus di HP).
const PAGE = 40;

function ProductDetail({ product, canEdit, onBack, onSaved }) {
  const [sb, setSb] = useState(null);
  const [edit, setEdit] = useState(null);   // { template, variant } — sama dengan desktop CatalogWorkspace
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { axios.get(`${API}/products/${product.id}/stock-breakdown`).then((r) => setSb(r.data)).catch(() => setSb({})); }, [product.id]);
  const openEdit = async () => {
    setBusy(true); setMsg(null);
    try {
      const fam = product.template_id ? await catalogApi.detail(product.template_id) : null;
      const variant = (fam?.variants || []).find((v) => v.id === product.id);
      const basePrice = product.global_price ?? product.price;
      setEdit({
        template: fam || { name: product.name, base_price: basePrice, description: product.description || "" },
        variant: variant || { ...product, price: basePrice },
      });
    } catch (e) { setMsg({ ok: false, text: catalogError(e) }); } finally { setBusy(false); }
  };
  const bal = sb?.balances || sb?.warehouses || [];
  return (
    <div className="space-y-2" data-testid="m-md-product-detail">
      <Back label="Produk" onClick={onBack} testId="m-md-product-back" />
      <ProductColorTriad product={product} compact showSupplier />
      <div className="m-card p-4">
        {product.image && <img src={product.image} alt={product.name} className="mb-2 h-40 w-full rounded-xl object-cover" />}
        <p className="text-[15px] font-bold" data-testid="m-md-product-name">{product.name}</p>
        <p className="text-[11.5px] m-muted">{product.sku} · {product.category || "-"} · {product.fabric_type || ""}</p>
        <p className="mt-1 text-[16px] font-bold tabular-nums" data-testid="m-md-product-price">{formatCurrency(product.price)} <span className="text-[11px] font-normal m-muted">/ {product.base_unit}</span></p>
        <p className="text-[11.5px]">Tersedia {formatQty(product.available_qty)} {product.base_unit}</p>
        {canEdit && (<>
          <button className="secondary-button mt-2 flex w-full items-center justify-center gap-1.5 py-2.5 text-[12px]" disabled={busy} onClick={openEdit} data-testid="m-md-product-edit">
            <Pencil size={13} /> {busy ? "Memuat…" : "Ubah SKU"}
          </button>
          <p className="mt-1 text-[11px] m-muted">Perubahan harga dasar tercatat di audit; harga per pelanggan/PT tetap lewat daftar harga.</p>
        </>)}
      </div>
      <Notice msg={msg} testId="m-md-product-msg" />
      {edit && <VariantEditor template={edit.template} product={edit.variant} onClose={() => setEdit(null)}
        onSaved={async () => { setEdit(null); setMsg({ ok: true, text: "SKU tersimpan." }); await onSaved?.(); }} />}
      <div className="m-card p-3" data-testid="m-md-product-stock">
        <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Stok per gudang</p>
        {sb === null && <p className="text-xs m-muted">Memuat…</p>}
        {sb && bal.length === 0 && <p className="text-xs m-muted">Belum ada stok.</p>}
        {bal.map((b, i) => <div key={i} className="flex justify-between py-0.5 text-[12px]"><span>{b.warehouse_name || b.warehouse_id}</span><span className="tabular-nums">{formatQty(b.available_qty ?? b.quantity)} {product.base_unit}</span></div>)}
      </div>
    </div>
  );
}

export function MobileMdProducts({ canEdit }) {
  const [rows, setRows] = useState(null);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [sel, setSel] = useState(null);
  const [loadErr, setLoadErr] = useState(null);
  const [limit, setLimit] = useState(PAGE);
  const load = () => axios.get(`${API}/products`).then((r) => { const fresh = list(r.data); setRows(fresh); return fresh; })
    .catch((e) => { setRows([]); setLoadErr(e); return null; });
  useEffect(() => { load(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { setLimit(PAGE); }, [q, cat]);
  const cats = useMemo(() => [...new Set((rows || []).map((p) => p.category).filter(Boolean))], [rows]);
  if (sel) return <ProductDetail product={sel} canEdit={canEdit} onBack={() => setSel(null)} onSaved={async () => { const p = ((await load()) || []).find((x) => x.id === sel.id); if (p) setSel(p); }} />;
  const shown = (rows || []).filter((p) => (!cat || p.category === cat) && (!q || `${p.name} ${p.sku}`.toLowerCase().includes(q.toLowerCase())));
  return (
    <div className="space-y-2" data-testid="m-md-products">
      {loadErr && <ErrorNotice message={loadErr} onRetry={() => { setLoadErr(""); load(); }} testId="m-md-products-load-error" />}
      <div className="m-card flex items-center gap-2 px-3 py-2"><Search size={15} className="m-muted" /><input className="w-full bg-transparent text-sm outline-none" placeholder="Cari produk / SKU" value={q} onChange={(e) => setQ(e.target.value)} data-testid="m-md-products-search" /></div>
      <Chips items={[["", "Semua"], ...cats.map((c) => [c, c])]} value={cat} onChange={setCat} prefix="m-md-products-cat" />
      {rows === null && <p className="text-xs m-muted">Memuat…</p>}
      {rows && <p className="px-1 text-[11px] m-muted" data-testid="m-md-products-count">{shown.length} produk{shown.length > limit ? ` · menampilkan ${limit} pertama` : ""}</p>}
      {rows && shown.length === 0 && <p className="py-8 text-center text-xs m-muted">Tidak ada produk yang cocok.</p>}
      {shown.slice(0, limit).map((p) => (
        <button key={p.id} className="m-card m-press flex w-full items-center gap-3 p-2.5 text-left" onClick={() => setSel(p)} data-testid={`m-md-product-${p.id}`}>
          {p.image ? <img src={p.image} alt="" className="h-12 w-12 shrink-0 rounded-lg object-cover" />
            : <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-[#F2F3F5]" title="Belum ada foto"><Package size={18} className="text-[#C7C7CC]" /></span>}
          <div className="min-w-0 flex-1"><p className="truncate text-[13px] font-bold">{p.name}</p><p className="truncate text-[11px] m-muted">{p.sku} · {p.category || "-"}</p></div>
          <div className="shrink-0 text-right">
            <p className="whitespace-nowrap text-[12.5px] font-bold tabular-nums">{formatCurrency(p.price)}<span className="text-[11px] font-normal m-muted">/{p.base_unit || "unit"}</span></p>
            <p className="whitespace-nowrap text-[11px] m-muted">tersedia {formatQty(p.available_qty)} {p.base_unit}</p>
          </div>
        </button>
      ))}
      {shown.length > limit && (
        <button className="secondary-button w-full py-2.5 text-[12px]" onClick={() => setLimit((n) => n + PAGE)} data-testid="m-md-products-more">
          Tampilkan {Math.min(PAGE, shown.length - limit)} produk lagi
        </button>
      )}
    </div>
  );
}
