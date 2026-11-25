import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Scissors } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import LinkCard from "../../components/LinkCard";
import { HelpTip } from "../../components/ListPageParts";
import { useEntityScope } from "../../context/EntityScopeContext";
import { entityShortById } from "../../utils/entityLabel";
import { apiErrorText } from "../../utils/apiError";
import { formatQty } from "../../utils/formatters";
import { toast } from "@/hooks/use-toast";
import DeskQueueCard, { DeskQueueCardSkeleton, inPlaceOf } from "../sales_admin/DeskQueueCard";
import { DESK_GRID_CLASS } from "../desks/DeskFrame";
import { cuttingDesk, cuttingLocations } from "./sampleApi";
import CuttingReceiveDialog from "./CuttingReceiveDialog";
import ListLimitNote from "../wms/ListLimitNote";   // FIX-7 (B3b LST-02)

const KIND = { standard: "Standar", hanger: "Hanger", catalogue: "Katalog" };   // G2-19 — satu istilah "Katalog"
const P = "cutting";
const IN_PLACE = inPlaceOf(["receive_cut"]);
const KEYS = ["awaiting_internal", "to_receive", "ready"];

const fmtWait = (m) => (m < 60 ? `${m} mnt` : m < 1440 ? `${Math.floor(m / 60)} j ${m % 60} mnt` : `${Math.floor(m / 1440)} hr ${Math.floor((m % 1440) / 60)} j`);

/** Antrean server (`queues[]` berkunci `key`) → antrean kartu bersama; `to_cut` tetap ringkasan (D-24a). */
export function toCuttingQueues(data, { canReceive = false, entities = [] } = {}) {
  const list = Array.isArray(data?.queues) ? data.queues : [];
  return list.filter((q) => KEYS.includes(q.key)).map((q) => {
    const rows = (q.rows || []).map((r) => ({
      ref_type: "wms_task", ref_id: r.task_id, row_key: r.task_id, number: r.order_number, title: r.customer_name || "—",
      subtitle: [
        [r.product_name, r.sku].filter(Boolean).join(" · "),
        KIND[r.sample_kind] || r.sample_kind,
        `${formatQty(r.quantity)} ${r.unit || ""}`.trim(),
        r.warehouse_name || r.warehouse_id,
        r.child_roll_no ? `potongan ${r.child_roll_no} dari ${r.parent_roll_no}` : "",
        r.source_owner_entity_id ? `stok milik ${entityShortById(entities, r.source_owner_entity_id, "PT lain")} — tunggu pembelian internal` : "",
        r.handoff ? `diterima ${r.handoff.received_by}${r.handoff.transferred ? " (tiba lewat transfer)" : ""}` : "",
        r.handoff_pending ? `Menunggu transfer ${r.handoff_pending.transfer_code} ke ${r.handoff_pending.to_warehouse_name || r.handoff_pending.to_warehouse_id}` : "",
      ].filter(Boolean).join(" · "),
      value: Number(r.quantity) || 0, unit: r.unit, age_days: Math.floor((r.wait_minutes || 0) / 1440), at: r.cut_at || "",
      entity_id: r.roll_owner_entity_id || "", order_id: r.order_id, warehouse_id: r.warehouse_id,
      roll_owner_entity_id: r.roll_owner_entity_id,
      action: q.key === "to_receive" && canReceive ? "Terima" : "", action_kind: "receive_cut",
    }));
    return { id: q.key, label: q.label, count: rows.length, value_kind: "qty", value_label: "Qty", action_label: "", rows };
  });
}

const HELP = "Gudang memotong → hasil potong diterima Admin Cutting (bisa dipindah ke lokasi kirim) → baru boleh dikirim.";

