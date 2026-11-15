/**
 * TransferListPanel — PY-T4 (PY-11) · daftar transfer gaji per karyawan (pop-up rincian, `DetailModal`).
 *
 * Sumber: GET /api/hr/payroll/runs/{id}/transfer-list (`payroll.pay`) — daftar diturunkan dari slip proses itu (tidak
 * disimpan), jumlahnya = gaji bersih proses. "Unduh Excel" = GET …/transfer-list/export (berkas
 * `transfer-gaji-<nomor>.xlsx`; server mencatat pengunduhan di jejak audit tanpa nominal).
 *
 * Kolom: No. · Nama penerima · Bank · Nomor rekening · Nominal · Slip (6 kolom, muat di pop-up 896 px; kartu HP bergulir
 * di wadahnya). Baris tanpa nomor rekening bertanda "Tanpa rekening — bayar tunai" (ikon + teks + warna). Kaki:
 * "Total Rp … · {n} penerima". Memuat · galat (+ Coba lagi) · kosong dibedakan.
 */
import { useCallback, useEffect, useState } from "react";
import { Banknote, Download, ListChecks } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import DetailModal from "../../components/DetailModal";
import ErrorNotice from "../../components/ErrorNotice";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatDate, formatPeriod } from "../../utils/formatters";

export const TEKS_TUNAI = "Tanpa rekening — bayar tunai";

/** "Total Rp … · {n} penerima" (kaki tabel). */
export const kakiTransfer = (data) => `Total ${formatCurrency(data?.total || 0)} · ${data?.count || 0} penerima`;

/** Unduh berkas Excel daftar transfer (blob; nama dari Content-Disposition). */
export async function unduhDaftarTransfer(runId) {
  const r = await axios.get(`${API}/hr/payroll/runs/${runId}/transfer-list/export`, { responseType: "blob" });
  const cd = String(r.headers?.["content-disposition"] || "");
  const m = /filename="([^"]+)"/.exec(cd);
  const url = URL.createObjectURL(r.data);
  const a = document.createElement("a");
  a.href = url; a.download = m ? m[1] : `transfer-gaji-${runId}.xlsx`; a.click();
  URL.revokeObjectURL(url);
}

export default function TransferListPanel({ runId, open = true, onClose }) {
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading");   // loading | error | ready
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [dlErr, setDlErr] = useState("");

  const load = useCallback(async () => {
    if (!runId) return;
    setState("loading");
    try {
      const r = await axios.get(`${API}/hr/payroll/runs/${runId}/transfer-list`);
      setData(r.data || null); setErr(""); setState("ready");
    } catch (e) { setErr(apiErrorText(e) || ""); setState("error"); }
  }, [runId]);
  useEffect(() => { if (open) load(); }, [open, load]);

  const unduh = async () => {
    setBusy(true); setDlErr("");
    try { await unduhDaftarTransfer(runId); } catch (e) { setDlErr(apiErrorText(e) || "Unduhan gagal."); }
    finally { setBusy(false); }
  };

  const run = data?.run || {};
  const items = data?.items || [];
  const acc = data?.pay_account;
  return (
    <DetailModal open={open} onClose={onClose} size="lg" label="Daftar transfer gaji" testId="transfer-modal" framed>
      <div className="space-y-3" data-testid="transfer-panel">
        <div className="flex flex-wrap items-start gap-2 pr-6">
          <h2 className="flex items-center gap-2 text-fs-16 font-bold text-kn-text" data-testid="transfer-title">
            <ListChecks size={16} className="text-kn-action" aria-hidden="true" />
            Daftar transfer{run.number ? ` ${run.number}` : ""}{run.period ? ` · ${formatPeriod(run.period)}` : ""}</h2>
        </div>
        {state === "ready" && (
          <div className="flex flex-wrap items-center gap-2" data-testid="transfer-bar">
            <p className="text-fs-12 text-kn-text-2" data-testid="transfer-source">
              {acc ? `Dibayar ${data.paid_date ? formatDate(data.paid_date) : ""} dari ${acc.name}${acc.account_number ? ` (${acc.bank_name || ""} ${acc.account_number})` : ""}.`
                : "Belum dibayar. Daftar ini bisa diunduh untuk disiapkan di bank sebelum menekan Bayar."}</p>
            <button type="button" data-testid="transfer-download" disabled={busy || items.length === 0} onClick={unduh}
              className="secondary-button btn-sm ml-auto whitespace-nowrap"><Download size={13} aria-hidden="true" />
              {busy ? "Menyiapkan…" : "Unduh Excel"}</button>
          </div>
        )}
        {dlErr && <ErrorNotice testId="transfer-download-error" message={dlErr} onDismiss={() => setDlErr("")} />}
        {state === "loading" ? (
          <p className="py-6 text-center text-fs-13 text-kn-text-2" role="status" data-testid="transfer-loading">Memuat daftar transfer…</p>
        ) : state === "error" ? (
          <ErrorNotice testId="transfer-error" message={`Daftar transfer tidak bisa dimuat. ${err}`.trim()} onRetry={load} />
        ) : items.length === 0 ? (
          <p className="py-6 text-center text-fs-13 text-kn-text-2" data-testid="transfer-empty">Penggajian ini tidak memuat slip.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table head-wrap w-full" data-testid="transfer-table">
              <thead><tr>
                <th className="text-right">No.</th><th>Nama penerima</th><th>Bank</th><th>Nomor rekening</th>
                <th className="text-right">Nominal</th><th>Slip</th>
              </tr></thead>
              <tbody>
                {items.map((it) => (
                  <tr key={it.employee_id || it.no} data-testid={`transfer-row-${it.no}`}>
                    <td className="text-right tabular-nums">{it.no}</td>
                    <td className="min-w-[140px] break-words">{it.account_holder || it.employee_name}
                      {it.account_holder && it.account_holder !== it.employee_name && <span className="block text-fs-12 text-kn-text-2">{it.employee_name}</span>}</td>
                    {it.cash ? (
                      <td colSpan={2} data-testid={`transfer-cash-${it.no}`}>
                        <span className="status-pill status-pending inline-flex items-center gap-1 whitespace-nowrap">
                          <Banknote size={12} aria-hidden="true" />{TEKS_TUNAI}</span></td>
                    ) : (<>
                      <td className="whitespace-nowrap">{it.bank_name || "—"}</td>
                      <td className="font-mono whitespace-nowrap">{it.account_number}</td>
                    </>)}
                    <td className="text-right tabular-nums whitespace-nowrap">{formatCurrency(it.amount)}</td>
                    <td className="font-mono whitespace-nowrap text-fs-12">{it.slip_number || "—"}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot><tr>
                <td colSpan={6} className="text-right font-bold" data-testid="transfer-foot">{kakiTransfer(data)}
                  {data.without_account > 0 && <span className="ml-2 font-normal text-fs-12 text-kn-text-2">({data.without_account} dibayar tunai)</span>}</td>
              </tr></tfoot>
            </table>
          </div>
        )}
      </div>
    </DetailModal>
  );
}
