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

/** Status pesanan "sebelum gudang" — sama dengan `pay_hold_service.STATUS_SEBELUM_GUDANG` (server tetap penentu). */
export const STATUS_SEBELUM_GUDANG = ["reserved", "waiting_approval", "waiting_stock", "approved"];

/**
 * SATU predikat klien "pesanan wajib bayar dulu dan belum dilepas ke gudang" — cermin `pay_hold_service.wajib_bayar_sebelum_gudang`
 * (pagar B3 server): status `STATUS_SEBELUM_GUDANG` + tanpa pengecualian berizin (`dispatch_payment_release`) + gerbang bayar
 * (`dispatch_payment_gate.evaluate`) berlaku (`applies`; sample dan pesanan khusus dikecualikan server dari gerbang).
 * `gate` = jawaban `GET /sales-orders/{id}/dispatch-payment-gate` (`applies`, `released`) — sumber hitungan tunggal.
 * CELAH: tanpa `gate` (belum dimuat / gagal) klien hanya punya penanda `pay_hold` / `release.waiting === "bayar"` (yang
 * dipakai `pay_hold_service.ditahan`) — pesanan sebelum penanda ada bisa luput; server tetap penentu (409).
 */
export function isHeldForPayment(order, gate = null) {
  if (!order || !STATUS_SEBELUM_GUDANG.includes(order.status)) return false;
  if (order.dispatch_payment_release || order.order_type === "sample") return false;
  if (gate && typeof gate.applies === "boolean") return gate.applies && !gate.released;
  return order.pay_hold != null || order.release?.waiting === "bayar";
}
