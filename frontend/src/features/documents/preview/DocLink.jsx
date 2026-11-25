/**
 * DocLink (Meja gelombang 2) — nomor dokumen sebagai tautan pembuka pratinjau pop-up.
 * Tanpa id dokumen, tanpa izin baca jenisnya, atau di luar penyedia navigasi → teks biasa (bukan tombol mati / 403).
 * Pola sama dengan `CardLink` (`features/finance/cards/partyCards.jsx`): izin dari `perms` (= `currentUser.permissions`).
 */
import { useAppNav } from "../../../context/AppNavContext";
import { canPreview } from "./docPreviewRegistry";

export default function DocLink({ docType, docId, number, entityId, perms, testId, className = "", children }) {
  const nav = useAppNav();
  const label = children || number || "—";
  if (!docId || !nav.previewsEnabled || !canPreview(perms, docType)) {
    return <span className={className} data-testid={testId ? `${testId}-text` : undefined}>{label}</span>;
  }
  return (
    <button type="button" className={`link-button text-left ${className}`.trim()} data-testid={testId}
      title="Lihat ringkasan dokumen"
      onClick={(e) => {
        e.stopPropagation();
        nav.openDocPreview({ docType, docId, ...(number ? { number } : {}), ...(entityId ? { entityId } : {}) });
      }}>
      {label}
    </button>
  );
}
