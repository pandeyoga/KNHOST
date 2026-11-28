/**
 * jenisKas — Kas & Bank bagian 3 (Tugas 4a): kosakata & aturan layar jenis kas rekening, dana tetap, lokasi (tanpa React).
 *
 * Satu sumber untuk form rekening (`BankAccountForm`), kartu rekening (`BankAccountsView` / `RekeningKasParts`),
 * perubahan menunggu (`BankAccountChangesPanel`), dan Kas Kecil › Dana tetap. Aturan mengikuti server
 * (`backend/services/bank_service.py`): `account_cash_type`, `PESAN_*`, `JENIS_BERLOKASI`, `alasan_jenis_kas_terkunci`
 * — server tetap penentu (galat tampil di tempat). Rancangan §5.1, §5.2, §7.8 butir 5.
 */
import { can } from "../../config/roles";

/** Label jenis kas (= `cash_ledger.CASH_TYPE_LABEL`, huruf kecil seperti lencana kartu). */
export const JENIS_KAS_LABEL = { kas_kasir: "Kas kasir", kas_kecil: "Kas kecil", kas_besar: "Kas besar" };
export const labelJenisKas = (ct) => JENIS_KAS_LABEL[ct] || ct || "";

/** Pilihan jenis kas rekening tunai baru (§5.1: bank → kas besar seperti sekarang). */
export const PILIHAN_JENIS_KAS_TUNAI = [
  { value: "kas_kasir", label: "Kas Kasir" },
  { value: "kas_kecil", label: "Kas Kecil" },
];

/** Jenis kas yang boleh berlokasi kerja (`bank_service.JENIS_BERLOKASI`). */
export const JENIS_BERLOKASI = ["kas_kasir", "kas_kecil"];

/** Jenis kas TETAP rekening = server `bank_service.account_cash_type`: tersimpan bila sah, selain itu dari jenis rekening
 *  (tunai = kas kecil, bank = kas besar). */
export function jenisKasRekening(a) {
  if (a && Object.prototype.hasOwnProperty.call(JENIS_KAS_LABEL, a.cash_type)) return a.cash_type;
  return a?.account_type === "cash" ? "kas_kecil" : "kas_besar";
}

/** Kalimat alasan jenis kas tidak bisa diubah — SAMA dengan `bank_service.alasan_jenis_kas_terkunci` (server hanya
 *  mengirim `jenis_kas_terkunci: bool`; kalimat dipilih dari `gl_account_code`, yang juga dipakai server). "" = boleh. */
export function alasanJenisKasTerkunci(a) {
  if (!a?.jenis_kas_terkunci) return "";
  const nama = a.name || "";
  if (a.gl_account_code) {
    return `Jenis kas rekening ${nama} tidak bisa diubah karena akun buku besarnya (${a.gl_account_code}) dibuat untuk `
      + "jenis kas itu. Nonaktifkan rekening ini lalu buat rekening baru dengan jenis kas yang benar.";
  }
  return `Jenis kas rekening ${nama} tidak bisa diubah karena rekening ini sudah punya transaksi kas. Pindahkan `
    + "saldonya lewat Pindah Dana ke rekening baru dengan jenis kas yang benar.";
}

/** Rekening kas kecil yang memakai dana tetap (dana tetap > 0). */
export const pakaiDanaTetap = (a) => jenisKasRekening(a) === "kas_kecil" && Number(a?.dana_tetap) > 0;

/** Aksi "Isi ulang" ditawarkan: izin `cash.create` (server rute isi ulang) + rekening kas kecil aktif berdana tetap.
 *  Alasan lain (isi ulang terbuka, tidak perlu) ditulis server di posisi dana tetap (`alasan_isi_ulang`). */
export const bolehIsiUlang = (a, perms) => can(perms, "cash", "create") && a?.is_active !== false && pakaiDanaTetap(a);

/** Kas & Bank 3 (ketetapan R4, server `bank_account_change_service.PESAN_BAWAAN_TUNAI_KASIR`) — di PT yang punya kas
 *  kasir penerima, bawaan penerimaan tunai selalu rekening kas kasir; mencentangnya di rekening lain ditolak server. */
export const PESAN_BAWAAN_TUNAI_KASIR = "PT ini punya rekening kas kasir, jadi bawaan penerimaan tunai selalu rekening kas kasir.";

/** Cara bayar `kode` yang bawaannya dipegang kas kasir PT untuk rekening `accountId` (jenis kas `cashType`) — sama dengan
 *  server `_periksa_bawaan_tunai`: rekening bukan kasir, ada kas kasir LAIN yang aktif, berperuntukan penerimaan pelanggan,
 *  dan melayani cara bayar itu (`rekeningPt` = rekening PT dari `GET /bank-accounts`, nilai yang berlaku). */
export function bawaanDipegangKasir(rekeningPt, accountId, cashType, kode) {
  if (cashType === "kas_kasir") return false;
  return (rekeningPt || []).some((a) => a.id !== accountId && a.is_active !== false && jenisKasRekening(a) === "kas_kasir"
    && (a.purposes || []).includes("penerimaan_pelanggan") && (a.payment_method_codes || []).includes(kode));
}

/** Label rekening sumber isi ulang: "{nama} · {bank} {nomor}". */
export function labelSumber(s) {
  const bank = [s?.bank_name, s?.account_number].filter(Boolean).join(" ");
  return `${s?.name || "Rekening"}${bank ? ` · ${bank}` : ""}`;
}
