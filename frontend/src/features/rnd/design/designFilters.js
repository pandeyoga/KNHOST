/**
 * designFilters (fase 3 · P6, D-09) — saringan & hitungan layar **Desain & Pattern** (`RndDesignsView`) untuk
 * kedua mode tampilan: **Master** (semua desain) dan **Galeri** (showcase desain ACC — dulu layar sendiri
 * `DesignGalleryView` / `cs-design-gallery`). Satu fungsi saringan untuk dua mode supaya "Galeri" tidak
 * kembali menjadi daftar kedua dengan aturan sendiri.
 */
import { DESIGN_STATUS_META, PROOFING_STATE_META } from "../rndMeta";
import { inDateRange } from "./DateQuickNav";

/** Status yang dianggap "sudah ACC" — isi mode Galeri (sama dengan galeri showcase lama). */
export const ACC_STATUSES = ["approved", "final_submitted", "active"];

export const DESIGN_MODES = [
  { key: "master", label: "Master", testId: "rnd-designs-tab-master" },
  { key: "gallery", label: "Galeri Desain (Showcase)", testId: "rnd-designs-tab-gallery" },
];

export const REVISION_OPTS = [
  { value: "", label: "Semua ronde" }, { value: "0", label: "Pengajuan awal (belum revisi)" },
  { value: "1", label: "≥ 1× revisi" }, { value: "2", label: "≥ 2× revisi" }, { value: "3", label: "≥ 3× revisi" },
];
export const SCORE_OPTS = [
  { value: "", label: "Semua nilai ACC" }, { value: "unscored", label: "Belum ACC / belum dinilai" },
  { value: "1", label: "≥ 1,00" }, { value: "1.5", label: "≥ 1,50" }, { value: "1.75", label: "≥ 1,75" }, { value: "2", label: "= 2,00" },
];
export const ARTWORK_OPTS = [{ value: "", label: "Berkas: semua" }, { value: "yes", label: "Sudah ada berkas desain" }, { value: "no", label: "Belum ada berkas" }];
export const HOLD_OPTS = [{ value: "", label: "Ditahan: semua" }, { value: "yes", label: "Sedang ditahan" }, { value: "no", label: "Tidak ditahan" }];
export const PROOFING_OPTS = [{ value: "", label: "Proofing: semua" },
  ...Object.entries(PROOFING_STATE_META).map(([k, m]) => ({ value: k, label: m.label }))];
export const ORIGIN_OPTS = [{ value: "", label: "Asal: semua" }, { value: "internal", label: "Desain internal" }, { value: "special_order", label: "Pesanan Khusus" }, { value: "redesign", label: "Redesign" }];
// UAT 24 Okt (P1.5) — kepemilikan & status produksi desain (dulu hanya di galeri showcase).
export const OWN_OPTS = [{ value: "", label: "Semua kepemilikan" }, { value: "white", label: "White label" },
  { value: "customer", label: "Customer label" }, { value: "claim_pending", label: "Klaim menunggu" }];
export const PROD_OPTS = [{ value: "", label: "Diproduksi & belum" }, { value: "yes", label: "Sudah diproduksi" }, { value: "no", label: "Belum diproduksi" }];

export const EMPTY_FILTER = { q: "", status: "", cat: "", dcat: "", designer: "", tag: "", product: "", revision: "", score: "", artwork: "", line: "", hold: "", proofing: "", origin: "", own: "", produced: "" };
export const EMPTY_DATE = { field: "approved_at", from: "", to: "", preset: "" };

/** Status tampil (desain `retired` lama dibaca sebagai arsip). */
export const statusOf = (d) => (d.status === "retired" ? "archived" : (d.status || "draft"));

/** Pilihan chip status per mode. Galeri hanya status ACC (status "acc" preset = semua status ACC). */
export function statusOptions(mode) {
  if (mode === "gallery") {
    return [{ key: "", label: "Semua status ACC" }, ...ACC_STATUSES.map((s) => ({ key: s, label: DESIGN_STATUS_META[s].label }))];
  }
  return [{ key: "", label: "Semua status" },
    ...Object.entries(DESIGN_STATUS_META).filter(([k]) => k !== "retired").map(([k, m]) => ({ key: k, label: m.label }))];
}

