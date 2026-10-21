import { ReturnStatusPill } from "../ReturnShared";
import CreateReturnForm from "../CreateReturnForm";
import CreateSpecialOrderForm from "../CreateSpecialOrderForm";
import { useEffect, useMemo, useState } from "react";
import { Search, ChevronRight, ArrowLeft, Plus } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import KNSelect from "../../../components/KNSelect";
import { MobileReturnActions, MobileSpecialOrderDetail, OdStatus } from "./MobileSalesFlows";

const fmtDate = (s) => (s ? new Date(s).toLocaleDateString("id-ID", { day: "2-digit", month: "short" }) : "-");

/** Retur jual versi HP: daftar kartu + buat retur dari pesanan pelanggan (alasan + baris). */
// Cek UI UAT v3 (2026-10-22) — dokumen retur tidak menyimpan total rupiah (nilai diputus Finance saat kompensasi);
// dulu daftar HP menulis "Rp 0". Kini: nilai bila ada, selain itu qty klaim per satuan.
export const returnValueText = (r) => {
  const amt = Number(r.total_amount || r.grand_total || 0);
  if (amt > 0) return formatCurrency(amt);
  const by = {};
  (r.items || []).forEach((it) => { const u = it.unit || ""; by[u] = (by[u] || 0) + Number(it.quantity_returned || it.quantity || 0); });
  const parts = Object.entries(by).filter(([, q]) => q > 0).map(([u, q]) => `${formatQty(q)} ${u}`.trim());
  return parts.length ? `klaim ${parts.join(" · ")}` : "—";
};

export function MobileReturns({ user, initialOrder = null, focusId = null }) {
  const [rows, setRows] = useState(null);
  const [create, setCreate] = useState(!!initialOrder);
  const [sel, setSel] = useState(null);
  const load = () => axios.get(`${API}/sales-returns`).then((r) => {
    const list = Array.isArray(r.data) ? r.data : r.data.items || [];
    setRows(list);
    if (focusId) setSel((cur) => cur || list.find((x) => x.id === focusId) || null);
    setSel((cur) => (cur ? list.find((x) => x.id === cur.id) || cur : cur));
  }).catch(() => setRows([]));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  if (create) {
    return <MobileReturnCreate initialOrder={initialOrder} onBack={() => setCreate(false)} onDone={() => { setCreate(false); load(); }} />;
  }
  if (sel) return (
    <div className="space-y-2 p-3" data-testid="m-return-detail">
      <button className="m-subpage-back" onClick={() => setSel(null)} data-testid="m-return-back"><ArrowLeft size={17} /> Retur</button>
      <div className="m-card p-4 space-y-1 text-[12.5px]">
        <p className="text-[15px] font-bold">{sel.number}</p>
        <p className="m-muted">{sel.customer_name} · {fmtDate(sel.created_at)} · <ReturnStatusPill status={sel.status} /></p>
        <p className="m-muted">Alasan: {sel.reason || sel.complaint_reason || sel.complaint_note || sel.notes || "-"}</p>
        {sel.order_number && <p className="m-muted">Atas pesanan {sel.order_number}</p>}
        {(sel.items || []).map((it, i) => <div key={i} className="flex justify-between border-t border-[#EFF0F2] pt-1"><span>{it.product_name}</span><span className="tabular-nums">{it.quantity_returned ?? it.quantity} {it.unit}{it.reason ? ` · ${it.reason}` : ""}</span></div>)}
        <div className="flex justify-between border-t border-[#EFF0F2] pt-1 font-bold"><span>Total</span><span className="tabular-nums">{returnValueText(sel)}</span></div>
      </div>
      <MobileReturnActions ret={sel} onChanged={load} />
    </div>);
  return (
    <div className="space-y-2 p-3" data-testid="m-returns">
      <button className="primary-button w-full py-3 flex items-center justify-center gap-2" onClick={() => setCreate(true)} data-testid="m-return-new"><Plus size={16} /> Buat retur jual</button>
      {rows === null && <p className="text-xs m-muted">Memuat retur…</p>}
      {rows && rows.length === 0 && <p className="text-xs m-muted" data-testid="m-returns-empty">Belum ada retur.</p>}
      {(rows || []).map((r) => (
        <button key={r.id} className="m-card m-press w-full p-3 text-left" onClick={() => setSel(r)} data-testid={`m-return-${r.id}`}>
          <div className="flex items-center gap-2"><div className="min-w-0 flex-1"><p className="text-[13px] font-bold">{r.number} <span className="ml-1 inline-block align-middle"><ReturnStatusPill status={r.status} /></span></p><p className="truncate text-[11px] m-muted">{r.customer_name} · {fmtDate(r.created_at)} · {returnValueText(r)}</p></div><ChevronRight size={16} className="text-[#C7C7CC]" /></div>
        </button>
      ))}
    </div>
  );
}

