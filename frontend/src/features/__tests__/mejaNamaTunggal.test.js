// MEJA-8 — satu nama per meja (§5.1): menu = breadcrumb = judul.
import fs from "fs"; import path from "path";
import { PAGE_META, breadcrumbFor } from "../../config/navigationConfig";
import { HUB_TABS } from "../../config/hubTabs";

test.each([["sales-admin-desk", "Meja Admin Sales"], ["finance-desk", "Meja Keuangan"], ["md-desk", "Meja MD"],
  ["my-desk", "Meja Saya"], ["warehouse-admin-desk", "Meja Gudang"], ["sample-admin-desk", "Meja Sample"]])("%s → %s", (v, nama) => {
  expect(PAGE_META[v].title).toBe(nama);
});
test("breadcrumb Meja Keuangan = judul = tab hub", () => {
  expect(HUB_TABS["finance-tower"][0].label).toBe("Meja Keuangan");
  expect(breadcrumbFor("finance-desk", "finance-tower", "admin").slice(-1)[0]).toBe("Meja Keuangan");
});
test("tidak ada nama usang di kode layar (string & teks JSX; komentar diabaikan)", () => {
  const usang = /Meja Finance|Meja Admin Sample|Meja Admin Gudang|Perlu Tindakan/;
  const salah = [];
  const telusur = (d) => fs.readdirSync(d, { withFileTypes: true }).forEach((e) => {
    const p = path.join(d, e.name);
    if (e.isDirectory()) { if (e.name !== "__tests__") telusur(p); return; }
    if (!/\.(js|jsx)$/.test(e.name)) return;
    const kode = fs.readFileSync(p, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|\s)\/\/[^\n]*/g, "$1");
    if (usang.test(kode)) salah.push(path.relative(path.join(__dirname, "../.."), p));
  });
  telusur(path.join(__dirname, "../.."));
  expect(salah).toEqual([]);
});
