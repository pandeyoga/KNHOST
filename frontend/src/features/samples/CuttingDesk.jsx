import { useCallback, useEffect, useState } from "react";
import { RefreshCw, PackageCheck, Clock } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import { apiErrorText } from "../../utils/apiError";
import { formatQty } from "../../utils/formatters";
import { KNSelect } from "../../components/KNSelect";
import { cuttingDesk, cuttingLocations, receiveCut } from "./sampleApi";

// Hanya gudang yang boleh dipakai pemilik roll (bersama, atau khusus untuk PT itu).
const destFor = (locs, owner) => locs.filter((l) => !owner || l.sharing_mode !== "dedicated" || (l.entity_ids || []).includes(owner));

const KIND = { standard: "Standar", hanger: "Hanger", catalogue: "Catalogue" };

const fmtWait = (m) => (m < 60 ? `${m} mnt` : m < 1440 ? `${Math.floor(m / 60)} j ${m % 60} mnt` : `${Math.floor(m / 1440)} hr ${Math.floor((m % 1440) / 60)} j`);

// Durasi sejak dipotong gudang sampai diterima Admin Cutting (berjalan bila belum diterima).
function WaitBadge({ row, th, done }) {
  const m = row.wait_minutes;
  if (m == null) return null;
  const level = done ? "done" : m >= th.late_minutes ? "late" : m >= th.warn_minutes ? "warn" : "ok";
  const cls = { late: "bg-[#FDECEC] text-[#C62828]", warn: "bg-[#FFF3D6] text-[#9A5B00]", ok: "bg-[#E8F5EC] text-[#1E7B3C]", done: "bg-[#F2F2F7] text-[#6B6B73]" }[level];
  const text = done ? `diterima setelah ${fmtWait(m)}` : `${level === "late" ? "Terlambat · " : ""}menunggu ${fmtWait(m)}`;
  return (
    <span data-testid={`cutting-wait-${row.task_id}`} data-level={level} className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold tabular-nums ${cls}`}>
      <Clock size={10} />{text}</span>
  );
}

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
  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load]);
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
      {data?.late_count > 0 && (
        <p data-testid="cutting-late-alert" className="rounded-lg bg-[#FDECEC] px-3 py-2 text-[11.5px] font-semibold text-[#C62828]">
          {data.late_count} potongan menunggu diterima Admin Cutting lebih dari {Math.round(data.wait_thresholds.late_minutes / 60)} jam.</p>
      )}
      <div className="grid gap-3 lg:grid-cols-2">
        {(data?.queues || []).map((q) => (
          <div key={q.key} data-testid={`cutting-queue-${q.key}`} className="section-card overflow-hidden">
            <p className="flex items-center justify-between border-b border-[#EFF0F2] px-3 py-2 text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">
              {q.label}<span data-testid={`cutting-queue-count-${q.key}`} className="rounded-full bg-[#F2F2F7] px-2 py-0.5 text-[10px]">{q.rows.length}</span></p>
            {q.rows.length === 0 ? <p className="p-4 text-center text-[11.5px] text-[#8E8E93]">Kosong.</p> : (
              <ul className="divide-y divide-[#F2F3F5] text-[12px]">
                {q.rows.map((r) => (
                  <li key={r.task_id} data-testid={`cutting-row-${r.task_id}`} className="px-3 py-2">
                    <p className="flex flex-wrap items-center gap-1.5 font-semibold">{r.order_number} · {r.product_name} <span className="rounded bg-[#FFF3D6] px-1.5 text-[10px] text-[#9A5B00]">{KIND[r.sample_kind] || r.sample_kind}</span>
                      {data.wait_thresholds && <WaitBadge row={r} th={data.wait_thresholds} done={q.key === "ready"} />}</p>
                    <p className="text-[11px] text-[#6B6B73]">{formatQty(r.quantity)} {r.unit} · {r.warehouse_name || r.warehouse_id}
                      {r.child_roll_no ? ` · potongan ${r.child_roll_no} dari ${r.parent_roll_no}` : ""}
                      {r.source_owner_entity_id ? ` · stok milik ${r.source_owner_entity_id} — tunggu pembelian internal` : ""}
                      {r.handoff ? ` · diterima ${r.handoff.received_by}${r.handoff.transferred ? " (dipindah lokasi)" : ""}` : ""}</p>
                    {q.key === "to_receive" && canReceive && (
                      <div className="mt-1.5 flex flex-wrap items-center gap-2">
                        <div className="min-w-[200px]">
                          <KNSelect data-testid={`cutting-dest-${r.task_id}`} aria-label="Lokasi tujuan" className="field !h-8 text-[11px]"
                            value={dest[r.task_id] || r.warehouse_id} onValueChange={(v) => setDest((d) => ({ ...d, [r.task_id]: v }))}
                            options={destFor(locs, r.roll_owner_entity_id).map((l) => ({ value: l.id, label: l.name }))} />
                        </div>
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
