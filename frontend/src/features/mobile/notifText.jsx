/**
 * Teks & tujuan notifikasi untuk SEMUA aplikasi HP (fase 3 · P7, L-09).
 *
 * Dulu hanya panel Notifikasi aplikasi HP Ops yang merapikan teks (tahap mentah → label Indonesia, nomor dokumen tak
 * patah, lencana "Putuskan di HP"); lonceng Sales/MD menampilkan teks server apa adanya. Kini lonceng `NotifSheet`
 * dipakai keempat aplikasi HP, jadi aturan teks pindah ke sini dan dipakai lembar notifikasi bersama.
 */
import { roleLabel } from "../../config/roles";
import { docStatusLabel } from "../../utils/docStatus";
import { resolveView } from "../../utils/viewAlias";

// Audit UI HP (manager) — status/tahap mentah di teks notifikasi ("tahap: pending_approval") → label Indonesia.
const STAGE_LABEL = {
  pending_approval: "menunggu persetujuan", pending: "menunggu", approved: "disetujui", rejected: "ditolak",
  draft: "draf", submitted: "diajukan", in_review: "ditinjau", inspecting: "diperiksa", received: "diterima",
  completed: "selesai", done: "selesai", cancelled: "dibatalkan", waiting_stock: "menunggu stok",
  // UAT 24 Okt (audit UI tahap 2, G5-10) — tahap giliran yang dulu tetap mentah ("tahap: shipped").
  waiting_approval: "menunggu persetujuan", confirmed: "dikonfirmasi", picked: "sudah diambil", shipped: "dikirim",
  partially_shipped: "dikirim sebagian", receiving: "sedang diterima", partial: "diterima sebagian",
  inspected: "selesai inspeksi", refund_settled: "selesai · pengembalian dana", credit_settled: "selesai · store credit",
  nego_settled: "selesai · nego", settled: "selesai · per roll (campuran)",
};
const lc = (t) => t.charAt(0).toLowerCase() + t.slice(1);
// Kode tak dikenal jatuh ke peta status bersama (docStatusLabel), bukan ke kode mentah.
export const stageText = (code) => STAGE_LABEL[code] || lc(docStatusLabel(code));
export const humanizeNotif = (text) => String(text || "")
  .replace(/\b(tahap|status):\s*([a-z][a-z_]+)/g, (m, k, code) => `${k}: ${stageText(code)}`)
  // Eskalasi lama: "… oleh all." / "oleh manager." (kode peran mentah dari server).
  .replace(/\boleh (all|[a-z][a-z_]*)\./g, (m, r) => (r === "all" ? "oleh semua penerima." : roleLabel(r) !== r ? `oleh ${roleLabel(r)}.` : m))
  .replace(/\bAvailable\b/g, "Tersedia");

// G5-57 — nomor dokumen ("SRET-00158", "KSC/SOS-00014") tidak boleh patah di tengah saat judul dibungkus.
const DOC_NO = /((?:[A-Z]{2,6}\/)?[A-Z]{2,6}-\d[\d-]*)/;
export function NoBreakNumbers({ text }) {
  return String(text || "").split(DOC_NO).map((part, i) => (i % 2 ? <span key={i} className="whitespace-nowrap">{part}</span> : part));
}

/** Tautan notifikasi ("?view=orders", "/special-orders") → id layar (alias lama dipetakan). "" bila tanpa tautan. */
export const notifLink = (n) => String(n?.link || "").replace(/^\/?(\?view=)?/, "");
export const linkView = (n) => { const l = notifLink(n); return l ? resolveView(l) : ""; };

// UAT 24 Okt (audit UI tahap 2, G5-09) — lencana "Putuskan di HP" hanya bila dokumennya BENAR-BENAR ada di daftar
// Persetujuan HP (harga khusus via action_id, PO custom via ref/nomor) — dulu dari regex teks dan membuka tab kosong.
const sordIdOf = (n) => (String(n.ref || "").match(/so_custom_appr:([A-Za-z0-9_]+)/) || [])[1] || "";
const sordNoOf = (n) => (String(n.title || "").match(/(?:[A-Z]{2,6}\/)?SORD-[\d-]+/) || [])[0] || "";
export function decisionTarget(n, prices, specials) {
  if (n.action_type === "price_approval_view" && (prices || []).some((p) => p.id === n.action_id)) return n.action_id;
  if (n.type === "special_order_approval" || n.link === "special-orders") {
    const id = sordIdOf(n);
    if (id && (specials || []).some((s) => s.id === id)) return id;
    const no = sordNoOf(n);
    const hit = no && (specials || []).find((s) => s.number === no);
    if (hit) return hit.id;
  }
  return "";
}

/**
 * G5-57 — notifikasi identik (eskalasi lama yang tersalin per penerima) digabung jadi satu kartu `×N`.
 * → [{ n, ids }] dengan urutan kemunculan pertama.
 */
export function groupNotifications(rows) {
  const groups = [];
  const byKey = new Map();
  (rows || []).forEach((n) => {
    const k = `${n.type}|${n.title}|${n.body}|${n.read ? 1 : 0}`;
    if (byKey.has(k)) { byKey.get(k).ids.push(n.id); return; }
    const g = { n, ids: [n.id] };
    byKey.set(k, g); groups.push(g);
  });
  return groups;
}
