import MobilePendingQueue from "./MobilePendingQueue";
import MobileAmendSheet from "./MobileAmendSheet";
import MobileOrderJourney from "./MobileOrderJourney";
import MobileArReceipt from "./MobileArReceipt";
import SoApprovalsPanel from "../../orders/SoApprovalsPanel";
import VerifyOrderDialog from "../../sales_admin/VerifyOrderDialog";
import FulfillmentDecisionDialog from "../../sales_admin/FulfillmentDecisionDialog";
import { releaseMessage, releaseOrder } from "../../sales_admin/workDeskApi";
import { apiErrorText } from "../../../utils/apiError";
import { useEffect, useMemo, useState } from "react";
import { ClipboardList, Search, PackageX, ChevronDown, FileEdit, ClipboardCheck, CheckCircle2, PackageSearch, Wallet, RotateCcw } from "lucide-react";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import { StagePill, SubStatusChips } from "../../../components/SoStatusBadges";
import { hasPartialBackorder, isBackorderSo, isClosedSo, visibleSubs } from "../../orders/soStatusView";
import { roleIs } from "../../../config/roles";

const FILTERS = [
  { id: "all", label: "Semua" },
  { id: "active", label: "Aktif" },
  { id: "done", label: "Selesai" },
  { id: "cancelled", label: "Batal" },
];
const ACTIVE = ["reserved", "waiting_approval", "approved", "confirmed", "partially_picked", "picked", "partially_shipped", "shipped", "dispatched"];

// Admin Sales: verifikasi & konfirmasi hanya relevan sebelum barang diproses gudang.
const PRE_CONFIRM = ["reserved", "waiting_approval", "approved", "waiting_stock"];
const SHIPPED = ["shipped", "partially_shipped", "dispatched", "delivered", "done"];

// Cek UI UAT v3 (S11) — sample gratis dulu tampil "Belum bayar · Rp 0" + tombol Catat bayar.
const isFreeSample = (o) => o.sample_billing === "free" || (o.order_type === "sample" && !Number(o.grand_total || 0));

