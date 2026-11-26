/**
 * PayReportQueuePanel (LB-T8) — panel pop-up antrean `lapor_bayar` di Meja Keuangan (kelompok "Uang masuk perlu dicatat").
 * Isi, dalam SATU pop-up meja (tidak ada `DetailModal` kedua):
 *  · atas — laporan bayar itu: nominal, tanggal transfer, rekening, pelapor, bukti (blob), Terima / Tolak. Memakai
 *    `PayReportList` Tugas 7 apa adanya (satu sumber: pratinjau kwitansi, `moneyPost` + kunci idempotensi, alasan tolak);
 *  · bawah — pratinjau pesanan dari registri (`DeskDocPanel` → Body `sales_order`).
 * Sukses → toast (dari `PayReportList`) + `onRowChanged(row, queue)` (meja memuat ulang kartunya diam-diam) + pop-up menutup.
 * Galat → bilah galat di dalam panel; pop-up tetap terbuka dan laporan dimuat ulang (mis. sudah diputus orang lain).
 * Hanya pemegang `payment_report.decide` melihat baris ini (server tidak mengirimnya ke yang lain; meja ikut menyaring).
 */
import { useCallback, useEffect, useState } from "react";
import ErrorNotice from "../../components/ErrorNotice";
import { can } from "../../config/roles";
import { rememberDocEntities } from "../../services/docEntityRegistry";
import { apiErrorText } from "../../utils/apiError";
import PayReportList from "../orders/payReport/PayReportList";
import { listReports } from "../orders/payReport/payReportApi";
import DeskDocPanel from "./DeskDocPanel";
import { permsOf } from "./deskPerms";

export default function PayReportQueuePanel({ row, queue, currentUser, testPrefix = "desk", pt = "", traceEnabled = true,
                                              onClose, onRowChanged }) {
  const perms = permsOf(currentUser);
  const orderId = row?.order_id || "";
  const [data, setData] = useState(null);      // { items, bisa_putuskan } | null
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!orderId) { setLoading(false); return; }
    // Mode "Semua PT": aksi & muat laporan atas nama PT pesanannya (interseptor memakai registri ini; server tetap memeriksa).
    if (row.entity_id) rememberDocEntities([{ id: orderId, entity_id: row.entity_id }, { id: row.ref_id, entity_id: row.entity_id }]);
    try {
      setData(await listReports(orderId)); setError("");
    } catch (e) { setError(apiErrorText(e, "Laporan bayar tidak bisa dimuat.")); }
    finally { setLoading(false); }
  }, [orderId, row.entity_id, row.ref_id]);
  useEffect(() => { load(); }, [load]);

  const report = (data?.items || []).find((r) => r.id === row.ref_id) || null;
  const canDecide = can(perms, "payment_report", "decide") && data?.bisa_putuskan !== false;

  const changed = (info) => {
    if (info?.ok) { onRowChanged?.(row, queue); onClose?.(); } else load();
  };

  return (
    <div className="grid gap-3" data-testid={`${testPrefix}-payreport-panel`}>
      {error && <ErrorNotice message={error} onRetry={load} testId={`${testPrefix}-payreport-error`} />}
      {loading && <p className="py-2 text-center text-fs-12 text-kn-text-2" role="status">Memuat laporan…</p>}
      {report && <PayReportList reports={[report]} canDecide={canDecide} onChanged={changed} />}
      {!loading && !error && data && !report && (
        <p className="notice-bar info text-fs-12" data-testid={`${testPrefix}-payreport-gone`}>
          Laporan ini sudah tidak ada di daftar — kemungkinan sudah diputus. Muat ulang kartu untuk melihat keadaan terbaru.
        </p>
      )}
      <DeskDocPanel row={row} queue={queue} currentUser={currentUser} docType="sales_order" docId={orderId}
        testPrefix={testPrefix} pt={pt} traceEnabled={traceEnabled} />
    </div>
  );
}
