import { useEffect, useState } from "react";
import { Info, Loader2 } from "lucide-react";
import { TanyaCostChart } from "./TanyaCostChart";
import { TanyaCostTable } from "./TanyaCostTables";
import { fetchUsageDaily } from "./tanyaApi";
import { COST_METRICS, fmtInt, fmtUsd } from "./tanyaFormat";

const RANGES = [[7, "7 hari"], [30, "30 hari"], [90, "90 hari"]];
const SCOPES = [["bi", "Tanya KN"], ["all", "Semua fitur AI"]];

function Chips({ items, value, onChange, testId }) {
  return (
    <div className="tanya-periods" data-testid={testId}>
      {items.map(([k, label]) => (
        <button key={k} type="button" className={`tanya-chip ${value === k ? "active" : ""}`} onClick={() => onChange(k)}
          data-testid={`${testId}-${k}`}>{label}</button>
      ))}
    </div>
  );
}

function Kpis({ data }) {
  const b = data.budget;
  const cards = [
    ["total", "Biaya rentang ini", fmtUsd(data.totals.usd)],
    ["calls", "Panggilan AI", fmtInt(data.totals.calls)],
    ["avg", "Rata-rata per hari", fmtUsd(data.totals.avg_usd_per_day)],
    ["budget", "Anggaran bulan ini", `${fmtUsd(b.spent_usd)} / ${fmtUsd(b.limit_usd)}`, b.used_pct == null ? "" : `${b.used_pct.toLocaleString("id-ID")}% terpakai`],
    ["projection", "Perkiraan akhir bulan", fmtUsd(b.projected_usd), b.limit_usd && b.projected_usd > b.limit_usd ? "Melebihi anggaran" : "Sesuai laju saat ini"],
  ];
  return (
    <div className="tanya-cards">
      {cards.map(([k, label, value, sub]) => (
        <div key={k} className="tanya-card" data-testid={`tanya-cost-kpi-${k}`}>
          <div className="tanya-card-label">{label}</div>
          <div className="tanya-card-value">{value}</div>
          {sub && <div className={`tanya-card-delta ${sub === "Melebihi anggaran" ? "down" : ""}`}>{sub}</div>}
        </div>
      ))}
    </div>
  );
}

/** Halaman Biaya AI: grafik harian per fitur & per pengguna + rincian, untuk memantau anggaran. */
export function TanyaCostView() {
  const [days, setDays] = useState(30);
  const [scope, setScope] = useState("bi");
  const [metric, setMetric] = useState("usd");
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    setBusy(true); setError("");
    fetchUsageDaily({ days, scope }).then(setData)
      .catch((e) => setError(e?.response?.data?.detail || "Data biaya AI tidak dapat dimuat."))
      .finally(() => setBusy(false));
  }, [days, scope]);

  return (
    <div className="tanya-cost" data-testid="tanya-cost-page">
      <header className="tanya-cost-head section-card">
        <div>
          <div className="tanya-kicker">Pemantauan anggaran</div>
          <h2 className="tanya-answer-title">Biaya AI</h2>
          <p className="tanya-note">Biaya harian per fitur dan per pengguna, dari log setiap panggilan model (tanggal WIB).</p>
        </div>
        <div className="tanya-cost-controls">
          <Chips items={RANGES} value={days} onChange={setDays} testId="tanya-cost-range" />
          <Chips items={SCOPES} value={scope} onChange={setScope} testId="tanya-cost-scope" />
          <Chips items={Object.entries(COST_METRICS).map(([k, m]) => [k, m.label])} value={metric} onChange={setMetric} testId="tanya-cost-metric" />
        </div>
      </header>
      {error && <div className="tanya-error section-card" data-testid="tanya-cost-error">{error}</div>}
      {!data && busy && <div className="tanya-loading" data-testid="tanya-cost-loading"><Loader2 className="h-5 w-5 animate-spin" /> Memuat biaya AI…</div>}
      {data && (
        <div className={`tanya-cost ${busy ? "tanya-dim" : ""}`}>
          {data.demo_rows > 0 && (
            <div className="tanya-cost-notice" data-testid="tanya-cost-demo-notice">
              <Info className="h-4 w-4 shrink-0" />
              <span className="min-w-0">Termasuk {fmtInt(data.demo_rows)} baris data contoh (tidak dihitung ke anggaran). Hapus dengan <code className="break-all">scripts/seed_ai_usage_demo.py --clear</code>.</span>
            </div>
          )}
          <Kpis data={data} />
          <TanyaCostChart title="Per fitur, per hari" daily={data.daily_feature} series={data.feature_series} metric={metric} testId="tanya-cost-chart-feature" />
          <TanyaCostChart title="Per pengguna, per hari" daily={data.daily_user} series={data.user_series} metric={metric} testId="tanya-cost-chart-user" />
          <div className="tanya-cost-grid">
            <TanyaCostTable title="Rincian per fitur" nameLabel="Fitur" rows={data.features} testId="tanya-cost-table-feature" />
            <TanyaCostTable title="Rincian per pengguna" nameLabel="Pengguna" rows={data.users} testId="tanya-cost-table-user" />
          </div>
          <TanyaCostTable title="Rincian per model" nameLabel="Model" rows={data.models} testId="tanya-cost-table-model" />
        </div>
      )}
    </div>
  );
}
