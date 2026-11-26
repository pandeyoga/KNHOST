/**
 * Lapor Bayar CBD & DP (LB-T7) — pemanggil API laporan bayar per pesanan.
 * Semua tulis lewat `moneyPost` (kunci idempotensi dari `useIntentKey` milik layar): kirim ulang sesudah jaringan putus
 * diputar ulang server, bukan membuat laporan/kwitansi kedua. Rute: `backend/routers/payment_reports.py`.
 */
import axios, { API } from "../../../services/apiClient";
import { moneyPost } from "../../../utils/moneyRequest";

export const BUKTI_MAKS_BYTE = 10 * 1024 * 1024;
export const BUKTI_TIPE = ["image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"];
export const ALASAN_MIN = 5;

/** `{items, bisa_lapor, bisa_putuskan}` — kedua bendera = izin pemanggil, bukan keadaan pesanan. */
export const listReports = (orderId) =>
  axios.get(`${API}/sales-orders/${orderId}/payment-reports`).then((r) => r.data);

export const createReport = (orderId, body, key) =>
  moneyPost(`${API}/sales-orders/${orderId}/payment-reports`, body, key).then((r) => r.data);

/** Unggah bukti (multipart: JPG/PNG/WEBP/GIF/PDF ≤ 10 MB). */
export const uploadProof = (reportId, file, key) => {
  const fd = new FormData();
  fd.append("file", file);
  return moneyPost(`${API}/payment-reports/${reportId}/attachments`, fd, key).then((r) => r.data);
};

/** → `{report, receipt_number, released, waiting_bank}`. */
export const terima = (reportId, key) =>
  moneyPost(`${API}/payment-reports/${reportId}/terima`, null, key).then((r) => r.data);

export const tolak = (reportId, reason, key) =>
  moneyPost(`${API}/payment-reports/${reportId}/tolak`, { reason }, key).then((r) => r.data);

export const attachmentUrl = (reportId, attId) => `${API}/payment-reports/${reportId}/attachments/${attId}`;

/** Pesan bila berkas bukti tidak memenuhi syarat server ("" bila sah). */
export function proofProblem(file) {
  if (!file) return "Lampirkan bukti bayar dulu";
  if (file.size > BUKTI_MAKS_BYTE) return "Bukti terlalu besar (maksimal 10 MB).";
  if (file.type && !BUKTI_TIPE.includes(file.type)) return "Bukti harus berupa foto (JPG, PNG, WEBP, GIF) atau PDF.";
  return "";
}
