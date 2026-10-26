/**
 * OrderAnalyticsPanel — corong status & kecepatan pesanan di **Penjualan › Pesanan › Dasbor** (fase 3 · P3, D-17).
 *
 * KENAPA ADA: dulu ada DUA dasbor pesanan — Pesanan › Dasbor (data server daftar Pesanan) dan Analitik › Ringkasan
 * (`ManagerDashboard`: corong, pelanggan teratas, kecepatan). Keputusan pemilik D-17: satu dasbor di Pesanan
 * (bisa dibuka sales, angka satu sumber dengan daftar). Widget pesanan dari Ringkasan pindah ke sini; di Ringkasan
 * tinggal kartu tautan. Pelanggan teratas sudah ada di dasbor (agregat server per periode) — tidak digandakan.
 *
 * Sumber: `GET /reports/reservation-funnel` (izin `order.view`, cakupan sales & populasi daftar Pesanan K-06 —
 * tanpa pesanan sample) dan `GET /reports/order-velocity?days=`. Fase 4 · R5 (keputusan pemilik #3): kecepatan kini
 * untuk sales juga — server menyaring kepemilikan (`owner_scoped`, `scope_label`). `requireScopedVelocity` = peran
 * tanpa Analitik: angka hanya ditampilkan bila server MENGAKU sudah menyaring (server lama tanpa field → disembunyikan).
 * Tanpa `entity_id` = cakupan PT header, sama dengan daftar & ringkasan Pesanan.
 */
