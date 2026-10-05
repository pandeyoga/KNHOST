/**
 * ContractsView (FASE D/E · PS-06 · D-05/D-07/D-09)
 * Master **Kontrak Mitra & Supplier** (`supplier_contracts`):
 *   tarif basis bebas (pick/kg/meter/yard/roll/lumpsum/formula custom) + biaya tambahan,
 *   susut standar & toleransi selisih per mitra, masa berlaku, MOQ & lead time.
 * FASE G-0: form **Kebijakan Makloon** dihapus dari sini — tombolnya kini mengantar
 * ke Pusat Pengaturan (kelompok "Produksi & Makloon") supaya hanya ada satu editor.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { FileText, Plus, RefreshCw, Route, Search, Settings2, Trash2, Beaker, ArrowLeftRight, X } from "lucide-react";
import ErrorNotice from "../../../components/ErrorNotice";
import EntityBadge from "../../../components/EntityBadge";
import { openRnd } from "../../rnd/rndDeepLink";
import { openTrace } from "../../documents/trace/traceDeepLink";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import ContractFormModal from "./ContractFormModal";
import { StatusTabs } from "../../../components/ListControls";
import InternalPriceBulkPanel from "../../interco_prices/InternalPriceBulkPanel";
import { entitiesFromSummary, InternalPriceSummary } from "../../interco_prices/InternalPricesView";
import { internalPriceAccess, internalPriceSummary } from "../../interco_prices/internalPriceApi";
import { openConfig } from "../../settings/config/configDeepLink";
import {
  CONTRACT_STATUS_META, contractStats, deleteContract, FALLBACK_BASIS_LABELS,
  listContracts, setContractStatus,
} from "../makloon/makloonApi";

const TYPE_FILTERS = [
  { key: "", label: "Semua" },
  { key: "makloon", label: "Kontrak Makloon" },
  { key: "purchase", label: "Kontrak Pembelian" },
  { key: "internal", label: "Harga Internal" },
];

export default function ContractsView({ currentUser, selectedEntity }) {
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [icSummary, setIcSummary] = useState(null);
  const [icAccess, setIcAccess] = useState({});
  const [bulkPair, setBulkPair] = useState(null);

  const canManage = ["admin", "manager"].includes(currentUser?.role);

  const loadIc = useCallback(async () => {
    try {
      const a = await internalPriceAccess();
      setIcAccess(a);
      if (a.can_view) setIcSummary(await internalPriceSummary());
    } catch { setIcSummary(null); }
  }, []);
  useEffect(() => { loadIc(); }, [loadIc]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      if (type) params.contract_type = type;
      const [list, st] = await Promise.all([
        listContracts({ ...params, limit: 300 }),
        contractStats(params).catch(() => ({})),
      ]);
      setRows(Array.isArray(list) ? list : []);
      setStats(st || {});
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat kontrak.");
    } finally {
      setLoading(false);
    }
  }, [selectedEntity, type]);
  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return rows;
    return rows.filter((r) => [r.contract_number, r.partner_name, r.title, r.product_name, r.process_type]
      .some((v) => (v || "").toLowerCase().includes(term)));
  }, [rows, q]);
  const typeCount = (k) => {
    if (type) return k === type ? rows.length : undefined;
    return k ? rows.filter((r) => r.contract_type === k).length : rows.length;
  };

  const changeStatus = async (row, status) => {
    try {
      await setContractStatus(row.id, status, `Diubah dari layar kontrak oleh ${currentUser?.name || "pengguna"}`);
      await load();
    } catch (e) { setError(e.response?.data?.detail || "Gagal mengubah status kontrak."); }
  };

  const remove = async (row) => {
    try {
      await deleteContract(row.id);
      await load();
    } catch (e) { setError(e.response?.data?.detail || "Kontrak tidak bisa dihapus."); }
  };

  return (
    <div data-testid="supplier-contracts-view">
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="contracts-error" />

      <div className="section-card mb-3">
        <div className="section-head">
          <div className="flex items-center gap-2">
            <FileText size={16} className="text-[#0058CC]" />
            <h2 data-testid="contracts-title">Kontrak Mitra & Supplier</h2>
          </div>
          <div className="flex items-center gap-2">
            <button className="secondary-button" onClick={load} data-testid="contracts-refresh"><RefreshCw size={13} /> Muat ulang</button>
            {canManage && (
              <button
                className="secondary-button"
                onClick={() => openConfig({ group: "makloon", key: "makloon.contract_mode" })}
                data-testid="contracts-policy-button"
                title="Kebijakan makloon kini diatur di Pusat Pengaturan"
              >
                <Settings2 size={13} /> Kebijakan Makloon
              </button>
            )}
            {icAccess.can_view && (
              <button className="secondary-button" onClick={() => setBulkPair({})} data-testid="contracts-internal-bulk-button">
                <ArrowLeftRight size={13} /> Isi massal harga internal
                {icSummary?.missing_total > 0 && <span data-testid="contracts-internal-missing" className="ml-1 rounded-full bg-[#FFF4E0] px-1.5 text-[10px] font-bold text-[#8A5300]">{icSummary.missing_total}</span>}
              </button>
            )}
            {canManage && (
              <button className="primary-button" onClick={() => { setEditing(null); setShowForm(true); }} data-testid="contracts-create-button">
                <Plus size={13} /> Kontrak Baru
              </button>
            )}
          </div>
        </div>
        <div className="section-body space-y-2.5">
          <div className="grid grid-cols-2 gap-2 md:grid-cols-5" data-testid="contracts-stats">
            <Kpi label="Total kontrak" value={String(stats.total ?? 0)} />
            <Kpi label="Aktif" value={String(stats.active ?? 0)} tone="#1B7F4B" />
            <Kpi label="Makloon" value={String(stats.makloon ?? 0)} tone="#0058CC" />
            <Kpi label="Pembelian" value={String(stats.purchase ?? 0)} tone="#6B219A" />
            <Kpi label="Berakhir ≤ 30 hari" value={String(stats.expiring_30d ?? 0)} tone="#B26A00" />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative max-w-sm flex-1">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#9A9BA3]" />
              <input data-testid="contracts-search" value={q} onChange={(e) => setQ(e.target.value)}
                className="field !pl-8" placeholder="Cari nomor / mitra / produk / proses…" />
            </div>
            <div className="flex flex-wrap gap-1.5" data-testid="contracts-filters">
              <StatusTabs value={type} onChange={setType} testIdPrefix="contracts-filter"
                tabs={TYPE_FILTERS.map((f) => ({ ...f, testKey: f.key || "all", count: typeCount(f.key) }))} />
            </div>
          </div>
        </div>
      </div>

      <div className="section-card">
        <div className="grid grid-cols-[130px_1.4fr_1fr_150px_110px_120px] px-3 py-1.5 bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73] border-b border-[#EFF0F2]">
          <span>No. Kontrak</span><span>Mitra / Proses</span><span>Produk</span><span>Tarif & basis</span><span>Susut / Tol.</span><span className="text-right">Status</span>
        </div>
        {loading ? (
          <div className="py-10 text-center text-[12px] text-[#6B6B73]">Memuat kontrak…</div>
        ) : filtered.length === 0 ? (
          <div className="py-12 text-center text-[12px] text-[#6B6B73]" data-testid="contracts-empty">
            <FileText className="mx-auto mb-2 text-gray-300" size={28} />
            <p>Belum ada kontrak. Buat kontrak agar tarif, susut & toleransi mitra terkunci per dokumen.</p>
          </div>
        ) : (
          <div className="divide-y divide-[#EFF0F2] max-h-[620px] overflow-y-auto">
            {filtered.map((c) => {
              const meta = CONTRACT_STATUS_META[c.status] || CONTRACT_STATUS_META.draft;
              return (
                <div key={c.id} data-testid={`contract-row-${c.id}`}
                  className="grid grid-cols-[130px_1.4fr_1fr_150px_110px_120px] items-center px-3 py-2.5 hover:bg-[#FAFBFC]">
                  <button className="text-left text-[11.5px] font-bold text-[#0058CC]"
                    data-testid={`contract-open-${c.id}`}
                    onClick={() => { setEditing(c); setShowForm(true); }}>{c.contract_number}</button>
                  <div className="min-w-0">
                    <p className="truncate text-[12px] font-semibold">{c.partner_name || "—"}</p>
                    <p className="truncate text-[10.5px] text-[#6B6B73] flex items-center gap-1">
                      <EntityBadge entityId={c.entity_id} /> {c.contract_type === "makloon" ? c.process_type : c.contract_type === "internal" ? "harga internal" : "pembelian"}
                      {c.title ? ` · ${c.title}` : ""}
                    </p>
                    {/* FASE F — jawaban atas "harga ini dari mana?": nomor permintaan sample
                        asal harga, bisa diklik ke layar R&D. */}
                    {c.sample_ref && (
                      <button data-testid={`contract-sample-ref-${c.id}`}
                        title="Buka permintaan sample yang menjadi asal harga kontrak ini"
                        className="mt-0.5 inline-flex items-center gap-1 rounded border border-[#D9E8FF] bg-[#F2F7FF] px-1.5 py-[1px] text-[10px] font-bold text-[#0058CC] hover:border-[#0058CC]"
                        onClick={(e) => {
                          e.stopPropagation();
                          openRnd({ view: "rnd-samples", sampleNumber: c.sample_ref });
                        }}>
                        <Beaker size={10} /> asal harga: {c.sample_ref}
                      </button>
                    )}
                  </div>
                  <span className="truncate text-[11.5px]">{c.product_name || "Semua produk"}</span>
                  <div>
                    <p className="text-[11.5px] font-semibold tabular-nums">{formatCurrency(c.tariff_rate || 0)}</p>
                    <p className="text-[10px] text-[#6B6B73]">{FALLBACK_BASIS_LABELS[c.tariff_basis] || c.tariff_basis}</p>
                  </div>
                  <span className="text-[11.5px] tabular-nums">
                    {formatQty(c.shrinkage_pct || 0)}% / {c.tolerance_pct == null ? "kebijakan" : `${formatQty(c.tolerance_pct)}%`}
                  </span>
                  <div className="flex items-center justify-end gap-1.5">
                    <span className={`status-pill ${meta.cls}`}>{meta.label}</span>
                    {/* FASE G-4/F (US12) — auditor: satu klik ke rantai surat
                        (kontrak → permintaan sample → spesifikasi → PO/tagihan). */}
                    <button className="icon-button text-[#0058CC]" title="Buka Jejak Dokumen kontrak ini"
                      data-testid={`contract-trace-${c.id}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        openTrace({ docType: "supplier_contract", docId: c.id, number: c.contract_number });
                      }}><Route size={13} /></button>
                    {canManage && c.status === "active" && (
                      <button className="secondary-button !py-1 !px-2 text-[10.5px]"
                        data-testid={`contract-terminate-${c.id}`} onClick={() => changeStatus(c, "terminated")}>Hentikan</button>
                    )}
                    {canManage && c.status !== "active" && (
                      <button className="secondary-button !py-1 !px-2 text-[10.5px]"
                        data-testid={`contract-activate-${c.id}`} onClick={() => changeStatus(c, "active")}>Aktifkan</button>
                    )}
                    {canManage && (
                      <button className="icon-button text-red-400 hover:text-red-600" title="Hapus kontrak"
                        data-testid={`contract-delete-${c.id}`} onClick={() => remove(c)}><Trash2 size={13} /></button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {showForm && (
        <ContractFormModal contract={editing} selectedEntity={selectedEntity}
          onClose={() => { setShowForm(false); setEditing(null); }}
          onSaved={() => { setShowForm(false); setEditing(null); load(); }}
          onError={setError} />
      )}
      {bulkPair && (
        <div className="modal-overlay" data-testid="contracts-internal-bulk-modal" onClick={(e) => { if (e.target === e.currentTarget) setBulkPair(null); }}>
          <div className="modal-card" style={{ maxWidth: 980, maxHeight: "92vh", overflowY: "auto" }} onClick={(e) => e.stopPropagation()}>
            <div className="mb-2 flex items-start justify-between gap-2">
              <div><p className="modal-title">Isi massal harga internal</p>
                <p className="modal-subtitle">Barang ber-stok yang belum punya harga internal untuk pasangan PT. Penetap: MD, Finance, Admin.</p></div>
              <button className="icon-button" data-testid="contracts-internal-bulk-close" onClick={() => setBulkPair(null)}><X size={15} /></button>
            </div>
            <InternalPriceSummary summary={icSummary} onPick={(p) => setBulkPair({ seller: p.seller_entity_id, buyer: p.buyer_entity_id })} />
            <div className="mt-3">
              {entitiesFromSummary(icSummary).length > 1 && (
                <InternalPriceBulkPanel key={`${bulkPair.seller}-${bulkPair.buyer}`} entities={entitiesFromSummary(icSummary)} initial={bulkPair}
                  canSet={!!icAccess.can_set} onSaved={() => { loadIc(); load(); }} />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Kpi({ label, value, tone = "#1C1C1E" }) {
  return (
    <div className="rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-2">
      <p className="text-[9.5px] font-bold uppercase text-[#8E8E93]">{label}</p>
      <p className="text-[14px] font-bold tabular-nums leading-tight" style={{ color: tone }}>{value}</p>
    </div>
  );
}
