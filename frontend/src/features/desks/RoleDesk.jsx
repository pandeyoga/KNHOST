/**
 * RoleDesk — Sesi #087 · MEJA MD & MEJA ADMIN GUDANG (pola Meja Finance/Admin Sales) + Meja Saya (U-2).
 * Satu komponen untuk tiga meja: konfigurasi per `desk` (judul, pemuat, penjelasan).
 * Baris antrean melompat ke layar penanganannya lewat `onOpenDocument` (navigasi + auto-buka);
 * aksi `create_delivery` (Admin Gudang) membuka Logistik dengan SJ terpilih — jembatan WMS→Logistik.
 *
 * Meja gelombang 1 (spek 2026-11-25 §5.1): kerangka bersama `DeskFrame` — satu kepala (judul halaman + ikon ? berisi
 * penjelasan meja & "Bukan wewenang meja ini"), tab Antrean (kartu ukuran tetap, berisi paling mendesak dulu) | Pantau
 * (Pelacak SO bila berizin `order.view`; Meja Gudang + kartu retur internal). Kartu angka & kotak "Paling lama
 * menunggu" dihapus — urutan kartu sudah menaruh antrean tertua di depan.
 */
import { useCallback, useEffect, useState } from "react";
import { Inbox } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import { can } from "../../config/roles";
import { useAppNav } from "../../context/AppNavContext";
import { apiErrorText } from "../../utils/apiError";
import DeskQueueCard, { DeskQueueCardSkeleton } from "../sales_admin/DeskQueueCard";
import SoTrackerCard from "../sales_admin/SoTrackerCard";
import ReturnDeskSummaryCard, { returnSummaryHasContent, useReturnDeskSummary } from "../home/ReturnDeskSummaryCard";
import { orderDeskQueues, splitPantau } from "../sales_admin/deskQueueOrder";
import { mdDesk, warehouseAdminDesk, myDesk, rowLink, soTrackerLink } from "../sales_admin/workDeskApi";
import { resolveView } from "../../utils/viewAlias";
import { humanizeQueueRows } from "./deskText";
import { openLogistics } from "../logistics/logisticsDeepLink";
import DeskFrame, { DESK_GRID_CLASS } from "./DeskFrame";
import { markDeskReturn } from "./deskSession";

const DESKS = {
  md: {
    title: "Meja MD", load: mdDesk, testPrefix: "md-desk",
    intro: <>Pengembangan produk dari satu meja: <b>permintaan desain</b> (setujui · tugaskan · putuskan), <b>sample &amp; labdip</b> per putaran, <b>PR &amp; PO bahan</b>, <b>SPK makloon</b> (berjalan &amp; menunggu faktur mitra), dan SPK inspeksi yang belum punya acuan sample.</>,
  },
  warehouse_admin: {
    title: "Meja Admin Gudang", load: warehouseAdminDesk, testPrefix: "wh-desk", returns: true,
    intro: <>Memimpin operasi gudang: <b>SJ yang sudah diberangkatkan tetapi belum diangkut logistik</b>, tugas outbound, PO menunggu penerimaan, SPK belum ditugaskan, persetujuan opname/transfer, dan pengiriman gagal/belum ditutup.</>,
  },
  // U-2 (2026-09) — satu meja untuk 6 peran tersisa.
  me: {
    title: "Meja Saya", load: myDesk, testPrefix: "my-desk",
    intro: <>Semua yang menunggu tindakan Anda hari ini: <b>Giliran saya</b> (dokumen yang baru berpindah tahap ke Anda) dan antrean khas peran Anda. Buka baris untuk melompat ke layar penanganannya.</>,
  },
};

const NO_IN_PLACE = () => false;   // MD · Gudang · Meja Saya: semua aksi pindah layar (pop-up rincian dulu)

/** Izin pengguna: `currentUser` dari App; cadangan lama `localStorage kn_user` (pemanggil tanpa prop). */
function permsOf(currentUser) {
  if (currentUser?.permissions) return currentUser.permissions;
  try { return JSON.parse(localStorage.getItem("kn_user") || "null")?.permissions || {}; } catch { return {}; }
}

