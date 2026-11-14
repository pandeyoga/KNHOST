import { AlertTriangle, X } from "lucide-react";

/**
 * FocusNotice — PK-44 · pemberitahuan baku saat tautan dokumen tidak bisa dibuka di layar tujuan
 * ("Dokumen {nomor} tidak ditemukan di PT ini."). Pasangan `hooks/useFocusDoc`: `<FocusNotice {...fokus} />`.
 * Status = ikon + teks + warna (`notice-bar warning`), bisa ditutup.
 */
export default function FocusNotice({ pesan, tutup, testId = "focus-notice" }) {
  if (!pesan) return null;
  return (
    <div className="notice-bar warning" role="status" data-testid={testId}>
      <AlertTriangle size={14} aria-hidden="true" /> <span>{pesan}</span>
      {tutup && <button type="button" onClick={tutup} aria-label="Tutup pemberitahuan" data-testid={`${testId}-close`}><X size={12} /></button>}
    </div>
  );
}
