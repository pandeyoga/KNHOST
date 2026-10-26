/**
 * FinanceTowerView (FINANCE) — Dashboard Keuangan terpadu (Control Tower).
 * KPI posisi kas/AR/AP/modal kerja + Laba-Rugi MTD/YTD + tren + aging + rasio.
 * Sumber: /api/finance/tower. Panel dipisah ke FinanceTowerParts.jsx.
 */
import { apiErrorText } from "../../utils/apiError";
import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Wallet, Users, Truck, Coins, CalendarDays } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import { FC, entityParam, KpiCard, EmptyState, formatCurrency } from "./financeShared";
import {
  MonthlyTrendPanel, RatiosStrip, ArAgingPanel, ApAgingPanel,
  TopArPanel, TopApPanel, CashPanel, PlYtdCard,
} from "./FinanceTowerParts";

export default function FinanceTowerView({ selectedEntity }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const res = await axios.get(`${API}/finance/tower`, { params: { ...entityParam(selectedEntity) } });
      setData(res.data || null);
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat dashboard keuangan."));
    } finally { setLoading(false); }
  }, [selectedEntity]);

  useEffect(() => { load(); }, [load]);

  const ytd = data?.pl?.ytd || {};
  const mtd = data?.pl?.mtd || {};

  return (
    <div data-testid="finance-tower-view">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-[11px] text-[#8E8E93]">
          <CalendarDays size={13} className="text-[#6B219A]" />
          <span>Periode berjalan: <b className="text-[#1C1C1E]">{data?.period?.month || "—"}</b> · YTD {data?.period?.year || ""}</span>
        </div>
        <button data-testid="tower-refresh" className="icon-button" onClick={load} aria-label="Refresh"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
      </div>

      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="tower-error" />

      {loading ? (
        <div className="grid gap-3" data-testid="tower-loading">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">{[0, 1, 2, 3].map((i) => <div key={i} className="h-20 bg-[#F5F5F7] rounded-xl animate-pulse" />)}</div>
          <div className="h-[280px] bg-[#F5F5F7] rounded-xl animate-pulse" />
        </div>
      ) : !data ? (
        /* FASE P5 — dulu `null`: seluruh dasbor keuangan menjadi HALAMAN KOSONG tanpa
           satu kalimat pun. Pengguna tak bisa membedakan "belum ada data" dari "gagal
           memuat" — padahal bilah galat di atas hanya muncul bila ada exception. */
        <EmptyState icon={Wallet} testId="tower-empty"
          title="Belum ada data keuangan untuk badan usaha ini"
          hint="Angka muncul setelah ada jurnal, kas, piutang, atau hutang tercatat pada periode berjalan." />
      ) : (
        <>
          {/* Baris KPI likuiditas */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
            {/* Keputusan pemilik K-01/K-02 (26 Okt) — label sumber di tiap kartu: kas = saldo buku besar akun kas+bank
                (angka utama "Kas & Bank"); piutang = sub-buku dokumen belum lunas, semua pelanggan (= layar Piutang). */}
            <KpiCard testId="tower-kpi-cash" label="Posisi Kas" value={formatCurrency(data.cash?.total)} icon={Wallet} accent={FC.cash} tone="text-[#0058CC]" sub="Saldo buku besar akun kas & bank" />
            <KpiCard testId="tower-kpi-ar" label="Piutang (AR)" value={formatCurrency(data.ar?.outstanding)} icon={Users} accent={FC.revenue} tone="text-[#1B7F4B]" sub={`Sub-buku (dokumen belum lunas) · lewat jatuh tempo ${formatCurrency(data.ar?.overdue)}`} />
            <KpiCard testId="tower-kpi-ap" label="Hutang (AP)" value={formatCurrency(data.ap?.outstanding)} icon={Truck} accent={FC.expense} tone="text-[#C0392B]" />
            <KpiCard testId="tower-kpi-wc" label="Modal Kerja Bersih" value={formatCurrency(data.working_capital)} icon={Coins} accent={FC.purple} tone={(data.working_capital ?? 0) >= 0 ? "text-[#6B219A]" : "text-[#C0392B]"} sub="Kas + AR − AP" />
          </div>

          {/* Fase 3 · P4 (D-10) — dulu 4 kartu KPI Laba-Rugi (Pendapatan/Laba/Marjin Bersih/Pendapatan bulan ini);
              Marjin Bersih juga tampil di Rasio dan Posisi Kas juga di panel kas → angka ganda di satu layar.
              Kini satu kartu ringkas + "Rincian di Laporan Keuangan →"; Marjin Bersih hanya di Rasio. */}
          <div className="mb-3"><PlYtdCard ytd={ytd} mtd={mtd} year={data?.period?.year} /></div>

          <div className="grid lg:grid-cols-3 gap-3 mb-3">
            <div className="lg:col-span-2"><MonthlyTrendPanel monthly={data.monthly} /></div>
            <CashPanel cash={data.cash} />
          </div>

          <div className="mb-3"><RatiosStrip ratios={data.ratios} /></div>

          <div className="grid lg:grid-cols-2 gap-3 mb-3">
            <ArAgingPanel ar={data.ar} />
            <ApAgingPanel ap={data.ap} />
          </div>

          <div className="grid lg:grid-cols-2 gap-3">
            <TopArPanel ar={data.ar} />
            <TopApPanel ap={data.ap} />
          </div>
        </>
      )}
      <p className="mt-3 text-[11px] text-[#9A9BA3]">Dashboard terpadu — posisi kas & rasio memakai saldo akhir; Laba-Rugi operasional (exclude penutup). Rincian laba-rugi, neraca & arus kas ada di Laporan Keuangan.</p>
    </div>
  );
}
