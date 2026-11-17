// Deck PowerPoint Pelatihan Keuangan — fokus ALUR, NAVIGASI, dan TANGKAPAN LAYAR per langkah; rincian di catatan
// pembicara dan di manual (Panduan_Pelatihan_Keuangan_*.pdf). Sumber: src/ppt/data.json (siapkan_data.py).
//   NODE_PATH=<folder node_modules berisi pptxgenjs> node docs/pelatihan/2026-11-18_keuangan/src/ppt/buat_ppt.js
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const HERE = __dirname;
const ROOT = path.resolve(HERE, "..", "..");
const OUT = path.join(ROOT, "Presentasi_Pelatihan_Keuangan_ERP_Kain_Nusantara.pptx");
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

// ── 1. Pembuka ─────────────────────────────────────────────────────────────────────────────────────────────────────
pres.addSection({ title: "Pembuka" });
let s = pres.addSlide({ masterName: "JUDUL", sectionTitle: "Pembuka" });
s.addText("Pelatihan Keuangan ERP Kain Nusantara", { placeholder: "title" });
s.addText(`${D.tanggal} · ${D.skenario.length} skenario praktik · alur, navigasi & layar setiap langkah`, { placeholder: "body" });
const nLangkah = D.skenario.reduce((a, x) => a + x.langkah.length, 0);
const nLulus = D.skenario.reduce((a, x) => a + x.uji.lulus, 0), nUji = D.skenario.reduce((a, x) => a + x.uji.langkah, 0);
[[String(D.skenario.length), "skenario praktik"], [String(nLangkah), "langkah bergambar"], [`${nLulus}/${nUji}`, "langkah lulus uji layar & buku"]]
  .forEach(([v, l], i) => {
    const x = 0.8 + i * 3.6;
    s.addText(v, { x, y: 5.55, w: 3.3, h: 0.8, fontSize: 40, bold: true, color: "5EEAD4", fontFace: THEME.headFontFace, margin: 0,
      isTextBox: true, objectName: `judul-angka-${i}` });
    s.addText(l, { x, y: 6.35, w: 3.3, h: 0.4, fontSize: 14, color: "CBD5E1", margin: 0, isTextBox: true, objectName: `judul-label-${i}` });
  });
s.addNotes("Pembukaan. Slide ini menunjukkan alur, cara menuju layar, dan tangkapan layar setiap langkah. Rincian isian, " +
  "hasil yang harus terlihat, dan cek buku ada di manual (Panduan Pelatihan Keuangan, PDF) dan lembar latihan.");

s = pres.addSlide({ masterName: "ISI", sectionTitle: "Pembuka" });
s.addText("Cara belajar hari ini", { placeholder: "title" });
[["1", "Slide (layar besar)", "Alur bisnis, cara menuju layar, dan tangkapan layar tiap langkah — tombol yang diklik ditandai merah."],
  ["2", "Manual (PDF)", "Rincian tiap langkah: isian, yang harus terlihat, cek buku (jurnal & saldo), kesalahan umum."],
  ["3", "Praktik di akun sendiri", "Setiap peserta memakai akun Finance sendiri dan dokumen bernama “Latihan NN” (NN = nomor peserta)."],
  ["4", "Lembar latihan", "Centang langkah yang hasilnya sama; tulis nomor dokumen bila berbeda dan beri tahu pelatih."]]
  .forEach(([n, j, t], i) => {
    const x = 0.6 + (i % 2) * 6.15, y = 1.45 + Math.floor(i / 2) * 2.7;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 5.95, h: 2.45, rectRadius: 0.12, fill: { color: HEX.soft },
      line: { color: HEX.line, width: 0.75 }, objectName: `cara-${n}` });
    s.addText(n, { shape: pres.shapes.OVAL, x: x + 0.3, y: y + 0.3, w: 0.62, h: 0.62, fill: { color: HEX.teal }, color: "FFFFFF",
      fontSize: 20, bold: true, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: `cara-${n}-no` });
    s.addText(j, { x: x + 1.15, y: y + 0.3, w: 4.5, h: 0.62, fontSize: 20, bold: true, color: HEX.navy, valign: "middle",
      margin: 0, isTextBox: true, fontFace: THEME.headFontFace, objectName: `cara-${n}-judul` });
    s.addText(t, { x: x + 0.3, y: y + 1.1, w: 5.35, h: 1.15, fontSize: 15, color: HEX.slate, valign: "top", margin: 0,
      isTextBox: true, objectName: `cara-${n}-isi` });
  });

