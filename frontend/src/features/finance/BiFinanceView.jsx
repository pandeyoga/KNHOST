/**
 * BiFinanceView (FINANCE) — Dashboard BI Keuangan.
 * Tren bulanan (Pendapatan/Beban/Laba Bersih), KPI YTD, rasio, & perbandingan
 * antar PT. Sumber: /api/finance/bi. Chart: recharts. Gaya modul GL/existing.
 */
import { apiErrorText } from "../../utils/apiError";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ComposedChart, BarChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, Cell,
} from "recharts";
import { RefreshCw, TrendingUp, Percent, Scale, Building2, Activity, Landmark } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import KNSelect from "../../components/KNSelect";
import { formatCompactIDR, formatCurrency, formatPct } from "../../utils/formatters";
import FinReportLink from "./FinReportLink";

const NOW = new Date();
const YEARS = Array.from({ length: 6 }, (_, i) => {
  const y = String(NOW.getFullYear() - i);
  return { value: y, label: y };
});

const COLOR = {
  revenue: "#1B7F4B",
  expense: "#C0392B",
  net: "#6B219A",
  neutral: "#0058CC",
};

// UAT 24 Okt (audit UI tahap 2) — G1-14: salinan lokal compactIDR ("150.0 jt") diganti formatter bersama id-ID.
const compactIDR = (v) => formatCompactIDR(Number(v || 0));

// Audit UI 24 Okt (092/093): rasio dulu "2722.02x" (desimal titik, tanpa batas). Desimal koma;
// di atas 50x angka tidak bermakna (kewajiban lancar hampir nol) → "> 50x", angka persis di tooltip.
const RATIO_CAP = 50;
const fmtRatio = (v) => {
  if (v == null || Number.isNaN(Number(v))) return "—";
  const n = Number(v);
  if (n > RATIO_CAP) return `> ${RATIO_CAP}x`;
  return `${n.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}x`;
};
const fmtPctId = (v, d = 1) => (v == null ? "—" : `${Number(v).toLocaleString("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d })}%`);

const entityParam = (selectedEntity) =>
  selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {};

