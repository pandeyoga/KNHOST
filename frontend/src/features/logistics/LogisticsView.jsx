import { useEffect, useMemo, useRef, useState } from "react";
import { Truck, Plus, Search, RefreshCw, AlertTriangle } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import { listDeliveries, logisticsSummary, STATUS_LABEL } from "./logisticsApi";
import DeliveryCreateModal from "./DeliveryCreateModal";
import DeliveryDetailModal from "./DeliveryDetailModal";
import DriverTodayPanel from "./DriverTodayPanel";
import DeliveryTable from "./DeliveryTable";

// FB-02 — Modul Logistik: papan pengiriman (ekspedisi / armada sendiri).
const FILTERS = ["", "prepared", "loaded", "in_transit", "delivered", "completed", "failed"];
const ORDER_ROLES = ["admin", "manager", "sales", "sales_admin"];

export default function LogisticsView({ currentUser, selectedEntity, focusDelivery, onFocusConsumed }) {
  const role = currentUser?.role;
  const canManage = ["admin", "manager", "warehouse"].includes(role);
  const isDriver = role === "driver";
  const readOnly = !canManage && !isDriver;   // sales / admin sales: hanya-lihat
  const canOpenOrder = ORDER_ROLES.includes(role);
  const [rows, setRows] = useState([]);
  const [sum, setSum] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [preselectShipment, setPreselectShipment] = useState("");
  const [openId, setOpenId] = useState(null);
  const [tick, setTick] = useState(0);

  const params = useMemo(() => (selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {}), [selectedEntity]);

  async function load() {
    setLoading(true);
    try {
      const [r, s] = await Promise.all([
        listDeliveries({ ...params, status, ...(q ? { q } : {}) }),
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
    else if (focusDelivery?.search) { setStatus(""); setQ(focusDelivery.search); onFocusConsumed?.(); }
  }, [focusDelivery?.nonce]); // eslint-disable-line

  return (
    <div className="grid gap-3" data-testid="logistics-view">
      {isDriver && <DriverTodayPanel params={params} onOpen={setOpenId} refreshKey={tick} />}
      {sum && (
        <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-7 gap-2" data-testid="logistics-summary">
          {FILTERS.map((f) => (
            <button key={f || "all"} type="button" data-testid={`logistics-filter-${f || "all"}`}
              onClick={() => setStatus(f)} aria-pressed={status === f}
              className={`section-card !p-2.5 text-left transition-colors ${status === f ? "ring-2 ring-[#0058CC]" : "hover:bg-[#F7F9FC]"}`}>
              <p className="text-[10px] font-bold uppercase text-[#8E8E93]">{f ? STATUS_LABEL[f] : "Semua"}</p>
              <p className="text-[18px] font-bold tabular-nums">{f ? (sum.counts?.[f] ?? 0) : sum.total}</p>
            </button>
          ))}
        </div>
      )}
      {readOnly && (
        <div className="notice-bar warning !py-1.5" data-testid="logistics-readonly"><span className="text-[11.5px]">Mode hanya-lihat: Anda dapat memantau pengiriman & posisi, tanpa mengubahnya. Perubahan dikerjakan gudang & sopir.</span></div>
      )}
      {sum?.late > 0 && (
        <div className="notice-bar warning !py-1.5" data-testid="logistics-late"><AlertTriangle size={13} />
          <span className="text-[11.5px]"><b>{sum.late}</b> pengiriman melewati ETA dan belum terkirim.</span></div>
      )}
      <section className="section-card !p-3">
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="relative flex-1 min-w-[200px] max-w-[360px]">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#9A9BA3]" />
            <input data-testid="logistics-search" className="form-input !pl-8" placeholder="Cari nomor, resi, pelanggan, plat, sopir… (otomatis saat mengetik)"
              value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") load(); }} />
          </div>
          <button data-testid="logistics-search-button" className="secondary-button" onClick={load}><Search size={13} /> Cari</button>
          <button data-testid="logistics-refresh" className="secondary-button" onClick={load}><RefreshCw size={13} /> Muat ulang</button>
          {canManage && <button data-testid="logistics-create-button" className="primary-button ml-auto" onClick={() => setShowCreate(true)}><Plus size={14} /> Buat Pengiriman</button>}
        </div>
      </section>
      {error && <ErrorNotice message={error} onRetry={load} testId="logistics-error" />}

      {loading ? (
        <div className="section-card !p-10 text-center"><p className="text-[12px] text-[#6B6B73]" data-testid="logistics-loading">Memuat pengiriman…</p></div>
      ) : rows.length === 0 ? (
        q ? (
          /* L-6 — empty state khusus hasil pencarian (bukan "belum ada pengiriman") */
          <div className="section-card !p-12 text-center" data-testid="logistics-empty-search">
            <Search size={30} className="mx-auto text-[#C7C9CF] mb-2" />
            <p className="text-[13px] font-semibold text-[#3A3B42]">Tidak ada hasil untuk "{q}"{status ? ` pada status "${STATUS_LABEL[status]}"` : ""}</p>
            <p className="text-[12px] text-[#9A9BA3] mt-0.5">Coba kata kunci lain: nomor LG, nomor pesanan, resi, pelanggan, plat, atau nama sopir.</p>
            <div className="flex justify-center gap-2 mt-3">
              <button className="secondary-button" data-testid="logistics-clear-search" onClick={() => setQ("")}>Hapus pencarian</button>
              {status && <button className="secondary-button" data-testid="logistics-clear-filter" onClick={() => setStatus("")}>Tampilkan semua status</button>}
            </div>
          </div>
        ) : (
        <div className="section-card !p-12 text-center" data-testid="logistics-empty">
          <Truck size={30} className="mx-auto text-[#C7C9CF] mb-2" />
          <p className="text-[13px] font-semibold text-[#3A3B42]">Belum ada pengiriman{status ? ` berstatus "${STATUS_LABEL[status]}"` : ""}</p>
          <p className="text-[12px] text-[#9A9BA3] mt-0.5">{canManage ? "Buat pengiriman dari Surat Jalan yang sudah dispatch gudang." : "Pengiriman yang ditugaskan akan muncul di sini."}</p>
          {status && <button className="secondary-button mt-3" data-testid="logistics-clear-filter" onClick={() => setStatus("")}>Tampilkan semua</button>}
        </div>
        )
      ) : (
        <DeliveryTable rows={rows} onOpen={setOpenId} canOpenOrder={canOpenOrder} />
      )}

      {showCreate && <DeliveryCreateModal params={params} preselectShipmentId={preselectShipment} onClose={() => { setShowCreate(false); setPreselectShipment(""); }} onCreated={async (id) => { setShowCreate(false); await load(); setOpenId(id); }} />}
      {openId && <DeliveryDetailModal id={openId} canManage={canManage} canUpdate={canManage || isDriver} canOpenOrder={canOpenOrder} onClose={() => setOpenId(null)} onChanged={load} />}
    </div>
  );
}
