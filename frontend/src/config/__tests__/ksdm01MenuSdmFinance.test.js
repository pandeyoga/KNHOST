// K-SDM-01 (keputusan pemilik 17 Nov 2026: "SDM/HR itu dipegang finance juga") — Finance mengerjakan SDM & penggajian.
// Izin bawaan dari `access_builtin_fixture.json` (generator `backend/tests/fe03_access_fixture.py` =
// `permissions_config.KSDM01_DEFAULT_PAIRS`), overlay menu `ROLE_NAV.finance` (roles.js). Pemisahan tugas: Finance
// menyiapkan & memposting gaji, Manajer mengesahkan & membatalkan; struktur organisasi tetap Admin/Manajer.
// K-FIN-01 (pemilik 17 Nov 2026 malam: "untuk sekarang finance juga memiliki akses yang sama dengan manager dan jangan
// dipisah") MENGGANTIKAN pemisahan itu: Finance kini memegang izin SDM & gaji Manajer dan mewarisi menunya.
import builtin from "./fixtures/access_builtin_fixture.json";
import { buildNavGroups, hubTabsForRole, resolveDeepLinkTarget } from "../navigationConfig";
import { setAccessContext } from "../roles";

const login = (role, perms = builtin.permissions[role] || {}) => setAccessContext({
  role, permissions: perms, view_resources: builtin.view_resources, hidden_views: [], view_actions: builtin.view_actions,
});
afterEach(() => setAccessContext(null));

const menu = (role, perms) => {
  login(role, perms);
  const out = {};
  for (const g of buildNavGroups(role, { showComingSoon: false })) {
    const items = g.type === "group" ? g.items : [g];
    out[g.groupId || g.id] = Object.fromEntries(items.map((it) => [it.id, it.hub ? hubTabsForRole(it.hub, role).map((t) => t.view) : []]));
  }
  return out;
};

describe("K-SDM-01 — izin bawaan Finance", () => {
  const p = builtin.permissions.finance;
  test("SDM: K-SDM-01 + (K-FIN-01) hapus karyawan & struktur organisasi seperti Manajer — tanpa pengaturan SDM umum", () => {
    expect([...p.hr].sort()).toEqual(["create", "delete", "manage_attendance", "manage_org", "manage_payroll", "update",
      "view", "view_pii"]);
    expect(builtin.permissions.manager.hr.every((a) => p.hr.includes(a))).toBe(true);
  });
  test("Penggajian: siapkan, posting, bayar + (K-FIN-01) sahkan & batalkan seperti Manajer", () => {
    expect([...p.payroll].sort()).toEqual(["approve", "create", "pay", "post", "void"]);
    expect(builtin.permissions.manager.payroll).toEqual(expect.arrayContaining(["approve", "void"]));
  });
});

describe("K-SDM-01 — menu Finance", () => {
  test("SDM (K-FIN-01): menu SDM Finance = menu SDM Manajer (Karyawan, Kehadiran, Penggajian, Kinerja & Insentif, …)", () => {
    const m = menu("finance");
    expect(m.hrd).toEqual(menu("manager").hrd);
    expect(m.hrd["hr-payroll-hub"]).toEqual(expect.arrayContaining(["hr-payroll-runs", "hr-payroll-remittances",
      "hr-pay-components"]));
  });
  test("Pengaturan › SDM (K-FIN-01) = Manajer", () => {
    expect(menu("finance")["settings-hub"]["settings-hr"]).toEqual(menu("manager")["settings-hub"]["settings-hr"]);
  });
  test("Struktur Organisasi & Lacak Lapangan (K-FIN-01): terbuka seperti untuk Manajer", () => {
    for (const role of ["manager", "finance"]) {
      login(role);
      expect(resolveDeepLinkTarget("hr-org-units", role)).not.toBeNull();
      expect(resolveDeepLinkTarget("hr-payroll-runs", role)).toMatchObject({ view: "hr-payroll-runs", navId: "hr-payroll-hub" });
    }
    login("manager");
    const lacakManajer = !!resolveDeepLinkTarget("hr-live-tracking", "manager");
    login("finance");
    expect(!!resolveDeepLinkTarget("hr-live-tracking", "finance")).toBe(lacakManajer);
  });
  test("bukti-merah: Admin mencabut izin SDM Finance → Karyawan/Kehadiran/Proses Gaji tersembunyi, Setoran & Pajak tetap", () => {
    const tanpaHr = { ...builtin.permissions.finance };
    delete tanpaHr.hr;
    tanpaHr.payroll = ["pay"];
    const m = menu("finance", tanpaHr);
    expect(m.hrd["hr-people"]).toBeUndefined();
    expect(m.hrd["hr-attendance-hub"]).toBeUndefined();
    expect(m.hrd["hr-payroll-hub"]).toEqual(["hr-payroll-remittances"]);
    expect(m["settings-hub"]["settings-hr"]).toBeUndefined();
  });
});
