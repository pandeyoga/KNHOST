/**
 * BankLineQueuePanel (F1, rancangan kwitansi otomatis dari mutasi §5.4–§5.5) — panel pop-up antrean `mutasi_berkode` di
 * Meja Keuangan (kelompok "Uang masuk perlu dicatat"): mutasi bank berkode bayar yang TIDAK cocok sempurna (kartu
 * beralasan). Isi, dalam SATU pop-up meja (tidak ada `DetailModal` kedua):
 *  · atas — alasan kartu (`f1.alasan`) + referensi bank mutasi;
 *  · laporan bayar yang MENUNGGU untuk pesanan itu — selalu dimuat dari `GET /sales-orders/{id}/payment-reports` bila
 *    baris berpesanan (I3 gelombang akhir: kartu `laporan_beda`, `rekening_beda`, `nominal_beda` tidak membawa
 *    `report_id`, padahal "Catat kwitansi" ditolak server selama laporan menunggu). Per laporan: "Terima laporan ini
 *    dengan mutasi ini" (laporan diterima dengan mutasi ini sebagai buktinya — `receiptFromLine` dengan
 *    `payment_report_id`, satu permintaan atomik) hanya bila nominal laporan = mutasi (selisih < Rp 1) dan rekeningnya
 *    sama (server menegakkan hal yang sama); "Tolak" (alasan; aturan Lapor Bayar yang ada) selalu. Hanya pemegang
 *    `payment_report.decide` (server pun menuntutnya). Laporan `memproses` hanya dibaca;
 *  · kartu yang menyebut kwitansi terbuka (`receipt_id`) — catatan bahwa "Catat kwitansi" tidak ditawarkan (meja
 *    menyembunyikan tombolnya: uangnya mungkin sama);
 *  · bawah — pratinjau pesanan kode bayar dari registri (`DeskDocPanel` → Body `sales_order`).
 * "Catat kwitansi" = tombol kaki pop-up (`DeskRowDetail`, aksi di tempat): pop-up menutup lalu meja membuka form Terima
 * pembayaran terisi dari mutasi (`bankLineId`) — satu pop-up pada satu waktu. Pilihan lain (titipkan, abaikan, cocokkan
 * manual) = SATU tombol kaki "Buka Rekonsiliasi" (`row._openFullLabel`, gelombang akhir: dulu juga tombol kedua di panel).
 * Sukses Terima → toast + `onRowChanged` + pop-up menutup. Tolak → toast + kartu & laporan dimuat ulang, pop-up tetap
 * (lanjut Catat kwitansi). Galat → bilah galat di dalam panel; pop-up tetap terbuka dan laporan dimuat ulang.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import { can } from "../../config/roles";
import { rememberDocEntities } from "../../services/docEntityRegistry";
import { askConfirm, askReason } from "../../services/confirmService";
import useIntentKey from "../../hooks/useIntentKey";
import { apiErrorText } from "../../utils/apiError";
import { notifySuccess } from "../../utils/feedback";
import { formatCurrency, formatDate, formatDatesInText } from "../../utils/formatters";
import { ALASAN_MIN, listReports, tolak } from "../orders/payReport/payReportApi";
import { receiptFromLine } from "../finance/bank/bankLineReceiptApi";
import { badgeLabel } from "../sales_admin/workDeskApi";
import DeskDocPanel from "./DeskDocPanel";
import { permsOf } from "./deskPerms";

/** Status laporan bayar yang masih menunggu keputusan Finance (`payment_report_service.TERTUNDA`). */
const TERTUNDA = ["menunggu", "memproses"];
/** "Cocok sempurna" F1 — selisih nominal di bawah Rp 1 (server `SELISIH_COCOK`). */
const SELISIH_COCOK = 1;

/** Keterangan baris tanpa alasan di ujungnya (alasan sudah tampil di bilah alasan panel); tanggal mutasi dari server
 *  ("2026-11-27 · BCA … · KN-…") ditulis dengan pemformat tanggal baku ("27 Nov 2026"). */
function keteranganMutasi(row) {
  const sub = String(row?.subtitle || "");
  const alasan = String(row?.alasan || "");
  return formatDatesInText(alasan && sub.endsWith(` · ${alasan}`) ? sub.slice(0, -(alasan.length + 3)) : sub);
}

/** Mengapa laporan ini tidak bisa diterima BERSAMA mutasi ini ("" = bisa) — cermin pagar server `_laporan_untuk_mutasi`. */
function hambatanTerima(rep, row) {
  if (Math.abs((Number(rep.amount) || 0) - (Number(row.value) || 0)) >= SELISIH_COCOK) {
    return `Nominal laporan ${formatCurrency(rep.amount)} ≠ mutasi ${formatCurrency(row.value)} — Tolak bila bukan pembayaran ini.`;
  }
  if ((rep.account_id || "") !== (row.bank_account_id || "")) {
    return `Rekening laporan ${rep.account_name || "lain"} ≠ rekening mutasi — Tolak bila bukan pembayaran ini.`;
  }
  return "";
}

