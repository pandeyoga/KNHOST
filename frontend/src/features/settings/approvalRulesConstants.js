// Konstanta + helper untuk Approval Rules — skema MESIN (doc_type/min/max/required_role).
// KP-T3 — hanya pilihan yang benar-benar dipakai mesin: jenis "Diskon (%)" dan peran "Owner" dibuang; label peran
// dibaca dari registry peran (`config/roles.js`), bukan daftar statis.
import { ROLE_REGISTRY, roleLabel as registryRoleLabel } from "../../config/roles";

export function fmtNum(n) {
  return new Intl.NumberFormat("id-ID").format(n || 0);
}

/** Rupiah ringkas untuk kalimat jenjang: "Rp100.000.000". */
export function fmtRp(n) {
  return `Rp${fmtNum(n)}`;
}

export const DOC_TYPES = [
  { value: "sales_order", label: "Pesanan Penjualan (SO)" },
  { value: "purchase_order", label: "Pesanan Pembelian (PO)" },
  { value: "purchase_requisition", label: "Permintaan Pembelian (PR)" },
];

/** Jenis lama yang tidak dinilai mesin lagi — hanya untuk MEMBACA baris lama (mis. tabel master), bukan pilihan. */
export const RETIRED_DOC_TYPES = [
  { value: "discount", label: "Diskon (%)" },
];

export const NO_APPROVAL_LABEL = "Tanpa persetujuan (lolos otomatis)";

/** Pilihan Peran Penyetuju: tanpa persetujuan, Manajer, Admin — label dari registry peran. */
export function approverRoleOptions() {
  return [
    { value: "", label: NO_APPROVAL_LABEL },
    { value: "manager", label: registryRoleLabel("manager") },
    { value: "admin", label: registryRoleLabel("admin") },
  ];
}

export function isKnownRole(v) {
  return !v || !!ROLE_REGISTRY[v];
}

/** Teks untuk nilai tersimpan yang tidak ada di pilihan (peran kustom lama atau peran yang tidak ada). */
export function unknownRoleLabel(v) {
  return isKnownRole(v) ? registryRoleLabel(v) : `${v} — peran tidak dikenal, diperlakukan sebagai Manajer`;
}

export function docTypeLabel(v) {
  return [...DOC_TYPES, ...RETIRED_DOC_TYPES].find((t) => t.value === v)?.label || v;
}

export function roleLabel(v) {
  return v ? registryRoleLabel(v) : NO_APPROVAL_LABEL;
}

export function fmtRange(rule) {
  const pct = rule.is_percent || rule.doc_type === "discount";
  const unit = pct ? "%" : "Rp ";
  const lo = pct ? `${fmtNum(rule.min_amount)}${unit}` : `${unit}${fmtNum(rule.min_amount)}`;
  if (rule.max_amount === null || rule.max_amount === undefined) return `≥ ${lo}`;
  const hi = pct ? `${fmtNum(rule.max_amount)}${unit}` : `${unit}${fmtNum(rule.max_amount)}`;
  return `${lo} s/d < ${hi}`;
}

/** "Rp0 s/d < Rp100.000.000" · "≥ Rp100.000.000" (batas atas kosong = tanpa batas). */
export function tierRange(min, max) {
  if (max === null || max === undefined) return `≥ ${fmtRp(min)}`;
  return `${fmtRp(min)} s/d < ${fmtRp(max)}`;
}

/**
 * KP-T3 — kalimat jenjang satu jenis dokumen dari jawaban `GET /approval-rules/effective`:
 *   "Rp0 s/d < Rp100.000.000 — tanpa persetujuan", "≥ Rp100.000.000 — Manajer",
 *   "≥ Rp500.000.000 — ditambah Direksi (Admin)".
 */
export function tierLines(dt) {
  const lines = (dt?.tiers || []).map((t) => ({
    key: `t-${t.rule_id || t.min_amount}`,
    text: `${tierRange(t.min_amount, t.max_amount)} — ${t.required_role
      ? (t.required_role_label || registryRoleLabel(t.required_role)) : "tanpa persetujuan"}`,
    unknown: t.role_known === false,
  }));
  (dt?.extra_levels || []).forEach((lv) => {
    const who = lv.label && lv.label !== lv.role_label ? `${lv.label} (${lv.role_label})` : lv.role_label;
    lines.push({ key: `x-${lv.level}`, text: `≥ ${fmtRp(lv.min_amount)} — ditambah ${who}`,
      unknown: lv.role_known === false });
  });
  return lines;
}

export const SOURCE_BADGE = {
  grup: { label: "Aturan grup", cls: "badge-blue" },
  pt: { label: "Aturan khusus PT ini", cls: "badge-purple" },
  kosong: { label: "Belum ada aturan", cls: "badge-muted" },
};
