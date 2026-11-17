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
  view_actions: builtin.view_actions,   // PR-T5 — syarat aksi menu meja peran (sama dengan respons login)
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

/**
 * Pintu MATI yang sengaja ditutup izin server: id yang di baseline "sampai" menurut rancangan menu, tetapi server
 * TIDAK PERNAH melayani layar itu untuk peran tsb. Satu baris per keputusan + alasan.
 *  · Fase 4 · R5 — sales › Lot & Silsilah: seluruh `/api/lots*` dijaga `field_visibility.lot` (middleware), sales tanpa
 *    izin itu → layar berbunyi "Registri LOT tidak tersedia untuk peran Anda". Sumber izin tab kini `field_visibility`
 *    (`access_modules.VIEW_RESOURCE_OVERRIDES`), jadi tab disembunyikan; rancangan `hubTabs` tidak diubah.
 *  · KP-T9 — manajer › Peran & Hak Akses (`permission-matrix`): dulu alias tersembunyi yang membuka layar Badan Usaha &
 *    Akses pada bagian Peran — bagian itu sudah disaring izin `permission` (PR-T6) sehingga manajer (tanpa izin itu)
 *    mendarat di bagian Badan Usaha. Kini tab sendiri milik modul Peran & Hak Akses (`view_resources` = permission).
 */
const SERVER_GATED = { sales: ["inventory-lots"], manager: ["permission-matrix"] };
// FIX-1 (audit B1b UI-48) — pencabutan sah yang tercatat di roleReach.test.js (ROLE_REACH_REMOVALS).
const REMOVED = { warehouse_admin: ["my-desk"], sales_admin: ["my-desk"] };
// MN-T1 — id menu/hub yang kini mendarat di tab pertama lain di hub yang sama (tercatat di roleReach.test.js
// `ROLE_REACH_RELANDED`); layar lamanya tetap diperiksa terjangkau.
// KM-T2 — tab pertama SDM › Kinerja & Insentif kini Capaian (`incentive-capaian`).
// K-FIN-01 — Finance mewarisi menu Manajer: hub yang dulu hanya berisi satu tab Finance kini mendarat di tab pertama.
const RELANDED = { manager: { "hr-kpi-hub": "incentive-capaian" },
  finance: { "cash-bank": "bank-accounts", "products-pricing": "md-products", "wms-operations": "operations" } };

test("R5: Lot & Silsilah tersembunyi untuk sales (tanpa field_visibility.lot), tetap untuk gudang & manajer", () => {
  expect(builtin.view_resources["inventory-lots"]).toEqual(["field_visibility"]);
  login("sales");
  expect(resolveDeepLinkTarget("inventory-lots", "sales")).toBeNull();
  for (const role of ["warehouse", "manager"]) {
    login(role);
    expect(resolveDeepLinkTarget("inventory-lots", role)).toMatchObject({ view: "inventory-lots" });
  }
});

describe.each(BUILTIN.filter((r) => r !== "admin"))("peran %s dengan izin server", (role) => {
  test("setiap alamat yang dulu sampai (baseline) masih sampai — izin server tidak memblokir pintu rancangan", () => {
    login(role);
    const lost = [];
    const gated = new Set([...(SERVER_GATED[role] || []), ...(REMOVED[role] || [])]);
    const relanded = RELANDED[role] || {};
    for (const [id, view] of Object.entries(baseline.roles[role] || {})) {
      if (gated.has(id)) continue;
      const t = resolveDeepLinkTarget(id, role);
      if (relanded[id]) {
        if (t?.view !== relanded[id] || resolveDeepLinkTarget(view, role)?.view !== view) lost.push(`${id} → ${t?.view} (tercatat ${relanded[id]})`);
        continue;
      }
      const ok = new Set([view, aliasTarget(view), aliasTarget(id)]);
      if (!t) lost.push(`${id} → (tidak sampai; dulu ${view})`);
      else if (!ok.has(t.view)) lost.push(`${id} → ${t.view} (dulu ${view})`);
    }
    expect(lost).toEqual([]);
  });
});
