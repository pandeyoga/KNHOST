// PREP-C (K-GDG-10, 8 Nov 2026) — utilitas murni Putaway Order: label status (draf, tiba sebagian, dikembalikan),
// hitungan roll menunggu, dan ringkasan kesiapan draf. Sama dengan backend `putaway_arrival_service.final_status`.
export const PA_STATUS = {
  draft: ["#6B219A", "Draf — cek & terbitkan"],
  open: ["#0058CC", "Terbuka"],
  in_transit: ["#FF9500", "Dalam Perjalanan"],
  partially_received: ["#8C4A00", "Tiba Sebagian"],
  completed: ["#1B7F4B", "Selesai"],
  completed_with_exception: ["#8C4A00", "Selesai + Exception"],
  exception: ["#C0341D", "Exception"],
  returned: ["#6B6B73", "Dikembalikan ke Transit"],
  cancelled: ["#6B6B73", "Draf Dibatalkan"],
};
export const ARRIVAL_STATUSES = ["open", "in_transit", "partially_received"];
export const statusOf = (o) => PA_STATUS[o?.status] || ["#6B6B73", o?.status || "—"];

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
