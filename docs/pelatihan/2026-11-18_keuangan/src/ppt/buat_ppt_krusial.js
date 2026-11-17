// Deck FLOW KRUSIAL Pelatihan Keuangan — versi singkat (alur inti + layar kunci). Pilihan alur & langkah: src/krusial.json.
// Sumber data sama dengan deck lengkap: src/ppt/data.json (siapkan_data.py) + gambar alur src/ppt/alur/*.png.
//   NODE_PATH=<folder node_modules berisi pptxgenjs> node docs/pelatihan/2026-11-18_keuangan/src/ppt/buat_ppt.js
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const HERE = __dirname;
const ROOT = path.resolve(HERE, "..", "..");
const OUT = path.join(ROOT, "Presentasi_Flow_Krusial_Keuangan.pptx");
const D = JSON.parse(fs.readFileSync(path.join(HERE, "data.json"), "utf8"));
const SKILL = process.env.PPTX_SKILL || "";

const THEME = {
  name: "KN Pelatihan Keuangan", headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: { dk1: "0F172A", lt1: "FFFFFF", dk2: "334155", lt2: "F1F5F9", accent1: "0F766E", accent2: "7C3AED",
    accent3: "B45309", accent4: "2563EB", accent5: "DC2626", accent6: "15803D", hlink: "0F766E", folHlink: "7C3AED" },
};
const HEX = { teal: "0F766E", tealSoft: "E6F4F1", navy: "0F172A", slate: "334155", muted: "64748B", line: "E2E8F0",
  soft: "F8FAFC", amber: "B45309", amberSoft: "FFFBEB", green: "15803D", greenSoft: "F0FDF4", red: "DC2626", rose: "BE123C",
  roseSoft: "FFF1F2", violet: "7C3AED" };
const ROLE = { finance: "0F766E", manajer: "7C3AED", manager: "7C3AED", pelatih: "BE123C", sales: "2563EB",
  "admin sales": "0369A1", gudang: "B45309", admin: "334155", sistem: "475569", md: "9333EA" };
const roleColor = (r) => {
  const k = String(r || "").toLowerCase();
  const hit = Object.keys(ROLE).find((x) => k.startsWith(x));
  return hit ? ROLE[hit] : "334155";
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";            // 13.333" × 7.5"
pres.title = "Pelatihan Keuangan — ERP Kain Nusantara";
pres.author = "Tim ERP Kain Nusantara";
pres.company = "Kain Nusantara";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const W = 13.333;

// ── Tata letak (layout) ────────────────────────────────────────────────────────────────────────────────────────────
const FOOT = [
  { text: { text: "Pelatihan Keuangan · ERP Kain Nusantara · " + D.doc_id,
    options: { x: 0.6, y: 7.02, w: 8, h: 0.3, fontSize: 10, color: HEX.muted, margin: 0 } } },
];
pres.defineSlideMaster({
  title: "JUDUL", background: { color: HEX.navy },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.0, w: 11.7, h: 1.7, fontSize: 44, bold: true,
    color: "FFFFFF", fontFace: THEME.headFontFace, valign: "bottom", align: "left", margin: 0 }, text: "" } },
  { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 3.95, w: 11.2, h: 1.6, fontSize: 18, color: "CBD5E1",
    valign: "top", align: "left", margin: 0 }, text: "" } }],
});
pres.defineSlideMaster({
  title: "SEKSI", background: { color: HEX.teal },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.8, y: 0.9, w: 11.7, h: 1.5, fontSize: 36, bold: true,
    color: "FFFFFF", fontFace: THEME.headFontFace, valign: "bottom", align: "left", margin: 0 }, text: "" } },
  { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 2.7, w: 11.7, h: 3.6, fontSize: 18, color: "FFFFFF",
    valign: "top", align: "left", margin: 0 }, text: "" } }],
  slideNumber: { x: 12.2, y: 7.0, w: 0.6, h: 0.3, fontSize: 10, color: "CCFBF1" },
});
pres.defineSlideMaster({
  title: "ISI", background: { color: "FFFFFF" },
  objects: [...FOOT, { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.75, fontSize: 30,
    bold: true, color: HEX.navy, fontFace: THEME.headFontFace, valign: "middle", align: "left", margin: 0 }, text: "" } }],
  slideNumber: { x: 12.2, y: 7.0, w: 0.6, h: 0.3, fontSize: 10, color: HEX.muted },
});
pres.defineSlideMaster({
  title: "LANGKAH", background: { color: "FFFFFF" },
  objects: [...FOOT,
    { placeholder: { options: { name: "kicker", type: "body", x: 0.6, y: 0.28, w: 12.1, h: 0.32, fontSize: 12, bold: true,
      color: HEX.teal, margin: 0, valign: "middle" }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.62, w: 12.1, h: 0.62, fontSize: 26, bold: true,
      color: HEX.navy, fontFace: THEME.headFontFace, valign: "middle", align: "left", margin: 0 }, text: "" } }],
  slideNumber: { x: 12.2, y: 7.0, w: 0.6, h: 0.3, fontSize: 10, color: HEX.muted },
});

