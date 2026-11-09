/**
 * PREP-B — pendaftaran awal gedung (opname awal RFID, KEPUTUSAN_GATE_RFID §8): helper bersama layar desktop & HP.
 * Server = sumber kebenaran (validasi EPC, cakupan bin, produk tergantikan, biaya rata-rata); helper di sini hanya
 * merapikan masukan sebelum dikirim dan menyediakan label Bahasa Indonesia.
 */
import axios, { API } from "../../../services/apiClient";
import { rememberDocEntities } from "../../../services/docEntityRegistry";

export const REG = `${API}/registration/sessions`;

export const STATUS_LABEL = {
  draft: "Draf", running: "Berjalan", pending_approval: "Menunggu persetujuan", approved: "Disetujui",
  approved_with_exceptions: "Disetujui — ada pengecualian", rejected: "Ditolak",
};
export const STATUS_TONE = {
  draft: "bg-gray-50 text-gray-700 border-gray-200", running: "bg-blue-50 text-blue-700 border-blue-200",
  pending_approval: "bg-amber-50 text-amber-700 border-amber-200", approved: "bg-green-50 text-green-700 border-green-200",
  approved_with_exceptions: "bg-orange-50 text-orange-700 border-orange-200", rejected: "bg-red-50 text-red-700 border-red-200",
};
export const FREEZE_OPTIONS = [
  { value: "zone", label: "Beku per zona/rak (gedung besar) — zona lain tetap melayani" },
  { value: "warehouse", label: "Beku penuh (gedung kecil) — semua gerakan gedung ditolak" },
];
export const EPC_OPTIONS = [
  { value: "read", label: "EPC bawaan tag dibaca (tag sudah unik)" },
  { value: "system", label: "EPC dibuat sistem (ditulis ke tag sebelum ditempel)" },
];
export const GROUP_RESULT = {
  applied: "Disetujui", accepted_with_exceptions: "Disetujui — pengecualian diterima", exception: "Ada pengecualian",
};

/** Tempel banyak kode (handheld mengetik seperti keyboard): pisah baris/spasi/koma/titik koma, buang kembar. */
export function splitCodes(text) {
  const out = [];
  String(text || "").split(/[\s,;]+/).forEach((x) => { const s = x.trim(); if (s && !out.includes(s)) out.push(s); });
  return out.slice(0, 500);
}

/** EPC kanonik (24 hex huruf besar tanpa pemisah) — sama dengan `services/epc.try_canonical`; "" bila tidak sah. */
export function canonicalEpc(raw) {
  const s = String(raw || "").replace(/[\s\-:_.]/g, "").toUpperCase();
  return /^[0-9A-F]{24}$/.test(s) ? s : "";
}

/** Opsi cakupan dari struktur gudang: zona & rak (tingkat/bin cukup lewat rak). */
export function scopeOptions(zones) {
  const out = [];
  (zones || []).forEach((z) => {
    out.push({ id: z.id, label: z.name || z.id, kind: "zona" });
    (z.racks || []).forEach((r) => out.push({ id: r.id, label: `${z.name || z.id} › ${r.name || r.id}`, kind: "rak", parent: z.id }));
  });
  return out;
}

/** Bin aktif diingat per sesi di HP ini saja (kenyamanan; boleh hilang). */
export function rememberBin(sid, bin) {
  try { if (bin) localStorage.setItem(`kn_reg_bin_${sid}`, bin); else localStorage.removeItem(`kn_reg_bin_${sid}`); } catch { /* abaikan */ }
}
export function recalledBin(sid) {
  try { return localStorage.getItem(`kn_reg_bin_${sid}`) || ""; } catch { return ""; }
}

export const regApi = {
  // FIX-1 (K-B1-02) — sesi lintas PT di gedung lokasi kerja: aksi sesi dikirim atas nama PT sesi.
  list: (params) => axios.get(REG, { params }).then((r) => rememberDocEntities(r.data || [])),
  create: (body) => axios.post(REG, body).then((r) => r.data),
  get: (sid) => axios.get(`${REG}/${sid}`).then((r) => r.data),
  start: (sid) => axios.post(`${REG}/${sid}/start`).then((r) => r.data),
  bins: (sid) => axios.get(`${REG}/${sid}/bins`).then((r) => r.data?.bins || []),
  lines: (sid, params) => axios.get(`${REG}/${sid}/lines`, { params }).then((r) => r.data?.lines || []),
  addLine: (sid, body) => axios.post(`${REG}/${sid}/lines`, body).then((r) => r.data),
  patchLine: (sid, lid, body) => axios.patch(`${REG}/${sid}/lines/${lid}`, body).then((r) => r.data),
  voidLine: (sid, lid) => axios.delete(`${REG}/${sid}/lines/${lid}`).then((r) => r.data),
  photo: (sid, lid, file) => { const fd = new FormData(); fd.append("file", file); return axios.post(`${REG}/${sid}/lines/${lid}/photo`, fd).then((r) => r.data); },
  epcCheck: (sid, codes) => axios.post(`${REG}/${sid}/epc-check`, { codes }).then((r) => r.data?.results || []),
  labelDecode: (sid, raw) => axios.post(`${REG}/${sid}/label-decode`, { raw }).then((r) => r.data),
  rack: (sid, rackId, done) => axios.post(`${REG}/${sid}/racks/${rackId}`, { done }).then((r) => r.data),
  markWritten: (sid, ids) => axios.post(`${REG}/${sid}/lines/mark-written`, { line_ids: ids }).then((r) => r.data),
  submit: (sid) => axios.post(`${REG}/${sid}/submit`).then((r) => r.data),
  reconcile: (sid) => axios.get(`${REG}/${sid}/reconcile`).then((r) => r.data),
  approve: (sid, body) => axios.post(`${REG}/${sid}/approve`, body).then((r) => r.data),
  giveBack: (sid, reason) => axios.post(`${REG}/${sid}/return`, { reason }).then((r) => r.data),
  reject: (sid, reason) => axios.post(`${REG}/${sid}/reject`, { reason }).then((r) => r.data),
};
