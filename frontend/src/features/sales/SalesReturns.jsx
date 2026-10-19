/**
 * Sub-fase 1.11 — Returns & Barang Sisa (SalesReturns)
 *
 * View mandiri untuk mengelola retur dari customer:
 * - Daftar return dengan filter status/tipe
 * - Create return (dari SO yang sudah confirmed/done)
 * - Detail return (items, attachments)
 * - Approve / Reject (manager/admin)
 * - Upload bukti foto
 */
import { useState, useEffect, useCallback, useMemo } from "react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import LineFilter from "../../components/LineFilter";   // FASE L
import PaginationBar from "../../components/PaginationBar";
import { usePagedList } from "../../hooks/usePagedList";
import { CheckCircle2, Loader2, Plus, RotateCcw, Search, X, AlertCircle, ArrowRight, Map } from "lucide-react";
import { ReturnStatusPill, ReturnTypeBadge, fmtDate } from "./ReturnShared";
import { formatCurrency } from "../../utils/formatters";
import { resolveDeepLinkTarget } from "../../config/navigationConfig";
import ReturnDetail from "./ReturnDetail";
import CreateReturnForm from "./CreateReturnForm";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";

// L08 LN-080-T04 — status & tipe adalah SARINGAN (dropdown), bukan deretan tab.
const STATUS_OPTIONS = [
  ["all", "Semua status"], ["draft", "1 · Draf"], ["pending_approval", "2 · Menunggu ACC"],
  ["approved", "3 · Disetujui"], ["inspecting", "4 · Inspeksi"], ["inspected", "5 · Siap Diselesaikan"],
  ["refund_settled", "Hasil · Refund"], ["credit_settled", "Hasil · Store Credit"], ["nego_settled", "Hasil · Nego"],
  ["rejected", "Hasil · Ditolak"], ["cancelled", "Hasil · Dibatalkan"],
];
const TYPE_OPTIONS = [
  ["all", "Semua tipe"], ["retur", "Retur"], ["bs", "Barang Sisa (BS)"],
  ["penggantian", "Penggantian"], ["komplain", "Komplain"], ["garansi", "Garansi"],
];

// FASE P6 — kolom Unduh CSV (mengikuti kolom tabel retur jual).
import { qtyDualCsvColumns } from "../../utils/qtyDualCsv";   // FASE U — dua satuan di CSV

const CSV_COLUMNS = [
  { key: "number", header: "Nomor Retur" },
  { key: "order_number", header: "No. Pesanan" },
  { key: "customer_name", header: "Pelanggan" },
  { key: "return_type", header: "Tipe" },
  { key: "status", header: "Status" },
  { header: "Jumlah Item", type: "int", get: (r) => r.items?.length || 0 },
  // FASE U — dua satuan retur: gulungan yang benar-benar dikembalikan + ukurannya.
  ...qtyDualCsvColumns({ rollHeader: "Roll Retur", measureHeader: "Jumlah Retur" }),
  { key: "credit_note_number", header: "Nota Kredit" },
  { key: "created_at", header: "Dibuat", type: "date" },
];