export default function BankLineQueuePanel({ row, queue, currentUser, testPrefix = "desk", pt = "", traceEnabled = true,
                                             onClose, onRowChanged }) {
  const p = testPrefix;
  const perms = permsOf(currentUser);
  const lineId = row?.line_id || row?.ref_id || "";
  const orderId = row?.order_id || "";
  const reportId = row?.report_id || "";
  const canDecide = can(perms, "payment_report", "decide");
  const [laporan, setLaporan] = useState({ loading: Boolean(orderId), items: [], loaded: false });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const inFlight = useRef(false);
  const terimaIntent = useIntentKey("f1lapterima");
  const tolakIntent = useIntentKey("f1laptolak");

  const load = useCallback(async () => {
    if (row?.entity_id) {
      // Mode "Semua PT": aksi & muat atas nama PT mutasi (interseptor memakai registri ini; server tetap memeriksa).
      rememberDocEntities([{ id: orderId, entity_id: row.entity_id }, { id: lineId, entity_id: row.entity_id },
        { id: reportId, entity_id: row.entity_id }].filter((x) => x.id));
    }
    if (!orderId) return;
    setLaporan((x) => ({ ...x, loading: true }));
    try {
      const data = await listReports(orderId);
      const items = (data?.items || []).filter((r) => TERTUNDA.includes(r.status));
      // laporan yang disebut kartu (bila ada) di atas
      items.sort((a, b) => Number(b.id === reportId) - Number(a.id === reportId));
      setLaporan({ loading: false, loaded: true, items });
    } catch (e) {
      setLaporan({ loading: false, loaded: false, items: [] });
      setError(apiErrorText(e, "Laporan bayar pesanan ini tidak bisa dimuat."));
    }
  }, [orderId, lineId, reportId, row?.entity_id]);
  useEffect(() => { load(); }, [load]);

  async function terimaLaporan(rep) {
    if (inFlight.current || !rep) return;
    setError("");
    const ok = await askConfirm({
      title: "Terima laporan bayar dengan mutasi ini",
      message: `Laporan ${rep.number} (${formatCurrency(rep.amount)}) diterima dengan mutasi bank `
        + `${formatDate(row.stmt_date)} ${formatCurrency(row.value)} sebagai buktinya: kwitansi terbit dan langsung `
        + "terverifikasi bank."
        + (row.receipt_id ? ` Perhatian: kartu ini menyebut kwitansi yang sudah tercatat (${row.alasan || "lihat alasan"}) `
          + "— pastikan uangnya bukan uang yang sama." : ""),
      confirmLabel: "Ya, terima", cancelLabel: "Batal", testId: `${p}-bankline-accept-confirm`,
    });
    if (!ok) return;
    inFlight.current = true; setBusy(`terima:${rep.id}`);
    const body = { customer_id: row.customer_id || rep.customer_id || "", amount: Number(row.value) || 0,
      method: rep.method || "transfer", payment_report_id: rep.id };
    try {
      const out = await terimaIntent.send({ line: lineId, ...body }, (k) => receiptFromLine(lineId, body, k));
      const lepas = (out?.released_order_ids || []).length ? "Pesanan dilepas ke gudang." : "";
      notifySuccess(`Kwitansi ${out?.receipt?.number || ""} terbit`,
        [`Laporan ${rep.number} diterima dengan mutasi bank.`, lepas].filter(Boolean).join(" "));
      onRowChanged?.(row, queue);
      onClose?.();
    } catch (e) {
      setError(apiErrorText(e, "Laporan belum bisa diterima dengan mutasi ini."));
      load();
    } finally { inFlight.current = false; setBusy(""); }
  }

  async function tolakLaporan(rep) {
    if (inFlight.current || !rep) return;
    setError("");
    const reason = await askReason({ title: `Tolak laporan ${rep.number}?`, danger: true, reasonLabel: "Alasan menolak",
      message: "Tolak bila bukti laporan ini bukan mutasi ini. Pelapor diberi tahu alasannya.",
      reasonMinLength: ALASAN_MIN, confirmLabel: "Tolak laporan", testId: `${p}-bankline-reject-reason` });
    if (reason === null) return;
    inFlight.current = true; setBusy(`tolak:${rep.id}`);
    try {
      await tolakIntent.send({ id: rep.id, reason }, (k) => tolak(rep.id, reason, k));
      notifySuccess("Laporan bayar ditolak", `${rep.number} — kini catat kwitansi dari mutasi ini bila uangnya milik pesanan ini.`);
      onRowChanged?.(row, queue);
      await load();
    } catch (e) {
      setError(apiErrorText(e, "Laporan belum bisa ditolak."));
      load();
    } finally { inFlight.current = false; setBusy(""); }
  }

  const items = laporan.items;
  const tampilLaporan = laporan.loading ? Boolean(orderId) : items.length > 0 || (laporan.loaded && Boolean(reportId));

  return (
    <div className="grid gap-3" data-testid={`${p}-bankline-panel`}>
      <div className="notice-bar warning text-fs-12" data-testid={`${p}-bankline-reason`}>
        <AlertTriangle size={13} className="shrink-0" aria-hidden="true" />
        <span className="min-w-0 break-words">
          <b>{badgeLabel(row.alasan_kode || row.badge) || "Perlu dicek"}:</b> {row.alasan || "mutasi ini belum bisa menjadi kwitansi otomatis."}
        </span>
      </div>
      {row.ref && (
        <p className="text-fs-12 text-kn-text-2" data-testid={`${p}-bankline-ref`}>Referensi bank: {row.ref}</p>
      )}
      <ErrorNotice message={error} onDismiss={() => setError("")} testId={`${p}-bankline-error`} />

      {tampilLaporan && (
        <div className="rounded-md border border-kn-divider p-2.5" data-testid={`${p}-bankline-report`}>
          <p className="text-fs-12 font-bold uppercase tracking-wide text-kn-text-2">Laporan bayar menunggu</p>
          {laporan.loading && <p className="text-fs-12 text-kn-text-2" role="status">Memuat laporan…</p>}
          {!laporan.loading && items.map((rep) => {
            const hambatan = hambatanTerima(rep, row);
            const menunggu = rep.status === "menunggu";
            return (
              <div key={rep.id} className="mt-1.5 border-t border-kn-divider pt-1.5 first:border-t-0 first:pt-0"
                data-testid={`${p}-bankline-report-${rep.id}`}>
                <p className="text-fs-13 font-semibold text-kn-text">
                  {rep.number} · <span className="tabular-nums">{formatCurrency(rep.amount)}</span>
                </p>
                <p className="text-fs-12 text-kn-text-2">
                  Transfer {formatDate(rep.transfer_date)} · {rep.account_name || "rekening"}
                  {rep.created_by_name ? ` · dilapor ${rep.created_by_name}` : ""}
                </p>
                {canDecide && menunggu && (
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    {!hambatan && (
                      <button type="button" className="primary-button btn-sm" disabled={Boolean(busy)}
                        data-testid={`${p}-bankline-accept-report-${rep.id}`} onClick={() => terimaLaporan(rep)}>
                        <CheckCircle2 size={13} aria-hidden="true" /> {busy === `terima:${rep.id}` ? "Memproses…" : "Terima laporan ini dengan mutasi ini"}
                      </button>
                    )}
                    <button type="button" className="secondary-button btn-sm" disabled={Boolean(busy)}
                      data-testid={`${p}-bankline-reject-report-${rep.id}`} onClick={() => tolakLaporan(rep)}>
                      <XCircle size={13} aria-hidden="true" /> Tolak
                    </button>
                  </div>
                )}
                {(!canDecide || !menunggu || hambatan) && (
                  <p className="mt-1 text-fs-12 text-kn-text-2" data-testid={`${p}-bankline-report-note-${rep.id}`}>
                    {!canDecide ? "Terima/Tolak laporan bayar hanya untuk pemutus Lapor Bayar."
                      : !menunggu ? "Laporan ini sedang diproses — putuskan di antrean Lapor bayar."
                      : hambatan}
                  </p>
                )}
              </div>
            );
          })}
          {!laporan.loading && laporan.loaded && items.length === 0 && (
            <p className="text-fs-12 text-kn-text-2" data-testid={`${p}-bankline-report-gone`}>
              Laporan yang disebut kartu ini sudah tidak menunggu — kemungkinan sudah diputus. Muat ulang kartu untuk melihat keadaan terbaru.
            </p>
          )}
        </div>
      )}

      {row.receipt_id && (
        <p className="text-fs-12 text-kn-text-2" data-testid={`${p}-bankline-receipt-note`}>
          Kartu ini menyebut kwitansi yang sudah tercatat, jadi "Catat kwitansi" tidak ditawarkan supaya uang yang sama
          tidak tercatat dua kali. Periksa dan cocokkan di Rekonsiliasi Bank.
        </p>
      )}
      <p className="text-fs-12 text-kn-text-2" data-testid={`${p}-bankline-options`}>
        Pilihan lain — titipkan, abaikan, cocokkan manual — ada di Rekonsiliasi Bank (tombol Buka Rekonsiliasi di bawah).
      </p>

      <DeskDocPanel row={{ ...row, subtitle: keteranganMutasi(row) }} queue={queue} currentUser={currentUser} docType="sales_order"
        docId={orderId} testPrefix={p} pt={pt} traceEnabled={traceEnabled} />
    </div>
  );
}
