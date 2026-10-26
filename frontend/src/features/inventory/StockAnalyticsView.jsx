import { useEffect, useMemo, useState } from "react";
import {
  PieChart, Pie, Cell, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import {
  TrendingUp, TrendingDown, Minus, Boxes, Snowflake, Flame, Clock, RefreshCw, Search, Layers, Sparkles,
  Activity, Info,
} from "lucide-react";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import ResponsiveTable from "../../components/ResponsiveTable";
import { PageHeader } from "../../components/ListPageParts";
import axios, { API } from "../../services/apiClient";

const fmt = new Intl.NumberFormat("id-ID");
const fmtQty = (v) => fmt.format(Math.round((v || 0) * 100) / 100);
function fmtShort(v) {
  const n = Math.round(v || 0);
  // Audit UI 24 Okt (088): desimal koma ("Rp 22,4 M"), bukan titik.
  const d1 = (x) => x.toLocaleString("id-ID", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  if (n >= 1e9) return `Rp ${d1(n / 1e9)} M`;
  if (n >= 1e6) return `Rp ${d1(n / 1e6)} jt`;
  if (n >= 1e3) return `Rp ${(n / 1e3).toFixed(0)} rb`;
  return `Rp ${n}`;
}
const fmtCur = (v) => `Rp ${fmt.format(Math.round(v || 0))}`;
// UAT 24 Okt (audit UI tahap 2) — sumbu Y grafik umur dulu "Rp 24,0 M" sehingga patah dua baris di lebar 60px.
// Sumbu cukup angka + skala (Rp disebut di judul panel).
function fmtAxis(v) {
  const n = Math.round(v || 0);
  const d = (x) => x.toLocaleString("id-ID", { maximumFractionDigits: 1 });
  if (n >= 1e9) return `${d(n / 1e9)} M`;
  if (n >= 1e6) return `${d(n / 1e6)} jt`;
  if (n >= 1e3) return `${d(n / 1e3)} rb`;
  return `${n}`;
}
// K-05 (keputusan pemilik 26 Okt) — coverage TIDAK menentukan kelas; nilai ekstrem dibatasi tampilannya
// (angka hari asli tetap di tooltip). Dulu "2.708.316,9 hr" ditulis apa adanya.
export function fmtCoverage(days, cap = 365) {
  if (days == null) return null;
  if (days > cap) return `> ${fmt.format(cap)} hari`;
  return `${fmtQty(days)} hari`;
}
// Moving average per hari: kecil-kecil tetap terbaca ("< 0,01"), bukan "0".
export function fmtMa(v) {
  const n = Number(v) || 0;
  if (n <= 0) return "0";
  if (n < 0.01) return "< 0,01";
  return n.toLocaleString("id-ID", { maximumFractionDigits: n < 10 ? 2 : 1 });
}
function fmtSinceSale(days) {
  if (days == null) return null;
  if (days <= 0) return "hari ini";
  if (days === 1) return "kemarin";
  return `${fmt.format(days)} hari lalu`;
}
const unitText = (u) => u || "(satuan belum diisi)";

// K-05 — lima kelas laju jual (label dari server bila ada; ini cadangan & warna).
export const CLASS_META = {
  best: { label: "Best seller", color: "#1E9E4A", icon: Flame },
  normal: { label: "Normal", color: "#0058CC", icon: Activity },
  slow: { label: "Slow moving", color: "#D97706", icon: Clock },
  dead: { label: "Tidak bergerak", color: "#C0341D", icon: Snowflake },
  new: { label: "Baru", color: "#7A5AF8", icon: Sparkles },
};
const CLASS_KEYS = ["best", "normal", "slow", "dead", "new"];
const TREND_META = {
  naik: { label: "naik", icon: TrendingUp, color: "#1E9E4A" },
  turun: { label: "turun", icon: TrendingDown, color: "#C0341D" },
  stabil: { label: "stabil", icon: Minus, color: "#6B6B73" },
};

function KPICard({ icon: Icon, label, value, sub, color = "#0058CC", loading, testId, active, onClick, title }) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      title={title}
      className={`text-left rounded-xl border bg-white p-4 flex flex-col gap-2 transition-all ${
        active ? "border-[#0058CC] ring-2 ring-[#0058CC]/20" : "border-[#EFF0F2] hover:border-[#D0D0D5]"
      } ${onClick ? "cursor-pointer" : "cursor-default"}`}
    >
      <div className="flex items-center gap-2">
        <div className="rounded-lg p-1.5" style={{ background: `${color}18` }}><Icon size={16} style={{ color }} /></div>
        <span className="text-[12px] font-semibold text-[#6B6B73]">{label}</span>
      </div>
      {loading ? <div className="h-7 bg-[#F5F5F7] rounded animate-pulse" />
        : <p className="text-[22px] font-bold text-[#1C1C1E] tabular-nums leading-tight">{value}</p>}
      {sub && <p className="text-[11px] text-[#6B6B73]">{sub}</p>}
    </button>
  );
}

