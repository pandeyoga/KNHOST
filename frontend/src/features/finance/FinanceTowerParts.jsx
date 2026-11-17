/**
 * FinanceTowerParts (FINANCE) — sub-panel dashboard Control Tower.
 * Dipisah agar FinanceTowerView tetap < 500 baris (batas guardrail).
 *
 * Pola UI 16 Nov (04_POLA_UI §1.5 · masukan pemilik M32): tiap kartu/panel angka punya jalan ke daftar sumbernya —
 * rasio → Laporan Keuangan (Laba-Rugi/Neraca), umur & terbesar → Piutang / Tagihan Pemasok, nama → kartu pelanggan/
 * pemasok, rincian kas → Rekening & Saldo. `onOpen` / `openReport(tab)` dari layar induk = `undefined` bila peran tidak
 * boleh membuka layar itu (kartu tampil tanpa tautan, bukan tombol mati).
 */
import {
  ComposedChart, BarChart, Bar, Line, Cell, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from "recharts";
import {
  ChevronRight, TrendingUp, PieChart as PieIcon, Users, Truck, Scale, Landmark, Percent, PiggyBank,
} from "lucide-react";
import { FC, compactIDR, chartTooltip, Panel, EmptyState, formatCurrency } from "./financeShared";
import { isZeroMetric, MetricRow } from "../../components/ListPageParts";
import { CustomerCardLink, SupplierCardLink } from "./cards/partyCards";
import FinReportLink from "./FinReportLink";

/** Tautan baku di kepala panel ("Buka Piutang ›"); tanpa `onClick` (peran tak boleh membuka) → tidak dirender. */
export function PanelLink({ onClick, label, testId }) {
  if (!onClick) return null;
  return (
    <button type="button" className="link-button" onClick={onClick} data-testid={testId}>
      {label} <ChevronRight size={12} aria-hidden="true" />
    </button>
  );
}

export function MonthlyTrendPanel({ monthly }) {
  const rows = monthly || [];
  const empty = rows.length === 0 || !rows.some((m) => m.revenue || m.expense || m.net_income);
  const withExpense = rows.map((m) => ({ ...m, expense: (m.cogs || 0) + (m.opex || 0) }));
  return (
    <Panel title="Tren Bulanan — Pendapatan · Beban · Laba Bersih" icon={TrendingUp} testId="tower-monthly"
      actions={<FinReportLink testId="tower-monthly-link" label="Laba-Rugi" />}>
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

/** M32 — kartu rasio = tautan ke laporan sumbernya: marjin → Laba-Rugi, rasio neraca → Neraca. `openReport(tab)` →
 *  handler klik (atau `undefined` bila peran tidak boleh membuka Laporan Keuangan). */
export function RatiosStrip({ ratios, openReport = () => undefined }) {
  const r = ratios || {};
  const capped = (v) => Number(v) > RATIO_CAP;
  const items = [
    // Fase 3 · P4 (D-10) — Marjin Bersih tampil SEKALI di dasbor (dulu juga di baris KPI Laba-Rugi).
    { k: "gross", label: "Marjin Kotor", value: fmtPctId(r.gross_margin), icon: Percent, hint: "laba kotor ÷ pendapatan, tahun berjalan", tab: "pl" },
    { k: "net", label: "Marjin Bersih", value: fmtPctId(r.net_margin), icon: Percent, hint: "laba bersih ÷ pendapatan, tahun berjalan", tab: "pl" },
    { k: "current", label: "Rasio Lancar", value: fmtRatio(r.current_ratio), icon: Scale, tab: "bs",
      hint: capped(r.current_ratio) ? "kewajiban lancar hampir nol" : "aset lancar ÷ kewajiban lancar" },
    { k: "der", label: "Utang thd Ekuitas", value: fmtRatio(r.debt_to_equity), icon: Landmark, tab: "bs",
      hint: "total kewajiban ÷ ekuitas" },
  ];
  return (
    <MetricRow testId="tower-ratios" items={items.map((it) => ({
      label: it.label, value: it.value, icon: it.icon, hint: it.hint, testId: `tower-ratio-${it.k}`,
      onClick: openReport(it.tab),
    }))} />
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

export function ArAgingPanel({ ar, onOpen }) {
  const a = ar?.aging || {};
  // PK-41 (RP-12) — judul kelompok dari `bucket_labels` server (batas `ar.aging_buckets`); bawaan 30/60/90 hari.
  const lbl = Object.fromEntries((ar?.bucket_labels || []).map((b) => [b.key, b.label]));
  const pakai = (k) => !(ar?.bucket_labels || []).length || k in lbl;   // kolom yang tidak dipakai batas PT disembunyikan
  const data = [
    { key: "current", name: lbl.current || "Belum jatuh tempo", value: a.current || 0, color: FC.revenue },
    { key: "b1_30", name: lbl.b1_30 || "1–30 hari", value: a.b1_30 || 0, color: FC.teal },
    { key: "b31_60", name: lbl.b31_60 || "31–60 hari", value: a.b31_60 || 0, color: FC.amber },
    { key: "b61_90", name: lbl.b61_90 || "61–90 hari", value: a.b61_90 || 0, color: "#E67E22" },
    { key: "b90_plus", name: lbl.b90_plus || "> 90 hari", value: a.b90_plus || 0, color: FC.expense },
  ].filter((d) => pakai(d.key));
  return (
    <Panel title="Umur Piutang (AR Aging)" icon={Users} testId="tower-ar-aging"
      actions={<PanelLink onClick={onOpen} label="Buka Piutang" testId="tower-ar-aging-open" />}>
      <AgingBars data={data} testId="tower-ar-aging-chart" />
    </Panel>
  );
}

export function ApAgingPanel({ ap, onOpen }) {
  const a = ap?.aging || {};
  const data = [
    { name: "0-30", value: a.d0_30 || 0, color: FC.teal },
    { name: "31-60", value: a.d31_60 || 0, color: FC.amber },
    { name: "61-90", value: a.d61_90 || 0, color: "#E67E22" },
    { name: ">90", value: a.d90_plus || 0, color: FC.expense },
  ];
  return (
    <Panel title="Umur Hutang (AP Aging)" icon={Truck} testId="tower-ap-aging"
      actions={<PanelLink onClick={onOpen} label="Buka Tagihan Pemasok" testId="tower-ap-aging-open" />}>
      <AgingBars data={data} testId="tower-ap-aging-chart" />
    </Panel>
  );
}

export function TopArPanel({ ar, onOpen, perms }) {
  const rows = ar?.top || [];
  return (
    <Panel title="Piutang Terbesar" icon={Users} testId="tower-top-ar"
      actions={<PanelLink onClick={onOpen} label="Buka Piutang" testId="tower-top-ar-open" />}>
      {rows.length === 0 ? <p className="text-[11px] text-[#9A9BA3] py-3 text-center">Tidak ada piutang.</p> : (
        <div className="space-y-1.5">
          {rows.map((c, i) => (
            <div key={i} data-testid={`tower-ar-row-${i}`} className="flex items-center justify-between gap-2 text-[12px] border-b border-[#F5F5F7] last:border-0 pb-1.5">
              {/* M32 — nama pelanggan membuka kartu pelanggan (piutang, tagihan, riwayat). */}
              <CustomerCardLink id={c.customer_id} name={c.customer_name} perms={perms} testId={`tower-ar-card-${i}`}
                className="font-semibold truncate max-w-[150px]" />
              <div className="text-right"><span className="tabular-nums font-semibold text-[#1B7F4B]">{formatCurrency(c.outstanding)}</span>
                {c.oldest_days > 0 && <span className="block text-[9px] text-[#C0392B]">telat {c.oldest_days}h</span>}</div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

export function TopApPanel({ ap, onOpen, perms }) {
  const rows = ap?.top || [];
  return (
    <Panel title="Hutang Terbesar" icon={Truck} testId="tower-top-ap"
      actions={<PanelLink onClick={onOpen} label="Buka Tagihan Pemasok" testId="tower-top-ap-open" />}>
      {rows.length === 0 ? <p className="text-[11px] text-[#9A9BA3] py-3 text-center">Tidak ada hutang.</p> : (
        <div className="space-y-1.5">
          {rows.map((b, i) => (
            <div key={i} data-testid={`tower-ap-row-${i}`} className="flex items-center justify-between gap-2 text-[12px] border-b border-[#F5F5F7] last:border-0 pb-1.5">
              <SupplierCardLink id={b.party_id} name={b.party || b.number} perms={perms} testId={`tower-ap-card-${i}`}
                className="font-semibold truncate max-w-[150px]" />
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
export function CashPanel({ cash, onOpen }) {
  const accounts = cash?.accounts || [];
  return (
    <Panel title="Rincian Kas per Akun (GL)" icon={PieIcon} testId="tower-cash-panel"
      actions={<PanelLink onClick={onOpen} label="Rekening & Saldo" testId="tower-cash-open" />}>
      {accounts.length === 0 ? <p className="text-[11px] text-[#9A9BA3] py-3 text-center">Belum ada akun kas/bank bersaldo.</p> : (
        <div className="space-y-1.5">
          {accounts.map((a) => (
            <div key={a.code} className="flex items-center justify-between gap-3 text-[12px] border-b border-[#F5F5F7] last:border-0 pb-1.5">
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
