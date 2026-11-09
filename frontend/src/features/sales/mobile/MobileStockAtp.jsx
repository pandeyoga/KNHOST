import { useEffect, useMemo, useState } from "react";
import { ArrowLeftRight, RefreshCw } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { can } from "../../../config/roles";
import { formatQty } from "../../../utils/formatters";
import InternalRequestCreateModal from "../../internal_requests/InternalRequestCreateModal";
import { displaySku, maskedSkuTitle } from "../../pos/skuDisplay";
import StockFigures, { figureState } from "../../../components/StockFigures";

// FIX-2 (B1b UI-45) — sama dengan papan desktop: angka = PT saya; grup hanya angka kedua ("Total grup (semua PT)").
const pv = (r, k) => Number(r[`total_${k}`] || 0);
const grp = (r, k) => (r.global_total ? Number(r.global_total[k] || 0) : Number(r[`total_${k}`] || 0));
// FIX-2 (B1 UI-40) — chip "Habis" memakai angka LOKAL server yang SAMA dengan desktop (dulu HP = grup 128, desktop =
// PT 292) dan menyebut cakupannya; "Habis di grup" = angka GLOBAL.
const localState = (r) => figureState(r, "local", r.total_available);
const globalState = (r) => figureState(r, "global", grp(r, "available"));
const TABS = [
  { key: "", label: "Semua" },
  { key: "empty", label: "Habis di cakupan saya", test: (r) => localState(r) === "habis" },
  { key: "empty_global", label: "Habis di grup", test: (r) => globalState(r) === "habis" },
  { key: "short", label: "ATP Kurang", test: (r) => pv(r, "atp") < 0 || (r.total_pending_demand || 0) > 0 },
  { key: "incoming", label: "Akan Datang", test: (r) => pv(r, "incoming") > 0 },
  { key: "interco", label: "Antar-PT", test: (r) => !!r.has_intercompany_opportunity },
];
const PAGE = 30;

