import { useEffect, useState } from "react";
import { X } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { formatCurrency } from "../../../utils/formatters";
import { offlinePost } from "../../../utils/offlineQueue";
import { parseDecimal } from "../../../utils/decimalInput";
import MoneyInput from "../../../components/MoneyInput";

const METHODS = [["transfer", "Transfer"], ["cash", "Tunai"], ["giro", "Giro/Cek"]];

/** Kwitansi penerimaan dari HP sales: alokasi FIFO otomatis ke tagihan terbuka (bisa diubah), offline-aware.
 *  UAT 24 Okt (audit UI tahap 2) — G2-21: dibuka dari satu SO (`focusOrderId`) → SO itu di urutan PERTAMA dan
 *  teralokasi lebih dulu (dulu FIFO mulai dari SO tertua milik pelanggan, SO yang dibuka di urutan terakhir). */
export default function MobileArReceipt({ customer, focusOrderId = "", onClose, onDone }) {
  const [orders, setOrders] = useState(null);
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("transfer");
  const [notes, setNotes] = useState("");
  const [alloc, setAlloc] = useState({});
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  useEffect(() => {
    axios.get(`${API}/ar-receipts/open-orders`, { params: { customer_id: customer.id } })
      .then((r) => {
        const rows = r.data || [];
        const fid = focusOrderId || customer.focus_order_id || "";
        setOrders(fid ? [...rows.filter((o) => o.order_id === fid), ...rows.filter((o) => o.order_id !== fid)] : rows);
      }).catch((e) => setMsg({ ok: false, text: e.response?.data?.detail || "Gagal memuat tagihan." }));
  }, [customer.id, customer.focus_order_id, focusOrderId]);
  const total = Number.isNaN(parseDecimal(String(amount || ""))) ? 0 : (parseDecimal(String(amount || "")) || 0);
  const autoAlloc = (amt) => { let left = amt; const a = {}; (orders || []).forEach((o) => { const x = Math.min(left, Number(o.outstanding || 0)); if (x > 0) { a[o.order_id] = x; left -= x; } }); setAlloc(a); };
  const setAmt = (v) => { setAmount(v); const n = parseDecimal(String(v || "")); autoAlloc(Number.isNaN(n) ? 0 : n || 0); };
  const allocated = Object.values(alloc).reduce((s, v) => s + Number(v || 0), 0);
  const diff = Math.round((total - allocated) * 100) / 100;
  const submit = async () => {
    setBusy(true); setMsg(null);
    try {
      const body = { customer_id: customer.id, amount: total, method, notes, allocations: Object.entries(alloc).filter(([, v]) => Number(v) > 0).map(([order_id, v]) => ({ order_id, amount: Number(v) })) };
      if (diff > 0.009) body.variance_decision = { kind: "deposit", note: "Kelebihan bayar disimpan sebagai titipan (HP sales)" };
      const r = await offlinePost(`${API}/ar-receipts`, body, { label: `Kwitansi ${customer.name} ${formatCurrency(total)}` });
      if (r.queued) { setMsg({ ok: true, text: "Offline — kwitansi tersimpan di HP, dikirim saat sinyal kembali (tanpa dobel)." }); return; }
      setMsg({ ok: true, text: `Kwitansi ${r.data?.number || ""} tersimpan.` });
      setTimeout(() => onDone?.(r.data), 900);
    } catch (e) { const d = e.response?.data?.detail; setMsg({ ok: false, text: (d && (d.message || (typeof d === "string" ? d : JSON.stringify(d)))) || "Gagal menyimpan kwitansi." }); }
    finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-end bg-black/40" data-testid="m-ar-receipt">
      <div className="w-full max-h-[92vh] overflow-y-auto rounded-t-2xl bg-white p-4 space-y-3">
        <div className="flex items-center justify-between"><p className="text-[15px] font-bold">Catat pembayaran · {customer.name}</p><button onClick={onClose} data-testid="m-ar-close" aria-label="Tutup"><X size={20} /></button></div>
        {/* G2-21 — label di atas setiap isian (dulu "Jumlah diterima" hanya placeholder). */}
        <label className="block"><span className="mb-1 block text-[11.5px] font-semibold text-[#3C3C43]">Jumlah diterima <span className="text-red-500">*</span></span>
          <MoneyInput className="w-full rounded-xl border-2 border-[#E5E5EA] p-3 text-lg tabular-nums" placeholder="0" value={amount}
            onChange={(v) => setAmt(v)} testId="m-ar-amount" /></label>
        <div><span className="mb-1 block text-[11.5px] font-semibold text-[#3C3C43]">Metode</span>
          <div className="flex gap-1" role="radiogroup" aria-label="Metode">{METHODS.map(([id, l]) => <button key={id} role="radio" aria-checked={method === id} className={`flex-1 rounded-lg py-2 text-xs font-semibold ${method === id ? "bg-[#0058CC] text-white" : "bg-[#F2F3F5]"}`} onClick={() => setMethod(id)} data-testid={`m-ar-method-${id}`}>{l}</button>)}</div></div>
        <div className="space-y-1.5">
          <p className="text-[11.5px] font-semibold text-[#3C3C43]">Alokasi ke tagihan <span className="font-normal m-muted">(otomatis mulai dari {focusOrderId || customer.focus_order_id ? "pesanan yang dibuka, lalu yang tertua" : "yang tertua"}; bisa diubah)</span></p>
          {orders === null && <p className="text-xs m-muted">Memuat tagihan…</p>}
          {orders && orders.length === 0 && <p className="text-xs m-muted" data-testid="m-ar-no-orders">Tidak ada tagihan terbuka.</p>}
          {(orders || []).map((o) => (
            <div key={o.order_id} className="flex items-center gap-2 rounded-lg border border-[#EFF0F2] p-2 text-[12px]" data-testid={`m-ar-order-${o.order_id}`}>
              <div className="flex-1 min-w-0"><b>{o.number}</b>{(focusOrderId || customer.focus_order_id) === o.order_id && <span className="ml-1 rounded bg-[#EAF2FF] px-1 text-[10px] font-semibold text-[#0058CC]">dibuka</span>}<p className="text-[10.5px] m-muted">sisa {formatCurrency(o.outstanding)}</p></div>
              <label className="block text-right"><span className="block text-[10px] m-muted">Dialokasikan (Rp)</span>
                <input type="number" inputMode="decimal" aria-label={`Alokasi ke ${o.number}`} className="w-28 rounded-lg border border-[#E5E5EA] p-1.5 text-right text-[12px] tabular-nums" value={alloc[o.order_id] ?? ""} onChange={(e) => setAlloc({ ...alloc, [o.order_id]: e.target.value })} data-testid={`m-ar-alloc-${o.order_id}`} /></label>
            </div>
          ))}
        </div>
        <label className="block"><span className="mb-1 block text-[11.5px] font-semibold text-[#3C3C43]">Catatan <span className="font-normal m-muted">(opsional)</span></span>
          <textarea className="w-full rounded-xl border border-[#E5E5EA] p-2 text-sm" rows={2} placeholder="No. referensi transfer, dll." value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="m-ar-notes" /></label>
        <div className="flex justify-between text-[12px]" data-testid="m-ar-summary"><span>Teralokasi {formatCurrency(allocated)}</span><span className={diff !== 0 ? "text-[#B25E00] font-semibold" : "m-muted"}>{total <= 0 ? "Isi jumlah dulu" : diff > 0 ? `lebih ${formatCurrency(diff)} → titipan` : diff < 0 ? `alokasi melebihi ${formatCurrency(-diff)}` : "pas"}</span></div>
        {msg && <div className={`notice-bar ${msg.ok ? "success" : "danger"} text-xs`} data-testid="m-ar-msg">{msg.text}</div>}
        <button className="primary-button w-full py-3" disabled={busy || total <= 0 || diff < -0.009 || allocated <= 0} onClick={submit} data-testid="m-ar-submit">{busy ? "Menyimpan…" : `Simpan kwitansi ${formatCurrency(total)}`}</button>
      </div>
    </div>
  );
}
