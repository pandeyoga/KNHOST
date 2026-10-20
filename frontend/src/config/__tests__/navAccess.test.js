// FE-03 (review 2026-10-20) — menu peran kustom mengikuti katalog modul + struktur menu terbaru.
// Fixture dihasilkan dari backend (`backend/tests/fe03_access_fixture.py`); tes backend
// `test_fe03_access_catalog.py` menjaga fixture tetap sama dengan katalog.
import fixture from "./fixtures/access_nav_fixture.json";
import { buildNavGroups, hubTabsForRole } from "../navigationConfig";
import { registerDynamicRoles, setPreviewRoleNav } from "../roles";

const menu = (role) => {
  const out = {};
  for (const g of buildNavGroups(role, { showComingSoon: false })) {
    const items = g.type === "group" ? g.items : [g];
    out[g.groupId || g.id] = Object.fromEntries(items.map((it) => [it.id, it.hub ? hubTabsForRole(it.hub, role).map((t) => t.view) : []]));
  }
  return out;
};

beforeAll(() => {
  registerDynamicRoles([...fixture,
    { id: "cr_interco_hide_akuntansi", label: "x", custom: true, base_role: "",
      nav: { add: fixture.find((r) => r.id === "cr_interco").nav.add, remove: ["akuntansi"] } }]);
});

test("Interco penuh: induk Akuntansi muncul dengan transaksi Interco + Retur Antar-PT saja", () => {
  const m = menu("cr_interco");
  expect(Object.keys(m.akuntansi)).toEqual(["interco-transactions"]);
  expect(m["returns-hub"]["returns-hub"]).toEqual(["interco-returns"]);   // tab retur pelanggan/supplier tidak ikut
  expect(m.pembelian).toBeUndefined();                                     // hub Hutang tanpa tab = tidak jadi pintu mati
});

test("Akuntansi penuh: Buku Besar, Laporan, Tutup Buku, Buka Periode, Posting Gagal", () => {
  const m = menu("cr_accounting");
  expect(Object.keys(m.akuntansi)).toEqual(expect.arrayContaining(["ledger", "fin-reports", "closing", "period-unlock", "posting-failures"]));
  expect(m.akuntansi.ledger).toEqual(["general-ledger", "chart-of-accounts"]);
  expect(m.akuntansi["tax-hub"]).toBeUndefined();
});

test("Operasi Gudang penuh: tab Barang Masuk/Keluar & hub RFID", () => {
  const m = menu("cr_warehouse_ops");
  expect(m.gudang["wms-operations"]).toEqual(expect.arrayContaining(["operations", "goods-receipts", "wms-outbound", "qc-inspection"]));
  expect(m.gudang["rfid-hub"].length).toBeGreaterThan(0);
});

test("QC kustom: hanya tab QC & Inspeksi di Operasi Gudang", () => {
  expect(menu("cr_qc").gudang["wms-operations"]).toEqual(["qc-inspection"]);
});

test("Turunan Manager tanpa Akuntansi: menu akuntansi dicabut, sisanya tetap", () => {
  const m = menu("cr_manager_no_accounting");
  ["ledger", "fin-reports", "closing", "period-unlock"].forEach((id) => expect((m.akuntansi || {})[id]).toBeUndefined());
  expect(m.akuntansi["interco-transactions"]).toBeDefined();
});

test("Induk yang disembunyikan eksplisit tetap tertutup walau anaknya sah", () => {
  expect(menu("cr_interco_hide_akuntansi").akuntansi).toBeUndefined();
});

test("Pratinjau editor peran = menu akun nyata", () => {
  for (const r of fixture) {
    setPreviewRoleNav({ inherit: r.base_role || null, add: r.nav.add, remove: r.nav.remove });
    expect(menu("__preview")).toEqual(menu(r.id));
  }
  setPreviewRoleNav(null);
});

test("Peran bawaan tidak mendapat grup baru dari aturan anak; pintu hub tanpa tab hilang", () => {
  expect(menu("sales").keuangan).toBeUndefined();
  expect(menu("sales_admin")["meja-peran"]).toBeUndefined();
  ["md", "md_quality", "sample_admin"].forEach((r) => expect((menu(r).gudang || {})["wms-operations"]).toBeUndefined());
  expect(menu("admin").akuntansi["interco-transactions"]).toBeDefined();
});
