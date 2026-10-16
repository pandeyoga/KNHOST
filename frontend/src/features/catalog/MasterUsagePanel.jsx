import { useEffect, useState } from "react";
import { Link2, Trash2 } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { askConfirm } from "../../services/confirmService";

/** P01 IMP-14 — dipakai di mana + kebijakan hapus master (Admin/MD; hanya bila belum dipakai). */
export function MasterUsagePanel({ kind, id, canPurge, onPurged }) {
  const [info, setInfo] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    setInfo(null); setErr("");
    if (id) axios.get(`${API}/master/usage/${kind}/${id}`).then((r) => setInfo(r.data)).catch((e) => setErr(e?.response?.data?.detail || "Gagal memuat jejak pemakaian."));
  }, [kind, id]);
  const purge = async () => {
    if (!await askConfirm({ title: "Hapus permanen?", message: `${info.name} belum pernah dipakai dan akan dihapus permanen.`, confirmLabel: "Hapus", danger: true })) return;
    try { await axios.delete(`${API}/master/${kind}/${id}/purge`); onPurged?.(); }
    catch (e) { const d = e?.response?.data?.detail; setErr(typeof d === "object" ? d.message : d || "Gagal menghapus."); }
  };
  if (err) return <p data-testid={`master-usage-error-${kind}`} className="text-xs text-[#C0392B]">{err}</p>;
  if (!info) return null;
  return (
    <div data-testid={`master-usage-${kind}`} className="mt-1 rounded-md border border-[#EFF0F2] bg-[#FAFBFC] px-2 py-1.5 text-xs text-[#3C3C43]">
      <span className="inline-flex items-center gap-1 font-semibold"><Link2 size={12} />Dipakai di:</span>{" "}
      {info.refs.length ? info.refs.map((r) => <span key={r.collection} data-testid={`master-usage-ref-${r.collection}`} className="mr-2">{r.label} <b>{r.count}</b></span>) : <span data-testid="master-usage-none">belum dipakai</span>}
      <p data-testid="master-usage-policy" className="text-[11px] text-[#6B6B73]">{info.policy}</p>
      {canPurge && info.can_delete && <button data-testid={`master-purge-${kind}`} className="secondary-button mt-1 !py-0.5 text-xs !text-red-600" onClick={purge}><Trash2 size={12} />Hapus permanen</button>}
    </div>
  );
}