// Fase 4 · R3 (L-02) — kartu panel = `.section-card` + `.section-head` baku (dulu kartu `rounded-xl p-4` sendiri).
function Panel({ title, right, children }) {
  return (
    <section className="section-card min-w-0">
      <div className="section-head flex-wrap">
        <h2>{title}</h2>
        {right}
      </div>
      <div className="section-body">{children}</div>
    </section>
  );
}

function ClassBadge({ cls, labels }) {
  const m = CLASS_META[cls] || CLASS_META.normal;
  return (
    <span data-testid={`sa-class-${cls}`} className="inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold"
          style={{ background: `${m.color}18`, color: m.color }}>
      <m.icon size={11} /> {(labels && labels[cls]) || m.label}
    </span>
  );
}

/** K-05 — dasar metode klasifikasi, ditulis singkat untuk pemilik/pembaca layar. */
export function MethodNote({ th = {}, method = {} }) {
  const w = th.velocity_window_days ?? 90;
  const groups = method.rank_groups || [];
  return (
    <details data-testid="sa-method" className="rounded-xl border border-[#E1E8F5] bg-[#F7FAFF] px-4 py-3 text-[12px] text-[#3C3C43]">
      <summary className="cursor-pointer select-none font-semibold text-[#0058CC] flex items-center gap-1.5">
        <Info size={14} /> Dasar kelas: moving average penjualan {w} hari, peringkat persentil per satuan
      </summary>
      <ul className="mt-2 list-disc space-y-1 pl-5" data-testid="sa-method-body">
        <li><b>Ukuran laju jual</b> = rata-rata bergerak (moving average) qty terjual per hari selama {w} hari terakhir,
          dalam satuan dasar produk, dari pesanan penjualan yang hidup (tanpa batal, draf, kedaluwarsa, ditolak, dan
          tanpa pesanan sample). MA {th.trend_window_days ?? 30} hari ditampilkan untuk arah tren (naik/turun bila
          berbeda lebih dari {th.trend_band_pct ?? 10}%).</li>
        <li><b>Peringkat</b> = persentil di antara SKU yang terjual <b>pada satuan yang sama</b> — yard, meter, dan kg
          tidak dibandingkan. <b>Best seller</b> = {th.best_seller_pct ?? 20}% teratas, <b>Slow moving</b> = {th.slow_moving_pct ?? 20}% terbawah,
          sisanya <b>Normal</b>.</li>
        <li><b>Tidak bergerak</b> (dead stock) = punya stok tetapi tidak terjual sama sekali dalam {w} hari.
          <b> Baru</b> = SKU berumur kurang dari {th.new_sku_age_days ?? 90} hari (sejak produk dibuat, roll pertama, atau
          penjualan pertama — mana yang paling awal); tidak diperingkat supaya tidak dinilai tidak adil.</li>
        <li><b>Cukup untuk</b> (coverage) = stok fisik ÷ moving average harian — ditampilkan terpisah dan <b>tidak</b> menentukan
          kelas; di atas {th.coverage_cap_days ?? 365} hari ditulis “&gt; {th.coverage_cap_days ?? 365} hari”.</li>
        <li><b>Dasar metode:</b> analisis ABC/Pareto (sebagian kecil SKU menyumbang sebagian besar penjualan) dan
          klasifikasi FSN (Fast / Slow / Non-moving) yang baku dalam manajemen persediaan; moving average dipakai
          sebagai ukuran laju permintaan karena meredam lonjakan pesanan harian.</li>
        <li><b>Cakupan:</b> kelas dihitung atas seluruh SKU badan usaha; saringan gudang & kategori hanya menyaring
          tampilan.{groups.length > 0 && <> Diperingkat: {groups.map((g) => `${unitText(g.unit)} ${fmt.format(g.ranked)} SKU`).join(" · ")}.</>}
          {" "}Ambang diatur di Pusat Pengaturan › Stok, Satuan &amp; Alokasi.</li>
      </ul>
    </details>
  );
}