// ── Pembantu ───────────────────────────────────────────────────────────────────────────────────────────────────────
const img = (rel) => path.join(ROOT, rel);
const pngSize = (file) => { const b = fs.readFileSync(file); return [b.readUInt32BE(16), b.readUInt32BE(20)]; };
const potong = (s, n) => {
  s = String(s || "").trim();
  if (s.length <= n) return s;
  const cut = s.slice(0, n);
  const titik = Math.max(cut.lastIndexOf(". "), cut.lastIndexOf("; "));
  return (titik > n * 0.55 ? cut.slice(0, titik + 1) : cut.slice(0, cut.lastIndexOf(" "))) + " …";
};
function fit(wh, box) {          // gambar di dalam kotak, rasio dijaga, rata tengah
  const [iw, ih] = wh || [1366, 900];
  const s = Math.min(box.w / iw, box.h / ih);
  const w = iw * s, h = ih * s;
  return { x: box.x + (box.w - w) / 2, y: box.y + (box.h - h) / 2, w, h };
}
function gambar(slide, rel, wh, box, name) {
  const g = fit(wh, box);
  slide.addShape(pres.shapes.RECTANGLE, { x: g.x - 0.04, y: g.y - 0.04, w: g.w + 0.08, h: g.h + 0.08, fill: { color: HEX.line },
    line: { color: HEX.line, width: 0.5 }, shadow: { type: "outer", color: "94A3B8", opacity: 0.35, blur: 6, offset: 2, angle: 90 },
    objectName: `${name}-bingkai` });
  slide.addImage({ path: img(rel), ...g, altText: name, objectName: name });
  return g;
}
function lencana(slide, text, x, y, color, name) {
  const w = Math.min(3.5, 0.32 + String(text).length * 0.095);
  slide.addText(text, { shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.08, x, y, w, h: 0.32, fill: { color },
    color: "FFFFFF", fontSize: 12, bold: true, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: name });
  return w;
}
function label(slide, text, x, y, w, color, name) {
  slide.addText(text.toUpperCase(), { x, y, w, h: 0.26, fontSize: 10.5, bold: true, color, charSpacing: 1, margin: 0,
    isTextBox: true, objectName: name });
}
function kartuTeks(slide, { x, y, w, h, judul, isi, fill, color, name, size = 14 }) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line: { color: fill },
    objectName: `${name}-latar` });
  label(slide, judul, x + 0.25, y + 0.2, w - 0.5, color, `${name}-judul`);
  const runs = Array.isArray(isi) ? isi.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < isi.length - 1,
    paraSpaceAfter: 6 } })) : [{ text: isi }];
  slide.addText(runs, { x: x + 0.25, y: y + 0.52, w: w - 0.5, h: h - 0.7, fontSize: size, color: HEX.navy, valign: "top",
    margin: 0, isTextBox: true, objectName: `${name}-isi`, fit: "shrink" });
}
const circ = ["①", "②", "③", "④", "⑤"];
const menuLangkah = (menu) => String(menu || "").split("›").map((s) => s.trim()).filter(Boolean)
  .map((p, i) => `${circ[i] || i + 1} ${p}`).join("  →  ");

