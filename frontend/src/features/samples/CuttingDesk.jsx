import { useCallback, useEffect, useState } from "react";
import { RefreshCw, PackageCheck } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import { apiErrorText } from "../../utils/apiError";
import { formatQty } from "../../utils/formatters";
import { cuttingDesk, cuttingLocations, receiveCut } from "./sampleApi";

const KIND = { standard: "Standar", hanger: "Hanger", catalogue: "Catalogue" };

/** L06 LN-061 — Meja Cutting / Admin Cutting: potong → terima hasil (boleh pindah lokasi) → kirim. */
export default function CuttingDesk({ selectedEntity = "all", canReceive }) {
  const [data, setData] = useState(null);
  const [locs, setLocs] = useState([]);
  const [dest, setDest] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const load = useCallback(async () => {
    try {
      const params = selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {};
      const [d, l] = await Promise.all([cuttingDesk(params), cuttingLocations()]);
      setData(d); setLocs(l); setError("");
    } catch (e) { setError(apiErrorText(e, "Gagal memuat Meja Cutting.")); }
  }, [selectedEntity]);
  useEffect(() => { load(); }, [load]);
  const receive = async (r) => {
    setBusy(r.task_id);
    try { await receiveCut(r.task_id, dest[r.task_id] || r.warehouse_id); await load(); }
    catch (e) { setError(apiErrorText(e, "Gagal menerima hasil potong.")); } finally { setBusy(""); }
  };
  return (
    <section data-testid="cutting-desk" className="grid gap-3">
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="cutting-desk-error" />
      <div className="flex items-center justify-between">
        <p className="text-[11.5px] text-[#6B6B73]">Gudang memotong → hasil potong <b>diterima Admin Cutting</b> (bisa dipindah ke lokasi kirim) → baru boleh dikirim.</p>
        <button data-testid="cutting-desk-refresh" className="icon-button" onClick={load} aria-label="Muat ulang"><RefreshCw size={14} /></button>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        {(data?.queues || []).map((q) => (
          <div key={q.key} data-testid={`cutting-queue-${q.key}`} className="section-card overflow-hidden">
            <p className="flex items-center justify-between border-b border-[#EFF0F2] px-3 py-2 text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">
              {q.label}<span data-testid={`cutting-queue-count-${q.key}`} className="rounded-full bg-[#F2F2F7] px-2 py-0.5 text-[10px]">{q.rows.length}</span></p>
            {q.rows.length === 0 ? <p className="p-4 text-center text-[11.5px] text-[#8E8E93]">Kosong.</p> : (
              <ul className="divide-y divide-[#F2F3F5] text-[12px]">
                {q.rows.map((r) => (
                  <li key={r.task_id} data-testid={`cutting-row-${r.task_id}`} className="px-3 py-2">
                    <p className="font-semibold">{r.order_number} · {r.product_name} <span className="rounded bg-[#FFF3D6] px-1.5 text-[10px] text-[#9A5B00]">{KIND[r.sample_kind] || r.sample_kind}</span></p>
                    <p className="text-[11px] text-[#6B6B73]">{formatQty(r.quantity)} {r.unit} · {r.warehouse_name || r.warehouse_id}
                      {r.child_roll_no ? ` · potongan ${r.child_roll_no} dari ${r.parent_roll_no}` : ""}
                      {r.source_owner_entity_id ? ` · stok milik ${r.source_owner_entity_id} — tunggu pembelian internal` : ""}
                      {r.handoff ? ` · diterima ${r.handoff.received_by}${r.handoff.transferred ? " (dipindah lokasi)" : ""}` : ""}</p>
                    {q.key === "to_receive" && canReceive && (
                      <div className="mt-1.5 flex flex-wrap items-center gap-2">
                        <select data-testid={`cutting-dest-${r.task_id}`} className="field !h-8 !w-auto text-[11px]" value={dest[r.task_id] || r.warehouse_id}
                          onChange={(e) => setDest((d) => ({ ...d, [r.task_id]: e.target.value }))}>
                          {locs.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
                        </select>
                        <button data-testid={`cutting-receive-${r.task_id}`} className="primary-button !h-8" disabled={busy === r.task_id} onClick={() => receive(r)}>
                          <PackageCheck size={13} /> Terima hasil potong</button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