/** Buat retur di HP = form desktop (cek kebijakan, barang dari Surat Jalan, pilih per roll, foto kamera wajib bila kebijakan meminta). */
function MobileReturnCreate({ onBack, onDone, initialOrder = null }) {
  return (
    <div className="space-y-2 p-3" data-testid="m-return-create">
      <div className="m-card m-return-form p-3">
        <CreateReturnForm variant="modal" orders={initialOrder ? [initialOrder] : []} initialOrderId={initialOrder?.id || ""}
          onCreated={() => onDone()} onCancel={onBack} />
      </div>
    </div>
  );
}

/** Pesanan khusus versi HP: daftar kartu + form ringkas (pelanggan, spesifikasi, target kirim). */
export function MobileSpecialOrders({ focusId = null }) {
  const [rows, setRows] = useState(null);
  const [create, setCreate] = useState(false);
  const [openId, setOpenId] = useState(focusId);
  const load = () => axios.get(`${API}/special-orders`).then((r) => setRows(Array.isArray(r.data) ? r.data : r.data.items || [])).catch(() => setRows([]));
  useEffect(() => { load(); }, []);
  if (openId) return <MobileSpecialOrderDetail id={openId} onBack={() => { setOpenId(null); load(); }} />;
  if (create) {
    return <MobileSpecialOrderCreate onBack={() => setCreate(false)} onDone={() => { setCreate(false); load(); }} />;
  }
  return (
    <div className="space-y-2 p-3" data-testid="m-special-orders">
      <button className="primary-button w-full py-3 flex items-center justify-center gap-2" onClick={() => setCreate(true)} data-testid="m-special-new"><Plus size={16} /> Ajukan pesanan khusus</button>
      {rows === null && <p className="text-xs m-muted">Memuat…</p>}
      {rows && rows.length === 0 && <p className="text-xs m-muted" data-testid="m-special-empty">Belum ada pesanan khusus.</p>}
      {(rows || []).map((s) => (
        <button key={s.id} className="m-card m-press w-full p-3 text-left" onClick={() => setOpenId(s.id)} data-testid={`m-special-${s.id}`}>
          <div className="flex items-center justify-between gap-2 text-[13px]"><b>{s.number || s.id}</b><OdStatus status={s.status} /></div>
          <p className="text-[11px] m-muted truncate">{s.customer_name} · {s.title || s.items?.[0]?.description || s.custom_item?.description || s.custom_item?.name || "-"}{(s.items || []).length > 1 ? ` (+${s.items.length - 1} baris)` : ""} · kirim {fmtDate(s.expected_delivery)}</p>
          {s.quoted_price != null && <p className="text-[11px] tabular-nums">Penawaran {formatCurrency(s.quoted_price)}</p>}
        </button>
      ))}
    </div>
  );
}

/** Pesanan khusus di HP = form desktop (multi-baris, spesifikasi teknis, kategori desain, gambar referensi + kamera). */
function MobileSpecialOrderCreate({ onBack, onDone }) {
  return <CreateSpecialOrderForm onCancel={onBack} onCreated={() => onDone()} />;
}