const head = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.navy } } });
const TBL = { fontFace: THEME.bodyFontFace, border: { type: "solid", pt: 0.5, color: HEX.line }, valign: "middle" };
const potongan = (arr, n) => {        // bagi rata: paling banyak n baris per slide, jumlah baris tiap slide seimbang
  const k = Math.max(1, Math.ceil(arr.length / n)), m = Math.ceil(arr.length / k), out = [];
  for (let i = 0; i < arr.length; i += m) out.push(arr.slice(i, i + m));
  return out;
};
const MODUL = Object.fromEntries(D.modul.map((m) => [m.no, m]));
const skenarioModul = (no) => D.skenario.filter((x) => x.modul === no);
const ujiTeks = (x) => (x.uji.langkah ? `${x.uji.lulus}/${x.uji.langkah} langkah lulus uji layar & buku`
  : "ringkasan — langkahnya diuji di skenario terkait");
const SEC0 = "0 · Pengantar";

// Halaman pembuka bagian: judul besar + ringkasan, lalu satu slide isi bagian (pengantar + daftar skenario)
function halamanModul(m, sec) {
  let t = pres.addSlide({ masterName: "JUDUL", sectionTitle: sec });
  t.addText(`Bagian ${m.no} · ${m.judul}`, { placeholder: "title" });
  t.addText(m.ringkas, { placeholder: "body" });
  t.addNotes((m.intro || []).join("\n\n"));
  const daftar = skenarioModul(m.no);
  if (!daftar.length && !(m.intro || []).length) return;
  t = pres.addSlide({ masterName: "LANGKAH", sectionTitle: sec });
  t.addText(`Bagian ${m.no} · ${m.judul}`, { placeholder: "kicker" });
  t.addText("Isi bagian ini", { placeholder: "title" });
  kartuTeks(t, { x: 0.6, y: 1.45, w: 5.6, h: 5.35, judul: "Mengapa bagian ini penting", fill: HEX.tealSoft, color: HEX.teal,
    name: `modul-${m.no}-intro`, isi: m.intro || [], size: 15 });
  const baris = [];
  let subNow = "";
  for (const x of daftar) {
    if (x.sub_judul && x.sub_judul !== subNow) {
      subNow = x.sub_judul;
      baris.push([{ text: subNow, options: { colspan: 3, bold: true, color: HEX.teal, fill: { color: HEX.soft } } }]);
    }
    baris.push([{ text: x.no, options: { bold: true, color: HEX.teal } }, { text: potong(x.judul, 70), options: { color: HEX.navy } },
      { text: `${x.menit}′`, options: { color: HEX.muted, align: "right" } }]);
  }
  if (baris.length) {
    t.addTable([[head("No"), head("Materi"), head("Menit")]].concat(baris), { ...TBL, x: 6.45, y: 1.45, w: 6.25, colW: [0.75, 4.75, 0.75],
      fontSize: baris.length > 16 ? 9.5 : 11.5, margin: [0.02, 0.06, 0.02, 0.06], autoPage: false });
  }
}


// ══ FLOW KRUSIAL ═════════════════════════════════════════════════════════════════════════════════════════════════════
const K = JSON.parse(fs.readFileSync(path.join(HERE, "..", "krusial.json"), "utf8"));
const SK = Object.fromEntries(D.skenario.map((x) => [x.kode, x]));
const ALUR = K.alur.filter((a) => SK[a.dasar]);          // alur yang materinya belum ada (mis. S5 sebelum diuji) dilewati
let s;

