/**
 * W2-REQ-02 — Tata kelola master: preview data legacy (tanpa mengubah data), eksekusi batch
 * dari usulan preview yang dicentang, dan rollback per batch. SKU tidak pernah diubah.
 */
import { useEffect, useState } from "react";
import { ShieldCheck, RotateCcw } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";

export const MasterGovernancePanel = () => {
  const [pv, setPv] = useState(null);
  const [batches, setBatches] = useState([]);
  const [picked, setPicked] = useState({});
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = async () => {
    setError("");
    try {
      const [a, b] = await Promise.all([axios.get(`${API}/master-governance/preview`), axios.get(`${API}/master-governance/batches`)]);
      setPv(a.data); setBatches(b.data || []); setPicked({});
    } catch (e) { setError(apiErrorText(e, "Gagal memuat preview")); }
  };
  useEffect(() => { load(); }, []);
  const key = (p) => `${p.product_id}:${p.field}`;
  const run = async (fn) => { setBusy(true); setError(""); try { await fn(); await load(); } catch (e) { setError(apiErrorText(e, "Gagal")); } finally { setBusy(false); } };
  const apply = () => run(() => axios.post(`${API}/master-governance/batches`, {
    preview_signature: pv.preview_signature, note,
    accepted: pv.proposals.filter((p) => picked[key(p)]).map((p) => ({ product_id: p.product_id, field: p.field })),
  }));
  const rollback = (b) => {
    const reason = window.prompt(`Alasan rollback ${b.id}`) || "";
    if (reason.trim().length >= 5) run(() => axios.post(`${API}/master-governance/batches/${b.id}/rollback`, { reason }));
  };
  if (!pv) return error ? <div data-testid="mg-error" className="catalog-alert error">{error}</div> : null;
  const nPicked = Object.values(picked).filter(Boolean).length;
  return (
    <section data-testid="master-governance-panel" className="section-card space-y-3 p-3 text-[12px]">
      <h3 className="flex items-center gap-1.5 text-[13px] font-bold"><ShieldCheck size={15} /> Tata kelola master (preview legacy)</h3>
      <p className="text-[#6B6B73]">{pv.product_count} produk · kosong {pv.missing.length} · tidak kanonik {pv.non_canonical.length} · konflik {pv.conflicts.length} · kandidat duplikat {pv.duplicate_candidates.length}. Standar penamaan: {pv.policy.naming_standard}.</p>
      {pv.proposals.length > 0 && (
        <div data-testid="mg-proposals" className="space-y-1">
          {pv.proposals.map((p) => (
            <label key={key(p)} data-testid={`mg-proposal-${p.product_id}-${p.field}`} className="flex items-center gap-2">
              <input type="checkbox" checked={!!picked[key(p)]} onChange={(e) => setPicked({ ...picked, [key(p)]: e.target.checked })} />
              <span className="font-mono">{p.sku}</span> {p.field}: <s>{p.from || "∅"}</s> → <b>{p.to}</b> <span className="text-[#8E8E93]">({p.reason})</span>
            </label>
          ))}
          <div className="flex gap-2">
            <input data-testid="mg-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Catatan batch" className="field flex-1" />
            <button data-testid="mg-apply" className="primary-button" disabled={busy || !nPicked} onClick={apply}>Eksekusi {nPicked} perubahan</button>
          </div>
        </div>
      )}
      {pv.conflicts.length > 0 && <div data-testid="mg-conflicts" className="text-amber-700">Konflik (butuh keputusan manual): {pv.conflicts.map((c) => `${c.sku} ${c.field} [${c.candidates.join("/")}]`).join("; ")}</div>}
      {pv.duplicate_candidates.length > 0 && <div data-testid="mg-duplicates">Kandidat duplikat (atribut kanonik sama): {pv.duplicate_candidates.map((d) => d.products.map((x) => x.sku).join(" = ")).join("; ")}</div>}
      {batches.length > 0 && (
        <div data-testid="mg-batches" className="space-y-1">
          {batches.map((b) => (
            <div key={b.id} data-testid={`mg-batch-${b.id}`} className="flex items-center gap-2">
              <span className="font-mono">{b.id}</span> {b.status} · {b.changes.length} perubahan · {b.applied_by}
              {b.status === "applied" && <button data-testid={`mg-rollback-${b.id}`} className="secondary-button !py-0.5" disabled={busy} onClick={() => rollback(b)}><RotateCcw size={12} /> Rollback</button>}
            </div>
          ))}
        </div>
      )}
      {error && <div data-testid="mg-error" className="text-red-700">{error}</div>}
    </section>
  );
};
