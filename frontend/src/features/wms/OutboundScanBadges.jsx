// Badge + MiniBar untuk OutboundScanInterface (dipisah agar file utama di bawah
// batas guardrail). Pure presentational.
import StatusBadge from "../../components/StatusBadge";

// FIX-8 (KN_37 §8) — label status tugas keluar dipindah ke kosakata tunggal `utils/statusVocab.js` (ranah
// "task_out", istilah sama persis); lencana = StatusBadge baku (ikon + teks + warna token). Dulu kode tak dikenal
// tampil MENTAH ({label: status}); kini lewat peta umum (tidak pernah kode mentah).
export function Badge({ status }) {
  return <StatusBadge status={status} domain="task_out" testId={`outbound-status-badge-${status}`} />;
}

export function MiniBar({ pct, status }) {
  const color = status === 'dispatched' ? 'bg-[#34C759]' : status === 'escalated' ? 'bg-red-400' : 'bg-[#FF9500]';
  return (
    <div className="h-1 w-full rounded-full bg-gray-200 overflow-hidden">
      <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  );
}