function langkahAlur(a) {
  const out = [];
  for (const [kode, nos] of a.langkah) {
    const sc = SK[kode];
    if (!sc) continue;
    const pilih = nos === "semua" ? sc.langkah : sc.langkah.filter((L) => nos.includes(L.no));
    for (const L of pilih) out.push({ sc, L });
  }
  return out;
}

function slideLangkah(a, nomor, { sc, L }, ke, dari) {
  const sec = `${nomor} · ${potong(a.judul, 40)}`;
  s = pres.addSlide({ masterName: "LANGKAH", sectionTitle: sec });
  s.addText(`${nomor}. ${potong(a.judul, 50)} · layar ${ke} dari ${dari} · materi ${sc.no}`, { placeholder: "kicker" });
  s.addText(potong(L.judul, 70), { placeholder: "title" });
  if (L.img) gambar(s, L.img, L.wh, { x: 0.6, y: 1.45, w: 8.35, h: 5.35 }, `K${nomor}-${sc.kode}-L${L.no}-gambar`);
  const px = L.img ? 9.25 : 0.6, pw = L.img ? 3.5 : 12.1;
  lencana(s, L.peran || "Finance", px, 1.45, roleColor(L.peran), `K${nomor}-${sc.kode}-L${L.no}-peran`);
  s.addText(L.menu || "", { x: px, y: 1.88, w: pw, h: 0.5, fontSize: 11, color: HEX.muted, margin: 0, isTextBox: true, valign: "top",
    objectName: `K${nomor}-${sc.kode}-L${L.no}-menu`, fit: "shrink" });
  const blok = [{ text: "LAKUKAN", options: { bold: true, fontSize: 10.5, color: HEX.teal, charSpacing: 1, breakLine: true } },
    { text: potong(L.aksi, 210), options: { breakLine: true, paraSpaceAfter: 9, color: HEX.navy } }];
  if (L.isi) blok.push({ text: "ISI", options: { bold: true, fontSize: 10.5, color: HEX.teal, charSpacing: 1, breakLine: true } },
    { text: potong(L.isi, 130), options: { breakLine: true, paraSpaceAfter: 9, color: HEX.navy } });
  blok.push({ text: "YANG HARUS TERLIHAT", options: { bold: true, fontSize: 10.5, color: HEX.green, charSpacing: 1, breakLine: true } },
    { text: potong(L.hasil, L.isi ? 230 : 300), options: { color: HEX.navy } });
  s.addText(blok, { x: px, y: 2.45, w: pw, h: 4.35, fontSize: 14, valign: "top", margin: 0, isTextBox: true,
    objectName: `K${nomor}-${sc.kode}-L${L.no}-teks`, fit: "shrink" });
  s.addNotes(`${sc.no} ${sc.judul} — langkah ${L.no} · ${L.peran}\nDI MANA: ${L.menu}\nLAKUKAN: ${L.aksi}` + (L.isi ? `\nISI: ${L.isi}` : "")
    + `\nYANG HARUS TERLIHAT: ${L.hasil}\n(Rincian lengkap: manual, materi ${sc.no}.)`);
}

// ── Pembuka ─────────────────────────────────────────────────────────────────────────────────────────────────────────
const SECP = "Pembuka";
pres.addSection({ title: SECP });
s = pres.addSlide({ masterName: "JUDUL", sectionTitle: SECP });
s.addText(K.judul, { placeholder: "title" });
s.addText(`${D.tanggal} · ${K.subjudul}`, { placeholder: "body" });
const nUji = ALUR.reduce((n, a) => n + langkahAlur(a).length, 0);
[[String(ALUR.length), "alur krusial"], [String(nUji), "layar kunci"], ["459/459", "langkah materi lulus uji layar & buku"]]
  .forEach(([v, l], i) => {
    const x = 0.8 + i * 3.6;
    s.addText(v, { x, y: 5.55, w: 3.3, h: 0.8, fontSize: 40, bold: true, color: "5EEAD4", fontFace: THEME.headFontFace, margin: 0,
      isTextBox: true, objectName: `kj-angka-${i}` });
    s.addText(l, { x, y: 6.35, w: 3.3, h: 0.4, fontSize: 14, color: "CBD5E1", margin: 0, isTextBox: true, objectName: `kj-label-${i}` });
  });
