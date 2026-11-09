// PREP-C (K-GDG-10, 8 Nov 2026) — utilitas murni Putaway Order: label status (draf, tiba sebagian, dikembalikan),
// hitungan roll menunggu, dan ringkasan kesiapan draf. Sama dengan backend `putaway_arrival_service.final_status`.
// FIX-8 (KN_37 §8) — label status PA dipindah ke kosakata tunggal `utils/statusVocab.js` (ranah "putaway", istilah
// sama persis); warna/ikon dari nada kosakata (lencana StatusBadge). `PA_STATUS` tetap {kode: [nada, label]}.
import { DOMAIN_LABELS, statusLabel, statusTone } from "../../utils/statusVocab";

export const PA_STATUS = Object.fromEntries(Object.entries(DOMAIN_LABELS.putaway)
  .map(([k, label]) => [k, [statusTone(k, "putaway"), label]]));
export const ARRIVAL_STATUSES = ["open", "in_transit", "partially_received"];
/** [nada, label] — dulu [hex, label]. */
export const statusOf = (o) => [statusTone(o?.status, "putaway"), statusLabel(o?.status, "putaway")];

export const countBy = (items, status) => (items || []).filter((i) => (i.status || "pending") === status).length;
export const pendingCount = (o) => countBy(o?.items, "pending");

/** Kesiapan draf → {ready, notReady, inspection}. Roll belum siap = tag/label belum terverifikasi atau berubah. */
export function draftReadiness(detail) {
  const items = detail?.items || [];
  return {
    ready: items.filter((i) => i.ready).length,
    notReady: items.filter((i) => i.ready === false).length,
    inspection: items.filter((i) => i.inspection_requested).length,
  };
}

export const purposeLabel = (p) => (p === "inspection" ? "ke gedung inspeksi" : "ke gudang simpan");

/** Kode hasil baca handheld/gate dari teks bebas (spasi/koma/titik koma/baris baru). */
export const parseCodes = (text) => String(text || "").split(/[\s,;]+/).map((x) => x.trim()).filter(Boolean);

/** Pesan satu trip tiba untuk layar. */
export function tripMessage(o) {
  const t = o?.trip || {};
  if (o?.duplicate_trip) return "Trip ini sudah tercatat sebelumnya — tidak dicatat dua kali.";
  const n = (t.arrived_roll_nos || []).length;
  const rest = pendingCount(o);
  const parts = [n ? `${n} roll tiba` : "Tidak ada roll baru yang tiba"];
  if ((t.already_roll_nos || []).length) parts.push(`${t.already_roll_nos.length} sudah tiba sebelumnya`);
  if ((t.unknown_epcs || []).length) parts.push(`${t.unknown_epcs.length} kode bukan milik PA ini`);
  parts.push(rest ? `${rest} roll masih menunggu` : "semua roll sudah diputuskan");
  return parts.join(" · ") + (o?.btg_number ? ` — BTG ${o.btg_number}` : "");
}
