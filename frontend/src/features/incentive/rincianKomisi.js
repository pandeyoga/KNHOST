/**
 * rincianKomisi.js — KA-10 · teks rincian faktor komisi per artikel untuk sales (kartu "Capaian & Insentif Saya" dan
 * Beranda Sales). Hanya memformat kunci daftar putih server (`incentive_me.KUNCI_RINCIAN`); tidak pernah menampilkan
 * angka margin/HPP — baris yang dibatasi hanya diberi kata "dibatasi batas margin".
 */
import { formatCurrency, formatDecimal } from "../../utils/formatters";

export const TEKS_DIBATASI = "dibatasi batas margin";

/** Pengali → "×0,8"; kosong/tak sah (mis. capaian bulan tak berlaku) → "—". */
export function formatPengali(v) {
  if (v === null || v === undefined || v === "" || Number.isNaN(Number(v))) return "—";
  return `×${formatDecimal(Number(v), 2)}`;
}

/** Satu baris rincian → teks siap tampil. Pengali harga disertai alasannya bila ada ("×0,8 · diskon 2–3%"); `asal` = asal
 *  tarif dari server ("Tarif artikel (PT ini)", "Tarif varian (PT ini)", "Tarif kategori (Semua PT)") — KA-11: dua baris
 *  artikel yang sama bisa bertarif beda (pengecualian varian), sales perlu tahu sebabnya (rancangan 6.1 "tarif + asalnya"). */
export function ringkasRincian(b) {
  const alasan = b?.price_reason_label ? ` · ${b.price_reason_label}` : "";
  const satuan = b?.unit || "satuan";
  return {
    satuan,
    tarif: `${formatCurrency(b?.rate || 0)}/${satuan}`,
    asal: b?.rate_origin || "",
    pengaliHarga: `${formatPengali(b?.price_factor)}${alasan}`,
    pengaliCapaian: formatPengali(b?.achievement_factor),
    dibatasi: !!b?.capped,
    catatanBatas: b?.capped ? TEKS_DIBATASI : "",
  };
}
