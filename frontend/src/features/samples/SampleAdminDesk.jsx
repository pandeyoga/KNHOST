/**
 * SampleAdminDesk — REVISI SAMPEL: MEJA ADMIN SAMPEL (POV tim sample).
 * Antrean per tahap: ACC pembayaran (berbayar) → teruskan ke gudang → dipotong → dikirim/diambil → selesai.
 * Satu tindakan per baris; pantau membuka daftar Pesanan Sample dengan baris terpilih.
 *
 * Meja gelombang 1 (spek 2026-11-25 §5.1): kerangka bersama `DeskFrame` — satu kepala (judul halaman + ikon ?),
 * tab Antrean (ACC bayar, teruskan ke gudang) | Pantau (Pelacak SO bila berizin `order.view`, lalu antrean yang
 * dikerjakan pihak lain: dipotong gudang, dikirim/diambil, selesai). Aksi di tempat (setujui bayar, teruskan ke
 * gudang) → hasil sukses = toast, lalu hanya kartu terkait yang dimuat ulang.
 */
import { useCallback, useEffect, useState } from "react";
import { Inbox } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import { can } from "../../config/roles";
import { toast } from "@/hooks/use-toast";
import { apiErrorText } from "../../utils/apiError";
import DeskQueueCard, { DeskQueueCardSkeleton, inPlaceOf } from "../sales_admin/DeskQueueCard";
import SoTrackerCard from "../sales_admin/SoTrackerCard";
import { orderDeskQueues, splitPantau } from "../sales_admin/deskQueueOrder";
import ReleaseToWarehouseDialog from "../sales_admin/ReleaseToWarehouseDialog";
import { soTrackerLink } from "../sales_admin/workDeskApi";
import DeskFrame, { DESK_GRID_CLASS } from "../desks/DeskFrame";
import { markDeskReturn } from "../desks/deskSession";
import SamplePaymentApproveDialog from "./SamplePaymentApproveDialog";
import { sampleDesk, confirmSampleOrder } from "./sampleApi";

const DESK_KEY = "sample_admin";
const P = "sample-desk";
const IN_PLACE = inPlaceOf(["approve_payment", "confirm"]);
const HELP = (
  <>
    Pesanan sample dari sales (SOS-): <b>sample berbayar</b> disetujui pembayarannya dulu (Finance/Admin Sample),
    <b> sample gratis</b> langsung siap. Lalu <b>teruskan ke gudang</b> → gudang memotong dari roll (pindai RFID, catat
    panjang aktual) → dikirim / diambil pelanggan.
  </>
);

const sampleLink = (row) => ({ view: "sample-orders", nav_id: "sample-orders", focus_type: "sample_order",
  focus_id: row.ref_id, number: row.number });

