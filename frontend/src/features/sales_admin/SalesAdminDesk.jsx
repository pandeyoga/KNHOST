/**
 * SalesAdminDesk — FASE E-8 (E8.7 · US15/US16/US17/US18/US22) · **MEJA ADMIN SALES**.
 *
 * Bukan "menu tambahan", melainkan tempat kerja: antrean kerja, tiap antrean membawa jumlah + nilai + umur tertua,
 * tiap baris membawa SATU tindakan. Mesinnya sudah ada (papan pending SO · backorder · retur · permintaan internal ·
 * pengingat penagihan) — layar ini menyatukannya, tidak membangun ulang (E8.11).
 *
 * Meja gelombang 1 (spek 2026-11-25 §5.1): kerangka bersama `DeskFrame` — satu kepala (judul halaman + ikon ?),
 * tab Antrean (kartu ukuran tetap, berisi paling mendesak dulu) | Pantau (Pelacak SO, Keep & Pending, aturan grade,
 * antrean "Menunggu manajer"). Batas wewenang (faktur pajak, uang masuk, keputusan selisih bayar) disebut di ikon ?.
 * Aksi di tempat (periksa, pemenuhan, lepas) → pop-up aksinya / langsung; hasil sukses = toast, lalu hanya kartu
 * terkait yang dimuat ulang. Aksi pindah layar menyimpan posisi gulir (`markDeskReturn`) lebih dulu.
 */
import { useCallback, useEffect, useState } from "react";
import { Inbox } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import { can } from "../../config/roles";
import { toast } from "@/hooks/use-toast";
import DeskQueueCard, { DeskQueueCardSkeleton, inPlaceOf } from "./DeskQueueCard";
import SoTrackerCard from "./SoTrackerCard";
import VerifyOrderDialog from "./VerifyOrderDialog";
import ReleaseToWarehouseDialog from "./ReleaseToWarehouseDialog";
import FulfillmentDecisionDialog from "./FulfillmentDecisionDialog";
import KeepPendingPanel from "./KeepPendingPanel";
import CustomerGradeRulesCard from "./CustomerGradeRulesCard";
import DeskFrame, { DESK_GRID_CLASS } from "../desks/DeskFrame";
import { markDeskReturn } from "../desks/deskSession";
import { orderDeskQueues, splitPantau } from "./deskQueueOrder";
import { releaseMessage, releaseOrder, rowLink, salesAdminDesk, soTrackerLink } from "./workDeskApi";
import { apiErrorText } from "../../utils/apiError";

const DESK_KEY = "sales_admin";
const P = "desk";
const IN_PLACE = inPlaceOf(["verify", "fulfill", "release"]);

const HELP = (
  <>
    Alur pesanan dari ujung ke ujung: <b>periksa kelengkapan</b> → <b>putuskan pemenuhan</b> (stok sendiri · ambil dari
    PT lain · reorder ke supplier) → <b>konfirmasi</b> → dokumen → proses retur. Konfirmasi rutin adalah wewenang Anda;
    nilai besar, kredit, dan harga khusus tetap keputusan manajer.
  </>
);

