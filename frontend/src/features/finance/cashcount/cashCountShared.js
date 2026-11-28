/**
 * cashCountShared — Kas & Bank bagian 3 (Tugas 4b): kosakata & aturan layar Opname Kas (tanpa React).
 *
 * Satu sumber untuk daftar (`CashCountsView`), form Hitung (`CashCountForm`, juga di Meja Keuangan), pop-up Setujui
 * (`CashCountApproveModal`), aksi kartu rekening (`OpnameKartuAksi`) dan pratinjau dokumen
 * (`documents/preview/bodies/CashCountPreview`). Aturan mengikuti server (`backend/services/cash_count_service.py`,
 * `routers/cash_counts.py`): hitung `cash.create`; Setujui/Tolak hanya untuk `menunggu_persetujuan` dan pemegang
 * `cash.approve` (Setujui nonaktif bagi penghitung dengan kalimat server `kontrol.pesan`; penghitung BOLEH menolak
 * hitungannya sendiri — tidak menggerakkan uang); piutang karyawan hanya untuk kekurangan kas. Izin, bukan nama peran.
 * Server tetap penentu (galat tampil di tempat aksi).
 */
import { can } from "../../../config/roles";
import { formatCurrency, formatDate } from "../../../utils/formatters";
import { PESAN_SEDANG_DIPROSES } from "../cashout/cashOutShared";

export const MENUNGGU = "menunggu_persetujuan";

export const STATUS_OPNAME = {
  menunggu_persetujuan: { label: "Menunggu persetujuan", tone: "warning", icon: "clock" },
  selesai: { label: "Selesai", tone: "success", icon: "check" },
  disetujui: { label: "Disetujui", tone: "success", icon: "check" },
  ditolak: { label: "Ditolak", tone: "danger", icon: "x" },
};
export const statusOpname = (s) => STATUS_OPNAME[s] || { label: s || "—", tone: "neutral", icon: "circle" };

/** Pilihan saringan status (dropdown, pola UI §1.2). */
export const PILIHAN_STATUS = [
  { value: "", label: "Semua status" },
  ...Object.entries(STATUS_OPNAME).map(([value, s]) => ({ value, label: s.label })),
];

/** Perlakuan selisih (server `cash_count_service.PERLAKUAN_LABEL`). */
export const PERLAKUAN = { selisih_kas: "Selisih kas", piutang_karyawan: "Piutang karyawan" };

export const JEJAK_LABEL = { hitung: "Dihitung", setujui: "Disetujui", tolak: "Ditolak" };

export const ALASAN_MIN = 5;   // sama dengan server (K-14: alasan minimum 5 huruf)

/**
 * Pecahan uang rupiah yang beredar (kertas 100.000–1.000, logam 1.000–100) — alat bantu hitung, BUKAN aturan bisnis:
 * rincian pecahan opsional dan server menerima nilai pecahan berapa pun (> 0).
 */
export const PECAHAN_RUPIAH = [100000, 50000, 20000, 10000, 5000, 2000, 1000, 500, 200, 100];

export const TEKS_BANTU = "Opname kas mencocokkan uang fisik di rekening tunai (kas kasir, kas kecil, kas besar tunai) "
  + "dengan saldo bukunya. Hitung uangnya dulu: saldo buku dipotret sistem saat hitungan disimpan, lalu selisih = uang "
  + "fisik − saldo buku. Tanpa selisih, opname langsung selesai. Ada selisih → orang kedua yang berizin menyetujui kas "
  + "memutuskan: selisih kas (lebih atau kurang) atau piutang karyawan (kurang saja, atas nama karyawan yang menanggung). "
  + "Ditolak → hitung ulang. Saldo rekening bank dicocokkan lewat Rekonsiliasi Bank.";

const angka = (v) => (v === "" || v === null || v === undefined ? NaN : Number(v));
const lembarOf = (v) => {
  const n = Math.floor(Number(v));
  return Number.isFinite(n) && n > 0 ? n : 0;
};

/** Jumlah rupiah dari `{nilai: lembar}` (lembar kosong/negatif = 0). */
export function totalPecahan(lembar = {}) {
  return PECAHAN_RUPIAH.reduce((s, nilai) => s + nilai * lembarOf(lembar[nilai]), 0);
}

/** Baris pecahan yang dikirim (`[{nilai, lembar}]`, besar ke kecil, hanya yang berlembar). */
export function barisPecahan(lembar = {}) {
  return PECAHAN_RUPIAH.filter((nilai) => lembarOf(lembar[nilai]) > 0).map((nilai) => ({ nilai, lembar: lembarOf(lembar[nilai]) }));
}

/** Validasi isian form Hitung (kalimat sama dengan server; jumlah fisik 0 = laci kosong, sah). */
export function validasiHitung(f = {}) {
  if (!f.account_id) return "Pilih rekening tunai yang dihitung.";
  if (f.pakaiPecahan) {
    if (barisPecahan(f.lembar).length === 0) return "Isi jumlah uang fisik yang dihitung (atau rincian pecahannya).";
    return "";
  }
  const n = angka(f.jumlah_fisik);
  if (!Number.isFinite(n)) return "Isi jumlah uang fisik yang dihitung (atau rincian pecahannya).";
  if (n < 0) return "Jumlah uang fisik tidak boleh negatif.";
  return "";
}

