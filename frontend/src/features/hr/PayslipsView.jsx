/**
 * PayslipsView — daftar & rincian slip gaji. PY-T1: dipakai panel "Cari slip" di Proses Gaji (`embedded`), menggantikan
 * tab Slip Gaji (id lama `hr-payslips` = alias ke Proses Gaji; rute cadangan merender Proses Gaji dengan panel terbuka).
 *
 * Rincian slip = DAFTAR KOMPONEN (Pendapatan · Potongan · Tanggungan perusahaan), bukan empat baris tetap; slip lama tanpa
 * komponen disusun dari kolomnya. Cari per nama karyawan atau periode; saringan periode di server. Sumber:
 * GET /api/hr/payslips?entity_id&period · GET /api/hr/payslips/{id}/pdf.
 */
import { useEffect, useMemo, useState } from "react";
import apiErrorText from "../../utils/apiError";
import axios, { API } from "../../services/apiClient";
import { Receipt, RefreshCw, FileText, Building2 } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import EntityBadge from "../../components/EntityBadge";
import ErrorNotice from "../../components/ErrorNotice";
import useListSearch from "@/hooks/useListSearch";
import { rp, pct, recentMonths, openPayslipPdf, runTypeLabel, slipDeductions, slipGroups } from "./payrollUtils";
import { formatPeriod } from "../../utils/formatters";

/** Rincian satu slip: komponen dikelompokkan, total, gaji bersih. Diekspor untuk uji. */
export function SlipDetail({ slip, busy, onPdf }) {
  const groups = slipGroups(slip);
  return (
    <div data-testid="payslip-detail">
      <div className="px-3 py-3 border-b border-kn-divider">
        <p className="text-fs-14 font-bold flex items-center gap-1"><Building2 size={14} className="text-kn-text-2" aria-hidden="true" /> {slip.employee_name}</p>
        <p className="text-fs-12 text-kn-text-2">{slip.number} · {formatPeriod(slip.period)} · {runTypeLabel(slip.run_type)} · PTKP {slip.ptkp_status}{slip.ter_category ? ` · kategori TER ${slip.ter_category}` : ""}</p>
      </div>
      <div className="px-3 py-2 space-y-2">
        {groups.map((g) => (
          <div key={g.key} data-testid={`payslip-detail-group-${g.key}`}>
            <p className="text-fs-12 font-bold text-kn-text-2 mt-1">{g.label}</p>
            {g.rows.length === 0 ? <p className="text-fs-12 text-kn-text-2">—</p> : g.rows.map((c, i) => (
              <div key={`${c.code}-${i}`} className="flex items-start justify-between gap-2 py-0.5 text-fs-13">
                <span className="min-w-0 break-words text-kn-text">{c.label}{c.code === "PPH21" && slip.pph21_method !== "annual_pasal17" && c.rate != null ? ` (${pct(Number(c.rate) / 100)})` : ""}{c.code === "PPH21" && slip.pph21_method === "annual_pasal17" ? " (hitung ulang tahunan)" : ""}</span>
                <span className="tabular-nums whitespace-nowrap">{rp(c.amount)}</span>
              </div>
            ))}
          </div>
        ))}
        <div className="flex items-center justify-between border-t border-kn-divider pt-2 text-fs-13 font-bold"><span>Penghasilan bruto</span><span className="tabular-nums text-kn-action">{rp(slip.gross)}</span></div>
        <div className="rounded-lg bg-kn-action px-3 py-2 flex items-center justify-between">
          <span className="text-fs-13 font-bold text-white">Gaji bersih diterima</span>
          <span className="text-fs-14 font-bold text-white tabular-nums" data-testid="payslip-detail-net">{rp(slip.net)}</span>
        </div>
        <button type="button" data-testid="payslip-detail-pdf" disabled={busy} onClick={() => onPdf(slip.id)} className="primary-button btn-sm w-full justify-center whitespace-nowrap"><FileText size={13} /> {busy ? "Membuka..." : "Unduh / Lihat PDF"}</button>
      </div>
    </div>
  );
}