export default function RoleDesk({ desk = "md", currentUser, selectedEntity = "all", onOpenDocument }) {
  const cfg = DESKS[desk] || DESKS.md;
  const deskKey = DESKS[desk] ? desk : "md";
  const p = cfg.testPrefix;
  const perms = permsOf(currentUser);
  const { go } = useAppNav();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      setData(await cfg.load(params)); setError("");
    } catch (e) { setError(apiErrorText(e, `Gagal memuat ${cfg.title}.`)); }
    finally { setLoading(false); }
  }, [selectedEntity, cfg]);

  useEffect(() => { load(); }, [load]);

  const open = (link) => { markDeskReturn(deskKey); onOpenDocument?.(link); };

  /** Layar penanganan baris. `full` = "Buka layar penuh" (dokumennya), bukan jalan pintas aksinya. */
  function navigate(shown, queue, { full = false } = {}) {
    const row = shown?._raw || shown;   // aksi memakai baris ASLI dari server (nomor/id apa adanya), bukan teks tampilan
    if (!full && row.action_kind === "create_delivery") {
      // Jembatan Gudang → Logistik: buka Logistik dengan SJ ini terpilih untuk dibuat pengiriman.
      openLogistics({ createFromShipmentId: row.ref_id });
      open({ view: "logistics", nav_id: "logistics" });
      return;
    }
    if (row.ref_type === "logistics_delivery") {
      openLogistics({ deliveryId: row.ref_id });
      open({ view: "logistics", nav_id: "logistics" });
      return;
    }
    if (row.ref_type === "shipment") {
      openLogistics({ search: row.number || "" });
      open({ view: "logistics", nav_id: "logistics" });
      return;
    }
    const turnLink = resolveView(row.link || row.extra?.link);
    if (queue?.id === "giliran_saya" && turnLink) {
      open({ view: turnLink, nav_id: turnLink, focus_id: row.ref_id, focus_type: row.ref_type, number: row.number || "" });
      return;
    }
    open(rowLink(row, queue?.id, desk));
  }

  // Audit UI tahap 2 (G5-10) — notifikasi LAMA di "Giliran saya" masih berteks "tahap: cancelled" (notifikasi baru
  // sudah berlabel dari server). Fase 4 · R6: berlaku untuk SEMUA antrean (subjudul "waiting_approval · Budi",
  // "outbound", nomor id teknis) lewat `deskText.js`; baris asli disimpan di `_raw` untuk aksi.
  const queues = humanizeQueueRows(Array.isArray(data?.queues) ? data.queues : []);
  const split = splitPantau(queues, deskKey);

  const antrean = loading && !data ? (
    <div data-testid={`${p}-loading`} className={DESK_GRID_CLASS}>
      {[0, 1, 2, 3].map((i) => <DeskQueueCardSkeleton key={i} testPrefix={p} index={i} />)}
    </div>
  ) : split.antrean.length === 0 ? (
    <div className="section-card section-pad text-center text-fs-13 text-kn-text-2" data-testid={`${p}-empty`}>
      <Inbox size={24} className="mx-auto mb-2 text-kn-neutral" aria-hidden="true" />
      Belum ada antrean untuk PT yang sedang Anda lihat.
    </div>
  ) : (
    <div className={DESK_GRID_CLASS}>
      {orderDeskQueues(split.antrean).map((q) => (
        <DeskQueueCard key={q.id} queue={q} loading={loading} testPrefix={p} stateKey={`${deskKey}:${q.id}`}
          inPlace={NO_IN_PLACE} onAction={(row, queue) => navigate(row, queue)}
          onOpenFull={(row, queue) => navigate(row, queue, { full: true })} />
      ))}
    </div>
  );

  // FIX-1 (audit B1b UI-56) — pelacak SO (nilai Rupiah) hanya untuk pemegang izin pesanan; sopir/desainer tidak.
  const tracker = can(perms, "order", "view") && (
    <SoTrackerCard key="tracker" desk={desk} selectedEntity={selectedEntity} testPrefix={p} refreshKey={tick}
      onOpen={(r) => open(soTrackerLink(r))} />
  );
  // Kartu retur internal (Meja Gudang) hanya dimuat untuk pemegang izin endpoint-nya dan hanya digambar bila ada isinya —
  // Pantau "kosong" diputuskan dari yang benar-benar tampil, bukan dari daftar komponen.
  const retSummary = useReturnDeskSummary(selectedEntity, {
    enabled: Boolean(cfg.returns) && (can(perms, "sales_return", "view") || can(perms, "interco", "view")),
    refreshKey: tick,
  });
  const returns = returnSummaryHasContent(retSummary) && (
    <ReturnDeskSummaryCard key="returns" selectedEntity={selectedEntity} summary={retSummary}
      onNavigate={(t) => { markDeskReturn(deskKey); go(t); }} />
  );
  const pantau = tracker || returns ? (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-3">{returns}{tracker}</div>
  ) : null;

  return (
    <div data-testid={`${p}`} className="grid grid-cols-[minmax(0,1fr)] gap-3">
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId={`${p}-error`} />
      <DeskFrame deskKey={deskKey} testPrefix={p} help={cfg.intro} notMine={data?.not_my_desk || []}
        antrean={antrean} pantau={pantau} pantauLoading={retSummary === undefined} ready={!loading}
        onReload={() => { load(); setTick((t) => t + 1); }} />
    </div>
  );
}