s.addNotes("Versi singkat untuk kelas: hanya alur yang paling sering dikerjakan Finance. Semua langkah lain ada di manual lengkap " +
  "(Panduan Pelatihan Keuangan) dan sudah diuji di layar.");

s = pres.addSlide({ masterName: "ISI", sectionTitle: SECP });
s.addText("Alur yang dibahas", { placeholder: "title" });
const langkahY = Math.min(1.0, 5.5 / Math.max(1, ALUR.length));
ALUR.forEach((a, i) => {
  const y = 1.35 + i * langkahY;
  s.addText(String(i + 1), { shape: pres.shapes.OVAL, x: 0.6, y: y + 0.1, w: 0.6, h: 0.6, fill: { color: HEX.teal }, color: "FFFFFF",
    fontSize: 20, bold: true, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: `kj-agenda-${i}-no` });
  s.addText([{ text: a.judul, options: { bold: true, fontSize: 18, color: HEX.navy, breakLine: true, fontFace: THEME.headFontFace } },
    { text: a.pengantar, options: { fontSize: 12.5, color: HEX.slate } }], { x: 1.45, y, w: 11.25, h: langkahY - 0.08, valign: "middle",
    margin: 0, isTextBox: true, objectName: `kj-agenda-${i}-teks`, fit: "shrink" });
});

s = pres.addSlide({ masterName: "ISI", sectionTitle: SECP });
s.addText("Akses Finance & siapa mengerjakan apa", { placeholder: "title" });
kartuTeks(s, { x: 0.6, y: 1.35, w: 4.6, h: 5.4, judul: "Akses Finance (17 Nov 2026)", fill: HEX.amberSoft, color: HEX.amber, name: "kj-akses",
  isi: [K.catatan_akses], size: 15 });
s.addTable([[head("Peran"), head("Tugas di aplikasi")]].concat(D.peran.map(([p, t]) => [
  { text: p, options: { bold: true, color: roleColor(p) } }, { text: t, options: { color: HEX.navy } }])),
{ ...TBL, x: 5.45, y: 1.35, w: 7.25, colW: [1.9, 5.35], fontSize: 11.5, margin: [0.04, 0.08, 0.04, 0.08] });

s = pres.addSlide({ masterName: "ISI", sectionTitle: SECP });
s.addText("Alur uang — di mana tiap alur terjadi", { placeholder: "title" });
gambar(s, "src/ppt/alur/peta_uang.png", pngSize(path.join(HERE, "alur", "peta_uang.png")), { x: 0.6, y: 1.35, w: 12.1, h: 4.4 }, "kj-peta");
s.addText("Setiap dokumen membuat jurnal otomatis. Tugas Finance: mencatat uang masuk & keluar pada dokumen yang benar, mencocokkannya " +
  "dengan bank, dan memastikan buku seimbang.", { x: 0.6, y: 6.0, w: 12.1, h: 0.8, fontSize: 15, color: HEX.slate, margin: 0,
  isTextBox: true, objectName: "kj-peta-teks" });

