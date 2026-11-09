/**
 * statusVocab — FIX-8 (Standar UI Gudang v1 tahap 2 · B4 §3.9 · KN_37 §8): **SATU sumber kosakata status** untuk
 * lencana `StatusBadge` di layar WMS-RFID.
 *
 * Isi:
 *  1. `DOMAIN_LABELS` — label Indonesia per ranah (roll, transfer, tugas masuk/keluar, Putaway Order, GRN, SPK
 *     inspeksi, pendaftaran awal, opname, lot, job cetak, pengiriman). Label DIPINDAH apa adanya dari peta lama di
 *     berkas fitur (yang kini mengimpor dari sini) — istilah layar TIDAK diubah (K-13, `KN_32`). Kode di luar ranah
 *     jatuh ke peta umum `DOC_STATUS_LABEL` (utils/docStatus) — tidak pernah kode mentah.
 *  2. `STATUS_TONE` — nada tiap kode (6 nada B4 §3.9): netral · info · berhasil · perhatian · bahaya · khusus.
 *     `DOMAIN_TONE` menimpa bila arti kode berbeda per ranah.
 *  3. Ikon — status selalu ikon + teks + warna (WCAG 1.4.1, prinsip KN_37 §1.3): ikon bawaan per nada, ditimpa per kode.
 *
 * Aturan nada: berhasil = selesai/baik; info = sedang berjalan/terbuka; perhatian = menunggu orang/ditahan/sebagian;
 * bahaya = gagal/ditolak/rusak (perlu tindakan); netral = draf/arsip/dibatalkan/final pasif; khusus = kategori
 * (dipesan, makloon, sampel) — bukan hijau/kuning/merah.
 */
import { docStatusLabel } from "./docStatus";

export const TONES = ["neutral", "info", "success", "warning", "danger", "special"];

