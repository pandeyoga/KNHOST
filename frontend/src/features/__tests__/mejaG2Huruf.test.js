/**
 * Meja gelombang 2 (A7): huruf & warna panel yang dipakai ulang di meja.
 * Kelima berkas memakai skala huruf baku (text-fs-*) dan token warna kn-*.
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
// baseline hex per berkas sebelum konversi (diukur 25 Nov 2026)
const BERKAS = {
  "sales_admin/VerifyOrderDialog.jsx": 28,
  "sales_admin/OrderPreviewCard.jsx": 30,
  "sales_admin/FulfillmentDecisionDialog.jsx": 12,
  "sales_admin/FulfillmentLineCard.jsx": 26,
  "finance/payments/PaymentVarianceDialog.jsx": 39,
};
const baca = (rel) => fs.readFileSync(path.join(ROOT, rel), "utf8");

describe.each(Object.entries(BERKAS))("%s", (rel, hexAwal) => {
  const src = baca(rel);

  test("tanpa ukuran huruf mentah text-[Npx]", () => {
    expect(src.match(/text-\[\d/g) || []).toEqual([]);
  });

  test("jumlah hex turun dari baseline", () => {
    const hex = (src.match(/#[0-9a-fA-F]{3,8}\b/g) || []).length;
    expect(hex).toBeLessThan(hexAwal);
  });

  test("tanpa uppercase pada label (label kolom 12/600 tanpa huruf besar)", () => {
    expect(src).not.toMatch(/\buppercase\b/);
  });
});
