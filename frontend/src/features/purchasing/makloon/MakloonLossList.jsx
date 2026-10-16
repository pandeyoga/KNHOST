import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { can } from "../../../config/roles";
import { formatCurrency, formatQty } from "../../../utils/formatters";

const STATUS = { pending_approval: "Menunggu persetujuan", posted: "Dibukukan", rejected: "Ditolak", auto: "Diproses" };

/** L01 — daftar susut/hilang bahan di mitra + persetujuan (hak `makloon_order.approve_loss`). */
export default function MakloonLossList({ mkoId, step, currentUser, onDone, onError }) {
  const [note, setNote] = useState({});
  const [busy, setBusy] = useState("");
  const canApprove = can(currentUser?.permissions, "makloon_order", "approve_loss");
  const [settle, setSettle] = useState({});
  const [bills, setBills] = useState([]);
  const hasPending = (step.material_losses || []).some((l) => l.status === "pending_approval");
  useEffect(() => {
    if (!canApprove || !hasPending) return;
    axios.get(`${API}/makloon-orders/${mkoId}/steps/${step.seq}/deductible-bills`).then(({ data }) => setBills(data || [])).catch(() => setBills([]));
  }, [canApprove, hasPending, mkoId, step.seq]);
  const decide = async (loss, approve) => {
    setBusy(loss.id);
    const st = settle[loss.id] || { mode: "tagih_ganti", bill: "" };
    try {
      await axios.post(`${API}/makloon-orders/${mkoId}/steps/${step.seq}/material-loss/${loss.id}/decide`,
        { approve, note: note[loss.id] || "", settle: st.mode, bill_id: st.mode === "potong_bon" ? st.bill : "" });
      await onDone?.();
    } catch (e) { onError?.(e.response?.data?.detail || "Gagal memutuskan susut."); }
    finally { setBusy(""); }
  };
  return (
    <div className="mt-2 rounded-lg border border-[#F0B5AE] bg-[#FFF5F4] p-2.5 text-[11px]" data-testid={`mko-loss-list-${step.seq}`}>
      <p className="mb-1 font-semibold text-[#A8221A]">Susut / hilang di mitra</p>
      {(step.material_losses || []).map((l) => (
        <div key={l.id} className="border-t border-[#F5D5D0] py-1.5 first:border-t-0" data-testid={`mko-loss-${l.id}`}>
          <p>
            {formatQty(l.qty)} {step.input_unit} · {l.roll_ids.length} roll · toleransi {l.tolerance_pct}% →
            dalam toleransi {formatQty(l.within_qty)} · di atas {formatQty(l.over_qty)}
            {l.status === "posted" && <> · beban {formatCurrency(l.expense_value)} · {l.settle === "potong_bon" ? "potong tagihan jasa" : "klaim mitra"} {formatCurrency(l.claim_value)}</>}
            {" "}<span className={l.status === "posted" ? "pill-success" : l.status === "rejected" ? "pill-muted" : "pill-warning"} data-testid={`mko-loss-status-${l.id}`}>{STATUS[l.status] || l.status}</span>
          </p>
          <p className="text-[#6B6B73]">{l.reason} — dicatat {l.recorded_by}{l.decided_by ? ` · diputuskan ${l.decided_by}` : ""}</p>
          {l.status === "pending_approval" && canApprove && l.recorded_by_id === currentUser?.id && (
            <p className="mt-1 text-[10.5px] text-[#8C4A00]" data-testid={`mko-loss-own-${l.id}`}>Anda pencatatnya — persetujuan harus oleh pengguna lain yang berwenang.</p>
          )}
          {l.status === "pending_approval" && canApprove && l.recorded_by_id !== currentUser?.id && (
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <select className="field !py-1 text-[11px]" data-testid={`mko-loss-settle-${l.id}`}
                value={(settle[l.id] || {}).mode || "tagih_ganti"}
                onChange={(e) => setSettle({ ...settle, [l.id]: { mode: e.target.value, bill: bills[0]?.id || "" } })}>
                <option value="tagih_ganti">Tagih ganti rugi (piutang klaim mitra)</option>
                <option value="potong_bon" disabled={!bills.length}>Potong tagihan jasa mitra{bills.length ? "" : " — tidak ada tagihan terbuka"}</option>
              </select>
              {(settle[l.id] || {}).mode === "potong_bon" && (
                <select className="field !py-1 text-[11px]" data-testid={`mko-loss-bill-${l.id}`} value={settle[l.id].bill}
                  onChange={(e) => setSettle({ ...settle, [l.id]: { ...settle[l.id], bill: e.target.value } })}>
                  {bills.map((b) => <option key={b.id} value={b.id}>{b.bill_number || b.id} · sisa {formatCurrency(b.remaining)}</option>)}
                </select>
              )}
              <input className="field !py-1 text-[11px] min-w-[200px] flex-1" placeholder="Catatan keputusan (wajib bila menolak)"
                data-testid={`mko-loss-note-${l.id}`} value={note[l.id] || ""} onChange={(e) => setNote({ ...note, [l.id]: e.target.value })} />
              <button type="button" disabled={busy === l.id} data-testid={`mko-loss-approve-${l.id}`} onClick={() => decide(l, true)} className="primary-button !py-1 text-[11px]"><Check size={12} /> Setujui</button>
              <button type="button" disabled={busy === l.id} data-testid={`mko-loss-reject-${l.id}`} onClick={() => decide(l, false)} className="secondary-button !py-1 text-[11px]"><X size={12} /> Tolak</button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
