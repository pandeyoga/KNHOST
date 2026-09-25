/** ColorUseRequestsPanel — antrean izin pakai warna eksklusif; manager (color.approve) menyetujui/menolak/mencabut. */
import { useEffect, useState } from "react";
import { Check, ShieldCheck, Undo2, X } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";

const TONE = { pending: "bg-[#FEF3C7] text-[#92400E]", approved: "bg-[#DCFCE7] text-[#166534]", rejected: "bg-[#FEE2E2] text-[#991B1B]", revoked: "bg-[#F5F5F7] text-[#6B6B73]" };

export default function ColorUseRequestsPanel({ canApprove, reloadKey, onChanged }) {
  const [rows, setRows] = useState([]);
  const [showAll, setShowAll] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState({});

  const load = () => axios.get(`${API}/color-library/use-requests`).then((r) => setRows(Array.isArray(r.data) ? r.data : [])).catch(() => {});
  useEffect(() => { load(); }, [reloadKey]);

  const act = async (row, action) => {
    setError("");
    try {
      await axios.post(`${API}/color-library/use-requests/${row.id}/${action}`, { note: note[row.id] || "" });
      setNote((n) => ({ ...n, [row.id]: "" }));
      load(); onChanged?.();
    } catch (e) { setError(e.response?.data?.detail || "Gagal memproses permintaan."); }
  };

  const pending = rows.filter((r) => r.status === "pending");
  const shown = showAll ? rows : pending;
  if (!rows.length) return null;
  return (
    <section className="rounded-xl border border-[#FDE68A] bg-[#FFFBEB]" data-testid="color-use-requests-panel">
      <header className="flex items-center gap-2 px-3 py-2">
        <ShieldCheck size={14} className="text-[#B45309]" />
        <h3 className="text-[12.5px] font-bold">Izin pakai warna eksklusif</h3>
        <span className="rounded bg-white px-1.5 text-[10px] font-bold text-[#92400E]" data-testid="color-use-requests-pending-count">{pending.length} menunggu</span>
        <button type="button" data-testid="color-use-requests-toggle" onClick={() => setShowAll((v) => !v)} className="ml-auto text-[10.5px] font-semibold text-[#0058CC] hover:underline">
          {showAll ? "Hanya yang menunggu" : `Lihat semua (${rows.length})`}
        </button>
      </header>
      <ErrorNotice message={error} onDismiss={() => setError("")} testId="color-use-requests-error" />
      <div className="divide-y divide-[#FDE68A] border-t border-[#FDE68A]">
        {shown.length === 0 && <p className="px-3 py-3 text-[11px] text-[#6B6B73]">Tidak ada permintaan yang menunggu.</p>}
        {shown.map((r) => (
          <div key={r.id} className="flex flex-wrap items-center gap-2 px-3 py-2 text-[11px]" data-testid={`color-use-request-${r.id}`}>
            <span className="h-7 w-7 shrink-0 rounded" style={{ backgroundColor: r.hex }} />
            <div className="min-w-[220px] flex-1">
              <p><b>{r.color_code}</b> · {r.color_name} <span className="text-[#92400E]">(milik {r.owner_customer_name})</span> → <b>{r.target_label}</b></p>
              <p className="text-[#6B6B73]">{r.requested_by}: “{r.reason}”{r.context ? ` · ${r.context}` : ""}{r.decision_note ? ` · catatan: ${r.decision_note}` : ""}</p>
            </div>
            <span className={`rounded px-1.5 py-px text-[9.5px] font-bold ${TONE[r.status]}`} data-testid={`color-use-request-status-${r.id}`}>{r.status_label}</span>
            {canApprove && (r.status === "pending" || r.status === "approved") && (
              <div className="flex items-center gap-1">
                <input className="field h-7 w-[150px] text-[11px]" placeholder={r.status === "pending" ? "Catatan (wajib bila tolak)" : "Alasan cabut"} value={note[r.id] || ""}
                  onChange={(e) => setNote({ ...note, [r.id]: e.target.value })} data-testid={`color-use-request-note-${r.id}`} />
                {r.status === "pending" ? (<>
                  <button type="button" className="primary-button h-7 px-2 text-[11px]" onClick={() => act(r, "approve")} data-testid={`color-use-request-approve-${r.id}`}><Check size={12} /> Setujui</button>
                  <button type="button" className="secondary-button h-7 px-2 text-[11px]" onClick={() => act(r, "reject")} data-testid={`color-use-request-reject-${r.id}`}><X size={12} /> Tolak</button>
                </>) : (
                  <button type="button" className="secondary-button h-7 px-2 text-[11px]" onClick={() => act(r, "revoke")} data-testid={`color-use-request-revoke-${r.id}`}><Undo2 size={12} /> Cabut</button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