export default function PayslipsView({ selectedEntity, embedded = false }) {
  const [rows, setRows] = useState([]);
  const srch = useListSearch(rows, ["employee_name", "period", "number"], { testId: "payslips", placeholder: "Cari slip: nama karyawan atau periode (mis. 2026-10)…" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [period, setPeriod] = useState("");
  const [sel, setSel] = useState(null);
  const [busy, setBusy] = useState(false);

  const params = useMemo(() => (selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {}), [selectedEntity]);

  useEffect(() => { load(); }, [period, selectedEntity]); // eslint-disable-line
  async function load() {
    setLoading(true);
    try { const r = await axios.get(`${API}/hr/payslips`, { params: { ...params, ...(period ? { period } : {}) } }); setRows(Array.isArray(r.data) ? r.data : []); setError(""); }
    catch (e) { setError(apiErrorText(e, "Gagal memuat slip gaji.")); }
    finally { setLoading(false); }
  }
  async function pdf(id) { setBusy(true); try { await openPayslipPdf(id); } catch (e) { setError(apiErrorText(e, "PDF slip gagal dibuka.")); } finally { setBusy(false); } }

  const periodOpts = [{ value: "", label: "Semua periode" }, ...recentMonths().map((m) => ({ value: m, label: formatPeriod(m) }))];

  return (
    <div data-testid="payslips-view">
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="payslips-error" />
      <div className={`flex flex-wrap items-end gap-2 ${embedded ? "mb-2" : "section-card section-pad mb-3"}`}>
        {!embedded && <h2 className="flex items-center gap-2 mr-auto" data-testid="payslips-title"><Receipt size={16} className="text-kn-action" aria-hidden="true" />Slip Gaji Karyawan</h2>}
        <div className="w-[180px]"><label className="field-label">Periode</label>
          <KNSelect data-testid="payslips-period" value={period} onValueChange={setPeriod} className="field" options={periodOpts} /></div>
        <button type="button" data-testid="payslips-refresh" onClick={load} className="secondary-button btn-sm whitespace-nowrap"><RefreshCw size={13} /> Muat ulang</button>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_340px]">
        <div className="section-card min-w-0">
          {srch.toolbar}
          {loading ? (
            <div className="section-pad text-center text-fs-12 text-kn-text-2" data-testid="payslips-loading" role="status">Memuat...</div>
          ) : srch.shown.length === 0 ? (
            <div className="section-pad text-center text-fs-12 text-kn-text-2" data-testid="payslips-empty"><Receipt className="mx-auto mb-2 text-kn-text-2" size={26} aria-hidden="true" />
              <p>{rows.length === 0 ? "Belum ada slip gaji. Hitung penggajian dulu di atas." : "Tidak ada slip yang cocok dengan pencarian."}</p></div>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table head-wrap w-full tabular-nums" data-testid="payslips-table">
                <thead><tr>
                  <th className="text-left">Karyawan</th><th className="text-left">Periode</th><th className="text-left">Jenis</th>
                  <th className="text-right">Pendapatan</th><th className="text-right">Potongan + PPh 21</th><th className="text-right">Gaji bersih</th>
                </tr></thead>
                <tbody>
                  {srch.pageRows.map((s) => (
                    <tr key={s.id} data-testid={`payslip-row-${s.id}`} className={`cursor-pointer ${sel?.id === s.id ? "bg-kn-action-soft" : ""}`} onClick={() => setSel(s)}>
                      <td className="text-left"><span className="flex items-center gap-1 min-w-0"><EntityBadge entityId={s.entity_id} /><button type="button" className="link-button text-left font-semibold break-words" onClick={(e) => { e.stopPropagation(); setSel(s); }}>{s.employee_name}</button></span></td>
                      <td className="text-left whitespace-nowrap">{formatPeriod(s.period)}</td>
                      <td className="text-left whitespace-nowrap">{runTypeLabel(s.run_type)}</td>
                      <td className="text-right text-kn-action">{rp(s.gross)}</td>
                      <td className="text-right text-kn-danger-text">{rp(slipDeductions(s) + Number(s.pph21 || 0))}</td>
                      <td className="text-right font-bold text-kn-success-text">{rp(s.net)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {srch.pager && <div className="px-3 py-2 border-t border-kn-divider">{srch.pager}</div>}
        </div>

        <div className="section-card">
          {!sel ? (
            <div className="section-pad text-center text-fs-12 text-kn-text-2" data-testid="payslip-detail-empty"><FileText className="mx-auto mb-2 text-kn-text-2" size={26} aria-hidden="true" /><p>Pilih slip untuk melihat komponennya.</p></div>
          ) : <SlipDetail slip={sel} busy={busy} onPdf={pdf} />}
        </div>
      </div>
    </div>
  );
}