/** L06 LN-061 — Meja Cutting / Admin Cutting: potong → terima hasil (boleh pindah lokasi) → kirim. */
export default function CuttingDesk({ selectedEntity = "all", canReceive }) {
  const { entities } = useEntityScope();   // nama PT pemilik stok (bukan id teknis, INV-UI-02)
  const [data, setData] = useState(null);
  const [locs, setLocs] = useState([]);
  const [error, setError] = useState("");
  const [recvRow, setRecvRow] = useState(null);
  const load = useCallback(async () => {
    try {
      const params = selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {};
      const [d, l] = await Promise.all([cuttingDesk(params), cuttingLocations()]);
      setData(d); setLocs(l); setError("");
    } catch (e) { setError(apiErrorText(e, "Gagal memuat Meja Cutting.")); }
  }, [selectedEntity]);
  useEffect(() => {
    load();
    const t = setInterval(load, 60000);   // muat ulang diam-diam: data diganti, status kartu (cari/saring/halaman) tetap
    return () => clearInterval(t);
  }, [load]);

  const handleAction = (row) => {
    if (row.action_kind === "receive_cut") setRecvRow(row);
  };
  const toCut = (data?.queues || []).find((x) => x.key === "to_cut");
  const queues = toCuttingQueues(data, { canReceive, entities });
  const siblings = recvRow
    ? (queues.find((x) => x.id === "to_receive")?.rows || []).filter((r) => r.order_id === recvRow.order_id).length : 1;
  return (
    <section data-testid="cutting-desk" className="grid grid-cols-1 gap-3">
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="cutting-desk-error" />
      <div className="flex items-center justify-end gap-1">
        <HelpTip text={HELP} testId="cutting-desk-help" />
        <button data-testid="cutting-desk-refresh" className="icon-button" onClick={load} aria-label="Muat ulang"><RefreshCw size={14} /></button>
      </div>
      {data?.late_count > 0 && (
        <p data-testid="cutting-late-alert" className="rounded-lg bg-kn-danger-soft px-3 py-2 text-fs-12 font-semibold text-kn-danger-text">
          {data.late_count} potongan menunggu diterima Admin Cutting lebih dari {fmtWait(data.wait_thresholds.late_minutes)}.</p>
      )}
      {/* FIX-7 (B3b LST-02, P1) — server kini hanya memuat tugas TERBUKA (500 terbaru) dan memberi jumlah sungguhan; bila
          antrean terbuka melebihi batas, tanda ini muncul (dulu tugas baru hilang diam-diam setelah 500 tugas sample). */}
      <ListLimitNote meta={data?.truncated ? { total: data.total_open, truncated: true, shown: data.shown, skip: 0 } : null}
        noun="tugas potong terbuka" hint="yang tampil = tugas terbuka TERBARU; tugas terbuka paling lama tidak ikut — tuntaskan atau batalkan di Operasi Gudang › Cutting." testId="cutting-desk-limit" />
      {!data ? (
        <div data-testid="cutting-loading" className={DESK_GRID_CLASS}>
          {[0, 1].map((i) => <DeskQueueCardSkeleton key={i} testPrefix={P} index={i} />)}
        </div>
      ) : (
        <div className={DESK_GRID_CLASS}>
          {toCut && <ToCutSummary queue={toCut} />}
          {queues.map((qq) => (
            <DeskQueueCard key={qq.id} queue={qq} testPrefix={P} stateKey={`${P}:${qq.id}`} inPlace={IN_PLACE}
              onAction={handleAction} onOpenFull={handleAction} />
          ))}
        </div>
      )}
      {recvRow && (
        <CuttingReceiveDialog row={recvRow} locations={locs} siblings={siblings}
          onClose={() => setRecvRow(null)} onChanged={load}
          onDone={(msg) => { setRecvRow(null); toast({ title: msg }); load(); }} />
      )}
    </section>
  );
}

/**
 * Fase 3 · P3 (D-24a, keputusan pemilik) — "menunggu dipotong gudang" adalah antrean GUDANG: tempat kerjanya
 * Operasi Gudang › Cutting (`wms-cutting`). Di Meja Cutting cukup ringkasan (jumlah + nomor pesanan) + tautan bila
 * peran boleh membuka layar itu; bagian penerimaan hasil potong oleh Admin Cutting tetap di sini.
 */
function ToCutSummary({ queue }) {
  const rows = queue.rows || [];
  const numbers = [...new Set(rows.map((r) => r.order_number).filter(Boolean))];
  const shown = numbers.slice(0, 8).join(", ");
  const more = numbers.length > 8 ? ` +${numbers.length - 8} lainnya` : "";
  return (
    <div data-testid={`cutting-queue-${queue.key}`} className="section-card overflow-hidden">
      <p className="flex items-center justify-between border-b border-kn-divider px-3 py-2 text-fs-14 font-semibold text-kn-text">
        {queue.label}<span data-testid={`cutting-queue-count-${queue.key}`} className="rounded-full bg-kn-neutral-soft px-2 py-0.5 text-fs-12 font-medium tabular-nums">{rows.length}</span></p>
      <div className="grid gap-2 p-3 text-fs-13">
        {rows.length === 0 ? <p className="text-center text-fs-12 text-kn-text-2">Kosong.</p> : (
          <p data-testid="cutting-to-cut-numbers" className="text-fs-13 text-kn-text">
            {rows.length} baris potong dari {numbers.length} pesanan: <b>{shown}</b>{more}.
          </p>
        )}
        {/* Preset layar Cutting gudang (P5): tahap "cut"; satu pesanan → langsung tersaring nomornya. */}
        <LinkCard testId="cutting-to-cut-link" icon={Scissors} what="Pemotongan oleh gudang"
          where="Gudang › Operasi Gudang › Cutting" view="wms-cutting" label="Buka Cutting gudang"
          preset={{ stage: "cut", q: numbers.length === 1 ? numbers[0] : "" }}
          readOnlyText="Dipotong oleh gudang di Operasi Gudang › Cutting — hasilnya muncul di antrean penerimaan di sebelah." />
      </div>
    </div>
  );
}
