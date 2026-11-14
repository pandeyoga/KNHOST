// ─── Shared helpers untuk modul Digitalisasi Formulir Sukacita ───────────────
// Petty Cash: Pengajuan Dana (PD) · Pertanggungjawaban (Settlement) · Kendaraan.
// SSOT status label/tone + StatusPill + konstanta. Fungsi CETAK (print) dokumen
// dipindah ke utils/docPrint.js (self-contained, di luar scan UX baseline).
import { Banknote, CheckCheck, CheckCircle2, Clock, FilePen, Send, XCircle } from "lucide-react";
import { formatDate } from "../../utils/formatters";
import { docStatusLabel } from "../../utils/docStatus";
export {
  printCashAdvance, printTandaTerima, printSettlement, terbilang, printHTML,
} from "../../utils/docPrint";

// ─── Status Cash Advance (Form PD) ───────────────────────────────────────────
// PK-24 — status = ikon + teks + warna (KN_37 §1.3); `icon` dipakai `StatusPill`.
export const CA_STATUS = {
  draft:            { label: "Draf",                 cls: "pill-muted", icon: FilePen },
  pending_atasan:   { label: "Menunggu Atasan",       cls: "pill-warning", icon: Clock },
  pending_pimpinan: { label: "Menunggu Pimpinan",     cls: "pill-warning", icon: Clock },
  pending_finance:  { label: "Menunggu Keuangan",     cls: "pill-warning", icon: Clock },
  approved:         { label: "Disetujui",             cls: "pill-info", icon: CheckCircle2 },
  disbursed:        { label: "Dicairkan",             cls: "pill-info", icon: Banknote },
  settled:          { label: "Selesai (LPJ)",         cls: "pill-success", icon: CheckCheck },
  rejected:         { label: "Ditolak",               cls: "pill-danger", icon: XCircle },
};

// PK-24 — `approved` = disetujui, jurnalnya belum terbit (gagal → Keuangan › Posting Gagal).
export const STL_STATUS = {
  draft:        { label: "Draf",                cls: "pill-muted", icon: FilePen },
  submitted:    { label: "Diajukan",            cls: "pill-warning", icon: Send },
  approved:     { label: "Menunggu jurnal",     cls: "pill-info", icon: Clock },
  posted_to_gl: { label: "Terposting GL",       cls: "pill-success", icon: CheckCheck },
  rejected:     { label: "Ditolak",             cls: "pill-danger", icon: XCircle },
};

// Urutan tahap approval PD (untuk timeline & progress).
export const CA_STAGE_ORDER = ["pending_atasan", "pending_pimpinan", "pending_finance", "approved"];
export const CA_STAGE_LABEL = {
  atasan: "Atasan Langsung",
  pimpinan: "Pimpinan",
  finance: "Bagian Keuangan",
};

export const SATUAN_OPTIONS = [
  { value: "unit", label: "Unit" },
  { value: "roll", label: "Roll" },
  { value: "yard", label: "Yard" },
  { value: "kg", label: "Kg" },
  { value: "meter", label: "Meter" },
  { value: "paket", label: "Paket" },
  { value: "lembar", label: "Lembar" },
  { value: "hari", label: "Hari" },
];

export function StatusPill({ status, map = CA_STATUS, testId }) {
  const s = map[status] || { label: docStatusLabel(status) || "—", cls: "pill-muted" };
  const Icon = s.icon;
  return (
    <span data-testid={testId} className={`status-pill ${s.cls} inline-flex items-center gap-1 whitespace-nowrap`}>
      {Icon && <Icon size={12} aria-hidden="true" />}{s.label}
    </span>
  );
}

// PK-42 (UX-18) — satu pemformat tanggal WIB bersama (`utils/formatters`); dulu zona perangkat / bentuk sendiri.
export const fmtDate = (s) => formatDate(s);