export default function MobileOrders({ orders = [], loading, onBrowse, onRefresh, role, user, focusId, onReturn, onDashboard }) {
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState(focusId || null);
  const [amend, setAmend] = useState(null);
  const [verify, setVerify] = useState(null);
  const [fulfill, setFulfill] = useState(null);
  const [pay, setPay] = useState(null);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState(null);
  const isAdmin = roleIs(role, ["sales_admin"]);   // Sisir lanjutan gerbang peran (2026-10-21) — meja Admin Sales (peran acuan dikenali)
  useEffect(() => {
    if (!focusId) return;
    setOpen(focusId); setFilter("all");
    setTimeout(() => document.querySelector(`[data-testid="mobile-order-${focusId}"]`)?.scrollIntoView({ block: "center" }), 250);
  }, [focusId]);
  const flash = (ok, text) => { setMsg({ ok, text }); if (ok) onRefresh?.(); };
  // Trial 22 Okt (E8) — pesanan yang ditahan Admin Sales dilepas ke gudang.
  const doRelease = async (o) => {
    setBusy(o.id); setMsg(null);
    try { flash(true, releaseMessage(await releaseOrder(o.id), o.number)); }
    catch (e) { flash(false, apiErrorText(e, "Gagal melepas pesanan ke gudang.")); } finally { setBusy(""); }
  };

  const list = useMemo(() => {
    const term = q.toLowerCase().trim();
    return orders.filter((o) => {
      if (filter === "active" && !ACTIVE.includes(o.status)) return false;
      if (filter === "done" && o.status !== "done" && o.status !== "delivered") return false;
      if (filter === "cancelled" && !["cancelled", "expired"].includes(o.status)) return false;
      if (!term) return true;
      return [o.number, o.customer_name].filter(Boolean).join(" ").toLowerCase().includes(term);
    });
  }, [orders, q, filter]);

  return (
    <div data-testid="mobile-orders">
      <MobilePendingQueue />
      <div className="mb-2 flex items-center gap-2">
        <ClipboardList size={16} className="text-[#0058CC]" />
        <h2 className="m-section-title">{isAdmin ? "Pesanan PT" : "Pesanan Saya"}</h2>{/* Audit UI 24 Okt — Admin Sales melihat semua SO PT */}
        {onDashboard && <button className="ml-auto rounded-full border border-[#0058CC] px-3 py-1 text-[11.5px] font-semibold text-[#0058CC]" onClick={onDashboard} data-testid="mobile-orders-dashboard-btn">Dasbor</button>}
      </div>

      {msg && <div className={`notice-bar ${msg.ok ? "success" : "danger"} mb-2 text-xs`} data-testid="mobile-orders-msg">{msg.text}</div>}
      <div className="mb-2.5 flex items-center gap-2 rounded-xl bg-white px-3 py-2 border border-[#EFF0F2]">
        <Search size={15} className="text-[#8E8E93]" />
        <input data-testid="mobile-orders-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Cari nomor / pelanggan…"
          className="w-full bg-transparent text-[13px] outline-none placeholder:text-[#8E8E93]" />
      </div>

      <div className="no-scrollbar mb-3 flex gap-2 overflow-x-auto">
        {FILTERS.map((f) => (
          <button key={f.id} data-testid={`mobile-orders-filter-${f.id}`} onClick={() => setFilter(f.id)}
            className={`whitespace-nowrap rounded-full border px-3 py-1.5 text-[12px] font-semibold transition ${filter === f.id ? "border-[#0058CC] bg-[#0058CC] text-white" : "border-[#E5E5EA] bg-white text-[#3A3A3C]"}`}>
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-2.5">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-20 animate-pulse rounded-xl bg-[#ECEDF0]" />)}</div>
      ) : list.length === 0 ? (
        <div data-testid="mobile-orders-empty" className="flex flex-col items-center gap-3 py-20 text-center m-muted">
          <PackageX size={32} className="text-[#C7C7CC]" />
          <p className="text-[13px] font-medium text-[#1C1C1E]">{orders.length && (filter !== "all" || q.trim())
            ? `Tidak ada pesanan ${filter !== "all" ? `berstatus ${(FILTERS.find((f) => f.id === filter) || {}).label}` : ""}${q.trim() ? ` yang cocok dengan “${q.trim()}”` : ""}.`
            : "Belum ada pesanan."}</p>
          <button onClick={onBrowse} className="primary-button mt-1 px-5 py-2.5">Buat Pesanan</button>
        </div>
      ) : (
        <div className="space-y-2.5">
          {list.map((o) => {
            const total = o.grand_total ?? o.total_amount ?? 0;
            const isOpen = open === o.id;
            return (
              <div key={o.id} data-testid={`mobile-order-${o.id}`} className="m-card overflow-hidden">
                <button className="m-press flex w-full items-center gap-3 p-3 text-left" onClick={() => setOpen(isOpen ? null : o.id)}>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[12.5px] font-bold text-[#0058CC]">{o.number}</span>
                      <StagePill order={o} testId={`mobile-order-stage-${o.id}`} />
                      {/* Fase 4 · R1 — sama dengan daftar Pesanan desktop (R5, keputusan pemilik): "Backorder" = status Menunggu stok
                          SAJA; SO hidup di tahap lain yang bersisa kurang stok = "Sebagian menunggu stok"; SO tutup tanpa chip. */}
                      {isBackorderSo(o) && (
                        <span data-testid={`mobile-order-backorder-chip-${o.id}`}
                          className="rounded-sm bg-[#FFF1EA] px-1 py-0.5 text-[10px] font-bold uppercase tracking-wide text-[#B23B14]">Backorder</span>
                      )}
                      {hasPartialBackorder(o) && (
                        <span data-testid={`mobile-order-partial-stock-chip-${o.id}`}
                          className="rounded-sm bg-[#FFF7EF] px-1 py-0.5 text-[10px] font-semibold text-[#8C4A00]">Sebagian menunggu stok</span>
                      )}
                    </div>
                    <p className="mt-0.5 truncate text-[11.5px] text-[#3C3C43]">{o.customer_name}</p>
                    {/* UAT 24 Okt (audit UI tahap 2) — G2-20: SO batal tidak lagi "Dibatalkan" dua kali + "Belum bayar". */}
                    <SubStatusChips subs={visibleSubs(o)} testIdPrefix={`mobile-order-sub-${o.id}`} className="mt-0.5" />
                    <p className="mt-0.5 text-[10.5px] m-muted" data-testid={`mobile-order-meta-${o.id}`}>{(o.items || []).length} item{isClosedSo(o) ? "" : <> • {isFreeSample(o) ? "Gratis" : o.payment_status === "paid" ? <span className="text-[#1A7A3A]">Lunas</span> : o.payment_status === "partial" ? "Bayar sebagian" : "Belum bayar"}</>}</p>
                  </div>
                  <div className="flex flex-col items-end">
                    <span className="text-[13px] font-bold tabular-nums">{formatCurrency(total)}</span>
                    <ChevronDown size={15} className={`mt-1 text-[#8E8E93] transition-transform ${isOpen ? "rotate-180" : ""}`} />
                  </div>
                </button>
                {isOpen && (
                  <div data-testid={`mobile-order-detail-${o.id}`} className="border-t border-[#EFF0F2] bg-[#FAFBFC] px-3 py-2.5">
                    {(o.items || []).map((it, i) => (
                      <div key={i} className="flex items-center justify-between py-1 text-[12px]">
                        {/* G2-33 — qty berformat id-ID + satuan (dulu "× 24.78"). */}
                        <span className="min-w-0 flex-1 truncate text-[#3C3C43]">{it.product_name || it.name} <span className="m-muted">× {formatQty(it.quantity)} {it.unit || ""}</span></span>
                        <span className="tabular-nums font-semibold">{formatCurrency((it.price || it.unit_price || 0) * (it.quantity || 0))}</span>
                      </div>
                    ))}
                    <div className="mt-1.5 flex items-center justify-between border-t border-[#EFF0F2] pt-1.5 text-[12.5px] font-bold">
                      <span>Total</span>
                      <span className="tabular-nums text-[#0058CC]">{formatCurrency(total)}</span>
                    </div>
                    {o.fulfillment_method === "ambil"
                      ? <p className="mt-1.5 text-[11px] m-muted" data-testid={`mobile-order-pickup-${o.id}`}>Diambil di gudang{o.pickup_date ? ` · ${o.pickup_date}` : ""}</p>
                      : o.shipping_address && <p className="mt-1.5 text-[11px] m-muted">Kirim ke: {o.shipping_address.recipient_name || ""} · {o.shipping_address.address || ""}{o.shipping_address.city ? `, ${o.shipping_address.city}` : ""}</p>}
                    {o.payment_term_name && <p className="text-[11px] m-muted">Termin: {o.payment_term_name}</p>}
                    {isAdmin && PRE_CONFIRM.includes(o.status) && (
                      <div className="mt-2 grid grid-cols-2 gap-2" data-testid={`mobile-order-admin-actions-${o.id}`}>
                        {!o.release?.requested && (
                          <button className="primary-button col-span-2 flex items-center justify-center gap-1 py-2.5 text-[12px]" onClick={() => setVerify(o)} data-testid={`mobile-order-verify-${o.id}`}><ClipboardCheck size={14} /> Periksa & lepas ke gudang</button>
                        )}
                        {o.release?.requested && o.release?.hold && (
                          <button className="primary-button col-span-2 flex items-center justify-center gap-1 py-2.5 text-[12px]" disabled={busy === o.id} onClick={() => doRelease(o)} data-testid={`mobile-order-release-${o.id}`}><CheckCircle2 size={14} /> {busy === o.id ? "Memproses…" : "Lepas ke gudang"}</button>
                        )}
                        {/* Fase 4 · R1 (keputusan pemilik R5) — helper yang sama dengan layar Pesanan desktop, bukan `has_backorder` mentah. */}
                        {(isBackorderSo(o) || hasPartialBackorder(o)) && (
                          <button className="secondary-button col-span-2 flex items-center justify-center gap-1 py-2.5 text-[12px]" onClick={() => setFulfill(o)} data-testid={`mobile-order-fulfill-${o.id}`}><PackageSearch size={14} /> Keputusan pemenuhan</button>
                        )}
                      </div>
                    )}
                    <div className="mt-2 grid grid-cols-2 gap-2">
                      {!["cancelled", "expired"].includes(o.status) && (o.items || []).length > 0 && (
                        <button className="secondary-button flex items-center justify-center gap-1.5 py-2.5 text-[12px]" onClick={() => setAmend(o)} data-testid={`mobile-order-amend-${o.id}`}>
                          <FileEdit size={14} /> Ajukan koreksi
                        </button>
                      )}
                      {o.payment_status !== "paid" && !isFreeSample(o) && !["cancelled", "expired"].includes(o.status) && (
                        <button className="secondary-button flex items-center justify-center gap-1.5 py-2.5 text-[12px]" onClick={() => setPay({ id: o.customer_id, name: o.customer_name, focus_order_id: o.id })} data-testid={`mobile-order-pay-${o.id}`}>
                          <Wallet size={14} /> Catat bayar
                        </button>
                      )}
                      {SHIPPED.includes(o.status) && onReturn && (
                        <button className="secondary-button flex items-center justify-center gap-1.5 py-2.5 text-[12px]" onClick={() => onReturn(o)} data-testid={`mobile-order-return-${o.id}`}>
                          <RotateCcw size={14} /> Ajukan retur
                        </button>
                      )}
                    </div>
                    {/* Cek UI UAT v3 (2026-10-22) — sama dengan detail SO desktop: status persetujuan (harga khusus /
                        kredit / nilai) + [Ajukan Harga Khusus] per SO + [Minta Persetujuan Kredit]. Dulu HP sales tidak
                        punya jalur ini, sehingga harga khusus yang ditolak tidak bisa diajukan ulang dari HP. */}
                    {user && (
                      <div className="mt-2" data-testid={`mobile-order-approvals-${o.id}`}>
                        <SoApprovalsPanel order={o} user={user} onRefresh={onRefresh} />
                      </div>
                    )}
                    <MobileOrderJourney orderId={o.id} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
      {amend && <MobileAmendSheet order={amend} user={user} onClose={(done) => { setAmend(null); if (done) onRefresh?.(); }} />}
      {verify && <VerifyOrderDialog orderId={verify.id} orderNumber={verify.number} customerName={verify.customer_name}
        onClose={() => setVerify(null)} onVerified={(m) => { setVerify(null); flash(true, m); }} />}
      {fulfill && <FulfillmentDecisionDialog orderId={fulfill.id} orderNumber={fulfill.number} customerName={fulfill.customer_name}
        onClose={() => setFulfill(null)} onDecided={(m) => { setFulfill(null); flash(true, m); }} />}
      {pay && <MobileArReceipt customer={pay} onClose={() => setPay(null)} onDone={(m) => { setPay(null); flash(true, m || "Kwitansi tersimpan."); }} />}
    </div>
  );
}
