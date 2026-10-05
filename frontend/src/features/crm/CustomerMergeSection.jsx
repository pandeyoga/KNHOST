import { useEffect, useState } from "react";
import { GitMerge } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";

// P18 MASTER-05 / COMM-01 — gabung pelanggan DUPLIKAT ke pelanggan ini (admin; izin customer.delete).
export default function CustomerMergeSection({ customer, onDone, onError }) {
  const [opts, setOpts] = useState([]);
  const [src, setSrc] = useState("");
  const [preview, setPreview] = useState(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    axios.get(`${API}/customers`).then((r) => {
      const rows = Array.isArray(r.data) ? r.data : (r.data?.items || []);
      setOpts(rows.filter((c) => c.id !== customer.id && c.status !== "merged")
        .map((c) => ({ value: c.id, label: `${c.name} · ${c.code || ""} · ${c.city || ""}` })));
    }).catch(() => setOpts([]));
  }, [customer.id]);

  async function pick(v) {
    setSrc(v); setPreview(null);
    if (!v) return;
    try {
      const r = await axios.get(`${API}/customers/${customer.id}/merge-preview`, { params: { source_id: v } });
      setPreview(r.data);
    } catch (e) { onError?.(e.response?.data?.detail || "Gagal memuat pratinjau gabung."); }
  }

  async function merge() {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/customers/${customer.id}/merge`, { data: { source_id: src, reason } });
      onDone?.(`${r.data.total_moved} dokumen dipindahkan ke ${customer.name}; pelanggan duplikat ditandai digabung.`);
      setSrc(""); setPreview(null); setReason("");
    } catch (e) { onError?.(e.response?.data?.detail || "Gagal menggabung pelanggan."); }
    finally { setBusy(false); }
  }

  return (
    <div className="section-card" data-testid="customer-merge-section">
      <div className="section-header"><h3 className="flex items-center gap-1.5"><GitMerge size={14} /> Gabung pelanggan duplikat</h3></div>
      <div className="section-body space-y-2">
        <KNSelect value={src} onValueChange={pick} options={opts} placeholder="Pilih pelanggan duplikat…" data-testid="customer-merge-source" searchable className="field" />
        {preview && (
          <div className="text-[12px]" data-testid="customer-merge-preview">
            <b>{preview.total}</b> dokumen akan dipindah
            {Object.entries(preview.references || {}).map(([k, v]) => <span key={k} className="pill pill-muted ml-1">{k}: {v}</span>)}
            {!preview.can_merge && <div className="text-red-700 mt-1" data-testid="customer-merge-conflict">Harga khusus bentrok: {preview.price_conflicts.join(", ")}</div>}
          </div>
        )}
        {preview?.can_merge && (
          <div className="flex flex-col gap-2 max-w-xl">
            <input className="field" placeholder="Alasan penggabungan (wajib)" value={reason}
                   onChange={(e) => setReason(e.target.value)} data-testid="customer-merge-reason" />
            <button className="primary-button self-start" disabled={busy || reason.trim().length < 5} onClick={merge} data-testid="customer-merge-submit">Gabungkan</button>
          </div>
        )}
      </div>
    </div>
  );
}
