/**
 * FinanceTowerParts (FINANCE) — sub-panel dashboard Control Tower.
 * Dipisah agar FinanceTowerView tetap < 500 baris (batas guardrail).
 */
import {
  ComposedChart, BarChart, Bar, Line, Cell, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from "recharts";
import { TrendingUp, PieChart as PieIcon, Users, Truck, Scale, Landmark, Percent, PiggyBank } from "lucide-react";
import { FC, compactIDR, chartTooltip, Panel, EmptyState, formatCurrency } from "./financeShared";
import { isZeroMetric } from "../../components/ListPageParts";
import FinReportLink from "./FinReportLink";

export function MonthlyTrendPanel({ monthly }) {
  const rows = monthly || [];
  const empty = rows.length === 0 || !rows.some((m) => m.revenue || m.expense || m.net_income);
  const withExpense = rows.map((m) => ({ ...m, expense: (m.cogs || 0) + (m.opex || 0) }));
  return (
    <Panel title="Tren Bulanan — Pendapatan · Beban · Laba Bersih" icon={TrendingUp} testId="tower-monthly">
      {empty ? (
        <EmptyState icon={TrendingUp} title="Belum ada aktivitas GL tahun ini" testId="tower-monthly-empty" />
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={withExpense} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={FC.grid} />
            <XAxis dataKey="label" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} tickFormatter={compactIDR} width={54} />
            <Tooltip formatter={(v, n) => [formatCurrency(v), n]} {...chartTooltip} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="revenue" name="Pendapatan" fill={FC.revenue} radius={[4, 4, 0, 0]} maxBarSize={22} />
            <Bar dataKey="expense" name="Beban" fill={FC.expense} radius={[4, 4, 0, 0]} maxBarSize={22} />
            <Line type="linear" dataKey="net_income" name="Laba Bersih" stroke={FC.net} strokeWidth={2.5} dot={{ r: 2 }} />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}

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

export function RatiosStrip({ ratios }) {
  const r = ratios || {};
  const exact = (v) => (v == null ? "" : `Nilai persis: ${Number(v).toLocaleString("id-ID", { maximumFractionDigits: 2 })}x`);
  const items = [
    // Fase 3 · P4 (D-10) — Marjin Bersih tampil SEKALI di dasbor (dulu juga di baris KPI Laba-Rugi).
    { label: "Marjin Kotor", value: fmtPctId(r.gross_margin), icon: Percent, hint: "laba kotor ÷ pendapatan, tahun berjalan" },
    { label: "Marjin Bersih", value: fmtPctId(r.net_margin), icon: Percent, hint: "laba bersih ÷ pendapatan, tahun berjalan" },
    { label: "Rasio Lancar", value: fmtRatio(r.current_ratio), icon: Scale, title: exact(r.current_ratio),
      hint: Number(r.current_ratio) > RATIO_CAP ? "kewajiban lancar hampir nol" : "aset lancar ÷ kewajiban lancar" },
    { label: "Utang thd Ekuitas", value: fmtRatio(r.debt_to_equity), icon: Landmark, title: exact(r.debt_to_equity),
      hint: "total kewajiban ÷ ekuitas" },
  ];
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3" data-testid="tower-ratios">
      {items.map((it) => (
        <div key={it.label} className="rounded-xl border border-[#EFF0F2] bg-white px-3 py-2.5" title={it.title || undefined}>
          <div className="flex items-center gap-1.5 mb-0.5"><it.icon size={12} className="text-[#6B219A]" /><p className="text-[11px] font-bold uppercase tracking-wide text-[#8E8E93]">{it.label}</p></div>
          <p className="text-[15px] font-bold tabular-nums text-[#1C1C1E]">{it.value}</p>
          {it.hint && <p className="text-[11px] text-[#9A9BA3]">{it.hint}</p>}
        </div>
      ))}
    </div>
  );
}

function AgingBars({ data, testId }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 4, bottom: 0 }} data-testid={testId}>
        <CartesianGrid strokeDasharray="3 3" stroke={FC.grid} />
        <XAxis dataKey="name" tick={{ fontSize: 10 }} />
        <YAxis tick={{ fontSize: 10 }} tickFormatter={compactIDR} width={48} />
        <Tooltip formatter={(v) => formatCurrency(v)} {...chartTooltip} />
        <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={36}>
          {data.map((d, i) => <Cell key={i} fill={d.color} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function ArAgingPanel({ ar }) {
  const a = ar?.aging || {};
  const data = [
    { name: "Lancar", value: a.current || 0, color: FC.revenue },
    { name: "1-30", value: a.b1_30 || 0, color: FC.teal },
    { name: "31-60", value: a.b31_60 || 0, color: FC.amber },
    { name: "61-90", value: a.b61_90 || 0, color: "#E67E22" },
    { name: ">90", value: a.b90_plus || 0, color: FC.expense },
  ];
  return (
    <Panel title="Umur Piutang (AR Aging)" icon={Users} testId="tower-ar-aging">
      <AgingBars data={data} testId="tower-ar-aging-chart" />
    </Panel>
  );
}

export function ApAgingPanel({ ap }) {
  const a = ap?.aging || {};
  const data = [
    { name: "0-30", value: a.d0_30 || 0, color: FC.teal },
    { name: "31-60", value: a.d31_60 || 0, color: FC.amber },
    { name: "61-90", value: a.d61_90 || 0, color: "#E67E22" },
    { name: ">90", value: a.d90_plus || 0, color: FC.expense },
  ];
  return (
    <Panel title="Umur Hutang (AP Aging)" icon={Truck} testId="tower-ap-aging">
      <AgingBars data={data} testId="tower-ap-aging-chart" />
    </Panel>
  );
}

export function TopArPanel({ ar }) {
  const rows = ar?.top || [];
  return (
    <Panel title="Piutang Terbesar" icon={Users} testId="tower-top-ar">
      {rows.length === 0 ? <p className="text-[11px] text-[#9A9BA3] py-3 text-center">Tidak ada piutang.</p> : (
        <div className="space-y-1.5">
          {rows.map((c, i) => (
            <div key={i} data-testid={`tower-ar-row-${i}`} className="flex items-center justify-between gap-2 text-[12px] border-b border-[#F5F5F7] last:border-0 pb-1.5">
              <span className="font-semibold text-[#1C1C1E] truncate max-w-[150px]" title={c.customer_name}>{c.customer_name}</span>
              <div className="text-right"><span className="tabular-nums font-semibold text-[#1B7F4B]">{formatCurrency(c.outstanding)}</span>
                {c.oldest_days > 0 && <span className="block text-[9px] text-[#C0392B]">telat {c.oldest_days}h</span>}</div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

export function TopApPanel({ ap }) {
  const rows = ap?.top || [];
  return (
    <Panel title="Hutang Terbesar" icon={Truck} testId="tower-top-ap">
      {rows.length === 0 ? <p className="text-[11px] text-[#9A9BA3] py-3 text-center">Tidak ada hutang.</p> : (
        <div className="space-y-1.5">
          {rows.map((b, i) => (
            <div key={i} data-testid={`tower-ap-row-${i}`} className="flex items-center justify-between gap-2 text-[12px] border-b border-[#F5F5F7] last:border-0 pb-1.5">
              <span className="font-semibold text-[#1C1C1E] truncate max-w-[150px]" title={b.party}>{b.party || b.number}</span>
              {/* G1-38 — per pemasok (bukan per tagihan): sisa + jumlah tagihan, seperti panel piutang. */}
              <div className="text-right"><span className="tabular-nums font-semibold text-[#C0392B]">{formatCurrency(b.amount)}</span>
                {(b.bill_count || 0) > 0 && <span className="block text-[9px] text-[#8E8E93]">{b.bill_count} tagihan</span>}</div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

// Fase 3 · P4 (D-10) — total "Posisi Kas" sudah di kartu KPI atas (label sumber K-02); panel ini hanya RINCIAN per
// akun, supaya angka yang sama tidak tampil dua kali di satu layar.
export function CashPanel({ cash }) {
  const accounts = cash?.accounts || [];
  return (
    <Panel title="Rincian Kas per Akun (GL)" icon={PieIcon} testId="tower-cash-panel">
      {accounts.length === 0 ? <p className="text-[11px] text-[#9A9BA3] py-3 text-center">Belum ada akun kas/bank bersaldo.</p> : (
        <div className="space-y-1.5">
          {accounts.map((a) => (
            <div key={a.code} className="flex items-center justify-between text-[12px] border-b border-[#F5F5F7] last:border-0 pb-1.5">
              <span className="text-[#6B6B73]"><span className="text-[10px] text-[#9A9BA3] mr-1.5">{a.code}</span>{a.name}</span>
              <span className="tabular-nums font-semibold text-[#1C1C1E]">{formatCurrency(a.balance)}</span>
            </div>
          ))}
        </div>
      )}
      <p className="mt-2 text-[10.5px] text-[#9A9BA3]">Jumlahnya = Posisi Kas di kartu atas.</p>
    </Panel>
  );
}

/**
 * Fase 3 · P4 (D-10) — SATU kartu ringkas Laba-Rugi YTD (dulu 4 kartu KPI terpisah + Marjin Bersih ganda).
 * Rincian laba-rugi hanya di Laporan Keuangan (tautan di kepala kartu).
 */
function PlStat({ label, value, sub, tone = "text-[#1C1C1E]", testId }) {
  const zero = isZeroMetric(value);
  return (
    <div className="min-w-0" data-testid={testId}>
      <p className="text-[11px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p>
      <p className={`text-[15px] sm:text-[17px] font-bold tabular-nums break-words ${zero ? "text-[#8E8E93]" : tone}`}
        data-testid={`${testId}-value`}>{value}</p>
      {sub && <p className="text-[10px] text-[#9A9BA3] mt-0.5">{sub}</p>}
    </div>
  );
}

export function PlYtdCard({ ytd = {}, mtd = {}, year }) {
  const net = ytd.net_income ?? 0;
  return (
    <Panel title={`Laba-Rugi YTD ${year || ""}`.trim()} icon={PiggyBank} testId="tower-pl-ytd"
      actions={<FinReportLink testId="tower-pl-link" />}>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <PlStat testId="tower-kpi-rev-ytd" label="Pendapatan YTD" value={formatCurrency(ytd.revenue)} tone="text-[#1B7F4B]" />
        <PlStat testId="tower-kpi-net-ytd" label="Laba Bersih YTD" value={formatCurrency(net)} tone={net >= 0 ? "text-[#1C1C1E]" : "text-[#C0392B]"} />
        {/* Audit UI 24 Okt (085↔092): pendapatan JURNAL bulan berjalan (diakui saat kirim) — beda dengan
            "Nilai Pesanan 30 Hari" di Analitik › Ringkasan. */}
        <PlStat testId="tower-kpi-rev-mtd" label="Pendapatan Bulan Ini (Jurnal)" value={formatCurrency(mtd.revenue)}
          sub={`diakui saat kirim · laba ${formatCurrency(mtd.net_income)}`} />
      </div>
    </Panel>
  );
}
