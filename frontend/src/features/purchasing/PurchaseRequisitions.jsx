import { useEffect, useState } from "react";
import { MergeModal, MergeSuggestions, canMerge } from "./PrMergePanel";
import axios, { API } from "../../services/apiClient";
import {
  ClipboardList, Plus, CheckCircle2, RefreshCw, Clock, FileText, Loader2,
} from "lucide-react";
import { formatCurrency } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";
import LineFilter from "../../components/LineFilter";   // FASE L
import { PageHeader, MetricRow, SearchBox, StatusTabs } from "../../components/ListPageParts";
import { SOURCE_LABEL, StatusPill } from "./prConstants";
import DetailPanel from "./PurchaseRequisitionDetailPanel";
import PrCreateModal from "./PrCreateModal";
import { can } from "../../config/roles";

/**
 * Purchase Requisitions (Depth #2a) — Hulu procurement.
 * PR → approval (matriks 'purchase_requisition') → konversi ke PO.
 * Sumber: manual | reorder | special_order.
 */

export default function PurchaseRequisitions({ currentUser, selectedEntity = "all", focusDoc, onClearFocus }) {
  const [view, setView] = useState("list");            // list | create | detail
  const [items, setItems] = useState([]);
  const [byStatus, setByStatus] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);

  // master data
  const [products, setProducts] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const canApprove = can(currentUser?.permissions, "purchase_requisition", "approve");
  const canPo = can(currentUser?.permissions, "purchase_order", "create");   // P15 — gabung = buat PO (hak sama dgn konversi PR)   // Sisir lanjutan gerbang peran (2026-10-21)

  useEffect(() => { loadMasters(); }, []);             // eslint-disable-line
  const [lineFilter, setLineFilter] = useState("");   // FASE L
  // UAT 24 Okt (P15) — gabung beberapa PR ke 1 PO.
  const [picked, setPicked] = useState([]);
  const [merge, setMerge] = useState(null);   // { supplier } saat modal gabung terbuka
  const [mergeKey, setMergeKey] = useState(0);
  useEffect(() => { load(); }, [statusFilter, selectedEntity, lineFilter]); // eslint-disable-line

  async function loadMasters() {
    try {
      const [p, w, s] = await Promise.all([
        axios.get(`${API}/products`).catch(() => ({ data: [] })),
        axios.get(`${API}/warehouses`).catch(() => ({ data: [] })),
        axios.get(`${API}/suppliers`).catch(() => ({ data: [] })),
      ]);
      setProducts(Array.isArray(p.data) ? p.data : (p.data?.items || []));
      setWarehouses(Array.isArray(w.data) ? w.data : (w.data?.items || []));
      setSuppliers(Array.isArray(s.data) ? s.data : (s.data?.items || []));
    } catch (e) { /* non-blocking */ }
  }

  async function load() {
    setLoading(true);
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      if (lineFilter) params.line = lineFilter;          // FASE L — disaring di server
      const res = await axios.get(`${API}/purchase-requisitions`, { params });
      setItems(res.data?.items || []);
      setByStatus(res.data?.by_status || {});
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat Purchase Requisition.");
    } finally {
      setLoading(false);
    }
  }

  function flash(msg) { setToast(msg); setTimeout(() => setToast(""), 3500); }

  // Deep-link dari Meja MD → langsung buka PR yang diklik.
  useEffect(() => {
    if (focusDoc?.focus_type === "purchase_requisition" && focusDoc.focus_id) {
      openDetail(focusDoc.focus_id);
      onClearFocus?.();
    }
  }, [focusDoc?.focus_id]); // eslint-disable-line

  async function openDetail(id) {
    try {
      const res = await axios.get(`${API}/purchase-requisitions/${id}`);
      setSelected(res.data); setView("detail");
    } catch (e) { flash(e.response?.data?.detail || "Gagal memuat detail PR."); }
  }

  const tabs = [
    { key: "", label: "Semua" },
    { key: "draft", label: "Draf" },
    { key: "pending_approval", label: "Menunggu Persetujuan" },
    { key: "approved", label: "Disetujui" },
    { key: "converted", label: "Jadi PO" },
    { key: "rejected", label: "Ditolak" },
  ];

  if (view === "detail" && selected) {
    return (
      <DetailPanel
        pr={selected} canApprove={canApprove} suppliers={suppliers} warehouses={warehouses}
        onBack={() => { setSelected(null); setView("list"); load(); }}
        onChanged={(msg) => { flash(msg); }}
        reload={openDetail}
      />
    );
  }

  const q = search.trim().toLowerCase();
  const shown = !q ? items : items.filter((pr) => [pr.number, pr.warehouse_name, ...(pr.items || []).map((it) => it.product_name)]
    .some((v) => (v || "").toLowerCase().includes(q)));
  const total = Object.values(byStatus).reduce((a, b) => a + (b || 0), 0) || items.length;

  return (
    <div data-testid="purchase-requisitions-view" className="view-container">
      {toast && <div className="notice-bar success" data-testid="pr-toast"><span>{toast}</span><button onClick={() => setToast("")}>×</button></div>}
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="pr-error" />

      <PageHeader icon={ClipboardList} title={<span data-testid="pr-title">Permintaan Pembelian (PR)</span>}
        subtitle="Kebutuhan barang dari gudang, saran reorder, atau pesanan khusus — disetujui dulu, lalu dikonversi menjadi PO."
        actions={<>
          <button data-testid="pr-refresh" className="secondary-button" onClick={load} aria-label="Muat ulang">
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Muat ulang
          </button>
          <button data-testid="pr-create-btn" className="primary-button" onClick={() => setView("create")}>
            <Plus size={14} /> PR Baru
          </button>
        </>} />

      <MetricRow testId="pr-metrics" items={[
        { label: "Total PR", value: total, icon: ClipboardList, hint: "semua status", testId: "pr-metric-total" },
        { label: "Menunggu Persetujuan", value: byStatus.pending_approval || 0, icon: Clock, testId: "pr-metric-pending" },
        { label: "Disetujui", value: byStatus.approved || 0, icon: CheckCircle2, testId: "pr-metric-approved" },
        { label: "Jadi PO", value: byStatus.converted || 0, icon: FileText, testId: "pr-metric-converted" },
      ]} />

      <SearchBox value={search} onChange={setSearch} testId="pr-search" placeholder="Cari no. PR / barang / gudang…">
        <LineFilter value={lineFilter} onChange={setLineFilter} storageKey="purchase-requisitions"
                    allowed={currentUser?.allowed_line_codes} testId="pr-line-filter" />
      </SearchBox>
      <StatusTabs value={statusFilter} onChange={setStatusFilter} testId={(k) => `pr-tab-${k || "all"}`}
        tabs={tabs.map((t) => ({ ...t, count: t.key ? byStatus[t.key] : 0 }))} />

      <MergeSuggestions entityId={selectedEntity} reloadKey={mergeKey} canAct={canPo}
        onPick={(g) => { setPicked(g.prs.map((p) => p.pr_id)); setMerge({ supplier: g.supplier_id, label: [g.supplier_code, g.supplier_name].filter(Boolean).join(" · ") }); }} />
      {picked.length > 0 && (
        <div className="notice-bar" data-testid="pr-merge-bar">
          <span>{picked.length} PR dipilih untuk digabung.</span>
          <span className="flex gap-2">
            <button type="button" className="link-button" onClick={() => setPicked([])}>Batal pilih</button>
            <button type="button" className="primary-button !h-8" data-testid="pr-merge-open" disabled={picked.length < 2}
              onClick={() => setMerge({ supplier: "" })}>Gabung ke 1 PO</button>
          </span>
        </div>
      )}
      {merge && (
        <MergeModal prs={items.filter((p) => picked.includes(p.id))} suppliers={suppliers} presetSupplier={merge.supplier} presetSupplierLabel={merge.label}
          onClose={() => setMerge(null)}
          onDone={(res) => { setMerge(null); setPicked([]); setMergeKey((k) => k + 1);
            flash(`${res.po?.po_number} dibuat dari ${(res.prs || []).map((p) => p.number).join(", ")}.`); load(); }} />
      )}

      {loading ? (
        <div data-testid="pr-loading" className="loading-state"><Loader2 size={22} className="spin" /><p>Memuat permintaan pembelian…</p></div>
      ) : shown.length === 0 ? (
        <div data-testid="pr-empty" className="empty-state">
          <ClipboardList size={30} style={{ opacity: 0.3 }} />
          <p className="font-semibold">{q || statusFilter ? "Tidak ada PR yang cocok dengan filter ini." : "Belum ada Permintaan Pembelian."}</p>
          <p className="text-sm text-muted">Klik <b>PR Baru</b> untuk mengajukan kebutuhan barang.</p>
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table" style={{ minWidth: 860 }}>
            <thead>
              <tr><th className="w-8" aria-label="Pilih untuk digabung" /><th>Nomor</th><th>Barang / Gudang</th><th>Sumber</th><th className="text-right">Estimasi</th><th>Status</th><th className="text-right">Aksi</th></tr>
            </thead>
            <tbody>
              {shown.map((pr) => (
                <tr key={pr.id} data-testid={`pr-row-${pr.id}`} className="cursor-pointer" onClick={() => openDetail(pr.id)}>
                  <td onClick={(e) => e.stopPropagation()}>
                    {canPo && canMerge(pr) && (
                      <input type="checkbox" data-testid={`pr-pick-${pr.id}`} aria-label={`Pilih ${pr.number} untuk digabung`}
                        checked={picked.includes(pr.id)}
                        onChange={() => setPicked((cur) => (cur.includes(pr.id) ? cur.filter((x) => x !== pr.id) : [...cur, pr.id]))} />
                    )}
                  </td>
                  <td><span className="font-mono font-semibold">{pr.number}</span></td>
                  <td className="max-w-[420px]">
                    <p className="truncate font-medium">{pr.items?.[0]?.product_name || "-"}{pr.items?.length > 1 ? ` +${pr.items.length - 1}` : ""}</p>
                    <p className="text-xs text-muted">{pr.warehouse_name || "—"}</p>
                  </td>
                  <td><span className="feature-badge">{SOURCE_LABEL[pr.source] || String(pr.source || "—").replace(/_/g, " ")}</span></td>
                  <td className="text-right font-semibold tabular-nums">{formatCurrency(pr.total_est_amount)}</td>
                  <td>
                    <StatusPill status={pr.status} />
                    {/* UAT 24 Okt (audit UI tahap 2) — G4-12: status PR "Disetujui" bisa sudah sebagian jadi PO
                        (PR baru "Jadi PO" bila SEMUA baris terealisasi) — nomor PO ditampilkan supaya tidak menebak. */}
                    {pr.status === "approved" && pr.realization_status === "partially_realized" && (
                      <p className="mt-0.5 text-[11px] text-[#8C4A00]" data-testid={`pr-partial-${pr.id}`}>sebagian sudah jadi PO</p>
                    )}
                    {pr.po_number && ["approved", "converted"].includes(pr.status) && (
                      <p className="mt-0.5 text-[11px] text-[#6B6B73]" data-testid={`pr-po-number-${pr.id}`}>{pr.po_number}</p>
                    )}
                  </td>
                  <td className="text-right" onClick={(e) => e.stopPropagation()}>
                    <button data-testid={`pr-open-${pr.id}`} className="link-button" onClick={() => openDetail(pr.id)}>Detail →</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Fase 3 · P5 (L-03) — "PR Baru" dulu menggantikan seluruh halaman; kini pop-up baku di atas daftar. */}
      {view === "create" && (
        <PrCreateModal
          products={products} warehouses={warehouses} suppliers={suppliers}
          selectedEntity={selectedEntity}
          onCancel={() => setView("list")}
          onCreated={(pr) => { flash(`${pr.number} dibuat.`); setView("list"); load(); }}
        />
      )}
    </div>
  );
}

