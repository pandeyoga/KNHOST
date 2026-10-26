import { useEffect, useMemo, useRef, useState } from "react";
import { Truck, Plus, Search, RefreshCw, AlertTriangle, LayoutDashboard, ListOrdered, Bus, ListChecks, Download } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import PageTabs from "../../components/PageTabs";
import { PageHeader } from "../../components/ListPageParts";
import KNDatePicker from "../../components/KNDatePicker";
import useViewPreset from "../../hooks/useViewPreset";
import { wibDate } from "../../utils/formatters";
import { listDeliveries, logisticsSummary, STATUS_LABEL, carrierText } from "./logisticsApi";
import DeliveryCreateModal from "./DeliveryCreateModal";
import DeliveryDetailModal from "./DeliveryDetailModal";
import DriverTodayPanel from "./DriverTodayPanel";
import DeliveryTable from "./DeliveryTable";
import DispatchDashboard from "./DispatchDashboard";
import HistoryPanel from "./HistoryPanel";
import FleetPanel from "./FleetPanel";
import { can, roleIs } from "../../config/roles";
import TripPlannerPanel from "./TripPlannerPanel";

// FB-02 — Modul Logistik: Dasbor (aksi cepat + visual) · Daftar · Armada · Picking & Trip.
// Fase 3 · P5 — D-19: tab "Riwayat" DILEBUR ke Daftar. Saringan status "Terkirim/Selesai/Gagal" dan kartu
// "Riwayat" memakai mesin riwayat server (rentang tanggal, moda, statistik, CSV, halaman); status berjalan
// memakai daftar aktif. Satu tombol "Buat Pengiriman" di kepala halaman (dulu juga di kartu KPI Dasbor).
const HISTORY = "history";                          // semua status akhir (dulu tab Riwayat)
const TERMINAL = ["delivered", "completed", "failed"];
const FILTERS = ["", "prepared", "loaded", "in_transit", "delivered", "completed", "failed", HISTORY];
const TABS = [
  { id: "dashboard", label: "Dasbor", icon: LayoutDashboard },
  { id: "list", label: "Daftar pengiriman", icon: ListOrdered },
  { id: "fleet", label: "Armada", icon: Bus },
  { id: "trip", label: "Picking & Trip", icon: ListChecks, manageOnly: true },
];