// ─── Main component ─────────────────────────────────────────────────────────
export default function SalesReturns({ currentUser, onNavigate, focusDoc, onClearFocus }) {
  const [filterStatus, setFilterStatus] = useState("all");
  const [returnType, setReturnType]   = useState("all");   // UI/UX 2026-06 — saring per tipe
  const [search, setSearch]         = useState("");
  const [selected, setSelected]     = useState(null);  // detail panel
  const [showCreate, setShowCreate] = useState(false);
  const [orders, setOrders]         = useState([]);
  const [notice, setNotice]         = useState(null);
  const [error, setError]           = useState(null);
  // P2 — lencana & kartu ringkasan dari AGREGAT server, bukan dari isi halaman.
  const [counts, setCounts]         = useState({});

  const token = localStorage.getItem("kn_token") || "";

  // P2 — daftar retur jual dipaginasi di server (?page/?page_size/?q/?status).
  // Sebelumnya seluruh retur (cap 500) ditarik sekaligus lalu disaring di peramban.
  const [lineFilter, setLineFilter] = useState("");   // FASE L
  const params = useMemo(
    () => ({ ...(filterStatus === "all" ? {} : { status: filterStatus }),
             ...(returnType === "all" ? {} : { return_type: returnType }),
             ...(lineFilter ? { line: lineFilter } : {}) }),
    [filterStatus, returnType, lineFilter]);
  const paged = usePagedList("/sales-returns", { params, search, pageSize: 20 });
  const returns = paged.items;
  const loading = paged.loading;

  // Hitungan memakai saringan yang sama dengan daftar (tipe, lini, cari) — status tidak, karena
  // hitungan inilah yang menjelaskan sebaran status di dalam cakupan saringan.
  const loadCounts = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/sales-returns/status-counts`, { params: {
        ...(returnType === "all" ? {} : { return_type: returnType }),
        ...(lineFilter ? { line: lineFilter } : {}), ...(search ? { q: search } : {}) } });
      setCounts(res.data || {});
    } catch { /* lencana bukan alasan menggagalkan layar */ }
  }, [returnType, lineFilter, search]);

  const load = useCallback(() => { paged.refresh(); loadCounts(); },
    [paged.refresh, loadCounts]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { loadCounts(); }, [loadCounts]);

  // Deep-link dari Meja Admin Sales: saring tabel ke nomor retur + buka detailnya.
  useEffect(() => {
    if (focusDoc?.focus_type !== "sales_return" || !focusDoc.focus_id) return;
    setFilterStatus("all");
    if (focusDoc.number) setSearch(`"${focusDoc.number}"`);
    axios.get(`${API}/sales-returns/${focusDoc.focus_id}`).then((r) => setSelected(r.data)).catch(() => {});
    onClearFocus?.();
  }, [focusDoc?.focus_id]); // eslint-disable-line

  // Load eligible orders for create form
  async function loadOrders() {
    try {
      const res = await axios.get(`${API}/sales-orders`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const all = res.data?.items || res.data || [];
      const eligible = all.filter(o =>
        ["confirmed","partially_picked","picked","partially_shipped","shipped","done"].includes(o.status)
      );
      setOrders(eligible);
    } catch (_) {}
  }

  // Penyaringan status & pencarian sudah dilakukan SERVER; daftar dipakai apa adanya.
  const filtered = returns;

  const canApprove = ["admin", "manager"].includes(currentUser?.role);
  const cnt = (s) => Number(counts[s] || 0);
  const rTotal = Number(counts.all || 0);
  const scopeParts = [returnType !== "all" && `Tipe: ${TYPE_OPTIONS.find(([v]) => v === returnType)?.[1]}`,
    lineFilter && `Lini: ${lineFilter}`, search && `Cari: "${search}"`].filter(Boolean);
  const scopeLabel = scopeParts.length ? `Cakupan: ${scopeParts.join(" · ")}` : "Cakupan: semua retur yang boleh Anda lihat";

  // ─── lifecycle actions (R1 state machine) ─────────────────────────────────
  async function handleApprove(ret) {
    try {
      const res = await axios.post(`${API}/sales-returns/${ret.id}/approve`, { notes: "" });
      setNotice(`${ret.number} disetujui. Lanjut ke inspeksi.`);
      setSelected(res.data); load();
    } catch (e) {
      setError("Gagal approve: " + (e.response?.data?.detail || e.message));
    }
  }

  async function handleStartInspect(ret) {
    try {
      const res = await axios.post(`${API}/sales-returns/${ret.id}/inspect/start`, {});
      setNotice(`Inspeksi ${ret.number} dimulai.`);
      setSelected(res.data); load();
    } catch (e) {
      setError("Gagal mulai inspeksi: " + (e.response?.data?.detail || e.message));
    }
  }

  async function handleCompleteInspect(ret, inspections, notes) {
    try {
      const res = await axios.post(`${API}/sales-returns/${ret.id}/inspect/complete`,
        { inspections, notes: notes || "" });
      setNotice(`Inspeksi ${ret.number} selesai. Pilih outcome untuk menyelesaikan.`);
      setSelected(res.data); load();
    } catch (e) {
      setError("Gagal simpan inspeksi: " + (e.response?.data?.detail || e.message));
    }
  }

  async function handleSettle(ret, outcome, itemDecisions, notes, returnWarehouseId, refundAccountCode, decisionNote, payout) {
    try {
      const body = { outcome, item_decisions: itemDecisions || [], notes: notes || "", decision_note: decisionNote || "", payout: payout || "" };
      if (returnWarehouseId) body.return_warehouse_id = returnWarehouseId;
      if (refundAccountCode) body.refund_account_code = refundAccountCode;
      const res = await axios.post(`${API}/sales-returns/${ret.id}/settle`, body);
      const st = res.data?.settlement || {};
      const cashMsg = st.cash_txn_number ? ` · refund tunai ${st.cash_txn_number}` : "";
      setNotice(`${ret.number} diselesaikan (${outcome})${cashMsg}.`);
      setSelected(res.data); load();
    } catch (e) {
      setError("Gagal settle: " + (e.response?.data?.detail || e.message));
    }
  }

  async function handleReject(ret, reason) {
    try {
      const res = await axios.post(`${API}/sales-returns/${ret.id}/reject`, { notes: reason });
      setNotice(`${ret.number} ditolak.`);
      setSelected(res.data); load();
    } catch (e) {
      setError("Gagal reject: " + (e.response?.data?.detail || e.message));
    }
  }

  async function handleReverse(ret, reason) {
    // R5.4 — reversal/koreksi retur settled (lempar error agar modal bisa tampilkan pesan).
    const res = await axios.post(`${API}/sales-returns/${ret.id}/reverse`, { notes: reason });
    const summ = res.data?._reversal_summary || {};
    setNotice(`${ret.number} dibatalkan (reversal) · ${summ.reversal_jes || 0} jurnal balik, ${summ.rolls_removed || 0} roll dihapus.`);
    setSelected(res.data); load();
    return res.data;
  }

  async function handleSubmit(ret) {
    try {
      const res = await axios.post(`${API}/sales-returns/${ret.id}/submit`, {});
      setNotice(`${ret.number} dikirim untuk approval.`);
      setSelected(res.data); load();
    } catch (e) {
      setError("Gagal submit: " + (e.response?.data?.detail || e.message));
    }
  }

  async function handleCancelDraft(ret) {
    if (!window.confirm(`Buang draf ${ret.number}? Draf tidak bisa dipulihkan.`)) return;
    try {
      const res = await axios.post(`${API}/sales-returns/${ret.id}/cancel-draft`, {});
      setNotice(`${ret.number} dibuang.`);
      setSelected(res.data); load();
    } catch (e) {
      setError("Gagal membuang draf: " + (e.response?.data?.detail || e.message));
    }
  }

  if (selected) {
    return (
      <ReturnDetail
        ret={selected}
        token={token}
        onNavigate={onNavigate}
        canApprove={canApprove}
        currentUser={currentUser}
        onApprove={handleApprove}
        onReject={handleReject}
        onSubmit={handleSubmit}
        onCancelDraft={handleCancelDraft}
        onStartInspect={handleStartInspect}
        onCompleteInspect={handleCompleteInspect}
        onSettle={handleSettle}
        onReverse={handleReverse}
        onBack={() => { setSelected(null); load(); }}
        onAttachmentUploaded={(updated) => setSelected(updated)}
        onReturnChanged={(updated) => { if (updated) setSelected(updated); load(); }}
        notice={notice}
        onClearNotice={() => setNotice(null)}
      />
    );
  }

  return (
    <div data-testid="sales-returns-view" className="view-container">
      {/* FASE P4 — form retur jual menjadi POP-UP. Sebelumnya tombol "Buat Return"
          MENUKAR seluruh halaman (daftar retur & ringkasan hilang), jadi pengguna
          kehilangan konteks dan harus menekan "kembali" untuk melihat datanya lagi. */}
      <FormModal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        title="Buat Retur / Barang Sisa"
        subtitle="Retur, BS, penggantian, komplain & garansi dari pesanan yang sudah dikirim"
        icon={RotateCcw}
        size="lg"
        testId="sales-return-form"
      >
        <CreateReturnForm
          variant="modal"
          orders={orders}
          token={token}
          onCreated={(doc) => {
            setShowCreate(false);
            setNotice(`${doc.number} berhasil dibuat.`);
            load();
            setSelected(doc);
          }}
          onCancel={() => setShowCreate(false)}
          onLoadOrders={loadOrders}
        />
      </FormModal>
      {/* Header */}
      <div className="view-header">
        <div>
          <h1 className="view-title flex items-center gap-2"><RotateCcw size={20} /> Retur & Barang Sisa</h1>
          <p className="view-subtitle">Kelola retur, barang sisa (BS), penggantian, komplain & garansi (aftersales) + Nota Kredit</p>
        </div>
        <button
          data-testid="create-return-btn"
          className="primary-button"
          onClick={() => { loadOrders(); setShowCreate(true); }}
        >
          <Plus size={14} /> Buat Retur
        </button>
      </div>

      {/* Ringkasan */}
      <div data-testid="return-stats" className="grid grid-cols-2 gap-2 sm:grid-cols-4" style={{ marginBottom: 16 }}>
        {[
          { k: "total", label: "Total Retur", value: rTotal, icon: RotateCcw, hint: "semua status dalam cakupan" },
          { k: "pending", label: "Menunggu Persetujuan", value: cnt("pending_approval"), icon: AlertCircle, hint: "status 2" },
          { k: "process", label: "Diproses", value: cnt("approved") + cnt("inspecting") + cnt("inspected"), icon: CheckCircle2, hint: "status 3 + 4 + 5" },
          { k: "done", label: "Selesai", value: cnt("refund_settled") + cnt("credit_settled") + cnt("nego_settled"), icon: CheckCircle2, hint: "refund + store credit + nego (tanpa ditolak/batal)" },
        ].map(({ k, label, value, icon: Icon, hint }) => (
          <div key={label} className="metric-card" data-testid={`return-stat-${k}`}>
            <div className="metric-icon"><Icon size={16} /></div>
            <div className="metric-body">
              <div className="metric-label">{label}</div>
              <div className="metric-value tabular-nums">{value}</div>
              {hint && <div className="metric-hint">{hint}</div>}
            </div>
          </div>
        ))}
      </div>

      {/* Notices */}
      {notice && (
        <div className="notice-bar success" data-testid="return-notice">
          <CheckCircle2 size={14} /> {notice}
          <button onClick={() => setNotice(null)}><X size={12} /></button>
        </div>
      )}
      {error && (
        <ErrorNotice message={error} onRetry={load} onDismiss={() => setError(null)} testId="return-error" />
      )}
      {paged.error && (
        <ErrorNotice message={paged.error} onRetry={paged.refresh} testId="return-list-error" />
      )}

      {/* PETA RETUR (anti-dualisme, 2026-06) — di sistem ini ada TIGA jalur retur
          yang berbeda dokumen & muaranya; layar ini KHUSUS retur jual. Disebut
          eksplisit beserta jalannya supaya orang tidak mencatat retur beli di sini. */}
      <div className="mb-3 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border border-[#E4E9F2] bg-[#F8FAFD] px-3 py-2 text-[11.5px] text-[#3A3A3C]"
        data-testid="return-map-strip">
        <Map size={13} className="shrink-0 text-[#0058CC]" />
        <span><b>Layar ini = Retur JUAL</b> (barang kembali dari pelanggan → muaranya Nota Kredit).</span>
        <MapLink view="purchase-returns" label="Retur Pembelian ke Pemasok" role={currentUser?.role} onNavigate={onNavigate} />
        <MapLink view="interco-transactions" label="Retur antar-PT" role={currentUser?.role} onNavigate={onNavigate} />
        <MapLink view="return-policies" label="Kebijakan / jendela retur" role={currentUser?.role} onNavigate={onNavigate} />
      </div>

      {/* Filters */}
      <div className="filter-bar" style={{ marginBottom: 12 }}>
        <div className="search-wrap">
          <Search size={13} />
          <input
            data-testid="return-search"
            placeholder="Cari nomor / pesanan / pelanggan…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <LineFilter value={lineFilter} onChange={setLineFilter} storageKey="sales-returns"
                    allowed={currentUser?.allowed_line_codes} testId="sret-line-filter" />
      </div>
      <p className="text-[11px] text-[#6B6B73]" style={{ margin: "-8px 0 12px" }} data-testid="return-stats-scope">{scopeLabel}</p>
      <div className="mb-4 flex flex-wrap items-end gap-3" data-testid="return-filters">
        <div style={{ minWidth: 230 }}>
          <label className="form-label">Status</label>
          <KNSelect data-testid="return-status-filter" className="form-select" value={filterStatus} onValueChange={setFilterStatus}
            options={STATUS_OPTIONS.map(([v, l]) => ({ value: v, label: `${l} (${v === "all" ? rTotal : cnt(v)})` }))} />
        </div>
        <div style={{ minWidth: 200 }}>
          <label className="form-label">Kategori / tipe</label>
          <KNSelect data-testid="return-type-filter" className="form-select" value={returnType} onValueChange={setReturnType}
            options={TYPE_OPTIONS.map(([v, l]) => ({ value: v, label: l }))} />
        </div>
        <span className="text-[11px] text-[#6B6B73] self-center" data-testid="return-list-count">
          Daftar: {paged.total ?? 0} retur{filterStatus !== "all" ? " (status terpilih)" : ""}
        </span>
      </div>

      {/* Table */}
      {loading ? (
        <div className="empty-state"><Loader2 size={20} className="spin" /> Memuat...</div>
      ) : filtered.length === 0 ? (
        <div className="empty-state" data-testid="return-empty">
          <RotateCcw size={28} style={{ opacity: 0.3 }} />
          <p className="font-semibold">Belum ada data retur{search ? ` untuk "${search}"` : ""}.</p>
          <p className="text-sm text-muted" style={{ maxWidth: 460, margin: "4px auto 0" }}>
            Kelola retur barang, barang sisa (BS), penggantian, komplain & garansi dari pesanan yang sudah dikirim. Setiap retur melewati alur <b>persetujuan → inspeksi → penyelesaian</b> (refund / store credit / nego / tolak).
          </p>
          <button className="primary-button" style={{ marginTop: 12 }} onClick={() => { loadOrders(); setShowCreate(true); }}>
            <Plus size={13} /> Buat Retur Pertama
          </button>
        </div>
      ) : (
        <div className="table-wrap" data-testid="returns-table">
          <table className="data-table" style={{ minWidth: 1120 }}>
            <thead>
              <tr>
                <th>Nomor</th>
                <th>No. Pesanan</th>
                <th>Pelanggan</th>
                <th>Tipe</th>
                <th>Status</th>
                <th className="text-right">Item</th>
                <th className="text-right">Nilai (CN)</th>
                <th>Nota Kredit</th>
                <th>Umur</th>
                <th>Dibuat</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(r => (
                <tr key={r.id} data-testid={`return-row-${r.id}`}
                  className="cursor-pointer" onClick={() => setSelected(r)}>
                  <td><span className="font-mono font-semibold">{r.number}</span></td>
                  <td className="font-mono text-xs text-muted">{r.order_number}</td>
                  <td>{r.customer_name || "-"}</td>
                  <td><ReturnTypeBadge type={r.return_type} /></td>
                  <td><ReturnStatusPill status={r.status} /></td>
                  <td className="text-right tabular-nums">{r.items?.length || 0} item</td>
                  <td className="text-right tabular-nums">
                    {r.credit_note_amount
                      ? <strong>{formatCurrency(r.credit_note_amount)}</strong>
                      : <span className="text-muted text-sm" title="Nilai resmi terbit bersama Nota Kredit saat retur diselesaikan">—</span>}
                  </td>
                  <td>
                    {r.credit_note_number ? (
                      <span className="feature-badge badge-green" data-testid={`return-cn-${r.id}`}>
                        {r.credit_note_number}
                      </span>
                    ) : (
                      <span className="text-muted text-sm">—</span>
                    )}
                  </td>
                  <td><AgeCell r={r} /></td>
                  <td className="text-muted">{fmtDate(r.created_at)}</td>
                  <td>
                    <button
                      data-testid={`view-return-${r.id}`}
                      className="link-button"
                      onClick={(e) => { e.stopPropagation(); setSelected(r); }}
                    >Detail →</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {/* P2 — kontrol halaman: daftar retur bisa panjang (satu retur per komplain). */}      {!loading && filtered.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <PaginationBar
            page={paged.page} pageSize={paged.pageSize} total={paged.total}
            hasMore={paged.hasMore} loading={paged.loading}
            onPrev={paged.prev} onNext={paged.next} onPageSize={paged.setPageSize}
            testId="returns-pager" label="retur"
            exportConfig={{ columns: CSV_COLUMNS, rows: filtered,
              fetchAll: paged.fetchAll, filename: "retur-jual" }}
          />
        </div>
      )}
    </div>
  );
}

/** Tautan peta retur — hanya hidup bila layar tujuannya memang wilayah peran ini. */
function MapLink({ view, label, role, onNavigate }) {
  const target = resolveDeepLinkTarget(view, role);
  return (
    <button type="button" data-testid={`return-map-${view}`}
      disabled={!target}
      title={target ? `Buka ${label}` : "Layar ini bukan wilayah peran Anda"}
      onClick={() => target && onNavigate?.(target.navId, target.view, target.tab)}
      className={`inline-flex items-center gap-1 font-bold ${
        target ? "text-[#0058CC] hover:underline" : "cursor-not-allowed text-[#9A9BA3]"}`}>
      {label} <ArrowRight size={11} />
    </button>
  );
}

const TERMINAL_ST = ["refund_settled", "credit_settled", "nego_settled", "rejected", "cancelled"];

/** Umur dokumen retur yang masih berjalan — retur menua = uang pelanggan menggantung. */
function AgeCell({ r }) {
  if (TERMINAL_ST.includes(r.status)) return <span className="text-muted text-sm">selesai</span>;
  const days = Math.max(0, Math.floor((Date.now() - new Date(r.created_at).getTime()) / 86400000));
  const cls = days >= 7 ? "bg-[#FFE5E5] text-[#C62828]"
    : days >= 3 ? "bg-[#FFF1DB] text-[#B26A00]" : "bg-[#EFF3FB] text-[#33538B]";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-bold tabular-nums ${cls}`}>
      {days === 0 ? "hari ini" : `${days} hari`}
    </span>
  );
}