// ── 1. Label per ranah (dipindah 1:1 dari peta lama; istilah tidak diubah) ─────────────────────────────────────
export const DOMAIN_LABELS = {
  /** dulu `features/wms/inventory/inventoryConstants.jsx` ROLL_STATUS_META */
  roll: {
    available: "Tersedia", reserved: "Dipesan", committed: "Dialokasikan", picked: "Sudah Diambil",
    packed: "Sudah Dikemas", quarantine: "Karantina", receiving: "Sedang Diterima", blocked: "Diblokir",
    damaged: "Rusak", sold: "Terjual", in_transit_inbound: "Dalam Perjalanan (Masuk)",
    in_transit_transfer: "Dalam Perjalanan (Transfer)", in_transit_intercompany: "Dalam Perjalanan (Antar-PT)",
    in_transit_sales: "Dalam Perjalanan (Penjualan)", consumed: "Habis Terpakai", delivered: "Terkirim",
    returned_supplier: "Diretur ke Supplier", subcon: "Di Makloon", hold: "Ditahan",
  },
  /** dulu `features/wms/transfer/transferConstants.jsx` STATUS_MAP */
  transfer: {
    draft: "Draf", waiting_approval: "Menunggu Persetujuan", approved: "Disetujui", picking: "Pengambilan",
    staging: "Disiapkan", dispatched: "Dalam Perjalanan", partially_received: "Diterima Sebagian", completed: "Selesai",
    returned: "Dikembalikan", returning: "Batal — kembali ke asal", rejected: "Ditolak", cancelled: "Dibatalkan",
  },
  /** dulu `features/wms/inbound/InboundTaskPanel.jsx` STATUS_MAP */
  task_in: {
    waiting_goods: "Menunggu barang", receiving: "Sedang diterima", qc_check: "Cek QC", put_away: "Penempatan rak",
    completed: "Selesai", escalated: "Dieskalasi", qc_pending: "Menunggu QC", qc_rejected: "Ditolak QC",
    cancelled: "Dibatalkan", closed: "Ditutup",
  },
  /** dulu `features/wms/OutboundScanBadges.jsx` STATUS_MAP */
  task_out: {
    scheduled: "Terjadwal", created: "Siap diambil", picking: "Pengambilan", packing: "Pengemasan",
    staging: "Siap muat", partially_shipped: "Terkirim Sebagian", dispatched: "Terkirim", escalated: "Dieskalasi",
  },
  /** dulu `features/mobile/MobileWarehouseApp.jsx` STATUS_ID (kartu tugas HP gudang) */
  task_hp: {
    pending: "Menunggu", created: "Baru", waiting_goods: "Menunggu barang", receiving: "Menerima", qc_check: "Cek QC",
    qc_pending: "Menunggu QC", qc_rejected: "Ditolak QC", put_away: "Simpan", picking: "Ambil", picked: "Sudah diambil",
    packing: "Kemas", packed: "Sudah dikemas", escalated: "Eskalasi", completed: "Selesai", shipped: "Terkirim",
    dispatched: "Diberangkatkan", cancelled: "Dibatalkan",
  },
  /** dulu `features/wms/putawayUtils.js` PA_STATUS */
  putaway: {
    draft: "Draf — cek & terbitkan", open: "Terbuka", in_transit: "Dalam Perjalanan", partially_received: "Tiba Sebagian",
    completed: "Selesai", completed_with_exception: "Selesai + Exception", exception: "Exception",
    returned: "Dikembalikan ke Transit", cancelled: "Draf Dibatalkan",
  },
  /** dulu `features/wms/grn/grnApi.js` STATUS */
  grn: {
    draft: "Draf", reading: "Membaca SJ", review: "Tinjau SJ", counting: "Hitung fisik", reconcile: "Rekonsiliasi",
    closing: "Memposting", closed: "Ditutup", rejected: "Ditolak", cancelled: "Dibatalkan",
  },
  /** dulu `features/inspections/inspectionsApi.js` INS_STATUS_LABEL */
  inspection: {
    draft: "Draf (belum ditugaskan)", assigned: "Ditugaskan", in_progress: "Sedang diperiksa",
    done: "Selesai (sudah diputuskan)", closed: "Ditutup",
  },
  /** dulu `features/inventory/registration/registrationApi.js` STATUS_LABEL */
  registration: {
    draft: "Draf", running: "Berjalan", pending_approval: "Menunggu persetujuan", approved: "Disetujui",
    approved_with_exceptions: "Disetujui — ada pengecualian", rejected: "Ditolak",
  },
  /** dulu `features/inventory/CycleCount.jsx` STATUS_LABELS */
  cycle_count: {
    open: "Open", submitted: "Submitted", approved: "Disetujui",
    approved_with_exceptions: "Disetujui — ada exception", rejected: "Ditolak",
  },
  /** dulu `features/rfid/printerLabels.js` JOB_STATUS / ITEM_STATUS */
  print_job: {
    queued: "Antre Cetak", printing: "Sedang Dicetak", printed: "Tercetak", partial: "Tercetak Sebagian",
    failed: "Gagal Cetak", needs_review: "Perlu Ditinjau", verified: "Terverifikasi",
    verified_with_issues: "Verif. Bermasalah",
  },
  print_item: {
    pending: "Menunggu", started: "Sedang dicetak", confirmed: "Tercetak", failed: "Gagal", unknown: "Tidak pasti",
  },
  /** label pengiriman = `features/logistics/logisticsApi.js` STATUS_LABEL (server juga mengirim `status_label`) */
  delivery: {
    prepared: "Disiapkan", loaded: "Dimuat", in_transit: "Dalam perjalanan", delivered: "Terkirim",
    completed: "Selesai", failed: "Gagal kirim",
  },
};

// ── 2. Nada ────────────────────────────────────────────────────────────────────────────────────────────────────
const T = (tone, codes) => Object.fromEntries(codes.map((c) => [c, tone]));
export const STATUS_TONE = {
  ...T("neutral", ["draft", "cancelled", "closed", "archived", "inactive", "void", "voided", "expired", "sold",
    "consumed", "returned_supplier", "legacy_completed", "created", "new", "pending", "returned", "released",
    "offline", "retired", "deactivated", "not_applicable"]),
  ...T("info", ["open", "approved", "assigned", "in_progress", "processing", "picking", "packing", "staging",
    "receiving", "reading", "counting", "closing", "running", "scheduled", "queued", "printing", "started",
    "loaded", "in_transit", "in_transit_inbound", "in_transit_transfer", "in_transit_intercompany",
    "in_transit_sales", "dispatched", "put_away", "putaway", "submitted", "picked", "packed", "shipped",
    "online", "connected", "waiting_dispatch"]),
  ...T("success", ["available", "completed", "done", "delivered", "received", "verified", "posted", "paid",
    "active", "passed", "confirmed", "settled", "green", "ok", "ready", "printed"]),
  ...T("warning", ["waiting_approval", "pending_approval", "waiting_goods", "waiting_stock", "waiting", "qc_pending",
    "qc_check", "review", "reconcile", "partially_received", "partially_shipped", "partial", "partially_picked",
    "partially_paid", "quarantine", "karantina", "hold", "on_hold", "blocked", "hold_shade", "escalated",
    "returning", "needs_review", "approved_with_exceptions", "completed_with_exception", "unknown",
    "received_hold", "low", "stale", "yellow", "warning"]),
  ...T("danger", ["rejected", "failed", "damaged", "qc_rejected", "exception", "verified_with_issues", "lost",
    "missing", "error", "overdue", "received_damaged", "red", "rework", "empty", "alarm"]),
  ...T("special", ["reserved", "committed", "subcon", "sample", "in_process", "earmarked"]),
};