s = pres.addSlide({ masterName: "ISI", sectionTitle: "Pembuka" });
s.addText("Jadwal satu hari", { placeholder: "title" });
const head = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.navy } } });
const rows = [[head("Jam"), head("Kode"), head("Skenario"), head("Menit")]].concat(D.jadwal.map((j) => {
  const isBreak = !j.kode;
  const o = isBreak ? { italic: true, color: HEX.muted, fill: { color: HEX.soft } } : { color: HEX.navy };
  return [{ text: j.jam, options: { ...o, bold: true } }, { text: j.kode || "", options: { ...o, bold: true } },
    { text: j.judul, options: o }, { text: String(j.menit), options: o }];
}));
s.addTable(rows, { x: 0.6, y: 1.3, w: 12.1, colW: [1.0, 0.9, 9.3, 0.9], fontSize: 11, fontFace: THEME.bodyFontFace,
  rowH: 0.24, border: { type: "solid", pt: 0.5, color: HEX.line }, margin: [0.02, 0.08, 0.02, 0.08], valign: "middle" });

s = pres.addSlide({ masterName: "ISI", sectionTitle: "Pembuka" });
s.addText("Alur uang — di mana tiap skenario terjadi", { placeholder: "title" });
gambar(s, "src/ppt/alur/peta_uang.png", pngSize(path.join(HERE, "alur", "peta_uang.png")), { x: 0.6, y: 1.35, w: 12.1, h: 4.4 },
  "peta-alur-uang");
s.addText("Setiap dokumen operasional otomatis membuat jurnal. Tugas keuangan: mencatat uang masuk/keluar, mencocokkannya dengan " +
  "dokumen dan bank, lalu memastikan buku seimbang sebelum laporan dan tutup buku.", { x: 0.6, y: 6.0, w: 12.1, h: 0.8,
  fontSize: 15, color: HEX.slate, margin: 0, isTextBox: true, objectName: "peta-alur-keterangan" });

if (D.nav_contoh.length) {
  s = pres.addSlide({ masterName: "ISI", sectionTitle: "Pembuka" });
  s.addText("Cara menuju layar", { placeholder: "title" });
  gambar(s, D.nav_contoh[0].img, [1366, 900], { x: 0.6, y: 1.35, w: 8.0, h: 5.4 }, "navigasi-contoh");
  [["①", "Klik nama grup di menu kiri", "Isinya terbuka (mis. KEUANGAN)."],
    ["②", "Klik menunya", "Mis. Piutang — layar terbuka di kanan."],
    ["③", "Pilih tab di atas layar", "Mis. Penagihan & Penerimaan."],
    ["⌕", "Atau ketik di Cari menu… (Ctrl+K)", "Ketik nama layar, tekan Enter."]].forEach(([n, j, t], i) => {
    const y = 1.45 + i * 1.32;
    s.addText(n, { shape: pres.shapes.OVAL, x: 8.95, y, w: 0.55, h: 0.55, fill: { color: i < 3 ? HEX.red : HEX.slate },
      color: "FFFFFF", fontSize: 16, bold: true, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: `nav-${i}-no` });
    s.addText([{ text: j, options: { bold: true, breakLine: true, color: HEX.navy } }, { text: t, options: { color: HEX.slate } }],
      { x: 9.7, y: y - 0.05, w: 3.05, h: 1.1, fontSize: 14, valign: "top", margin: 0, isTextBox: true, objectName: `nav-${i}-teks` });
  });
  s.addNotes("Tanda merah bernomor pada gambar navigasi di tiap skenario mengikuti urutan ini: ① grup, ② menu, ③ tab. " +
    "Jejak lokasi di kiri atas (Beranda › grup › menu) bisa diklik untuk kembali.");
}