export default function SalesAdminDesk({ currentUser, selectedEntity = "all", onOpenDocument }) {
  const perms = currentUser?.permissions || {};
  const [desk, setDesk] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshingId, setRefreshingId] = useState("");
  const [error, setError] = useState("");
  const [busyRef, setBusyRef] = useState("");
  const [verifyRow, setVerifyRow] = useState(null);
  const [fulfillRow, setFulfillRow] = useState(null);
  const [releaseRow, setReleaseRow] = useState(null);
  // Uji alur A1 (pelatihan 18 Nov) — Pelacak SO & Keep/Pending dimuat sendiri; sesudah aksi meja (periksa & lepas,
  // pemenuhan, lepas tahanan) keduanya ikut dimuat ulang (`trackerTick`), supaya status SO yang baru dilepas tidak basi.
  const [trackerTick, setTrackerTick] = useState(0);

  // `quiet` — muat ulang sesudah aksi: halaman tidak dikosongkan, kartu terkait saja yang bertanda (`refreshingId`).
  const load = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      setDesk(await salesAdminDesk(params));
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat Meja Admin Sales."));
    } finally { if (!quiet) setLoading(false); }
  }, [selectedEntity]);

  useEffect(() => { load(); }, [load]);

  const queues = Array.isArray(desk?.queues) ? desk.queues : [];
  const reloadAll = () => { load(); setTrackerTick((t) => t + 1); };
  async function reloadQueue(queueId) {
    setRefreshingId(queueId || "");
    setTrackerTick((t) => t + 1);
    try { await load({ quiet: true }); } finally { setRefreshingId(""); }
  }
  function done(msg, queueId) {
    toast({ title: msg });
    reloadQueue(queueId);
  }

  function open(link) {
    markDeskReturn(DESK_KEY);
    onOpenDocument?.(link);
  }

  // Trial 22 Okt (E8) — antrean "Ditahan": lepas ke gudang lewat pratinjau + konfirmasi (Meja gelombang 1, Task 10).
  // Baris Pelacak SO mencari baris `siap_dikonfirmasi` ber-id sama untuk `order_lines`; bila tidak ada, dialog
  // memuat pesanannya sendiri.
  function startRelease(row, queueId) {
    const found = queues.find((qq) => qq.id === "siap_dikonfirmasi")?.rows?.find((r) => r.ref_id === row.ref_id);
    const src = found || row;
    setReleaseRow({ id: src.ref_id, number: src.number, title: src.title, entity_id: src.entity_id || row.entity_id || "",
      order_lines: found?.order_lines, _qid: found ? "siap_dikonfirmasi" : queueId });
  }

  function openFull(row, queue) {
    setVerifyRow(null); setFulfillRow(null);
    open(rowLink(row, queue?.id || row?._qid, DESK_KEY));
  }

  function handleAction(row, queue) {
    const qid = queue?.id || "";
    if (row.action_kind === "verify") { setVerifyRow({ ...row, _qid: qid }); return; }
    if (row.action_kind === "fulfill") { setFulfillRow({ ...row, _qid: qid }); return; }
    if (row.action_kind === "release") { startRelease(row, qid); return; }
    open(rowLink(row, qid, DESK_KEY));
  }

  const split = splitPantau(queues, DESK_KEY);
  const card = (q) => (
    <DeskQueueCard key={q.id} queue={q} busyRef={busyRef} loading={loading || refreshingId === q.id}
      testPrefix={P} stateKey={`${DESK_KEY}:${q.id}`} inPlace={IN_PLACE} onAction={handleAction} onOpenFull={openFull} />
  );

  const antrean = loading && !desk ? (
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

  const pantau = (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-3">
      {/* Trial 22 Okt (B9) — aksi Pelacak SO dikerjakan DI MEJA (dulu [Atur pemenuhan] hanya membuka daftar pesanan). */}
      {can(perms, "order", "view") && (
        <SoTrackerCard desk="sales_admin" selectedEntity={selectedEntity} testPrefix={P} refreshKey={trackerTick} showRefresh={false}
          inPlaceActions={["Atur pemenuhan", "Periksa & lepas", "Lepas ke gudang"]}
          onOpenFull={(r) => open(soTrackerLink(r))} onOpen={(r) => {
          const row = { ref_id: r.id, number: r.number, title: r.customer_name, ref_type: "sales_order", entity_id: r.entity_id || "" };
          if (r.action === "Atur pemenuhan") return setFulfillRow(row);
          if (r.action === "Periksa & lepas") return setVerifyRow(row);
          if (r.action === "Lepas ke gudang") return startRelease(row, "");
          return open(soTrackerLink(r));
        }} />
      )}
      {/* Pola UI (M4, pemilik 16 Nov) — Keep & Pending butuh ruang: satu baris penuh, tidak berdampingan. */}
      <KeepPendingPanel selectedEntity={selectedEntity} onOpenDocument={open} refreshKey={trackerTick} showRefresh={false} />
      <CustomerGradeRulesCard selectedEntity={selectedEntity} />
      {split.pantau.length > 0 && <div className={DESK_GRID_CLASS}>{split.pantau.map(card)}</div>}
    </div>
  );

  return (
    <div data-testid="sales-admin-desk" className="grid grid-cols-[minmax(0,1fr)] gap-3">
      <ErrorNotice message={error} onRetry={() => load()} onDismiss={() => setError("")} testId={`${P}-error`} />

      <DeskFrame deskKey={DESK_KEY} testPrefix={P} help={HELP} notMine={desk?.not_my_desk || []}
        antrean={antrean} pantau={pantau} ready={!loading} onReload={reloadAll} />

      {verifyRow && (
        <VerifyOrderDialog
          orderId={verifyRow.ref_id}
          orderNumber={verifyRow.number}
          customerName={verifyRow.title}
          onClose={() => setVerifyRow(null)}
          onVerified={(msg) => { const qid = verifyRow._qid; setVerifyRow(null); done(msg, qid); }}
          onOpenFull={() => openFull(verifyRow)}
        />
      )}

      {releaseRow && (
        <ReleaseToWarehouseDialog
          order={releaseRow}
          run={() => releaseOrder(releaseRow.id)}
          onClose={() => setReleaseRow(null)}
          onDone={(res) => { const r = releaseRow; setReleaseRow(null); done(releaseMessage(res, r.number), r._qid); }}
        />
      )}

      {fulfillRow && (
        <FulfillmentDecisionDialog
          orderId={fulfillRow.ref_id}
          orderNumber={fulfillRow.number}
          customerName={fulfillRow.title}
          onClose={() => setFulfillRow(null)}
          onDecided={(msg) => { const qid = fulfillRow._qid; setFulfillRow(null); done(msg, qid); }}
          onOpenFull={() => openFull(fulfillRow)}
        />
      )}
    </div>
  );
}
