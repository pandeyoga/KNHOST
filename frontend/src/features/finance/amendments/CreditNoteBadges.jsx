/**
 * PK-32 — satu kosakata status nota kredit / nota debit untuk semua layar (Koreksi & Amandemen, jejak koreksi di
 * rincian pesanan, nota batal item, rincian retur):
 *   pending_finance → Menunggu Finance · issued → Terbit (efek belum tuntas) · posted → Selesai · void → Batal.
 * Nilai lama `offset` dibaca Selesai. Status selalu ikon + teks + warna (`status-pill`). Lencana jurnal = PK-18
 * `JournalStatusBadge` di samping nomor nota.
 */
import { CheckCircle2, Clock, FileCheck2, XCircle } from "lucide-react";
import JournalStatusBadge from "../../../components/JournalStatusBadge";
import { docStatusLabel } from "../../../utils/docStatus";
import { formatCurrency } from "../../../utils/formatters";

export const NOTE_STATUS = {
  pending_finance: { label: "Menunggu Finance", cls: "status-pending", Icon: Clock },
  issued: { label: "Terbit", cls: "status-shipped", Icon: FileCheck2 },
  posted: { label: "Selesai", cls: "status-done", Icon: CheckCircle2 },
  void: { label: "Batal", cls: "status-draft", Icon: XCircle },
};

export const noteStatusOf = (status) => (status === "offset" ? "posted" : status || "");
export const noteStatusLabel = (status) => NOTE_STATUS[noteStatusOf(status)]?.label || docStatusLabel(status);

/** Pil status nota (ikon + teks + warna). */
export function NoteStatusPill({ note, testId }) {
  const key = noteStatusOf(note?.status);
  const meta = NOTE_STATUS[key];
  const id = testId || `note-status-${note?.id}`;
  if (!meta) {
    return <span className="status-pill status-draft" data-testid={id}>{noteStatusLabel(note?.status)}</span>;
  }
  const { cls, Icon, label } = meta;
  return (
    <span className={`status-pill ${cls} inline-flex items-center gap-1`} data-testid={id} data-status={key}>
      <Icon size={12} aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

/** Nomor nota + lencana jurnal (PK-18) — lencana tidak tampil untuk nota lama tanpa penanda / tanpa jurnal. */
export function NoteNumber({ note, className = "" }) {
  return (
    <span className={`inline-flex flex-wrap items-center gap-1.5 ${className}`}>
      <span className="font-semibold text-kn-action" data-testid={`note-number-${note?.id}`}>{note?.number}</span>
      <JournalStatusBadge status={note?.gl_status} error={note?.gl_error} journalEntryId={note?.journal_entry_id}
        testId={`note-journal-${note?.id}`} />
    </span>
  );
}

/** Kalimat bagian tertangguh & kelebihan bayar (spesifikasi PK-32 §Layar). */
export function NoteRecognitionHints({ note }) {
  const deferred = Number(note?.deferred_net || 0);
  const excess = Number(note?.excess_payment || 0);
  const debit = note?.kind === "debit_note";
  if (deferred <= 0 && excess <= 0) return null;
  return (
    <div className="space-y-0.5 text-fs-12 text-kn-text-2" data-testid={`note-hints-${note?.id}`}>
      {deferred > 0 && (
        <p data-testid={`note-deferred-${note?.id}`}>
          {formatCurrency(deferred)} belum {debit ? "menambah" : "mengurangi"} pendapatan karena barangnya belum dikirim.
        </p>
      )}
      {excess > 0 && (
        <p data-testid={`note-excess-${note?.id}`}>
          Kelebihan bayar {formatCurrency(excess)} tetap sebagai uang muka pelanggan.
        </p>
      )}
    </div>
  );
}
