import { useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import FilterChips from "../../components/FilterChips";

const META = { mapped: ["Dipetakan", "#34C759"], excluded: ["Dikecualikan", "#8E8E93"], unmapped: ["Belum dipetakan", "#FF9500"] };

export default function CoveragePanel() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState("all");
  useEffect(() => {
    axios.get(`${API}/export-center/coverage`).then((r) => setData(r.data)).catch((e) => setError(e.response?.data?.detail || e.message));
  }, []);
  if (error) return <ErrorNotice message={error} testId="export-coverage-error" />;
  if (!data) return <div className="h-24 rounded-xl bg-[#F5F5F7] animate-pulse" />;
  const rows = data.collections.filter((r) => status === "all" || r.status === status);
  return (
    <div data-testid="export-coverage-panel" className="rounded-xl border border-[#EFF0F2] bg-white p-4 space-y-3">
      <div>
        <h3 className="text-[13px] font-bold text-[#1C1C1E]">Cakupan data bisnis</h3>
        <p className="text-[12px] text-[#6B6B73]">Setiap koleksi di basis data dipetakan ke dataset, dikecualikan dengan alasan, atau ditandai belum dipetakan — tidak ada yang hilang diam-diam.</p>
      </div>
      {/* Fase 4 · R2 (L-01) — pil hitam buatan sendiri → FilterChips (testid `export-coverage-filter-*` tetap). */}
      <FilterChips testId="export-coverage-filter" ariaLabel="Saring status cakupan" value={status} onChange={setStatus}
        options={["all", "mapped", "excluded", "unmapped"].map((k) => ({
          key: k, label: k === "all" ? "Semua" : META[k][0], count: k === "all" ? data.summary.total : data.summary[k],
        }))} />
      <div className="max-h-[420px] overflow-y-auto divide-y divide-[#F0F0F3]">
        {rows.map((r) => (
          <div key={r.collection} data-testid={`export-coverage-row-${r.collection}`} className="py-1.5 flex flex-wrap items-center gap-x-3 text-[12px]">
            <span className="font-mono text-[11.5px] text-[#1C1C1E] w-full truncate sm:w-56">{r.collection}</span>
            <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold" style={{ background: `${META[r.status][1]}18`, color: META[r.status][1] }}>{META[r.status][0]}</span>
            <span className="text-[#6B6B73]">{r.datasets ? r.datasets.join(", ") : r.reason}</span>
            <span className="ml-auto text-[#8E8E93] tabular-nums">{r.rows.toLocaleString("id-ID")} dok</span>
          </div>
        ))}
      </div>
    </div>
  );
}
