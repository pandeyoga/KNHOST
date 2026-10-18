import { useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";

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
      <div className="flex flex-wrap gap-1.5">
        {["all", "mapped", "excluded", "unmapped"].map((s) => (
          <button key={s} type="button" data-testid={`export-coverage-filter-${s}`} onClick={() => setStatus(s)}
                  className={`px-3 py-1 rounded-full border text-[12px] font-semibold ${status === s ? "bg-[#1C1C1E] text-white border-[#1C1C1E]" : "bg-white border-[#E5E5EA] text-[#3A3A3C]"}`}>
            {s === "all" ? `Semua (${data.summary.total})` : `${META[s][0]} (${data.summary[s]})`}
          </button>
        ))}
      </div>
      <div className="max-h-[420px] overflow-y-auto divide-y divide-[#F0F0F3]">
        {rows.map((r) => (
          <div key={r.collection} data-testid={`export-coverage-row-${r.collection}`} className="py-1.5 flex flex-wrap items-center gap-x-3 text-[12px]">
            <span className="font-mono text-[11.5px] text-[#1C1C1E] w-56 truncate">{r.collection}</span>
            <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold" style={{ background: `${META[r.status][1]}18`, color: META[r.status][1] }}>{META[r.status][0]}</span>
            <span className="text-[#6B6B73]">{r.datasets ? r.datasets.join(", ") : r.reason}</span>
            <span className="ml-auto text-[#8E8E93] tabular-nums">{r.rows.toLocaleString("id-ID")} dok</span>
          </div>
        ))}
      </div>
    </div>
  );
}
