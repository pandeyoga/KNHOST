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
import FocusNotice from "../../components/FocusNotice";
import useFocusDoc from "../../hooks/useFocusDoc";
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

import PagedRows from "@/components/PagedRows";
import { can } from "../../config/roles";
import ExportMenu from "../../components/ExportMenu";   // FIX-4 — tombol baku Unduh (Excel/CSV, Pusat Export)
import ListLimitNote, { metaFromHeaders } from "../wms/ListLimitNote";   // FIX-7 (B3b LST-01)

export default function MakloonOrdersView({ currentUser, selectedEntity, focusDoc, onClearFocus }) {
  const [rows, setRows] = useState([]);
  const [listMeta, setListMeta] = useState(null);   // FIX-7 — jumlah sungguhan (header server)
  const [moreBusy, setMoreBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [lineFilter, setLineFilter] = useState("");   // FASE L
  const [showCreate, setShowCreate] = useState(false);
  const [detailId, setDetailId] = useState(null);

  const canManage = can(currentUser?.permissions, "makloon_order", "create");   // Sisir gerbang peran (2026-10-20) — POST /makloon-orders

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      if (lineFilter) params.line = lineFilter;          // FASE L
      const res = await axios.get(`${API}/makloon-orders`, { params });
      const list = Array.isArray(res.data) ? res.data : [];
      setRows(list);
      setListMeta(metaFromHeaders(res, list.length));
      setError("");
    } catch (e) { setError(e.response?.data?.detail || "Gagal memuat order makloon."); }
    finally { setLoading(false); }
  }, [selectedEntity, lineFilter]);
  useEffect(() => { loadAll(); }, [loadAll]);
  // FIX-7 (B3b LST-01) — dulu 500 order terbaru tanpa tanda; kini "Muat berikutnya" dari server.
  const loadMore = async () => {
    setMoreBusy(true);
    try {
      const params = { skip: rows.length };
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      if (lineFilter) params.line = lineFilter;
      const res = await axios.get(`${API}/makloon-orders`, { params });
      const seen = new Set(rows.map((o) => o.id));
      const next = [...rows, ...(Array.isArray(res.data) ? res.data : []).filter((o) => !seen.has(o.id))];
      setRows(next);
      const m = metaFromHeaders(res, next.length);
      setListMeta(m ? { ...m, shown: next.length, skip: 0 } : null);
    } catch (e) { setError(e.response?.data?.detail || "Gagal memuat order makloon berikutnya."); } finally { setMoreBusy(false); }
  };

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((o) => (!statusFilter || o.status === statusFilter)
      && (!q || [o.mko_number, o.material_name, o.final_output_name].some((v) => (v || "").toLowerCase().includes(q))));
  }, [rows, search, statusFilter]);
  const cnt = (k) => rows.filter((o) => o.status === k).length;
  // PK-44 (IA-04) — tautan dokumen membuka rincian order makloon ber-id itu (dicek ada dulu → pemberitahuan bila tidak).
  const fokus = useFocusDoc(focusDoc, "makloon_order", async (id) => {
    await axios.get(`${API}/makloon-orders/${id}`);
    setDetailId(id);
  }, onClearFocus);

  if (detailId) {
    return (
      <>
        <ErrorNotice message={error} onDismiss={() => setError("")} testId="mko-detail-error" />
        <MakloonOrderDetailPanel mkoId={detailId} currentUser={currentUser}
          onBack={() => { setDetailId(null); setError(""); loadAll(); }} onError={setError} />
      </>
    );
  }

  return (
    <div data-testid="makloon-orders-view" className="view-container">
      <ErrorNotice message={error} onRetry={loadAll} onDismiss={() => setError("")} testId="mko-error" />
      <FocusNotice {...fokus} testId="mko-focus-notice" />
      <PageHeader icon={Boxes} title={<span data-testid="makloon-orders-title">Order Makloon (Subkontrak)</span>}
        subtitle="Kirim bahan ke mitra makloon (tenun, rajut, celup, printing…), pantau tiap langkah, lalu terima hasilnya."
        actions={canManage && <button data-testid="create-makloon-order-button" onClick={() => setShowCreate(true)} className="primary-button"><Plus size={14} /> Buat Order Makloon</button>} />
      <MetricRow testId="mko-stats" items={[
        { label: "Total order", value: listMeta?.total ?? rows.length, icon: Boxes, hint: "semua status" },
        { label: "Draf", value: cnt("draft"), icon: Clock },
        { label: "Diproses", value: cnt("in_process") + cnt("partially_received"), icon: Loader2 },
        { label: "Selesai", value: cnt("completed"), icon: CheckCircle2 },
      ]} />
      <SearchBox value={search} onChange={setSearch} testId="mko-search" placeholder="Cari no. pesanan / bahan / hasil…">
        <LineFilter value={lineFilter} onChange={setLineFilter} storageKey="makloon-orders"
                    allowed={currentUser?.allowed_line_codes} testId="mko-line-filter" />
      </SearchBox>
      <div className="kn-list-toolbar">
        <StatusTabs groupTestId="mko-filters" value={statusFilter} onChange={setStatusFilter} testId={(k) => `mko-filter-${k || "all"}`}
          tabs={FILTERS.map((f) => ({ ...f, count: f.key ? cnt(f.key) : 0 }))} />
        <ExportMenu dataset="makloon_orders" label="order-makloon" testId="mko-export" search={search}
          filters={[statusFilter && ["status", "eq", statusFilter], lineFilter && ["line_code", "eq", lineFilter]]} sort={[{ key: "created_at", dir: "desc" }]} />
      </div>

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
              <PagedRows rows={filtered} testId="makloon-orders-pager">{(o) => {
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
              }}</PagedRows>
            </tbody>
          </table>
        </div>
      )}
      {!loading && <ListLimitNote meta={listMeta} noun="order makloon" onMore={loadMore} loading={moreBusy}
        hint="saringan status & cari di layar hanya atas order yang sudah dimuat." testId="mko-limit" />}

      {showCreate && <MakloonWizard selectedEntity={selectedEntity}
        onClose={() => setShowCreate(false)}
        onSaved={(o) => { setShowCreate(false); loadAll(); if (o?.id) setDetailId(o.id); }}
        onError={setError} />}
    </div>
  );
}
