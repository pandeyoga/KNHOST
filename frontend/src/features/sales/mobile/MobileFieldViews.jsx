import { useEffect, useState } from "react";
import { MapPin, LogIn, LogOut, Loader2 } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { offlinePost } from "../../../utils/offlineQueue";
import KNSelect from "../../../components/KNSelect";
import SpecialPriceRequestForm from "../../pricing/SpecialPriceRequestForm";
import ErrorNotice from "../../../components/ErrorNotice";
import { formatQty } from "../../../utils/formatters";

/** §3-A Tahap 1 — tiga layar lapangan: Minta Harga Khusus · Kunjungan · Status Stok. */
export function MobileSpecialPrice({ selectedEntity }) {
  const [custs, setCusts] = useState([]); const [prods, setProds] = useState([]);
  const [cid, setCid] = useState(""); const [pid, setPid] = useState("");
  useEffect(() => {
    // UAT 24 Okt (P14) — pemilih pelanggan untuk pesanan: sales hanya pelanggannya sendiri (+ walk-in PT); pelanggan
    // tanpa sales masuk antrean "Pelanggan tanpa sales" di Meja Admin Sales.
    axios.get(`${API}/customers`, { params: { for_order: true, with_credit: false } }).then((r) => setCusts(Array.isArray(r.data) ? r.data : r.data.items || [])).catch(() => {});
    axios.get(`${API}/products`).then((r) => setProds(Array.isArray(r.data) ? r.data : r.data.items || [])).catch(() => {});
  }, []);
  // Audit UI 24 Okt (HP Minta Harga Khusus) — dulu hanya 2 dropdown tanpa label/penjelasan dan tombol kirim baru
  // muncul setelah keduanya dipilih. Kini: penjelasan singkat, label bertanda *, dropdown satu gaya (keduanya
  // bisa dicari), dan form harga + bukti + tombol "Ajukan" selalu terlihat.
  return (
    <div className="p-3 space-y-3" data-testid="m-special-price">
      <div className="m-card p-3 space-y-3">
        <p className="text-[12px] leading-snug text-[#6B6B73]" data-testid="m-sp-intro">Ajukan harga nego untuk satu pelanggan &amp; produk, lalu lampirkan bukti chat/penawaran. Diputus Manajer; statusnya ada di <b>Harga Khusus Saya</b>.</p>
        <label className="grid gap-1">
          <span className="field-label">Pelanggan *</span>
          <KNSelect data-testid="m-sp-customer" className="field" searchable aria-label="Pelanggan" placeholder="Pilih pelanggan" value={cid} onValueChange={setCid} options={custs.map((c) => ({ value: c.id, label: c.name }))} />
        </label>
        <label className="grid gap-1">
          <span className="field-label">Produk *</span>
          <KNSelect data-testid="m-sp-product" className="field" searchable aria-label="Produk" placeholder="Pilih produk" value={pid} onValueChange={setPid} options={prods.map((p) => ({ value: p.id, label: `${p.name}${p.variant_label ? ` · ${p.variant_label}` : ""}` }))} />
        </label>
        <SpecialPriceRequestForm compact product={prods.find((p) => p.id === pid)} customer={custs.find((c) => c.id === cid)} entityId={selectedEntity || ""} />
      </div>
    </div>
  );
}

