/**
 * Sub-fase 1.12 — Special Order (OD)
 *
 * Main view untuk Special Orders (produk custom yang belum ada di katalog)
 * Features:
 * - List special orders dengan filter status
 * - Create special order
 * - Detail view
 * - Approve/Reject (manager/admin)
 */
import { useState, useEffect } from "react";
import { can } from "../../config/roles";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import { AlertCircle, CheckCircle2, Clock, Loader2, Package, Plus, Sparkles, X } from "lucide-react";
import CreateSpecialOrderForm from "./CreateSpecialOrderForm";
import SpecialOrderDetail from "./SpecialOrderDetail";
import { StatusPill, fmtDay, odPhaseOf } from "./SpecialOrderShared";
import { StatusTabs, SearchBox, ListToolbar } from "../../components/ListControls";
import PagedRows from "../../components/PagedRows";
import KNSelect from "../../components/KNSelect";
import { formatCurrency, formatQty } from "../../utils/formatters";



// Main component
export default function SpecialOrders({ currentUser, focusDoc = null, onClearFocus }) {
  const [loading, setLoading] = useState(true);
  const [orders, setOrders] = useState([]);
  const [stats, setStats] = useState({});
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  
  // Filters
  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [originFilter, setOriginFilter] = useState("");
  
  // Views
  const [view, setView] = useState("list"); // list | create | detail
  const [selectedOrder, setSelectedOrder] = useState(null);

  useEffect(() => {
    loadOrders();
  }, [statusFilter, originFilter]);

  // Deep-link dari Meja Admin Sales → langsung buka rincian OD.
  useEffect(() => {
    if (!focusDoc?.focus_id) return;
    axios.get(`${API}/special-orders/${focusDoc.focus_id}`).then((r) => { setSelectedOrder(r.data); setView("detail"); }).catch(() => {}).finally(() => onClearFocus?.());
  }, [focusDoc?.focus_id]); // eslint-disable-line

  const token = localStorage.getItem("kn_token");

  async function loadOrders() {
    setLoading(true);
    if (!token) {
      setError("Session tidak valid. Silakan login kembali.");
      setLoading(false);
      return;
    }
    
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.append("status", statusFilter);
      if (originFilter) params.append("origin", originFilter);
      
      const res = await axios.get(`${API}/special-orders?${params}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setOrders(res.data.items || []);
      setStats(res.data.by_status || {});
      setError(null);
    } catch (e) {
      setError("Gagal memuat pesanan khusus: " + (e.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  }

  function handleCreateSuccess(newOrder) {
    setNotice(`Pesanan khusus ${newOrder.number} berhasil dibuat.`);
    setView("detail");
    setSelectedOrder(newOrder);
    loadOrders();
  }

  function handleDetailUpdate(updatedOrder) {
    setSelectedOrder(updatedOrder);
    loadOrders();
  }

  // Filter orders by search
  const filteredOrders = orders.filter(o => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      (o.number || "").toLowerCase().includes(q) ||
      (o.customer_name || "").toLowerCase().includes(q) ||
      (o.custom_item?.description || "").toLowerCase().includes(q)
    );
  });

  // Status tabs
  const statusTabs = [
    { key: "", label: "Semua" },
    { key: "draft", label: "Draf" },
    { key: "pending_approval", label: "Menunggu Persetujuan" },
    // 23 Okt — status "confirmed" berlaku sejak OD disetujui (desain/sample/harga masih berjalan; lencana baris
    // menyebut fasenya) → tab berlabel "Disetujui", bukan "Terkonfirmasi" yang terbaca seolah harga sudah final.
    { key: "confirmed", label: "Disetujui" },
    { key: "in_production", label: "Produksi" },
    { key: "ready", label: "Siap" },
    { key: "shipped", label: "Dikirim" },
    { key: "done", label: "Selesai" },
  ];

  // FE-04 — tombol mengikuti izin efektif server (POST /special-orders → order.create).
  const canCreate = can(currentUser?.permissions, "order", "create");
  const soTotal = Object.values(stats).reduce((s, v) => s + (v.count || 0), 0);
  const soCnt = (k) => stats[k]?.count || 0;

  // ─── Render views ────────────────────────────────────────────────────────────────

  if (view === "create") {
    return (
      <CreateSpecialOrderForm
        token={token}
        onCreated={handleCreateSuccess}
        onCancel={() => setView("list")}
      />
    );
  }

  if (view === "detail" && selectedOrder) {
    return (
      <SpecialOrderDetail
        order={selectedOrder}
        token={token}
        currentUser={currentUser}
        onBack={() => { setView("list"); setSelectedOrder(null); }}
        onUpdate={handleDetailUpdate}
        notice={notice}
        onClearNotice={() => setNotice(null)}
      />
    );
  }

  // ─── List View ──────────────────────────────────────────────────────────────────

  return (
    <div data-testid="special-orders-view" className="view-container">
      {/* Notice */}
      {notice && (
        <div className="notice-bar success" data-testid="special-order-notice">
          <CheckCircle2 size={14} /> {notice}
          <button onClick={() => setNotice(null)}><X size={12} /></button>
        </div>
      )}

      {/* Error */}
      {error && (
        <ErrorNotice message={error} onRetry={loadOrders} onDismiss={() => setError(null)} testId="special-order-error" />
      )}

      {/* Header */}
      <div className="view-header">
        <div>
          <h1 className="view-title">
            <Sparkles size={20} /> Pesanan Khusus (OD)
          </h1>
          <p className="view-subtitle">
            Pesanan khusus untuk produk custom yang belum ada di katalog
          </p>
        </div>
        {canCreate && (
          <button
            data-testid="create-special-order-btn"
            className="primary-button"
            onClick={() => setView("create")}
          >
            <Plus size={14} /> Buat Pesanan Khusus
          </button>
        )}
      </div>

      {/* Ringkasan */}
      <div data-testid="special-order-stats" className="grid grid-cols-2 gap-2 sm:grid-cols-5" style={{ marginBottom: 12 }}>
        {[
          { label: "Total OD", value: soTotal, icon: Sparkles, hint: "semua status" },
          { label: "Draf", value: soCnt("draft"), icon: Package },
          { label: "Menunggu Persetujuan", value: soCnt("pending_approval"), icon: Clock },
          { label: "Produksi", value: soCnt("in_production"), icon: Loader2 },
          { label: "Selesai", value: soCnt("done"), icon: CheckCircle2 },
        ].map(({ label, value, icon: Icon, hint }) => (
          <div key={label} className="metric-card">
            <div className="metric-icon"><Icon size={16} /></div>
            <div className="metric-body">
              <div className="metric-label">{label}</div>
              <div className="metric-value tabular-nums">{formatQty(value)}</div>
              {hint && <div className="metric-hint">{hint}</div>}
            </div>
          </div>
        ))}
      </div>

      {/* Status tabs → baris cari (standar daftar penjualan) */}
      <StatusTabs testIdPrefix="status-tab" value={statusFilter} onChange={setStatusFilter}
        tabs={statusTabs.map((t) => ({ ...t, count: t.key ? soCnt(t.key) : soTotal }))} />
      <ListToolbar testId="special-order-toolbar">
        <SearchBox value={searchQuery} onChange={setSearchQuery} testId="special-order-search"
          placeholder="Cari nomor / pelanggan / keterangan…" />
        <KNSelect data-testid="special-order-origin-filter" className="field !w-auto" value={originFilter}
          options={[{ value: "", label: "Label: semua" }, { value: "special_order", label: "Pesanan Khusus" }, { value: "redesign", label: "Redesign" }]}
          onValueChange={setOriginFilter} />
      </ListToolbar>

      {/* Loading */}
      {loading ? (
        <div className="loading-state">
          <Loader2 size={24} className="spin" />
          <p>Memuat pesanan khusus…</p>
        </div>
      ) : filteredOrders.length === 0 ? (
        <div className="empty-state" data-testid="special-order-empty">
          <Sparkles size={32} style={{ opacity: 0.3 }} />
          <p className="font-semibold">Belum ada pesanan khusus {statusFilter ? `dengan status ${statusTabs.find(t => t.key === statusFilter)?.label}` : ""}.</p>
          <p className="text-sm text-muted" style={{ maxWidth: 460, margin: "4px auto 0" }}>
            Pesanan Khusus (OD) dipakai untuk produk custom yang belum ada di katalog — mis. kain motif khusus, warna Pantone, atau bordir seragam. Alur: buat OD → menunggu approval bila nilainya besar → produksi → kirim.
          </p>
          {canCreate && (
            <button className="primary-button" style={{ marginTop: 12 }} onClick={() => setView("create")}>
              <Plus size={14} /> Buat Pesanan Khusus Pertama
            </button>
          )}
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Nomor</th>
                <th>Pelanggan</th>
                <th>Deskripsi item</th>
                <th className="text-right">Qty · harga target</th>
                <th className="text-right">Total</th>
                <th>Status</th>
                <th>Tenggat kirim</th>
              </tr>
            </thead>
            <tbody>
              <PagedRows rows={filteredOrders} pageSize={20} testId="special-orders-pager">{(order) => (
                // 23 Okt — seluruh baris membuka detail; tautan "Detail" pindah ke sel nomor (dulu kolom aksi paling kanan
                // terdorong keluar layar 1440 px dan nomor OD pecah tiga baris).
                <tr key={order.id} data-testid={`special-order-row-${order.id}`} className="cursor-pointer"
                  onClick={() => { setSelectedOrder(order); setView("detail"); }}>
                  <td className="whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <Sparkles size={12} className="text-purple-500" />
                      <span className="font-mono font-semibold">{order.number}</span>
                      {order.origin === "redesign" && <span className="feature-badge badge-orange" data-testid={`special-order-redesign-badge-${order.id}`}>Redesign</span>}
                    </div>
                    <div className="mt-0.5 flex items-center gap-2 pl-5 text-[10.5px]">
                      {(order.items || []).length > 1 && <span className="text-muted" data-testid={`special-order-items-count-${order.id}`}>{order.items.length} item</span>}
                      <button type="button" data-testid={`view-special-order-${order.id}`} className="link-button"
                        onClick={(e) => { e.stopPropagation(); setSelectedOrder(order); setView("detail"); }}>Detail →</button>
                    </div>
                  </td>
                  <td>
                    <div className="font-medium">{order.customer_name}</div>
                    <div className="text-xs text-muted">{order.customer_email}</div>
                  </td>
                  <td>
                    <div className="max-w-xs">
                      <div className="font-medium truncate">
                        {order.custom_item?.description || "-"}
                      </div>
                      {order.custom_item?.specifications && Object.keys(order.custom_item.specifications).length > 0 && (
                        <div className="text-xs text-muted">
                          {Object.entries(order.custom_item.specifications).slice(0, 2).map(([k, v]) => `${k}: ${v}`).join(", ")}
                        </div>
                      )}
                    </div>
                  </td>
                  {/* Cek UI UAT v3 (S13) — OD multi-item dulu hanya menampilkan qty & harga target item pertama. */}
                  {(() => {
                    const items = (order.items || []).filter((i) => i.status !== "cancelled");
                    const units = [...new Set(items.map((i) => i.unit || "meter"))];
                    const multi = items.length > 1;
                    // Audit UI 24 Okt (120) — satuan berbeda TIDAK dijumlah; tampil per satuan (dulu hanya item pertama).
                    const perUnit = units.map((u) => ({ u, q: items.filter((i) => (i.unit || "meter") === u).reduce((a, i) => a + Number(i.quantity || 0), 0) }));
                    const target = Number(order.custom_item?.target_price || 0);
                    return (<>
                      <td className="whitespace-nowrap text-right tabular-nums" data-testid={`special-order-qty-${order.id}`}>
                        {multi
                          ? perUnit.map(({ u, q }, ix) => <span key={u}>{ix > 0 ? " · " : ""}<strong>{formatQty(q)}</strong> {u}</span>)
                          : <><strong>{formatQty(order.custom_item?.quantity)}</strong> {order.custom_item?.unit}</>}
                        {/* Audit UI 24 Okt (120) — "@ Rp 0" dulu tampil saat harga target kosong padahal total terisi. */}
                        <div className="text-[11px] text-muted">
                          {multi ? "harga per item" : target > 0 ? `@ ${formatCurrency(target)}` : "harga di rincian"}
                        </div>
                      </td>
                    </>);
                  })()}
                  <td className="whitespace-nowrap text-right font-semibold tabular-nums">
                    {formatCurrency(order.total_amount)}
                  </td>
                  <td>
                    <StatusPill status={order.status} phase={odPhaseOf(order)} />
                  </td>
                  <td className="whitespace-nowrap text-muted">
                    {order.expected_delivery ? <><Clock size={11} className="mr-1 inline" />{fmtDay(order.expected_delivery)}</> : "—"}
                  </td>
                </tr>
              )}</PagedRows>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
