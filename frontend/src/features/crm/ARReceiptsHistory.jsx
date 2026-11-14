/**
 * ARReceiptsHistory (EPIC3B) — daftar penerimaan pembayaran terbaru.
 * GET /api/ar-receipts. Refresh saat `refreshKey` berubah.
 *
 * PK-42 (UX-12) — berhalaman di server (`usePagedList`, 25 per halaman, terbaru dulu, cari nomor / pelanggan) dengan
 * "Menampilkan a–b dari N penerimaan"; dulu semua dimuat lalu dipotong 25 baris di layar tanpa keterangan.
 * Standar UI (KN_37): tabel baku `data-table`, kolom aksi lekat di kanan, status = ikon + teks + warna.
 *
 * PK-44 (IA-04) — `focus = { id, number, nonce }` dari tautan dokumen (Jejak / Dokumen Terkait): kotak cari server diisi
 * nomornya (kwitansi di luar halaman termuat tetap ketemu tanpa memuat semua baris) dan barisnya disorot.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { Wallet, RefreshCw, Ban, Route, CheckCircle2, AlertTriangle } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import JournalStatusBadge from "../../components/JournalStatusBadge";   // PK-18 — jurnal kwitansi / pembaliknya
import PaginationBar from "../../components/PaginationBar";
import { SearchBox } from "../../components/ListControls";
import { usePagedList } from "../../hooks/usePagedList";
import { formatCurrency } from "../../utils/formatters";
import { apiErrorText } from "../../utils/apiError";
import { fmtDate } from "./crmUtils";
import DocumentActionsBar from "../documents/DocumentActionsBar";
import { openTrace } from "../documents/trace/traceDeepLink";
import { can } from "../../config/roles";
// FASE G-3 — status selisih pembayaran per kwitansi (diputus / menunggu keputusan).
import { directionMeta, varianceKindMeta } from "../finance/payments/paymentApi";
import { askReason } from "@/services/confirmService";
import { gulirKe } from "../../hooks/useFocusDoc";

const PAGE_SIZE = 25;
// Butir CSV di "Unduh ▾" = kolom yang terlihat di layar (INV-UI-07), kata yang sama dengan tabel.
const RECEIPT_CSV_COLUMNS = [
  { key: "number", header: "No. kwitansi" },
  { key: "receipt_date", header: "Tanggal", type: "date" },
  { key: "customer_name", header: "Pelanggan" },
  { key: "method", header: "Metode" },
  { key: "amount", header: "Jumlah", type: "num" },
  { header: "Pesanan", get: (r) => (r.allocations || []).map((a) => a.order_number).join(", ") },
  { header: "Status", get: (r) => (r.status === "void" ? "Dibatalkan" : "Tercatat") },
];

function VarianceCell({ v = {} }) {
  if (!v.direction || v.direction === "none") return <span className="text-kn-text-2">—</span>;
  if (v.decision_kind) {
    const km = varianceKindMeta(v.decision_kind);
    return (
      <span className="status-pill" style={{ background: km.bg, color: km.fg }}
        title={`${v.decision_number || ""} · ${v.reason_label || ""}`}>
        <CheckCircle2 size={12} aria-hidden="true" />{km.label}
      </span>
    );
  }
  const dm = directionMeta(v.direction);
  return (
    <span className="status-pill" style={{ background: dm.bg, color: dm.fg }}
      title="Menunggu keputusan di Keuangan → Rencana Bayar & Denda → Selisih Bayar">
      <AlertTriangle size={12} aria-hidden="true" />{dm.label} · perlu diputus
    </span>
  );
}

export default function ARReceiptsHistory({ refreshKey, selectedEntity, currentUser, onChanged, focus = null }) {
  // FASE E-8 — membatalkan kwitansi (uang masuk yang sudah tercatat) tetap
  // wewenang manajer: Finance boleh MENCATAT, tidak boleh MENGHAPUS jejak uang.
  const canVoid = can(currentUser?.permissions || {}, "ar_receipt", "void");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [voiding, setVoiding] = useState("");
  const [sorot, setSorot] = useState("");
  useEffect(() => {
    if (!focus?.id) return;
    setSearch(focus.number || ""); setSorot(focus.id);
    gulirKe(`ar-history-row-${focus.id}`, 700);
  }, [focus?.nonce]); // eslint-disable-line react-hooks/exhaustive-deps

  // PK-42 — PT dari kepala aplikasi; "Semua PT" = tanpa saringan (server memakai cakupan pengguna).
  const params = useMemo(
    () => (selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {}), [selectedEntity]);
  const paged = usePagedList("/ar-receipts", { pageSize: PAGE_SIZE, params, search });
  const rows = paged.items;

  // Kwitansi baru dicatat di pop-up induk → muat ulang (pemuatan pertama sudah dijalankan hook).
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    paged.refresh();
  }, [refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

  async function voidReceipt(r) {
    // Berdampak UANG: membalik pembayaran pada order + kas + deposit.
    const reason = await askReason({
      title: `Batalkan penerimaan ${r.number}?`,
      message: `Nominal ${formatCurrency(r.amount)} akan dibalik: pembayaran pada order, `
        + `catatan kas, dan deposit pelanggan dikoreksi kembali.`,
      reasonLabel: "Alasan pembatalan",
      reasonPlaceholder: "Contoh: transfer ditolak bank / salah pelanggan",
      confirmLabel: "Batalkan Penerimaan",
      danger: true,
      testId: "ar-void-confirm",
    });
    if (reason === null) return;
    setVoiding(r.id);
    try {
      await axios.post(`${API}/ar-receipts/${r.id}/void`, null, { params: { reason } });
      await paged.refresh();
      onChanged?.(`Penerimaan ${r.number} dibatalkan.`);
    } catch (e) {
      setError(apiErrorText(e, "Gagal membatalkan penerimaan."));
    } finally { setVoiding(""); }
  }

  const listError = paged.error;
  return (
    <div className="section-card mt-3" data-testid="ar-receipts-history">
      <div className="section-head">
        <div className="flex items-center gap-2"><Wallet size={15} className="text-kn-success-text" /><h2>Riwayat Pembayaran (AR)</h2></div>
        <button type="button" data-testid="ar-history-refresh" className="icon-button ml-auto" onClick={paged.refresh}
          aria-label="Muat ulang" title="Muat ulang"><RefreshCw size={13} className={paged.loading ? "animate-spin" : ""} /></button>
      </div>
      <div className="section-body">
        <ErrorNotice message={error} onDismiss={() => setError("")} testId="ar-history-action-error" />
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <SearchBox value={search} onChange={(v) => { setSearch(v); if (!v) setSorot(""); }} placeholder="Cari nomor kwitansi / pelanggan…" testId="ar-history-search" />
        </div>
        {listError ? (
          <ErrorNotice message={listError} onRetry={paged.refresh} testId="ar-history-error" />
        ) : paged.loading && rows.length === 0 ? (
          <div className="py-6 text-center text-fs-12 text-kn-text-2" data-testid="ar-history-loading">Memuat...</div>
        ) : rows.length === 0 ? (
          <div className="py-8 text-center text-fs-12 text-kn-text-2" data-testid="ar-history-empty">
            {search.trim() ? `Tidak ada penerimaan yang cocok dengan “${search.trim()}”.` : "Belum ada pembayaran tercatat."}
          </div>
        ) : (
          <div className="table-wrap">
            <table className="data-table head-wrap" data-testid="ar-history-table">
              <thead>
                <tr>
                  <th>No.</th><th>Tanggal</th><th>Pelanggan</th><th>Metode</th><th className="text-right">Jumlah</th>
                  <th>Pesanan</th><th>Selisih</th><th>Status</th><th className="col-sticky-end text-right">Dokumen &amp; aksi</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const isVoid = r.status === "void";
                  return (
                    <tr key={r.id} data-testid={`ar-history-row-${r.id}`} className={r.id === sorot ? "row-focus" : undefined}>
                      <td className="font-mono whitespace-nowrap text-kn-action">{r.number}</td>
                      <td className="whitespace-nowrap text-kn-text-2">{fmtDate(r.receipt_date)}</td>
                      <td className="font-semibold">{r.customer_name}</td>
                      <td className="capitalize">{r.method}</td>
                      <td className={`text-right tabular-nums font-semibold ${isVoid ? "line-through text-kn-text-2" : "text-kn-success-text"}`}>{formatCurrency(r.amount)}</td>
                      <td className="text-fs-12 text-kn-text-2">{(r.allocations || []).map((a) => a.order_number).join(", ") || "—"}</td>
                      <td data-testid={`ar-history-variance-${r.id}`}><VarianceCell v={r.variance} /></td>
                      <td>
                        <div className="flex flex-col items-start gap-1">
                          <span data-testid={`ar-history-status-${r.id}`}
                            className={`status-pill ${isVoid ? "bg-kn-danger-soft text-kn-danger-text" : "bg-kn-success-soft text-kn-success-text"}`}>
                            {isVoid ? <Ban size={12} aria-hidden="true" /> : <CheckCircle2 size={12} aria-hidden="true" />}
                            {isVoid ? "Dibatalkan" : "Tercatat"}
                          </span>
                          {/* PK-18 — kwitansi batal: status jurnal PEMBALIKNYA; selain itu jurnal penerimaannya */}
                          <JournalStatusBadge testId={`ar-history-journal-${r.id}`}
                            status={isVoid ? r.void_gl_status : r.gl_status}
                            error={isVoid ? r.void_gl_error : r.gl_error}
                            journalEntryId={isVoid ? r.void_journal_entry_id : r.journal_entry_id} />
                        </div>
                      </td>
                      <td className="col-sticky-end">
                        <div className="flex items-center justify-end gap-1">
                          <DocumentActionsBar
                            docType="ar_receipt"
                            sourceId={r.id}
                            entityId={r.entity_id}
                            number={r.number}
                            label="Kwitansi"
                            esignable={!isVoid}
                            autoCheckSignature={false}
                            currentUser={currentUser}
                            compact
                          />
                          {/* FASE G-4 — telusuri dari kwitansi ke SO → Surat Jalan → Faktur → Retur */}
                          <button type="button" data-testid={`ar-history-trace-${r.id}`} className="icon-button"
                            title="Buka Jejak Dokumen (rantai surat terkait)" aria-label={`Jejak dokumen ${r.number}`}
                            onClick={() => openTrace({ docType: "ar_receipt", docId: r.id, number: r.number })}>
                            <Route size={13} />
                          </button>
                          {canVoid && !isVoid && (
                            <button type="button" data-testid={`ar-history-void-${r.id}`} className="icon-button text-kn-danger-text"
                              disabled={voiding === r.id} onClick={() => voidReceipt(r)}
                              title="Batalkan (anulir) penerimaan" aria-label={`Batalkan penerimaan ${r.number}`}><Ban size={14} /></button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {!listError && paged.total > 0 && (
          <div className="mt-2">
            <PaginationBar page={paged.page} pageSize={paged.pageSize} total={paged.total} hasMore={paged.hasMore}
              loading={paged.loading} onPrev={paged.prev} onNext={paged.next} testId="ar-history-pager" label="penerimaan"
              exportConfig={{ columns: RECEIPT_CSV_COLUMNS, rows: rows, fetchAll: paged.fetchAll, filename: "riwayat-penerimaan" }}
              exportSpec={{ dataset: "ar_receipts", label: "riwayat-penerimaan", search,
                sort: [{ key: "receipt_date", dir: "desc" }] }} />
          </div>
        )}
      </div>
    </div>
  );
}