/** Badan `POST /api/cash-counts`. Dengan rincian pecahan, jumlah fisik = total pecahan (server memeriksa keduanya sama). */
export function badanHitung(f = {}) {
  const catatan = String(f.catatan || "").trim();
  if (f.pakaiPecahan) {
    return { account_id: f.account_id, jumlah_fisik: totalPecahan(f.lembar), pecahan: barisPecahan(f.lembar), catatan };
  }
  return { account_id: f.account_id, jumlah_fisik: Number(f.jumlah_fisik), pecahan: [], catatan };
}

/** Selisih dalam kata: "Lebih Rp …" / "Kurang Rp …" / "Tanpa selisih" (dari `selisih` bertanda server). */
export function selisihTeks(d) {
  const s = Number(d?.selisih) || 0;
  if (Math.abs(s) < 0.005) return "Tanpa selisih";
  return `${s > 0 ? "Lebih" : "Kurang"} ${formatCurrency(Math.abs(s))}`;
}

/** Nada teks selisih (token `kn-*`). */
export const selisihNada = (d) => {
  const s = Number(d?.selisih) || 0;
  if (Math.abs(s) < 0.005) return "text-kn-text-2";
  return s > 0 ? "text-kn-success-text" : "text-kn-danger-text";
};

/** Pilihan perlakuan untuk opname `d`: piutang karyawan hanya untuk kekurangan kas (`boleh_piutang` server). */
export function opsiPerlakuan(d) {
  const kurang = typeof d?.boleh_piutang === "boolean" ? d.boleh_piutang : (Number(d?.selisih) || 0) < 0;
  return [
    { value: "selisih_kas", label: PERLAKUAN.selisih_kas },
    ...(kurang ? [{ value: "piutang_karyawan", label: PERLAKUAN.piutang_karyawan }] : []),
  ];
}

/**
 * Ringkasan dampak persetujuan (pola N5: nominal, rekening, arah, akun lawan, tanggal) — tanpa kode akun (dipetakan per PT).
 * `karyawan` = `{name, code}` terpilih (piutang karyawan).
 */
export function ringkasanSetujui(d, perlakuan, karyawan) {
  if (!d || !perlakuan) return "";
  const nominal = formatCurrency(Math.abs(Number(d.selisih) || 0));
  const rekening = d.account_name || "rekening ini";
  const tgl = d.tanggal ? ` bertanggal ${formatDate(d.tanggal)}` : "";
  if ((Number(d.selisih) || 0) > 0) {
    return `Kas masuk ${nominal} ke ${rekening}${tgl}, dibukukan ke akun Selisih Kas (pendapatan lain-lain).`;
  }
  if (perlakuan === "piutang_karyawan") {
    const siapa = karyawan ? `${karyawan.name}${karyawan.code ? ` (${karyawan.code})` : ""}` : "karyawan yang dipilih";
    return `Kas keluar ${nominal} dari ${rekening}${tgl}, dicatat sebagai piutang karyawan atas nama ${siapa} `
      + "(akun Piutang Karyawan – Kekurangan Kas).";
  }
  return `Kas keluar ${nominal} dari ${rekening}${tgl}, dibebankan ke akun Selisih Kas (beban lain-lain).`;
}

/**
 * Aksi baris untuk opname `d` dan izin `perms` → { setujui, tolak }.
 * Tiap aksi: null (tidak ditawarkan) atau { label, alasan } (alasan terisi = tombol nonaktif dengan alasan tertulis —
 * Setujui memakai kalimat server `kontrol.pesan`; penghitung tetap boleh menolak hitungannya sendiri).
 */
export function aksiOpname(d, perms) {
  const out = { setujui: null, tolak: null };
  if (!d || d.status !== MENUNGGU || !can(perms, "cash", "approve")) return out;
  const sibuk = d.dalam_proses ? PESAN_SEDANG_DIPROSES : "";
  const ditolak = d.kontrol?.ditolak ? (d.kontrol.pesan || "Selisih opname ini harus diputuskan orang lain.") : "";
  out.setujui = { label: d.terbit_error ? "Setujui lagi" : "Setujui", alasan: sibuk || ditolak };
  out.tolak = { label: "Tolak", alasan: sibuk };
  return out;
}

/** Rekening tunai (opname hanya untuk `account_type="cash"`; rekening bank → Rekonsiliasi Bank). */
export const rekeningTunai = (list) => (Array.isArray(list) ? list : []).filter((a) => a?.account_type === "cash");

/** Label jenis kas rekening (server: `cash_type_label`). */
export const JENIS_KAS = { kas_kasir: "Kas kasir", kas_kecil: "Kas Kecil", kas_besar: "Kas besar" };
export const jenisKas = (a) => a?.cash_type_label || JENIS_KAS[a?.cash_type] || "";

/** Label rekening tunai untuk pilihan: nama · jenis kas (+ PT bila lintas PT) — TANPA saldo (hitung buta). */
export function labelRekeningTunai(a, ptLabel = "") {
  if (!a) return "";
  return [a.name, jenisKas(a), ptLabel].filter(Boolean).join(" · ");
}
