/**
 * cashOutShared — Kas & Bank bagian 2 (Tugas 4): kosakata & aturan layar pengajuan kas keluar manual (tanpa React).
 *
 * Satu sumber untuk form Catat Transaksi (`CashManagementView`), bagian "Menunggu persetujuan"
 * (`CashOutPendingSection`) dan pratinjau dokumen (`documents/preview/bodies/CashOutRequestPreview`). Aturan mengikuti
 * server (`backend/services/cash_out_request_service.py`, `routers/cash_out_requests.py`): Setujui/Tolak hanya untuk
 * `menunggu_persetujuan` dan pemegang `cash.approve`; Batal oleh pengaju (`cash.create`) atau pemegang `cash.delete`.
 * Izin, bukan nama peran. Server tetap penentu (galat tampil di tempat aksi).
 */
import { can } from "../../../config/roles";
import { formatCurrency } from "../../../utils/formatters";

export const MENUNGGU = "menunggu_persetujuan";

export const STATUS_PENGAJUAN = {
  menunggu_persetujuan: { label: "Menunggu persetujuan", tone: "warning", icon: "clock" },
  disetujui: { label: "Disetujui", tone: "success", icon: "check" },
  ditolak: { label: "Ditolak", tone: "danger", icon: "x" },
  dibatalkan: { label: "Dibatalkan", tone: "neutral", icon: "ban" },
};
export const statusPengajuan = (s) => STATUS_PENGAJUAN[s] || { label: s || "—", tone: "neutral", icon: "circle" };

export const JEJAK_LABEL = { ajukan: "Diajukan", setujui: "Disetujui", tolak: "Ditolak", batal: "Dibatalkan" };

export const ALASAN_MIN = 5;   // sama dengan server (K-14: alasan minimum 5 huruf)

export const TEKS_BANTU = "Kas keluar manual di atas batas PT tidak langsung tercatat: ia menjadi pengajuan yang baru "
  + "menjadi kas dan jurnal sesudah orang kedua yang berizin menyetujuinya. Pengajuan yang menunggu belum mengurangi saldo "
  + "kas. Pengaju bisa membatalkan selama menunggu. Batas diatur per PT di Pengaturan › Persetujuan › Kontrol dua orang.";

/**
 * Batas PT dari `GET /api/cash-out-requests/batas` → `{min_orang, batas_nominal}` yang bisa dipakai, atau null bila
 * jawabannya tidak berbentuk batas (rute gagal / belum dimuat — server tetap penentu: jawaban 202 tetap ditangani).
 */
export function bacaBatas(data) {
  if (!data || typeof data !== "object" || Array.isArray(data)) return null;
  const min = String(data.min_orang ?? "").trim();
  const batas = Number(data.batas_nominal);
  if (!min && !Number.isFinite(batas)) return null;
  return { min_orang: min || "1", batas_nominal: Number.isFinite(batas) ? batas : 0 };
}

/**
 * Apakah isian form akan menjadi PENGAJUAN (aturan yang sama dengan `dual_control.butuh_orang_kedua`): hanya kas keluar;
 * `min_orang` "2" = semua; selain itu nominal > batas (batas 0 = tidak dipakai). → `{ butuh, catatan }`.
 */
export function butuhPersetujuan(batas, { direction, amount } = {}) {
  const kosong = { butuh: false, catatan: "" };
  if (!batas || direction !== "out") return kosong;
  if (batas.min_orang === "2") {
    return { butuh: true, catatan: "Semua kas keluar manual PT ini diajukan untuk disetujui orang kedua." };
  }
  const n = Number(amount);
  if (batas.batas_nominal > 0 && Number.isFinite(n) && n > batas.batas_nominal) {
    return { butuh: true, catatan: `Di atas ${formatCurrency(batas.batas_nominal)} — akan diajukan untuk disetujui orang kedua.` };
  }
  return kosong;
}

/** Apakah `user` = pengaju (penilaian server `kontrol.sendiri` bila ada; selain itu id pengaju). */
export function pengajuSendiri(d, user) {
  if (typeof d?.kontrol?.sendiri === "boolean") return d.kontrol.sendiri;
  const uid = user?.id || "";
  return Boolean(uid && d?.pengaju?.id === uid);
}

/**
 * Aksi baris untuk pengajuan `d`, izin `perms`, dan pengguna `user` → { setujui, tolak, batal }.
 * Tiap aksi: null (tidak ditawarkan) atau { label, alasan } (alasan terisi = tombol nonaktif dengan alasan tertulis —
 * kalimat dari server: `kontrol.pesan` untuk Setujui, `kontrol.tolak_pesan` untuk Tolak).
 */
export function aksiPengajuan(d, perms, user) {
  const out = { setujui: null, tolak: null, batal: null };
  if (!d || d.status !== MENUNGGU) return out;
  const sibuk = d.dalam_proses ? "Sedang diproses — muat ulang sebentar lagi." : "";
  const sendiri = pengajuSendiri(d, user);
  if (can(perms, "cash", "approve")) {
    const ditolak = d.kontrol?.ditolak ? (d.kontrol.pesan || "Kas keluar ini harus disetujui orang lain.") : "";
    out.setujui = { label: d.terbit_error ? "Setujui lagi" : "Setujui", alasan: sibuk || ditolak };
    const tolakSendiri = sendiri ? (d.kontrol?.tolak_pesan || "Pengajuan ini Anda ajukan sendiri. Pakai Batal bila tidak jadi.") : "";
    out.tolak = { label: "Tolak", alasan: sibuk || tolakSendiri };
  }
  if ((sendiri && can(perms, "cash", "create")) || can(perms, "cash", "delete")) out.batal = { label: "Batal", alasan: sibuk };
  return out;
}
