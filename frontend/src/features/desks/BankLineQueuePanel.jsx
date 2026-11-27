/**
 * BankLineQueuePanel (F1, rancangan kwitansi otomatis dari mutasi §5.4–§5.5) — panel pop-up antrean `mutasi_berkode` di
 * Meja Keuangan (kelompok "Uang masuk perlu dicatat"): mutasi bank berkode bayar yang TIDAK cocok sempurna (kartu
 * beralasan). Isi, dalam SATU pop-up meja (tidak ada `DetailModal` kedua):
 *  · atas — alasan kartu (`f1.alasan`) + referensi bank mutasi;
 *  · laporan bayar yang menunggu untuk pesanan itu (`report_id`): "Terima laporan ini dengan mutasi ini" (laporan diterima
 *    dengan mutasi ini sebagai buktinya — `receiptFromLine` dengan `payment_report_id`, satu permintaan atomik) dan
 *    "Tolak" (alasan; aturan Lapor Bayar yang ada). Hanya pemegang `payment_report.decide` (server pun menuntutnya);
 *  · "Buka Rekonsiliasi" — pilihan lain (titipkan, abaikan, cocokkan manual) di Rekonsiliasi Bank;
 *  · bawah — pratinjau pesanan kode bayar dari registri (`DeskDocPanel` → Body `sales_order`).
 * "Catat kwitansi" = tombol kaki pop-up (`DeskRowDetail`, aksi di tempat): pop-up menutup lalu meja membuka form Terima
 * pembayaran terisi dari mutasi (`bankLineId`) — satu pop-up pada satu waktu.
 * Sukses Terima → toast + `onRowChanged` + pop-up menutup. Tolak → toast + kartu dimuat ulang, pop-up tetap (lanjut Catat
 * kwitansi). Galat → bilah galat di dalam panel; pop-up tetap terbuka dan laporan dimuat ulang.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, ExternalLink, XCircle } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import { can } from "../../config/roles";
import { rememberDocEntities } from "../../services/docEntityRegistry";
import { askConfirm, askReason } from "../../services/confirmService";
import useIntentKey from "../../hooks/useIntentKey";
import { apiErrorText } from "../../utils/apiError";
import { notifySuccess } from "../../utils/feedback";
import { formatCurrency, formatDate } from "../../utils/formatters";
import { ALASAN_MIN, listReports, tolak } from "../orders/payReport/payReportApi";
import { receiptFromLine } from "../finance/bank/bankLineReceiptApi";
import { badgeLabel } from "../sales_admin/workDeskApi";
import DeskDocPanel from "./DeskDocPanel";
import { permsOf } from "./deskPerms";

/** Keterangan baris tanpa alasan di ujungnya (alasan sudah tampil di bilah alasan panel). */
function tanpaAlasan(row) {
  const sub = String(row?.subtitle || "");
  const alasan = String(row?.alasan || "");
  return alasan && sub.endsWith(` · ${alasan}`) ? sub.slice(0, -(alasan.length + 3)) : sub;
}

