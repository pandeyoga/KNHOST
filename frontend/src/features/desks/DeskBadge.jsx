import { badgeGroup, badgeLabel } from "../sales_admin/workDeskApi";

const TONE = {
  danger: "bg-kn-danger-soft text-kn-danger-text",
  warn: "bg-kn-warning-soft text-kn-warning-text",
  ok: "bg-kn-success-soft text-kn-success-text",
  info: "bg-kn-action-soft text-kn-action",
  mute: "bg-kn-neutral-soft text-kn-text-2",
};

/** Lencana status baris meja (hanya token kn-*). */
export default function DeskBadge({ badge, testId, className = "" }) {
  const label = badgeLabel(badge);
  if (!label) return null;
  return (
    <span data-testid={testId}
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-fs-12 font-medium ${TONE[badgeGroup(badge)] || TONE.mute} ${className}`}>
      {label}
    </span>
  );
}