import { useEffect, useState } from "react";
import {
  BarChart, Bar, LineChart, Line, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { Filter, TrendingUp } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { formatCurrency } from "../../utils/formatters";

const STATUS_COLORS = {
  draft: "#8E8E93", reserved: "#007AFF", waiting_approval: "#FF9500",
  approved: "#34C759", confirmed: "#30D158", done: "#1C7C4A",
  cancelled: "#FF3B30", expired: "#FF6B00", shipped: "#5856D6",
};
const CHART_COLORS = ["#007AFF", "#34C759", "#FF9500", "#FF3B30", "#5856D6", "#FF6B00", "#8E8E93"];
// Audit UI 24 Okt (085): sumbu corong dulu memakai kode status mentah ("reserved", "waiting_stock", "done").
const FUNNEL_LABEL = {
  draft: "Draf", reserved: "Stok dipesan", waiting_approval: "Menunggu persetujuan",
  approved: "Disetujui", confirmed: "Dikonfirmasi", waiting_stock: "Menunggu stok",
  partially_picked: "Sebagian diambil", picked: "Sudah diambil", partially_shipped: "Sebagian dikirim",
  shipped: "Dikirim", done: "Selesai", cancelled: "Batal", expired: "Kedaluwarsa",
};
export const funnelLabel = (s) => FUNNEL_LABEL[s] || String(s || "—").replace(/_/g, " ");
const SKIP_FUNNEL = ["cancelled", "expired"];

export default function OrderAnalyticsPanel({ days = 30, showVelocity = false, requireScopedVelocity = false,
  testId = "order-analytics" }) {
  const [funnel, setFunnel] = useState(null);
  const [velocity, setVelocity] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    setLoading(true);
    Promise.all([
      axios.get(`${API}/reports/reservation-funnel`),
      showVelocity ? axios.get(`${API}/reports/order-velocity`, { params: { days } }) : Promise.resolve({ data: null }),
    ]).then(([f, v]) => {
      if (!live) return;
      setFunnel(f.data || null); setVelocity(v.data || null); setError("");
    }).catch(() => { if (live) setError("Analitik pesanan gagal dimuat — coba muat ulang halaman."); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [days, showVelocity]);

  const funnelData = (funnel?.funnel || []).filter((f) => !SKIP_FUNNEL.includes(f.status))
    .map((f) => ({ ...f, label: funnelLabel(f.status) }));
  // G3 D4-FE-01 — grafik memakai SELURUH rentang periode terpilih (tanpa potong 14 hari).
  // R5 — server lama (tanpa `owner_scoped`) belum menyaring kepemilikan: jangan tampilkan ke peran tanpa Analitik.
  const velocityShown = showVelocity && !(requireScopedVelocity && velocity && velocity.owner_scoped === undefined);
  const velocityData = velocity?.period_days === days ? (velocity?.velocity || []) : [];

  return (
    <div className={`grid grid-cols-1 gap-3 ${velocityShown ? "lg:grid-cols-2" : ""}`} data-testid={testId}>
      <div className="section-card" data-testid="order-analytics-funnel">
        <div className="section-head">
          <div className="flex items-center gap-2"><Filter size={14} className="text-[#007AFF]" /><h2>Corong status pesanan</h2></div>
          <span className="text-[10.5px] text-[#6B6B73]">{funnel?.total_orders ?? 0} total</span>
        </div>
        <div className="section-body">
          {/* K-06 (26 Okt) — populasi corong = daftar Pesanan; pesanan sample dikecualikan dan disebut jumlahnya. */}
          <p className="mb-2 text-[11px] text-[#8E8E93]" data-testid="order-analytics-funnel-scope">
            Sama dengan daftar Pesanan · tanpa pesanan sample{funnel?.sample_excluded ? ` (${funnel.sample_excluded} dikecualikan)` : ""} · semua tanggal
          </p>
          {error ? <p className="py-6 text-center text-[12px] text-[#C0392B]" data-testid="order-analytics-error">{error}</p>
            : loading ? <div className="h-36 rounded bg-[#F5F5F7] animate-pulse" />
              : funnelData.length === 0 ? <p className="py-10 text-center text-[12px] text-[#8E8E93]">Belum ada data pesanan</p>
                : (
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={funnelData} margin={{ top: 4, right: 8, left: 0, bottom: 24 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#EFF0F2" />
                      <XAxis dataKey="label" tick={{ fontSize: 10 }} angle={-25} textAnchor="end" interval={0} />
                      <YAxis tick={{ fontSize: 10 }} allowDecimals={false} width={28} />
                      <Tooltip formatter={(val) => [val, "Pesanan"]} />
                      <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                        {funnelData.map((entry, index) => (
                          <Cell key={entry.status} fill={STATUS_COLORS[entry.status] || CHART_COLORS[index % CHART_COLORS.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
        </div>
      </div>

      {velocityShown && (
        <div className="section-card" data-testid="order-analytics-velocity">
          <div className="section-head">
            <div className="flex items-center gap-2"><TrendingUp size={14} className="text-[#007AFF]" /><h2>Kecepatan pesanan — {days} hari</h2></div>
            <span className="text-[10.5px] text-[#6B6B73]">{velocity?.total_orders ?? 0} pesanan · rata-rata {velocity?.avg_per_day ?? 0}/hari</span>
          </div>
          <div className="section-body">
            {loading ? <div className="h-36 rounded bg-[#F5F5F7] animate-pulse" />
              : velocityData.length === 0 ? <p className="py-10 text-center text-[12px] text-[#8E8E93]">Belum ada data pesanan untuk periode ini</p>
                : (
                  <ResponsiveContainer width="100%" height={180}>
                    <LineChart data={velocityData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#EFF0F2" />
                      <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v) => String(v).slice(5)} minTickGap={8} />
                      <YAxis tick={{ fontSize: 10 }} allowDecimals={false} width={28} />
                      <Tooltip
                        formatter={(val, name) => [name === "total_amount" ? formatCurrency(val) : val, name === "count" ? "Pesanan" : name === "done" ? "Selesai" : "Nilai"]}
                        labelFormatter={(l) => `Tgl ${l}`} />
                      <Line type="monotone" dataKey="count" stroke="#007AFF" strokeWidth={2} dot={false} name="count" />
                      <Line type="monotone" dataKey="done" stroke="#34C759" strokeWidth={1.5} dot={false} strokeDasharray="4 2" name="done" />
                    </LineChart>
                  </ResponsiveContainer>
                )}
            <p className="mt-1 text-[10.5px] text-[#8E8E93]" data-testid="order-analytics-velocity-scope">
              {velocity?.scope_label || "Semua pesanan dalam cakupan PT · termasuk sample"} · garis putus = selesai.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