export default function BiFinanceView({ selectedEntity }) {
  const [year, setYear] = useState(String(NOW.getFullYear()));
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const res = await axios.get(`${API}/finance/bi`, { params: { year, ...entityParam(selectedEntity) } });
      setData(res.data || null);
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat data BI Keuangan."));
    } finally {
      setLoading(false);
    }
  }, [year, selectedEntity]);

  useEffect(() => { load(); }, [load]);

  const ratios = data?.ratios || {};
  const monthly = data?.monthly || [];
  const comparison = data?.entity_comparison || [];

  // Empty-state detection: BE selalu mengisi 12 bulan/entitas walau semua nol,
  // jadi cek "aktivitas nyata" (bukan sekadar length === 0) untuk trigger empty.
  const hasMonthlyData = monthly.length === 0 || monthly.some(
    (m) => Number(m?.revenue || 0) !== 0 || Number(m?.expense || 0) !== 0 || Number(m?.net_income || 0) !== 0,
  );
  const monthlyIsEmpty = monthly.length === 0 || !hasMonthlyData;
  const comparisonIsEmpty = comparison.length === 0 || !comparison.some(
    (c) => Number(c?.revenue || 0) !== 0 || Number(c?.expense || 0) !== 0 || Number(c?.net_income || 0) !== 0,
  );

  return (
    <div data-testid="bi-finance-view">
      {/* Fase 3 · P4 (D-10) — 4 kartu KPI atas (Pendapatan/Beban/Laba Bersih/Marjin Bersih) DIHAPUS: angka yang sama
          sudah di Dasbor Keuangan (ringkas) & Laporan Keuangan (rinci), dan Marjin Bersih tampil dua kali di layar ini.
          BI kini fokus pada tren, rasio (Marjin Bersih sekali) dan perbandingan PT + tautan ke Laporan Keuangan. */}
      <div className="section-card">
        <div className="section-head flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <Activity size={15} className="text-[#6B219A]" />
            <h3 className="text-[13px] font-bold text-[#1C1C1E]">BI Keuangan · Analitik</h3>
          </div>
          <div className="flex flex-wrap items-center gap-2 ml-auto">
            <FinReportLink testId="bi-pl-link" />
            <div className="w-[110px]">
              <KNSelect data-testid="bi-year-select" className="field py-1.5 text-[12px]" value={year} onValueChange={setYear} options={YEARS} />
            </div>
            <button data-testid="bi-refresh" className="icon-button" onClick={load} aria-label="Refresh"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
          </div>
        </div>

        <div className="section-body">
          <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="bi-error" />

          {loading ? (
            <div className="grid gap-3" data-testid="bi-loading">
              <div className="h-[280px] bg-[#F5F5F7] rounded animate-pulse" />
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">{[0, 1, 2, 3].map((i) => <div key={i} className="h-20 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
            </div>
          ) : (
            <>
              {/* Tren Bulanan */}
              <div className="rounded-lg border border-[#EFF0F2] p-3 mb-4" data-testid="bi-monthly-chart">
                <div className="flex items-center gap-2 mb-3">
                  <TrendingUp size={14} className="text-[#6B219A]" />
                  <h4 className="text-[12px] font-bold text-[#1C1C1E]">Tren Bulanan {year} — Pendapatan · Beban · Laba Bersih</h4>
                </div>
                {monthlyIsEmpty ? (
                  <div
                    className="h-[280px] flex flex-col items-center justify-center text-center"
                    data-testid="bi-monthly-empty"
                  >
                    <Activity size={22} className="text-[#C7C7CC] mb-2" />
                    <p className="text-[12px] font-semibold text-[#1C1C1E]">Belum ada data tren bulanan</p>
                    <p className="text-[11px] text-[#8E8E93] mt-1">Tidak ada jurnal operasional pada tahun {year}. Coba pilih tahun lain atau muat ulang.</p>
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={280}>
                    <ComposedChart data={monthly} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#EFF0F2" />
                      <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 10 }} tickFormatter={compactIDR} width={56} />
                      <Tooltip formatter={(val, name) => [formatCurrency(val), name]}
                        contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #EFF0F2" }} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Bar dataKey="revenue" name="Pendapatan" fill={COLOR.revenue} radius={[4, 4, 0, 0]} maxBarSize={26} />
                      <Bar dataKey="expense" name="Beban" fill={COLOR.expense} radius={[4, 4, 0, 0]} maxBarSize={26} />
                      <Line type="linear" dataKey="net_income" name="Laba Bersih" stroke={COLOR.net} strokeWidth={2.5} dot={{ r: 2 }} />
                    </ComposedChart>
                  </ResponsiveContainer>
                )}
              </div>

              {/* Rasio */}
              <p className="text-[11px] font-bold uppercase tracking-wide text-[#8E8E93] mb-2">Rasio Keuangan</p>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
                <RatioCard testId="bi-ratio-gross" label="Marjin Kotor" value={fmtPctId(ratios.gross_margin ?? 0)} icon={Percent} />
                <RatioCard testId="bi-ratio-net" label="Marjin Bersih" value={fmtPctId(ratios.net_margin ?? 0)} icon={Percent} />
                <RatioCard testId="bi-ratio-current" label="Rasio Lancar"
                  value={fmtRatio(ratios.current_ratio)} icon={Scale}
                  hint={`Aset Lancar ${formatCurrency(ratios.current_assets)} / Kwj. Lancar ${formatCurrency(ratios.current_liabilities)}`} />
                <RatioCard testId="bi-ratio-dte" label="Utang thd Ekuitas"
                  value={fmtRatio(ratios.debt_to_equity)} icon={Landmark}
                  hint={`Kewajiban ${formatCurrency(ratios.liabilities_total)} / Ekuitas ${formatCurrency(ratios.equity_total)}`} />
              </div>

              {/* Perbandingan antar PT */}
              {comparisonIsEmpty ? (
                <div
                  className="rounded-lg border border-dashed border-[#EFF0F2] p-6 text-center"
                  data-testid="bi-entity-empty"
                >
                  <Building2 size={22} className="text-[#C7C7CC] mx-auto mb-2" />
                  <p className="text-[12px] font-semibold text-[#1C1C1E]">Belum ada data perbandingan antar entitas</p>
                  <p className="text-[11px] text-[#8E8E93] mt-1">Tidak ada entitas dengan aktivitas GL pada tahun {year}.</p>
                </div>
              ) : (
                <>
                  <p className="text-[11px] font-bold uppercase tracking-wide text-[#8E8E93] mb-2">Perbandingan Antar Entitas (PT)</p>
                  {/* Audit UI 24 Okt (093): saat satu badan usaha dipilih, daftar hanya berisi PT itu —
                      dulu tanpa keterangan sehingga terbaca "grup cuma punya 1 PT". */}
                  {comparison.length <= 1 && (
                    <p className="mb-2 text-[11px] text-[#6B6B73]" data-testid="bi-entity-scope-note">
                      Hanya badan usaha yang sedang dipilih yang ditampilkan. Pilih “Semua badan usaha” di
                      pemilih atas untuk membandingkan seluruh PT (lihat juga Konsolidasi Grup).
                    </p>
                  )}
                  <div className="grid lg:grid-cols-2 gap-4">
                    <div className="rounded-lg border border-[#EFF0F2] p-3" data-testid="bi-entity-chart">
                      <ResponsiveContainer width="100%" height={Math.max(180, comparison.length * 56)}>
                        <BarChart data={comparison} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#EFF0F2" horizontal={false} />
                          <XAxis type="number" tick={{ fontSize: 10 }} tickFormatter={compactIDR} />
                          <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={70} />
                          <Tooltip formatter={(val, name) => [formatCurrency(val), name]}
                            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #EFF0F2" }} />
                          <Legend wrapperStyle={{ fontSize: 11 }} />
                          <Bar dataKey="revenue" name="Pendapatan" fill={COLOR.revenue} radius={[0, 4, 4, 0]} maxBarSize={18} />
                          <Bar dataKey="net_income" name="Laba Bersih" fill={COLOR.net} radius={[0, 4, 4, 0]} maxBarSize={18}>
                            {comparison.map((r, i) => (
                              <Cell key={i} fill={r.net_income >= 0 ? COLOR.net : COLOR.expense} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="overflow-auto rounded-md border border-[#EFF0F2]">
                      <table className="w-full text-[12px]" data-testid="bi-entity-table">
                        <thead>
                          <tr className="text-left text-[10px] font-bold uppercase text-[#8E8E93] bg-[#FAFBFC] border-b border-[#EFF0F2]">
                            <th className="px-3 py-2">Entitas</th>
                            <th className="px-3 py-2 text-right">Pendapatan</th>
                            <th className="px-3 py-2 text-right">Beban</th>
                            <th className="px-3 py-2 text-right">Laba Bersih</th>
                            <th className="px-3 py-2 text-right">Marjin</th>
                          </tr>
                        </thead>
                        <tbody>
                          {comparison.length === 0 ? (
                            <tr data-testid="bi-entity-table-empty">
                              <td colSpan={5} className="px-3 py-6 text-center text-[11px] text-[#8E8E93]">Belum ada data entitas untuk ditampilkan.</td>
                            </tr>
                          ) : (
                            comparison.map((r) => (
                              <tr key={r.entity_id} data-testid={`bi-entity-row-${r.entity_id}`} className="border-b border-[#F5F5F7] last:border-0">
                                <td className="px-3 py-2 font-semibold text-[#1C1C1E] inline-flex items-center gap-1.5"><Building2 size={12} className="text-[#6B219A]" />{r.name}</td>
                                <td className="px-3 py-2 text-right tabular-nums text-[#1B7F4B]">{formatCurrency(r.revenue)}</td>
                                <td className="px-3 py-2 text-right tabular-nums text-[#C0392B]">{formatCurrency(r.expense)}</td>
                                <td className={`px-3 py-2 text-right tabular-nums font-semibold ${r.net_income >= 0 ? "text-[#1B7F4B]" : "text-[#C0392B]"}`}>{formatCurrency(r.net_income)}</td>
                                <td className="px-3 py-2 text-right tabular-nums">{formatPct(Number(r.net_margin || 0))}</td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </>
              )}
              <p className="mt-3 text-[11px] text-[#9A9BA3]">Angka operasional (mengecualikan jurnal penutup). Rasio neraca memakai posisi akhir tahun.</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function RatioCard({ label, value, icon: Icon, hint, testId }) {
  return (
    <div className="rounded-lg border border-[#EFF0F2] px-3 py-2.5" data-testid={testId}>
      <div className="flex items-center gap-1.5 mb-0.5">
        <Icon size={13} className="text-[#6B219A]" />
        <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p>
      </div>
      <p className="text-[16px] font-bold tabular-nums text-[#1C1C1E]" data-testid={`${testId}-value`}>{value}</p>
      {hint && <p className="text-[9px] text-[#9A9BA3] mt-0.5 truncate" title={hint}>{hint}</p>}
    </div>
  );
}
