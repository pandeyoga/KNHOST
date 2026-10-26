import { useCallback, useEffect, useRef, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import {
  TrendingUp, Package, AlertTriangle, Clock, CheckCircle, Star, RefreshCw, ArrowUpRight, ArrowDownRight, BarChart2,
} from "lucide-react";
import KNSelect from "../../components/KNSelect";
import LinkCard from "../../components/LinkCard";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";

const fmtCompact = (v) => {
  const n = Number(v) || 0;
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toLocaleString("id-ID", { maximumFractionDigits: 1 })} M`;
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toLocaleString("id-ID", { maximumFractionDigits: 1 })} jt`;
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toLocaleString("id-ID", { maximumFractionDigits: 1 })} rb`;
  return n.toLocaleString("id-ID");
};

function KPICard({ icon: Icon, label, value, sub, color = "#007AFF", trend, loading }) {
  return (
    <div data-testid={`kpi-${label.toLowerCase().replace(/\s+/g, "-")}`}
      className="rounded-xl border border-[#EFF0F2] bg-white p-4 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="rounded-lg p-1.5" style={{ background: `${color}18` }}>
            <Icon size={16} style={{ color }} />
          </div>
          <span className="text-[12px] font-semibold text-[#6B6B73]">{label}</span>
        </div>
        {trend !== undefined && (
          <span className={`text-[11px] font-bold flex items-center gap-0.5 ${
            trend >= 0 ? "text-green-600" : "text-red-600"
          }`}>
            {trend >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
            {Math.abs(trend)}%
          </span>
        )}
      </div>
      {loading ? (
        <div className="h-7 bg-[#F5F5F7] rounded animate-pulse" />
      ) : (
        <p className="text-2xl font-bold text-[#1C1C1E]">{value}</p>
      )}
      {sub && <p className="text-[11px] text-[#6B6B73]">{sub}</p>}
    </div>
  );
}

const fmt = new Intl.NumberFormat("id-ID");
const fmtCur = (v) => `Rp ${fmt.format(v)}`;

/**
 * ManagerDashboard — Analitik › **Ringkasan** (`reports`).
 * Fase 3 · P3 (D-17, keputusan pemilik): widget PESANAN (corong status, pelanggan teratas, kecepatan pesanan) pindah
 * ke SATU dasbor pesanan di Penjualan › Pesanan › Dasbor (data server daftar Pesanan; bisa dibuka sales). Di sini
 * tinggal kartu tautan + ringkasan KPI lintas domain, utilisasi gudang dan umur stok.
 */
export default function ManagerDashboard({ token, selectedEntity }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState(null);
  const [utilization, setUtilization] = useState([]);
  const [aging, setAging] = useState([]);
  const [agingDays, setAgingDays] = useState(30);
  const abortRef = useRef(null);

  const genRef = useRef(0);

  // G3 D4-FE-02 — generation guard + AbortController: respons/error/finally dari request lama
  // (aging/refresh sebelumnya atau setelah unmount) tidak boleh menyentuh state.
  const load = useCallback(async () => {
    const gen = ++genRef.current;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setLoading(true);
    // F0-E: laporan ter-scope per entitas aktif ('all' = oversight lintas-PT).
    const ent = selectedEntity || "all";
    const cfg = { headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      params: { entity_id: ent }, signal: ctrl.signal };
    try {
      const [sumRes, utilRes, agingRes] = await Promise.all([
        axios.get(`${API}/reports/summary`, cfg),
        axios.get(`${API}/reports/warehouse-utilization`, cfg),
        axios.get(`${API}/reports/stock-aging?days_threshold=${agingDays}`, cfg),
      ]);
      if (gen !== genRef.current) return;
      setSummary(sumRes.data);
      setUtilization(Array.isArray(utilRes.data) ? utilRes.data : []);
      setAging(Array.isArray(agingRes.data) ? agingRes.data : []);
      setError("");
    } catch (e) {
      if (gen !== genRef.current || axios.isCancel?.(e) || e?.name === "CanceledError") return;
      setError(e.response?.data?.detail || "Gagal memuat dashboard. Periksa koneksi lalu coba lagi.");
    } finally {
      if (gen === genRef.current) setLoading(false);
    }
  }, [agingDays, selectedEntity, token]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => () => { genRef.current += 1; abortRef.current?.abort(); }, []);

  // Audit UI 24 Okt (085): sumbu X dulu nama KOTA ("Bandung" berulang untuk gudang
  // berbeda) — sekarang nama gudang (dipendekkan di sumbu, utuh di tooltip).
  const utilizationData = utilization.map(w => ({
    name: w.warehouse_name || w.warehouse_city,
    on_hand: w.on_hand_qty,
    capacity: w.total_capacity,
    pct: w.utilization_pct,
  }));

  return (
    <section data-testid="manager-dashboard" className="section-card">
      <div className="section-head">
        <p className="text-[12px] text-[#6B6B73] min-w-0 truncate">Kinerja tim & operasi</p>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button onClick={load} className="secondary-button" data-testid="refresh-dashboard-button" aria-label="Muat ulang">
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>
      <div className="section-body">
        <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="manager-dashboard-error" />
        {/* KPI Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <KPICard icon={TrendingUp} label="Pesanan Hari Ini" value={summary?.orders_today ?? "—"} color="#007AFF" loading={loading} />
          {/* Audit UI 24 Okt (085↔092): angka ini = NILAI PESANAN (SO) yang masuk 30 hari terakhir,
              bukan pendapatan jurnal bulan berjalan di Posisi & Kontrol. */}
          <KPICard icon={Star} label="Nilai Pesanan 30 Hari" value={summary?.monthly_revenue !== undefined ? fmtCur(summary.monthly_revenue) : "—"} sub="nilai SO masuk · bukan pendapatan jurnal" color="#34C759" loading={loading} />
          {/* K-06 (26 Okt) — sama dengan KPI Pesanan: SO berstatus Menunggu persetujuan, tanpa pesanan sample. */}
          <KPICard icon={Clock} label="Menunggu Persetujuan" value={summary?.pending_approvals ?? "—"} sub="SO menunggu persetujuan · tanpa sample" color="#FF9500" loading={loading} />
          {/* K-04 (26 Okt) — definisi tunggal "Stok rendah": per produk per badan usaha, 0 < tersedia (papan stok) < 100. */}
          <KPICard icon={AlertTriangle} label="Stok Rendah" value={summary?.low_stock_items ?? "—"} sub="produk · tersedia < 100 (papan stok)" color="#FF3B30" loading={loading} />
          <KPICard icon={CheckCircle} label="Stock Opname Menunggu" value={summary?.pending_cycle_counts ?? "—"} sub="Menunggu review" color="#5856D6" loading={loading} />
        </div>

        {/* D-17 — analitik pesanan (corong, pelanggan teratas, kecepatan) = SATU dasbor di Pesanan. */}
        <LinkCard testId="manager-dashboard-orders-link" icon={BarChart2} className="mt-4"
          what="Analitik pesanan (corong status, pelanggan teratas, kecepatan pesanan)"
          where="Penjualan › Pesanan › Dasbor & Analitik" view="orders" label="Buka Dasbor Pesanan" />

        {/* Row: Utilization + Stock Aging */}
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          {/* Warehouse Utilization */}
          <div className="rounded-xl border border-[#EFF0F2] bg-white p-4">
            <h3 className="text-[14px] font-bold mb-3">Utilisasi Gudang</h3>
            {loading ? (
              <div className="h-36 bg-[#F5F5F7] rounded animate-pulse" />
            ) : utilizationData.length > 0 ? (
              <>
                {/* UAT 24 Okt (audit UI tahap 2) — 17 nama gudang di sumbu X dulu saling menimpa; kini miring & dipendekkan
                    (nama lengkap ada di tooltip dan daftar di bawah grafik). */}
                <ResponsiveContainer width="100%" height={190}>
                  <BarChart data={utilizationData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#EFF0F2" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={utilizationData.length > 8 ? "preserveStartEnd" : 0}
                      angle={-35} textAnchor="end" height={56}
                      tickFormatter={(v) => (String(v).length > 10 ? `${String(v).slice(0, 9)}…` : v)} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={fmtCompact} width={48} />
                    <Tooltip formatter={(val, name) => [fmt.format(val), name === "on_hand" ? "Stok fisik" : "Kapasitas"]} />
                    <Bar dataKey="capacity" fill="#EFF0F2" name="capacity" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="on_hand" fill="#007AFF" name="on_hand" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
                <div className="mt-2 grid gap-1.5">
                  {utilization.map(w => (
                    <div key={w.warehouse_id} className="flex items-center gap-2">
                      <span className="text-[11px] text-[#6B6B73] w-32 truncate">{w.warehouse_name}</span>
                      <div className="flex-1 h-1.5 bg-[#EFF0F2] rounded-full overflow-hidden">
                        <div className="h-full rounded-full bg-[#007AFF]" style={{ width: `${Math.min(w.utilization_pct, 100)}%` }} />
                      </div>
                      <span className="text-[11px] font-bold text-[#1C1C1E] w-10 text-right">{w.utilization_pct}%</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="h-36 flex items-center justify-center text-[13px] text-[#8E8E93]">Belum ada data gudang</div>
            )}
          </div>
          {/* Stock Aging */}
          <div className="rounded-xl border border-[#EFF0F2] bg-white p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Package size={15} className="text-[#FF9500]" />
                <h3 className="text-[14px] font-bold">Umur Stok</h3>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] text-[#6B6B73]">Min</span>
                <KNSelect
                  value={String(agingDays)}
                  onValueChange={(v) => setAgingDays(Number(v))}
                  className="field !py-0.5 !px-1.5 text-[11px] w-auto"
                  options={[
                    { value: "7",  label: "7 hari" },
                    { value: "14", label: "14 hari" },
                    { value: "30", label: "30 hari" },
                    { value: "60", label: "60 hari" },
                    { value: "90", label: "90 hari" },
                  ]}
                />
              </div>
            </div>
            {loading ? (
              <div className="space-y-2">{[...Array(4)].map((_, i) => <div key={i} className="h-8 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
            ) : aging.length > 0 ? (
              <div className="grid gap-1 max-h-56 overflow-auto">
                <div className="grid grid-cols-[1fr_80px_60px_80px_80px] gap-2 whitespace-nowrap text-[11px] font-bold uppercase text-[#8E8E93] pb-1 border-b border-[#EFF0F2]">
                  <span>Produk</span><span>Gudang</span><span>Stok Fisik</span><span>Diam</span><span>Nilai</span>
                </div>
                {aging.map((item, idx) => (
                  <div key={`${item.product_id}-${item.warehouse_id}-${item.lot || item.owner_entity_id || idx}`}
                    className="grid grid-cols-[1fr_80px_60px_80px_80px] gap-2 text-[11px] py-1.5 border-b border-[#F5F5F7] last:border-0">
                    <div className="min-w-0">
                      {/* UAT 24 Okt (audit UI tahap 2) — saldo tanpa master produk dulu "Unknown · Rp 0". */}
                      <p className={`truncate ${item.product_missing ? "italic text-[#8E8E93]" : "font-semibold"}`}
                        title={item.product_missing ? "Saldo stok tanpa data master produk — perlu dibereskan" : item.product_name}>{item.product_name}</p>
                      <p className="text-[10px] text-[#8E8E93]">{item.sku || "—"}</p>
                    </div>
                    <span className="text-[#6B6B73] truncate" title={[item.warehouse_name, item.warehouse_city].filter(Boolean).join(" · ")}>{item.warehouse_name || item.warehouse_city || "—"}</span>
                    <span className="font-semibold">{fmt.format(item.on_hand_qty)}</span>
                    <span className={`font-bold ${
                      (item.days_since_movement === null || item.days_since_movement > 60) ? "text-red-600"
                        : item.days_since_movement > 30 ? "text-orange-500"
                        : "text-[#1C1C1E]"
                    }`}>
                      {item.days_since_movement === null ? "tanpa mutasi" : `${item.days_since_movement} hari`}
                    </span>
                    <span className="text-[#3C3C43]">{item.product_missing ? "—" : fmtCur(item.estimated_value || 0)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="h-24 flex items-center justify-center text-[13px] text-[#8E8E93]">
                Tidak ada stok yang diam lebih dari {agingDays} hari sejak pergerakan terakhir.
                (Stok yang belum pernah terjual dihitung terpisah di Analitik Stok.)
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