function exportActiveCsv(rows, from, to) {
  const head = ["Nomor", "Tanggal dibuat", "Pesanan", "Pelanggan", "Moda", "Pengangkut", "Surat Jalan", "ETA", "Status"];
  const lines = rows.map((r) => [r.number, wibDate(r.created_at), r.order_number, r.customer_name, r.mode_label, carrierText(r),
    (r.shipment_nos || []).join(" "), r.eta || "", r.status_label].map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(","));
  const blob = new Blob([[head.join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
  a.download = `pengiriman-${from || "awal"}-${to || "kini"}.csv`; a.click(); URL.revokeObjectURL(a.href);
}

export default function LogisticsView({ currentUser, selectedEntity, focusDelivery, onFocusConsumed }) {
  const role = currentUser?.role;
  const canManage = can(currentUser?.permissions || {}, "logistics", "manage");   // Sisir lanjutan gerbang peran (2026-10-21)
  const isDriver = roleIs(role, ["driver"]);   // = pagar sopir server (role_in)
  const readOnly = !canManage && !isDriver;   // sales / admin sales: hanya-lihat
  const canOpenOrder = can(currentUser?.permissions || {}, "order", "view");
  const [tab, setTab] = useState(isDriver ? "list" : "dashboard");
  const [rows, setRows] = useState([]);
  const [sum, setSum] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [preselectShipment, setPreselectShipment] = useState("");
  const [openId, setOpenId] = useState(null);
  const [tick, setTick] = useState(0);
  const historyMode = status === HISTORY || TERMINAL.includes(status);

  const params = useMemo(() => (selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {}), [selectedEntity]);

  async function load() {
    setLoading(true);
    try {
      const listStatus = status === HISTORY ? "" : status;
      const [r, s] = await Promise.all([
        listDeliveries({ ...params, status: listStatus, ...(q ? { q } : {}) }),
        logisticsSummary(params),
      ]);
      setRows(Array.isArray(r) ? r : []); setSum(s); setError(""); setTick((t) => t + 1);
    } catch (e) { setError(e.response?.data?.detail || "Gagal memuat pengiriman."); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, [selectedEntity, status]); // eslint-disable-line
  // L-5 — cari sambil mengetik (debounce 300 ms); Enter / tombol Cari tetap bisa.
  const qMounted = useRef(false);
  useEffect(() => {
    if (!qMounted.current) { qMounted.current = true; return undefined; }
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
  }, [q]); // eslint-disable-line

  // Deep-link dari Perjalanan Pesanan ("Buka di Logistik") → langsung buka detailnya.
  useEffect(() => {
    if (focusDelivery?.deliveryId) { setStatus(""); setOpenId(focusDelivery.deliveryId); onFocusConsumed?.(); }
    // Sesi #087 — dari Meja Admin Gudang: langsung buka "Buat Pengiriman" dengan SJ terpilih.
    else if (focusDelivery?.createFromShipmentId) { setPreselectShipment(focusDelivery.createFromShipmentId); setShowCreate(true); onFocusConsumed?.(); }
    // Meja Admin Gudang / meja lain: saring daftar ke nomor SJ / pesanan yang diklik.
    else if (focusDelivery?.search) { setTab("list"); setStatus(""); setQ(focusDelivery.search); onFocusConsumed?.(); }
  }, [focusDelivery?.nonce]); // eslint-disable-line
  // Preset navigasi: `{ tab: "history" }` (tab Riwayat lama) → Daftar dengan saringan Riwayat.
  useViewPreset("logistics", (p) => {
    if (p.tab === HISTORY) { setTab("list"); setStatus(HISTORY); }
    else if (p.tab) setTab(p.tab);
    if (p.status !== undefined) setStatus(p.status);
  });

  const openCreate = (shipmentId = "") => { setPreselectShipment(shipmentId); setShowCreate(true); };
  const gotoList = (st = "") => { setStatus(st); setTab("list"); };
  // Rentang tanggal untuk daftar berjalan = tanggal dibuat (WIB), disaring di peramban; riwayat disaring server.
  const shownRows = useMemo(() => rows.filter((r) => {
    const d = wibDate(r.created_at);
    if (dateFrom && (!d || d < dateFrom)) return false;
    if (dateTo && (!d || d > dateTo)) return false;
    return true;
  }), [rows, dateFrom, dateTo]);
  const countOf = (f) => {
    if (!sum) return 0;
    if (f === "") return sum.total;
    if (f === HISTORY) return TERMINAL.reduce((a, k) => a + (sum.counts?.[k] || 0), 0);
    return sum.counts?.[f] ?? 0;
  };
  const filterLabel = (f) => (f === "" ? "Semua" : f === HISTORY ? "Riwayat (akhir)" : STATUS_LABEL[f]);

  return (
    <div className="grid gap-3" data-testid="logistics-view">
      <PageHeader icon={Truck} title="Pengiriman" testId="logistics-header"
        subtitle="Surat Jalan yang sudah dispatch gudang → pengiriman (ekspedisi, armada sendiri, atau diambil pelanggan)."
        actions={canManage
          ? <button data-testid="logistics-create-button" className="primary-button" onClick={() => openCreate("")}><Plus size={14} /> Buat Pengiriman</button>
          : null} />

      {isDriver && <DriverTodayPanel params={params} onOpen={setOpenId} refreshKey={tick} />}

      {/* L-01 — dulu pil hitam buatan sendiri; kini PageTabs baku (testid lama dipertahankan). */}
      <PageTabs testId="logistics-tabs" value={tab} onChange={setTab} ariaLabel="Tab pengiriman"
        tabs={TABS.filter((t) => (!isDriver || t.id !== "fleet") && (!t.manageOnly || canManage))
          .map((t) => ({ key: t.id, label: t.label, icon: t.icon, testId: `logistics-tab-${t.id}` }))} />

      {readOnly && (
        <div className="notice-bar warning !py-1.5" data-testid="logistics-readonly"><span className="text-[11.5px]">Mode hanya-lihat: Anda dapat memantau pengiriman & posisi, tanpa mengubahnya. Perubahan dikerjakan gudang & sopir.</span></div>
      )}

      {tab === "dashboard" && (
        <DispatchDashboard params={params} refreshKey={tick} canManage={canManage} canUpdate={canManage || isDriver}
          onOpen={setOpenId} onCreate={openCreate} onGotoList={gotoList} onGotoFleet={() => setTab("fleet")} />
      )}
      {tab === "fleet" && <FleetPanel params={params} canManage={canManage} onOpen={setOpenId} refreshKey={tick} />}
      {tab === "trip" && canManage && <TripPlannerPanel params={params} />}

      {tab === "list" && (<>
        {sum && (
          <div className="grid grid-cols-4 lg:grid-cols-8 gap-2" data-testid="logistics-summary">
            {FILTERS.map((f) => (
              <button key={f || "all"} type="button" data-testid={`logistics-filter-${f || "all"}`}
                onClick={() => setStatus(f)} aria-pressed={status === f}
                title={f === HISTORY ? "Terkirim, selesai & gagal — dengan rentang tanggal, moda, statistik & CSV" : undefined}
                className={`section-card !p-2.5 text-left transition-colors ${status === f ? "ring-2 ring-[#0058CC]" : "hover:bg-[#F7F9FC]"}`}>
                <p className="text-[10px] font-bold uppercase text-[#8E8E93] truncate">{filterLabel(f)}</p>
                <p className={`text-[18px] font-bold tabular-nums ${countOf(f) ? "" : "text-[#8E8E93]"}`}>{countOf(f)}</p>
              </button>
            ))}
          </div>
        )}
        {sum?.late > 0 && !historyMode && (
          <div className="notice-bar warning !py-1.5" data-testid="logistics-late"><AlertTriangle size={13} />
            <span className="text-[11.5px]"><b>{sum.late}</b> pengiriman melewati ETA dan belum terkirim.</span></div>
        )}
        <section className="section-card !p-3">
          <div className="flex flex-wrap items-end gap-2.5">
            <div className="relative flex-1 min-w-[200px] max-w-[360px]">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#9A9BA3]" />
              <input data-testid="logistics-search" className="form-input !pl-8" placeholder="Cari nomor, resi, pelanggan, plat, sopir… (otomatis saat mengetik)"
                value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") load(); }} />
            </div>
            <div className="grid gap-1 w-[150px]"><label className="text-[10.5px] font-bold uppercase text-[#6B6B73]">Dari</label>
              <KNDatePicker data-testid="logistics-from" value={dateFrom} onChange={setDateFrom} placeholder="Tgl awal" /></div>
            <div className="grid gap-1 w-[150px]"><label className="text-[10.5px] font-bold uppercase text-[#6B6B73]">Sampai</label>
              <KNDatePicker data-testid="logistics-to" value={dateTo} onChange={setDateTo} placeholder="Tgl akhir" /></div>
            <button data-testid="logistics-search-button" className="secondary-button" onClick={load}><Search size={13} /> Cari</button>
            <button data-testid="logistics-refresh" className="secondary-button" onClick={load}><RefreshCw size={13} /> Muat ulang</button>
            {!historyMode && (
              <button data-testid="logistics-export" className="secondary-button" disabled={!shownRows.length}
                onClick={() => exportActiveCsv(shownRows, dateFrom, dateTo)} title="Unduh CSV daftar yang tampil"><Download size={13} /> CSV</button>
            )}
          </div>
        </section>
        {error && <ErrorNotice message={error} onRetry={load} testId="logistics-error" />}

        {historyMode ? (
          <HistoryPanel params={params} onOpen={setOpenId} refreshKey={tick}
            status={status === HISTORY ? "" : status} dateFrom={dateFrom} dateTo={dateTo} q={q} />
        ) : loading ? (
          <div className="section-card !p-10 text-center"><p className="text-[12px] text-[#6B6B73]" data-testid="logistics-loading">Memuat pengiriman…</p></div>
        ) : shownRows.length === 0 ? (
          q || dateFrom || dateTo ? (
            <div className="section-card !p-12 text-center" data-testid="logistics-empty-search">
              <Search size={30} className="mx-auto text-[#C7C9CF] mb-2" />
              <p className="text-[13px] font-semibold text-[#3A3B42]">Tidak ada hasil{q ? ` untuk "${q}"` : ""}{dateFrom || dateTo ? " pada rentang tanggal ini" : ""}{status ? ` pada status "${STATUS_LABEL[status]}"` : ""}</p>
              <p className="text-[12px] text-[#9A9BA3] mt-0.5">Coba kata kunci lain: nomor LG, nomor pesanan, resi, pelanggan, plat, atau nama sopir.</p>
              <div className="flex justify-center gap-2 mt-3">
                {q && <button className="secondary-button" data-testid="logistics-clear-search" onClick={() => setQ("")}>Hapus pencarian</button>}
                {(dateFrom || dateTo) && <button className="secondary-button" data-testid="logistics-clear-dates" onClick={() => { setDateFrom(""); setDateTo(""); }}>Hapus rentang tanggal</button>}
                {status && <button className="secondary-button" data-testid="logistics-clear-filter" onClick={() => setStatus("")}>Tampilkan semua status</button>}
              </div>
            </div>
          ) : (
            <div className="section-card !p-12 text-center" data-testid="logistics-empty">
              <Truck size={30} className="mx-auto text-[#C7C9CF] mb-2" />
              <p className="text-[13px] font-semibold text-[#3A3B42]">Belum ada pengiriman{status ? ` berstatus "${STATUS_LABEL[status]}"` : ""}</p>
              <p className="text-[12px] text-[#9A9BA3] mt-0.5">{canManage ? "Buat pengiriman dari Surat Jalan yang sudah dispatch gudang — lihat aksi cepat di Dasbor." : "Pengiriman yang ditugaskan akan muncul di sini."}</p>
              {status && <button className="secondary-button mt-3" data-testid="logistics-clear-filter" onClick={() => setStatus("")}>Tampilkan semua</button>}
            </div>
          )
        ) : (
          <DeliveryTable rows={shownRows} onOpen={setOpenId} canOpenOrder={canOpenOrder} />
        )}
      </>)}

      {showCreate && <DeliveryCreateModal params={params} preselectShipmentId={preselectShipment} onClose={() => { setShowCreate(false); setPreselectShipment(""); }} onCreated={async (id) => { setShowCreate(false); setPreselectShipment(""); await load(); setOpenId(id); }} />}
      {openId && <DeliveryDetailModal id={openId} canManage={canManage} canUpdate={canManage || isDriver} canOpenOrder={canOpenOrder} onClose={() => setOpenId(null)} onChanged={load} />}
    </div>
  );
}
