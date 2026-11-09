// PREP-F — label & aturan tampilan antrean printer label RFID (CP30EN). Murni (tanpa React) supaya mudah diuji.
// Tiga dimensi yang SENGAJA dipisah di layar: status perangkat (printer/connector) · status job/label · verifikasi C72.

// FIX-8 (KN_37 §8) — label status job/label cetak dipindah ke kosakata tunggal `utils/statusVocab.js` (ranah
// "print_job" / "print_item", istilah sama persis). Bentuk lama [warna, label] dipertahankan untuk pemakai & CSV.
import { DOMAIN_LABELS } from "../../utils/statusVocab";
const COLOR_OF = { queued: "blue", printing: "purple", printed: "orange", partial: "orange", failed: "red",
  needs_review: "red", verified: "green", verified_with_issues: "red" };
const ITEM_COLOR_OF = { pending: "gray", started: "purple", confirmed: "green", failed: "red", unknown: "orange" };
export const JOB_STATUS = Object.fromEntries(Object.entries(DOMAIN_LABELS.print_job).map(([k, l]) => [k, [COLOR_OF[k] || "gray", l]]));

export const ITEM_STATUS = Object.fromEntries(Object.entries(DOMAIN_LABELS.print_item).map(([k, l]) => [k, [ITEM_COLOR_OF[k] || "gray", l]]));

export const RESULT_TEXT = {
  confirmed: "terkonfirmasi", failed: "gagal", unknown: "tidak pasti", not_applicable: "tanpa chip",
};

export const PRINTER_STATE = {
  ready: ["green", "Siap"], printing: ["blue", "Mencetak"], paused: ["orange", "Jeda"],
  paper_out: ["red", "Kertas habis"], ribbon_out: ["red", "Ribbon habis"], head_open: ["red", "Kepala printer terbuka"],
  rfid_error: ["red", "Galat RFID"], error: ["red", "Galat printer"], offline: ["red", "Printer tidak terjangkau"],
  unknown: ["gray", "Status tidak diketahui"],
};

export const EVIDENCE_SOURCE = {
  printer_readback: "Baca balik EPC oleh printer", printer_status: "Status printer", connector: "Connector",
  connector_recovery: "Pemulihan connector (sesudah mati/crash)", operator_manual: "Ditandai tercetak manual",
  legacy_job_ack: "Konfirmasi job (kontrak lama)",
};

export const KIND_LABEL = { rfid_tag: "Tag RFID", qr_label: "Label QR", text_reprint: "Cetak ulang teks" };

export const FOLLOW_UP_REASON = {
  unknown: "Hasil tidak pasti", conflict: "Hasil bertentangan", failed: "Gagal — perlu tindak lanjut",
  stale_started: "Klaim printer habis saat mencetak",
};

export const RESOLVE_ACTIONS = {
  confirm_success: "Tercetak & chip terbaca (sukses)",
  confirm_failed: "Gagal — label dimusnahkan",
  reprint: "Cetak ulang dengan EPC baru",
  close: "Tutup tanpa cetak ulang",
};

export const EVIDENCE_TYPES = [
  { value: "c72_scan", label: "Pindai C72 / reader (EPC terbaca)" },
  { value: "visual_check", label: "Cek visual label" },
  { value: "printer_log", label: "Log / layar printer" },
  { value: "other", label: "Lainnya" },
];

export const REPLACE_REASONS = [
  { value: "damaged", label: "Tag rusak / tidak terbaca" },
  { value: "lost", label: "Label/tag hilang" },
  { value: "wrong_roll", label: "Tertempel di roll yang salah" },
  { value: "print_issue", label: "Masalah hasil cetak" },
  { value: "other", label: "Lainnya" },
];

export const REPRINT_REASONS = [
  { value: "text_damaged", label: "Teks label rusak / pudar" },
  { value: "text_lost", label: "Label teks hilang (chip masih di roll)" },
  { value: "qty_changed", label: "Isi label berubah (qty/lot)" },
  { value: "other", label: "Lainnya" },
];

/** Tindakan yang sah untuk satu butir tindak lanjut (sama dengan aturan server `resolve_item`). */
export function actionsFor(row) {
  if (!row) return [];
  if (row.reason === "failed") return ["reprint", "close"];
  return ["confirm_success", "confirm_failed", "reprint"];
}

/** Konfirmasi sukses label RFID wajib bukti baca EPC (server menolak bukti lain). */
export function evidenceRequired(kind, action) {
  return action === "confirm_success" && kind === "rfid_tag" ? "c72_scan" : null;
}

export function jobProgress(job) {
  const c = job?.counts;
  if (!c) return `${job?.item_count ?? 0} label`;
  const parts = [`${c.confirmed || 0} tercetak`];
  if (c.failed) parts.push(`${c.failed} gagal`);
  if (c.unknown) parts.push(`${c.unknown} tidak pasti`);
  if (c.started) parts.push(`${c.started} sedang dicetak`);
  if (c.pending) parts.push(`${c.pending} menunggu`);
  return parts.join(" · ");
}

export function ageText(iso, now = Date.now()) {
  if (!iso) return "belum pernah";
  const m = Math.round((now - new Date(iso).getTime()) / 60000);
  if (m < 1) return "baru saja";
  if (m < 60) return `${m} mnt lalu`;
  if (m < 1440) return `${Math.round(m / 60)} jam lalu`;
  return `${Math.round(m / 1440)} hari lalu`;
}

/** Kesehatan printer: connector hidup (heartbeat ≤ 5 mnt) BUKAN berarti printer siap. */
export function printerHealth(p) {
  const conn = p?.online ? ["green", "Connector aktif"] : ["red", "Connector tidak aktif"];
  const st = PRINTER_STATE[p?.printer_state] || PRINTER_STATE.unknown;
  return { connector: conn, printer: p?.printer_state ? st : ["gray", "Belum ada laporan printer"] };
}

export function epcTail(epc) {
  return epc ? `…${String(epc).slice(-8)}` : "—";
}

export const JOB_CSV_COLUMNS = [
  { key: "job_number", header: "No. Job" },
  { header: "Jenis", get: (j) => KIND_LABEL[j.kind] || j.kind || "" },
  { key: "warehouse_name", header: "Gudang" },
  { header: "Status", get: (j) => (JOB_STATUS[j.status] || [null, j.status])[1] },
  { key: "item_count", header: "Jumlah label", type: "int" },
  { header: "Tercetak", get: (j) => j.counts?.confirmed ?? "", type: "int" },
  { header: "Gagal", get: (j) => j.counts?.failed ?? "", type: "int" },
  { header: "Tidak pasti", get: (j) => j.counts?.unknown ?? "", type: "int" },
  { header: "Printer", get: (j) => j.lease?.device_name || j.printed_by_device || "" },
  { key: "print_attempts", header: "Klaim printer", type: "int" },
  { key: "created_by", header: "Dibuat oleh" },
  { key: "created_at", header: "Dibuat", type: "datetime" },
];

export const FOLLOW_UP_CSV_COLUMNS = [
  { key: "job_number", header: "No. Job" },
  { key: "roll_no", header: "Roll" },
  { key: "sku", header: "SKU" },
  { key: "epc", header: "EPC" },
  { header: "Alasan", get: (r) => FOLLOW_UP_REASON[r.reason] || r.reason },
  { header: "Cetak", get: (r) => RESULT_TEXT[r.print_status] || "" },
  { header: "Chip", get: (r) => RESULT_TEXT[r.encode_status] || "" },
  { key: "warehouse_name", header: "Gudang" },
  { key: "started_at", header: "Mulai dicetak", type: "datetime" },
];
