import { useState, useMemo } from "react";
import { TrendingUp, TrendingDown, AlertCircle, Clock, Package, DollarSign, Users, Calendar } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import { getStage, stageMeta } from "../../utils/soStatus";
import { formatDate } from "../../utils/formatters";

function OrderDashboard({ orders = [], loading = false, summary = null }) {
  const [timeRange, setTimeRange] = useState("7d"); // 7d, 30d, 90d
  
  // G3 D4-ORDER-01 — SEMUA kartu & daftar periode dari agregat SERVER (scope entitas/sales/lini yang
  // sama dengan daftar). Data lokal hanya cadangan sementara, diberi label "hanya pesanan termuat".
  const metrics = useMemo(() => {
    const now = new Date();
    const cutoffDays = timeRange === "7d" ? 7 : timeRange === "30d" ? 30 : 90;
    const cutoffDate = new Date(now.getTime() - cutoffDays * 24 * 60 * 60 * 1000);
    const srv = summary?.periods?.[timeRange];
    if (srv) {
      const bs = srv.by_status || {};
      const sum = (...ks) => ks.reduce((a, k) => a + (bs[k] || 0), 0);
      return {
        fromServer: true,
        totalRevenue: srv.revenue,
        fulfilledCount: srv.fulfilled_count,
        totalOrders: srv.orders,
        // K-06 + B2 (keputusan pemilik 26 Okt) — KPI "Menunggu persetujuan" = SO `waiting_approval` SAJA, semua tanggal,
        // populasi = daftar Pesanan (tanpa sample). Dulu "Belum diproses" = + Dipesan + Disetujui.
        pendingOrders: summary.pending_count ?? (summary.by_status?.waiting_approval?.count || 0),
        pendingBasis: summary.pending_basis || "",
        expiringSoon: summary.expiring_soon_count ?? 0,
        avgOrderValue: srv.avg_order_value,
        topCustomers: srv.top_customers || [],
        statusTotal: srv.orders,
        statusCounts: {
          waiting: sum("waiting_approval"), reserved: sum("reserved"), approved: sum("approved"),
          confirmed: sum("confirmed", "partially_picked", "picked"),
          dispatched: sum("partially_shipped", "shipped", "dispatched"),
          done: sum("done"), cancelled: sum("cancelled"),
        },
        recentOrders: orders.slice(0, 10),
      };
    }
    const recentOrders = orders.filter(o => new Date(o.created_at) >= cutoffDate);
    const FULFILLED_STATUSES = ["confirmed", "partially_picked", "picked",
      "partially_shipped", "shipped", "dispatched", "done"];
    const fulfilled = recentOrders.filter(o => FULFILLED_STATUSES.includes(o.status));
    const totalRevenue = fulfilled.reduce((s, o) => s + (o.grand_total ?? o.total_amount ?? 0), 0);
    const customerOrders = {};
    fulfilled.forEach(o => {
      const c = (customerOrders[o.customer_id] ||= { name: o.customer_name, count: 0, revenue: 0 });
      c.count++;
      c.revenue += o.grand_total ?? o.total_amount ?? 0;
    });
    const cnt = (f) => recentOrders.filter(f).length;
    return {
      fromServer: false,
      totalRevenue,
      fulfilledCount: fulfilled.length,
      totalOrders: recentOrders.length,
      pendingOrders: orders.filter(o => o.status === "waiting_approval").length,
      pendingBasis: "",
      expiringSoon: cnt(o => { const h = (new Date(o.reservation_expires_at) - now) / 36e5; return h > 0 && h < 24; }),
      avgOrderValue: fulfilled.length > 0 ? totalRevenue / fulfilled.length : 0,
      topCustomers: Object.values(customerOrders).sort((a, b) => b.revenue - a.revenue).slice(0, 5),
      statusTotal: recentOrders.length,
      statusCounts: {
        waiting: cnt(o => o.status === "waiting_approval"), reserved: cnt(o => o.status === "reserved"),
        approved: cnt(o => o.status === "approved"),
        confirmed: cnt(o => ["confirmed", "partially_picked", "picked"].includes(o.status)),
        dispatched: cnt(o => ["partially_shipped", "shipped", "dispatched"].includes(o.status)),
        done: cnt(o => o.status === "done"), cancelled: cnt(o => o.status === "cancelled"),
      },
      recentOrders: orders.slice(0, 10),
    };
  }, [orders, timeRange, summary]);
  const scopeLabel = metrics.fromServer ? "seluruh pesanan dalam cakupan Anda" : "sementara: hanya pesanan yang termuat";
  const rangeLabel = { "7d": "7 hari terakhir", "30d": "30 hari terakhir", "90d": "90 hari terakhir" }[timeRange] || timeRange;
  
  const formatCurrency = (amount) => {
    return new Intl.NumberFormat("id-ID", {
      style: "currency",
      currency: "IDR",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };
  
  return (
    <div className="flex flex-col gap-3">
      {loading && (
        <div className="animate-pulse rounded-lg bg-[#FAFBFC] px-3 py-2 text-[12px] text-[#6B6B73]">Memuat data dasbor…</div>
      )}
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[18px] font-bold">Dasbor Pesanan</h1>
          <p className="text-[12px] text-[#6B6B73]">Pemantauan & analitik pesanan penjualan</p>
        </div>
        <KNSelect
          className="field !py-1.5 !text-[11px] w-auto"
          value={timeRange}
          onValueChange={setTimeRange}
          options={[
            { value: "7d", label: "7 Hari Terakhir" },
            { value: "30d", label: "30 Hari Terakhir" },
            { value: "90d", label: "90 Hari Terakhir" },
          ]}
        />
      </div>
      
      {/* Key Metrics */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="dashboard-metrics-row">
        <div className="section-card !p-3" data-testid="dashboard-metric-revenue">
          <div className="flex items-center gap-2 mb-2">
            <div className="p-1.5 rounded-lg bg-[#EFF4FF]">
              <DollarSign size={14} className="text-[#007AFF]" />
            </div>
            <p className="text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Pendapatan</p>
          </div>
          <p data-testid="order-dashboard-revenue" className="text-[18px] font-bold text-[#007AFF]">{formatCurrency(metrics.totalRevenue)}</p>
          <p className="text-[10px] text-slate-500" data-testid="order-dashboard-scope">Setelah diskon & PPN · {scopeLabel}</p>
          <p className="text-[10px] text-[#8E8E93] mt-1" data-testid="order-dashboard-count">{metrics.fulfilledCount} pesanan terpenuhi · {metrics.totalOrders} total periode</p>
        </div>
        
        <div className="section-card !p-3">
          <div className="flex items-center gap-2 mb-2">
            <div className="p-1.5 rounded-lg bg-orange-50">
              <Clock size={14} className="text-[#FF9500]" />
            </div>
            <p className="text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]" data-testid="order-dashboard-pending-label">Menunggu persetujuan</p>
          </div>
          <p className="text-[18px] font-bold text-[#FF9500]" data-testid="order-dashboard-pending">{metrics.pendingOrders}</p>
          {/* K-06 + B2 — label sumber/cakupan: hanya status Menunggu persetujuan, semua tanggal (≠ sebaran per periode). */}
          <p className="text-[10px] text-[#8E8E93] mt-1" data-testid="order-dashboard-pending-breakdown">
            {metrics.fromServer
              ? (metrics.pendingBasis || "Pesanan berstatus Menunggu persetujuan · semua tanggal · tanpa pesanan sample")
              : "Pesanan berstatus Menunggu persetujuan · sementara: hanya pesanan yang termuat"}
          </p>
        </div>
        
        <div className="section-card !p-3">
          <div className="flex items-center gap-2 mb-2">
            <div className="p-1.5 rounded-lg bg-red-50">
              <AlertCircle size={14} className="text-red-500" />
            </div>
            <p className="text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Reservasi hampir habis</p>
          </div>
          <p className="text-[18px] font-bold text-red-500" data-testid="order-dashboard-expiring">{metrics.expiringSoon}</p>
          <p className="text-[10px] text-[#8E8E93] mt-1">Berakhir dalam &lt; 24 jam</p>
        </div>
        
        <div className="section-card !p-3">
          <div className="flex items-center gap-2 mb-2">
            <div className="p-1.5 rounded-lg bg-green-50">
              <Package size={14} className="text-[#34C759]" />
            </div>
            <p className="text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Rata-rata Pesanan</p>
          </div>
          <p className="text-[18px] font-bold text-[#34C759]" data-testid="order-dashboard-avg">{formatCurrency(metrics.avgOrderValue)}</p>
          <p className="text-[10px] text-[#8E8E93] mt-1">Pendapatan ÷ {metrics.fulfilledCount} pesanan terpenuhi</p>
        </div>
      </div>
      
      {/* Charts & Lists */}
      <div className="grid gap-3 lg:grid-cols-2">
        {/* Top Customers */}
        <div className="section-card" data-testid="dashboard-top-customers">
          <div className="section-head">
            <div className="flex items-center gap-2">
              <Users size={14} className="text-[#007AFF]" />
              <h2>Pelanggan teratas</h2>
            </div>
            <span className="text-[10.5px] text-[#6B6B73]">{rangeLabel} · {scopeLabel}</span>
          </div>
          <div className="section-body">
            {metrics.topCustomers.length === 0 ? (
              <p className="text-[12px] text-[#8E8E93] text-center py-4">Belum ada data pelanggan</p>
            ) : (
              <div className="space-y-2">
                {metrics.topCustomers.map((customer, idx) => (
                  <div key={customer.customer_id || idx} data-testid={`dashboard-top-customer-${idx}`} className="flex items-center justify-between p-2 rounded-md bg-[#FAFBFC] border border-[#EFF0F2]">
                    <div className="flex-1 min-w-0">
                      <p className="text-[11.5px] font-semibold truncate">{customer.name}</p>
                      <p className="text-[10px] text-[#6B6B73]">{customer.count} pesanan</p>
                    </div>
                    <p className="text-[12px] font-bold text-[#007AFF]">{formatCurrency(customer.revenue)}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        
        {/* Status Distribution */}
        <div className="section-card" data-testid="dashboard-status-distribution">
          <div className="section-head">
            <div className="flex items-center gap-2">
              <TrendingUp size={14} className="text-[#007AFF]" />
              <h2>Sebaran status</h2>
            </div>
            <span className="text-[10.5px] text-[#6B6B73]" data-testid="order-dashboard-dist-scope">{metrics.statusTotal} pesanan dibuat {rangeLabel}</span>
          </div>
          <div className="section-body">
            <div className="space-y-2">
              {[
                { label: "Menunggu Persetujuan", count: metrics.statusCounts.waiting, color: "bg-gray-400" },
                { label: "Dipesan", count: metrics.statusCounts.reserved, color: "bg-[#FF9500]" },
                { label: "Disetujui", count: metrics.statusCounts.approved, color: "bg-blue-500" },
                { label: "Diproses (Ditahan/Sudah Diambil)", count: metrics.statusCounts.confirmed, color: "bg-[#34C759]" },
                { label: "Dikirim (sebagian/penuh)", count: metrics.statusCounts.dispatched, color: "bg-[#5856D6]" },
                { label: "Selesai", count: metrics.statusCounts.done, color: "bg-green-600" },
                { label: "Dibatalkan", count: metrics.statusCounts.cancelled, color: "bg-red-500" },
              ].map(({ label, count, color }) => {
                const percentage = metrics.statusTotal > 0 ? (count / metrics.statusTotal) * 100 : 0;
                return (
                  <div key={label} className="space-y-1">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="font-semibold">{label}</span>
                      <span className="text-[#6B6B73]">{count} ({Math.round(percentage)}%)</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-[#EFF0F2] overflow-hidden">
                      <div className={`h-full ${color}`} style={{ width: `${percentage}%` }}></div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
      
      {/* Pesanan terbaru */}
      <div className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2">
            <Calendar size={14} className="text-[#007AFF]" />
            <h2>Pesanan terbaru</h2>
          </div>
          <span className="text-[11px] text-[#6B6B73]">10 terbaru</span>
        </div>
        <div className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-[#FAFBFC] border-b border-[#EFF0F2]">
                <tr className="text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">
                  <th className="px-3 py-2 text-left">Pesanan</th>
                  <th className="px-3 py-2 text-left">Pelanggan</th>
                  <th className="px-3 py-2 text-left">Tanggal</th>
                  <th className="px-3 py-2 text-right">Total</th>
                  <th className="px-3 py-2 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EFF0F2]">
                {metrics.recentOrders.map((order) => (
                  <tr key={order.id} className="hover:bg-[#FAFBFC]">
                    <td className="px-3 py-2 text-[11.5px] font-bold text-[#007AFF]">{order.number}</td>
                    <td className="px-3 py-2 text-[11px]">{order.customer_name}</td>
                    <td className="px-3 py-2 text-[10.5px] text-[#6B6B73]">
                      {formatDate(order.created_at)}
                    </td>
                    <td className="px-3 py-2 text-[11.5px] font-semibold text-right tabular-nums">{formatCurrency(order.total_amount)}</td>
                    <td className="px-3 py-2 text-center">
                      <span
                        data-testid={`dashboard-order-stage-${order.id}`}
                        className={`status-pill ${stageMeta(getStage(order)).cls}`}
                      >
                        {stageMeta(getStage(order)).label}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export default OrderDashboard;
