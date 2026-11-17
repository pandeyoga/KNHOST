// K-SDM-01 (keputusan pemilik 17 Nov 2026: "SDM/HR itu dipegang finance juga") — Finance mengerjakan SDM & penggajian.
// Izin bawaan dari `access_builtin_fixture.json` (generator `backend/tests/fe03_access_fixture.py` =
// `permissions_config.KSDM01_DEFAULT_PAIRS`), overlay menu `ROLE_NAV.finance` (roles.js). Pemisahan tugas: Finance
// menyiapkan & memposting gaji, Manajer mengesahkan & membatalkan; struktur organisasi tetap Admin/Manajer.
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
  test("SDM: lihat, tambah, ubah, data pribadi, kehadiran, aturan gaji — tanpa hapus, struktur organisasi, pengaturan umum", () => {
    expect([...p.hr].sort()).toEqual(["create", "manage_attendance", "manage_payroll", "update", "view", "view_pii"]);
  });
  test("Penggajian: siapkan, posting, bayar — sahkan & batalkan tetap Manajer (pemisahan tugas)", () => {
    expect([...p.payroll].sort()).toEqual(["create", "pay", "post"]);
    expect(builtin.permissions.manager.payroll).toEqual(expect.arrayContaining(["approve", "void"]));
  });
});

describe("K-SDM-01 — menu Finance", () => {
  test("SDM › Karyawan, Kehadiran, Penggajian (Proses Gaji, Setoran & Pajak, Komponen & Masukan), Kinerja & Insentif", () => {
    const m = menu("finance");
    expect(m.hrd).toEqual({
      "hr-people": ["hr-employees"],
      "hr-attendance-hub": ["hr-attendance", "hr-leave", "hr-overtime"],
      "hr-payroll-hub": ["hr-payroll-runs", "hr-payroll-remittances", "hr-pay-components"],
      "hr-kpi-hub": ["incentive-capaian", "incentive-sheets", "incentive-setup"],
    });
  });
  test("Pengaturan › SDM: Aturan SDM & Penggajian, Shift & Lokasi Absen, Kalender Libur (tanpa Mesin Absen)", () => {
    expect(menu("finance")["settings-hub"]["settings-hr"]).toEqual(["settings-cfg-hr", "hr-attendance-setup", "hr-holidays"]);
  });
  test("Struktur Organisasi & Lacak Lapangan tidak dibuka (tetap Admin/Manajer)", () => {
    login("finance");
    expect(resolveDeepLinkTarget("hr-org-units", "finance")).toBeNull();
    expect(resolveDeepLinkTarget("hr-live-tracking", "finance")).toBeNull();
    expect(resolveDeepLinkTarget("hr-payroll-runs", "finance")).toMatchObject({ view: "hr-payroll-runs", navId: "hr-payroll-hub" });
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