s = pres.addSlide({ masterName: "ISI", sectionTitle: "Pembuka" });
s.addText("Peta menu keuangan", { placeholder: "title" });
s.addTable([[head("Menu"), head("Tab · dipakai untuk")]].concat(D.menu.map(([m, t]) => [
  { text: m, options: { bold: true, color: HEX.teal } }, { text: t, options: { color: HEX.navy } }])),
{ x: 0.6, y: 1.3, w: 12.1, colW: [3.6, 8.5], fontSize: 11.5, fontFace: THEME.bodyFontFace, border: { type: "solid", pt: 0.5,
  color: HEX.line }, margin: [0.03, 0.08, 0.03, 0.08], valign: "middle" });
s.addNotes("◆ = hanya Manajer. Finance melihat menu sesuai izinnya.");

s = pres.addSlide({ masterName: "ISI", sectionTitle: "Pembuka" });
s.addText("Akun & Kartu Peserta", { placeholder: "title" });
kartuTeks(s, { x: 0.6, y: 1.35, w: 5.6, h: 5.4, judul: "Akun & data latihan Anda", fill: HEX.tealSoft, color: HEX.teal, name: "akun",
  isi: ["Masuk: finance.latihNN@kainnusantara.id (NN = nomor Anda)", "Hanya PT Sukacita",
    "Pelanggan: Latihan NN · Toko Kain Peserta NN", "Pelanggan kedua: Latihan NN · Toko Kain Cicilan NN (F05) dan · Butik Sample (F14)",
    "Pemasok: Latihan NN · Pemasok Grey Peserta NN", "Cari dokumen Anda dengan nama itu — jangan memproses dokumen peserta lain"] });
s.addTable([[head("Kartu Peserta (nomor dokumen awal)"), head("Skenario")]].concat(D.kartu.map(([k, l, sk]) => [
  { text: l, options: { color: HEX.navy } }, { text: sk, options: { bold: true, color: HEX.teal } }])),
{ x: 6.5, y: 1.35, w: 6.2, colW: [4.7, 1.5], fontSize: 12, fontFace: THEME.bodyFontFace, border: { type: "solid", pt: 0.5,
  color: HEX.line }, margin: [0.03, 0.08, 0.03, 0.08], valign: "middle" });

s = pres.addSlide({ masterName: "ISI", sectionTitle: "Pembuka" });
s.addText("Cara mengetik nominal & menyimpan", { placeholder: "title" });
kartuTeks(s, { x: 0.6, y: 1.35, w: 5.95, h: 5.4, judul: "Nominal — semua benar", fill: HEX.tealSoft, color: HEX.teal, name: "tips-nominal",
  size: 16, isi: ["3.374.122,50  ·  3374122,5  ·  Rp 3.374.123  ·  3374123", "Selalu baca PRATINJAU di bawah kotak (mis. Rp 3.374.122,50)",
    "Baca kalimat konfirmasi sebelum [Ya, simpan] — nominal, rekening, PT", "Nominal minus, kosong, atau huruf ditolak dengan pesan"] });
kartuTeks(s, { x: 6.75, y: 1.35, w: 5.95, h: 5.4, judul: "Kebiasaan aman", fill: HEX.amberSoft, color: HEX.amber, name: "tips-aman", size: 16,
  isi: ["Klik tombol simpan SEKALI, tunggu pesan hasil", "Pakai tanggal hari ini", "Bayar tagihan: ketik nominal penuh (kurang ≤ Rp 5.000 menutup tagihan)",
    "Bila daftar tetap abu-abu, tekan muat ulang", "Tempel mutasi bank: salin langsung dari Excel"] });
