/**
 * SampleOrdersView — REVISI SAMPEL: daftar Pesanan Sample (SOS-) TERPISAH dari SO roll biasa.
 * Sales melihat pesanan sampelnya sendiri; admin/manajer/Admin Sample/Finance melihat semua.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Scissors, RefreshCw, Gift, Banknote, XCircle, CheckCircle2, Truck, PackageCheck } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { SAMPLE_STATUS_LABEL } from "../../utils/sampleOrder";
import { listSampleOrders, sampleStats, cancelSampleOrder, approveSamplePayment, confirmSampleOrder } from "./sampleApi";
import { StatusTabs, SearchBox, ListToolbar } from "../../components/ListControls";
import PagedRows from "../../components/PagedRows";
import CatalogueCreateModal from "./CatalogueCreateModal";
import CatalogueComponents from "./CatalogueComponents";
import CuttingDesk from "./CuttingDesk";
import CuttingLocations from "./CuttingLocations";
import { can, roleIs } from "../../config/roles";

const FILTERS = [
  { id: "all", label: "Semua" },
  { id: "waiting_approval", label: "Menunggu ACC bayar" },
  { id: "approved", label: "Siap ke gudang" },
  { id: "confirmed,partially_picked,picked", label: "Di gudang" },
  { id: "partially_shipped,shipped,delivered", label: "Dikirim / diambil" },
  { id: "done", label: "Selesai" },
  { id: "cancelled", label: "Dibatalkan" },
];

const CUT = { requested: "menunggu potong", cut: "sudah dipotong", awaiting_internal: "menunggu pembelian internal (stok PT lain)" };
const KIND = { standard: "Standar", hanger: "Hanger", catalogue: "Catalogue" };
const TABS = [["orders", "Pesanan Sample"], ["desk", "Meja Cutting"], ["locations", "Lokasi Cutting"]];

export default function SampleOrdersView({ user, selectedEntity = "all", focusDoc, onClearFocus }) {
  const [orders, setOrders] = useState([]);
  const [stats, setStats] = useState(null);
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [busy, setBusy] = useState("");
  const [toast, setToast] = useState("");
  const [tab, setTab] = useState("orders");
  const [showCat, setShowCat] = useState(false);
  const role = user?.role || "";
  // Sisir lanjutan gerbang peran (2026-10-21): bayar = sample_order.approve_payment + peran penyetuju server (SAMPLE_PAYMENT_APPROVERS, role_in);
  // konfirmasi/terima potong/batal/buat/konfig lokasi = sample_order.confirm/cutting_receive/cancel/create/cutting_config.
  const perms = user?.permissions;
  const canPay = can(perms, "sample_order", "approve_payment") && roleIs(role, ["finance", "sample_admin", "manager", "admin"]);
  const canConfirm = can(perms, "sample_order", "confirm");
  const canReceiveCut = can(perms, "sample_order", "cutting_receive");
  const canCancel = can(perms, "sample_order", "cancel");
  const canCreateCat = can(perms, "sample_order", "create");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      if (filter !== "all") params.status = filter;
      const [rows, st] = await Promise.all([listSampleOrders(params), sampleStats(params.entity_id ? { entity_id: params.entity_id } : {})]);
      setOrders(rows); setStats(st); setError("");
    } catch (e) { setError(apiErrorText(e, "Gagal memuat pesanan sample.")); }
    finally { setLoading(false); }
  }, [selectedEntity, filter]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (focusDoc?.focus_type === "sample_order" && focusDoc?.focus_id) { setFilter("all"); setSelectedId(focusDoc.focus_id); onClearFocus?.(); }
  }, [focusDoc]); // eslint-disable-line

  const sel = useMemo(() => orders.find((o) => o.id === selectedId) || null, [orders, selectedId]);
  const shown = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return orders;
    return orders.filter((o) => [o.number, o.customer_name, o.sales_name, ...(o.items || []).flatMap((i) => [i.product_name, i.sku])]
      .some((v) => String(v || "").toLowerCase().includes(t)));
  }, [orders, q]);
  const flash = (m) => { setToast(m); setTimeout(() => setToast(""), 5000); };
  const run = async (fn, okMsg) => {
    setBusy(sel.id); setError("");
    try { await fn(); flash(okMsg); await load(); } catch (e) { setError(apiErrorText(e, "Aksi gagal.")); } finally { setBusy(""); }
  };

  const bs = stats?.by_status || {};
  const tabBar = (
    // Audit UI 24 Okt (121) — sub-tab memakai tab-bar standar (dulu pil cokelat unik); tombol buat berbahasa Indonesia.
    <div className="tab-bar !mb-0 items-end" role="tablist">
      {TABS.map(([k, l]) => (
        <button key={k} role="tab" aria-selected={tab === k} data-testid={`sample-tab-${k}`} onClick={() => setTab(k)}
          className={`tab-button ${tab === k ? "active" : ""}`}>{l}</button>
      ))}
      {canCreateCat && <button data-testid="sample-catalogue-create" className="primary-button ml-auto mb-1.5" onClick={() => setShowCat(true)}>+ Buat Sample Katalog</button>}
      <CatalogueCreateModal open={showCat} onClose={() => setShowCat(false)} entityId={selectedEntity !== "all" ? selectedEntity : ""}
        onCreated={(so) => { flash(`${so.number} (catalogue) dibuat.`); setTab("orders"); load(); }} />
    </div>
  );
  if (tab !== "orders") {
    return (
      <div data-testid="sample-orders-view" className="grid gap-4">
        {tabBar}
        {toast && <div data-testid="sample-orders-toast" className="rounded-md border border-[#A7D8B0] bg-[#EAF7EE] px-3 py-2 text-[12px] text-[#126E2C]">{toast}</div>}
        {tab === "desk" ? <CuttingDesk selectedEntity={selectedEntity} canReceive={canReceiveCut} />
          : <CuttingLocations canEdit={can(perms, "sample_order", "cutting_config")} />}
      </div>
    );
  }
  return (
    <div data-testid="sample-orders-view" className="grid gap-4">
      {tabBar}
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="sample-orders-error" />
      {toast && <div data-testid="sample-orders-toast" className="rounded-md border border-[#A7D8B0] bg-[#EAF7EE] px-3 py-2 text-[12px] text-[#126E2C]">{toast}</div>}
      <section className="section-card">
        <div className="section-head">
          <div className="flex min-w-0 items-center gap-2">
            <Scissors size={15} className="text-[#9A5B00]" />
            <span className="kicker">Penjualan</span>
            <h2 data-testid="sample-orders-title">Pesanan Sample (SOS)</h2>
          </div>
          <button data-testid="sample-orders-refresh" className="icon-button" onClick={load} aria-label="Muat ulang"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
        </div>
        <p className="px-3 pt-2 text-[11.5px] text-[#6B6B73]">Pesanan sample <b>terpisah</b> dari pesanan roll/yard biasa (SO). Gratis → langsung ke Admin Sample; berbayar → disetujui Finance/Admin Sample dulu → diteruskan ke gudang untuk dipotong dari roll (RFID) → dikirim / diambil.</p>
        <div data-testid="sample-orders-metrics" className="grid gap-3 p-3 sm:grid-cols-4">
          <Metric label="Total" value={stats?.total ?? "—"} testId="sample-metric-total" />
          <Metric label="Gratis / Berbayar" value={stats ? `${stats.free} / ${stats.paid}` : "—"} testId="sample-metric-billing" />
          <Metric label="Menunggu ACC bayar" value={bs.waiting_approval || 0} testId="sample-metric-waiting" tone="#FFF3D6" />
          <Metric label="Nilai berbayar" value={formatCurrency(stats?.paid_value || 0)} testId="sample-metric-value" />
        </div>
      </section>

      <div>
        <StatusTabs testIdPrefix="sample-filter" value={filter} onChange={setFilter}
          tabs={FILTERS.map((f) => ({ key: f.id, testKey: f.id.split(",")[0], label: f.label,
            count: f.id === "all" ? (stats?.total ?? 0) : f.id.split(",").reduce((n, s) => n + Number(bs[s] || 0), 0) }))} />
        <ListToolbar testId="sample-orders-toolbar">
          <SearchBox value={q} onChange={setQ} testId="sample-orders-search" placeholder="Cari nomor / pelanggan / sales / produk…" />
        </ListToolbar>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
        <section className="section-card overflow-hidden">
          {loading && orders.length === 0 ? <p className="p-6 text-center text-[12px] text-[#6B6B73]">Memuat…</p>
            : shown.length === 0 ? <p data-testid="sample-orders-empty" className="p-8 text-center text-[12px] text-[#6B6B73]">{q.trim() ? `Tidak ada pesanan sample yang cocok dengan “${q.trim()}”.` : "Belum ada pesanan sample untuk saringan ini."}</p>
            : (
              <table className="w-full text-[12px]">
                <thead><tr className="border-b border-[#EFF0F2] text-left text-[10px] uppercase tracking-wide text-[#8E8E93]"><th className="px-3 py-2">Nomor</th><th className="px-3 py-2">Pelanggan</th><th className="px-3 py-2">Skema</th><th className="px-3 py-2">Item</th><th className="px-3 py-2">Status</th><th className="px-3 py-2 text-right">Nilai</th></tr></thead>
                <tbody>
                  <PagedRows rows={shown} pageSize={20} testId="sample-orders-pager">{(o) => (
                    <tr key={o.id} data-testid={`sample-order-row-${o.id}`} onClick={() => setSelectedId(o.id)}
                      className={`cursor-pointer border-b border-[#F2F3F5] hover:bg-[#FFF9EC] ${sel?.id === o.id ? "bg-[#FFF3D6]" : ""}`}>
                      <td className="px-3 py-2 font-bold text-[#9A5B00]">{o.number}</td>
                      <td className="px-3 py-2"><p className="font-semibold">{o.customer_name}</p><p className="text-[10.5px] text-[#8E8E93]">{o.sales_name || "—"}</p></td>
                      <td className="px-3 py-2"><Billing b={o.sample_billing} /></td>
                      <td className="px-3 py-2 text-[#3C3C43]">{(o.items || []).map((i) => `${i.product_name} ${formatQty(i.quantity)} ${i.base_unit || i.unit}`).join(" · ")}</td>
                      <td className="px-3 py-2"><span className={`status-pill status-${o.status}`}>{SAMPLE_STATUS_LABEL[o.status] || o.status}</span></td>
                      <td className="px-3 py-2 text-right tabular-nums">{o.sample_billing === "free" ? "Gratis" : formatCurrency(o.grand_total)}</td>
                    </tr>
                  )}</PagedRows>
                </tbody>
              </table>
            )}
        </section>

        <aside className="section-card" data-testid="sample-order-detail">
          {!sel ? <p className="p-6 text-center text-[12px] text-[#6B6B73]">Pilih pesanan sample untuk melihat detail & tindakan.</p> : (
            <div className="p-3 space-y-3 text-[12px]">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">Pesanan Sample</p>
                <p data-testid="sample-detail-number" className="text-[16px] font-bold text-[#9A5B00]">{sel.number}</p>
                <p className="font-semibold">{sel.customer_name}</p>
                <p className="text-[#6B6B73]">{sel.fulfillment_method === "ambil" ? <><PackageCheck size={11} className="inline" /> Diambil di gudang {sel.pickup_date}</> : <><Truck size={11} className="inline" /> Dikirim ke {sel.shipping_city || sel.customer_city}</>}</p>
                <div className="mt-1 flex items-center gap-2"><Billing b={sel.sample_billing} /><span className={`status-pill status-${sel.status}`}>{SAMPLE_STATUS_LABEL[sel.status] || sel.status}</span></div>
              </div>
              <ul data-testid="sample-detail-items" className="divide-y divide-[#F2F3F5] rounded-md border border-[#EFF0F2]">
                {(sel.items || []).map((i) => (
                  <li key={i.product_id} className="px-2.5 py-1.5">
                    <p className="font-semibold">{i.product_name} <span className="text-[#8E8E93]">{i.sku}</span> <span data-testid={`sample-line-kind-${i.product_id}`} className="rounded bg-[#FFF3D6] px-1.5 text-[10px] text-[#9A5B00]">{KIND[i.sample_kind || "standard"]}</span></p>
                    <p className="text-[11px] text-[#3C3C43]">{formatQty(i.quantity)} {i.base_unit || i.unit} · {CUT[i.sample_cut_status] || i.sample_cut_status || "—"}{i.child_roll_no ? ` · potongan ${i.child_roll_no} dari ${i.cut_roll_no}` : i.suggested_roll_no ? ` · saran roll ${i.suggested_roll_no}` : ""}</p>
                    {sel.sample_billing === "paid" && <p className="text-[11px] tabular-nums">{formatCurrency(i.price)}/{i.base_unit || i.unit} → {formatCurrency(i.line_total ?? i.subtotal ?? i.price * i.quantity)}</p>}
                  </li>
                ))}
              </ul>
              <CatalogueComponents order={sel} canEdit={canCreateCat} onChanged={() => { flash("Warna soft diganti — komponen dasar tetap."); load(); }} />
              {sel.sample_billing === "paid" && <p className="text-right text-[13px] font-bold tabular-nums">Total {formatCurrency(sel.grand_total)}</p>}
              {sel.sample_billing === "paid" && (
                <p data-testid="sample-detail-payment" className={`rounded-md px-2.5 py-1.5 text-[11px] ${sel.sample_payment_status === "approved" ? "bg-[#EAF7EE] text-[#126E2C]" : "bg-[#FFF3D6] text-[#9A5B00]"}`}>
                  {sel.sample_payment_status === "approved" ? <><CheckCircle2 size={11} className="inline" /> Pembayaran disetujui {sel.sample_payment_approved_by}</>
                    : sel.sample_payment_status === "reapproval_required" ? "Tagihan berubah melewati toleransi sesudah dipotong — perlu persetujuan ULANG Finance/Admin Sample. Kiriman sample ditahan."
                    : "Pembayaran belum disetujui Finance/Admin Sample."}
                </p>
              )}
              {/* F-15 — riwayat penyesuaian tagihan karena panjang aktual potong (≤ toleransi otomatis, di atasnya disetujui ulang) */}
              {(sel.sample_payment_adjustments || []).map((a, i) => (
                <p key={i} data-testid={`sample-detail-adjustment-${i}`} className="text-[10.5px] text-[#4A4A52]">
                  {a.auto ? "Disesuaikan otomatis" : "Melewati toleransi → persetujuan ulang"}: {formatCurrency(a.from)} → {formatCurrency(a.to)} ({a.pct}% · toleransi {a.tolerance_pct}%)
                </p>
              ))}
              <div className="flex flex-wrap gap-2">
                {canPay && sel.status === "waiting_approval" && sel.sample_billing === "paid" && (
                  <button data-testid="sample-detail-approve-payment" className="primary-button" disabled={busy === sel.id} onClick={() => run(() => approveSamplePayment(sel.id), `${sel.number}: pembayaran disetujui.`)}><Banknote size={13} /> Setujui Pembayaran</button>
                )}
                {canPay && sel.sample_payment_status === "reapproval_required" && (
                  <button data-testid="sample-detail-reapprove-payment" className="primary-button" disabled={busy === sel.id} onClick={() => run(() => approveSamplePayment(sel.id), `${sel.number}: tagihan baru ${formatCurrency(sel.grand_total)} disetujui — kiriman dilepas.`)}><Banknote size={13} /> Setujui Ulang Pembayaran ({formatCurrency(sel.grand_total)})</button>
                )}
                {canConfirm && sel.status === "approved" && (
                  <button data-testid="sample-detail-confirm" className="primary-button" disabled={busy === sel.id} onClick={() => run(() => confirmSampleOrder(sel.id), `${sel.number} diteruskan ke gudang — tugas potong lahir.`)}><Scissors size={13} /> Teruskan ke Gudang</button>
                )}
                {canCancel && ["waiting_approval", "approved"].includes(sel.status) && (
                  <button data-testid="sample-detail-cancel" className="secondary-button" disabled={busy === sel.id} onClick={() => run(() => cancelSampleOrder(sel.id, "Dibatalkan dari daftar pesanan sample"), `${sel.number} dibatalkan.`)}><XCircle size={13} /> Batalkan</button>
                )}
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">Riwayat</p>
                <ul data-testid="sample-detail-timeline" className="mt-1 space-y-1 text-[11px] text-[#3C3C43]">
                  {(sel.timeline || []).slice().reverse().slice(0, 8).map((t, i) => <li key={i}>• {t.label || t.event || t.action} <span className="text-[#8E8E93]">— {t.actor} · {String(t.at || t.timestamp || "").slice(0, 16).replace("T", " ")}</span></li>)}
                </ul>
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

function Billing({ b }) {
  return b === "free"
    ? <span data-testid="sample-billing-free" className="inline-flex items-center gap-1 rounded-full bg-[#EAF7EE] px-2 py-0.5 text-[10px] font-bold text-[#126E2C]"><Gift size={10} /> GRATIS</span>
    : <span data-testid="sample-billing-paid" className="inline-flex items-center gap-1 rounded-full bg-[#FFF3D6] px-2 py-0.5 text-[10px] font-bold text-[#9A5B00]"><Banknote size={10} /> BERBAYAR</span>;
}

function Metric({ label, value, testId, tone = "#F5F5F7" }) {
  return (
    <div data-testid={testId} className="rounded-md p-2.5" style={{ background: tone }}>
      <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p>
      <p className="text-[15px] font-bold tabular-nums">{value}</p>
    </div>
  );
}
