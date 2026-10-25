import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { ClipboardList, Plus, Layers } from "lucide-react";
import { formatDate } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";
import { SearchBox } from "../../components/ListControls";
import RFQCreateModal from "./RFQCreateModal";
import RFQDetailPanel from "./RFQDetailPanel";
import DetailModal from "../../components/DetailModal";
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
          <div className="tab-bar">
            {TABS.map((t) => (
              <button key={t.key} data-testid={`rfq-tab-${t.key}`} className={`tab-button ${tab === t.key ? "active" : ""}`} onClick={() => setTab(t.key)}>
                {t.label}<span className="tab-badge">{counts[t.key]}</span>
              </button>
            ))}
          </div>
          <div className="mt-2"><SearchBox value={q} onChange={setQ} placeholder="Cari nomor / judul / PR / supplier…" testId="rfq-search" /></div>
        </div>
        {/* UAT 24 Okt (audit UI tahap 2) — G4-04: pesan muat/kosong di LUAR wadah min-w (dulu
            terpotong di HP); di < 640px daftar tampil sebagai kartu (nomor, status, item, penawaran). */}
        {loading ? (
          <div className="py-10 text-center text-[12px] text-[#6B6B73]">Memuat RFQ...</div>
        ) : filtered.length === 0 ? (
          <div className="px-4 py-12 text-center text-[12px] text-[#6B6B73]" data-testid="rfq-empty">
            <Layers className="mx-auto mb-2 text-gray-300" size={28} />
            <p>{q.trim() ? `Tidak ada RFQ yang cocok dengan “${q.trim()}”` : `Belum ada RFQ${tab !== "all" ? ` berstatus ${(TABS.find((t) => t.key === tab)?.label || "").toLowerCase()}` : ""}`}.</p>
            {canCreate && tab === "all" && !q.trim() && <p className="mt-1 text-[11px]">Buat RFQ dari PR disetujui atau manual untuk membandingkan harga supplier.</p>}
          </div>
        ) : (
          <>
            <div className="hidden overflow-x-auto sm:block">
              <div className="min-w-[700px]">
                <div className="grid grid-cols-[110px_1.5fr_90px_110px_140px_100px] gap-x-2 whitespace-nowrap px-3 py-1.5 bg-[#FAFBFC] text-[11px] font-bold uppercase text-[#6B6B73] border-b border-[#EFF0F2]">
                  <span>Nomor</span><span>Judul / Sumber</span><span className="text-center">Item</span><span className="text-center" title="Supplier yang sudah menawar / diundang">Penawaran</span><span>Status</span><span className="text-right">Dibuat</span>
                </div>
                <div className="divide-y divide-[#EFF0F2] max-h-[600px] overflow-y-auto">
                  {filtered.map((r) => {
                    const quoted = (r.suppliers || []).filter((s) => s.quote_status === "quoted").length;
                    return (
                      <button key={r.id} data-testid={`rfq-row-${r.id}`} onClick={() => setDetailId(r.id)}
                              className="w-full text-left grid grid-cols-[110px_1.5fr_90px_110px_140px_100px] gap-x-2 items-center px-3 py-2.5 hover:bg-[#FAFBFC]">
                        <span className="text-[11.5px] font-bold text-[#0058CC]">{r.rfq_number}</span>
                        <div className="min-w-0">
                          <p className="text-[12px] font-semibold truncate">{r.title}</p>
                          <p className="text-[11px] text-[#6B6B73] truncate">{r.source === "pr" ? `Dari ${r.pr_number}` : "Manual"} · {r.warehouse_name}</p>
                        </div>
                        <span className="text-[12px] text-center tabular-nums">{(r.items || []).length}</span>
                        <span className="text-[12px] text-center tabular-nums">{quoted}/{(r.suppliers || []).length}</span>
                        <div><StatusPill status={r.status} />{r.status === "awarded" && <p className="text-[11px] text-[#6B6B73] mt-0.5 truncate">{(r.award?.po_numbers || []).join(", ")}</p>}</div>
                        <span className="text-[11px] text-right text-[#6B6B73]">{formatDate(r.created_at)}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
            <div className="divide-y divide-[#EFF0F2] sm:hidden" data-testid="rfq-cards">
              {filtered.map((r) => {
                const quoted = (r.suppliers || []).filter((s) => s.quote_status === "quoted").length;
                return (
                  <button key={r.id} data-testid={`rfq-card-${r.id}`} onClick={() => setDetailId(r.id)}
                    className="block w-full px-3 py-2.5 text-left hover:bg-[#FAFBFC]">
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-[12px] font-bold text-[#0058CC]">{r.rfq_number}</span>
                      <StatusPill status={r.status} />
                    </div>
                    <p className="mt-0.5 text-[12px] font-semibold">{r.title || "—"}</p>
                    <p className="text-[11px] text-[#6B6B73]">{r.source === "pr" ? `Dari ${r.pr_number}` : "Manual"} · {r.warehouse_name}</p>
                    <p className="mt-0.5 text-[11px] text-[#3C3C43]">
                      {(r.items || []).length} item · {quoted}/{(r.suppliers || []).length} supplier menawar · {formatDate(r.created_at)}
                    </p>
                    {r.status === "awarded" && (r.award?.po_numbers || []).length > 0 && (
                      <p className="text-[11px] text-[#6B6B73]">PO: {(r.award?.po_numbers || []).join(", ")}</p>
                    )}
                  </button>
                );
              })}
            </div>
          </>
        )}
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
