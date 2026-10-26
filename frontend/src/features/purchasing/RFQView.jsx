import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { ClipboardList, Plus, Layers } from "lucide-react";
import { formatDate } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";
import { SearchBox } from "../../components/ListControls";
import RFQCreateModal from "./RFQCreateModal";
import RFQDetailPanel from "./RFQDetailPanel";
import DetailModal from "../../components/DetailModal";
import FilterChips from "../../components/FilterChips";
import ResponsiveTable from "../../components/ResponsiveTable";
import { can } from "../../config/roles";
import { canWriteInScope, WRITE_BLOCK_HINT } from "../../utils/writeScope";

/**
 * RFQView (Fase 6.1 — P1 Sourcing) — RFQ / Quotation.
 * Tender multi-supplier: create (PR/manual) → quote → compare → award → PO.
 */
const TABS = [
  { key: "all", label: "Semua" },
  { key: "draft", label: "Draf" },
  { key: "open", label: "Berjalan" },
  { key: "awarded", label: "Pemenang dipilih" },
  { key: "cancelled", label: "Batal" },
];

function StatusPill({ status }) {
  const map = {
    draft: ["pill-muted", "Draf"], open: ["pill-info", "Berjalan"],
    awarded: ["pill-success", "Pemenang dipilih"], cancelled: ["pill-muted", "Batal"],
  };
  const [cls, label] = map[status] || ["pill-muted", status];
  return <span className={`status-pill ${cls}`}>{label}</span>;
}

const quotedOf = (r) => (r.suppliers || []).filter((s) => s.quote_status === "quoted").length;
const RFQ_COLUMNS = [
  { key: "rfq_number", header: "Nomor", mobile: "title",
    render: (r) => <span className="font-bold text-[#0058CC] whitespace-nowrap">{r.rfq_number}</span> },
  { key: "status", header: "Status", mobile: "badge",
    render: (r) => (
      <span>
        <StatusPill status={r.status} />
        {r.status === "awarded" && (r.award?.po_numbers || []).length > 0 && (
          <span className="mt-0.5 block text-[11px] text-[#6B6B73]">PO: {(r.award?.po_numbers || []).join(", ")}</span>
        )}
      </span>
    ) },
  { key: "title", header: "Judul / Sumber", mobile: "subtitle",
    render: (r) => (
      <span className="min-w-0">
        <span className="block font-semibold">{r.title || "—"}</span>
        <span className="block text-[11px] text-[#6B6B73]">{r.source === "pr" ? `Dari ${r.pr_number}` : "Manual"} · {r.warehouse_name}</span>
      </span>
    ) },
  { key: "items", header: "Item", align: "center", priority: 2, render: (r) => (r.items || []).length },
  { key: "quotes", header: "Penawaran", align: "center", priority: 1, mobileLabel: "Supplier menawar",
    render: (r) => `${quotedOf(r)}/${(r.suppliers || []).length}` },
  { key: "created_at", header: "Dibuat", align: "right", priority: 3, render: (r) => formatDate(r.created_at) },
];

