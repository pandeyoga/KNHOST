/**
 * approvalDecisions — SATU dialog keputusan untuk Pesanan Khusus (PO Custom) & harga khusus (fase 3 · P1, D-07/D-27).
 *
 * KENAPA ADA: keputusan yang sama diputus di empat tempat dengan dialog berbeda — SpecialOrderDetail (askConfirm
 * tanpa catatan), aplikasi HP Persetujuan (askReason, catatan opsional, catatan bawaan "Disetujui dari HP"),
 * Persetujuan Saya (matriks) dan papan beranda. Keputusan pemilik D-07: keputusan hanya di layar Pesanan Khusus
 * (desktop) dan HP Persetujuan, dengan dialog yang IDENTIK. Modul ini hanya dialog + panggilan endpoint yang
 * sudah ada — aturan (pemisahan tugas, tingkat persetujuan, K-11) tetap di server.
 *
 * Kontrak (pola confirmService — tipe berbeda supaya tidak tertukar):
 *   const res = await approveSpecialOrder(order, { defaultNote: "Disetujui dari HP" });
 *   if (res === null) return;            // pengguna membatalkan dialog
 *   setOk(res.message); onUpdate(res.data);
 *   // galat server DILEMPAR (axios error) → pemanggil menampilkan `decisionErrorText(e)` di layarnya.
 *
 *   approveSpecialOrder(order, opts) · rejectSpecialOrder(order, opts) · approvePrice(req, opts) · rejectPrice(req, opts)
 *   opts: `defaultNote` (catatan bila kosong; HP: "Disetujui dari HP") · `testId` (dialog) · `api` (klien axios
 *         pengganti, untuk uji).
 * Setujui: catatan OPSIONAL. Tolak: alasan WAJIB, minimal `REASON_MIN_LENGTH` (5) huruf — keputusan K-14.
 * `message`: kalimat hasil berantai (mis. "Pesanan disetujui. Diteruskan otomatis: DSR-0012, SMP-0031.").
 */
import axios, { API } from "./apiClient";
import { askReason, REASON_MIN_LENGTH } from "./confirmService";
import { apiErrorText } from "../utils/apiError";
import { formatCurrency } from "../utils/formatters";

const join = (...xs) => xs.filter(Boolean).join(" · ");

function orderMessage(o) {
  const amount = Number(o?.total_amount) > 0 ? formatCurrency(o.total_amount) : "";
  return join(o?.custom_item?.description, amount);
}

function priceMessage(p) {
  const unit = p?.unit || "satuan";
  const normal = p?.normal_price !== undefined && p?.normal_price !== null
    ? `(pembanding ${formatCurrency(p.normal_price)}/${unit})` : "";
  return join(p?.product_name, `${formatCurrency(p?.requested_price)}/${unit} ${normal}`.trim());
}

/** Kalimat hasil setuju PO Custom — berantai ke dokumen yang lahir otomatis (DSR/sample). */
export function specialOrderApprovedText(data) {
  if (data?.status === "pending_approval") return "Disetujui di tingkat Anda — menunggu tingkat persetujuan berikutnya.";
  const ch = data?.chain || {};
  const made = [ch.design_request?.number, ...(ch.samples || []).map((s) => s.number)].filter(Boolean);
  return `Pesanan disetujui.${made.length ? ` Diteruskan otomatis: ${made.join(", ")}.` : ""}`;
}

/** Teks galat keputusan untuk ditampilkan pemanggil (403/409 server tetap terbaca manusia). */
export function decisionErrorText(e, fallback = "Keputusan gagal disimpan.") {
  return apiErrorText(e, fallback);
}

async function askApprove({ title, message, testId }) {
  return askReason({
    title, message, confirmLabel: "Setujui",
    reasonLabel: "Catatan (opsional)", reasonRequired: false, reasonPlaceholder: "Boleh dikosongkan",
    testId,
  });
}

async function askReject({ title, message, testId }) {
  return askReason({
    title, message, confirmLabel: "Tolak", danger: true,
    reasonLabel: "Alasan penolakan", reasonRequired: true, reasonMinLength: REASON_MIN_LENGTH,
    testId,
  });
}

const orderTitle = (verb, o) => `${verb} ${o?.number || "pesanan khusus"}${o?.customer_name ? ` · ${o.customer_name}` : ""}`;
const priceTitle = (verb, p) => `${verb} harga khusus${p?.customer_name ? ` · ${p.customer_name}` : ""}`;

/** Setujui Pesanan Khusus (PO Custom). → `{ data, message }` | null (batal). */
export async function approveSpecialOrder(order, { defaultNote = "", testId = "sord-approve-dialog", api = axios } = {}) {
  const note = await askApprove({ title: orderTitle("Setujui", order), message: orderMessage(order), testId });
  if (note === null) return null;
  const res = await api.post(`${API}/special-orders/${order.id}/approve`, { notes: note.trim() || defaultNote });
  return { data: res.data, message: specialOrderApprovedText(res.data) };
}

/** Tolak Pesanan Khusus. → `{ data, message }` | null (batal). */
export async function rejectSpecialOrder(order, { testId = "sord-reject-dialog", api = axios } = {}) {
  const reason = await askReject({ title: orderTitle("Tolak", order), message: orderMessage(order), testId });
  if (reason === null) return null;
  const res = await api.post(`${API}/special-orders/${order.id}/reject`, { reason: reason.trim() });
  return { data: res.data, message: `${order?.number || "Pesanan khusus"} ditolak.` };
}

/** Setujui permintaan harga khusus. → `{ data, message }` | null (batal). */
export async function approvePrice(req, { defaultNote = "", testId = "price-approve-dialog", api = axios } = {}) {
  const note = await askApprove({ title: priceTitle("Setujui", req), message: priceMessage(req), testId });
  if (note === null) return null;
  const res = await api.post(`${API}/price-approvals/${req.id}/approve`, { decision_notes: note.trim() || defaultNote });
  return { data: res.data, message: "Harga khusus disetujui." };
}

/** Tolak permintaan harga khusus. → `{ data, message }` | null (batal). */
export async function rejectPrice(req, { testId = "price-reject-dialog", api = axios } = {}) {
  const reason = await askReject({ title: priceTitle("Tolak", req), message: priceMessage(req), testId });
  if (reason === null) return null;
  const res = await api.post(`${API}/price-approvals/${req.id}/reject`, { decision_notes: reason.trim() });
  return { data: res.data, message: "Harga khusus ditolak." };
}
