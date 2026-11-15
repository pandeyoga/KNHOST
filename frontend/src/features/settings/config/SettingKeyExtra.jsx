/**
 * SettingKeyExtra — PY-T3 (L5, L6) · keterangan dan tautan khusus satu kunci di kartu Pusat Pengaturan.
 *
 *  · `hr.overtime.multiplier` — saat "Cara menghitung pengali lembur" = bertingkat, pengali tunggal TIDAK dipakai mesin:
 *    kartu menulisnya (nilai yang tampil bukan nilai yang dipakai).
 *  · `hr.overtime.sumber` — tautan "Lihat dampaknya": menit lembur absensi tanpa pengajuan pada periode berjalan dan
 *    nilainya per karyawan (GET /api/hr/payroll/overtime-impact, izin mengatur penggajian), bahan memutuskan apakah
 *    lembur dibayar dari pengajuan saja.
 *
 * `peers` = butir lain yang sedang dimuat layar (kunci → butir), supaya nilai kunci pasangan tidak diminta ulang.
 */
import { useEffect, useState } from "react";
import { BarChart3, Info } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import DetailModal from "../../../components/DetailModal";
import ErrorNotice from "../../../components/ErrorNotice";
import { apiErrorText } from "../../../utils/apiError";
import { formatCurrency, formatPeriod, todayWib } from "../../../utils/formatters";
import { canCurrent } from "../../../config/roles";

export const KUNCI_KHUSUS = ["hr.overtime.multiplier", "hr.overtime.sumber"];
export const CATATAN_PENGALI = "Tidak dipakai saat ini: cara menghitung pengali lembur = bertingkat. Dipakai hanya bila cara hitung pengali = flat.";

/** Catatan L6 untuk pengali tunggal; "" bila pengali itu memang dipakai (mode flat) atau mode belum termuat. */
export function catatanPengali(peers) {
  const mode = peers?.["hr.overtime.mode"];
  if (!mode) return "";
  return mode.value === "flat" ? "" : CATATAN_PENGALI;
}

function DampakLembur({ entityId, onClose }) {
  const period = String(todayWib()).slice(0, 7);
  const [state, setState] = useState("loading");
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let hidup = true;
    axios.get(`${API}/hr/payroll/overtime-impact`, { params: { period, entity_id: entityId || undefined } })
      .then((r) => { if (hidup) { setData(r.data || {}); setState("ready"); } })
      .catch((e) => { if (hidup) { setErr(apiErrorText(e) || ""); setState("error"); } });
    return () => { hidup = false; };
  }, [entityId, period]);
  const rows = data?.rows || [];
  return (
    <DetailModal open onClose={onClose} size="md" framed label="Dampak lembur dari absensi" testId="cfg-overtime-impact">
      <div className="space-y-3">
        <h3 className="flex items-center gap-2 text-fs-14 font-semibold"><BarChart3 size={14} className="text-kn-action" aria-hidden="true" />Lembur absensi tanpa pengajuan · {formatPeriod(period)}</h3>
        <p className="text-fs-12 text-kn-text-2">Menit lebih di absensi (sudah disetujui, pada tanggal tanpa pengajuan lembur) dan nilainya. Pada pilihan “Pengajuan yang disetujui saja” menit ini tidak dibayar; pada pilihan absensi, dibayar.</p>
        {state === "loading" ? <p className="text-fs-13 text-kn-text-2" role="status">Menghitung dampak…</p>
          : state === "error" ? <ErrorNotice testId="cfg-overtime-impact-error" message={`Dampak lembur tidak bisa dihitung. ${err}`.trim()} />
            : rows.length === 0 ? <p className="text-fs-13 text-kn-text-2" data-testid="cfg-overtime-impact-empty">Tidak ada lembur dari absensi tanpa pengajuan pada periode ini.</p>
              : (
                <div className="overflow-x-auto">
                  <table className="data-table head-wrap w-full" data-testid="cfg-overtime-impact-table">
                    <thead><tr><th>Karyawan</th><th>Hari</th><th>Menit</th><th>Nilai</th></tr></thead>
                    <tbody>
                      {rows.map((r) => (
                        <tr key={r.employee_id}><td className="min-w-[140px]">{r.employee_name}</td><td className="tabular-nums">{r.days}</td>
                          <td className="tabular-nums">{r.minutes}</td><td className="tabular-nums whitespace-nowrap">{formatCurrency(r.amount)}</td></tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="mt-2 text-fs-12 text-kn-text-2" data-testid="cfg-overtime-impact-total">{rows.length} karyawan · {data.total_minutes} menit · {formatCurrency(data.total_amount)}</p>
                </div>
              )}
        <div className="flex justify-end"><button type="button" className="secondary-button btn-sm" onClick={onClose}>Tutup</button></div>
      </div>
    </DetailModal>
  );
}

export default function SettingKeyExtra({ item, peers, scopeType, scopeId }) {
  const [buka, setBuka] = useState(false);
  if (!item || !KUNCI_KHUSUS.includes(item.key)) return null;
  if (item.key === "hr.overtime.multiplier") {
    const teks = catatanPengali(peers);
    return teks ? <p className="cfg-hint-sm flex items-start gap-1" data-testid="cfg-extra-multiplier"><Info size={12} aria-hidden="true" /> {teks}</p> : null;
  }
  const bolehLihat = canCurrent("hr", "manage_payroll");
  const ent = scopeType === "entity" ? scopeId : "";
  return (
    <div className="cfg-hint-sm flex flex-wrap items-center gap-2" data-testid="cfg-extra-overtime-source">
      {bolehLihat && ent ? (
        <button type="button" className="cfg-link-btn" onClick={() => setBuka(true)} data-testid="cfg-overtime-impact-open">
          <BarChart3 size={12} /> Lihat dampaknya
        </button>
      ) : (
        <span data-testid="cfg-overtime-impact-why">{bolehLihat ? "Pilih satu PT di bilah cakupan untuk melihat dampaknya." : "Melihat dampaknya butuh izin mengatur penggajian."}</span>
      )}
      {buka && <DampakLembur entityId={ent} onClose={() => setBuka(false)} />}
    </div>
  );
}
