/**
 * configApi.js — FASE G-0 · klien API Pusat Pengaturan.
 *
 * Satu tempat untuk semua panggilan konfigurasi supaya komponen UI tetap tipis
 * dan tidak ada URL yang tersebar (aturan repo: satu jalur, bukan ad-hoc).
 */
import axios, { API } from "../../../services/apiClient";
import { apiErrorText } from "../../../utils/apiError";
import { stripInternalCodes } from "../../../utils/cleanText";
import { entityShortFromCtx } from "../../../utils/entityLabel";

const BASE = `${API}/config`;

export const configApi = {
  /** Katalog setting + grup (sumber tampilan UI generik). */
  registry: (params = {}) => axios.get(`${BASE}/registry`, { params }).then((r) => r.data),

  /** Nilai efektif untuk satu grup / hasil pencarian, mengikuti konteks scope. */
  effective: (params = {}) => axios.get(`${BASE}/effective`, { params }).then((r) => r.data),

  /** Jejak "kenapa nilainya begini?" untuk satu setting. */
  explain: (params = {}) => axios.get(`${BASE}/explain`, { params }).then((r) => r.data),

  /** "Coba dulu" — jalankan aturan tanpa menyimpan. */
  simulate: (body) => axios.post(`${BASE}/simulate`, body).then((r) => r.data),

  /** Simpan satu/beberapa perubahan (append-only + langsung aktif di mesin). */
  save: (items) => axios.put(`${BASE}/values`, { items }).then((r) => r.data),

  /** Tulis nilai bawaan sistem pada lapisan yang disebut (KF-T4: "Pakai nilai bawaan sistem …"; alasan wajib bila
   *  kuncinya berisiko tinggi). */
  reset: (body) => axios.post(`${BASE}/values/reset`, body).then((r) => r.data),

  /** FASE E-4 (E4.6) — cabut nilai pada satu lapisan → kembali mewarisi lapisan di atasnya. */
  clear: (body) => axios.post(`${BASE}/values/clear`, body).then((r) => r.data),

  /** KF-T3 — batalkan satu perubahan berjadwal yang belum berlaku: `{ id, reason }`. */
  cancelScheduled: (body) => axios.post(`${BASE}/values/cancel-scheduled`, body).then((r) => r.data),

  /** Riwayat perubahan (siapa, kapan, dari→ke, alasan). KF-T4 — saringan `group`, `changed_by`, `scope_type`/`scope_id`,
   *  `date_from`/`date_to`, halaman `offset`/`limit` → `{ rows, total }`. */
  history: (params = {}) => axios.get(`${BASE}/history`, { params }).then((r) => r.data),

  /** KF-T5 — pelanggan/barang yang punya aturan khusus untuk satu kunci: `{ key, scope_type }` → `{ rows, total }`. */
  layers: (params = {}) => axios.get(`${BASE}/layers`, { params }).then((r) => r.data),

  /** Kesehatan wiring: apakah setiap setting benar-benar tersambung ke kode. */
  health: () => axios.get(`${BASE}/health`).then((r) => r.data),

  /** DAFTAR DAMPAK — dokumen terbuka mana yang terpengaruh koreksi harga master. */
  impactPreview: (body) => axios.post(`${BASE}/impact-preview`, body).then((r) => r.data),

  /** Terapkan koreksi harga HANYA ke dokumen yang dicentang. */
  impactApply: (body) => axios.post(`${BASE}/impact-apply`, body).then((r) => r.data),
};

/** Pesan error yang enak dibaca user (bukan stack trace). */
// UAT 24 Okt (audit UI tahap 2, G5-15) — lewat apiErrorText: "Permission ditolak: settings.view" mentah dulu tampil
// apa adanya; kini kalimat akses Indonesia (G0-03), detail objek/422 juga terbaca.
export const errMsg = (e, fallback = "Terjadi kesalahan.") => apiErrorText(e, fallback) || fallback;

