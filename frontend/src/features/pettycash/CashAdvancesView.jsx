import { apiErrorText } from "../../utils/apiError";
import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { Wallet, Plus, RefreshCw, FileText } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";
import { SearchBox } from "../../components/ListControls";
import FilterChips from "../../components/FilterChips";
import ResponsiveTable from "../../components/ResponsiveTable";
import { MetricRow } from "../../components/ListPageParts";
import { StatusPill, fmtDate } from "./pettyCashShared";
import CashAdvanceForm from "./CashAdvanceForm";
import CashAdvanceDetail from "./CashAdvanceDetail";
import DetailModal from "../../components/DetailModal";
import { can } from "../../config/roles";

/**
 * CashAdvancesView — Form Pengajuan Dana (PD).
 * List + metrics + filter status; buat/ubah via CashAdvanceForm; detail + workflow
 * (submit → approval berjenjang → disburse) via CashAdvanceDetail.
 *
 * Fase 3 · P4 (L-03) — dulu form & rincian MENGGANTI seluruh halaman (daftar hilang). Kini daftar selalu tampil;
 * form Buat/Ubah = FormModal (di CashAdvanceForm), rincian + alur persetujuan = DetailModal framed.
 *
 * Fase 4 · R2 — layar dibuka juga dari aplikasi HP (Lainnya › Kas Kecil): daftar grid lebar tetap (tombol Detail di luar
 * layar 390 px) → `ResponsiveTable` (kartu di HP, pola sama dengan LPJ); saringan status → `FilterChips` (`ca-tab-*`
 * tetap); KPI → `MetricRow` baku (nol netral).
 */
const TABS = [
  { key: "", label: "Semua" },
  { key: "draft", label: "Draf" },
  { key: "pending_atasan", label: "Menunggu Persetujuan" },
  { key: "approved", label: "Disetujui" },
  { key: "disbursed", label: "Dicairkan" },
  { key: "settled", label: "Selesai" },
  { key: "rejected", label: "Ditolak" },
];
const PENDING = ["pending_atasan", "pending_pimpinan", "pending_finance"];

