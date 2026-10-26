/**
 * sampleViewUtils (fase 3 · P6, D-24b) — logika murni layar **Sample R&D** gabungan
 * (`RndSamplesView`: Papan · Daftar · Galeri).
 *
 * KENAPA BERKAS INI ADA: Labdip/Handfeel/Proofing dulu tiga layar galeri sendiri
 * (`SampleTypeGalleryView`) dengan saringan & KPI masing-masing, sementara Produk Baru/Uji Ulang
 * punya papan/daftar dengan saringan berbeda. Keputusan pemilik 26 Okt: SATU layar dengan chip
 * jenis; galeri per jenis tetap ada sebagai mode tampilan. Supaya aturan saringan tidak bercabang
 * dua lagi, semuanya dikumpulkan di sini (tanpa JSX → mudah diuji).
 */
import { sampleRevisionCount } from "../../components/RevisionProgress";
import { roundTypeOf, sampleTypesOf } from "./sampleTypeMeta";

/** Mode tampilan (PageTabs tingkat-2). Kunci = nilai preset `mode` (alias `rnd-labdip` dkk. → "gallery"). */
export const SAMPLE_MODES = [
  { key: "board", label: "Papan", testId: "rnd-samples-tab-board" },
  { key: "list", label: "Daftar", testId: "rnd-samples-tab-list" },
  { key: "gallery", label: "Galeri", testId: "rnd-samples-tab-gallery" },
];

/** Jenis baku yang dulu punya layar galeri sendiri → id view lamanya (dipakai gerbang `hidden_views`). */
export const LEGACY_TYPE_VIEW = { labdip: "rnd-labdip", handfeel: "rnd-handfeel", proofing: "rnd-proofing" };

/**
 * Chip TUJUAN (hanya di mode Galeri). Papan/Daftar mengikuti menu (Produk Baru / Uji Ulang); galeri lama
 * mencakup SEMUA tujuan, jadi bawaannya "all" — sama dengan isi galeri sebelum digabung.
 */
export const PURPOSE_OPTIONS = [
  { key: "all", label: "Semua tujuan" },
  { key: "new_development", label: "Produk baru" },
  { key: "revalidation", label: "Uji ulang" },
];

export const RESULT_OPTS = [
  { value: "", label: "Semua hasil" }, { value: "acc", label: "Sudah ada ACC" },
  { value: "revisi", label: "Hasil terakhir: revisi" }, { value: "pending", label: "Menunggu hasil supplier" },
  { value: "none", label: "Belum ada ronde" },
];
export const PROOF_OPTS = [{ value: "", label: "Bukti: semua" }, { value: "yes", label: "Sudah ada foto bukti" }, { value: "no", label: "Belum ada bukti" }];
export const SCORE_OPTS = [
  { value: "", label: "Semua skor" }, { value: "unscored", label: "Belum dinilai" },
  { value: "70", label: "≥ 70" }, { value: "80", label: "≥ 80" }, { value: "90", label: "≥ 90" },
];
export const EMPTY_GALLERY_FILTER = { supplier: "", result: "", proof: "", score: "" };

/** Kode jenis yang dipakai kartu galeri: chip jenis aktif, atau jenis pertama dokumen bila "Semua jenis". */
export function cardTypeOf(sample, code) {
  return code || sampleTypesOf(sample)[0] || "";
}

/** Ronde milik satu jenis (tanpa jenis → semua ronde). */
export function roundsOfType(sample, code) {
  const rounds = sample?.rounds || [];
  if (!code) return rounds;
  return rounds.filter((r) => roundTypeOf(r, sample) === code);
}

/** Pencarian teks yang sama untuk ketiga mode (gabungan isian papan lama + galeri lama). */
export function matchSampleSearch(s, term) {
  const t = String(term || "").trim().toLowerCase();
  if (!t) return true;
  return [s.number, s.title, s.brief, s.spec_number, s.color_target?.name, s.design_code, s.so_number, s.requested_by,
    ...(s.participants || []).map((p) => p.supplier_name)]
    .some((v) => String(v || "").toLowerCase().includes(t));
}

