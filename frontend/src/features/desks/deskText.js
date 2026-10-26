/**
 * deskText — teks baris antrean Meja Peran (RoleDesk) tanpa kode mentah.
 *
 * Fase 4 · R6 (sisa audit UI tahap 2, G5-10): notifikasi giliran LAMA di "Giliran saya" masih berteks
 * "tahap: cancelled"; baris antrean lain menulis kode apa adanya di subjudul ("waiting_approval · Budi",
 * "outbound · 12 yard", "motif") dan nomor jatuh ke id teknis ("wms_bef96c0e9725") bila dokumennya tak bernomor.
 * Notifikasi baru sudah berlabel dari server; data lama & subjudul dirapikan di sini (satu tempat, teruji).
 */
import { docStatusLabel, hasDocStatusLabel } from "../../utils/docStatus";

const FLOW_LABEL = { inbound: "Terima barang", outbound: "Kirim barang", sample_cut: "Potong sample" };
// Sama dengan `DSR_TARGET_LABEL` (features/design/designRequestsApi.js) — jenis target permintaan desain.
const TARGET_LABEL = { motif: "Motif", pattern: "Pattern / Pola", artwork: "Artwork Printing" };
const CODE = /^[a-z][a-z_]*$/;
const TECH_ID = /^[a-z][a-z0-9]*_[0-9a-f]{6,}$/;

/** "tahap: refund_settled" → "tahap: selesai · refund" (huruf kecil, sama dengan pola lama RoleDesk). */
export const humanizeStage = (text) => (typeof text !== "string" ? text
  : text.replace(/\b(tahap|status):\s*([a-z][a-z_]+)/g, (m, k, code) => `${k}: ${docStatusLabel(code).toLowerCase()}`));

/** Satu potongan subjudul yang berupa kode mentah → label; potongan lain apa adanya. */
const segLabel = (seg) => {
  if (!CODE.test(seg)) return seg;
  if (FLOW_LABEL[seg]) return FLOW_LABEL[seg];
  if (TARGET_LABEL[seg]) return TARGET_LABEL[seg];
  return hasDocStatusLabel(seg) ? docStatusLabel(seg) : seg;
};

/** Subjudul antrean: "waiting_approval · Budi" → "Menunggu persetujuan · Budi". */
export const humanizeSubtitle = (text) => (typeof text !== "string" || !text ? text
  : humanizeStage(text).split(" · ").map((s) => segLabel(s.trim())).join(" · "));

/** Nomor baris yang jatuh ke id teknis → nomor turunan tugas gudang (GRN-/PICK-, sama dengan dokumen cetak) atau "". */
export const deskNumber = (row) => {
  const n = String(row?.number || "");
  if (!TECH_ID.test(n)) return n;
  if (row?.ref_type === "wms_task") return `${row.flow_type === "inbound" ? "GRN" : "PICK"}-${n.slice(-6).toUpperCase()}`;
  return "";
};

/** Rapikan seluruh baris antrean (judul, subjudul, nomor). Baris asli tetap di `_raw` — aksi (buka dokumen,
 *  saring layar tujuan) memakai nomor/id apa adanya dari server, bukan teks tampilan. */
export const humanizeQueueRows = (queues = []) => queues.map((q) => ({
  ...q,
  rows: (q.rows || []).map((r) => ({ ...r, number: deskNumber(r), title: humanizeStage(r.title),
    subtitle: humanizeSubtitle(r.subtitle), _raw: r })),
}));
