/**
 * ContractsView (FASE D/E · PS-06 · D-05/D-07/D-09)
 * Master **Kontrak Mitra & Supplier** (`supplier_contracts`):
 *   tarif basis bebas (pick/kg/meter/yard/roll/lumpsum/formula custom) + biaya tambahan,
 *   susut standar & toleransi selisih per mitra, masa berlaku, MOQ & lead time.
 * FASE G-0: form **Kebijakan Makloon** dihapus dari sini — tombolnya kini mengantar
 * ke Pusat Pengaturan (kelompok "Produksi & Makloon") supaya hanya ada satu editor.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { FileText, Plus, RefreshCw, Route, Search, Settings2, Trash2, Beaker, ArrowLeftRight } from "lucide-react";
import ErrorNotice from "../../../components/ErrorNotice";
import LinkCard from "../../../components/LinkCard";
import { useAppNav } from "../../../context/AppNavContext";
import EntityBadge from "../../../components/EntityBadge";
import { openRnd } from "../../rnd/rndDeepLink";
import { openTrace } from "../../documents/trace/traceDeepLink";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import ContractFormModal from "./ContractFormModal";
import ContractToleranceInline from "./ContractToleranceInline";
import { can } from "../../../config/roles";
import { StatusTabs } from "../../../components/ListControls";
import usePagedRows from "../../../hooks/usePagedRows";
import useProcessTypes from "../../../hooks/useProcessTypes";
import { internalPriceAccess, internalPriceSummary } from "../../interco_prices/internalPriceApi";
import { openConfig } from "../../settings/config/configDeepLink";
import { askConfirm, askReason } from "../../../services/confirmService";
import {
  CONTRACT_STATUS_META, contractStats, deleteContract, FALLBACK_BASIS_LABELS,
  listContracts, setContractStatus,
} from "../makloon/makloonApi";

// Kolom tabel kontrak — dipakai kepala & baris; wadah gulir samping (min-w) untuk HP.
const COLS = "grid-cols-[130px_minmax(200px,1.4fr)_minmax(140px,1fr)_150px_120px_minmax(260px,auto)]";

const TYPE_FILTERS = [
  { key: "", label: "Semua" },
  { key: "makloon", label: "Kontrak Makloon" },
  { key: "purchase", label: "Kontrak Pembelian" },
  // Fase 3 · P5 — D-23: saringan ini DIPERTAHANKAN (hanya untuk melihat/menghentikan kontrak harga internal yang
  // sudah ada — layar Harga Internal Antar-PT hanya mengisi yang belum berharga); pengisian lewat tautan di bawah.
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
  const { labelOf: processLabel } = useProcessTypes();
  const { canOpen } = useAppNav();

  // Sisir gerbang peran (2026-10-20): buat/ubah status/hapus = supplier_contract.create/update/delete;
  // pintasan kebijakan membuka Pusat Pengaturan (settings.view; hak ubah per setelan dari server).
  const canCreate = can(currentUser?.permissions, "supplier_contract", "create");
  const canUpdate = can(currentUser?.permissions, "supplier_contract", "update");
  const canDelete = can(currentUser?.permissions, "supplier_contract", "delete");
  const canOpenConfig = can(currentUser?.permissions, "settings", "view");

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
      // UAT 24 Okt (audit UI tahap 2) — G4-07: KPI & hitungan tab dari SELURUH kontrak
      // (tanpa filter tab); dulu tab "Kontrak Makloon" membuat KPI Pembelian jadi 0.
      const listParams = type ? { ...params, contract_type: type } : params;
      const [list, st] = await Promise.all([
        listContracts({ ...listParams, limit: 300 }),
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
  // 241+ baris → dipecah per halaman (dulu tanpa paginasi).
  const { pageRows, pager } = usePagedRows(filtered, { pageSize: 50, testId: "contracts-pager" });
  // Hitungan tab dari statistik server (bukan jumlah baris termuat) — tetap sama di semua tab.
  const typeCount = (k) => {
    const v = k ? stats[k] : stats.total;
    return typeof v === "number" ? v : undefined;
  };

  // UAT 24 Okt (audit UI tahap 2) — G4-01: Hentikan/Aktifkan meminta alasan pengguna
  // (dikirim ke server & tercatat di riwayat status), hapus meminta konfirmasi bahaya.
  const changeStatus = async (row, status) => {
    const stopping = status === "terminated";
    const reason = await askReason({
      title: `${stopping ? "Hentikan" : "Aktifkan"} kontrak ${row.contract_number}?`,
      message: stopping
        ? `Kontrak ${row.contract_number} (${row.partner_name || "mitra"}) tidak lagi dipakai untuk order/PO baru. Dokumen yang sudah memakai kontrak ini tidak berubah.`
        : `Kontrak ${row.contract_number} (${row.partner_name || "mitra"}) akan dipakai lagi untuk order/PO baru selama masa berlakunya.`,
      reasonLabel: stopping ? "Alasan penghentian" : "Alasan pengaktifan",
      confirmLabel: stopping ? "Hentikan kontrak" : "Aktifkan kontrak",
      danger: stopping,
    });
    if (reason === null) return;
    try {
      await setContractStatus(row.id, status, reason);
      await load();
    } catch (e) { setError(e.response?.data?.detail || "Gagal mengubah status kontrak."); }
  };

  const remove = async (row) => {
    const ok = await askConfirm({
      title: `Hapus kontrak ${row.contract_number}?`,
      message: `Kontrak ${row.contract_number} (${row.partner_name || "mitra"}) dihapus permanen beserta tarif, susut & toleransinya. `
        + "Kontrak yang sudah dipakai order makloon/PO tidak bisa dihapus — hentikan saja.",
      confirmLabel: "Hapus kontrak",
      danger: true,
    });
    if (!ok) return;
    try {
      await deleteContract(row.id);
      await load();
    } catch (e) { setError(e.response?.data?.detail || "Kontrak tidak bisa dihapus."); }
  };

  return (
    <div data-testid="supplier-contracts-view">
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="contracts-error" />

      <div className="section-card mb-3">
        <div className="section-head flex-wrap gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <FileText size={16} className="shrink-0 text-[#0058CC]" />
            <h2 data-testid="contracts-title">Kontrak Mitra & Supplier</h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button className="secondary-button" onClick={load} data-testid="contracts-refresh"><RefreshCw size={13} /> Muat ulang</button>
            {canOpenConfig && (
              <button
                className="secondary-button"
                onClick={() => openConfig({ group: "makloon", key: "makloon.contract_mode" })}
                data-testid="contracts-policy-button"
                title="Kebijakan makloon kini diatur di Pusat Pengaturan"
              >
                <Settings2 size={13} /> Kebijakan Makloon
              </button>
            )}
            {canCreate && (
              <button className="primary-button" onClick={() => { setEditing(null); setShowForm(true); }} data-testid="contracts-create-button">
                <Plus size={13} /> Kontrak Baru
              </button>
            )}
          </div>
        </div>
        <div className="section-body space-y-2.5">
          <div className="grid grid-cols-2 gap-2 md:grid-cols-6" data-testid="contracts-stats">
            <Kpi label="Total kontrak" value={String(stats.total ?? 0)} />
            <Kpi label="Aktif" value={String(stats.active ?? 0)} tone="#1B7F4B" />
            <Kpi label="Makloon" value={String(stats.makloon ?? 0)} tone="#0058CC" />
            <Kpi label="Pembelian" value={String(stats.purchase ?? 0)} tone="#6B219A" />
            <Kpi label="Harga internal" value={String(stats.internal ?? 0)} tone="#0058CC" />
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
          {/* Fase 3 · P5 — D-23: pop-up "Isi massal harga internal" (ringkasan pasangan + editor massal) dulu
              menduplikasi layar Harga Internal Antar-PT. Kini satu layar; di sini tautan. Manajer & gudang (tanpa menu
              Produk & Harga) memakai tab tersembunyi `supplier-internal-prices` (diaktifkan P8) — sampai itu ringkasan
              baca-saja. Saringan "Harga Internal" tetap untuk melihat/menghentikan kontrak yang sudah ada. */}
          {icAccess.can_view && (
            <LinkCard testId="contracts-internal-link" icon={ArrowLeftRight} what="Harga internal antar-PT"
              where="Produk & Harga › Harga Internal Antar-PT"
              view={canOpen("internal-prices") ? "internal-prices" : "supplier-internal-prices"}
              label="Isi / periksa harga internal" count={icSummary?.missing_total || undefined}
              summary={icSummary ? `${icSummary.missing_total || 0} barang ber-stok belum punya harga` : null} />
          )}
        </div>
      </div>

      <div className="section-card overflow-x-auto">
        <div className="min-w-[1000px]">
        <div className={`grid ${COLS} gap-x-2 whitespace-nowrap px-3 py-1.5 bg-[#FAFBFC] text-[11px] font-bold uppercase text-[#6B6B73] border-b border-[#EFF0F2]`}>
          <span>No. Kontrak</span><span>Mitra / Proses</span><span>Produk</span><span>Tarif & basis</span><span>Susut / Toleransi</span><span className="text-right">Status & aksi</span>
        </div>
        {loading ? (
          <div className="py-10 text-center text-[12px] text-[#6B6B73]">Memuat kontrak…</div>
        ) : filtered.length === 0 ? (
          <div className="py-12 text-center text-[12px] text-[#6B6B73]" data-testid="contracts-empty">
            <FileText className="mx-auto mb-2 text-gray-300" size={28} />
            {type || q.trim() ? (
              <>
                <p>Tidak ada kontrak{type ? ` berjenis ${TYPE_FILTERS.find((f) => f.key === type)?.label.toLowerCase() || type}` : ""}{q.trim() ? ` yang cocok dengan “${q.trim()}”` : ""}.</p>
                <button className="secondary-button mx-auto mt-2 !py-1 !px-2 text-[11px]" data-testid="contracts-empty-reset"
                  onClick={() => { setType(""); setQ(""); }}>Tampilkan semua</button>
              </>
            ) : (
              <p>Belum ada kontrak. Buat kontrak agar tarif, susut & toleransi mitra terkunci per dokumen.</p>
            )}
          </div>
        ) : (
          <div className="divide-y divide-[#EFF0F2] max-h-[620px] overflow-y-auto">
            {pageRows.map((c) => {
              const meta = CONTRACT_STATUS_META[c.status] || CONTRACT_STATUS_META.draft;
              return (
                <div key={c.id} data-testid={`contract-row-${c.id}`}
                  className={`grid ${COLS} gap-x-2 items-center px-3 py-2.5 hover:bg-[#FAFBFC]`}>
                  <button className="text-left text-[11.5px] font-bold text-[#0058CC]"
                    data-testid={`contract-open-${c.id}`}
                    onClick={() => { setEditing(c); setShowForm(true); }}>{c.contract_number}</button>
                  <div className="min-w-0">
                    <p className="truncate text-[12px] font-semibold">{c.partner_name || "—"}</p>
                    <p className="truncate text-[11px] text-[#6B6B73] flex items-center gap-1">
                      <EntityBadge entityId={c.entity_id} /> {c.contract_type === "makloon" ? (processLabel(c.process_type) || "makloon") : c.contract_type === "internal" ? "harga internal" : "pembelian"}
                      {c.title ? ` · ${c.title}` : ""}
                    </p>
                    {/* FASE F — jawaban atas "harga ini dari mana?": nomor permintaan sample
                        asal harga, bisa diklik ke layar R&D. */}
                    {c.sample_ref && (
                      <button data-testid={`contract-sample-ref-${c.id}`}
                        title="Buka permintaan sample yang menjadi asal harga kontrak ini"
                        className="mt-0.5 inline-flex items-center gap-1 rounded border border-[#D9E8FF] bg-[#F2F7FF] px-1.5 py-[1px] text-[11px] font-bold text-[#0058CC] hover:border-[#0058CC]"
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
                    <p className="text-[11px] text-[#6B6B73]">{FALLBACK_BASIS_LABELS[c.tariff_basis] || c.tariff_basis}</p>
                  </div>
                  <ContractToleranceInline contract={c} onSaved={load} onError={setError}
                    canEdit={can(currentUser?.permissions, "supplier_contract", "update") && c.status !== "terminated"} />
                  <div className="flex items-center justify-end gap-1.5">
                    <span className={`status-pill ${meta.cls}`}>{meta.label}</span>
                    {/* FASE G-4/F (US12) — auditor: satu klik ke rantai surat
                        (kontrak → permintaan sample → spesifikasi → PO/tagihan). */}
                    <button className="icon-button text-[#0058CC]" title="Buka Jejak Dokumen kontrak ini" aria-label="Jejak dokumen"
                      data-testid={`contract-trace-${c.id}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        openTrace({ docType: "supplier_contract", docId: c.id, number: c.contract_number });
                      }}><Route size={13} /></button>
                    {canUpdate && c.status === "active" && (
                      <button className="secondary-button !py-1 !px-2 text-[11px]"
                        data-testid={`contract-terminate-${c.id}`} onClick={() => changeStatus(c, "terminated")}>Hentikan</button>
                    )}
                    {canUpdate && c.status !== "active" && (
                      <button className="secondary-button !py-1 !px-2 text-[11px]"
                        data-testid={`contract-activate-${c.id}`} onClick={() => changeStatus(c, "active")}>Aktifkan</button>
                    )}
                    {canDelete && (
                      <button className="icon-button text-red-400 hover:text-red-600" title="Hapus kontrak" aria-label="Hapus kontrak"
                        data-testid={`contract-delete-${c.id}`} onClick={() => remove(c)}><Trash2 size={13} /></button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
        </div>
        {!loading && filtered.length > 50 && <div className="border-t border-[#EFF0F2] px-3 py-2">{pager}</div>}
      </div>

      {showForm && (
        <ContractFormModal contract={editing} selectedEntity={selectedEntity}
          onClose={() => { setShowForm(false); setEditing(null); }}
          onSaved={() => { setShowForm(false); setEditing(null); load(); }}
          onError={setError} />
      )}
    </div>
  );
}

function Kpi({ label, value, tone = "#1C1C1E" }) {
  return (
    <div className="rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-2">
      <p className="text-[11px] font-bold uppercase text-[#8E8E93]">{label}</p>
      <p className="text-[14px] font-bold tabular-nums leading-tight" style={{ color: tone }}>{value}</p>
    </div>
  );
}