if (D.nav_contoh.length) {
  s = pres.addSlide({ masterName: "ISI", sectionTitle: SECP });
  s.addText("Cara menuju layar", { placeholder: "title" });
  gambar(s, D.nav_contoh[0].img, [1366, 900], { x: 0.6, y: 1.35, w: 8.0, h: 5.4 }, "kj-nav");
  [["①", "Klik nama grup di menu kiri", "Mis. KEUANGAN."], ["②", "Klik menunya", "Mis. Piutang."],
    ["③", "Pilih tab di atas layar", "Mis. Penagihan & Penerimaan."], ["⌕", "Atau Cari menu… (Ctrl+K)", "Ketik nama layar, Enter."]]
    .forEach(([n, j, t], i) => {
      const y = 1.45 + i * 1.32;
      s.addText(n, { shape: pres.shapes.OVAL, x: 8.95, y, w: 0.55, h: 0.55, fill: { color: i < 3 ? HEX.red : HEX.slate }, color: "FFFFFF",
        fontSize: 16, bold: true, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: `kj-nav-${i}-no` });
      s.addText([{ text: j, options: { bold: true, breakLine: true, color: HEX.navy } }, { text: t, options: { color: HEX.slate } }],
        { x: 9.7, y: y - 0.05, w: 3.05, h: 1.1, fontSize: 14, valign: "top", margin: 0, isTextBox: true, objectName: `kj-nav-${i}-teks` });
    });
}

// ── Alur ────────────────────────────────────────────────────────────────────────────────────────────────────────────
ALUR.forEach((a, i) => {
  const nomor = i + 1, base = SK[a.dasar], sec = `${nomor} · ${potong(a.judul, 40)}`;
  pres.addSection({ title: sec });
  s = pres.addSlide({ masterName: "SEKSI", sectionTitle: sec });
  s.addText(`${nomor}. ${a.judul}`, { placeholder: "title" });
  s.addText([{ text: a.pengantar, options: { breakLine: true, paraSpaceAfter: 12 } },
    { text: `${base.peran} · materi lengkap: ${base.no} ${base.judul}`, options: { fontSize: 14, color: "CCFBF1" } }], { placeholder: "body" });
  if ((base.konsep || []).length) {
    s = pres.addSlide({ masterName: "LANGKAH", sectionTitle: sec });
    s.addText(`${nomor}. ${a.judul}`, { placeholder: "kicker" });
    s.addText("Konsep inti", { placeholder: "title" });
    const k = base.konsep.slice(0, 5);
    s.addText(k.map((t, j) => ({ text: potong(t, 240), options: { bullet: { type: "number" }, breakLine: j < k.length - 1, paraSpaceAfter: 10,
      color: HEX.navy } })), { x: 0.6, y: 1.5, w: 12.1, h: 5.3, fontSize: k.length > 4 ? 16 : 18, valign: "top", margin: 0, isTextBox: true,
      objectName: `kj-${nomor}-konsep`, fit: "shrink" });
  }
  const alurPng = path.join(HERE, "alur", `${base.kode}.png`);
  if (fs.existsSync(alurPng)) {
    s = pres.addSlide({ masterName: "LANGKAH", sectionTitle: sec });
    s.addText(`${nomor}. ${a.judul}`, { placeholder: "kicker" });
    s.addText("Alur & siapa mengerjakan", { placeholder: "title" });
    gambar(s, path.relative(ROOT, alurPng), pngSize(alurPng), { x: 0.6, y: 1.45, w: 12.1, h: 4.6 }, `kj-${nomor}-alur`);
    s.addText(base.alur.map((x, j) => `${j + 1}. ${x.peran} — ${x.label}`).join("   ·   "), { x: 0.6, y: 6.15, w: 12.1, h: 0.65,
      fontSize: 12, color: HEX.slate, margin: 0, isTextBox: true, valign: "top", objectName: `kj-${nomor}-alur-teks`, fit: "shrink" });
  }
  const jt = base.jurnal_per_tahap || [];
  potongan(jt, 8).forEach((bar, k, all) => {
    s = pres.addSlide({ masterName: "LANGKAH", sectionTitle: sec });
    s.addText(`${nomor}. ${a.judul}`, { placeholder: "kicker" });
    s.addText(all.length > 1 ? `Jurnal di setiap tahap (${k + 1}/${all.length})` : "Jurnal di setiap tahap", { placeholder: "title" });
    const kontrol = (base.titik_kontrol || []).length && k === all.length - 1;
    s.addTable([[head("Tahap"), head("Dokumen"), head("Jurnal (D = debit, K = kredit)")]].concat(bar.map((r) => [
      { text: r.tahap, options: { bold: true, color: HEX.navy } }, { text: r.dokumen, options: { color: HEX.slate } },
      { text: r.jurnal, options: { color: HEX.teal } }])),
    { ...TBL, x: 0.6, y: 1.45, w: kontrol ? 8.3 : 12.1, colW: kontrol ? [2.3, 1.9, 4.1] : [3.2, 2.6, 6.3],
      fontSize: bar.length > 6 ? 10.5 : 12, margin: [0.04, 0.07, 0.04, 0.07] });
    if (kontrol) kartuTeks(s, { x: 9.1, y: 1.45, w: 3.6, h: 5.35, judul: "Titik kontrol", fill: HEX.amberSoft, color: HEX.amber,
      name: `kj-${nomor}-kontrol`, isi: base.titik_kontrol.slice(0, 6).map((x) => potong(x, 140)), size: 12 });
  });
  if (!jt.length && ((base.cek_buku || []).length || (base.kesalahan_umum || []).length)) {
    s = pres.addSlide({ masterName: "LANGKAH", sectionTitle: sec });
    s.addText(`${nomor}. ${a.judul}`, { placeholder: "kicker" });
    s.addText("Hasil di buku & kesalahan umum", { placeholder: "title" });
    kartuTeks(s, { x: 0.6, y: 1.45, w: 5.95, h: 5.35, judul: "Cek di buku", fill: HEX.greenSoft, color: HEX.green, name: `kj-${nomor}-buku`,
      isi: (base.cek_buku || []).slice(0, 5).map((x) => potong(x, 200)), size: 14 });
    kartuTeks(s, { x: 6.75, y: 1.45, w: 5.95, h: 5.35, judul: "Kesalahan yang sering terjadi", fill: HEX.amberSoft, color: HEX.amber,
      name: `kj-${nomor}-salah`, isi: (base.kesalahan_umum || []).slice(0, 4).map((x) => potong(x, 200)), size: 14 });
  }
  const ls = langkahAlur(a);
  ls.forEach((x, j) => slideLangkah(a, nomor, x, j + 1, ls.length));
});

