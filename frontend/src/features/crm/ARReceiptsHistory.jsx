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
 *
 * PM-T3 — kolom "Rekening" (cara bayar + rekening penerima + tanda "Tidak sesuai instruksi") dan "No. referensi";
 * lencana status Tercatat · Terverifikasi bank · Tunai · Dianulir (ikon + teks + warna); saringan "Belum terverifikasi
 * lebih dari {N} hari" (`?bank_verified=false&older_than_days=` — batas dari `payment.hari_wajar_verifikasi_bank`).
 * PM-T4 — lencana "Titipan sales" untuk kwitansi tunai yang uangnya masih di tangan sales (belum masuk kas).
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { Wallet, RefreshCw, Ban, Route, CheckCircle2, AlertTriangle, BadgeCheck, Clock, Banknote } from "lucide-react";
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
import DocLink from "../documents/preview/DocLink";   // Meja gelombang 2 — kwitansi & pesanan teralokasi membuka rincian
import { can } from "../../config/roles";
// FASE G-3 — status selisih pembayaran per kwitansi (diputus / menunggu keputusan).
import { directionMeta, varianceKindMeta } from "../finance/payments/paymentApi";
import { askReason } from "@/services/confirmService";
import { gulirKe } from "../../hooks/useFocusDoc";
import { docStatusLabel } from "../../utils/docStatus";
import { usePaymentMethods } from "../../config/paymentMethods";

const PAGE_SIZE = 25;

/** PM-T3 — "{bank} {nomor}" rekening penerima dari potret kwitansi (rekening lama tanpa potret → "—"). */
export const receiptAccountText = (r) => {
  const a = r?.account_snapshot || {};
  const head = [a.bank_name, a.account_number].map((x) => String(x || "").trim()).filter(Boolean).join(" ");
  return head || String(a.name || "");
};

/**
 * PM-T3 — status kwitansi: Dianulir · Tunai (uang ke rekening kas, tidak menunggu mutasi bank) · Terverifikasi bank
 * (kas cocok penuh dengan mutasi rekening yang sama) · Tercatat (berdasarkan bukti pelanggan).
 */
export function receiptStatus(r, isCash = () => false) {
  if (r?.status === "void") return { key: "void", label: docStatusLabel("void"), icon: Ban, cls: "bg-kn-danger-soft text-kn-danger-text" };
  // PM-T4 — tunai yang dicatat sebagai titipan di tangan sales (belum masuk kas sampai setorannya diterima).
  if (r?.cash_holding_id) return { key: "titipan", label: "Titipan sales", icon: Wallet, cls: "bg-kn-warning-soft text-kn-warning-text" };
  if (Number(r?.amount || 0) > 0 && isCash(r?.payment_method_code || r?.method)) {
    return { key: "cash", label: "Tunai", icon: Banknote, cls: "bg-kn-neutral-soft text-kn-text" };
  }
  if (r?.bank_verified) return { key: "verified", label: "Terverifikasi bank", icon: BadgeCheck, cls: "bg-kn-success-soft text-kn-success-text" };
  return { key: "recorded", label: "Tercatat", icon: Clock, cls: "bg-kn-action-soft text-kn-action" };
}

// Butir CSV di "Unduh ▾" = kolom yang terlihat di layar (INV-UI-07), kata yang sama dengan tabel.
const receiptCsvColumns = (labelOf, isCash) => [
  { key: "number", header: "No. kwitansi" },
  { key: "receipt_date", header: "Tanggal", type: "date" },
  { key: "customer_name", header: "Pelanggan" },
  { header: "Cara bayar", get: (r) => labelOf(r.payment_method_code || r.method) },
  { header: "Rekening", get: (r) => receiptAccountText(r) },
  { header: "No. referensi", get: (r) => r.reference_no || "" },
  { key: "amount", header: "Jumlah", type: "num" },
  { header: "Pesanan", get: (r) => (r.allocations || []).map((a) => a.order_number).join(", ") },
  { header: "Status", get: (r) => receiptStatus(r, isCash).label },
  { header: "Tidak sesuai instruksi", get: (r) => (r.instruction_mismatch ? `Ya — ${r.mismatch_note || ""}` : "") },
];