s.addNotes("Hasil uji variasi isian: format nominal gaya Indonesia, Inggris, dengan 'Rp' dan spasi semuanya terbaca benar sesudah " +
  "perbaikan; klik ganda tidak membuat kwitansi/pembayaran ganda. Rinciannya di Lampiran A manual dan LAPORAN_AUDIT.md.");

s = pres.addSlide({ masterName: "ISI", sectionTitle: "Pembuka" });
s.addText("Istilah yang sering muncul", { placeholder: "title" });
s.addTable(D.istilah.map(([k, v]) => [{ text: k, options: { bold: true, color: HEX.teal } }, { text: v, options: { color: HEX.navy } }]),
  { x: 0.6, y: 1.3, w: 12.1, colW: [2.6, 9.5], fontSize: 13, fontFace: THEME.bodyFontFace, border: { type: "solid", pt: 0.5,
    color: HEX.line }, margin: [0.04, 0.08, 0.04, 0.08], valign: "middle" });

// ── 2. Skenario ────────────────────────────────────────────────────────────────────────────────────────────────────
const BAGIAN = { A: "Bagian A · Petugas Keuangan", B: "Bagian B · Manajer Keuangan" };
let bagianNow = "";
for (const sc of D.skenario) {
  const sec = `${sc.kode} · ${potong(sc.judul, 46)}`;
  if (sc.bagian !== bagianNow) {
    bagianNow = sc.bagian;
    pres.addSection({ title: BAGIAN[bagianNow] });
    s = pres.addSlide({ masterName: "JUDUL", sectionTitle: BAGIAN[bagianNow] });
    s.addText(BAGIAN[bagianNow], { placeholder: "title" });
    s.addText(bagianNow === "A" ? "Dikerjakan peserta dengan akun Finance masing-masing."
      : "Diperagakan pelatih dengan akun Manajer — tutup buku memengaruhi semua pengguna.", { placeholder: "body" });
  }
  pres.addSection({ title: sec });
  // a. pembuka skenario
  s = pres.addSlide({ masterName: "SEKSI", sectionTitle: sec });
  s.addText(`${sc.kode} · ${sc.judul}`, { placeholder: "title" });
  s.addText([
    { text: "Tujuan", options: { bold: true, breakLine: true, color: "CCFBF1", fontSize: 14 } },
    { text: potong(sc.tujuan, 300), options: { breakLine: true, paraSpaceAfter: 12 } },
    { text: "Kapan dipakai", options: { bold: true, breakLine: true, color: "CCFBF1", fontSize: 14 } },
    { text: potong(sc.kapan, 260), options: { breakLine: true, paraSpaceAfter: 12 } },
    { text: `${sc.peran} · ${sc.menit} menit · teruji di layar & buku: ${sc.uji.lulus}/${sc.uji.langkah} langkah lulus`,
      options: { fontSize: 14, color: "CCFBF1" } }], { placeholder: "body" });
  s.addNotes(`TUJUAN: ${sc.tujuan}\n\nKAPAN DIPAKAI: ${sc.kapan}\n\nDATA AWAL: ${sc.data_awal}`);
  // b. alur
  const alurPng = path.join(HERE, "alur", `${sc.kode}.png`);
  if (fs.existsSync(alurPng)) {
    s = pres.addSlide({ masterName: "LANGKAH", sectionTitle: sec });
    s.addText(`${sc.kode} · ${sc.judul}`, { placeholder: "kicker" });
    s.addText("Alur", { placeholder: "title" });
    gambar(s, path.relative(ROOT, alurPng), pngSize(alurPng), { x: 0.6, y: 1.45, w: 12.1, h: 4.3 }, `${sc.kode}-alur`);
    const cab = sc.alur.filter((a) => a.cabang).map((a) => `${a.label}: ${a.cabang}`);
    s.addText(sc.alur.map((a, i) => `${i + 1}. ${a.peran} — ${a.label}`).join("   ·   "), { x: 0.6, y: 5.95, w: 12.1, h: 0.85,
      fontSize: 12.5, color: HEX.slate, margin: 0, isTextBox: true, valign: "top", objectName: `${sc.kode}-alur-teks`, fit: "shrink" });
    s.addNotes(`Alur ${sc.kode}: ` + sc.alur.map((a, i) => `${i + 1}) ${a.peran}: ${a.label}${a.cabang ? ` (cabang: ${a.cabang})` : ""}`).join("; ")
      + (cab.length ? `\nCabang: ${cab.join("; ")}` : ""));
  }
  // c. navigasi (paling banyak 2 gambar per slide)
  const navs = sc.navigasi.filter((n) => n.img);
  for (let i = 0; i < navs.length; i += 2) {
    const pair = navs.slice(i, i + 2);
    s = pres.addSlide({ masterName: "LANGKAH", sectionTitle: sec });
    s.addText(`${sc.kode} · ${sc.judul}`, { placeholder: "kicker" });
    s.addText(navs.length > 2 ? `Cara menuju layar (${i / 2 + 1}/${Math.ceil(navs.length / 2)})` : "Cara menuju layar", { placeholder: "title" });
    if (pair.length === 1) {
      gambar(s, pair[0].img, pair[0].wh, { x: 0.6, y: 1.45, w: 8.4, h: 5.35 }, `${sc.kode}-nav-${i}`);
      s.addText([{ text: "Klik sesuai nomor merah:", options: { bold: true, breakLine: true, color: HEX.navy } },
        ...String(pair[0].menu).split("›").map((p, k, arr) => ({ text: `${circ[k] || k + 1}  ${p.trim()}`,
          options: { breakLine: k < arr.length - 1, color: HEX.red, bold: true, paraSpaceAfter: 8 } }))],
      { x: 9.3, y: 1.6, w: 3.45, h: 3.2, fontSize: 18, valign: "top", margin: 0, isTextBox: true, objectName: `${sc.kode}-nav-${i}-teks` });
    } else {
      pair.forEach((n, k) => {
        const box = { x: 0.6 + k * 6.15, y: 1.45, w: 5.95, h: 4.35 };
        gambar(s, n.img, n.wh, box, `${sc.kode}-nav-${i + k}`);
        s.addText(menuLangkah(n.menu), { x: box.x, y: 5.95, w: box.w, h: 0.8, fontSize: 14, bold: true, color: HEX.red,
          margin: 0, isTextBox: true, valign: "top", objectName: `${sc.kode}-nav-${i + k}-teks`, fit: "shrink" });
      });
    }
    s.addNotes(pair.map((n) => `Cara menuju layar: ${n.menu}`).join("\n"));
  }
  // d. satu slide per langkah
  const n = sc.langkah.length;
  for (const L of sc.langkah) {
    s = pres.addSlide({ masterName: "LANGKAH", sectionTitle: sec });
    s.addText(`${sc.kode} · ${sc.judul} · langkah ${L.no} dari ${n}`, { placeholder: "kicker" });
    s.addText(`${L.no}. ${L.judul}`, { placeholder: "title" });
    if (L.img) gambar(s, L.img, L.wh, { x: 0.6, y: 1.45, w: 8.35, h: 5.35 }, `${sc.kode}-L${L.no}-gambar`);
    const px = L.img ? 9.25 : 0.6, pw = L.img ? 3.5 : 12.1;
    lencana(s, L.peran || "Finance", px, 1.45, roleColor(L.peran), `${sc.kode}-L${L.no}-peran`);
    s.addText(L.menu, { x: px, y: 1.88, w: pw, h: 0.5, fontSize: 11, color: HEX.muted, margin: 0, isTextBox: true, valign: "top",
      objectName: `${sc.kode}-L${L.no}-menu`, fit: "shrink" });
    const blok = [{ text: "LAKUKAN", options: { bold: true, fontSize: 10.5, color: HEX.teal, charSpacing: 1, breakLine: true } },
      { text: potong(L.aksi, 210), options: { breakLine: true, paraSpaceAfter: 9, color: HEX.navy } }];
    if (L.isi) blok.push({ text: "ISI", options: { bold: true, fontSize: 10.5, color: HEX.teal, charSpacing: 1, breakLine: true } },
      { text: potong(L.isi, 130), options: { breakLine: true, paraSpaceAfter: 9, color: HEX.navy } });
    blok.push({ text: "YANG HARUS TERLIHAT", options: { bold: true, fontSize: 10.5, color: HEX.green, charSpacing: 1, breakLine: true } },
      { text: potong(L.hasil, L.isi ? 230 : 300), options: { color: HEX.navy } });
    s.addText(blok, { x: px, y: 2.45, w: pw, h: 4.35, fontSize: 14, valign: "top", margin: 0, isTextBox: true,
      objectName: `${sc.kode}-L${L.no}-teks`, fit: "shrink" });
    s.addNotes(`${sc.kode} langkah ${L.no} · ${L.peran}\nDI MANA: ${L.menu}\nLAKUKAN: ${L.aksi}` + (L.isi ? `\nISI: ${L.isi}` : "")
      + `\nYANG HARUS TERLIHAT: ${L.hasil}`);
  }
  // e. hasil di buku & kesalahan umum
  s = pres.addSlide({ masterName: "LANGKAH", sectionTitle: sec });
  s.addText(`${sc.kode} · ${sc.judul}`, { placeholder: "kicker" });
  s.addText("Hasil di buku & kesalahan umum", { placeholder: "title" });
  kartuTeks(s, { x: 0.6, y: 1.45, w: 5.95, h: 5.35, judul: "Cek di buku (jurnal & saldo)", fill: HEX.greenSoft, color: HEX.green,
    name: `${sc.kode}-buku`, isi: (sc.cek_buku.length ? sc.cek_buku : ["Tidak ada jurnal baru di skenario ini."]).map((x) => potong(x, 230)), size: 14 });
  kartuTeks(s, { x: 6.75, y: 1.45, w: 5.95, h: 5.35, judul: "Kesalahan yang sering terjadi", fill: HEX.amberSoft, color: HEX.amber,
    name: `${sc.kode}-salah`, isi: (sc.kesalahan_umum.length ? sc.kesalahan_umum : ["—"]).map((x) => potong(x, 230)), size: 14 });
  s.addNotes(`CEK BUKU:\n- ${sc.cek_buku.join("\n- ")}\n\nKESALAHAN UMUM:\n- ${sc.kesalahan_umum.join("\n- ")}` +
    (sc.catatan_pelatih ? `\n\nCATATAN PELATIH: ${sc.catatan_pelatih}` : ""));
}

