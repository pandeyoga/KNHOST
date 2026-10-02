import { useEffect, useMemo, useState } from "react";
import { History, ShieldCheck, ShieldAlert, ShieldQuestion, EyeOff, RefreshCw, ArrowRight } from "lucide-react";
import axios, { API } from "../services/apiClient";

const ACTION_LABELS = {
  created: "Dibuat", updated: "Diubah", deleted: "Dihapus", deactivated: "Dinonaktifkan",
  reassigned: "Dipindah sales", address_added: "Alamat ditambah", voided: "Dibatalkan",
};
const SOURCE_SUFFIX = Object.keys(ACTION_LABELS);

function actionLabel(action = "") {
  const key = SOURCE_SUFFIX.find((s) => action.endsWith(`_${s}`) || action === s);
  return key ? ACTION_LABELS[key] : action.replace(/_/g, " ");
}

function fmtTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("id-ID", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Jakarta" }) + " WIB";
  } catch { return iso; }
}

function fmtValue(v) {
  if (v === null || v === undefined || v === "") return <span className="text-[#9A9BA3] italic">kosong</span>;
  if (typeof v === "boolean") return v ? "Ya" : "Tidak";
  if (typeof v === "object") {
    const s = JSON.stringify(v);
    return <span className="font-mono text-[10.5px]" title={s}>{s.length > 80 ? `${s.slice(0, 80)}…` : s}</span>;
  }
  return String(v);
}

const INTEGRITY = {
  ok: { icon: ShieldCheck, label: "Sidik isi cocok", cls: "text-[#1B7F4B] bg-[#E6F6EC]" },
  mismatch: { icon: ShieldAlert, label: "Sidik isi TIDAK cocok — catatan berubah", cls: "text-[#C0392B] bg-[#FDEDE7]" },
  unsigned: { icon: ShieldQuestion, label: "Catatan lama tanpa sidik", cls: "text-[#6B6B73] bg-[#F5F5F7]" },
};

