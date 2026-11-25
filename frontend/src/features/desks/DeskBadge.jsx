import { badgeClass, badgeLabel } from "../sales_admin/workDeskApi";

/**
 * Lencana status baris meja: 12/500, nada dari `badgeClass` (token kn-*, satu kamus dengan lencana lama).
 * Label panjang terpotong dengan elipsis di dalam lebar kolomnya; teks utuh ada di `title`.
 */
export default function DeskBadge({ badge, testId, className = "" }) {
  const label = badgeLabel(badge);
  if (!label) return null;
  return (
    <span data-testid={testId} title={label}
      className={`inline-flex min-w-0 max-w-full items-center rounded-full border px-2 py-0.5 text-fs-12 font-medium ${badgeClass(badge)} ${className}`}>
      <span className="truncate">{label}</span>
    </span>
  );
}