// UAT 24 Okt (audit UI tahap 2, G5-61) — teks bantu registri memuat backtick markdown literal (`rnd.x`) dan kode
// keputusan "(KN-D16)"; dibersihkan sebelum tampil. Setting "(Lama) … TIDAK DIPAKAI LAGI" dikenali sebagai usang.
export const cleanCfgText = (t) => stripInternalCodes(String(t || "").replace(/`([^`]+)`/g, "$1"));
export const isDeprecatedSetting = (item) => item?.status === "not_used"
  || /\(lama\)|tidak dipakai lagi/i.test(`${item?.label || ""} ${item?.help || ""}`);
/** Cakupan riwayat/lapisan: nama badan usaha, bukan id (`ent_ksc`). KF-T5 — pelanggan/barang: nama dari server
 *  (`label`), id tidak pernah tampil. */
export const scopeText = (type, id, label = "") => {
  const t = SCOPE_LABEL_SHORT[type] || type || "";
  if (!id) return t;
  if (type === "customer" || type === "product") return label ? `${t}: ${label}` : t;
  return `${t}: ${type === "entity" ? entityShortFromCtx(id, id) : id}`;
};
// KF-T4 — "Berlaku untuk": Semua PT (aturan grup) · PT · pelanggan · produk (glosarium KN_32; tanpa "Global"/"entitas").
const SCOPE_LABEL_SHORT = { global: "Semua PT", entity: "PT", customer: "Pelanggan", supplier: "Pemasok",
  product: "Barang", document: "Dokumen" };   // KF-T5 — lapisan produk ditulis "barang" (kartu barang)

/** Angka gaya Indonesia (titik ribuan, koma desimal). */
export function idNum(v, maxDec = 2) {
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v);
  return n.toLocaleString("id-ID", { maximumFractionDigits: maxDec });
}

/** Label satu butir daftar: dari `options` (atau `ref_options`, mis. nama peran) bila ada. */
function itemLabel(entry, v) {
  const opt = [...(entry.options || []), ...(entry.ref_options || [])].find((o) => String(o.value) === String(v));
  return opt ? opt.label : String(v);
}

/** Format nilai config menjadi teks yang dimengerti awam. */
export function formatValue(entry, value) {
  if (value === null || value === undefined || value === "") return "—";
  switch (entry.type) {
    case "bool":
      return value ? "Ya / Aktif" : "Tidak / Mati";
    case "pct":
      return `${idNum(value)}${entry.unit ? ` ${entry.unit}` : " %"}`;
    case "money":
      return `Rp ${idNum(value, 0)}`;
    case "int":
    case "duration":
    case "decimal":
      return `${idNum(value)}${entry.unit ? ` ${entry.unit}` : ""}`;
    case "enum": {
      const opt = (entry.options || []).find((o) => o.value === value);
      return opt ? opt.label : String(value);
    }
    case "list":
      // KF-T4 — butir berlabel (nama peran, nama pilihan), bukan kode mentah.
      return Array.isArray(value) ? (value.length ? value.map((v) => itemLabel(entry, v)).join(" · ") : "—")
        : String(value);
    case "text":
      return (entry.ref_options || []).length ? itemLabel(entry, value) : String(value);
    case "table":
      return Array.isArray(value)
        ? `${value.length} baris`
        : `${Object.keys(value || {}).length} entri`;
    default:
      return String(value);
  }
}

/**
 * Keputusan pemilik K-08 (26 Okt) — kelompok bobot yang membentuk SATU nilai dan dibaca sebagai porsi dari 100%.
 * Server (`rnd_kpi_service.compute_grade`) menyetarakan jumlahnya ke 100%; layar menampilkan jumlah setelan dan,
 * bila bukan 100, porsi efektif hasil penyetaraan — supaya tidak ada lagi "40% + 40% + 20% + 20% = 120%".
 */
export const WEIGHT_SETS = [
  {
    id: "rnd-designer-grade",
    label: "Bobot nilai desainer",
    keys: ["rnd.kpi_weight_on_time", "rnd.kpi_weight_score", "rnd.kpi_weight_acc", "rnd.kpi_weight_design"],
    names: ["tepat waktu", "skor penilaian", "sekali-jadi (ACC)", "nilai versi desain"],
  },
];

/** Ringkasan kelompok bobot yang SEMUA kuncinya ada di `items` (nilai efektif) → [{id,label,total,parts:[{name,value,share}]}]. */
export function weightSetSummaries(items) {
  const byKey = new Map((items || []).map((i) => [i.key, i]));
  return WEIGHT_SETS.filter((s) => s.keys.every((k) => byKey.has(k))).map((s) => {
    const values = s.keys.map((k) => Number(byKey.get(k).value) || 0);
    const total = values.reduce((a, b) => a + b, 0);
    const parts = values.map((v, i) => ({
      name: s.names[i], value: v, share: total > 0 ? Math.round((v * 1000) / total) / 10 : 0,
    }));
    return { id: s.id, label: s.label, total, parts };
  });
}

export const RISK_LABEL = { low: "Risiko rendah", medium: "Risiko sedang", high: "Risiko tinggi" };

/**
 * Ringkas nilai apa pun menjadi teks aman untuk JSX.
 *
 * Kenapa perlu: sebagian setting bertipe `table`/`list` bernilai objek/array.
 * `String(obj)` menghasilkan "[object Object]", dan merender objek langsung ke
 * JSX memicu React error #31 ("Objects are not valid as a React child") — hal
 * ini benar-benar terjadi pada `scheduled_applied` di layar Kesehatan Konfigurasi.
 */
export function shortVal(v, max = 60) {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "boolean") return v ? "Ya" : "Tidak";
  if (typeof v === "object") {
    const s = Array.isArray(v) ? v.join(" · ") : JSON.stringify(v);
    return s.length > max ? `${s.slice(0, max)}…` : s;
  }
  return String(v);
}

export const LAYER_TONE = {
  code_default: "muted", legacy_global: "blue", global: "blue",
  legacy_entity: "purple", entity: "purple", supplier: "teal",
  customer: "teal", product: "orange", document: "orange", hypothetical: "orange",
  override: "red",   // KF-T3 — ditimpa aturan lain (penimpaan terdaftar)
};

/** KF-T4 (KF-UX-13) — saringan kartu: semua · sudah diubah · risiko tinggi · tiga tema lintas kelompok (server `themes`). */
export const CARD_FILTERS = [
  { key: "all", label: "Semua" },
  { key: "changed", label: "Sudah diubah" },
  { key: "high", label: "Risiko tinggi" },
  { key: "persetujuan", label: "Persetujuan", theme: true },
  { key: "pengingat", label: "Pengingat & batas waktu", theme: true },
  { key: "toleransi", label: "Toleransi selisih", theme: true },
];
export function cardFilterOk(item, filter) {
  if (!filter || filter === "all") return true;
  if (filter === "changed") return item.never_changed === false;
  if (filter === "high") return item.risk === "high";
  return (item.themes || []).includes(filter);
}
/** KF-T4 — "Bisa dibedakan untuk: …" dari `scopes`. */
export const SCOPE_CAN = { global: "Semua PT", entity: "Satu PT", customer: "Satu pelanggan", product: "Satu barang",
  supplier: "Satu pemasok", document: "Satu dokumen" };

export const WIRING_TONE = { OK: "green", STALE: "orange", MISSING: "red", NOT_USED: "muted" };
export const WIRING_LABEL = {
  OK: "Aktif & tersambung", STALE: "Referensi kode basi",
  MISSING: "Referensi kode salah", NOT_USED: "Tidak dipakai",
};
export const VERDICT_TONE = { ok: "green", warn: "orange", block: "red" };
export const SCOPE_LABEL = {
  // KF-T4 — bilah "Berlaku untuk" (glosarium: PT, aturan grup).
  global: "Semua PT (aturan grup)", entity: "Satu PT",
  customer: "Pelanggan ini", supplier: "Pemasok tertentu",   // KF-T5
  product: "Barang ini", document: "Dokumen tertentu",
};