/** Daftar harga versi HP: harga efektif per pelanggan (umum → PT → pelanggan → khusus) dalam kartu. */
export function MobilePricelist({ selectedEntity }) {
  const [customers, setCustomers] = useState([]);
  const [cid, setCid] = useState("");
  const [q, setQ] = useState("");
  const [grid, setGrid] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { axios.get(`${API}/customers`).then((r) => setCustomers(Array.isArray(r.data) ? r.data : r.data.items || [])).catch(() => {}); }, []);
  const cust = customers.find((c) => c.id === cid);
  useEffect(() => {
    if (!cid) { setGrid(null); return; }
    setGrid(null); setErr("");
    axios.get(`${API}/customer-prices`, { params: { customer_id: cid, entity_id: (selectedEntity && selectedEntity !== "all" ? selectedEntity : cust?.entity_id) || undefined } })
      .then((r) => setGrid(r.data)).catch((e) => setErr(e.response?.data?.detail || "Gagal memuat harga."));
  }, [cid]); // eslint-disable-line
  const rows = useMemo(() => (grid?.rows || grid?.items || []).filter((r) => !q || `${r.product_name} ${r.sku}`.toLowerCase().includes(q.toLowerCase())), [grid, q]);
  const eff = (r) => r.special_price ?? r.customer_price ?? r.entity_price ?? r.global_price;
  const src = (r) => (r.special_price != null ? ["Harga khusus", "#B25E00", "#FFF4E5"] : r.customer_price != null ? ["Harga pelanggan", "#0058CC", "#EAF2FF"] : r.entity_price != null ? ["Harga PT", "#1B7F4B", "#E6F6EC"] : ["Harga umum", "#6B6B73", "#F2F3F5"]);
  return (
    <div className="space-y-2 p-3" data-testid="m-pricelist">
      <KNSelect value={cid} onValueChange={setCid} options={customers.map((c) => ({ value: c.id, label: c.name }))} placeholder="Pilih pelanggan untuk harga efektif" data-testid="m-pricelist-customer" />
      {cid && <div className="m-card flex items-center gap-2 px-3 py-2"><Search size={15} className="m-muted" /><input className="w-full bg-transparent text-sm outline-none" placeholder="Cari produk / SKU" value={q} onChange={(e) => setQ(e.target.value)} data-testid="m-pricelist-search" /></div>}
      {err && <div className="notice-bar danger text-xs">{String(err)}</div>}
      {!cid && <p className="text-xs m-muted p-2" data-testid="m-pricelist-hint">Pilih pelanggan: harga yang tampil adalah harga yang akan dipakai di keranjang (umum → PT → pelanggan → khusus disetujui).</p>}
      {cid && grid === null && !err && <p className="text-xs m-muted">Memuat harga…</p>}
      {rows.map((r) => { const [l, fg, bg] = src(r); return (
        <div key={r.product_id} className="m-card p-3" data-testid={`m-price-${r.product_id}`}>
          <div className="flex items-start gap-2"><div className="min-w-0 flex-1"><p className="truncate text-[13px] font-bold">{r.product_name}</p><p className="text-[10.5px] m-muted">{r.sku} · {r.category || ""} · per {r.base_unit}</p></div>
            <div className="text-right"><p className="text-[14px] font-bold tabular-nums" data-testid={`m-price-eff-${r.product_id}`}>{formatCurrency(eff(r))}</p>{eff(r) !== r.global_price && <p className="text-[10px] m-muted line-through tabular-nums">{formatCurrency(r.global_price)}</p>}</div></div>
          <span className="mt-1 inline-block rounded px-1.5 text-[9.5px] font-bold" style={{ color: fg, background: bg }} data-testid={`m-price-src-${r.product_id}`}>{l}</span>
        </div>); })}
      {cid && grid && rows.length === 0 && <p className="text-xs m-muted" data-testid="m-pricelist-empty">Tidak ada produk.</p>}
    </div>
  );
}
