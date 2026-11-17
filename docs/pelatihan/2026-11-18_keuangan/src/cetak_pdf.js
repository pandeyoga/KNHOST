// Cetak HTML panduan → PDF A4 (Chromium/Playwright) dengan nomor halaman di kaki.
//   node cetak_pdf.js <masuk.html> <keluar.pdf> <ID dokumen>
const { chromium } = require("playwright");
const path = require("path");

(async () => {
  const [src, out, docId] = process.argv.slice(2);
  const b = await chromium.launch({ args: ["--no-proxy-server"] });
  const page = await b.newPage();
  await page.goto("file://" + path.resolve(src), { waitUntil: "load" });
  await page.emulateMedia({ media: "print" });
  await page.pdf({
    path: out, format: "A4", printBackground: true, preferCSSPageSize: true, displayHeaderFooter: true,
    headerTemplate: "<span></span>",
    footerTemplate: `<div style="font:7pt Arial;color:#64748B;width:100%;padding:0 12mm;display:flex;justify-content:space-between">
      <span>ERP Kain Nusantara · Pelatihan Keuangan · ${docId || ""}</span>
      <span>Hal. <span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`,
    margin: { top: "13mm", bottom: "14mm", left: "12mm", right: "12mm" },
  });
  await b.close();
})();
