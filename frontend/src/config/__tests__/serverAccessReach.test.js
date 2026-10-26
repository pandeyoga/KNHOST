// Fase 3 · P8 — JANGKAUAN PERAN BAWAAN DENGAN IZIN SERVER (temuan koordinator setelah P7).
//
// `roleReach.test.js` menguji rancangan menu TANPA konteks akses. Di aplikasi nyata `App.js` memanggil
// `setAccessContext(user)` dengan izin efektif + `view_resources` dari server (`routers/auth._my_nav`): menu/tab yang
// modul pembukanya (katalog `backend/access_modules.py`) tak satu pun berizin DISEMBUNYIKAN. Karena itu id grup baru
// `settings-hub` yang hanya milik modul Admin memblokir SELURUH grup Pengaturan untuk Admin Sales (Kebijakan Retur) —
// tak terlihat oleh uji tanpa izin server. Fixture `access_builtin_fixture.json` dibuat generator backend
// (`backend/tests/fe03_access_fixture.py`; `test_fe03_access_catalog.py` menjaga kesamaannya dengan server).
import builtin from "./fixtures/access_builtin_fixture.json";
import baseline from "./fixtures/role_reach_baseline.json";
import { buildNavGroups, hubTabsForRole, resolveDeepLinkTarget } from "../navigationConfig";
import { ROLE_IDS, setAccessContext } from "../roles";
import { aliasTarget } from "../viewAliases";

const BUILTIN = ROLE_IDS.filter((r) => !String(r).startsWith("cr_") && r !== "__preview");
const login = (role) => setAccessContext({
  role, permissions: builtin.permissions[role] || {}, view_resources: builtin.view_resources, hidden_views: [],
});
afterEach(() => setAccessContext(null));

const menu = (role) => {
  const out = {};
  for (const g of buildNavGroups(role, { showComingSoon: false })) {
    const items = g.type === "group" ? g.items : [g];
    out[g.groupId || g.id] = Object.fromEntries(items.map((it) => [it.id, it.hub ? hubTabsForRole(it.hub, role).map((t) => t.view) : []]));
  }
  return out;
};

test("fixture memuat izin semua peran bawaan", () => {
  expect(BUILTIN.filter((r) => !builtin.permissions[r])).toEqual([]);
});

test("Admin Sales: Pengaturan › Penjualan › Kebijakan Retur & Gudang & Mutu › Master Grade Mutu tetap terbuka", () => {
  login("sales_admin");
  const s = menu("sales_admin")["settings-hub"];
  expect(s).toBeDefined();
  expect(s["settings-sales"]).toEqual(["return-policies"]);
  expect(s["settings-warehouse"]).toEqual(["grade-master"]);
  expect(resolveDeepLinkTarget("return-policies", "sales_admin")).toMatchObject({ navId: "settings-sales", view: "return-policies" });
});

test("Admin Gudang: Pengaturan › Gudang & Mutu (Penerimaan & OCR, Master Grade Mutu)", () => {
  login("warehouse_admin");
  expect(menu("warehouse_admin")["settings-hub"]["settings-warehouse"]).toEqual(["settings-receiving-ocr", "grade-master"]);
});

test("Gudang: Kinerja Mitra Makloon (D-22) terbuka dengan izin server", () => {
  login("warehouse");
  expect(menu("warehouse").pembelian["purchase-orders"]).toContain("makloon-claim-recap");
});

describe.each(BUILTIN.filter((r) => r !== "admin"))("peran %s dengan izin server", (role) => {
  test("setiap alamat yang dulu sampai (baseline) masih sampai — izin server tidak memblokir pintu rancangan", () => {
    login(role);
    const lost = [];
    for (const [id, view] of Object.entries(baseline.roles[role] || {})) {
      const t = resolveDeepLinkTarget(id, role);
      const ok = new Set([view, aliasTarget(view), aliasTarget(id)]);
      if (!t) lost.push(`${id} → (tidak sampai; dulu ${view})`);
      else if (!ok.has(t.view)) lost.push(`${id} → ${t.view} (dulu ${view})`);
    }
    expect(lost).toEqual([]);
  });
});