// ── 2b. Dokumen yang terbit ───────────────────────────────────────────────────────────────────────────────────────
if ((D.dokumen || []).length) {
  const SECD = "Dokumen yang terbit";
  pres.addSection({ title: SECD });
  s = pres.addSlide({ masterName: "JUDUL", sectionTitle: SECD });
  s.addText("Dokumen yang terbit", { placeholder: "title" });
  s.addText("Setiap dokumen dicetak dari data latihan, lalu isinya (nomor, tanggal, PT, barang, DPP, PPN, total, terbilang) dicocokkan " +
    "dengan transaksi. Pengaturan naskah dokumen diuji: ubah → tercetak → dikembalikan.", { placeholder: "body" });
  const HASIL = { lulus: ["Lulus", HEX.green], diperbaiki: ["Diperbaiki & diuji ulang", HEX.green], keputusan: ["Perlu keputusan pemilik", HEX.amber] };
  for (const d of D.dokumen) {
    s = pres.addSlide({ masterName: "LANGKAH", sectionTitle: SECD });
    s.addText("Dokumen yang terbit", { placeholder: "kicker" });
    s.addText(d.judul, { placeholder: "title" });
    gambar(s, d.img, d.wh, { x: 0.6, y: 1.45, w: 5.7, h: 5.35 }, `dok-${d.judul}`);
    const [hl, hc] = HASIL[d.hasil] || [d.hasil || "—", HEX.slate];
    s.addText([
      { text: "CARA MENCETAK", options: { bold: true, fontSize: 10.5, color: HEX.teal, charSpacing: 1, breakLine: true } },
      { text: potong(d.cara_cetak, 220), options: { breakLine: true, paraSpaceAfter: 10, color: HEX.navy } },
      { text: "YANG DICEK", options: { bold: true, fontSize: 10.5, color: HEX.teal, charSpacing: 1, breakLine: true } },
      { text: potong(d.dicek, 330), options: { breakLine: true, paraSpaceAfter: 10, color: HEX.navy } },
      { text: "HASIL AUDIT", options: { bold: true, fontSize: 10.5, color: hc, charSpacing: 1, breakLine: true } },
      { text: hl, options: { bold: true, color: hc } }],
    { x: 6.65, y: 1.45, w: 6.05, h: 5.35, fontSize: 14, valign: "top", margin: 0, isTextBox: true, objectName: `dok-${d.judul}-teks`,
      fit: "shrink" });
    s.addNotes(`${d.judul}\nCARA MENCETAK: ${d.cara_cetak}\nYANG DICEK: ${d.dicek}\nHASIL: ${hl}` + (d.catatan ? `\nCATATAN: ${d.catatan}` : ""));
  }
}

