/**
 * RoleSummaryPanel — PR-T6: panel "Ringkasan peran" di editor peran (dan ringkasan pendek di formulir akun).
 * Isinya dari `summary` server (`POST /api/access/roles/preview` saat menyunting, `GET /api/access/roles/{id}/summary`
 * di formulir akun): halaman awal, data yang terlihat, kategori kerja, PT, batas persetujuan, dan per modul
 * "bisa … tidak bisa …" per halaman. Tiga keadaan dibedakan: memuat (kerangka abu-abu), galat (+ Coba lagi), kosong.
 *
 * Pola UI 16 Nov (M43) — dulu kolom kanan panjang (rincian per modul selalu terbuka, peringatan berparagraf). Kini SATU
 * baris ringkas (jumlah per tingkat · halaman awal · data · PT), peringatan masing-masing satu baris kecil, dan rincian
 * per modul + batas persetujuan di "Rincian" yang dibuka bila perlu.
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
  const risky = summary?.risky || [];
  const mods = summary?.modules || [];
  const approvals = approvalLines(summary?.approvals);
  return (
    <div className="space-y-1" data-testid="role-summary-panel">
      <div className="cfg-role-line">
        <ListChecks size={13} className="text-kn-action" aria-hidden="true" />
        <b>Ringkasan</b>
        {header}
        {summary && !error && (
          <>
            <span className="text-kn-text-2" aria-hidden="true">·</span>
            <span className="text-kn-text-2" data-testid="role-summary-home">Halaman awal: <b>{summary.home?.label}</b></span>
            <span className="text-kn-text-2" aria-hidden="true">·</span>
            <span className="text-kn-text-2" data-testid="role-summary-scope">Data yang terlihat: <b>{summary.data_scope?.label}</b></span>
            <span className="text-kn-text-2" aria-hidden="true">·</span>
            <span className="text-kn-text-2" data-testid="role-summary-pt">{ptText(summary.cross_entity)}</span>
          </>
        )}
      </div>
      {loading && !summary && <SummarySkeleton />}
      {error && (
        <p className="cfg-role-line err" data-testid="role-summary-error">
          Ringkasan tidak bisa dimuat.
          <button type="button" className="secondary-button btn-sm" data-testid="role-summary-retry" onClick={onRetry}>
            <RotateCcw size={12} /> Coba lagi
          </button>
        </p>
      )}
      {summary && !error && (
        <div className={`space-y-1 ${loading ? "opacity-60" : ""}`} data-testid="role-summary-body">
          {mods.length === 0 && !loading ? (
            <p className="cfg-role-line err" data-testid="role-summary-empty">Belum ada modul yang dinyalakan.</p>
          ) : null}
          {risky.length > 0 && (
            <p className="cfg-role-line warn" data-testid="role-summary-risky" title={`Perhatian — peran ini bisa: ${risky.join("; ")}.`}>
              <AlertTriangle size={12} aria-hidden="true" />
              <span className="cfg-role-line-clamp">Perhatian — peran ini bisa: {risky.join("; ")}.</span>
            </p>
          )}
          <details className="cfg-role-more" data-testid="role-summary-details">
            <summary>Rincian per modul &amp; batas persetujuan</summary>
            <div className="space-y-1 text-fs-12 text-kn-text">
              <p className="m-0" data-testid="role-summary-category">Kategori kerja: <b>{summary.kategori?.label}</b></p>
              <div data-testid="role-summary-approvals">
                <p className="m-0 font-semibold">Batas persetujuan:</p>
                {approvals.length === 0
                  ? <p className="m-0 text-kn-text-2">Tidak tercantum di aturan persetujuan mana pun.</p>
                  : approvals.map((t) => <p key={t} className="m-0 text-kn-text-2">{t}</p>)}
              </div>
              {mods.length > 0 && (
                <ul className="max-h-72 space-y-1 overflow-auto pr-1" data-testid="role-summary-modules">
                  {mods.map((m) => (
                    <li key={m.id} data-testid={`role-summary-module-${m.id}`}>
                      <b>{m.label}</b>
                      {(m.pages || []).map((p) => (
                        <span key={p.label} className="block pl-2 text-kn-text-2">— {pageLine(p)}</span>
                      ))}
                    </li>
                  ))}
                </ul>
              )}
              {(summary.follows_base || []).length > 0 && (
                <p className="m-0 text-kn-text-2" data-testid="role-summary-follows">Mengikuti peran dasar: {summary.follows_base.join("; ")}.</p>
              )}
            </div>
          </details>
        </div>
      )}
    </div>
  );
}
