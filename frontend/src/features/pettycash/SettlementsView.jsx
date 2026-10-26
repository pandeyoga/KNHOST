import { apiErrorText } from "../../utils/apiError";
import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { ReceiptText, Plus, RefreshCw, FileText } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";
import { SearchBox } from "../../components/ListControls";
import DetailModal from "../../components/DetailModal";
import ResponsiveTable from "../../components/ResponsiveTable";
import { STL_STATUS, StatusPill } from "./pettyCashShared";
import SettlementForm from "./SettlementForm";
import SettlementDetail from "./SettlementDetail";
import { can } from "../../config/roles";

/**
 * SettlementsView — Laporan Pertanggungjawaban (LPJ) atas PD dicairkan.
 * List + detail (submit → approve[post GL] / reject) + cetak.
 *
 * Fase 3 · P4 (L-03/L-07) — dulu form & rincian MENGGANTI seluruh halaman; kini daftar selalu tampil, form = FormModal
 * (SettlementForm), rincian = DetailModal framed (SettlementDetail). Daftar dulu grid buatan sendiri (lebar tetap,
 * aksi di luar layar 390 px) → `ResponsiveTable` (tabel baku ≥641 px, kartu di HP; tombol Detail di kaki kartu).
 */
const TABS = [
  { key: "", label: "Semua" }, { key: "draft", label: "Draf" },
  { key: "submitted", label: "Diajukan" }, { key: "posted_to_gl", label: "Terposting" },
  { key: "rejected", label: "Ditolak" },
];

