/**
 * rincianKomisi.js — KA-10 · teks rincian faktor komisi per artikel untuk sales (kartu "Capaian & Insentif Saya" dan
 * Beranda Sales). Hanya memformat kunci daftar putih server (`incentive_me.KUNCI_RINCIAN`); tidak pernah menampilkan
 * angka margin/HPP — baris yang dibatasi hanya diberi kata "dibatasi batas margin".
 *
 * BTP-5 (keputusan pemilik A1-6) — dua jenis baris bukan artikel biasa, dikenali dari `price_reason` server:
 *  - "koreksi": komisi barang yang tidak jadi dikirim dipotong di bulan penutupan (pesanan dibatalkan sesudah bayar /
 *    sisa pesanan ditutup) — jumlah & komisi negatif, `keterangan` = pesanan + alasan dari server;
 *  - "saldo": potongan yang terbawa dari bulan lalu (negatif) atau sisa potongan yang dibawa ke bulan berikutnya —
 *    tanpa tarif/pengali, hanya `keterangan`.
 */
import { formatCurrency, formatDecimal } from "../../utils/formatters";

export const TEKS_DIBATASI = "dibatasi batas margin";
export const KODE_KOREKSI = ["koreksi_batal", "koreksi_tutup_sisa"];
export const KODE_SALDO = ["potongan_terbawa", "potongan_dibawa"];

/** Pengali → "×0,8"; kosong/tak sah (mis. capaian bulan tak berlaku) → "—". */
export function formatPengali(v) {
  if (v === null || v === undefined || v === "" || Number.isNaN(Number(v))) return "—";
  return `×${formatDecimal(Number(v), 2)}`;
}

/** M6 (tinjauan akhir) — nilai komisi satu baris untuk layar: `{nilai, negatif}`. Server menulis baris
 *  `potongan_dibawa` POSITIF (penyeimbang supaya Σ rincian = total bulan ini, yang tidak pernah negatif), padahal maknanya
 *  POTONGAN yang dipindah ke bulan berikutnya → ditampilkan sebagai pengurang (bertanda minus). Koreksi dan potongan
 *  terbawa memang negatif dari server. `negatif` → layar mewarnainya merah (`KELAS_NEGATIF`). */
export function nilaiKomisi(b) {
  const v = Number(b?.commission || 0);
  const nilai = b?.price_reason === "potongan_dibawa" ? -Math.abs(v) : v;
  return { nilai, negatif: nilai < 0 };
}

export const KELAS_NEGATIF = "text-[#C0392B]";
export const KELAS_POSITIF = "text-[#1B7F4B]";

/** Kelas warna nilai komisi: merah untuk pengurang (negatif), hijau selain itu. */
export function kelasNilaiKomisi(b) {
  return nilaiKomisi(b).negatif ? KELAS_NEGATIF : KELAS_POSITIF;
}

/** Jenis baris rincian: "koreksi" | "saldo" | "biasa". */
export function jenisRincian(b) {
  const kode = b?.price_reason || "";
  if (KODE_KOREKSI.includes(kode)) return "koreksi";
  if (KODE_SALDO.includes(kode)) return "saldo";
  return "biasa";
}

/** Satu baris rincian → teks siap tampil. Pengali harga disertai alasannya bila ada ("×0,8 · diskon 2–3%"); `asal` = asal
 *  tarif dari server ("Tarif artikel (PT ini)", "Tarif varian (PT ini)", "Tarif kategori (Semua PT)") — KA-11: dua baris
 *  artikel yang sama bisa bertarif beda (pengecualian varian), sales perlu tahu sebabnya (rancangan 6.1 "tarif + asalnya").
 *  BTP-5 — `jenis` + `keterangan`: baris koreksi menulis pesanan & alasannya terpisah dari pengali harga; baris saldo
 *  potongan tidak punya tarif/pengali ("—"). */
export function ringkasRincian(b) {
  const jenis = jenisRincian(b);
  if (jenis === "saldo") {
    return { jenis, satuan: "", tarif: "—", asal: "", pengaliHarga: "—", pengaliCapaian: "—", dibatasi: false,
      catatanBatas: "", keterangan: b?.price_reason_label || b?.name || "" };
  }
  const alasan = jenis === "biasa" && b?.price_reason_label ? ` · ${b.price_reason_label}` : "";
  const satuan = b?.unit || "satuan";
  return {
    jenis,
    satuan,
    tarif: `${formatCurrency(b?.rate || 0)}/${satuan}`,
    asal: b?.rate_origin || "",
    pengaliHarga: `${formatPengali(b?.price_factor)}${alasan}`,
    pengaliCapaian: formatPengali(b?.achievement_factor),
    dibatasi: !!b?.capped,
    catatanBatas: b?.capped ? TEKS_DIBATASI : "",
    keterangan: jenis === "koreksi" ? (b?.price_reason_label || "") : "",
  };
}