export default function BankLineQueuePanel({ row, queue, currentUser, testPrefix = "desk", pt = "", traceEnabled = true,
                                             onClose, onOpenFull, onRowChanged }) {
  const p = testPrefix;
  const perms = permsOf(currentUser);
  const lineId = row?.line_id || row?.ref_id || "";
  const orderId = row?.order_id || "";
  const reportId = row?.report_id || "";
  const canDecide = can(perms, "payment_report", "decide");
  const [laporan, setLaporan] = useState({ loading: Boolean(reportId && orderId), item: null, loaded: false });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const inFlight = useRef(false);
  const terimaIntent = useIntentKey("f1lapterima");
  const tolakIntent = useIntentKey("f1laptolak");

  const load = useCallback(async () => {
    if (row?.entity_id) {
      // Mode "Semua PT": aksi & muat atas nama PT mutasi (interseptor memakai registri ini; server tetap memeriksa).
      rememberDocEntities([{ id: orderId, entity_id: row.entity_id }, { id: lineId, entity_id: row.entity_id },
        { id: reportId, entity_id: row.entity_id }]);
    }
    if (!reportId || !orderId) return;
    setLaporan((x) => ({ ...x, loading: true }));
    try {
      const data = await listReports(orderId);
      setLaporan({ loading: false, loaded: true, item: (data?.items || []).find((r) => r.id === reportId) || null });
    } catch (e) {
      setLaporan({ loading: false, loaded: false, item: null });
      setError(apiErrorText(e, "Laporan bayar pesanan ini tidak bisa dimuat."));
    }
  }, [orderId, lineId, reportId, row?.entity_id]);
  useEffect(() => { load(); }, [load]);

  const rep = laporan.item;
  // Hanya laporan `menunggu` yang bisa diterima bersama mutasi (server menolak yang sedang diproses).
  const bisaPutus = canDecide && rep && rep.status === "menunggu";

  async function terimaLaporan() {
    if (inFlight.current || !rep) return;
    setError("");
    const ok = await askConfirm({
      title: "Terima laporan bayar dengan mutasi ini",
      message: `Laporan ${rep.number} (${formatCurrency(rep.amount)}) diterima dengan mutasi bank `
        + `${formatDate(row.stmt_date)} ${formatCurrency(row.value)} sebagai buktinya: kwitansi terbit dan langsung `
        + "terverifikasi bank.",
      confirmLabel: "Ya, terima", cancelLabel: "Batal", testId: `${p}-bankline-accept-confirm`,
    });
    if (!ok) return;
    inFlight.current = true; setBusy("terima");
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

  async function tolakLaporan() {
    if (inFlight.current || !rep) return;
    setError("");
    const reason = await askReason({ title: `Tolak laporan ${rep.number}?`, danger: true, reasonLabel: "Alasan menolak",
      message: "Tolak bila bukti laporan ini bukan mutasi ini. Pelapor diberi tahu alasannya.",
      reasonMinLength: ALASAN_MIN, confirmLabel: "Tolak laporan", testId: `${p}-bankline-reject-reason` });
    if (reason === null) return;
    inFlight.current = true; setBusy("tolak");
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

      {reportId && (
        <div className="rounded-md border border-kn-divider p-2.5" data-testid={`${p}-bankline-report`}>
          <p className="text-fs-12 font-bold uppercase tracking-wide text-kn-text-2">Laporan bayar menunggu</p>
          {laporan.loading && <p className="text-fs-12 text-kn-text-2" role="status">Memuat laporan…</p>}
          {rep && (
            <>
              <p className="text-fs-13 font-semibold text-kn-text">
                {rep.number} · <span className="tabular-nums">{formatCurrency(rep.amount)}</span>
              </p>
              <p className="text-fs-12 text-kn-text-2">
                Transfer {formatDate(rep.transfer_date)} · {rep.account_name || "rekening"}
                {rep.created_by_name ? ` · dilapor ${rep.created_by_name}` : ""}
              </p>
              {bisaPutus ? (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <button type="button" className="primary-button btn-sm" disabled={Boolean(busy)}
                    data-testid={`${p}-bankline-accept-report`} onClick={terimaLaporan}>
                    <CheckCircle2 size={13} aria-hidden="true" /> {busy === "terima" ? "Memproses…" : "Terima laporan ini dengan mutasi ini"}
                  </button>
                  <button type="button" className="secondary-button btn-sm" disabled={Boolean(busy)}
                    data-testid={`${p}-bankline-reject-report`} onClick={tolakLaporan}>
                    <XCircle size={13} aria-hidden="true" /> Tolak
                  </button>
                </div>
              ) : (
                <p className="mt-1 text-fs-12 text-kn-text-2" data-testid={`${p}-bankline-report-note`}>
                  {!canDecide ? "Terima/Tolak laporan bayar hanya untuk pemutus Lapor Bayar."
                    : rep.status === "memproses" ? "Laporan ini sedang diproses — putuskan di antrean Lapor bayar."
                    : "Laporan ini sudah tidak menunggu keputusan."}
                </p>
              )}
            </>
          )}
          {!laporan.loading && laporan.loaded && !rep && (
            <p className="text-fs-12 text-kn-text-2" data-testid={`${p}-bankline-report-gone`}>
              Laporan ini sudah tidak ada di daftar — kemungkinan sudah diputus. Muat ulang kartu untuk melihat keadaan terbaru.
            </p>
          )}
        </div>
      )}

      {onOpenFull && (
        <p className="flex flex-wrap items-center gap-2 text-fs-12 text-kn-text-2">
          Pilihan lain — titipkan, abaikan, cocokkan manual — ada di Rekonsiliasi Bank.
          <button type="button" className="link-button" data-testid={`${p}-bankline-open-recon`}
            onClick={() => { onClose?.(); onOpenFull(row, queue); }}>
            Buka Rekonsiliasi <ExternalLink size={12} className="ml-1" aria-hidden="true" />
          </button>
        </p>
      )}

      <DeskDocPanel row={{ ...row, subtitle: tanpaAlasan(row) }} queue={queue} currentUser={currentUser} docType="sales_order"
        docId={orderId} testPrefix={p} pt={pt} traceEnabled={traceEnabled} />
    </div>
  );
}