/** Baris dasar per mode: Galeri = hanya desain ACC. */
export function rowsForMode(rows, mode) {
  return mode === "gallery" ? (rows || []).filter((d) => ACC_STATUSES.includes(d.status)) : (rows || []);
}

/** Saringan lengkap (teks, chip status, 13 dropdown, rentang tanggal) — sama untuk kedua mode. */
export function filterDesigns(rows, f = EMPTY_FILTER, date = EMPTY_DATE) {
  const term = String(f.q || "").trim().toLowerCase();
  return (rows || []).filter((d) => {
    if (f.status && statusOf(d) !== f.status) return false;
    if (f.cat && d.category_code !== f.cat) return false;
    if (f.dcat && d.design_category_code !== f.dcat) return false;
    if (f.designer && d.created_by !== f.designer) return false;
    if (f.tag && !(d.tags || []).includes(f.tag)) return false;
    if (f.product && !(d.recommended_product_ids || []).includes(f.product)) return false;
    const rev = d.revision_count ?? Math.max(0, (d.version || 1) - 1);
    if (f.revision === "0" && rev !== 0) return false;
    if (f.revision && f.revision !== "0" && rev < Number(f.revision)) return false;
    const sc = d.final_score;
    if (f.score === "unscored" && sc !== null && sc !== undefined) return false;
    if (f.score && f.score !== "unscored" && !(sc !== null && sc !== undefined && Number(sc) >= Number(f.score))) return false;
    if (f.artwork === "yes" && !d.artwork_count) return false;
    if (f.artwork === "no" && d.artwork_count) return false;
    if (f.hold === "yes" && !d.on_hold) return false;
    if (f.hold === "no" && d.on_hold) return false;
    if (f.proofing && (d.proofing?.state || "none") !== f.proofing) return false;
    if (f.origin && (d.origin || "internal") !== f.origin) return false;
    if (f.own && (f.own === "claim_pending" ? !d.claim_pending : (d.ownership || "white") !== f.own)) return false;
    if (f.produced && (f.produced === "yes") !== Boolean(d.produced)) return false;
    if (!inDateRange(d[date.field], date.from, date.to)) return false;
    if (!term) return true;
    return [d.code, d.title, d.story, d.category_name, d.design_category_name, d.created_by, d.proofing?.detail,
      d.proofing?.master_product?.sku, ...(d.tags || []), ...(d.recommended_products || []).map((p) => `${p.sku} ${p.name}`)]
      .some((v) => String(v || "").toLowerCase().includes(term));
  });
}

/** Hitungan per chip status — dari seluruh baris mode aktif (G5-41). */
export function statusCounts(rows) {
  const c = { "": (rows || []).length };
  (rows || []).forEach((d) => { const k = statusOf(d); c[k] = (c[k] || 0) + 1; });
  return c;
}

/** KPI kepala layar (selalu dari SEMUA desain termuat, apa pun modenya). */
export function designStats(rows) {
  const r = rows || [];
  return {
    total: r.length,
    review: r.filter((d) => ["pending_approval", "in_review"].includes(d.status)).length,
    revision: r.filter((d) => d.status === "revision").length,
    final: r.filter((d) => ["approved", "final_submitted"].includes(d.status)).length,
    acc: r.filter((d) => ACC_STATUSES.includes(d.status)).length,
    hold: r.filter((d) => d.on_hold).length,
    proofing: r.filter((d) => d.proofing?.state === "in_progress").length,
    master: r.filter((d) => d.proofing?.state === "master").length,
  };
}

/** Jumlah saringan aktif (tanpa teks & lini; chip status tidak dihitung di Galeri — G5-40). */
export function activeFilterCount(f, date, mode) {
  return Object.entries(f).filter(([k, v]) => v && k !== "q" && k !== "line" && !(mode === "gallery" && k === "status")).length
    + (date.from || date.to ? 1 : 0);
}