// ── 3. Penutup ─────────────────────────────────────────────────────────────────────────────────────────────────────
pres.addSection({ title: "Penutup" });
s = pres.addSlide({ masterName: "ISI", sectionTitle: "Penutup" });
s.addText("Semua skenario sudah diuji di layar & di buku", { placeholder: "title" });
s.addTable([[head("Kode"), head("Skenario"), head("Hasil uji")]].concat(D.skenario.map((x) => [
  { text: x.kode, options: { bold: true, color: HEX.teal } }, { text: x.judul, options: { color: HEX.navy } },
  { text: `${x.uji.lulus}/${x.uji.langkah} lulus`, options: { bold: true, color: x.uji.ok ? HEX.green : HEX.red } }])),
{ x: 0.6, y: 1.3, w: 12.1, colW: [0.9, 9.4, 1.8], fontSize: 11, fontFace: THEME.bodyFontFace, rowH: 0.27,
  border: { type: "solid", pt: 0.5, color: HEX.line }, margin: [0.02, 0.08, 0.02, 0.08], valign: "middle" });
s.addNotes("Tiap skenario dijalankan otomatis di browser dengan akun peran yang sama dengan peserta, lalu angkanya dicocokkan " +
  "dengan jurnal, saldo, dan status di server. Rincian temuan & perbaikan: LAPORAN_AUDIT.md.");
s = pres.addSlide({ masterName: "JUDUL", sectionTitle: "Penutup" });
s.addText("Tanya jawab & evaluasi", { placeholder: "title" });
s.addText("Isi lembar evaluasi di manual. Temuan layar atau angka yang berbeda: catat nomor dokumen + tangkapan layar, " +
  "serahkan ke pelatih.", { placeholder: "body" });

(async () => {
  await pres.writeFile({ fileName: OUT });
  if (SKILL) {
    const { applyTheme } = require(path.join(SKILL, "scripts", "apply_theme.js"));
    await applyTheme(OUT, THEME);
  }
  console.log("PPTX:", OUT);
})();
