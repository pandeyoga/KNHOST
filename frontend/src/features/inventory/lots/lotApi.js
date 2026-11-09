/**
 * lotApi (FASE C · D-10/D-26/D-27) — satu pintu panggilan API lot & helper tampilan.
 * Komponen layar TIDAK memanggil axios langsung agar jalur data tunggal & mudah diaudit.
 */
import axios, { API } from "../../../services/apiClient";
import { formatDate, formatDateTime } from "../../../utils/formatters";
import { permissionDeniedText } from "../../../utils/apiError";

export const lotApi = {
  list: (params) => axios.get(`${API}/lots`, { params }).then((r) => r.data),
  stats: (params) => axios.get(`${API}/lots/stats`, { params }).then((r) => r.data),
  settings: () => axios.get(`${API}/lots/settings`).then((r) => r.data),
  // FASE G-0: `saveSettings` DIHAPUS — kebijakan lot hanya bisa diubah lewat
  // Pusat Pengaturan (PUT /api/config/values). Endpoint backend tetap ada untuk
  // kompatibilitas mesin/skrip lama, tetapi UI tidak lagi punya jalur tulis kedua.
  detail: (id) => axios.get(`${API}/lots/${id}`).then((r) => r.data),
  genealogy: (id) => axios.get(`${API}/lots/${id}/genealogy`).then((r) => r.data),
  recall: (id) => axios.get(`${API}/lots/${id}/recall`).then((r) => r.data),
  label: (id, body) => axios.post(`${API}/lots/${id}/label`, body).then((r) => r.data),
  create: (body) => axios.post(`${API}/lots`, body).then((r) => r.data),
  patch: (id, body) => axios.patch(`${API}/lots/${id}`, body).then((r) => r.data),
  setStatus: (id, body) => axios.post(`${API}/lots/${id}/status`, body).then((r) => r.data),
  split: (id, body) => axios.post(`${API}/lots/${id}/split`, body).then((r) => r.data),
  merge: (body) => axios.post(`${API}/lots/merge`, body).then((r) => r.data),
  rework: (id, body) => axios.post(`${API}/lots/${id}/rework`, body).then((r) => r.data),
  attachRolls: (id, body) => axios.post(`${API}/lots/${id}/rolls`, body).then((r) => r.data),
  identityTrace: (code) => axios.get(`${API}/lots/identity-trace`, { params: { code } }).then((r) => r.data),
  unassignedRolls: (params) => axios.get(`${API}/lots/unassigned-rolls`, { params }).then((r) => r.data),
};

/** Nada warna status lot (informasional — tidak memblokir penjualan). */
export const LOT_STATUS_TONE = {
  released: "pill-success",
  karantina: "pill-warning",
  in_process: "pill-info",
  hold_shade: "pill-warning",
  rework: "pill-danger",
};

export const SOURCE_TONE = {
  receiving: "pill-info",
  makloon: "pill-info",
  production: "pill-info",
  split: "pill-warning",
  merge: "pill-warning",
  rework: "pill-danger",
  migration: "pill-muted",
  manual: "pill-muted",
  return: "pill-warning",
  transfer: "pill-muted",
  adjustment: "pill-muted",
};

// UAT 24 Okt (audit UI tahap 2) — "Permission ditolak: …" (kode izin) → kalimat akses (G0-03).
export const errText = (e, fallback) => {
  const d = e?.response?.data?.detail;
  return (typeof d === "string" && permissionDeniedText(d)) || d || e?.message || fallback || "Terjadi kesalahan.";
};

// FIX-8 (B3b INP-15 · G-OUT-01) — tanggal/waktu lot lewat formatter tunggal WIB (dulu zona perangkat; jam tanpa "WIB").
export const shortDate = (iso) => formatDate(iso);
export const shortDateTime = (iso) => formatDateTime(iso);