/** Kode yang artinya berbeda di ranah tertentu. */
export const DOMAIN_TONE = {
  roll: { picked: "info", packed: "info", delivered: "neutral", hold: "warning" },
  task_out: { dispatched: "success", created: "neutral" },
  task_hp: { dispatched: "success", shipped: "success" },
  putaway: { returned: "warning", cancelled: "neutral", draft: "special" },
  print_job: { printed: "warning", partial: "warning" },
  print_item: { confirmed: "success" },
  transfer: { approved: "info", dispatched: "info", returned: "neutral" },
  lot: { released: "success", in_process: "info" },
  grn: { closed: "success" },
  cycle_count: { submitted: "warning" },
};

// ── 3. Ikon (nama ikon lucide; dipetakan ke komponen di `components/StatusBadge.jsx`) ─────────────────────────────
export const TONE_ICON = {
  neutral: "circle", info: "dot", success: "check", warning: "alert", danger: "x", special: "tag",
};
export const STATUS_ICON = {
  draft: "draft", cancelled: "ban", void: "ban", voided: "ban", rejected: "x", failed: "x",
  waiting_approval: "clock", pending_approval: "clock", waiting_goods: "clock", waiting_stock: "clock",
  waiting: "clock", pending: "clock", queued: "clock", scheduled: "clock", qc_pending: "shield", qc_check: "shield",
  quarantine: "shield", karantina: "shield", hold: "pause", on_hold: "pause", blocked: "pause", hold_shade: "pause",
  in_transit: "truck", in_transit_inbound: "truck", in_transit_transfer: "truck", in_transit_intercompany: "truck",
  in_transit_sales: "truck", dispatched: "truck", loaded: "truck", returning: "truck", shipped: "truck",
  escalated: "alert", closed: "archive", archived: "archive",
};

const _own = (m, k) => (m && Object.prototype.hasOwnProperty.call(m, k) ? m[k] : undefined);
const _key = (s) => String(s || "").trim().toLowerCase().replace(/[\s-]+/g, "_");

/** Label Indonesia sebuah status (ranah dulu, lalu peta umum). Kosong → "—". Tidak pernah kode mentah. */
export function statusLabel(status, domain) {
  if (status === null || status === undefined || status === "") return "—";
  const s = String(status);
  const dm = domain ? DOMAIN_LABELS[domain] : null;
  return _own(dm, s) || _own(dm, _key(s)) || docStatusLabel(s) || "—";
}

/** Nada sebuah status (ranah dulu, lalu umum, bawaan netral). */
export function statusTone(status, domain) {
  const k = _key(status);
  return _own(DOMAIN_TONE[domain], k) || _own(STATUS_TONE, k) || "neutral";
}

/** Nama ikon sebuah status: penimpaan per kode, lalu bawaan nada. */
export function statusIcon(status, tone) {
  return _own(STATUS_ICON, _key(status)) || TONE_ICON[tone] || TONE_ICON.neutral;
}

/** { label, tone, icon } untuk satu status. `label`/`tone` eksplisit (dari layar) menang. */
export function statusMeta(status, { domain, label, tone } = {}) {
  const t = TONES.includes(tone) ? tone : statusTone(status, domain);
  return { label: label || statusLabel(status, domain), tone: t, icon: statusIcon(status, t) };
}

/** Pil lama (`pill-*` / warna `Pill`) → nada baku. Dipakai pembungkus lama selama peralihan. */
export const LEGACY_TONE = {
  "pill-success": "success", "pill-info": "info", "pill-warning": "warning", "pill-danger": "danger",
  "pill-muted": "neutral", "pill-purple": "special",
  green: "success", blue: "info", info: "info", orange: "warning", red: "danger", purple: "special", gray: "neutral",
};

/** Label per ranah sebagai peta {kode: label} — untuk opsi saringan & kolom CSV layar. */
export const domainLabels = (domain) => ({ ...(DOMAIN_LABELS[domain] || {}) });
