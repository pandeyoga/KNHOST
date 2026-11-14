/**
 * CashFlowTab (FINANCE) — Laporan Arus Kas (metode langsung, digolongkan per jenis transaksi — PK-41).
 * Sumber: /api/finance/cash-flow (+ export.csv). Dipakai di FinancialStatementsView.
 * PK-16 — banner PT (`scope_meta`), gagal memuat → data dikosongkan, nama unduhan memuat PT / `gabungan`.
 * PK-41 (RP-06) — baris "Saldo awal rekening yang didaftarkan periode ini" di bawah Kas Awal (menambah kas awal, bukan
 * arus pendanaan) dan keterangan metode dari server.
 * MN-T3 (bagian E) — baris yang membawa kode akun = tautan ke buku besar akun itu pada rentang laporan (`traceLedger`);
 * baris laba bersih, total, dan kas awal/akhir tidak bisa diklik. Semua PT → petunjuk memilih satu PT.
 */
import { apiErrorText } from "../../utils/apiError";
import KNDatePicker from "@/components/KNDatePicker";
import { useCallback, useEffect, useState } from "react";
import {
  BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import {
  RefreshCw, Download, Waves, TrendingUp, Building2, Landmark, CheckCircle2, AlertTriangle, Wallet,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import EntityScopeBanner, { useScopeMeta, scopeFileTag } from "../../components/EntityScopeBanner";
import {
  FC, ytdRangeWib, compactIDR, entityParam, saveBlob, chartTooltip,
  KpiCard, Panel, EmptyState, formatCurrency,
} from "./financeShared";
import { TraceNotice, TraceValue, useLedgerTrace } from "./traceLedger";

export default function CashFlowTab({ selectedEntity }) {
  const [range, setRange] = useState(() => ytdRangeWib());   // WIB, dihitung saat layar dipasang
  const tr = useLedgerTrace({ from: "financial-statements", fromTab: "cf", selectedEntity });
  const traceRow = (code) => tr.trace(code, { start: range.start, end: range.end });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const scope = useScopeMeta(data?.scope_meta);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const params = { ...entityParam(selectedEntity) };
      if (range.start) params.start = range.start;
      if (range.end) params.end = range.end;
      const res = await axios.get(`${API}/finance/cash-flow`, { params });
      setData(res.data || null);
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat Laporan Arus Kas."));
      setData(null);   // PK-16 (RP-04) — tidak ada angka dari permintaan sebelumnya
    } finally { setLoading(false); }
  }, [selectedEntity, range]);

  useEffect(() => { load(); }, [load]);

  const doExport = async () => {
    try {
      const res = await axios.get(`${API}/finance/cash-flow/export.csv`, {
        params: { ...entityParam(selectedEntity), start: range.start, end: range.end },
        responseType: "blob",
      });
      saveBlob(res.data, `arus-kas_${scopeFileTag(scope)}_${range.start}_${range.end}.csv`);
    } catch { setError("Gagal mengunduh CSV."); }
  };

  const op = data?.operating || {};
  const inv = data?.investing || {};
  const fin = data?.financing || {};
  const waterfall = data ? [
    { name: "Operasi", value: op.total || 0, fill: FC.revenue },
    { name: "Investasi", value: inv.total || 0, fill: FC.blue },
    { name: "Pendanaan", value: fin.total || 0, fill: FC.amber },
    { name: "Perub. Kas", value: data.net_change || 0, fill: FC.purple },
  ] : [];

  return (
    <div data-testid="fs-cash-flow">
      <EntityScopeBanner meta={scope} />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
        <KpiCard testId="cf-kpi-begin" label="Kas Awal Periode" value={formatCurrency(data?.begin_cash)} icon={Wallet} accent={FC.muted}
          sub={(data?.opening_balance_additions || 0) !== 0 ? `ditambah saldo awal rekening baru ${formatCurrency(data.opening_balance_additions)}` : undefined} />
        <KpiCard testId="cf-kpi-operating" label="Kas Bersih Operasi" value={formatCurrency(op.total)} icon={TrendingUp} accent={FC.revenue} tone={(op.total ?? 0) >= 0 ? "text-[#1B7F4B]" : "text-[#C0392B]"} />
        <KpiCard testId="cf-kpi-netchange" label="Perubahan Kas Bersih" value={formatCurrency(data?.net_change)} icon={Waves} accent={FC.purple} tone={(data?.net_change ?? 0) >= 0 ? "text-[#1B7F4B]" : "text-[#C0392B]"} />
        <KpiCard testId="cf-kpi-end" label="Kas Akhir Periode" value={formatCurrency(data?.end_cash)} icon={Landmark} accent={FC.cash} tone="text-[#0058CC]" />
      </div>

      <div className="rounded-lg border border-[#EFF0F2] p-3 mb-3 bg-[#FCFCFD] flex flex-wrap items-end gap-3">
        <div><label className="block text-[10px] font-bold uppercase text-[#8E8E93] mb-1">Dari Tanggal</label>
          <KNDatePicker data-testid="cf-start" className="w-[170px] text-[12px]" clearable={false} value={range.start}
            onChange={(v) => setRange((r) => ({ ...r, start: v }))} /></div>
        <div><label className="block text-[10px] font-bold uppercase text-[#8E8E93] mb-1">Sampai Tanggal</label>
          <KNDatePicker data-testid="cf-end" className="w-[170px] text-[12px]" clearable={false} min={range.start} value={range.end}
            onChange={(v) => setRange((r) => ({ ...r, end: v }))} /></div>
        <div className="ml-auto flex items-center gap-2">
          {data && (
            <span data-testid="cf-reconcile" className={`inline-flex items-center gap-1 text-[11px] font-semibold rounded-full px-2.5 py-1 ${data.reconciled ? "bg-[#EAF6EF] text-[#1B7F4B]" : "bg-[#FDECEC] text-[#C0392B]"}`}>
              {data.reconciled ? <CheckCircle2 size={13} /> : <AlertTriangle size={13} />}
              {data.reconciled ? "Terekonsiliasi" : "Selisih rekonsiliasi"}
            </span>
          )}
          <button data-testid="cf-export" onClick={doExport} className="btn-secondary text-[12px] py-1.5 px-3 inline-flex items-center gap-1"><Download size={13} /> Ekspor CSV</button>
          <button data-testid="cf-refresh" className="icon-button" onClick={load} aria-label="Muat ulang" title="Muat ulang"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
        </div>
      </div>

      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="cf-error" />

      {loading ? (
        <div className="grid gap-2" data-testid="cf-loading">{[0, 1, 2, 3].map((i) => <div key={i} className="h-9 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
      ) : !data ? null : (
        <div className="grid lg:grid-cols-5 gap-3">
          <div className="lg:col-span-2">
            <Panel title="Kontribusi Arus Kas" icon={Waves} testId="cf-chart">
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={waterfall} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={FC.grid} />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={compactIDR} width={52} />
                  <Tooltip formatter={(v) => formatCurrency(v)} {...chartTooltip} />
                  <ReferenceLine y={0} stroke="#C7C7CC" />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={44}>
                    {waterfall.map((d, i) => <Cell key={i} fill={d.value >= 0 ? d.fill : FC.expense} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Panel>
          </div>
          <div className="lg:col-span-3">
            <TraceNotice notice={tr.notice} onDismiss={tr.clear} testId="cf-trace-notice" />
            <div className="overflow-auto rounded-xl border border-[#EFF0F2]" data-testid="cf-table">
              <table className="w-full text-[12px]">
                <tbody>
                  <SectionRows label={op.label} testId="op"
                    lead={{ name: op.net_income_label, amount: op.net_income }}
                    lines={op.working_capital} total={op.total} trace={tr.enabled ? traceRow : null} />
                  <SectionRows label={inv.label} testId="inv" lines={inv.lines} total={inv.total} trace={tr.enabled ? traceRow : null} />
                  <SectionRows label={fin.label} testId="fin" lines={fin.lines} total={fin.total} trace={tr.enabled ? traceRow : null} />
                  <tr className="border-t-2 border-[#E4E4EA] bg-[#F3EAFB]">
                    <td className="px-3 py-2.5 font-bold text-[#1C1C1E]">KENAIKAN/(PENURUNAN) KAS BERSIH</td>
                    <td className="px-3 py-2.5 text-right tabular-nums font-bold text-[#6B219A]" data-testid="cf-net-change">{formatCurrency(data.net_change)}</td>
                  </tr>
                  <tr className="border-b border-[#F5F5F7]"><td className="px-3 py-1.5 pl-6 text-[#6B6B73]">Kas Awal Periode</td><td className="px-3 py-1.5 text-right tabular-nums text-[#6B6B73]">{formatCurrency(data.begin_cash)}</td></tr>
                  <tr className="border-b border-kn-divider" data-testid="cf-opening-row">
                    <td className="px-3 py-1.5 pl-6 text-kn-text-2">{data.opening_balance_label || "Saldo awal rekening yang didaftarkan periode ini"}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-kn-text-2" data-testid="cf-opening">{formatCurrency(data.opening_balance_additions || 0)}</td>
                  </tr>
                  <tr><td className="px-3 py-2 font-bold text-[#1C1C1E]">Kas Akhir Periode</td><td className="px-3 py-2 text-right tabular-nums font-bold text-[#0058CC]" data-testid="cf-end-cash">{formatCurrency(data.end_cash)}</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
      {data?.noncash_disclosure?.lines?.length > 0 && (
        <div data-testid="cf-noncash" className="mt-3 rounded-xl border border-dashed border-[#E4E4EA] p-3 text-[12px]">
          <p className="font-bold text-[#1C1C1E]">{data.noncash_disclosure.label}</p>
          {data.noncash_disclosure.lines.map((l) => (
            <div key={l.code} className="flex justify-between py-0.5 text-[#6B6B73]">
              <span>{l.code} · {l.name}</span><span className="tabular-nums">{formatCurrency(l.amount)}</span></div>))}
        </div>)}
      <p className="mt-2 text-[11px] text-[#9A9BA3]" data-testid="cf-method">{data?.method_label || "Metode langsung: tiap jurnal kas digolongkan menurut jenis transaksinya."} Saldo awal rekening yang didaftarkan dalam periode menambah kas awal, bukan arus pendanaan. Jurnal nonkas (penyusutan, reklasifikasi, beli aset kredit) tidak menjadi arus kas.</p>
    </div>
  );
}

function SectionRows({ label, lead, lines, total, testId, trace = null }) {
  const arr = lines || [];
  return (
    <>
      <tr className="bg-[#FAFBFC] border-y border-[#EFF0F2]"><td colSpan={2} className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide text-[#6B219A]">{label}</td></tr>
      {lead && (
        <tr className="border-b border-[#F5F5F7]" data-testid={`cf-${testId}-lead`}>
          <td className="px-3 py-1.5 pl-6 text-[#3C3C43]">{lead.name}</td>
          <td className="px-3 py-1.5 text-right tabular-nums text-[#1C1C1E]">{formatCurrency(lead.amount)}</td>
        </tr>
      )}
      {arr.length === 0 && !lead ? (
        <tr><td colSpan={2} className="px-3 py-1.5 pl-6 text-[11px] text-[#9A9BA3]">Tidak ada perubahan.</td></tr>
      ) : arr.map((ln) => (
        <tr key={ln.code} className="border-b border-[#F5F5F7]">
          <td className="px-3 py-1.5 pl-6 text-[#3C3C43]"><span className="text-[10px] text-[#9A9BA3] mr-1.5">{ln.code}</span>
            <TraceValue enabled={Boolean(trace)} onClick={() => trace(ln.code)} testId={`cf-line-${ln.code}`}>{ln.name}</TraceValue></td>
          <td className={`px-3 py-1.5 text-right tabular-nums ${ln.amount >= 0 ? "text-[#1B7F4B]" : "text-[#C0392B]"}`}>{formatCurrency(ln.amount)}</td>
        </tr>
      ))}
      <tr className="border-b border-[#EFF0F2] bg-[#FCFCFD]">
        <td className="px-3 py-1.5 pl-6 font-semibold text-[#1C1C1E]">Kas Bersih dari {label?.replace("Arus Kas dari ", "")}</td>
        <td className="px-3 py-1.5 text-right tabular-nums font-bold text-[#1C1C1E]" data-testid={`cf-${testId}-total`}>{formatCurrency(total)}</td>
      </tr>
    </>
  );
}