export default function RFQView({ currentUser, selectedEntity }) {
  const [rfqs, setRfqs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState("all");
  const [showCreate, setShowCreate] = useState(false);
  const [detailId, setDetailId] = useState(null);
  const [q, setQ] = useState("");

  const canCreate = can(currentUser?.permissions, "rfq", "create");   // Sisir gerbang peran (2026-10-20) — POST /rfqs
  const writable = canWriteInScope(selectedEntity);

  useEffect(() => { load(); }, [selectedEntity]); // eslint-disable-line

  async function load() {
    setLoading(true);
    try {
      const params = (selectedEntity && selectedEntity !== "all") ? { entity_id: selectedEntity } : {};
      const r = await axios.get(`${API}/rfqs`, { params });
      setRfqs(Array.isArray(r.data) ? r.data : []);
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat RFQ.");
    } finally { setLoading(false); }
  }

  function onCreated(rfq) {
    setShowCreate(false);
    setNotice(`RFQ ${rfq.rfq_number} dibuat.`);
    load();
    setDetailId(rfq.id);
  }

  const filtered = useMemo(() => {
    const t = q.trim().toLowerCase();
    return rfqs.filter((r) => (tab === "all" || r.status === tab)
      && (!t || [r.rfq_number, r.title, r.pr_number, ...(r.suppliers || []).map((s) => s.supplier_name)].some((v) => String(v || "").toLowerCase().includes(t))));
  }, [rfqs, tab, q]);
  const counts = useMemo(() => TABS.reduce((a, t) => ({
    ...a, [t.key]: t.key === "all" ? rfqs.length : rfqs.filter((r) => r.status === t.key).length,
  }), {}), [rfqs]);

  return (
    <div data-testid="rfq-view">
      {notice && <div className="notice-bar success" data-testid="rfq-notice"><span>{notice}</span><button onClick={() => setNotice("")}>×</button></div>}
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="rfq-error" />

      <div className="section-card mb-3">
        <div className="section-head flex-wrap gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <ClipboardList size={16} className="shrink-0 text-[#0058CC]" />
            <h2 data-testid="rfq-title">RFQ / Penawaran — Tender Pengadaan</h2>
          </div>
          {canCreate && (
            // UAT 24 Okt (audit UI tahap 2) — G4-05: mode "Semua badan usaha" hanya untuk melihat.
            <button data-testid="rfq-create-button" onClick={() => setShowCreate(true)} className="primary-button"
              disabled={!writable} title={writable ? undefined : WRITE_BLOCK_HINT}>
              <Plus size={13} /> Buat RFQ
            </button>
          )}
        </div>
        <div className="section-body">
          {/* Fase 3 · P5 (L-01/L-04) — status = SARINGAN (FilterChips), bukan tab; testid lama `rfq-tab-*` tetap. */}
          <FilterChips ariaLabel="Status RFQ" value={tab} onChange={setTab} chipTestId={(k) => `rfq-tab-${k}`}
            options={TABS.map((t) => ({ key: t.key, label: t.label, count: counts[t.key] }))} />
          <div className="mt-2"><SearchBox value={q} onChange={setQ} placeholder="Cari nomor / judul / PR / supplier…" testId="rfq-search" /></div>
        </div>
        {/* UAT 24 Okt (audit UI tahap 2) — G4-04 · fase 3 P5 (L-04): satu definisi kolom → tabel di desktop, kartu di
            HP 390 px (ResponsiveTable); pesan muat/kosong di luar wadah gulir. Testid baris `rfq-row-<id>` tetap. */}
        <div className="px-3 pb-3">
          <ResponsiveTable testId="rfq-list" rows={filtered} rowKey="id" loading={loading}
            rowTestId={(r) => `rfq-row-${r.id}`} onRowClick={(r) => setDetailId(r.id)} columns={RFQ_COLUMNS}
            empty={(
              <span className="block py-6 text-center text-[12px] text-[#6B6B73]" data-testid="rfq-empty">
                <Layers className="mx-auto mb-2 text-gray-300" size={28} />
                {q.trim() ? `Tidak ada RFQ yang cocok dengan “${q.trim()}”` : `Belum ada RFQ${tab !== "all" ? ` berstatus ${(TABS.find((t) => t.key === tab)?.label || "").toLowerCase()}` : ""}`}.
                {canCreate && tab === "all" && !q.trim() && <span className="mt-1 block text-[11px]">Buat RFQ dari PR disetujui atau manual untuk membandingkan harga supplier.</span>}
              </span>
            )} />
        </div>
      </div>

      <RFQCreateModal open={showCreate} selectedEntity={selectedEntity}
        onClose={() => setShowCreate(false)} onCreated={onCreated} onError={(m) => setError(m)} />

      {detailId && (
        <DetailModal onClose={() => setDetailId(null)}
          label="Rincian permintaan penawaran" testId="rfq-detail-modal">
          <RFQDetailPanel rfqId={detailId} currentUser={currentUser}
            onClose={() => setDetailId(null)}
            onChanged={(msg) => { if (msg) setNotice(msg); load(); }} />
        </DetailModal>
      )}
    </div>
  );
}
