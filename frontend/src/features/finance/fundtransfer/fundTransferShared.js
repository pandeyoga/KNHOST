/**
 * fundTransferShared — Kas & Bank bagian 1 (Tugas 6): kosakata & aturan layar Pindah Dana (tanpa React).
 *
 * Satu sumber untuk daftar (`FundTransfersView`), form (`FundTransferForm`), dan pratinjau dokumen
 * (`features/documents/preview/bodies/FundTransferPreview`). Aturan aksi mengikuti server
 * (`backend/services/fund_transfer_service.py`): Setujui hanya untuk `menunggu_persetujuan`, Terima hanya untuk
 * `dalam_perjalanan`, Batal untuk dokumen hidup dan untuk pembatalan yang belum tuntas. Izin, bukan nama peran:
 * buat/terima `cash.create`, batal `cash.delete`, setujui `cash.approve`. Server tetap penentu (galat tampil di tempat).
 */
import { can } from "../../../config/roles";

export const STATUS_PINDAH_DANA = {
  menunggu_persetujuan: { label: "Menunggu persetujuan", tone: "warning", icon: "clock" },
  dalam_perjalanan: { label: "Dalam perjalanan", tone: "info", icon: "truck" },
  selesai: { label: "Selesai", tone: "success", icon: "check" },
  batal: { label: "Batal", tone: "neutral", icon: "ban" },
};
export const statusPindahDana = (s) => STATUS_PINDAH_DANA[s] || { label: s || "—", tone: "neutral", icon: "circle" };

/** Pilihan saringan status (dropdown, pola UI §1.2). */
export const PILIHAN_STATUS = [
  { value: "", label: "Semua status" },
  ...Object.entries(STATUS_PINDAH_DANA).map(([value, s]) => ({ value, label: s.label })),
];

export const ALASAN_MIN = 5;   // sama dengan server (K-14: alasan minimum 5 huruf)

/** Kalimat petunjuk kas manual → Pindah Dana (server `cash_ledger.PESAN_KATEGORI_TRANSFER_DITUTUP`). */
export const TEKS_PAKAI_PINDAH_DANA = "Pakai Pindah Dana untuk setor tunai, isi kas kecil, dan pindah antar rekening.";

export const JEJAK_LABEL = {
  buat: "Dibuat", setujui: "Disetujui", terbit: "Kas terbit", terima: "Diterima rekening tujuan", batal: "Dibatalkan",
  batal_diteruskan: "Pembatalan diteruskan",
};

/** Validasi isian sebelum dikirim (server menolak hal yang sama; negatif = 422 skema, jadi dicegah di sini). */
export function validasiPindahDana(f) {
  if (!f.rekening_asal_id || !f.rekening_tujuan_id) return "Pilih rekening asal dan rekening tujuan.";
  if (f.rekening_asal_id === f.rekening_tujuan_id) return "Rekening asal dan tujuan tidak boleh sama.";
  const nominal = Number(f.nominal);
  if (!Number.isFinite(nominal) || nominal <= 0) return "Nominal pindah dana harus lebih dari 0.";
  const biaya = f.biaya === "" || f.biaya === null || f.biaya === undefined ? 0 : Number(f.biaya);
  if (!Number.isFinite(biaya) || biaya < 0) return "Biaya transfer tidak boleh negatif.";
  if (f.tanggal_terima && f.tanggal_kirim && f.tanggal_terima < f.tanggal_kirim) {
    return "Tanggal terima tidak boleh sebelum tanggal kirim.";
  }
  return "";
}

/** Badan permintaan `POST /api/fund-transfers` dari isian form. */
export function badanPindahDana(f, entityId) {
  return {
    entity_id: entityId || "", rekening_asal_id: f.rekening_asal_id, rekening_tujuan_id: f.rekening_tujuan_id,
    nominal: Number(f.nominal), biaya: f.biaya === "" || f.biaya == null ? 0 : Number(f.biaya),
    tanggal_kirim: f.tanggal_kirim || "", tanggal_terima: f.tanggal_terima || "", catatan: (f.catatan || "").trim(),
  };
}

/**
 * Aksi baris untuk dokumen `d` dan izin `perms` → { setujui, terima, batal, catatan }.
 * Tiap aksi: null (tidak ditawarkan) atau { label, alasan } (alasan terisi = tombol nonaktif dengan alasan tertulis).
 */
export function aksiPindahDana(d, perms) {
  const out = { setujui: null, terima: null, batal: null, catatan: "" };
  if (!d) return out;
  const sibuk = d.dalam_proses ? "Sedang diproses — muat ulang sebentar lagi." : "";
  if (d.status === "menunggu_persetujuan") {
    if (can(perms, "cash", "approve")) {
      const ditolak = d.kontrol?.ditolak ? (d.kontrol.pesan || "Rekan lain yang berwenang yang menyetujui.") : "";
      out.setujui = { label: d.terbit_error ? "Setujui lagi" : "Setujui", alasan: sibuk || ditolak };
    }
    if (can(perms, "cash", "delete")) out.batal = { label: "Batal", alasan: sibuk };
  } else if (d.status === "dalam_perjalanan") {
    if (can(perms, "cash", "create")) out.terima = { label: "Terima", alasan: sibuk };
    if (can(perms, "cash", "delete")) out.batal = { label: "Batal", alasan: sibuk };
  } else if (d.status === "selesai") {
    if (can(perms, "cash", "delete")) out.batal = { label: "Batal", alasan: sibuk };
  } else if (d.status === "batal" && d.batal_tertunda) {
    out.catatan = "Pembatalan belum tuntas.";
    if (can(perms, "cash", "delete")) out.batal = { label: "Teruskan pembatalan", alasan: sibuk };
  }
  if (sibuk && !out.catatan) out.catatan = sibuk;
  return out;
}

/** Label rekening untuk pilihan form: nama · bank/nomor atau "Kas tunai" (tanpa id teknis). */
export function labelRekening(a) {
  if (!a) return "";
  const rinci = a.account_type === "bank" ? [a.bank_name, a.account_number].filter(Boolean).join(" ") : "Kas tunai";
  return [a.name, rinci].filter(Boolean).join(" · ");
}
