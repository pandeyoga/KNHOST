import { useEffect, useState } from "react";
import { Download, RefreshCw, RotateCcw } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";

const STATUS = {
  queued: ["Antre", "#8E8E93"], running: ["Diproses", "#FF9500"], done: ["Siap", "#34C759"],
  failed: ["Gagal", "#C0341D"], expired: ["Kedaluwarsa", "#8E8E93"],
};
const errText = (e) => e.response?.data?.detail?.message || e.response?.data?.detail || e.message;

async function readBlobError(e) {
  const blob = e.response?.data;
  if (blob instanceof Blob) {
    try { return JSON.parse(await blob.text()).detail?.message || "Unduh gagal"; } catch { return "Unduh gagal"; }
  }
  return errText(e);
}

export default function JobsPanel({ refreshKey }) {
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState(null);
  const load = () => axios.get(`${API}/export-center/jobs`).then((r) => setJobs(r.data.items || [])).catch((e) => setError(errText(e)));
  useEffect(() => { load(); }, [refreshKey]); // eslint-disable-line
  useEffect(() => {
    if (!jobs.some((j) => ["queued", "running"].includes(j.status))) return undefined;
    const t = setTimeout(load, 2000);
    return () => clearTimeout(t);
  }, [jobs]); // eslint-disable-line

  const download = async (j) => {
    setError(null);
    try {
      const r = await axios.get(`${API}/export-center/jobs/${j.id}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = j.file_name; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { setError(await readBlobError(e)); }
  };
  const retry = async (j) => {
    setError(null);
    try { await axios.post(`${API}/export-center/jobs/${j.id}/retry`); load(); } catch (e) { setError(errText(e)); }
  };

  return (
    <div data-testid="export-jobs-panel" className="rounded-xl border border-[#EFF0F2] bg-white p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-[13px] font-bold text-[#1C1C1E]">Pekerjaan export saya</h3>
        <button type="button" data-testid="export-jobs-refresh" onClick={load} className="text-[#6B6B73] hover:text-[#1C1C1E]"><RefreshCw size={14} /></button>
      </div>
      {error && <ErrorNotice message={error} onDismiss={() => setError(null)} testId="export-jobs-error" />}
      {!jobs.length && <p className="text-[12px] text-[#8E8E93]">Belum ada export. File tersedia 24 jam dan hanya bisa diunduh oleh Anda.</p>}
      <div className="divide-y divide-[#F0F0F3]">
        {jobs.map((j) => {
          const [label, color] = STATUS[j.status] || [j.status, "#8E8E93"];
          return (
            <div key={j.id} data-testid={`export-job-${j.id}`} className="py-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px]">
              <span className="font-semibold text-[#1C1C1E]">{j.dataset_label}</span>
              <span className="uppercase text-[10.5px] font-bold text-[#6B6B73]">{j.format}</span>
              <span data-testid={`export-job-status-${j.id}`} className="rounded-full px-2 py-0.5 text-[11px] font-semibold"
                    style={{ background: `${color}18`, color }}>{label}</span>
              <span className="text-[#6B6B73]">{(j.written_rows || 0).toLocaleString("id-ID")}/{(j.total_rows || 0).toLocaleString("id-ID")} baris</span>
              {j.partitions?.length > 1 && <span className="text-[#6B6B73]">{j.partitions.length} sheet data</span>}
              {j.error && <span className="text-[#C0341D]">{j.error}</span>}
              <span className="ml-auto flex items-center gap-2">
                {j.status === "done" && <button type="button" data-testid={`export-job-download-${j.id}`} onClick={() => download(j)}
                  className="inline-flex items-center gap-1 rounded-full bg-[#0058CC] text-white px-3 py-1 font-semibold"><Download size={12} /> Unduh</button>}
                {["failed", "expired", "done"].includes(j.status) && <button type="button" data-testid={`export-job-retry-${j.id}`} onClick={() => retry(j)}
                  title="Jalankan ulang dengan hak akses saat ini" className="inline-flex items-center gap-1 text-[#0058CC] font-semibold"><RotateCcw size={12} /> Ulangi</button>}
              </span>
              <p className="w-full text-[11px] text-[#8E8E93]">{j.filter_text} · {j.date_text} · dibuat {String(j.created_at).replace("T", " ").slice(0, 16)}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
