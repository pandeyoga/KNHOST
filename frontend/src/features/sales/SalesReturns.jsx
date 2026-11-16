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
import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { can } from "../../config/roles";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import { apiErrorText } from "../../utils/apiError";
import { askConfirm } from "../../services/confirmService";
import LineFilter from "../../components/LineFilter";   // FASE L
import PaginationBar from "../../components/PaginationBar";
import { usePagedList } from "../../hooks/usePagedList";
import { CheckCircle2, Loader2, Plus, RotateCcw, X, AlertCircle } from "lucide-react";
import { ListToolbar, MetricRow, PageHeader, SearchInput } from "../../components/ListPageParts";   // pola UI 16 Nov
import { ReturnStatusPill, ReturnTypeBadge, fmtDate } from "./ReturnShared";
import { formatCurrency } from "../../utils/formatters";
import ReturnDetail from "./ReturnDetail";
import CreateReturnForm from "./CreateReturnForm";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";

// L08 LN-080-T04 — status & tipe adalah SARINGAN (dropdown), bukan deretan tab.
// UAT 24 Okt (audit UI tahap 2) — G2-16: tanpa nomor urut & satu nama dengan kartu/lencana
// (dulu "2 · Menunggu ACC" sementara KPI menulis "Menunggu Persetujuan").
const STATUS_OPTIONS = [
  ["all", "Semua status"], ["draft", "Draf"], ["pending_approval", "Menunggu Persetujuan"],
  ["approved", "Disetujui"], ["inspecting", "Inspeksi"], ["inspected", "Siap diselesaikan"],
  ["refund_settled", "Selesai · refund"], ["credit_settled", "Selesai · store credit"], ["nego_settled", "Selesai · nego"], ["settled", "Selesai · per roll (campuran)"],
  ["rejected", "Ditolak"], ["cancelled", "Dibatalkan"],
];
const OPERATOR_STATUSES = ["all", "approved", "inspecting"];   // F-11-layar — tahap kerja Gudang/QC
// Pola UI 16 Nov — kelompok status untuk kartu "Diproses"/"Selesai" (juga pilihan di dropdown status).
const GROUP_PROCESS = "approved,inspecting,inspected";
const GROUP_DONE = "refund_settled,credit_settled,nego_settled,settled";
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
export default function SalesReturns({ currentUser, onNavigate, onOpenDocument, focusDoc, onClearFocus }) {
  const [filterStatus, setFilterStatus] = useState("all");
  const [returnType, setReturnType]   = useState("all");   // UI/UX 2026-06 — saring per tipe
  const [search, setSearch]         = useState("");
  const [selected, setSelected]     = useState(null);  // detail panel
  const [showCreate, setShowCreate] = useState(false);
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

  // Penyaringan status & pencarian sudah dilakukan SERVER; daftar dipakai apa adanya.
  const filtered = returns;

  // FE-04 — ACC/settle/pembalikan retur → sales_return.approve (izin efektif server).
  const canApprove = can(currentUser?.permissions, "sales_return", "approve");
  const canCreate = can(currentUser?.permissions, "sales_return", "create");
  // F-11-layar — Gudang/QC (wms.scan/qc.inspect tanpa sales_return.view): server hanya mengirim
  // retur approved/inspecting tanpa field uang; layar ikut tanpa kolom & kartu uang.
  const operator = !can(currentUser?.permissions, "sales_return", "view");
  const cnt = (s) => Number(counts[s] || 0);
  // Kelompok status = beberapa status sekaligus ("a,b"); server menyaring `$in` (pola UI 16 Nov — kartu = saringan cepat).
  const statusCount = (v) => String(v).split(",").reduce((n, x) => n + cnt(x), 0);
  const rTotal = Number(counts.all || 0);
  const statusOptions = operator ? STATUS_OPTIONS.filter(([v]) => OPERATOR_STATUSES.includes(v))
    : [STATUS_OPTIONS[0], [GROUP_PROCESS, "Diproses (semua)"], [GROUP_DONE, "Selesai (semua)"], ...STATUS_OPTIONS.slice(1)];
  const statCards = operator ? [
    // 23 Okt — petunjuk berbahasa kerja (dulu "status 3 + 4" — nomor urut internal yang tak dikenal pengguna).
    { k: "total", label: "Retur untuk Gudang/QC", value: rTotal, icon: RotateCcw, status: "all" },
    { k: "receive", label: "Menunggu Terima / QC", value: cnt("approved"), icon: AlertCircle, status: "approved" },
    { k: "process", label: "Sedang QC", value: cnt("inspecting"), icon: CheckCircle2, status: "inspecting" },
  ] : [
    { k: "total", label: "Total Retur", value: rTotal, icon: RotateCcw, status: "all" },
    { k: "pending", label: "Menunggu Persetujuan", value: cnt("pending_approval"), icon: AlertCircle, status: "pending_approval" },
    { k: "process", label: "Diproses", value: statusCount(GROUP_PROCESS), icon: CheckCircle2, status: GROUP_PROCESS },
    { k: "done", label: "Selesai", value: statusCount(GROUP_DONE), icon: CheckCircle2, status: GROUP_DONE },
  ];

  // ─── lifecycle actions (R1 state machine) ─────────────────────────────────
  // FE-07 — satu pintu aksi: error tampil di layar AKTIF (detail/modal, bukan state induk yang tak terlihat),
  // pemanggil menerima pesan errornya sehingga modal hanya ditutup bila berhasil, dan klik ulang selama
  // proses berjalan diabaikan (tidak menggandakan transaksi). Hasil: null = berhasil, string = pesan gagal.
  const busyRef = useRef("");
  const [busyAction, setBusyAction] = useState("");
  async function runAction(key, label, fn) {
    if (busyRef.current) return "Aksi lain masih diproses — tunggu sampai selesai.";
    busyRef.current = key; setBusyAction(key); setError(null);
    try {
      await fn();
      return null;
    } catch (e) {
      const msg = `${label}: ${apiErrorText(e)}`;
      setError(msg);
      return msg;
    } finally {
      busyRef.current = ""; setBusyAction("");
    }
  }

  // Cek UI UAT v3 (S14) — respons aksi = dokumen mentah (tanpa nomor roll, nilai, bukti): dulu kolom qty aktual
  // menampilkan id roll mentah setelah [Mulai Inspeksi]. Tampilkan respons dulu, lalu muat ulang detail lengkap.
  async function showFresh(doc) {
    setSelected(doc);
    if (!doc?.id) return;
    try { const r = await axios.get(`${API}/sales-returns/${doc.id}`); setSelected(r.data); } catch { /* respons aksi tetap tampil */ }
  }

  function handleApprove(ret) {
    return runAction("approve", "Gagal approve", async () => {
      const res = await axios.post(`${API}/sales-returns/${ret.id}/approve`, { notes: "" });
      setNotice(`${ret.number} disetujui. Lanjut ke inspeksi.`);
      showFresh(res.data); load();
    });
  }

  function handleSettle(ret, outcome, itemDecisions, notes, returnWarehouseId, refundAccountCode, decisionNote, payout, exchange,
    refundAccountId) {
    return runAction("settle", "Gagal settle", async () => {
      const body = { outcome, item_decisions: itemDecisions || [], notes: notes || "", decision_note: decisionNote || "", payout: payout || "" };
      if (returnWarehouseId) body.return_warehouse_id = returnWarehouseId;
      if (refundAccountCode) body.refund_account_code = refundAccountCode;
      if (refundAccountId) body.refund_account_id = refundAccountId;   // PK-20 — rekening kas refund tunai
      if (exchange) body.exchange = true;
      const res = await axios.post(`${API}/sales-returns/${ret.id}/settle`, body);
      const st = res.data?.settlement || {};
      const cashMsg = st.cash_txn_number ? ` · refund tunai ${st.cash_txn_number}` : "";
      const outLabel = exchange ? "tukar barang — saldo untuk pesanan pengganti"
        : ({ refund: "pengembalian dana", store_credit: "store credit", nego: "nego/diskon" }[outcome] || outcome);
      setNotice(`${ret.number} diselesaikan (${outLabel})${cashMsg}.`);
      showFresh(res.data); load();
    });
  }

  function handleReject(ret, reason) {
    return runAction("reject", "Gagal reject", async () => {
      const res = await axios.post(`${API}/sales-returns/${ret.id}/reject`, { notes: reason });
      setNotice(`${ret.number} ditolak.`);
      showFresh(res.data); load();
    });
  }

  async function handleReverse(ret, reason) {
    // R5.4 — reversal/koreksi retur settled (lempar error agar modal bisa tampilkan pesan).
    const res = await axios.post(`${API}/sales-returns/${ret.id}/reverse`, { notes: reason });
    const summ = res.data?._reversal_summary || {};
    setNotice(`${ret.number} dibatalkan (reversal) · ${summ.reversal_jes || 0} jurnal balik, ${summ.rolls_removed || 0} roll dihapus.`);
    showFresh(res.data); load();
    return res.data;
  }

  function handleSubmit(ret) {
    return runAction("submit", "Gagal submit", async () => {
      const res = await axios.post(`${API}/sales-returns/${ret.id}/submit`, {});
      setNotice(`${ret.number} dikirim untuk approval.`);
      showFresh(res.data); load();
    });
  }

  async function handleCancelDraft(ret) {
    const ok = await askConfirm({ title: `Buang draf ${ret.number}?`, message: "Draf tidak bisa dipulihkan.",
                                  confirmLabel: "Buang draf", danger: true, testId: "return-cancel-draft-confirm" });
    if (!ok) return null;
    return runAction("cancel_draft", "Gagal membuang draf", async () => {
      const res = await axios.post(`${API}/sales-returns/${ret.id}/cancel-draft`, {});
      setNotice(`${ret.number} dibuang.`);
      showFresh(res.data); load();
    });
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
        onOpenDocument={onOpenDocument}
        onSettle={handleSettle}
        onReverse={handleReverse}
        onBack={() => { setSelected(null); setError(null); load(); }}
        onAttachmentUploaded={(updated) => showFresh(updated)}
        onReturnChanged={(updated) => { if (updated) showFresh(updated); load(); }}
        notice={notice}
        onClearNotice={() => setNotice(null)}
        error={error}
        onClearError={() => setError(null)}
        busyAction={busyAction}
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
          token={token}
          onCreated={(doc) => {
            setShowCreate(false);
            setNotice(`${doc.number} berhasil dibuat.`);
            load();
            showFresh(doc);
          }}
          onCancel={() => setShowCreate(false)}
        />
      </FormModal>
      {/* Pola UI (04_POLA_UI §2.A, contoh 2 — pemilik 16 Nov M23/M24): kepala SATU baris (keterangan di ?), kartu angka =
          saringan cepat, satu bilah daftar (cari · lini · status · tipe · jumlah · Unduh · + Buat Retur) tepat di atas
          tabel. Dulu: subjudul, 4 kartu berketerangan panjang, bilah peta retur, chip lini, label "Cakupan", dua dropdown
          berlabel di baris lain, dan tombol buat jauh di kepala halaman. Retur antar-PT & ke supplier ada di tab hub. */}
      <PageHeader icon={RotateCcw} title="Retur & Barang Sisa" testId="return-header"
        help={operator
          ? "Retur pelanggan yang menunggu scan terima/kirim/tiba dan pemeriksaan QC."
          : "Retur JUAL: barang kembali dari pelanggan — muaranya Nota Kredit. Termasuk barang sisa (BS), penggantian, komplain & garansi. Retur ke supplier dan retur antar-PT ada di tab di atas; kebijakan/jendela retur di Pengaturan › Penjualan."} />

      {/* Kartu angka = saringan cepat (klik → daftar tersaring; klik lagi → semua). */}
      <MetricRow testId="return-stats" items={statCards.map(({ k, label, value, icon, status }) => ({
        label, value, icon, testId: `return-stat-${k}`,
        active: status !== undefined && status !== "all" && filterStatus === status,
        onClick: status === undefined ? undefined : () => setFilterStatus(filterStatus === status ? "all" : status),
      }))} />

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

      <div className="mt-3">
        <ListToolbar testId="return-filters"
          count={`${paged.total ?? 0} retur`}
          actions={canCreate && (
            <button data-testid="create-return-btn" className="primary-button" onClick={() => setShowCreate(true)}>
              <Plus size={14} /> Buat Retur
            </button>
          )}>
          <SearchInput testId="return-search" placeholder="Cari nomor / pesanan / pelanggan…" value={search}
            onChange={setSearch} className="min-w-[220px] flex-1 sm:max-w-[320px]" />
          <LineFilter value={lineFilter} onChange={setLineFilter} storageKey="sales-returns"
                      allowed={currentUser?.allowed_line_codes} testId="sret-line-filter" />
          <KNSelect data-testid="return-status-filter" aria-label="Status" className="!h-auto !w-auto min-w-[190px] rounded-lg border border-kn-field-border bg-white !px-2 !py-1.5 text-fs-13"
            value={filterStatus} onValueChange={(v) => setFilterStatus(v || "all")}
            options={statusOptions.map(([v, l]) => ({ value: v, label: `${l} (${v === "all" ? rTotal : statusCount(v)})` }))} />
          <KNSelect data-testid="return-type-filter" aria-label="Tipe" className="!h-auto !w-auto min-w-[150px] rounded-lg border border-kn-field-border bg-white !px-2 !py-1.5 text-fs-13"
            value={returnType} onValueChange={(v) => setReturnType(v || "all")}
            options={TYPE_OPTIONS.map(([v, l]) => ({ value: v, label: l }))} />
        </ListToolbar>
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
          {canCreate && (
            <button className="primary-button" style={{ marginTop: 12 }} onClick={() => setShowCreate(true)}>
              <Plus size={13} /> Buat Retur Pertama
            </button>
          )}
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
                {!operator && <th className="text-right">Nilai (CN)</th>}
                {!operator && <th>Nota Kredit</th>}
                <th>Umur</th>
                <th>Dibuat</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(r => (
                <tr key={r.id} data-testid={`return-row-${r.id}`}
                  className="cursor-pointer" onClick={() => showFresh(r)}>
                  <td><span className="font-mono font-semibold">{r.number}</span></td>
                  <td className="font-mono text-xs text-muted">{r.order_number}</td>
                  <td>{r.customer_name || "-"}</td>
                  <td><ReturnTypeBadge type={r.return_type} /></td>
                  <td><ReturnStatusPill status={r.status} /></td>
                  <td className="text-right tabular-nums">{r.items?.length || 0} item</td>
                  {!operator && <>
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
                  </>}
                  <td><AgeCell r={r} /></td>
                  <td className="text-muted">{fmtDate(r.created_at)}</td>
                  <td>
                    <button
                      data-testid={`view-return-${r.id}`}
                      className="link-button"
                      onClick={(e) => { e.stopPropagation(); showFresh(r); }}
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
            exportConfig={{ columns: operator ? CSV_COLUMNS.filter((c) => c.key !== "credit_note_number") : CSV_COLUMNS, rows: filtered,
              fetchAll: paged.fetchAll, filename: "retur-jual" }}
            exportSpec={{ dataset: "sales_returns", label: "retur-jual", search,
              filters: [filterStatus !== "all" && ["status", filterStatus.includes(",") ? "in" : "eq", filterStatus], returnType !== "all" && ["return_type", "eq", returnType]],
              sort: [{ key: "created_at", dir: "desc" }], unsupported: lineFilter ? "Saringan lini belum bisa diikuti berkas Excel retur jual — kosongkan lini atau pakai CSV." : "" }}
          />
        </div>
      )}
    </div>
  );
}

const TERMINAL_ST = ["refund_settled", "credit_settled", "nego_settled", "settled", "rejected", "cancelled"];

/** Umur dokumen retur yang masih berjalan — retur menua = uang pelanggan menggantung. */
function AgeCell({ r }) {
  // G2-16 — retur yang sudah tutup tidak punya umur berjalan → "—" (dulu kata "selesai" di kolom UMUR).
  if (TERMINAL_ST.includes(r.status)) return <span className="text-muted text-sm" title="Retur sudah ditutup">—</span>;
  const days = Math.max(0, Math.floor((Date.now() - new Date(r.created_at).getTime()) / 86400000));
  const cls = days >= 7 ? "bg-[#FFE5E5] text-[#C62828]"
    : days >= 3 ? "bg-[#FFF1DB] text-[#B26A00]" : "bg-[#EFF3FB] text-[#33538B]";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-bold tabular-nums ${cls}`}>
      {days === 0 ? "< 1 hari" : `${days} hari`}
    </span>
  );
}
