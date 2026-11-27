/**
 * cutoverShared — Kas & Bank bagian 1 (Tugas 6): aturan layar Akun per rekening (alat pindah saldo, spesifikasi §5.3).
 *
 * Server: `backend/services/cash_account_cutover_service.py` (rute `/api/kas-per-rekening/...`, semua `accounting.manage`).
 * Kalimat 409 yang dikenali layar disalin persis dari server: sidik angka berbeda ("Angka berubah, muat ulang.") dan
 * selisih yang belum dicentang (R10: "… centang 'sudah diperiksa' untuk melanjutkan.").
 */
export const PESAN_ANGKA_BERUBAH = "Angka berubah, muat ulang.";
export const ALASAN_MIN = 5;
export const NAMA_JENIS_KAS = { kas_besar: "Kas besar / bank", kas_kecil: "Kas kecil" };
export const jenisKas = (ct) => NAMA_JENIS_KAS[ct] || "—";

export const STATUS_USULAN = {
  menunggu: { label: "Menunggu persetujuan", tone: "warning", icon: "clock" },
  memproses: { label: "Sedang diproses", tone: "info", icon: "dot" },
  disetujui: { label: "Disetujui", tone: "success", icon: "check" },
  ditolak: { label: "Ditolak", tone: "danger", icon: "x" },
};
export const statusUsulan = (s) => STATUS_USULAN[s] || { label: s || "—", tone: "neutral", icon: "circle" };

/** Galat server berbunyi "angka berubah" (sidik yang dilihat penyetuju ≠ hitungan server). */
export const angkaBerubah = (teks) => String(teks || "").trim() === PESAN_ANGKA_BERUBAH;
/** Galat server berbunyi "selisih belum dicentang" (R10). */
export const selisihBelumDicentang = (teks) => /centang 'sudah diperiksa'/.test(String(teks || ""));

/** Rekening pratinjau yang berselisih (|selisih| ≥ 1 sen, aturan yang sama dengan server `rekening_berselisih`). */
export const rekeningBerselisih = (pv) => (pv?.rekening || []).filter((r) => Math.abs(Number(r.selisih) || 0) >= 0.005);

/**
 * Alasan tombol "Siapkan pindah saldo" nonaktif (kalimat tertulis, bukan tooltip); "" = boleh.
 * Urutan = urutan penolakan server `siapkan`: PT aktif → usulan hidup → posting gagal/tertunda.
 */
export function alasanTidakBisaSiapkan(pv, { canManage }) {
  if (!canManage) return "Menyiapkan pindah saldo butuh akses Akuntansi tingkat kelola.";
  if (!pv) return "Pratinjau belum dimuat.";
  if (pv.aktif) return "PT ini sudah memakai akun per rekening — pindah saldo hanya sekali per PT.";
  if (pv.usulan) return "Usulan pindah saldo PT ini masih menunggu persetujuan. Setujui atau tolak dulu.";
  if (Number(pv.posting_gagal) > 0) {
    return `Selesaikan dulu ${pv.posting_gagal} posting kas yang gagal atau tertunda — rincian dan tempat menyelesaikannya di bawah.`;
  }
  if (!(pv.rekening || []).length) return "PT ini belum punya rekening.";
  return "";
}

/**
 * Tinjauan akhir Minor 1 — tempat menyelesaikan tiap jenis posting tertunda (`posting_gagal_rincian[].tempat` dari server
 * `TEMPAT_TERTUNDA`): view yang dibuka tombolnya. Hanya jenis registri yang tampil di Posting Gagal; jurnal induk yang
 * gagal juga tampil di sana; gaji jalur lama dibayar di Proses Gaji; yang sedang berjalan cukup dimuat ulang.
 */
export const TOMBOL_TERTUNDA = {
  posting_gagal: { view: "posting-failures", label: "Buka Posting Gagal" },
  dokumen_induk: { view: "posting-failures", label: "Buka Posting Gagal" },
  proses_gaji: { view: "hr-payroll-runs", label: "Buka Proses Gaji" },
};

/** Tombol unik (per view) untuk rincian posting tertunda yang bisa diselesaikan di layar lain. */
export function tombolTertunda(rincian) {
  const out = [];
  for (const x of rincian || []) {
    const t = TOMBOL_TERTUNDA[x.tempat];
    if (t && !out.some((o) => o.view === t.view)) out.push(t);
  }
  return out;
}

/** Nilai pilihan "Sub-akun baru (dibuat sistem)" di Siapkan untuk rekening yang akunnya sekarang akun pilihan Finance;
 *  dikirim ke server sebagai "" (tinjauan akhir I2). */
export const PILIH_SUBAKUN_BARU = "__subakun_baru__";

/**
 * Akun bagan PT yang boleh dipilih untuk rekening `rek` (saringan layar; server memeriksa ulang `periksa_akun_pilihan`):
 * akun khusus PT itu, aktif, bisa diposting, aset, bukan akun kas bawaan, belum dipakai rekening lain.
 */
export function akunPilihan(accounts, rek, entityId) {
  return (accounts || []).filter((a) => a && a.entity_id === entityId && a.is_active !== false && a.is_postable !== false
    && (a.type || "") === "asset" && !["1-1100", "1-1110"].includes(a.code)
    && (!a.bank_account_id || a.bank_account_id === rek.id));
}