/** Stok & ATP versi HP — kartu ringkas dari /inventory/status-board (siap janji, akan datang, peluang antar-PT). */
export default function MobileStockAtp({ user, selectedEntity = "all" }) {
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  const [tab, setTab] = useState("");
  const [limit, setLimit] = useState(PAGE);
  const [requestFor, setRequestFor] = useState(null);
  const [toast, setToast] = useState("");
  const canRequest = can(user?.permissions || {}, "internal_request", "create") && selectedEntity && selectedEntity !== "all";
  const load = () => {
    setErr("");
    const params = selectedEntity && selectedEntity !== "all" ? { owner_entity_id: selectedEntity } : {};
    axios.get(`${API}/inventory/status-board`, { params }).then((r) => setRows(Array.isArray(r.data) ? r.data : []))
      .catch((e) => { setErr(e.response?.data?.detail || "Gagal memuat stok."); setRows([]); });
  };
  useEffect(load, [selectedEntity]); // eslint-disable-line react-hooks/exhaustive-deps
  const counts = useMemo(() => Object.fromEntries(TABS.map((t) => [t.key, t.test ? (rows || []).filter(t.test).length : (rows || []).length])), [rows]);
  const list = useMemo(() => (rows || []).filter((r) => `${r.product_name} ${r.sku}`.toLowerCase().includes(q.toLowerCase())
    && (TABS.find((t) => t.key === tab)?.test || (() => true))(r)), [rows, q, tab]);
  useEffect(() => setLimit(PAGE), [q, tab]);

  return (
    <div className="space-y-2 p-3" data-testid="m-stock">
      <div className="flex gap-2">
        <input className="min-w-0 flex-1 rounded-lg border border-[#E5E5EA] p-2.5 text-sm" placeholder="Cari produk / SKU" value={q} onChange={(e) => setQ(e.target.value)} data-testid="m-stock-search" />
        <button className="rounded-lg border border-[#E5E5EA] px-3" onClick={load} aria-label="Muat ulang" data-testid="m-stock-refresh"><RefreshCw size={15} /></button>
      </div>
      <div className="no-scrollbar -mx-3 flex gap-1.5 overflow-x-auto px-3" data-testid="m-stock-tabs">
        {TABS.map((t) => (
          <button key={t.key || "all"} onClick={() => setTab(t.key)} data-testid={`m-stock-tab-${t.key || "all"}`}
            className={`min-h-[48px] shrink-0 rounded-full border px-3 py-1.5 text-[14px] font-semibold ${tab === t.key ? "border-[#0058CC] bg-[#0058CC] text-white" : "border-[#E5E5EA] bg-white text-[#3C3C43]"}`}>
            {t.label} <span className="opacity-70">{counts[t.key] ?? 0}</span>
          </button>
        ))}
      </div>
      {/* FIX-2 (B1 UI-06, K-B1-03) — angka utama kartu = Tersedia LOKAL (PT saya × lokasi kerja), kedua = GLOBAL (semua
          PT); ATP/akan datang/per gudang di rincian (ketuk angka). Dulu angka utama = total grup 16 px, "PT saya" 11 px. */}
      {rows && rows.length > 0 && (
        <p className="text-[14px] m-muted" data-testid="m-stock-scope-note">Angka pertama = cakupan Anda ({rows[0]?.stock_scope_label || "PT saya"}), kedua = semua PT. Ketuk angka untuk rincian per lokasi, PT, status, barang datang, dan ATP.</p>
      )}
      {toast && <div className="notice-bar success text-xs" data-testid="m-stock-toast">{toast}</div>}
      {err && <div className="notice-bar danger text-xs" data-testid="m-stock-error">{err}</div>}
      {rows === null && <p className="p-6 text-center text-sm m-muted">Memuat…</p>}
      {rows && !list.length && <p className="p-6 text-center text-sm m-muted" data-testid="m-stock-empty">Tidak ada stok yang cocok.</p>}
      {list.slice(0, limit).map((r) => <StockCard key={r.product_id} r={r} canRequest={canRequest}
        onRequest={() => setRequestFor({ product_id: r.product_id, qty: "" })} />)}
      {list.length > limit && <button className="secondary-button w-full justify-center py-2.5" onClick={() => setLimit(limit + PAGE)} data-testid="m-stock-more">Muat lagi ({list.length - limit})</button>}
      <InternalRequestCreateModal open={!!requestFor} prefillProductId={requestFor?.product_id || ""} prefillQty={requestFor?.qty || ""}
        onClose={() => setRequestFor(null)} onCreated={(doc) => { setRequestFor(null); setToast(`Permintaan ${doc?.number || ""} terkirim ke PT lain.`); }} />
    </div>
  );
}

function StockCard({ r, canRequest, onRequest }) {
  const f = r.stock_figures || {};
  return (
    <div className="m-card p-3" data-testid={`m-stock-card-${r.product_id}`}>
      <div className="min-w-0">
        <p className="truncate text-[15px] font-bold">{r.product_name}</p>
        <p className="truncate font-mono text-[14px] m-muted" title={maskedSkuTitle(r.sku)}>{displaySku(r.sku)} · {r.unit}</p>
      </div>
      <StockFigures size="lg" className="mt-2" testId={`m-stock-figures-${r.product_id}`} unit={f.unit || r.unit}
        local={f.local} global={f.global} localLabel={r.stock_scope_label || "PT saya"} globalLabel="Total grup (semua PT)"
        productIds={[r.product_id]} showState />
      {(r.total_pending_demand || 0) > 0 && <p className="mt-1 text-[14px] text-[#A05000]">Permintaan tertunda {formatQty(r.total_pending_demand)} {r.unit}</p>}
      {r.has_intercompany_opportunity && (
        <div className="mt-2 flex items-center justify-between gap-2 rounded-lg bg-[#F6EEFC] px-2.5 py-1.5" data-testid={`m-stock-interco-${r.product_id}`}>
          <span className="flex items-center gap-1 text-[14px] font-semibold text-[#7A3FA0]"><ArrowLeftRight size={14} /> PT lain punya {formatQty(r.other_entities_available || 0)} {r.unit}</span>
          {canRequest && <button className="min-h-[48px] rounded-md bg-[#7A3FA0] px-3 py-1 text-[14px] font-semibold text-white" onClick={onRequest} data-testid={`m-stock-request-${r.product_id}`}>Minta</button>}
        </div>
      )}
    </div>
  );
}