export function VarianceCell({ v = {}, isVoid = false }) {
  if (!v.direction || v.direction === "none") return <span className="text-kn-text-2">—</span>;
  // S4 (pelatihan 18 Nov) — kwitansi dianulir: keputusan selisihnya ikut dibatalkan dan tidak ada yang perlu diputus.
  // Dulu tampil "Kurang Bayar · Perlu Diputus" (merah) pada kwitansi yang sudah batal.
  if (isVoid && !v.decision_kind) {
    return <span className="text-fs-12 text-kn-text-2" title="Kwitansi dianulir — keputusan selisihnya ikut dibatalkan">Ikut dianulir</span>;
  }
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
  const pm = usePaymentMethods("masuk", selectedEntity);
  // PM-T3 — saringan "Belum terverifikasi lebih dari N hari" (N = pengaturan PT; server memakai nilai yang sama).
  const [unverified, setUnverified] = useState(false);
  const [batasHari, setBatasHari] = useState(null);
  useEffect(() => {
    let alive = true;
    const p = selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {};
    axios.get(`${API}/settings/effective`, { params: p })
      .then((r) => { if (alive) setBatasHari(r.data?.payment?.hari_wajar_verifikasi_bank ?? null); })
      .catch(() => { if (alive) setBatasHari(null); });
    return () => { alive = false; };
  }, [selectedEntity]);
  useEffect(() => {
    if (!focus?.id) return;
    setSearch(focus.number || ""); setSorot(focus.id);
    gulirKe(`ar-history-row-${focus.id}`, 700);
  }, [focus?.nonce]); // eslint-disable-line react-hooks/exhaustive-deps

  // PK-42 — PT dari kepala aplikasi; "Semua PT" = tanpa saringan (server memakai cakupan pengguna).
  const params = useMemo(() => ({
    ...(selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {}),
    ...(unverified ? { bank_verified: "false", older_than_days: "" } : {}),
  }), [selectedEntity, unverified]);
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
          <label className="inline-flex items-center gap-1.5 whitespace-nowrap text-fs-12 text-kn-text" data-testid="ar-history-unverified">
            <input type="checkbox" checked={unverified} onChange={(e) => setUnverified(e.target.checked)}
              data-testid="ar-history-unverified-toggle" />
            Belum terverifikasi lebih dari {batasHari ?? "batas wajar"}{batasHari != null ? " hari" : ""}
          </label>
        </div>
        {listError ? (
          <ErrorNotice message={listError} onRetry={paged.refresh} testId="ar-history-error" />
        ) : paged.loading && rows.length === 0 ? (
          <div className="py-6 text-center text-fs-12 text-kn-text-2" data-testid="ar-history-loading">Memuat...</div>
        ) : rows.length === 0 ? (
          <div className="py-8 text-center text-fs-12 text-kn-text-2" data-testid="ar-history-empty">
            {search.trim() ? `Tidak ada penerimaan yang cocok dengan “${search.trim()}”.`
              : unverified ? "Tidak ada kwitansi non-tunai yang menunggu dicocokkan dengan mutasi bank melewati batas wajar."
                : "Belum ada pembayaran tercatat."}
          </div>
        ) : (
          <div className="table-wrap">
            <table className="data-table head-wrap" data-testid="ar-history-table">
              <thead>
                <tr>
                  <th>No.</th><th>Tanggal</th><th>Pelanggan</th><th>Rekening</th><th>No. referensi</th>
                  <th className="text-right">Jumlah</th>
                  <th>Pesanan</th><th>Selisih</th><th>Status</th><th className="col-sticky-end text-right">Dokumen &amp; aksi</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const isVoid = r.status === "void";
                  const st = receiptStatus(r, pm.isCash);
                  const StIcon = st.icon;
                  return (
                    <tr key={r.id} data-testid={`ar-history-row-${r.id}`} className={r.id === sorot ? "row-focus" : undefined}>
                      <td className="font-mono whitespace-nowrap">
                        <DocLink docType="ar_receipt" docId={r.id} number={r.number} entityId={r.entity_id}
                          perms={currentUser?.permissions} testId={`ar-history-number-${r.id}`} />
                      </td>
                      <td className="whitespace-nowrap text-kn-text-2">{fmtDate(r.receipt_date)}</td>
                      <td className="font-semibold">{r.customer_name}</td>
                      <td data-testid={`ar-history-account-${r.id}`}>
                        <p>{pm.labelOf(r.payment_method_code || r.method)}</p>
                        {receiptAccountText(r) && <p className="text-fs-12 text-kn-text-2">{receiptAccountText(r)}</p>}
                        {r.instruction_mismatch && (
                          <span className="status-pill mt-1 bg-kn-warning-soft text-kn-warning-text" data-testid={`ar-history-mismatch-${r.id}`}
                            title={r.mismatch_note || ""}>
                            <AlertTriangle size={12} aria-hidden="true" />Tidak sesuai instruksi
                          </span>
                        )}
                      </td>
                      <td className="font-mono text-fs-12" data-testid={`ar-history-ref-${r.id}`}>{r.reference_no || "—"}</td>
                      <td className={`text-right tabular-nums font-semibold ${isVoid ? "line-through text-kn-text-2" : "text-kn-success-text"}`}>{formatCurrency(r.amount)}</td>
                      <td className="text-fs-12 text-kn-text-2" data-testid={`ar-history-allocs-${r.id}`}>
                        {(r.allocations || []).length === 0 ? "—" : r.allocations.map((a, i) => (
                          <span key={`${a.order_id || a.order_number}-${i}`}>
                            {i > 0 && ", "}
                            <DocLink docType="sales_order" docId={a.order_id} number={a.order_number} entityId={r.entity_id}
                              perms={currentUser?.permissions} testId={`ar-history-order-${r.id}-${a.order_id}`} />
                          </span>
                        ))}
                      </td>
                      <td data-testid={`ar-history-variance-${r.id}`}><VarianceCell v={r.variance} isVoid={isVoid} /></td>
                      <td>
                        <div className="flex flex-col items-start gap-1">
                          <span data-testid={`ar-history-status-${r.id}`} data-status={st.key} className={`status-pill ${st.cls}`}>
                            <StIcon size={12} aria-hidden="true" />{st.label}
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
              exportConfig={{ columns: receiptCsvColumns(pm.labelOf, pm.isCash), rows: rows, fetchAll: paged.fetchAll,
                filename: "riwayat-penerimaan" }}
              exportSpec={{ dataset: "ar_receipts", label: "riwayat-penerimaan", search,
                sort: [{ key: "receipt_date", dir: "desc" }] }} />
          </div>
        )}
      </div>
    </div>
  );
}
