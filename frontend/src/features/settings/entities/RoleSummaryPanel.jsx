/**
 * RoleSummaryPanel — PR-T6: panel "Ringkasan peran" di editor peran (dan ringkasan pendek di formulir akun).
 * Isinya dari `summary` server (`POST /api/access/roles/preview` saat menyunting, `GET /api/access/roles/{id}/summary`
 * di formulir akun): halaman awal, data yang terlihat, kategori kerja, PT, batas persetujuan, dan per modul
 * "bisa … tidak bisa …" per halaman. Tiga keadaan dibedakan: memuat (kerangka abu-abu), galat (+ Coba lagi), kosong.
 */
import { AlertTriangle, ListChecks, RotateCcw } from "lucide-react";

const rupiah = (n) => `Rp ${Math.round(Number(n) || 0).toLocaleString("id-ID")}`;

/** "PT: semua PT aktif" / "PT: hanya yang ditugaskan per akun". */
export const ptText = (cross) => (cross ? "PT: semua PT aktif" : "PT: hanya yang ditugaskan per akun");

/** Kalimat batas persetujuan: daftar "{jenis} — {jenjang}, sampai Rp …|tanpa batas", atau "Mengikuti tingkat …". */
export function approvalLines(approvals) {
  if (approvals && !Array.isArray(approvals) && approvals.follows_rank_of) {
    return [`Mengikuti tingkat ${approvals.follows_rank_of}; diatur di Aturan Persetujuan.`];
  }
  return (approvals || []).map((a) => `${a.label} — ${a.level}, ${a.max_amount == null ? "tanpa batas" : `sampai ${rupiah(a.max_amount)}`}`);
}

/** "{halaman}: bisa {aksi, aksi}; tidak bisa {aksi, aksi}." */
export function pageLine(p) {
  const parts = [];
  if ((p.can || []).length) parts.push(`bisa ${p.can.join(", ")}`);
  if ((p.cannot || []).length) parts.push(`tidak bisa ${p.cannot.join(", ")}`);
  return `${p.label}: ${parts.join("; ") || "—"}.`;
}

/** Jumlah modul per tingkat (ringkasan pendek formulir akun). */
export function levelCounts(modules) {
  const mods = modules || [];
  return {
    manage: mods.filter((m) => m.level === "manage" && !m.partial).length,
    partial: mods.filter((m) => m.partial).length,
    view: mods.filter((m) => m.level === "view").length,
  };
}

export function SummarySkeleton({ testId = "role-summary-loading" }) {
  return (
    <div className="space-y-1.5" data-testid={testId} aria-busy="true">
      {[70, 90, 55, 80].map((w) => <div key={w} className="h-3 animate-pulse rounded bg-kn-neutral-soft" style={{ width: `${w}%` }} />)}
    </div>
  );
}

export default function RoleSummaryPanel({ summary, loading, error, onRetry, header = null }) {
  return (
    <div className="rounded-md border border-kn-divider bg-white p-2.5" data-testid="role-summary-panel">
      <div className="mb-1 flex items-center gap-1.5">
        <ListChecks size={13} className="text-kn-action" />
        <p className="kicker !mb-0">Ringkasan peran</p>
      </div>
      {header}
      {loading && !summary && <SummarySkeleton />}
      {error && (
        <div className="flex flex-wrap items-center gap-2" data-testid="role-summary-error">
          <p className="text-fs-12 text-kn-danger-text">Ringkasan tidak bisa dimuat.</p>
          <button type="button" className="secondary-button btn-sm" data-testid="role-summary-retry" onClick={onRetry}>
            <RotateCcw size={12} /> Coba lagi
          </button>
        </div>
      )}
      {summary && !error && (
        <div className={`space-y-1.5 text-fs-12 text-kn-text ${loading ? "opacity-60" : ""}`} data-testid="role-summary-body">
          <ul className="space-y-0.5">
            <li data-testid="role-summary-home">Halaman awal: <b>{summary.home?.label}</b></li>
            <li data-testid="role-summary-scope">Data yang terlihat: <b>{summary.data_scope?.label}</b></li>
            <li data-testid="role-summary-category">Kategori kerja: <b>{summary.kategori?.label}</b></li>
            <li data-testid="role-summary-pt">{ptText(summary.cross_entity)}</li>
          </ul>
          <div data-testid="role-summary-approvals">
            <p className="font-semibold">Batas persetujuan:</p>
            {approvalLines(summary.approvals).length === 0
              ? <p className="text-kn-text-2">Tidak tercantum di aturan persetujuan mana pun.</p>
              : approvalLines(summary.approvals).map((t) => <p key={t} className="text-kn-text-2">{t}</p>)}
          </div>
          {(summary.modules || []).length === 0 ? (
            <p className="text-kn-danger-text" data-testid="role-summary-empty">Belum ada modul yang dinyalakan.</p>
          ) : (
            <ul className="max-h-72 space-y-1 overflow-auto pr-1" data-testid="role-summary-modules">
              {summary.modules.map((m) => (
                <li key={m.id} data-testid={`role-summary-module-${m.id}`}>
                  <b>{m.label}</b>
                  {(m.pages || []).map((p) => (
                    <span key={p.label} className="block pl-2 text-kn-text-2">— {pageLine(p)}</span>
                  ))}
                </li>
              ))}
            </ul>
          )}
          {(summary.risky || []).length > 0 && (
            <p className="flex items-start gap-1 font-semibold text-kn-warning-text" data-testid="role-summary-risky">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" />
              Perhatian — peran ini bisa: {summary.risky.join("; ")}.
            </p>
          )}
          {(summary.follows_base || []).length > 0 && (
            <p className="text-kn-text-2" data-testid="role-summary-follows">Mengikuti peran dasar: {summary.follows_base.join("; ")}.</p>
          )}
        </div>
      )}
    </div>
  );
}
