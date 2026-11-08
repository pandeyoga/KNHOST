// PREP-A (K-OPN-06) — API lembar perbaikan master produk (unduh → unggah/pratinjau → terapkan → batalkan).
import axios, { API } from "../../services/apiClient";

const BASE = `${API}/master-governance/cleanup`;

/** Galat dari respons `blob` (unduhan) tetap dibaca jadi kalimat — bukan "[object Blob]". */
export async function blobErrorText(e, fallback) {
  const data = e?.response?.data;
  if (data && typeof data.text === "function") {
    try {
      const j = JSON.parse(await data.text());
      if (typeof j.detail === "string") return j.detail;
      if (j.detail?.message) return j.detail.message;
    } catch { /* bukan JSON */ }
  }
  return e?.response?.data?.detail || e?.message || fallback;
}

export const masterCleanupApi = {
  sheet: (format = "xlsx") => axios.get(`${BASE}/sheet`, { params: { format }, responseType: "blob" }),
  preview: (file) => { const fd = new FormData(); fd.append("file", file); return axios.post(`${BASE}/preview`, fd).then((r) => r.data); },
  apply: (body) => axios.post(`${BASE}/apply`, body).then((r) => r.data),
  batches: () => axios.get(`${BASE}/batches`).then((r) => (Array.isArray(r.data) ? r.data : [])),
  rollback: (id, reason) => axios.post(`${BASE}/batches/${id}/rollback`, { reason }).then((r) => r.data),
};

export const ACTION_LABEL = {
  GANTI_NAMA: "Ganti nama", GANTI_KODE: "Ganti kode", GABUNG_KE: "Gabung ke", NONAKTIFKAN: "Nonaktifkan", PERTAHANKAN: "Pertahankan",
};
export const BATCH_STATUS = {
  planned: "Direncanakan", applied: "Diterapkan", applied_partial: "Diterapkan sebagian", failed: "Gagal",
  rolling_back: "Membatalkan", rolled_back: "Dibatalkan",
};
export const ROLLBACKABLE = ["applied", "applied_partial", "failed"];

/** Picu unduhan berkas dari Blob (nama dari Content-Disposition bila ada). */
export function saveBlob(res, fallbackName) {
  const cd = res?.headers?.["content-disposition"] || "";
  const name = (cd.match(/filename=([^;]+)/) || [])[1]?.trim() || fallbackName;
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url; a.download = name; a.style.display = "none";
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return name;
}
