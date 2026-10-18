/**
 * Layar HP tambahan untuk sales & Admin Sales:
 *  - MobilePriceStatus  : status pengajuan harga khusus saya (menunggu/disetujui/ditolak).
 *  - MobileSampleOrders : Pesanan Sampel (SOS-) + rinciannya (dulu hanya tampilan penuh).
 *  - MobileApprovalWatch: Admin Sales memantau persetujuan yang nyangkut (hanya-lihat, E8.1b).
 */
import { useEffect, useState } from "react";
import { ChevronDown, Tag, Scissors, ShieldQuestion } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import { badgeClass, badgeLabel } from "../../sales_admin/workDeskApi";
import { askReason } from "../../../services/confirmService";

const errText = (e, fb) => { const d = e?.response?.data?.detail; return (d && (d.message || (typeof d === "string" ? d : JSON.stringify(d)))) || fb; };
const fmtDate = (s) => (s ? new Date(s).toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" }) : "-");
const list = (d) => (Array.isArray(d) ? d : d?.items || []);

function Chips({ items, value, onChange, prefix }) {
  return (
    <div className="no-scrollbar flex gap-2 overflow-x-auto py-1">
      {items.map(([id, label]) => (
        <button key={id || "all"} onClick={() => onChange(id)} data-testid={`${prefix}-${id || "all"}`}
          className={`h-9 shrink-0 whitespace-nowrap rounded-full border px-3 text-[12px] font-semibold ${value === id ? "border-[#0058CC] bg-[#0058CC] text-white" : "border-[#E5E5EA] bg-white text-[#3A3A3C]"}`}>{label}</button>
      ))}
    </div>
  );
}

const PRICE_FILTERS = [["", "Semua"], ["pending", "Menunggu"], ["approved", "Disetujui"], ["rejected", "Ditolak"]];

export function MobilePriceStatus({ onNew }) {
  const [rows, setRows] = useState(null);
  const [status, setStatus] = useState("");
  const [err, setErr] = useState("");
  useEffect(() => { axios.get(`${API}/price-approvals`).then((r) => setRows(list(r.data))).catch((e) => { setRows([]); setErr(errText(e, "Gagal memuat pengajuan.")); }); }, []);
  const shown = (rows || []).filter((p) => !status || p.status === status);
  return (
    <div className="space-y-2" data-testid="m-price-status">
      {onNew && <button className="primary-button w-full py-3" onClick={onNew} data-testid="m-price-status-new"><Tag size={15} className="mr-1 inline" /> Ajukan harga khusus baru</button>}
      <Chips items={PRICE_FILTERS} value={status} onChange={setStatus} prefix="m-price-status-filter" />
      {err && <div className="notice-bar danger text-xs">{err}</div>}
      {rows === null && <p className="text-xs m-muted">Memuat…</p>}
      {rows && shown.length === 0 && <p className="py-8 text-center text-xs m-muted" data-testid="m-price-status-empty">Belum ada pengajuan harga khusus.</p>}
      {shown.map((p) => (
        <div key={p.id} className="m-card p-3" data-testid={`m-price-status-${p.id}`}>
          <div className="flex items-start gap-2">
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-bold">{p.customer_name}</p>
              <p className="truncate text-[11.5px] text-[#3C3C43]">{p.product_name} · min {formatQty(p.min_quantity)} {p.unit}</p>
            </div>
            <span className={`shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-bold ${badgeClass(p.is_expired ? "expired" : p.status)}`}>{p.is_expired ? "Kedaluwarsa" : (p.status_label || badgeLabel(p.status))}</span>
          </div>
          <p className="mt-1 text-[12px] tabular-nums"><s className="text-[#8E8E93]">{formatCurrency(p.normal_price)}</s> → <b>{formatCurrency(p.requested_price)}</b>{p.discount_percent ? <span className="text-[#B25E00]"> (−{Math.round(p.discount_percent)}%)</span> : null}</p>
          <p className="text-[10.5px] m-muted">Diajukan {fmtDate(p.created_at)}{p.valid_until ? ` · berlaku s/d ${fmtDate(p.valid_until)}` : ""}{p.approved_by_name ? ` · diputus ${p.approved_by_name}` : ""}</p>
          {p.decision_notes && <p className="mt-0.5 text-[11px] text-[#3C3C43]">Catatan: {p.decision_notes}</p>}
        </div>
      ))}
    </div>
  );
}

const SAMPLE_FILTERS = [["", "Semua"], ["waiting_approval", "Menunggu"], ["approved", "Disetujui"], ["confirmed", "Dikonfirmasi"], ["shipped", "Dikirim"], ["done", "Selesai"], ["cancelled", "Batal"]];

export function MobileSampleOrders({ canCancel = false }) {
  const [rows, setRows] = useState(null);
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const load = () => axios.get(`${API}/sample-orders`).then((r) => setRows(list(r.data))).catch((e) => { setRows([]); setErr(errText(e, "Gagal memuat pesanan sampel.")); });
  useEffect(() => { load(); }, []);
  const cancel = async (o) => {
    const note = await askReason({ title: `Batalkan ${o.number}?`, danger: true });
    if (!note) return;
    try { await axios.post(`${API}/sample-orders/${o.id}/cancel`, { note }); setMsg(`${o.number} dibatalkan.`); setErr(""); load(); }
    catch (e) { setErr(errText(e, "Gagal membatalkan sampel.")); }
  };
  const shown = (rows || []).filter((o) => !status || o.status === status);
  return (
    <div className="space-y-2" data-testid="m-sample-orders">
      <p className="rounded-xl border border-[#EFF0F2] bg-white px-3 py-2 text-[11px] m-muted">Buat pesanan sampel dari <b>Katalog</b>: buka produk → pilih <b>Sampel</b> → checkout (gratis / berbayar).</p>
      <Chips items={SAMPLE_FILTERS} value={status} onChange={setStatus} prefix="m-sample-filter" />
      {err && <div className="notice-bar danger text-xs" data-testid="m-sample-error">{err}</div>}
      {msg && <div className="notice-bar success text-xs" data-testid="m-sample-msg">{msg}</div>}
      {rows === null && <p className="text-xs m-muted">Memuat…</p>}
      {rows && shown.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-10 text-center" data-testid="m-sample-empty"><Scissors size={28} className="text-[#C7C7CC]" /><p className="text-xs m-muted">Belum ada pesanan sampel.</p></div>
      )}
      {shown.map((o) => {
        const isOpen = open === o.id;
        return (
          <div key={o.id} className="m-card overflow-hidden" data-testid={`m-sample-${o.id}`}>
            <button className="m-press flex w-full items-start gap-2 p-3 text-left" onClick={() => setOpen(isOpen ? null : o.id)}>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-[12.5px] font-bold text-[#0058CC]">{o.number}</span>
                  <span className={`rounded-full border px-1.5 py-0.5 text-[9.5px] font-bold ${badgeClass(o.status)}`}>{badgeLabel(o.status)}</span>
                  <span className={`rounded-full px-1.5 py-0.5 text-[9.5px] font-bold ${o.sample_billing === "free" ? "bg-[#E6F6EC] text-[#1B7F4B]" : "bg-[#FFF4E5] text-[#8A5300]"}`}>{o.sample_billing === "free" ? "Gratis" : "Berbayar"}</span>
                </div>
                <p className="truncate text-[12px] text-[#3C3C43]">{o.customer_name}</p>
                <p className="text-[10.5px] m-muted">{fmtDate(o.created_at)} · {(o.items || []).length} item{o.sample_billing === "paid" ? ` · bayar: ${badgeLabel(o.sample_payment_status || "pending")}` : ""}</p>
              </div>
              <div className="flex flex-col items-end"><span className="text-[12px] font-bold tabular-nums">{formatCurrency(o.grand_total)}</span><ChevronDown size={15} className={`mt-1 text-[#8E8E93] transition-transform ${isOpen ? "rotate-180" : ""}`} /></div>
            </button>
            {isOpen && (
              <div className="border-t border-[#EFF0F2] bg-[#FAFBFC] px-3 py-2.5 text-[12px]" data-testid={`m-sample-detail-${o.id}`}>
                {(o.items || []).map((it, i) => (
                  <div key={i} className="flex justify-between py-0.5"><span className="min-w-0 flex-1 truncate">{it.product_name}</span><span className="tabular-nums">{formatQty(it.quantity)} {it.unit}</span></div>
                ))}
                <p className="mt-1 text-[10.5px] m-muted">Sampel dipotong gudang setelah dikonfirmasi Admin Sampel{o.sample_billing === "paid" ? " (berbayar: setelah pembayaran disetujui Finance)" : ""}.</p>
                {canCancel && ["waiting_approval", "approved"].includes(o.status) && (
                  <button className="secondary-button mt-2 w-full py-2 text-[12px]" onClick={() => cancel(o)} data-testid={`m-sample-cancel-${o.id}`}>Batalkan sampel</button>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function MobileApprovalWatch() {
  const [items, setItems] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { axios.get(`${API}/approvals/my-queue`).then((r) => setItems(r.data?.items || r.data?.queue || [])).catch((e) => { setItems([]); setErr(errText(e, "Antrean tidak bisa dimuat.")); }); }, []);
  return (
    <div className="space-y-2" data-testid="m-approval-watch">
      <p className="rounded-xl border border-[#CBDFFF] bg-[#F2F7FF] px-3 py-2 text-[11px] text-[#31465F]">Hanya-lihat: pantau dokumen yang menunggu keputusan manajer supaya bisa dikejar. Keputusan tetap di layar manajer.</p>
      {err && <div className="notice-bar danger text-xs">{err}</div>}
      {items === null && <p className="text-xs m-muted">Memuat…</p>}
      {items && items.length === 0 && <p className="py-8 text-center text-xs m-muted" data-testid="m-approval-watch-empty">Tidak ada persetujuan yang menunggu.</p>}
      {(items || []).map((it, i) => (
        <div key={it.id || i} className="m-card p-3" data-testid={`m-approval-watch-${it.id || i}`}>
          <div className="flex items-start gap-2">
            <ShieldQuestion size={16} className="mt-0.5 shrink-0 text-[#6B219A]" />
            <div className="min-w-0 flex-1">
              <p className="text-[12.5px] font-bold">{it.number || it.doc_number || it.title}</p>
              <p className="truncate text-[11.5px] text-[#3C3C43]">{it.title || it.doc_label}</p>
              <p className="text-[10.5px] m-muted">{it.stage_label || it.stage}{it.requester ? ` · ${it.requester}` : ""}{it.days_waiting != null ? ` · ${it.days_waiting} hari menunggu` : ""}</p>
            </div>
            {it.amount != null && <span className="shrink-0 text-[12px] font-bold tabular-nums">{formatCurrency(it.amount)}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}
