import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart,
  Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { formatValue, labelOf, shortIdr, unitOf } from "./tanyaFormat";

const COLORS = ["#6B219A", "#007AFF", "#34C759", "#FF9500", "#AF52DE", "#FF3B30"];

export function TanyaChart({ result, spec }) {
  const rows = result?.rows || [];
  const x = spec.x || (result?.columns || []).find((c) => c.type !== "metric")?.key || "period";
  const ys = (spec.y || []).filter((k) => rows.some((r) => typeof r[k] === "number"));
  if (!rows.length || !ys.length) {
    return <div className="tanya-empty" data-testid="tanya-chart-empty">Belum ada data untuk grafik ini.</div>;
  }
  const tip = (v, k) => [formatValue(unitOf(result, k), v), labelOf(result, k)];
  const axisProps = { tick: { fontSize: 11 }, tickFormatter: shortIdr };
  const type = spec.type || "bar";
  const common = { data: rows, margin: { top: 8, right: 12, left: 4, bottom: 4 } };
  let chart;
  if (type === "pie") {
    chart = (
      <PieChart>
        <Pie data={rows} dataKey={ys[0]} nameKey={x} outerRadius={100} label={(e) => e[x]}>
          {rows.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Pie>
        <Tooltip formatter={tip} />
      </PieChart>
    );
  } else if (type === "hbar") {
    chart = (
      <BarChart {...common} layout="vertical">
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" {...axisProps} />
        <YAxis type="category" dataKey={x} width={140} tick={{ fontSize: 11 }} />
        <Tooltip formatter={tip} />
        {ys.map((k, i) => <Bar key={k} dataKey={k} fill={COLORS[i]} radius={[0, 4, 4, 0]} name={labelOf(result, k)} />)}
      </BarChart>
    );
  } else if (type === "line" || type === "area") {
    const C = type === "line" ? LineChart : AreaChart;
    chart = (
      <C {...common}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey={x} tick={{ fontSize: 11 }} />
        <YAxis {...axisProps} />
        <Tooltip formatter={tip} />
        <Legend />
        {ys.map((k, i) => (type === "line"
          ? <Line key={k} dataKey={k} stroke={COLORS[i]} strokeWidth={2} dot={false} name={labelOf(result, k)} />
          : <Area key={k} dataKey={k} stroke={COLORS[i]} fill={COLORS[i]} fillOpacity={0.15} name={labelOf(result, k)} />))}
      </C>
    );
  } else {
    chart = (
      <ComposedChart {...common}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey={x} tick={{ fontSize: 11 }} />
        <YAxis {...axisProps} />
        <Tooltip formatter={tip} />
        <Legend />
        {ys.map((k, i) => (type === "combo" && i > 0
          ? <Line key={k} dataKey={k} stroke={COLORS[i]} strokeWidth={2} name={labelOf(result, k)} />
          : <Bar key={k} dataKey={k} fill={COLORS[i]} radius={[4, 4, 0, 0]} stackId={type === "stacked_bar" ? "s" : undefined} name={labelOf(result, k)} />))}
      </ComposedChart>
    );
  }
  return (
    <div className="tanya-chart" data-testid={`tanya-chart-${result.result_id}`}>
      {spec.title && <div className="tanya-block-title">{spec.title}</div>}
      <ResponsiveContainer width="100%" height={280}>{chart}</ResponsiveContainer>
    </div>
  );
}
