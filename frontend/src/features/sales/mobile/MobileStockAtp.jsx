import { useEffect, useMemo, useState } from "react";
import { ArrowLeftRight, ChevronDown, ChevronRight, Clock3, PackageCheck, RefreshCw, Truck } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { can } from "../../../config/roles";
import { formatQty } from "../../../utils/formatters";
import InternalRequestCreateModal from "../../internal_requests/InternalRequestCreateModal";
import { displaySku, maskedSkuTitle } from "../../pos/skuDisplay";

// Sama dengan papan desktop: POV sales = total grup; baris kecil = PT saya.
const pv = (r, k) => (r.detail_scope === "own_entity" && r.global_total ? Number(r.global_total[k] || 0) : Number(r[`total_${k}`] || 0));
const TABS = [
  { key: "", label: "Semua" },
  { key: "empty", label: "Stok Habis", test: (r) => pv(r, "available") <= 0 },
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
  const [open, setOpen] = useState(null);
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
            className={`shrink-0 rounded-full border px-3 py-1.5 text-[11.5px] font-semibold ${tab === t.key ? "border-[#0058CC] bg-[#0058CC] text-white" : "border-[#E5E5EA] bg-white text-[#3C3C43]"}`}>
            {t.label} <span className="opacity-70">{counts[t.key] ?? 0}</span>
          </button>
        ))}
      </div>
      {/* Audit UI 24 Okt (HP Stok & ATP) — angka utama kartu = total GRUP, baris "PT saya" = badan usaha sendiri;
          dulu tanpa keterangan sehingga "Tersedia 50" tampak bertentangan dengan "PT saya: tersedia 0". */}
      {(rows || []).some((r) => r.detail_scope === "own_entity") && (
        <p className="text-[11px] m-muted" data-testid="m-stock-scope-note">Angka utama = total grup (semua PT). Baris “PT saya” = stok badan usaha Anda. Siap janji = tersedia + akan datang − permintaan tertunda (yang dipesan sudah tidak dihitung tersedia).</p>
      )}
      {toast && <div className="notice-bar success text-xs" data-testid="m-stock-toast">{toast}</div>}
      {err && <div className="notice-bar danger text-xs" data-testid="m-stock-error">{err}</div>}
      {rows === null && <p className="p-6 text-center text-sm m-muted">Memuat…</p>}
      {rows && !list.length && <p className="p-6 text-center text-sm m-muted" data-testid="m-stock-empty">Tidak ada stok yang cocok.</p>}
      {list.slice(0, limit).map((r) => <StockCard key={r.product_id} r={r} open={open === r.product_id}
        onToggle={() => setOpen(open === r.product_id ? null : r.product_id)} canRequest={canRequest}
        onRequest={() => setRequestFor({ product_id: r.product_id, qty: "" })} />)}
      {list.length > limit && <button className="secondary-button w-full justify-center py-2.5" onClick={() => setLimit(limit + PAGE)} data-testid="m-stock-more">Muat lagi ({list.length - limit})</button>}
      <InternalRequestCreateModal open={!!requestFor} prefillProductId={requestFor?.product_id || ""} prefillQty={requestFor?.qty || ""}
        onClose={() => setRequestFor(null)} onCreated={(doc) => { setRequestFor(null); setToast(`Permintaan ${doc?.number || ""} terkirim ke PT lain.`); }} />
    </div>
  );
}

function Num({ icon: Icon, label, value, unit, tone, testId }) {
  return (
    <div className="rounded-lg px-2 py-1.5" style={{ background: tone }} data-testid={testId}>
      <p className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-[#6B6B73]"><Icon size={10} /> {label}</p>
      <p className="text-[13px] font-bold tabular-nums">{formatQty(value)} <span className="text-[10px] font-medium text-[#6B6B73]">{unit}</span></p>
    </div>
  );
}

function StockCard({ r, open, onToggle, canRequest, onRequest }) {
  const atp = pv(r, "atp");
  const own = r.detail_scope === "own_entity" ? r.by_entity?.[0] : null;
  return (
    <div className="m-card p-3" data-testid={`m-stock-card-${r.product_id}`}>
      <button className="flex w-full items-start gap-2 text-left" onClick={onToggle} data-testid={`m-stock-toggle-${r.product_id}`}>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-bold">{r.product_name}</p>
          <p className="truncate font-mono text-[11px] m-muted" title={maskedSkuTitle(r.sku)}>{displaySku(r.sku)}</p>
        </div>
        <div className="text-right">
          <p className={`text-[16px] font-bold tabular-nums ${atp <= 0 ? "text-[#C62828]" : "text-[#1B7F4B]"}`} data-testid={`m-stock-atp-${r.product_id}`}>{formatQty(atp)}</p>
          <p className="text-[10px] font-semibold uppercase m-muted">siap janji · {r.unit}</p>
        </div>
        {open ? <ChevronDown size={16} className="mt-1 text-[#C7C7CC]" /> : <ChevronRight size={16} className="mt-1 text-[#C7C7CC]" />}
      </button>
      <div className="mt-2 grid grid-cols-3 gap-1.5">
        <Num icon={PackageCheck} label="Tersedia" value={pv(r, "available")} unit={r.unit} tone="#F2F7FF" testId={`m-stock-avail-${r.product_id}`} />
        <Num icon={Clock3} label="Dipesan" value={pv(r, "reserved")} unit={r.unit} tone="#FFF6E9" testId={`m-stock-reserved-${r.product_id}`} />
        <Num icon={Truck} label="Akan datang" value={pv(r, "incoming")} unit={r.unit} tone="#EEF9F1" testId={`m-stock-incoming-${r.product_id}`} />
      </div>
      {own && <p className="mt-1.5 text-[11px] m-muted" data-testid={`m-stock-own-${r.product_id}`}>PT saya ({own.entity_name}): tersedia {formatQty(own.available)} · ATP {formatQty(own.atp)} {r.unit}</p>}
      {(r.total_pending_demand || 0) > 0 && <p className="text-[10.5px] text-[#A05000]">Permintaan tertunda {formatQty(r.total_pending_demand)} {r.unit}</p>}
      {r.has_intercompany_opportunity && (
        <div className="mt-2 flex items-center justify-between gap-2 rounded-lg bg-[#F6EEFC] px-2.5 py-1.5" data-testid={`m-stock-interco-${r.product_id}`}>
          <span className="flex items-center gap-1 text-[11px] font-semibold text-[#7A3FA0]"><ArrowLeftRight size={12} /> PT lain punya {formatQty(r.other_entities_available || 0)} {r.unit}</span>
          {canRequest && <button className="rounded-md bg-[#7A3FA0] px-2 py-1 text-[10.5px] font-semibold text-white" onClick={onRequest} data-testid={`m-stock-request-${r.product_id}`}>Minta</button>}
        </div>
      )}
      {open && (
        <div className="mt-2 space-y-1 border-t border-[#EFF0F2] pt-2" data-testid={`m-stock-detail-${r.product_id}`}>
          {(r.by_entity || []).map((e) => (
            <div key={e.entity_id} className="text-[11px]">
              <p className="font-semibold">{e.entity_name}</p>
              {(e.by_warehouse || []).map((w) => (
                <p key={w.warehouse_id} className="flex justify-between pl-2 m-muted"><span className="truncate">{w.warehouse_name}</span>
                  <span className="shrink-0 tabular-nums">{formatQty(w.available)} · ATP {formatQty(w.atp)}{w.incoming ? ` · +${formatQty(w.incoming)}` : ""}</span></p>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