/** Saringan dasar semua mode: status (chip), revisi minimal, teks. Galeri: "Semua" tanpa yang batal (perilaku lama). */
export function filterSamples(rows, { status = "", minRevision = "", q = "", gallery = false } = {}) {
  const minRev = Number(minRevision) || 0;
  return (rows || []).filter((s) => {
    if (status) { if (s.status !== status) return false; } else if (gallery && s.status === "cancelled") return false;
    if (minRev && sampleRevisionCount(s) < minRev) return false;
    return matchSampleSearch(s, q);
  });
}

/** Hitungan per chip status — dari SELURUH baris termuat (bukan halaman/tab aktif; pelajaran G5-44). */
export function statusCounts(rows, { gallery = false } = {}) {
  const c = { "": 0 };
  (rows || []).forEach((s) => {
    c[s.status] = (c[s.status] || 0) + 1;
    if (!gallery || s.status !== "cancelled") c[""] += 1;
  });
  return c;
}

/** Saringan khusus galeri (hasil · bukti · skor · supplier) — dihitung pada ronde jenis aktif. */
export function galleryMatch(s, code, g = EMPTY_GALLERY_FILTER) {
  const rounds = roundsOfType(s, cardTypeOf(s, code));
  if (g.supplier && !(s.participants || []).some((p) => p.supplier_id === g.supplier)) return false;
  const last = rounds[rounds.length - 1];
  if (g.result === "acc" && !rounds.some((r) => r.result === "acc")) return false;
  if (g.result === "revisi" && last?.result !== "revisi") return false;
  if (g.result === "pending" && !(last && !last.result)) return false;
  if (g.result === "none" && rounds.length) return false;
  const proofs = rounds.reduce((a, r) => a + (r.attachments || []).length, 0);
  if (g.proof === "yes" && !proofs) return false;
  if (g.proof === "no" && proofs) return false;
  const best = rounds.reduce((a, r) => (r.score != null ? Math.max(a ?? 0, Number(r.score)) : a), null);
  if (g.score === "unscored" && best != null) return false;
  if (g.score && g.score !== "unscored" && !(best != null && best >= Number(g.score))) return false;
  return true;
}

/**
 * KPI galeri dari baris termuat (perilaku galeri lama: per jenis, tanpa yang batal). Kunci SAMA dengan
 * `stats` server supaya satu deret KPI melayani ketiga mode.
 */
export function galleryKpis(rows, code) {
  const live = (rows || []).filter((s) => s.status !== "cancelled");
  return {
    total: live.length,
    sent: live.filter((s) => s.status === "sent").length,
    in_progress: live.filter((s) => s.status === "in_progress").length,
    assessed: live.filter((s) => roundsOfType(s, cardTypeOf(s, code)).some((r) => r.result === "acc")).length,
    decided: live.filter((s) => s.status === "decided").length,
    overdue_rounds: live.filter((s) => roundsOfType(s, cardTypeOf(s, code)).some((r) => r.overdue)).length,
  };
}

/** Pemasok yang muncul di baris termuat (pilihan saringan galeri). */
export function suppliersOf(rows) {
  const m = new Map();
  (rows || []).forEach((s) => (s.participants || []).forEach((p) => { if (p.supplier_id) m.set(p.supplier_id, p.supplier_name); }));
  return [...m.entries()];
}

/** Parameter server: Papan/Daftar mengikuti tujuan menu; Galeri mengikuti chip tujuan ("all" = tanpa saringan). */
export function purposeParam(mode, routePurpose, galleryPurpose) {
  if (mode === "gallery") return galleryPurpose && galleryPurpose !== "all" ? galleryPurpose : "";
  return routePurpose || "";
}
