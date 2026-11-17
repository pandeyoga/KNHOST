// K-FIN-01 (keputusan pemilik 17 Nov 2026 malam, kata-kata asli: "untuk sekarang finance juga memiliki akses yang sama
// dengan manager dan jangan dipisah") — di layar, peran bawaan Finance menjangkau SEMUA menu, tab, dan alamat Manajer, dan
// gerbang nama peran lama (`roleIs`/`roleSatisfies`, registry) memperlakukan Finance seperti Manajer. Dihitung dari
// rancangan menu + izin server (`access_builtin_fixture.json`, generator `backend/tests/fe03_access_fixture.py`), jadi
// menu/tab Manajer yang lahir kemudian ikut diuji tanpa daftar.
import builtin from "./fixtures/access_builtin_fixture.json";
import { HUB_TABS, NAV_STRUCTURE, buildNavGroups, hubTabsForRole, resolveDeepLinkTarget } from "../navigationConfig";
import { ROLE_NAV, ROLE_REGISTRY, ROLE_SETARA, categoryOf, roleIs, roleSatisfies, setAccessContext } from "../roles";
import { listAliases } from "../viewAliases";

const login = (role) => setAccessContext({
  role, permissions: builtin.permissions[role] || {}, view_resources: builtin.view_resources, hidden_views: [],
  view_actions: builtin.view_actions,
});
afterEach(() => setAccessContext(null));

function alamat() {
  const ids = new Set();
  Object.values(HUB_TABS).flat().forEach((t) => ids.add(t.view));
  NAV_STRUCTURE.forEach((e) => {
    if (e.type === "standalone") { ids.add(e.id); if (e.view) ids.add(e.view); if (e.hub) ids.add(e.hub); }
    else {
      ids.add(e.groupId);
      (e.items || []).forEach((i) => { if (i.type === "heading") return; ids.add(i.id); if (i.view) ids.add(i.view); if (i.hub) ids.add(i.hub); });
    }
  });
  listAliases().forEach((a) => ids.add(a.from));
  return [...ids].filter(Boolean).sort();
}

/** Menu bentuk Sidebar: ["grup › menu › tab", …]. */
function menu(role) {
  const out = [];
  for (const g of buildNavGroups(role, { showComingSoon: false })) {
    const items = g.type === "group" ? g.items : [g];
    for (const it of items) {
      const tabs = it.hub ? hubTabsForRole(it.hub, role).map((t) => t.view) : [""];
      tabs.forEach((t) => out.push(`${g.groupId || g.id} › ${it.id} › ${t}`));
    }
  }
  return out;
}

test("registry: Finance mewarisi menu Manajer, lintas PT, kategori pengawas; setara satu arah", () => {
  expect(ROLE_NAV.finance.inherit).toBe("manager");
  expect(ROLE_REGISTRY.finance.crossEntity).toBe(true);
  expect(ROLE_REGISTRY.finance.rank).toBe(2);   // peringkat tetap — setara lewat ROLE_SETARA
  expect(ROLE_SETARA).toEqual({ finance: ["manager"] });
  expect(categoryOf("finance")).toBe("pengawas");
  expect(roleIs("finance", ["admin", "manager"])).toBe(true);
  expect(roleIs("manager", ["finance"])).toBe(false);
  expect(roleIs("sales_admin", ["manager"])).toBe(false);
  expect(roleSatisfies("finance", "manager")).toBe(true);
  expect(roleSatisfies("finance", "admin")).toBe(false);
  expect(roleSatisfies("sales_admin", "manager")).toBe(false);
});

test("izin bawaan (fixture server): Finance memegang setiap pasangan Manajer", () => {
  const f = builtin.permissions.finance;
  const kurang = Object.entries(builtin.permissions.manager)
    .flatMap(([res, acts]) => acts.filter((a) => !(f[res] || []).includes(a)).map((a) => `${res}.${a}`));
  expect(kurang).toEqual([]);
});

describe.each([["rancangan menu", false], ["izin server", true]])("jangkauan (%s)", (_n, server) => {
  test("setiap alamat yang sampai untuk Manajer sampai untuk Finance, ke layar yang sama", () => {
    const beda = [];
    for (const id of alamat()) {
      if (server) login("manager");
      const m = resolveDeepLinkTarget(id, "manager");
      if (!m) continue;
      if (server) login("finance");
      const f = resolveDeepLinkTarget(id, "finance");
      if (!f || f.view !== m.view) beda.push(`${id}: manajer ${m.view}, finance ${f ? f.view : "(tidak sampai)"}`);
    }
    expect(beda).toEqual([]);
  });

  test("setiap menu & tab Manajer tampil untuk Finance", () => {
    if (server) login("manager");
    const mgr = menu("manager");
    if (server) login("finance");
    const fin = new Set(menu("finance"));
    expect(mgr.length).toBeGreaterThan(50);
    expect(mgr.filter((x) => !fin.has(x))).toEqual([]);
  });
});

test("contoh layar khas Manajer terbuka untuk Finance (izin server)", () => {
  login("finance");
  for (const v of ["approval-inbox", "my-desk", "closing", "general-ledger", "hr-payroll-runs", "contra-bons",
    "settings-cfg-finance", "approval-rules", "hr-org-units"]) {
    expect([v, resolveDeepLinkTarget(v, "finance")?.view]).toEqual([v, v]);
  }
});
