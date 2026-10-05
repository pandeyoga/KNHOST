/**
 * W2-REQ-06 — tugas keputusan selisih penerimaan PO: tunggu sisa / amendment / short-close.
 */
import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { apiErrorText } from "../../../utils/apiError";

const OPTIONS = [["wait", "Tunggu sisa"], ["amend", "Amendment ke qty aktual"], ["short_close", "Short-close"]];

export const POVarianceTasksPanel = ({ po, onAmend, onChanged }) => {
  const [tasks, setTasks] = useState([]);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = () => axios.get(`${API}/po-variance-tasks`, { params: { status: "", po_id: po.id } })
    .then((r) => setTasks(r.data || [])).catch(() => setTasks([]));
  useEffect(() => { load(); }, [po.id]); // eslint-disable-line

  const decide = async (t, decision) => {
    setBusy(true); setError("");
    try {
      await axios.post(`${API}/po-variance-tasks/${t.id}/decide`, { decision, reason });
      setReason(""); await load(); onChanged?.();
      if (decision === "amend") onAmend?.(po);
    } catch (e) { setError(apiErrorText(e, "Gagal menyimpan keputusan")); } finally { setBusy(false); }
  };
  if (!tasks.length) return null;
  return (
    <div data-testid="po-variance-panel" className="rounded-md border border-amber-200 bg-amber-50 p-2.5 text-[11px] space-y-2">
      <div className="flex items-center gap-1.5 font-bold text-amber-800"><AlertTriangle size={13} /> Selisih penerimaan — keputusan MD</div>
      {tasks.map((t) => (
        <div key={t.id} data-testid={`po-variance-task-${t.id}`} className="rounded border border-amber-200 bg-white p-2">
          <div className="font-semibold">{t.product_name || t.product_id}</div>
          <div className="tabular-nums text-[#3C3C43]">Pesan {t.ordered_qty} · terima {t.received_qty} · kurang <b>{t.short_qty}</b> {t.unit} · PJ {t.assignee_name || "—"}</div>
          {t.finance_notified && <div className="text-amber-700">PO sudah punya DP/tagihan/pembayaran — Finance diberi tahu; nilai tidak diubah otomatis.</div>}
          {t.status === "open" ? (
            <div className="mt-1.5 space-y-1">
              <input data-testid={`po-variance-reason-${t.id}`} value={reason} onChange={(e) => setReason(e.target.value)}
                placeholder="Alasan keputusan (wajib)" className="w-full rounded border border-amber-200 px-2 py-1" />
              <div className="flex flex-wrap gap-1">
                {OPTIONS.map(([k, label]) => (
                  <button key={k} data-testid={`po-variance-decide-${k}-${t.id}`} disabled={busy || reason.trim().length < 5}
                    onClick={() => decide(t, k)} className="secondary-button !px-2 !py-1 text-[11px] disabled:opacity-40">{label}</button>
                ))}
              </div>
            </div>
          ) : (
            <div data-testid={`po-variance-status-${t.id}`} className="mt-1 text-[#1B7F4B]">
              {t.decision_label || t.decision} · {t.decided_by} · {t.reason}{t.status === "pending_amendment" ? " (menunggu amendment)" : ""}
            </div>
          )}
        </div>
      ))}
      {error && <div data-testid="po-variance-error" className="text-red-700">{error}</div>}
    </div>
  );
};
