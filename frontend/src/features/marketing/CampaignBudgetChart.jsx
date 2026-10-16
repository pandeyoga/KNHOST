/** Grafik anggaran vs realisasi kampanye per bulan + peringatan kampanye yang anggarannya hampir/sudah habis. */
import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { mktApi, fmtN } from "./marketingShared";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
const monthLabel = (m) => `${MONTHS[Number(m.slice(5, 7)) - 1]} ${m.slice(2, 4)}`;
const short = (v) => (v >= 1e6 ? `${(v / 1e6).toFixed(1)}jt` : v >= 1e3 ? `${Math.round(v / 1e3)}rb` : `${v}`);

export default function CampaignBudgetChart({ version }) {
  const [d, setD] = useState(null);
  useEffect(() => { mktApi.budgetSummary().then(setD).catch(() => setD(null)); }, [version]);
  if (!d) return null;
  const data = d.months.map((m) => ({ ...m, label: monthLabel(m.month) }));
  return (
    <div className="grid gap-2 rounded-xl border border-[#EFF0F2] bg-white p-3" data-testid="mkt-budget-chart">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Anggaran vs realisasi per bulan</p>
        <p className="text-[11px] text-[#6B6B73]" data-testid="mkt-budget-total">Total realisasi Rp {fmtN(d.total_realized)} dari anggaran Rp {fmtN(d.total_budget)}</p>
      </div>
      {d.alerts.length > 0 && (
        <div className="grid gap-1" data-testid="mkt-budget-alerts">
          {d.alerts.map((a) => (
            <p key={a.campaign_id} data-testid={`mkt-budget-alert-${a.campaign_id}`}
              className={`flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] font-semibold ${a.level === "over" ? "bg-[#FDECEC] text-[#B4231F]" : "bg-[#FFF6E5] text-[#B26A00]"}`}>
              <AlertTriangle size={12} /> {a.name}: terpakai {a.pct}% (Rp {fmtN(a.realized)} dari Rp {fmtN(a.budget)}) — {a.level === "over" ? `lewat Rp ${fmtN(-a.remaining)}` : `sisa Rp ${fmtN(a.remaining)}`}
            </p>
          ))}
        </div>
      )}
      {data.length ? (
        <div className="h-56 w-full" data-testid="mkt-budget-bars">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 4, right: 4, left: -8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F0F1F3" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 10 }} />
              <YAxis tickFormatter={short} tick={{ fontSize: 10 }} width={44} />
              <Tooltip formatter={(v) => `Rp ${fmtN(v)}`} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="budget" name="Anggaran" fill="#C9D8F2" radius={[3, 3, 0, 0]} />
              <Bar dataKey="realized" name="Realisasi" fill="#0058CC" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : <p className="text-[11px] text-[#9A9BA3]" data-testid="mkt-budget-empty">Belum ada kampanye berperiode/beranggaran.</p>}
      <p className="text-[10px] text-[#9A9BA3]">Anggaran dibagi rata ke bulan periode kampanye. Peringatan muncul saat realisasi ≥ {d.near_pct}% anggaran.</p>
    </div>
  );
}
