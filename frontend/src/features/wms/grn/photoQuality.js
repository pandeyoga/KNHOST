import { MIN_SHORT_SIDE } from "./grnApi";

// Ambang dikalibrasi dari foto SJ nyata (Laplacian variance pada sisi panjang 512 px):
// foto tajam ≥ 190, buram ringan (blur 1 px) ≤ 31.
const BLUR_BAD = 40;
const BLUR_WARN = 100;

/** Cek cepat di HP (tanpa internet): ketajaman, terang/gelap, silau, resolusi. */
export async function quickCheck(file) {
  if (!file.type.startsWith("image/")) return { issues: [] };
  const bmp = await createImageBitmap(file).catch(() => null);
  if (!bmp) return { issues: [] };
  const s = 512 / Math.max(bmp.width, bmp.height);
  const w = Math.max(3, Math.round(bmp.width * s)), h = Math.max(3, Math.round(bmp.height * s));
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  const ctx = c.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(bmp, 0, 0, w, h);
  const px = ctx.getImageData(0, 0, w, h).data;
  const g = new Float32Array(w * h);
  let sum = 0, glare = 0;
  for (let i = 0; i < w * h; i++) {
    const v = 0.299 * px[i * 4] + 0.587 * px[i * 4 + 1] + 0.114 * px[i * 4 + 2];
    g[i] = v; sum += v; if (v > 250) glare++;
  }
  let n = 0, m = 0, m2 = 0;
  for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) {
    const i = y * w + x;
    const l = g[i - 1] + g[i + 1] + g[i - w] + g[i + w] - 4 * g[i];
    n++; m += l; m2 += l * l;
  }
  const sharp = n ? m2 / n - (m / n) ** 2 : 0;
  const bright = sum / (w * h), glarePct = (glare / (w * h)) * 100;
  const shortSide = Math.min(bmp.width, bmp.height);
  const issues = [];
  if (sharp < BLUR_BAD) issues.push({ code: "blur", bad: true, label: "Buram — tulisan kabur" });
  else if (sharp < BLUR_WARN) issues.push({ code: "blur", bad: false, label: "Agak buram" });
  if (bright < 70) issues.push({ code: "dark", bad: true, label: "Terlalu gelap" });
  else if (bright > 235) issues.push({ code: "bright", bad: false, label: "Terlalu terang" });
  if (glarePct > 5) issues.push({ code: "glare", bad: false, label: "Ada pantulan cahaya" });
  if (shortSide < MIN_SHORT_SIDE) issues.push({ code: "small", bad: false, label: "Resolusi kecil (foto dari WhatsApp?)" });
  return { sharp: Math.round(sharp), bright: Math.round(bright), glarePct: Math.round(glarePct * 10) / 10, shortSide, issues };
}

/** Gabungkan hasil AI (terpotong/buram/silau/keterbacaan) ke daftar masalah yang sama. */
export function aiIssues(ai) {
  if (!ai?.checked) return [];
  const out = [];
  if (!ai.is_document) out.push({ code: "not_doc", bad: true, label: "Bukan foto surat jalan?" });
  if ((ai.cut_off_sides || []).length) out.push({ code: "cut", bad: true, label: `Terpotong di ${ai.cut_off_sides.join(", ")}` });
  if (ai.blurry) out.push({ code: "ai_blur", bad: true, label: "Tulisan sulit dibaca (buram)" });
  if (ai.glare_or_shadow) out.push({ code: "ai_glare", bad: false, label: "Silau/bayangan menutupi tulisan" });
  if (ai.legibility === "buruk") out.push({ code: "legib", bad: true, label: "Keterbacaan buruk" });
  else if (ai.legibility === "sebagian") out.push({ code: "legib", bad: false, label: "Sebagian sulit dibaca" });
  return out;
}

export const pageIssues = (p) => {
  const all = [...(p.quick?.issues || []), ...aiIssues(p.ai)];
  const seen = new Set();
  return all.filter((x) => (x.code === "ai_blur" && all.some((y) => y.code === "blur" && y.bad) ? false : !seen.has(x.code) && seen.add(x.code)));
};
export const pageBad = (p) => pageIssues(p).some((x) => x.bad);