export function MobileVisits() {
  const [me, setMe] = useState(null); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(""); const [custName, setCustName] = useState("");
  // Audit UI 24 Okt — nama pelanggan disarankan dari CRM (datalist); bila cocok, customer_id ikut dikirim.
  const [custs, setCusts] = useState([]);
  useEffect(() => {
    axios.get(`${API}/customers`, { params: { for_order: true, with_credit: false } })
      .then((r) => setCusts(Array.isArray(r.data) ? r.data : r.data.items || [])).catch(() => {});
  }, []);
  const custMatch = custs.find((c) => (c.name || "").trim().toLowerCase() === custName.trim().toLowerCase());
  const load = () => axios.get(`${API}/hr/visits/me`).then((r) => { setMe(r.data); setErr(""); }).catch((e) => setErr(e.response?.status === 404 ? "Akun Anda belum ditautkan ke profil karyawan — minta admin SDM." : (e.response?.data?.detail || "Gagal memuat kunjungan.")));
  useEffect(() => { load(); }, []);
  const geo = () => new Promise((res) => { if (!navigator.geolocation) return res({}); navigator.geolocation.getCurrentPosition((p) => res({ lat: p.coords.latitude, lon: p.coords.longitude }), () => res({}), { timeout: 4000 }); });
  const checkIn = async () => { setBusy(true); setErr(""); try { const r = await offlinePost(`${API}/hr/visits/check-in`, { customer_name: custName, customer_id: custMatch?.id || undefined, notes: note, ...(await geo()) }, { label: `Check-in ${custName}` }); setCustName(""); setNote(""); if (r.queued) setErr("Offline — check-in tersimpan di HP, dikirim saat sinyal kembali."); else await load(); } catch (e) { setErr(e.response?.data?.detail || "Check-in gagal."); } finally { setBusy(false); } };
  const checkOut = async () => { setBusy(true); setErr(""); try { const r = await offlinePost(`${API}/hr/visits/${me.ongoing.id}/check-out`, { outcome: "other", notes: note, ...(await geo()) }, { label: `Check-out ${me.ongoing.customer_name || ""}` }); setNote(""); if (r.queued) setErr("Offline — check-out tersimpan di HP, dikirim saat sinyal kembali."); else await load(); } catch (e) { setErr(e.response?.data?.detail || "Check-out gagal."); } finally { setBusy(false); } };
  if (err) return <div className="notice-bar danger m-3" data-testid="m-visits-error">{String(err)}</div>;
  if (!me) return <div className="p-6 text-center text-sm"><Loader2 size={16} className="animate-spin inline" /> Memuat…</div>;
  return (
    <div className="p-3 space-y-3" data-testid="m-visits">
      {me.ongoing ? (
        <div className="m-card p-4 space-y-2" data-testid="m-visit-ongoing">
          <div className="flex items-center gap-2 text-[#0058CC]"><MapPin size={16} /> <b>Sedang berkunjung</b></div>
          <div className="text-sm">{me.ongoing.customer_name} · mulai {String(me.ongoing.check_in?.ts || "").slice(11, 16)}</div>
          <textarea className="textarea w-full" rows={2} placeholder="Catatan hasil kunjungan" value={note} onChange={(e) => setNote(e.target.value)} data-testid="m-visit-note" />
          <button className="danger-button w-full py-3" disabled={busy} onClick={checkOut} data-testid="m-visit-checkout"><LogOut size={16} className="inline mr-1" /> Selesai (check-out)</button>
        </div>
      ) : (
        // Audit UI 24 Okt (HP Kunjungan) — isian berlabel (dulu placeholder saja) & satu ukuran huruf.
        <div className="m-card p-4 space-y-2" data-testid="m-visit-start">
          <label className="grid gap-1">
            <span className="field-label">Pelanggan / toko *</span>
            <input className="field" list="m-visit-customer-list" placeholder="Ketik / pilih dari daftar pelanggan" value={custName} onChange={(e) => setCustName(e.target.value)} data-testid="m-visit-customer" />
            <datalist id="m-visit-customer-list">{custs.map((c) => <option key={c.id} value={c.name} />)}</datalist>
          </label>
          <label className="grid gap-1">
            <span className="field-label">Tujuan kunjungan</span>
            <textarea className="field" rows={2} placeholder="cth: tawarkan koleksi baru" value={note} onChange={(e) => setNote(e.target.value)} data-testid="m-visit-note" />
          </label>
          <button className="primary-button w-full py-3" disabled={busy || !custName.trim()} onClick={checkIn} data-testid="m-visit-checkin"><LogIn size={16} className="inline mr-1" /> Mulai kunjungan (check-in)</button>
        </div>
      )}
      <div className="text-xs text-[#6E6E73]">Hari ini: {me.count_today || 0} kunjungan</div>
      {(me.today || []).map((v) => (
        <div key={v.id} className="m-card p-3 text-sm" data-testid={`m-visit-${v.id}`}><b>{v.customer_name}</b> · {v.status === "done" ? `${v.duration_min} menit` : "berjalan"}</div>
      ))}
    </div>
  );
}

export function MobileStock() {
  const [rows, setRows] = useState(null); const [q, setQ] = useState(""); const [err, setErr] = useState(null);
  const load = () => { setErr(null); axios.get(`${API}/inventory/balances`).then((r) => setRows(Array.isArray(r.data) ? r.data : r.data.items || [])).catch((e) => { setErr(e); setRows([]); }); };
  useEffect(() => { load(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps
  if (err) return <div className="p-3"><ErrorNotice message={err} onRetry={load} testId="m-stock-error" /></div>;   // dulu "Tidak ada stok yang cocok"
  if (rows === null) return <div className="p-6 text-center text-sm">Memuat…</div>;
  const f = rows.filter((r) => !q || `${r.product_name || ""} ${r.sku || ""}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="p-3 space-y-2" data-testid="m-stock">
      <input className="w-full rounded-lg border p-3" placeholder="Cari produk / SKU" value={q} onChange={(e) => setQ(e.target.value)} data-testid="m-stock-search" />
      {!f.length && <div className="p-6 text-center text-sm text-[#6E6E73]" data-testid="m-stock-empty">Tidak ada stok yang cocok.</div>}
      {f.slice(0, 80).map((r, i) => (
        <div key={r.id || i} className="m-card p-3 flex justify-between gap-2 text-sm" data-testid={`m-stock-row-${i}`}>
          <div className="min-w-0"><b>{r.product_name || r.product_id}</b><div className="text-xs text-[#6E6E73]">{r.warehouse_name || r.warehouse_id}</div></div>
          {/* Audit UI HP (md Status Stok) — angka dengan satuan (yard/kg bercampur) & format Indonesia (dulu "2499.56"). */}
          <div className="shrink-0 text-right tabular-nums"><div className="whitespace-nowrap"><b>{formatQty(r.available ?? r.available_qty ?? r.quantity)}</b> {r.base_unit || r.unit || ""} tersedia</div><div className="text-xs text-[#6E6E73] whitespace-nowrap">{formatQty(r.reserved ?? r.reserved_qty ?? 0)} {r.base_unit || r.unit || ""} dipesan</div></div>
        </div>
      ))}
    </div>
  );
}