/** Kolom tabel "Rincian per SKU" (Fase 4 · R3 · L-07) — isi sel sama dengan tabel lama. */
function saColumns({ labels, w, th, capDays }) {
  const num = "tabular-nums whitespace-nowrap";
  return [
    { key: "classification", header: "Kelas", mobile: "badge", render: (r) => <ClassBadge cls={r.classification} labels={labels} /> },
    { key: "sku", header: "SKU / Produk", mobile: "title", render: (r) => (
      <>
        <p className="font-semibold text-[#1C1C1E]">{r.sku}</p>
        <p className="text-[11px] text-[#6B6B73]">{r.product_name}</p>
      </>
    ) },
    { key: "warehouses", header: "Gudang", priority: 6, className: "text-[11px] text-[#6B6B73]", render: (r) => r.warehouses?.join(", ") || "—" },
    { key: "on_hand", header: "Stok fisik", align: "right", priority: 1, className: num, render: (r) => (r.stock_out
      ? <span className="rounded bg-[#FDECEA] px-1.5 py-0.5 text-[11px] font-semibold text-[#C0341D]" data-testid={`sa-stockout-${r.product_id}`}>stok habis</span>
      : `${fmtQty(r.on_hand_qty)} ${unitText(r.unit)}`) },
    // UAT 24 Okt (audit UI tahap 2) — satu skala Rupiah di kolom (dulu "Rp 1,4 M" bercampur "Rp 928,8 jt").
    { key: "value", header: "Nilai", align: "right", priority: 2, className: `${num} font-semibold`, render: (r) => fmtCur(r.value) },
    { key: "ma", header: <span title={`Moving average qty terjual per hari, ${w} hari terakhir (pesanan hidup)`}>MA {w} hari</span>,
      mobileLabel: `MA ${w} hari`, align: "right", priority: 3, className: num, render: (r) => (
        <span data-testid={`sa-ma-${r.product_id}`}>
          {fmtMa(r.ma_daily)} {unitText(r.unit)}/hari
          <span className="block text-[10.5px] text-[#8E8E93]">terjual {fmtQty(r.sold_qty_window)} {unitText(r.unit)}</span>
        </span>
      ) },
    { key: "trend", header: <span title={`Moving average ${th.trend_window_days ?? 30} hari terakhir dibanding MA ${w} hari`}>Tren {th.trend_window_days ?? 30} hari</span>,
      mobileLabel: `Tren ${th.trend_window_days ?? 30} hari`, align: "right", priority: 5, className: num, render: (r) => {
        const tm = TREND_META[r.trend];
        return (
          <>
            {tm ? (
              <span className="inline-flex items-center gap-1" style={{ color: tm.color }} data-testid={`sa-trend-${r.product_id}`}>
                <tm.icon size={12} /> {tm.label}
              </span>
            ) : <span className="text-[#8E8E93]">—</span>}
            <span className="block text-[10.5px] text-[#8E8E93]">{fmtMa(r.ma_trend_daily)} {unitText(r.unit)}/hari</span>
          </>
        );
      } },
    { key: "percentile", header: <span title="Persentil laju jual di antara SKU terjual bersatuan sama (100 = paling laku)">Persentil</span>,
      mobileLabel: "Persentil", align: "right", priority: 4, className: num, render: (r) => (
        <span data-testid={`sa-pct-${r.product_id}`}>
          {r.percentile == null ? (
            <span className="text-[#8E8E93]">{r.classification === "new" ? "belum diperingkat" : "—"}</span>
          ) : (
            <span title={`Laju jualnya di atas ±${fmt.format(Math.round(r.percentile))}% SKU bersatuan ${unitText(r.unit)} yang terjual`}>
              P{fmt.format(Math.round(r.percentile))}
              <span className="block text-[10.5px] text-[#8E8E93]">dari {fmt.format(r.rank_group_size || 0)} SKU {unitText(r.unit)}</span>
            </span>
          )}
        </span>
      ) },
    { key: "cover", header: <span title="Stok fisik ÷ moving average harian — tidak menentukan kelas">Cukup untuk</span>,
      mobileLabel: "Cukup untuk", align: "right", priority: 7, className: num, render: (r) => (r.days_of_supply == null
        ? <span className="text-[#8E8E93]" title={`Tidak ada penjualan dalam ${w} hari terakhir`}>tanpa penjualan</span>
        : <span data-testid={`sa-cover-${r.product_id}`} title={`${fmtQty(r.days_of_supply)} hari`}>{fmtCoverage(r.days_of_supply, capDays)}</span>) },
    { key: "last_sale", header: "Terjual terakhir", align: "right", priority: 8, className: num,
      render: (r) => (r.days_since_sale == null ? <span className="text-[#8E8E93]">belum pernah</span> : fmtSinceSale(r.days_since_sale)) },
  ];
}

