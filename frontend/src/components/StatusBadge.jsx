/**
 * StatusBadge — FIX-8 (Standar UI Gudang v1 tahap 2 · B4 §3.9 · KN_37 §8): SATU lencana status untuk layar WMS-RFID.
 *
 * Status = **ikon + teks + warna token** (tidak pernah warna saja — WCAG 1.4.1). Kosakata (label, nada, ikon) dari
 * satu sumber `utils/statusVocab.js`; layar boleh memberi `label` sendiri (istilah lama tidak diganti, K-13) dan nada
 * tetap dari kosakata. Menyatukan `Pill` (rfidShared), `RollStatusBadge`, `QcStatusBadge`, `TaskBadge`, lencana
 * transfer/keluar/GRN/SPK/PA dan `status-pill` buatan layar. Kelas `kn-badge` + `tone-*` (styles/standard.css) —
 * semua pasangan teks/latar dihitung G-UI-03 (`verify_ui_contrast.py`).
 *
 *   <StatusBadge status="quarantine" domain="roll" />                 → ikon perisai · "Karantina" · nada perhatian
 *   <StatusBadge status={t.status} label={labelLama(t.status)} />      → label layar, nada & ikon dari kosakata
 *   <StatusBadge tone="special" label="Antar PT" icon="tag" />         → lencana kategori tanpa kode status
 *
 * Props: status · domain · label · tone (neutral|info|success|warning|danger|special) · icon (nama, lihat ICONS) ·
 * size ("sm" bawaan | "md") · testId · title · className · children (teks pengganti label).
 */
import {
  AlertTriangle, Archive, Ban, CheckCircle2, Circle, CircleDot, Clock, FilePen, Lock, PauseCircle, ShieldAlert, Tag,
  Truck, XCircle,
} from "lucide-react";
import { statusMeta, TONES } from "../utils/statusVocab";

const ICONS = {
  circle: Circle, dot: CircleDot, check: CheckCircle2, alert: AlertTriangle, x: XCircle, tag: Tag, clock: Clock,
  shield: ShieldAlert, pause: PauseCircle, truck: Truck, ban: Ban, archive: Archive, draft: FilePen, lock: Lock,
};

export default function StatusBadge({
  status, domain, label, tone, icon, size = "sm", testId, title, className = "", children,
}) {
  const meta = statusMeta(status, { domain, label: children ? undefined : label, tone });
  const text = children || meta.label;
  const Icon = ICONS[icon] || ICONS[meta.icon] || Circle;
  const t = TONES.includes(meta.tone) ? meta.tone : "neutral";
  return (
    <span data-testid={testId} data-status={status || undefined} data-tone={t} title={title}
      className={`kn-badge tone-${t}${size === "md" ? " kn-badge-md" : ""}${className ? ` ${className}` : ""}`}>
      <Icon size={size === "md" ? 14 : 12} aria-hidden="true" className="kn-badge-icon" />
      <span>{text}</span>
    </span>
  );
}

export { StatusBadge };