export default function SettlementsView({ currentUser, selectedEntity = "all", entities = [] }) {
  const [view, setView] = useState("list");
  const [rows, setRows] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState(null);

  const canCreate = can(currentUser?.permissions, "cash_settlement", "create");   // Sisir gerbang peran (2026-10-20) — POST /cash-advance-settlements

  useEffect(() => { load(); loadCats(); }, [selectedEntity]); // eslint-disable-line

  async function load() {
    setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      const res = await axios.get(`${API}/cash-advance-settlements`, { params });
      setRows(Array.isArray(res.data) ? res.data : []);
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat pertanggungjawaban."));
    } finally { setLoading(false); }
  }
  async function loadCats() {
    try { const r = await axios.get(`${API}/expense-categories`); setCategories(Array.isArray(r.data) ? r.data : []); } catch (e) { /* noop */ }
  }
  function flash(msg) { setToast(msg); setTimeout(() => setToast(""), 3500); }

  async function openDetail(id) {
    try { const res = await axios.get(`${API}/cash-advance-settlements/${id}`); setSelected(res.data); setView("detail"); }
    catch (e) { flash(apiErrorText(e, "Gagal memuat detail.")); }
  }

  const metrics = useMemo(() => {
    const m = { total: rows.length, submitted: 0, posted: 0, amount: 0 };
    rows.forEach((r) => {
      if (r.status === "submitted") m.submitted += 1;
      if (r.status === "posted_to_gl") m.posted += 1;
      m.amount += Number(r.total_pengeluaran) || 0;
    });
    return m;
  }, [rows]);

  const [q, setQ] = useState("");
  const countOf = (k) => rows.filter((r) => !k || r.status === k).length;
  const filtered = rows.filter((r) => (!statusFilter || r.status === statusFilter)
    && (!q.trim() || [r.number, r.advance_number, r.description, r.requester_name, r.employee_name].some((v) => String(v || "").toLowerCase().includes(q.trim().toLowerCase()))));
  const entityName = (id) => entities.find((e) => e.id === id)?.short_name || entities.find((e) => e.id === id)?.legal_name || id || "—";
  const catLabels = useMemo(() => Object.fromEntries(categories.map((c) => [c.code, c.label])), [categories]);

  return (
    <div data-testid="settlements-view" className="grid gap-4">
      {toast && <div className="notice-bar success" data-testid="stl-toast"><span>{toast}</span><button onClick={() => setToast("")}>×</button></div>}
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="stl-error" />

      <section className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2 min-w-0">
            <ReceiptText size={15} className="text-[#0058CC]" />
            <span className="kicker">Kas & Petty Cash</span>
            <h2 data-testid="stl-title">Pertanggungjawaban (LPJ)</h2>
          </div>
          <div className="flex items-center gap-2">
            <button data-testid="stl-refresh" className="icon-button" onClick={load} aria-label="Muat ulang"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
            {canCreate && <button data-testid="stl-create-btn" className="btn-primary" onClick={() => setView("create")}><Plus size={14} /> LPJ Baru</button>}
          </div>
        </div>

        <section data-testid="stl-metrics" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 p-3">
          <Metric label="Total LPJ" value={metrics.total} tone="rgba(0,122,255,.12)" testId="stl-metric-total" />
          <Metric label="Diajukan" value={metrics.submitted} tone="rgba(255,149,0,.16)" testId="stl-metric-submitted" />
          <Metric label="Terposting GL" value={metrics.posted} tone="rgba(52,199,89,.15)" testId="stl-metric-posted" />
          <Metric label="Total Pengeluaran" value={formatCurrency(metrics.amount)} tone="rgba(0,122,255,.10)" testId="stl-metric-amount" money />
        </section>

        <div className="flex flex-wrap gap-1.5 px-3 pb-3">
          {TABS.map((t) => (<button key={t.key || "all"} data-testid={`stl-tab-${t.key || "all"}`} className={`tab-button ${statusFilter === t.key ? "active" : ""}`} onClick={() => setStatusFilter(t.key)}>{t.label}<span className="tab-badge">{countOf(t.key)}</span></button>))}
          <div className="ml-auto"><SearchBox value={q} onChange={setQ} placeholder="Cari nomor, PD, pemohon…" testId="stl-search" /></div>
        </div>
      </section>

      <section className="section-card">
        {loading && rows.length === 0 ? (
          <div data-testid="stl-loading" className="py-10 text-center text-[12px] text-[#6B6B73]">Memuat…</div>
        ) : filtered.length === 0 ? (
          <div data-testid="stl-empty" className="py-12 text-center text-[12px] text-[#6B6B73]"><FileText className="mx-auto mb-2 text-gray-300" size={28} /><p>Belum ada pertanggungjawaban. Klik <b>LPJ Baru</b>.</p></div>
        ) : (
          <ResponsiveTable testId="stl-table" rows={filtered} rowKey="id" rowTestId={(r) => `stl-row-${r.id}`}
            onRowClick={(r) => openDetail(r.id)} stickyActions
            columns={[
              { key: "number", header: "Nomor", mobile: "title",
                render: (r) => <span className="text-[11.5px] font-bold text-[#0058CC] whitespace-nowrap">{r.number}</span> },
              { key: "status", header: "Status", mobile: "badge", render: (r) => <StatusPill status={r.status} map={STL_STATUS} /> },
              { key: "ref", header: "Ref PD / Divisi", mobile: "subtitle",
                render: (r) => <span className="min-w-0"><span className="block text-[12px] font-semibold">{r.cash_advance_number || "—"}</span><span className="block text-[10.5px] text-[#9A9BA3]">{r.divisi || "—"} · {r.periode || "—"}</span></span> },
              { key: "entity", header: "Entitas", priority: 2, render: (r) => entityName(r.entity_id) },
              { key: "total", header: "Pengeluaran", align: "right", priority: 1,
                render: (r) => <span className="tabular-nums font-semibold">{formatCurrency(r.total_pengeluaran)}</span> },
            ]}
            actions={(r) => <button data-testid={`stl-open-${r.id}`} className="btn-secondary btn-xs" onClick={() => openDetail(r.id)}>Detail</button>}
          />
        )}
      </section>

      {view === "create" && (
        <SettlementForm categories={categories} selectedEntity={selectedEntity}
          onCancel={() => setView("list")}
          onSaved={(rec) => { flash(`${rec.number} dibuat.`); setSelected(rec); setView("detail"); load(); }} />
      )}

      {view === "detail" && selected && (
        <DetailModal framed size="xl" label={`Rincian ${selected.number || "LPJ"}`} testId="stl-detail-modal"
          onClose={() => { setSelected(null); setView("list"); load(); }}>
          <SettlementDetail stl={selected} currentUser={currentUser} entities={entities} catLabels={catLabels}
            onChanged={(rec) => { setSelected(rec); load(); }} flash={flash} />
        </DetailModal>
      )}
    </div>
  );
}

function Metric({ label, value, tone, testId, money }) {
  return (<div data-testid={testId} className="metric-card"><div className="metric-icon" style={{ background: tone }}><ReceiptText size={16} className="text-[#1C1C1E]" /></div><div className="min-w-0"><p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p><p className={`${money ? "text-[15px]" : "text-[17px]"} font-bold tabular-nums truncate`}>{value}</p></div></div>);
}