function IntegrityBadge({ status, testId }) {
  const m = INTEGRITY[status] || INTEGRITY.unsigned;
  const Icon = m.icon;
  return (
    <span data-testid={testId} title={m.label} className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9.5px] font-bold ${m.cls}`}>
      <Icon size={11} />{status === "ok" ? "Utuh" : status === "mismatch" ? "Berubah" : "Tanpa sidik"}
    </span>
  );
}

function DiffTable({ diff, testId }) {
  if (!diff?.length) return <p className="text-[11px] text-[#9A9BA3]" data-testid={`${testId}-nodiff`}>Tidak ada nilai sebelum/sesudah yang terekam.</p>;
  return (
    <table className="w-full text-[11px]" data-testid={`${testId}-diff`}>
      <thead>
        <tr className="text-left text-[9.5px] uppercase tracking-wide text-[#8E8E93]">
          <th className="py-1 pr-2 w-[28%]">Field</th><th className="py-1 pr-2">Nilai lama</th><th className="w-4" /><th className="py-1">Nilai baru</th>
        </tr>
      </thead>
      <tbody>
        {diff.map((d) => (
          <tr key={d.field} className="border-t border-[#F2F2F5] align-top" data-testid={`${testId}-field-${d.field}`}>
            <td className="py-1 pr-2 font-semibold text-[#3C3C43]">
              {d.field}
              {d.masked && <span className="ml-1 inline-flex items-center gap-0.5 rounded bg-[#FFF4E0] px-1 text-[9px] font-bold text-[#B45309]" data-testid={`${testId}-masked-${d.field}`}><EyeOff size={9} />disamarkan</span>}
            </td>
            <td className="py-1 pr-2 text-[#C0392B] line-through decoration-[#C0392B]/40" data-testid={`${testId}-from-${d.field}`}>{fmtValue(d.from)}</td>
            <td className="py-1"><ArrowRight size={11} className="text-[#9A9BA3]" /></td>
            <td className="py-1 text-[#1B7F4B] font-medium" data-testid={`${testId}-to-${d.field}`}>{fmtValue(d.to)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function HistoryRow({ row, testId, showLayer }) {
  return (
    <li className="relative pl-5 pb-4 last:pb-0" data-testid={testId}>
      <span className="absolute left-[5px] top-1.5 h-2 w-2 rounded-full bg-[#0058CC]" />
      <span className="absolute left-[8px] top-4 bottom-0 w-px bg-[#E5E5EA]" />
      <div className="flex flex-wrap items-center gap-1.5 text-[11.5px]">
        <b className="text-[#1C1C1E]" data-testid={`${testId}-action`}>{actionLabel(row.action)}</b>
        <span className="text-[#6B6B73]">oleh <b data-testid={`${testId}-actor`}>{row.actor || "Sistem"}</b>{row.role ? ` · ${row.role}` : ""}</span>
        <span className="text-[#9A9BA3]" data-testid={`${testId}-time`}>{fmtTime(row.timestamp)}</span>
        <IntegrityBadge status={row.integrity} testId={`${testId}-integrity`} />
      </div>
      <div className="mt-0.5 flex flex-wrap gap-2 text-[10px] text-[#8E8E93]">
        <span>Sumber: <span className="font-mono" data-testid={`${testId}-source`}>{row.source || row.action}</span></span>
        <span>Badan usaha: <span data-testid={`${testId}-scope`}>{row.scope_entity_name}</span></span>
        {showLayer && <span data-testid={`${testId}-layer`}>Lapisan: {row.layer_entity_id ? `Override ${row.layer_entity_name}` : "Template global"}</span>}
        {row.reason && <span>Alasan: {row.reason}</span>}
      </div>
      <div className="mt-1.5 rounded-md border border-[#EFF0F2] bg-[#FAFBFC] px-2.5 py-1.5"><DiffTable diff={row.diff} testId={testId} /></div>
    </li>
  );
}

/** Tab "Riwayat Perubahan" (P14): jejak audit satu sumber daya dengan nilai lama → baru. */
export default function AuditHistoryPanel({ entityType, entityId, testIdPrefix = "audit-history", showLayer = false }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [onlyChanges, setOnlyChanges] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/audit-logs/resource`, { params: { entity_type: entityType, entity_id: entityId } });
      setData(r.data); setError("");
    } catch (e) {
      setError(e.response?.status === 403 ? "Anda tidak memiliki izin melihat jejak audit." : (e.response?.data?.detail || "Gagal memuat riwayat perubahan."));
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [entityType, entityId]); // eslint-disable-line

  const rows = useMemo(() => (data?.items || []).filter((r) => !onlyChanges || (r.diff || []).length > 0), [data, onlyChanges]);

  return (
    <div data-testid={testIdPrefix}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <History size={14} className="text-[#0058CC]" />
        <span className="text-[11.5px] text-[#6B6B73]" data-testid={`${testIdPrefix}-count`}>{data ? `${data.total} catatan` : "…"}</span>
        <label className="ml-auto inline-flex items-center gap-1 text-[11px] text-[#3C3C43]">
          <input type="checkbox" data-testid={`${testIdPrefix}-only-changes`} checked={onlyChanges} onChange={(e) => setOnlyChanges(e.target.checked)} />
          Hanya yang punya nilai lama/baru
        </label>
        <button type="button" className="icon-button" data-testid={`${testIdPrefix}-refresh`} onClick={load} aria-label="Muat ulang"><RefreshCw size={13} className={loading ? "animate-spin" : ""} /></button>
      </div>
      {error && <div className="rounded-md bg-[#FDEDE7] px-3 py-2 text-[11.5px] text-[#C0392B]" data-testid={`${testIdPrefix}-error`}>{error}</div>}
      {!error && loading && !data && <div className="py-8 text-center text-[11.5px] text-[#9A9BA3]" data-testid={`${testIdPrefix}-loading`}>Memuat riwayat…</div>}
      {!error && data && rows.length === 0 && <div className="py-8 text-center text-[11.5px] text-[#9A9BA3]" data-testid={`${testIdPrefix}-empty`}>Belum ada perubahan tercatat.</div>}
      {!error && rows.length > 0 && (
        <ul className="max-h-[440px] overflow-y-auto pr-1" data-testid={`${testIdPrefix}-list`}>
          {rows.map((r) => <HistoryRow key={r.id} row={r} testId={`${testIdPrefix}-row-${r.id}`} showLayer={showLayer} />)}
        </ul>
      )}
      {data?.truncated && <p className="mt-2 text-[10.5px] text-[#B45309]" data-testid={`${testIdPrefix}-truncated`}>Menampilkan {data.items.length} dari {data.total} catatan terbaru.</p>}
    </div>
  );
}