export default function SampleAdminDesk({ currentUser, selectedEntity = "all", onOpenDocument }) {
  const perms = currentUser?.permissions || {};
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshingId, setRefreshingId] = useState("");
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0);
  const [forwardRow, setForwardRow] = useState(null);
  const [payRow, setPayRow] = useState(null);

  // `quiet` — muat ulang sesudah aksi: halaman tidak dikosongkan, hanya kartu terkait bertanda (`refreshingId`).
  const load = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      setData(await sampleDesk(params)); setError("");
    } catch (e) { setError(apiErrorText(e, "Gagal memuat Meja Sample.")); }
    finally { if (!quiet) setLoading(false); }
  }, [selectedEntity]);
  useEffect(() => { load(); }, [load]);

  async function reloadQueue(queueId) {
    setRefreshingId(queueId || "");
    setTick((t) => t + 1);
    try { await load({ quiet: true }); } finally { setRefreshingId(""); }
  }

  const open = (link) => { markDeskReturn(DESK_KEY); onOpenDocument?.(link); };

  async function handleAction(row, queue) {
    if (row.action_kind === "confirm") {
      setForwardRow({ id: row.ref_id, number: row.number, title: row.title, entity_id: row.entity_id || "",
        order_lines: row.order_lines || [], _qid: queue?.id });
      return;
    }
    if (row.action_kind === "approve_payment") {
      setPayRow({ id: row.ref_id, number: row.number, title: row.title, sample_billing: row.sample_billing,
        grand_total: row.grand_total, paid_total: row.paid_total, sample_payment_status: row.sample_payment_status
          || (row.badge === "persetujuan ulang" ? "reapproval_required" : ""), _qid: queue?.id });
      return;
    }
    open(sampleLink(row));
  }

  const queues = Array.isArray(data?.queues) ? data.queues : [];
  const split = splitPantau(queues, DESK_KEY);
  const card = (q) => (
    <DeskQueueCard key={q.id} queue={q} loading={loading || refreshingId === q.id} busyRef="" testPrefix={P}
      stateKey={`${DESK_KEY}:${q.id}`} inPlace={IN_PLACE} currentUser={currentUser} onAction={handleAction} onOpenFull={(row) => open(sampleLink(row))} />
  );

  const antrean = loading && !data ? (
    <div data-testid={`${P}-loading`} className={DESK_GRID_CLASS}>
      {[0, 1, 2, 3].map((i) => <DeskQueueCardSkeleton key={i} testPrefix={P} index={i} />)}
    </div>
  ) : split.antrean.length === 0 ? (
    <div className="section-card section-pad text-center text-fs-13 text-kn-text-2" data-testid={`${P}-empty`}>
      <Inbox size={24} className="mx-auto mb-2 text-kn-neutral" aria-hidden="true" />
      Belum ada antrean untuk PT yang sedang Anda lihat.
    </div>
  ) : (
    <div className={DESK_GRID_CLASS}>{orderDeskQueues(split.antrean).map(card)}</div>
  );

  const tracker = can(perms, "order", "view") && (
    <SoTrackerCard desk="sample_admin" selectedEntity={selectedEntity} testPrefix={P} refreshKey={tick} currentUser={currentUser}
      showRefresh={false}
      onOpen={(r) => open(soTrackerLink(r))} onOpenFull={(r) => open(soTrackerLink(r))} />
  );
  const pantau = tracker || split.pantau.length > 0 ? (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-3">
      {tracker}
      {split.pantau.length > 0 && <div className={DESK_GRID_CLASS}>{split.pantau.map(card)}</div>}
    </div>
  ) : null;

  return (
    <div data-testid="sample-desk" className="grid grid-cols-[minmax(0,1fr)] gap-3">
      <ErrorNotice message={error} onRetry={() => load()} onDismiss={() => setError("")} testId={`${P}-error`} />
      <DeskFrame deskKey={DESK_KEY} testPrefix={P} help={HELP} notMine={data?.not_my_desk || []}
        antrean={antrean} pantau={pantau} ready={!loading} onReload={() => { load(); setTick((t) => t + 1); }} />
      {payRow && (
        <SamplePaymentApproveDialog order={payRow} onClose={() => setPayRow(null)}
          onDone={() => {
            const p = payRow; setPayRow(null);
            // F-15 — persetujuan ULANG (tagihan berubah > toleransi sesudah potong): kiriman sample dilepas
            toast({ title: p.sample_payment_status === "reapproval_required"
              ? `${p.number}: tagihan baru disetujui — kiriman sample dilepas.`
              : `${p.number}: pembayaran sample disetujui — kini siap diteruskan ke gudang.` });
            reloadQueue(p._qid);
          }} />
      )}
      {forwardRow && (
        <ReleaseToWarehouseDialog mode="forward" order={forwardRow}
          run={() => confirmSampleOrder(forwardRow.id)}
          onClose={() => setForwardRow(null)}
          onDone={(r) => {
            const f = forwardRow; setForwardRow(null);
            toast({ title: `${f.number} diteruskan ke gudang — ${r?.tasks_created ?? ""} tugas potong lahir.` });
            reloadQueue(f._qid);
          }} />
      )}
    </div>
  );
}