export default function StockAnalyticsView({ currentUser, selectedEntity }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [warehouses, setWarehouses] = useState([]);
  const [warehouseId, setWarehouseId] = useState("all");
  const [category, setCategory] = useState("all");
  const [classFilter, setClassFilter] = useState("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    axios.get(`${API}/warehouses`).then((r) => setWarehouses(r.data || [])).catch(() => {});
  }, []);

  const load = async () => {
    setLoading(true); setError(null);
    try {
      const ent = selectedEntity && selectedEntity !== "all" ? selectedEntity : "all";
      const params = { entity_id: ent };
      if (warehouseId && warehouseId !== "all") params.warehouse_id = warehouseId;
      if (category && category !== "all") params.category = category;
      const r = await axios.get(`${API}/inventory/stock-analytics`, { params });
      setData(r.data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Gagal memuat Analitik Stok");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [selectedEntity, warehouseId, category]); // eslint-disable-line

  const summary = data?.summary || {};
  const byClass = summary.by_class || {};
  const rows = data?.rows || [];
  const th = data?.thresholds || {};
  const method = data?.method || {};
  const labels = method.class_labels || {};
  const w = th.velocity_window_days ?? 90;
  const capDays = th.coverage_cap_days ?? 365;
  const whFiltered = warehouseId && warehouseId !== "all";

  const categoryOpts = useMemo(() => {
    const set = new Set(rows.map((r) => r.category).filter(Boolean));
    return [{ value: "all", label: "Semua Kategori" }, ...[...set].sort().map((c) => ({ value: c, label: c }))];
  }, [rows]);
  const warehouseOpts = [{ value: "all", label: "Semua Gudang" },
    ...warehouses.map((wh) => ({ value: wh.id, label: wh.name }))];

  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((r) =>
      (classFilter === "all" || r.classification === classFilter) &&
      (!q || `${r.sku} ${r.product_name}`.toLowerCase().includes(q))
    );
  }, [rows, classFilter, search]);

  const pieData = CLASS_KEYS
    .map((c) => ({ name: labels[c] || CLASS_META[c].label, key: c, value: byClass[c]?.value || 0, color: CLASS_META[c].color }))
    .filter((d) => d.value > 0);
  const agingData = (summary.aging_buckets || []).map((b) => ({ name: b.bucket, value: b.value || 0 }));
  const hasAgingValue = agingData.some((a) => a.value > 0);
  const classSub = (c) => {
    const v = byClass[c] || {};
    if (c === "best" && summary.stock_out_skus) return `${fmtShort(v.value)} · ada SKU stok habis`;
    return fmtShort(v.value);
  };
  const classTitle = {
    best: `${th.best_seller_pct ?? 20}% teratas laju jual di satuannya`,
    normal: "Di antara Best seller dan Slow moving",
    slow: `${th.slow_moving_pct ?? 20}% terbawah di antara SKU yang terjual (per satuan)`,
    dead: `Punya stok, tidak terjual dalam ${w} hari`,
    new: `SKU berumur < ${th.new_sku_age_days ?? 90} hari — belum diperingkat`,
  };

  return (
    <div data-testid="stock-analytics-view" className="space-y-4">
      {/* Fase 4 · R3 (L-02) — kepala halaman = PageHeader baku (dulu kicker "ANALITIK" + h1 20 px buatan sendiri;
          lokasi kini dibaca dari breadcrumb menu). */}
      <PageHeader icon={TrendingUp} title="Analitik Stok — Kelas Laju Jual" testId="sa-header"
        subtitle={(
          <span data-testid="sa-subtitle">
            Kelas per SKU dari moving average penjualan {w} hari (pesanan hidup), diperingkat per satuan:
            Best seller {th.best_seller_pct ?? 20}% teratas · Slow moving {th.slow_moving_pct ?? 20}% terbawah ·
            Tidak bergerak = ada stok, tak terjual · Baru = umur &lt; {th.new_sku_age_days ?? 90} hari.
          </span>
        )}
        actions={(
          <>
            <KNSelect data-testid="sa-warehouse-filter" value={warehouseId} onValueChange={setWarehouseId}
              options={warehouseOpts} className="field !py-1 !px-2 text-[12px] w-auto" placeholder="Gudang" />
            <KNSelect data-testid="sa-category-filter" value={category} onValueChange={setCategory}
              options={categoryOpts} className="field !py-1 !px-2 text-[12px] w-auto" placeholder="Kategori" />
            <button type="button" data-testid="sa-refresh" onClick={load} className="secondary-button">
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Muat ulang
            </button>
          </>
        )} />

      <MethodNote th={th} method={method} />

      {error && <ErrorNotice message={error} onRetry={load} />}

      {/* KPI row (klik untuk filter kelas) */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <KPICard testId="sa-kpi-total-value" icon={Boxes} label="Nilai Persediaan" color="#0058CC" loading={loading}
          value={fmtShort(summary.total_on_hand_value)} sub={`${summary.sku_count ?? 0} SKU · biaya penuh, termasuk biaya angkut/impor ${fmtShort(summary.total_landed_value || 0)}`}
          active={classFilter === "all"} onClick={() => setClassFilter("all")} />
        {CLASS_KEYS.map((c) => (
          <KPICard key={c} testId={`sa-kpi-${c}`} icon={CLASS_META[c].icon} label={labels[c] || CLASS_META[c].label}
            color={CLASS_META[c].color} loading={loading} value={byClass[c]?.count ?? 0} sub={classSub(c)}
            title={classTitle[c]} active={classFilter === c} onClick={() => setClassFilter(c)} />
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Distribusi Nilai per Kelas">
          {pieData.length === 0 ? (
            <EmptyBox icon={Layers} text="Belum ada data persediaan untuk ditampilkan." />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={(e) => e.name}>
                  {pieData.map((d) => <Cell key={d.key} fill={d.color} />)}
                </Pie>
                <Tooltip formatter={(v) => fmtCur(v)} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Panel>
        <Panel title="Umur Persediaan (nilai Rp per umur)" right={<span className="text-[11px] text-[#6B6B73]">hari sejak masuk gudang</span>}>
          {!hasAgingValue ? (
            <EmptyBox icon={Clock} text="Belum ada nilai persediaan untuk dihitung umurnya." />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={agingData} margin={{ top: 8, right: 8, left: 8, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F0F0F2" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={fmtAxis} tick={{ fontSize: 10 }} width={52} />
                <Tooltip formatter={(v) => fmtCur(v)} />
                <Bar dataKey="value" fill="#0058CC" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Panel>
      </div>

      {/* Table */}
      <Panel
        title="Rincian per SKU"
        right={
          <div className="relative">
            <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-[#8E8E93]" />
            <input data-testid="sa-search" value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="Cari SKU / nama…" aria-label="Cari SKU atau nama produk"
              className="field !py-1 !pl-7 !text-[12px] w-44 max-w-full" />
          </div>
        }
      >
        {whFiltered && (
          <p className="mb-2 text-[11px] text-[#6B6B73]" data-testid="sa-wh-note">
            Saringan gudang: stok, nilai, dan “cukup untuk” memakai stok gudang ini; laju jual & kelas tetap dari
            penjualan seluruh badan usaha (pesanan tidak tercatat per gudang). SKU yang stoknya habis hanya tampil tanpa saringan gudang.
          </p>
        )}
        {/* Fase 4 · R3 (L-07) — `<table>` mentah min 1080 px → ResponsiveTable: `.data-table` di desktop (gulir di
            dalam wadahnya), kartu di HP 390 px (Kelas = lencana, SKU = judul; semua kolom tetap ada). Testid
            `sa-row-<id>`, `sa-ma-`, `sa-trend-`, `sa-pct-`, `sa-cover-`, `sa-stockout-` tetap. */}
        <ResponsiveTable testId="sa" rowKey="product_id" rows={loading ? [] : filteredRows} loading={loading}
          empty={<EmptyBox icon={Boxes} text={classFilter !== "all" || search
            ? "Tidak ada SKU sesuai saringan kelas/pencarian."
            : "Tidak ada SKU sesuai filter."} />}
          columns={saColumns({ labels, w, th, capDays })} />
      </Panel>
    </div>
  );
}

function EmptyBox({ icon: Icon, text }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
      <div className="rounded-full bg-[#F5F5F7] p-3"><Icon size={22} className="text-[#8E8E93]" /></div>
      <p className="text-[12px] text-[#6B6B73] max-w-xs">{text}</p>
    </div>
  );
}
