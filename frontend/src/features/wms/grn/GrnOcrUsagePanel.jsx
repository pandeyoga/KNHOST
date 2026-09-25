import { useEffect, useState } from "react";
import { ErrorBox, inputCls } from "./GrnBits";
import { errText, grnApi } from "./grnApi";

const usd = (v) => (v == null ? "—" : `US$${Number(v).toFixed(v >= 1 ? 2 : 4)}`);
const n = (v) => Number(v || 0).toLocaleString("id-ID");

function Kpi({ label, value, testId, tone = "" }) {
  return (
    <div className="rounded-xl border border-[#EFF0F2] bg-white p-3">
      <p className="text-[10px] font-bold uppercase text-[#6B6B73]">{label}</p>
      <p data-testid={testId} className={`mt-0.5 font-mono text-[16px] font-bold ${tone}`}>{value}</p>
    </div>
  );
}

/** Biaya OCR surat jalan per bulan: token, biaya, lembar, sisa anggaran per model & badan usaha (hak approve). */
export default function GrnOcrUsagePanel() {
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { setErr(""); grnApi.usage(month).then(setData).catch((e) => setErr(errText(e))); }, [month]);
  const rows = data?.rows || [];
  const pct = data?.budget_usd ? Math.min(100, ((data.budget_usd - (data.remaining_usd ?? 0)) / data.budget_usd) * 100) : 0;
  return (
    <div className="space-y-3" data-testid="grn-ocr-usage">
      <div className="flex items-center gap-2">
        <label className="text-[11px] font-semibold text-[#3C3C43]">Bulan</label>
        <input data-testid="grn-ocr-usage-month" type="month" className={`${inputCls} !w-40`} value={month} onChange={(e) => setMonth(e.target.value)} />
      </div>
      <ErrorBox text={err} />
      {data && (<>
        <div className="grid gap-2 sm:grid-cols-4">
          <Kpi label="Anggaran bulanan" value={usd(data.budget_usd)} testId="grn-ocr-usage-budget" />
          <Kpi label="Terpakai (badan usaha ini)" value={usd(data.spent_usd)} testId="grn-ocr-usage-spent" />
          <Kpi label="Sisa anggaran (semua)" value={usd(data.remaining_usd)} testId="grn-ocr-usage-remaining" tone={pct >= 80 ? "text-[#B4231F]" : "text-[#0F766E]"} />
          <Kpi label="Panggilan" value={n(rows.reduce((s, r) => s + r.calls, 0))} testId="grn-ocr-usage-calls" />
        </div>
        {data.budget_usd > 0 && (
          <div className="h-1.5 overflow-hidden rounded-full bg-[#EFF0F2]" data-testid="grn-ocr-usage-bar">
            <div className={`h-full rounded-full ${pct >= 80 ? "bg-[#B4231F]" : "bg-[#0F766E]"}`} style={{ width: `${pct}%` }} />
          </div>
        )}
        <div className="overflow-x-auto rounded-xl border border-[#EFF0F2] bg-white">
          <table className="w-full text-left text-[11px]" data-testid="grn-ocr-usage-table">
            <thead className="bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73]">
              <tr>{["Model", "Badan usaha", "Panggilan", "Berhasil", "Lembar", "Token masuk", "Token keluar", "Biaya", "Per lembar"].map((h) => <th key={h} className="px-2 py-1.5">{h}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.model}-${r.entity_id}`} data-testid={`grn-ocr-usage-row-${r.model}`} className="border-t border-[#EFF0F2]">
                  <td className="px-2 py-1.5 font-mono">{r.model}</td>
                  <td className="px-2">{r.entity_id}</td>
                  <td className="px-2 tabular-nums">{n(r.calls)}</td>
                  <td className="px-2 tabular-nums">{n(r.ok)}</td>
                  <td className="px-2 tabular-nums">{n(r.pages)}</td>
                  <td className="px-2 tabular-nums">{n(r.input)}</td>
                  <td className="px-2 tabular-nums">{n(r.output)}</td>
                  <td className="px-2 font-mono">{usd(r.cost_usd)}</td>
                  <td className="px-2 font-mono">{usd(r.cost_per_page)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!rows.length && <p className="p-3 text-[11px] text-[#6B6B73]" data-testid="grn-ocr-usage-empty">Belum ada pembacaan OCR pada bulan ini.</p>}
        </div>
      </>)}
    </div>
  );
}
