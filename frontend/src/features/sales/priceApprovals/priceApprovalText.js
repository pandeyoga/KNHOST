/**
 * UAT 24 Okt (audit UI tahap 2) — teks bersama kartu pengajuan harga khusus (desktop & HP).
 *  - discountInfo  : arah selisih harga. discount_percent > 0 = di bawah harga normal ("−12%");
 *                    < 0 = harga yang diajukan DI ATAS harga normal (dulu tampil "−-3064%").
 *  - requesterName : pengajuan dari checkout/SO menyimpan nama di `requested_by` (+ `requested_by_id`),
 *                    pengajuan biasa di `requested_by_name` — dulu kartu SO selalu "Pengaju: —".
 *  - deciderName   : akun sistem/kode keputusan internal (mis. "sistem (KLR-05)") tidak ditampilkan mentah.
 */
import { formatPct } from "../../../utils/formatters";
import { actorLabel } from "../../../utils/actorLabel";
import { stripInternalCodes } from "../../../utils/cleanText";

export function discountInfo(discountPercent) {
  const dp = Number(discountPercent || 0);
  if (!dp) return null;
  // ≥ 100% (harga salah ketik) dibulatkan; selebihnya satu desimal id-ID tanpa ",0".
  const pct = formatPct(Math.abs(dp), Math.abs(dp) >= 100 ? 0 : 1, { trim: true });
  return dp > 0
    ? { above: false, short: `−${pct}`, long: `−${pct}` }
    : { above: true, short: `+${pct}`, long: `+${pct} di atas harga normal` };
}

// G2-14 — opsi pemilih pelanggan: nama kembar dibedakan dengan kode & kota ("Toko A · CUST-0012 · Bandung").
export function customerOptionLabel(c) {
  return [c?.name, c?.code, c?.city].filter(Boolean).join(" · ") || c?.id || "";
}

export function requesterName(r, fallback = "—") {
  const name = r?.requested_by_name || (r?.requested_by_id ? r?.requested_by : "");
  return actorLabel(name, fallback);
}

// Kode keputusan internal (KLR-05, KLX-03, …) dibuang; "sistem (harga asal retur)" untuk pengganti retur.
export function deciderName(r, fallback = "") {
  if (!r?.approved_by_name) return fallback;
  if (r.source === "return_replacement" && /^sistem\b/i.test(r.approved_by_name)) return "Sistem (harga asal retur)";
  return actorLabel(stripInternalCodes(String(r.approved_by_name)), fallback);
}
