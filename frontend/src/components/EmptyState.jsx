/**
 * EmptyState — FIX-8 (Standar UI Gudang v1 tahap 2 · B4 §3.10 · KN_37 §6a): SATU tampilan keadaan daftar/panel.
 *
 * Lima keadaan yang WAJIB dibedakan (dulu satu teks "Belum ada …" untuk semuanya):
 *   loading   — sedang memuat: ikon berputar + "Memuat …". TIDAK PERNAH "0"/"belum ada" (B1b UI-50, LST-06).
 *   empty     — kosong sungguhan: ikon + judul + penjelasan + (opsional) satu aksi utama.
 *   filtered  — saringan/cari tidak menemukan apa pun: sebut itu + tombol "Reset saringan".
 *   error     — gagal memuat: kalimat galat (apiErrorText) + "Coba lagi".
 *   forbidden — server menolak izin (HTTP 403): "Anda tidak punya akses …" — BUKAN daftar kosong (B1b UI-49).
 *
 * Pakai `listStateKind({ loading, error, count, filtered })` untuk memilih keadaan dari state layar, atau beri
 * `kind` langsung. `asRow` + `colSpan` → dibungkus `<tr><td>` untuk tabel mentah.
 *
 * Props: kind · what (kata benda, mis. "transfer") · title · text · error (objek/teks galat) · onRetry · onReset ·
 * actionLabel + onAction (aksi utama keadaan kosong) · icon (ikon keadaan kosong) · compact · asRow · colSpan · testId ·
 * children (isi tambahan).
 */
import { AlertTriangle, Inbox, Loader2, Lock, SearchX } from "lucide-react";
import { apiErrorText, isForbiddenError, permissionDeniedText } from "../utils/apiError";

/** Galat bawaan hook daftar: objek axios, teks, atau {status, message}. 403 → "forbidden". */
export function isForbidden(error) {
  if (!error) return false;
  if (typeof error === "object" && Number(error.status) === 403 && !error.response) return true;
  return isForbiddenError(error);
}

/** Pilih keadaan dari state layar. `null` = ada baris → tampilkan daftarnya. */
export function listStateKind({ loading = false, error = null, count = 0, filtered = false } = {}) {
  if (error) return isForbidden(error) ? "forbidden" : "error";
  if (count > 0) return null;
  if (loading) return "loading";
  return filtered ? "filtered" : "empty";
}

function errorText(error, fallback) {
  if (!error) return fallback;
  if (typeof error === "object" && !error.response && typeof error.message === "string" && error.status) {
    return permissionDeniedText(error.message) || error.message || fallback;
  }
  return apiErrorText(error, fallback);
}

const ICON = { loading: Loader2, empty: Inbox, filtered: SearchX, error: AlertTriangle, forbidden: Lock };

export default function EmptyState({
  kind = "empty", what = "data", title, text, error, onRetry, onReset, actionLabel, onAction, icon,
  compact = false, asRow = false, colSpan = 1, testId, children,
}) {
  const k = ICON[kind] ? kind : "empty";
  const Icon = ((k === "empty" || k === "filtered") && icon) || ICON[k];
  let head = title;
  let body = text;
  if (k === "loading") head = head || `Memuat ${what}…`;
  if (k === "empty") head = head || `Belum ada ${what}.`;
  if (k === "filtered") {
    head = head || `Tidak ada ${what} yang cocok dengan saringan.`;
    body = body ?? "Ubah atau reset saringan & kata cari untuk melihat data lain.";
  }
  if (k === "error") {
    head = head || `Gagal memuat ${what}.`;
    body = body ?? errorText(error, "Coba lagi beberapa saat.");
  }
  if (k === "forbidden") {
    const why = errorText(error, "");
    // Kalimat izin dari server ("Anda tidak punya akses ke Master Grade.") dipakai; kalimat umum 403 ("… untuk
    // tindakan ini") diganti kata benda daftar supaya jelas APA yang tidak boleh dilihat.
    const specific = /^Anda tidak punya/.test(why) && !/untuk tindakan ini/.test(why);
    const first = specific ? (why.match(/^[^.]*\./) || [why])[0] : "";
    head = head || first || `Anda tidak punya akses ke ${what}.`;
    body = body ?? "Ini bukan daftar kosong — akun Anda tidak berhak melihat data ini. Minta admin menambah izin bila diperlukan.";
  }
  const node = (
    <div className={`kn-empty is-${k}${compact ? " kn-empty-compact" : ""}`} data-testid={testId} data-kind={k}
      role={k === "loading" ? "status" : k === "error" || k === "forbidden" ? "alert" : undefined}
      aria-live={k === "loading" ? "polite" : undefined}>
      <span className="kn-empty-icon"><Icon size={compact ? 16 : 20} className={k === "loading" ? "animate-spin" : ""} aria-hidden="true" /></span>
      <p className="kn-empty-title">{head}</p>
      {body ? <p className="kn-empty-text">{body}</p> : null}
      {children}
      {(k === "error" && onRetry) || (k === "filtered" && onReset) || (k === "empty" && onAction && actionLabel) ? (
        <div className="kn-empty-actions">
          {k === "error" && onRetry && (
            <button type="button" className="secondary-button btn-sm" onClick={onRetry}
              data-testid={testId ? `${testId}-retry` : undefined}>Coba lagi</button>
          )}
          {k === "filtered" && onReset && (
            <button type="button" className="secondary-button btn-sm" onClick={onReset}
              data-testid={testId ? `${testId}-reset` : undefined}>Reset saringan</button>
          )}
          {k === "empty" && onAction && actionLabel && (
            <button type="button" className="primary-button btn-sm" onClick={onAction}
              data-testid={testId ? `${testId}-action` : undefined}>{actionLabel}</button>
          )}
        </div>
      ) : null}
    </div>
  );
  if (!asRow) return node;
  return <tr><td colSpan={colSpan}>{node}</td></tr>;
}

export { EmptyState };
