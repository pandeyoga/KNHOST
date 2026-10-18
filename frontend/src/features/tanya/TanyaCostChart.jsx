import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { COST_METRICS, shortDay } from "./tanyaFormat";

const COLORS = ["#6B219A", "#007AFF", "#34C759", "#FF9500", "#AF52DE", "#FF3B30", "#8E8E93"];

/** Grafik batang bertumpuk harian: satu seri per fitur / pengguna. */
export function TanyaCostChart({ title, daily, series, metric, testId }) {
  const m = COST_METRICS[metric];
  const rows = (daily || []).map((d) => ({
    date: shortDay(d.date),
    ...Object.fromEntries(series.map((s) => [s.key, d.values?.[s.key]?.[metric] || 0])),
  }));
  const empty = !series.length || rows.every((r) => series.every((s) => !r[s.key]));
  return (
    <section className="tanya-cost-card section-card" data-testid={testId}>
      <div className="tanya-block-title">{title}</div>
      {empty ? (
        <div className="tanya-empty" data-testid={`${testId}-empty`}>Belum ada pemakaian AI di rentang ini.</div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={rows} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={12} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => (metric === "usd" ? `$${v}` : v.toLocaleString("id-ID"))} width={56} />
            <Tooltip formatter={(v, name) => [m.fmt(v), name]} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {series.map((s, i) => (
              <Bar key={s.key} dataKey={s.key} name={s.label} stackId="c" fill={COLORS[i % COLORS.length]}
                radius={i === series.length - 1 ? [4, 4, 0, 0] : 0} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      )}
    </section>
  );
}
