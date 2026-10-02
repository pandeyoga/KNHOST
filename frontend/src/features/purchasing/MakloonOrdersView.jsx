/**
 * MakloonOrdersView (M3) — daftar & lifecycle transaksi makloon/subkontrak.
 * GET /makloon-orders · buka detail (issue/receive/cancel) · buat order baru.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { Boxes, Plus, ArrowRight, Factory, Clock, Loader2, CheckCircle2 } from "lucide-react";
import { PageHeader, MetricRow, SearchBox, StatusTabs } from "../../components/ListPageParts";
import EntityBadge from "../../components/EntityBadge";
import ErrorNotice from "../../components/ErrorNotice";
import LineFilter from "../../components/LineFilter";   // FASE L
import { MKO_STATUS as MKO_STATUS_SHARED } from "./mkoStatus";
import { formatQty } from "../../utils/formatters";
import MakloonWizard from "./makloon/MakloonWizard";
import MakloonOrderDetailPanel from "./MakloonOrderDetailPanel";

export const MKO_STATUS = MKO_STATUS_SHARED; // re-export untuk kompatibilitas impor lama
const MODE_LABEL = { process_only: "Proses Saja", buy_process: "Beli + Proses" };
const FILTERS = [
  { key: "", label: "Semua" }, { key: "draft", label: "Draf" },
  { key: "in_process", label: "Diproses" }, { key: "partially_received", label: "Diterima sebagian" },
  { key: "completed", label: "Selesai" }, { key: "cancelled", label: "Dibatalkan" },
];

export default function MakloonOrdersView({ currentUser, selectedEntity }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [lineFilter, setLineFilter] = useState("");   // FASE L
  const [showCreate, setShowCreate] = useState(false);
  const [detailId, setDetailId] = useState(null);

  const canManage = ["admin", "manager"].includes(currentUser?.role);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      if (lineFilter) params.line = lineFilter;          // FASE L
      const res = await axios.get(`${API}/makloon-orders`, { params });
      setRows(Array.isArray(res.data) ? res.data : []);
      setError("");
    } catch (e) { setError(e.response?.data?.detail || "Gagal memuat order makloon."); }
    finally { setLoading(false); }
  }, [selectedEntity, lineFilter]);
  useEffect(() => { loadAll(); }, [loadAll]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((o) => (!statusFilter || o.status === statusFilter)
      && (!q || [o.mko_number, o.material_name, o.final_output_name].some((v) => (v || "").toLowerCase().includes(q))));
  }, [rows, search, statusFilter]);
  const cnt = (k) => rows.filter((o) => o.status === k).length;

  if (detailId) {
    return <MakloonOrderDetailPanel mkoId={detailId} currentUser={currentUser}
      onBack={() => { setDetailId(null); loadAll(); }} onError={setError} />;
  }

  return (
    <div data-testid="makloon-orders-view" className="view-container">
      <ErrorNotice message={error} onRetry={loadAll} onDismiss={() => setError("")} testId="mko-error" />
      <PageHeader icon={Boxes} title={<span data-testid="makloon-orders-title">Order Makloon (Subkontrak)</span>}
        subtitle="Kirim bahan ke mitra makloon (tenun, rajut, celup, printing…), pantau tiap langkah, lalu terima hasilnya."
        actions={canManage && <button data-testid="create-makloon-order-button" onClick={() => setShowCreate(true)} className="primary-button"><Plus size={14} /> Buat Order Makloon</button>} />
      <MetricRow testId="mko-stats" items={[
        { label: "Total order", value: rows.length, icon: Boxes, hint: "semua status" },
        { label: "Draf", value: cnt("draft"), icon: Clock },
        { label: "Diproses", value: cnt("in_process") + cnt("partially_received"), icon: Loader2 },
        { label: "Selesai", value: cnt("completed"), icon: CheckCircle2 },
      ]} />
      <SearchBox value={search} onChange={setSearch} testId="mko-search" placeholder="Cari no. pesanan / bahan / hasil…">
        <LineFilter value={lineFilter} onChange={setLineFilter} storageKey="makloon-orders"
                    allowed={currentUser?.allowed_line_codes} testId="mko-line-filter" />
      </SearchBox>
      <StatusTabs groupTestId="mko-filters" value={statusFilter} onChange={setStatusFilter} testId={(k) => `mko-filter-${k || "all"}`}
        tabs={FILTERS.map((f) => ({ ...f, count: f.key ? cnt(f.key) : 0 }))} />

      {loading ? (
        <div className="loading-state"><Loader2 size={22} className="spin" /><p>Memuat order makloon…</p></div>
      ) : filtered.length === 0 ? (
        <div className="empty-state" data-testid="mko-empty">
          <Factory size={30} style={{ opacity: 0.3 }} />
          <p className="font-semibold">{search || statusFilter ? "Tidak ada order yang cocok dengan filter ini." : "Belum ada order makloon."}</p>
          <p className="text-sm text-muted" style={{ maxWidth: 460 }}>Order makloon mencatat bahan yang dikirim ke mitra, langkah proses, estimasi hasil, dan penerimaan bertahap.</p>
          {canManage && !search && !statusFilter && <button className="primary-button" style={{ marginTop: 8 }} onClick={() => setShowCreate(true)}><Plus size={14} /> Buat Order Makloon Pertama</button>}
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table" style={{ minWidth: 900 }}>
            <thead>
              <tr><th>No. Pesanan</th><th>Bahan → Hasil</th><th>Mode</th><th>Progres</th><th>Status</th><th className="text-right">Aksi</th></tr>
            </thead>
            <tbody>
              {filtered.map((o) => {
                const st = MKO_STATUS[o.status] || MKO_STATUS.draft;
                const recv = (o.steps || []).filter((s) => s.status === "received").length;
                const total = (o.steps || []).length;
                return (
                  <tr key={o.id} data-testid={`mko-row-${o.id}`} className="cursor-pointer" onClick={() => setDetailId(o.id)}>
                    <td><span className="font-mono font-semibold">{o.mko_number}</span></td>
                    <td className="max-w-[420px]">
                      <p className="flex items-center gap-1 truncate font-medium">{o.material_name} <ArrowRight size={11} className="shrink-0 text-[#9A9BA3]" /> {o.final_output_name || "—"}</p>
                      <p className="flex items-center gap-1 truncate text-xs text-muted"><EntityBadge entityId={o.entity_id} /> <span className="tabular-nums">{formatQty(o.material_qty)} {o.material_unit}</span> · est. hasil <span className="tabular-nums">{formatQty(o.forecast?.expected_finished_qty)}</span></p>
                    </td>
                    <td className="text-muted">{MODE_LABEL[o.mode] || o.mode}</td>
                    <td className="min-w-[140px]">
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#EFF0F2]"><div className="h-full bg-[#0058CC]" style={{ width: total ? `${(recv / total) * 100}%` : "0%" }} /></div>
                      <p className="mt-0.5 text-[10.5px] text-muted tabular-nums">{recv}/{total} langkah diterima</p>
                    </td>
                    <td><span className={`status-pill ${st.cls}`}>{st.label}</span></td>
                    <td className="text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-1.5">
                        {(o.claim_summary?.needs_action || 0) > 0 && (
                          <span data-testid={`mko-claim-badge-${o.id}`} title="Klaim selisih perlu tindakan"
                            className="rounded-full bg-[#FFF4E5] px-2 py-0.5 text-[10px] font-bold text-[#B26A00]">{o.claim_summary.needs_action} klaim</span>
                        )}
                        <button data-testid={`detail-mko-${o.id}`} onClick={() => setDetailId(o.id)} className="link-button">Detail →</button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && <MakloonWizard selectedEntity={selectedEntity}
        onClose={() => setShowCreate(false)}
        onSaved={(o) => { setShowCreate(false); loadAll(); if (o?.id) setDetailId(o.id); }}
        onError={setError} />}
    </div>
  );
}