export default function CashAdvancesView({ currentUser, selectedEntity = "all", entities = [] }) {
  const [view, setView] = useState("list");     // list | create | edit | detail
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState(null);

  const canCreate = can(currentUser?.permissions, "cash_advance", "create");   // Sisir gerbang peran (2026-10-20) — POST /cash-advances

  useEffect(() => { load(); }, [selectedEntity]); // eslint-disable-line

  async function load() {
    setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      const res = await axios.get(`${API}/cash-advances`, { params });
      setRows(Array.isArray(res.data) ? res.data : []);
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat Pengajuan Dana."));
    } finally { setLoading(false); }
  }

  function flash(msg) { setToast(msg); setTimeout(() => setToast(""), 3500); }

  async function openDetail(id) {
    try {
      const res = await axios.get(`${API}/cash-advances/${id}`);
      setSelected(res.data); setView("detail");
    } catch (e) { flash(apiErrorText(e, "Gagal memuat detail.")); }
  }

  const metrics = useMemo(() => {
    const m = { total: rows.length, pending: 0, approved: 0, disbursed: 0, amount: 0 };
    rows.forEach((r) => {
      if (PENDING.includes(r.status)) m.pending += 1;
      if (r.status === "approved") m.approved += 1;
      if (r.status === "disbursed" || r.status === "settled") m.disbursed += 1;
      m.amount += Number(r.total_amount) || 0;
    });
    return m;
  }, [rows]);

  const [q, setQ] = useState("");
  const countOf = (k) => rows.filter((r) => !k || (k === "pending_atasan" ? PENDING.includes(r.status) : r.status === k)).length;
  const filtered = rows.filter((r) => {
    const t = q.trim().toLowerCase();
    if (t && ![r.number, r.purpose, r.description, r.requester_name, r.employee_name].some((v) => String(v || "").toLowerCase().includes(t))) return false;
    if (!statusFilter) return true;
    if (statusFilter === "pending_atasan") return PENDING.includes(r.status);
    return r.status === statusFilter;
  });

  const entityName = (id) => entities.find((e) => e.id === id)?.short_name
    || entities.find((e) => e.id === id)?.legal_name || id || "—";

  return (
    <div data-testid="cash-advances-view" className="grid gap-4">
      {toast && <div className="notice-bar success" data-testid="ca-toast"><span>{toast}</span><button onClick={() => setToast("")}>×</button></div>}
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="ca-error" />

      <section className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2 min-w-0">
            <Wallet size={15} className="text-[#0058CC]" />
            <span className="kicker">Kas & Petty Cash</span>
            <h2 data-testid="ca-title">Pengajuan Dana (PD)</h2>
          </div>
          <div className="flex items-center gap-2">
            <button data-testid="ca-refresh" className="icon-button" onClick={load} aria-label="Muat ulang"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
            {canCreate && <button data-testid="ca-create-btn" className="btn-primary" onClick={() => { setSelected(null); setView("create"); }}><Plus size={14} /> PD Baru</button>}
          </div>
        </div>

        <div className="section-body space-y-3">
          <MetricRow testId="ca-metrics" items={[
            { label: "Total PD", value: metrics.total, icon: Wallet, testId: "ca-metric-total" },
            { label: "Menunggu Persetujuan", value: metrics.pending, icon: Wallet, testId: "ca-metric-pending" },
            { label: "Disetujui", value: metrics.approved, icon: Wallet, testId: "ca-metric-approved" },
            { label: "Nilai Diajukan", value: formatCurrency(metrics.amount), icon: Wallet, testId: "ca-metric-amount" },
          ]} />
          <div className="flex flex-wrap items-center gap-2">
            <FilterChips ariaLabel="Saring status PD" className="min-w-0" value={statusFilter || "all"}
              onChange={(k) => setStatusFilter(k === "all" ? "" : k)}
              options={TABS.map((t) => ({ key: t.key || "all", label: t.label, count: countOf(t.key), testId: `ca-tab-${t.key || "all"}` }))} />
            <div className="w-full sm:ml-auto sm:w-auto"><SearchBox value={q} onChange={setQ} placeholder="Cari nomor, keperluan…" testId="ca-search" /></div>
          </div>
        </div>
      </section>

      <section className="section-card">
        {loading && rows.length === 0 ? (
          <div data-testid="ca-loading" className="py-10 text-center text-[12px] text-[#6B6B73]">Memuat…</div>
        ) : filtered.length === 0 ? (
          <div data-testid="ca-empty" className="py-12 text-center text-[12px] text-[#6B6B73]">
            <FileText className="mx-auto mb-2 text-gray-300" size={28} />
            <p>Belum ada Pengajuan Dana. Klik <b>PD Baru</b> untuk membuat.</p>
          </div>
        ) : (
          <ResponsiveTable testId="ca-table" rows={filtered} rowKey="id" rowTestId={(r) => `ca-row-${r.id}`}
            onRowClick={(r) => openDetail(r.id)} stickyActions
            columns={[
              { key: "number", header: "Nomor", mobile: "title",
                render: (r) => <span className="text-[11.5px] font-bold text-[#0058CC] whitespace-nowrap">{r.number}</span> },
              { key: "status", header: "Status", mobile: "badge", render: (r) => <StatusPill status={r.status} /> },
              { key: "kegiatan", header: "Kegiatan / Divisi", mobile: "subtitle",
                render: (r) => <span className="min-w-0"><span className="block text-[12px] font-semibold">{r.kegiatan || "—"}</span><span className="block text-[10.5px] text-[#9A9BA3]">{r.divisi || "—"} · {fmtDate(r.tanggal_pengajuan)}</span></span> },
              { key: "entity", header: "Entitas", priority: 2, render: (r) => entityName(r.entity_id) },
              { key: "total", header: "Total", align: "right", priority: 1,
                render: (r) => <span className="tabular-nums font-semibold">{formatCurrency(r.total_amount)}</span> },
            ]}
            actions={(r) => <button type="button" data-testid={`ca-open-${r.id}`} className="btn-secondary btn-xs" onClick={() => openDetail(r.id)}>Detail</button>}
          />
        )}
      </section>

      {(view === "create" || view === "edit") && (
        <CashAdvanceForm
          record={view === "edit" ? selected : null}
          entities={entities} selectedEntity={selectedEntity}
          onCancel={() => setView(selected && view === "edit" ? "detail" : "list")}
          onSaved={(rec, isEdit) => { flash(`${rec.number} ${isEdit ? "diperbarui" : "dibuat"}.`); setSelected(rec); setView("detail"); load(); }}
        />
      )}

      {view === "detail" && selected && (
        <DetailModal framed size="xl" label={`Rincian ${selected.number || "Pengajuan Dana"}`} testId="ca-detail-modal"
          onClose={() => { setSelected(null); setView("list"); load(); }}>
          <CashAdvanceDetail
            ca={selected} currentUser={currentUser} entities={entities}
            onEdit={(rec) => { setSelected(rec); setView("edit"); }}
            onChanged={(rec) => { setSelected(rec); load(); }}
            flash={flash}
          />
        </DetailModal>
      )}
    </div>
  );
}
