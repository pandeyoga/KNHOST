/**
 * BudgetCheckNotice & BudgetPreview — PK-39 (FY-12, K-12) · hasil pemeriksaan anggaran di dalam form / pop-up.
 *
 *   <BudgetCheckNotice check={doc.budget_check} />     hasil yang tersimpan di dokumen (kas, tagihan, LPJ)
 *   <BudgetPreview entityId source="cash_out" category amount date />   pratinjau SEBELUM disimpan (form kas)
 *
 * Pemeriksaannya di server (`budget_service.enforce_budget`); komponen ini hanya menampilkan. Mode "Tolak bila
 * melampaui" menolak simpan dengan pesan 400 yang tampil di galat pop-up pemanggil. Peran tanpa izin `budget.view`
 * tidak melihat pratinjau (403 → disembunyikan), tetapi tetap melihat peringatan yang tersimpan di dokumen.
 * Ikon + teks + warna (bukan warna saja); warna lewat token `kn-*`.
 */
import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, ShieldOff } from "lucide-react";
import axios, { API } from "../services/apiClient";
import { formatCurrency } from "../utils/formatters";

export function BudgetCheckNotice({ check, testId = "budget-check-notice" }) {
  const warnings = check?.warnings || [];
  if (!check || check.skipped || warnings.length === 0) return null;
  return (
    <div className="notice-bar warning items-start" role="status" data-testid={testId}>
      <AlertTriangle size={14} className="mt-0.5 shrink-0" />
      <div className="grid gap-0.5 text-fs-12">
        <b>Peringatan anggaran{check.mode_label ? ` · ${check.mode_label}` : ""}</b>
        {warnings.map((w, i) => <span key={i} data-testid={`${testId}-${i}`}>{w}</span>)}
      </div>
    </div>
  );
}

export function BudgetPreview({ entityId = "", source = "cash_out", category = "", amount = 0, date = "",
  testId = "budget-preview" }) {
  const [res, setRes] = useState(null);
  useEffect(() => {
    const nominal = Number(amount) || 0;
    if (nominal <= 0) { setRes(null); return undefined; }
    let batal = false;
    const t = setTimeout(() => {
      axios.post(`${API}/finance/budget-check`, {
        ...(entityId && entityId !== "all" ? { entity_id: entityId } : {}), source, category, amount: nominal,
        date: date || "", key: "",
      }).then((r) => { if (!batal) setRes(r.data || null); })
        .catch(() => { if (!batal) setRes(null); });   // 403 (tanpa izin lihat anggaran) / galat → tanpa pratinjau
    }, 450);
    return () => { batal = true; clearTimeout(t); };
  }, [entityId, source, category, amount, date]);

  if (!res || res.applies === false) return null;
  const off = res.mode === "off";
  const Icon = off ? ShieldOff : (res.over || res.warning ? AlertTriangle : CheckCircle2);
  const cls = off ? "info" : (res.blocked ? "danger" : (res.over || res.warning ? "warning" : "success"));
  const judul = off ? "Pemeriksaan anggaran mati"
    : res.blocked ? "Akan ditolak: melampaui anggaran"
      : res.over ? "Melampaui anggaran — tetap bisa disimpan dengan peringatan"
        : res.warning ? "Mendekati batas anggaran" : "Masih dalam anggaran";
  return (
    <div className={`notice-bar ${cls} items-start`} role="status" data-testid={testId}>
      <Icon size={14} className="mt-0.5 shrink-0" />
      <div className="grid gap-0.5 text-fs-12">
        <b data-testid={`${testId}-title`}>{judul}</b>
        {res.has_budget ? (
          <span className="tabular-nums">
            {res.label} ({res.key}) · pagu {formatCurrency(res.budget)} − realisasi {formatCurrency(res.actual)} −
            komitmen {formatCurrency(res.committed)} = sisa {formatCurrency(res.available)} · sesudah transaksi ini
            {" "}{formatCurrency(res.available_after)}
          </span>
        ) : (
          <span>{res.warning || `Belum ada pagu ${res.label || res.key} untuk ${res.year}.`}</span>
        )}
      </div>
    </div>
  );
}

export default BudgetCheckNotice;