// ── Penutup ─────────────────────────────────────────────────────────────────────────────────────────────────────────
pres.addSection({ title: "Penutup" });
s = pres.addSlide({ masterName: "ISI", sectionTitle: "Penutup" });
s.addText("Rutinitas harian Finance", { placeholder: "title" });
s.addTable([[head("Kapan"), head("Lakukan")]].concat(K.rutinitas.map(([w, t]) => [
  { text: w, options: { bold: true, color: HEX.teal } }, { text: t, options: { color: HEX.navy } }])),
{ ...TBL, x: 0.6, y: 1.35, w: 12.1, colW: [2.8, 9.3], fontSize: 15, margin: [0.08, 0.1, 0.08, 0.1] });
s = pres.addSlide({ masterName: "JUDUL", sectionTitle: "Penutup" });
s.addText("Tanya jawab", { placeholder: "title" });
s.addText("Langkah lengkap setiap alur ada di manual (Panduan Pelatihan Keuangan) — semuanya sudah diuji di layar dan dicocokkan " +
  "dengan buku. Temuan di kelas: catat nomor dokumen + tangkapan layar, serahkan ke pelatih.", { placeholder: "body" });

(async () => {
  await pres.writeFile({ fileName: OUT });
  if (SKILL) {
    const { applyTheme } = require(path.join(SKILL, "scripts", "apply_theme.js"));
    await applyTheme(OUT, THEME);
  }
  console.log("PPTX:", OUT);
})();
