import { CheckCircle2, X } from "lucide-react";

/**
 * OkNotice — bilah SUKSES baku (pasangan `ErrorNotice`): `.notice-bar success` + ikon centang + tombol tutup.
 * 23 Okt — beberapa layar R&D/desain memakai kotak hijau buatan sendiri (tanpa ikon & tanpa tutup) sehingga
 * pesan sukses tampil beda dari layar lain dan tidak bisa ditutup.
 */
export default function OkNotice({ message, onDismiss, testId = "ok-notice" }) {
  if (!message) return null;
  return (
    <div className="notice-bar success" data-testid={testId}>
      <CheckCircle2 size={14} /> <span>{message}</span>
      {onDismiss && <button type="button" onClick={onDismiss} aria-label="Tutup" data-testid={`${testId}-close`}><X size={12} /></button>}
    </div>
  );
}
