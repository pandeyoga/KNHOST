/**
 * MobileMdProducts — master produk versi HP MD: cari, rincian + stok per gudang, ubah nama/harga dasar.
 * Diekstrak dari MobileMdViews.jsx tanpa perubahan isi (fase 3 · P7, batas 500 baris per berkas).
 */
import ProductColorTriad from "../../../components/ProductColorTriad";
import { useEffect, useMemo, useState } from "react";
import { Package, Search } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import ErrorNotice from "../../../components/ErrorNotice";
import { errText } from "./MobileSalesFlows";
import { Back, Chips, Notice, list } from "./mdMobileParts";

// Daftar ratusan varian dirender bertahap (bukan 283 baris sekaligus di HP).
const PAGE = 40;

function ProductDetail({ product, canEdit, onBack, onSaved }) {
  const [sb, setSb] = useState(null);
  const [edit, setEdit] = useState(false);
  const [f, setF] = useState({ name: product.name || "", price: product.price ?? "" });
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { axios.get(`${API}/products/${product.id}/stock-breakdown`).then((r) => setSb(r.data)).catch(() => setSb({})); }, [product.id]);
  const save = async () => {
    setBusy(true); setMsg(null);
    try { const r = await axios.patch(`${API}/products/${product.id}`, { data: { name: f.name, price: Number(f.price) } }); setMsg({ ok: true, text: "Produk diperbarui." }); setEdit(false); onSaved?.(r.data); }
    catch (e) { setMsg({ ok: false, text: errText(e, "Gagal menyimpan produk.") }); } finally { setBusy(false); }
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
        {canEdit && !edit && <button className="secondary-button mt-2 w-full py-2.5 text-[12px]" onClick={() => setEdit(true)} data-testid="m-md-product-edit">Ubah nama / harga dasar</button>}
        {edit && (
          <div className="mt-2 space-y-2" data-testid="m-md-product-form">
            <input className="field" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="m-md-product-form-name" />
            <input type="number" inputMode="decimal" className="field" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} data-testid="m-md-product-form-price" />
            <p className="text-[11px] m-muted">Perubahan harga dasar tercatat di audit; harga per pelanggan/PT tetap lewat daftar harga.</p>
            <div className="grid grid-cols-2 gap-2"><button className="secondary-button py-2.5" onClick={() => setEdit(false)} data-testid="m-md-product-form-cancel">Batal</button><button className="primary-button py-2.5" disabled={busy || !f.name.trim() || !(Number(f.price) >= 0)} onClick={save} data-testid="m-md-product-form-save">Simpan</button></div>
          </div>
        )}
      </div>
      <Notice msg={msg} testId="m-md-product-msg" />
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
  const load = () => axios.get(`${API}/products`).then((r) => setRows(list(r.data))).catch((e) => { setRows([]); setLoadErr(e); });
  useEffect(() => { load(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { setLimit(PAGE); }, [q, cat]);
  const cats = useMemo(() => [...new Set((rows || []).map((p) => p.category).filter(Boolean))], [rows]);
  if (sel) return <ProductDetail product={sel} canEdit={canEdit} onBack={() => setSel(null)} onSaved={(p) => { setSel((c) => ({ ...c, ...p })); setRows((r) => r.map((x) => (x.id === p.id ? { ...x, ...p } : x))); }} />;
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
