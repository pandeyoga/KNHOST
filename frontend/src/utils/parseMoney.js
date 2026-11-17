/**
 * parseMoney (Pelatihan Keuangan 18 Nov · uji variasi isian) — pembaca nominal RUPIAH yang diketik / ditempel pengguna.
 *
 * Masalah yang diperbaiki: `MoneyInput` dulu memakai aturan desimal umum (`decimalInput.isDecimalDraft`): hanya SATU
 * pemisah boleh diketik. Mengetik "3.374.123" huruf demi huruf menjadi "3.374123" (= Rp 3,37 — nominal salah tanpa
 * peringatan); menempel "Rp 3.374.123" / "3,374,123" ditolak diam-diam; dan layar yang membaca nilainya dengan
 * `Number(v)` (form kwitansi, transaksi kas, LPJ kas kecil) membaca "3374122,5" sebagai 0.
 *
 * Aturan (khusus uang; untuk qty/desimal umum tetap `decimalInput.parseDecimal`):
 *  · Awalan "Rp"/"IDR", spasi (juga NBSP), dan akhiran ",-" diabaikan; tanda minus di depan boleh.
 *  · Ada titik DAN koma → pemisah yang paling KANAN adalah desimal ("3.374.122,50" · "3,374,122.50").
 *  · Pemisah yang sama muncul > 1 kali → pemisah ribuan ("3.374.123" · "3,374,123").
 *  · Satu pemisah: diikuti tepat 3 angka dengan bagian depan 1–3 angka (bukan 0) → ribuan ("1.500" = 1500);
 *    selain itu desimal ("3374122,5" · "3374122.5" · "0,500").
 *  · Pemisah di ujung saat masih mengetik ("3374122,") diabaikan.
 */

const SPASI = /[\s\u00a0\u202f]/g;

function bersihkan(value) {
  let t = String(value).replace(SPASI, "").replace(/−/g, "-");
  let neg = false;
  if (t.startsWith("-")) { neg = true; t = t.slice(1); }
  t = t.replace(/^(?:rp|idr)\.?/i, "");
  if (t.startsWith("-")) { neg = true; t = t.slice(1); }
  t = t.replace(/[.,]-$/, "");
  return { t, neg };
}

/** Teks/angka → nominal (Number). Kosong / bukan angka → NaN. */
export function parseMoney(value) {
  if (value === null || value === undefined) return NaN;
  if (typeof value === "number") return value;
  const { t: raw, neg } = bersihkan(value);
  const t = raw.replace(/[.,]+$/, "");
  if (!t || !/^\d[\d.,]*$/.test(t)) return NaN;
  const dots = (t.match(/\./g) || []).length;
  const commas = (t.match(/,/g) || []).length;
  let norm;
  if (dots && commas) {
    norm = t.lastIndexOf(",") > t.lastIndexOf(".")
      ? t.replace(/\./g, "").replace(",", ".")
      : t.replace(/,/g, "");
  } else if (dots + commas === 0) {
    norm = t;
  } else {
    const sep = dots ? "." : ",";
    const n = dots || commas;
    const ribuan = n > 1 || new RegExp(`^[1-9]\\d{0,2}\\${sep}\\d{3}$`).test(t);
    norm = ribuan ? t.split(sep).join("") : t.replace(sep, ".");
  }
  if (!/^\d+(\.\d+)?$/.test(norm)) return NaN;
  const out = Number(norm);
  return neg ? -out : out;
}

/** true bila teks masih wajar sebagai nominal yang sedang diketik/ditempel (huruf lain ditolak). */
export function isMoneyDraft(value) {
  if (value === null || value === undefined || value === "") return true;
  const s = String(value).replace(SPASI, " ").replace(/−/g, "-");
  return /^\s*-?\s*(?:(?:rp|idr)\.?|r|i|id)?\s*-?\s*[\d., ]*(?:[.,]-)?\s*$/i.test(s);
}

/** Teks kanonik untuk pemanggil `MoneyInput.onChange`: angka JS polos bertitik desimal ("3374122.5"), "" bila kosong /
 *  belum berupa angka. Aman dibaca `Number()`, `parseDecimal()`, maupun `parse_decimal` di backend. */
export function moneyText(value) {
  const n = parseMoney(value);
  return Number.isFinite(n) ? String(n) : "";
}

/** Nilai yang DIPEGANG pemanggil (angka, teks kanonik, atau teks lama) → Number. Teks angka polos ("1234.5") dibaca
 *  apa adanya (titik = desimal, seperti `Number`), teks lain lewat `parseMoney`. */
export function heldMoney(value) {
  if (value === null || value === undefined || value === "") return NaN;
  if (typeof value === "number") return value;
  const s = String(value).trim();
  return /^-?\d+(\.\d+)?$/.test(s) ? Number(s) : parseMoney(s);
}
