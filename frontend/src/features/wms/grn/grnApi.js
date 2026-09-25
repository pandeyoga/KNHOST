import axios, { API } from "../../../services/apiClient";

export const GRN = `${API}/goods-receipts`;

export const STATUS = {
  draft: { label: "Draf", cls: "bg-[#F2F2F7] text-[#3C3C43]" },
  reading: { label: "Membaca SJ", cls: "bg-[#EEF4FF] text-[#0058CC]" },
  review: { label: "Tinjau SJ", cls: "bg-[#FFF6E5] text-[#B26A00]" },
  counting: { label: "Hitung fisik", cls: "bg-[#EEF4FF] text-[#0058CC]" },
  reconcile: { label: "Rekonsiliasi", cls: "bg-[#FFF6E5] text-[#B26A00]" },
  closing: { label: "Memposting", cls: "bg-[#EEF4FF] text-[#0058CC]" },
  closed: { label: "Ditutup", cls: "bg-[#E7F6F3] text-[#0F766E]" },
  rejected: { label: "Ditolak", cls: "bg-[#FDECEC] text-[#B4231F]" },
  cancelled: { label: "Dibatalkan", cls: "bg-[#F2F2F7] text-[#6B6B73]" },
};

export const STEPS = ["draft", "review", "counting", "reconcile", "closed"];

export const KIND_LABEL = {
  match: "Cocok", short_vs_dn: "Kurang dari SJ", over_vs_dn: "Lebih dari SJ", rolls_mismatch: "Jumlah roll beda",
  weight_mismatch: "Berat beda", over_remaining: "Melebihi sisa PO", not_arrived: "Tidak datang",
  not_on_dn: "Tidak ada di SJ", non_stock: "Non-stok", rejected: "Ditolak",
};

export const ACTION_LABEL = {
  accept_note: "Terima dengan catatan", claim_supplier: "Klaim ke supplier", claim_makloon: "Klaim ke makloon",
  reject_goods: "Tolak barang",
};

export function allowedActions(kind, partnerType) {
  const claim = partnerType === "supplier" ? "claim_supplier" : "claim_makloon";
  if (["short_vs_dn", "rolls_mismatch", "not_arrived"].includes(kind)) return ["accept_note", claim];
  if (["over_remaining", "not_on_dn"].includes(kind)) return ["accept_note", "reject_goods"];
  return [];
}

export function errText(e, fallback = "Aksi gagal.") {
  const d = e?.response?.data?.detail;
  if (d && typeof d === "object") return d.message || (d.errors || []).join(" ") || fallback;
  if (Array.isArray(d)) return d.map((x) => x.msg).join("; ");
  return d || fallback;
}

export const grnApi = {
  list: (params) => axios.get(GRN, { params }).then((r) => r.data),
  get: (id) => axios.get(`${GRN}/${id}`).then((r) => r.data),
  targets: (id) => axios.get(`${GRN}/${id}/targets`).then((r) => r.data),
  rolls: (id) => axios.get(`${GRN}/${id}/rolls`).then((r) => r.data),
  partners: (partner_type) => axios.get(`${GRN}/partners`, { params: { partner_type } }).then((r) => r.data),
  variance: (since) => axios.get(`${GRN}/supplier-variance`, { params: { since } }).then((r) => r.data),
  profiles: () => axios.get(`${GRN}/dn-profiles`).then((r) => r.data),
  patchProfile: (partnerId, body) => axios.patch(`${GRN}/dn-profiles/${partnerId}`, body).then((r) => r.data),
  usage: (month) => axios.get(`${GRN}/usage`, { params: { month } }).then((r) => r.data),
  create: (body) => axios.post(GRN, body).then((r) => r.data),
  upload: (id, file, v) => {
    const fd = new FormData();
    fd.append("file", file);
    if (v) fd.append("expected_version", v);
    return axios.post(`${GRN}/${id}/files`, fd).then((r) => r.data);
  },
  fileBlob: (id, page) => axios.get(`${GRN}/${id}/files/${page}`, { responseType: "blob" }).then((r) => r.data),
  deleteFile: (id, page, v) => axios.delete(`${GRN}/${id}/files/${page}`, { params: { expected_version: v } }).then((r) => r.data),
  post: (id, path, body) => axios.post(`${GRN}/${id}/${path}`, body).then((r) => r.data),
  patch: (id, path, body) => axios.patch(`${GRN}/${id}/${path}`, body).then((r) => r.data),
  del: (id, path, params) => axios.delete(`${GRN}/${id}/${path}`, { params }).then((r) => r.data),
};

/** Kecilkan foto di klien: sisi panjang ≤ 2048 px, JPEG 0,85. PDF dikirim apa adanya. */
export async function shrinkImage(file, maxSide = 2048) {
  if (!file.type.startsWith("image/")) return { file, width: 0, height: 0 };
  const bmp = await createImageBitmap(file).catch(() => null);
  if (!bmp) return { file, width: 0, height: 0 };
  const scale = Math.min(1, maxSide / Math.max(bmp.width, bmp.height));
  const w = Math.round(bmp.width * scale), h = Math.round(bmp.height * scale);
  const canvas = document.createElement("canvas");
  canvas.width = w; canvas.height = h;
  canvas.getContext("2d").drawImage(bmp, 0, 0, w, h);
  const blob = await new Promise((res) => canvas.toBlob(res, "image/jpeg", 0.85));
  const name = file.name.replace(/\.[^.]+$/, "") + ".jpg";
  return { file: new File([blob], name, { type: "image/jpeg" }), width: w, height: h };
}

export const MIN_SHORT_SIDE = 1000;
