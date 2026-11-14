/**
 * JournalStatusBadge — PK-18 (GL-02, `02_STANDAR.md` L8) · status jurnal sebuah dokumen dari HASIL posting.
 *
 *   <JournalStatusBadge status={doc.gl_status} error={doc.gl_error} journalEntryId={doc.journal_entry_id} />
 *
 *  · `posted`  → "Jurnal terbit" (ikon centang). Ada `journalEntryId` → klik membuka jurnalnya di Buku Besar.
 *  · `failed`  → "Jurnal gagal" (ikon peringatan); petunjuk berisi `error`. Pemegang `accounting.view` bisa klik ke
 *                Keuangan › Posting Gagal (tempat jurnalnya diulang). `showError` → galat ditulis di samping lencana.
 *  · `pending` → "Jurnal diproses" (ikon jam).
 *  · selain itu (dokumen lama tanpa penanda, `not_required`) → tidak tampil.
 * Status selalu ikon + teks + warna (`status-pill`), bukan warna saja.
 */
import { AlertTriangle, CheckCircle2, Clock } from "lucide-react";
import { useAppNav } from "../context/AppNavContext";
import { canCurrent } from "../config/roles";

const NADA = {
  posted: { cls: "status-done", Icon: CheckCircle2, label: "Jurnal terbit" },
  failed: { cls: "status-rejected", Icon: AlertTriangle, label: "Jurnal gagal" },
  pending: { cls: "status-pending", Icon: Clock, label: "Jurnal diproses" },
};

export const journalStatusLabel = (status) => NADA[status]?.label || "";
/** Lencana tampil untuk status ini? (dokumen lama tanpa penanda / `not_required` → tidak). */
export const hasJournalBadge = (status) => !!NADA[status];

/** Bilah "Jurnal: <lencana> <galat>" di rincian dokumen — di bilahnya sendiri, bukan di kepala kartu. */
export function JournalStatusBar({ doc, testId = "journal-status" }) {
  if (!hasJournalBadge(doc?.gl_status)) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 text-[12px]" data-testid={`${testId}-bar`}>
      <span className="font-semibold text-kn-text-2">Jurnal</span>
      <JournalStatusBadge status={doc.gl_status} error={doc.gl_error} journalEntryId={doc.journal_entry_id}
        showError testId={testId} />
    </div>
  );
}

export default function JournalStatusBadge({ status, error = "", journalEntryId = "", showError = false,
  testId = "journal-status" }) {
  const { openDocument, go } = useAppNav();
  const nada = NADA[status];
  if (!nada) return null;
  const { cls, Icon, label } = nada;
  let onClick = null;
  let hint = label;
  if (status === "posted" && journalEntryId) {
    hint = "Buka jurnalnya di Buku Besar";
    onClick = () => openDocument({ view: "general-ledger", focus_type: "journal_entry", focus_id: journalEntryId });
  } else if (status === "failed") {
    hint = error ? `Jurnal gagal: ${error}` : "Jurnal gagal tercatat";
    if (canCurrent("accounting", "view")) {
      hint += " — buka Posting Gagal untuk mengulang";
      onClick = () => go("posting-failures");
    }
  } else if (status === "pending") {
    hint = "Dokumen tersimpan, jurnalnya belum selesai diterbitkan";
  }
  const isi = (
    <>
      <Icon size={12} aria-hidden="true" />
      <span>{label}</span>
    </>
  );
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5" data-testid={`${testId}-wrap`}>
      {onClick ? (
        <button type="button" onClick={onClick} title={hint} aria-label={hint} data-testid={testId}
          data-status={status} className={`status-pill ${cls} inline-flex cursor-pointer items-center gap-1 whitespace-nowrap`}>
          {isi}
        </button>
      ) : (
        <span title={hint} aria-label={hint} data-testid={testId} data-status={status}
          className={`status-pill ${cls} inline-flex items-center gap-1 whitespace-nowrap`}>{isi}</span>
      )}
      {showError && status === "failed" && error && (
        <span className="text-[12px] text-kn-danger-text" data-testid={`${testId}-error`}>{error}</span>
      )}
    </span>
  );
}
