// PR-T7 — tombol dan panggilan data di layar mengikuti izin, bukan nama peran (docs/blueprint/unit/PR-T7.md).
// Uji komponen lapis B: U5 (canCurrent tanpa konteks), U6 (prodPerms dari izin), U7/U8 (tab CRM), U9 (Tanya KN), dan
// panggilan kerangka aplikasi tabel 2 (Keep & Pending, Profil Saya, Pusat Persetujuan). Uji jalan peramban (U10–U15) =
// lapis A, terpisah.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    patch: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
// Pustaka radix/cmdk tidak termuat di lingkungan uji ini — diganti elemen polos.
jest.mock("../../components/KNSelect", () => {
  const S = (p) => <select data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />;
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/ui/dropdown-menu", () => {
  const P = ({ children }) => <div>{children}</div>;
  return { DropdownMenu: P, DropdownMenuContent: P, DropdownMenuItem: P, DropdownMenuLabel: P,
    DropdownMenuSeparator: () => null, DropdownMenuTrigger: P };
});
// Isi tab CRM tidak diuji di sini (memanggil API & memuat pemilih bawaan) — cukup kerangka tabnya.
jest.mock("../crm/CustomerList", () => () => null);
jest.mock("../crm/CollectionWorklist", () => () => null);
jest.mock("../crm/CreditOverridesPanel", () => () => null);
jest.mock("../crm/LeadsPipeline", () => () => null);
jest.mock("../crm/OmnichannelInteractions", () => () => null);
// Kartu Profil Saya memanggil endpoint sendiri — di luar uji ini.
jest.mock("../hr/AttendanceView", () => ({ STATUS_PILL: {}, fmtTime: () => "", fmtMin: () => "" }));
jest.mock("../hr/MyPayslipCard", () => ({ MyPayslipCard: () => null }));
jest.mock("../hr/MyLeaveCard", () => ({ MyLeaveCard: () => null }));
jest.mock("../hr/MyKpiCard", () => ({ MyKpiCard: () => null }));
jest.mock("../hr/MyDesignerKpiSection", () => ({ __esModule: true, default: () => null, showMyDesignerKpi: () => false }));
jest.mock("../incentive/MyIncentiveCard", () => () => null);   // KM-T5 — kartu insentif memanggil endpoint sendiri

import { canCurrent, registerDynamicRoles, setAccessContext } from "../../config/roles";
import { prodPerms } from "../production/ProductionParts";
import CrmView from "../crm/CrmView";
import { HUB_TABS, hubTabsForRole } from "../../config/navigationConfig";
import { AskKnButton } from "../../components/AskKnButton";
import KeepPendingPanel from "../sales_admin/KeepPendingPanel";
import EmployeeSelfService from "../hr/EmployeeSelfService";
import { loadInbox } from "../approvals/approvalInboxData";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(el); });
  await flush();
  return host;
}
const calledPaths = () => mockGet.mock.calls.map((c) => String(c[0]).replace(/^\/api/, ""));

beforeEach(() => {
  mockGet.mockReset();
  mockGet.mockImplementation(() => Promise.resolve({ data: {} }));
  setAccessContext(null);
  localStorage.clear();
});
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  document.body.innerHTML = "";
  registerDynamicRoles([]);
});

describe("U5 — canCurrent tanpa konteks izin", () => {
  test("konteks belum dimuat, peran bukan Admin → tidak", () => {
    setAccessContext(null);
    expect(canCurrent("accounting", "view")).toBe(false);
    setAccessContext({ role: "manager" });   // akun tanpa izin termuat
    expect(canCurrent("accounting", "view")).toBe(false);
  });
  test("peran Admin → boleh; izin termuat → mengikuti izin", () => {
    setAccessContext({ role: "admin" });
    expect(canCurrent("accounting", "view")).toBe(true);
    setAccessContext({ role: "cr_tagih", permissions: { ar: ["view"] } });
    expect(canCurrent("ar", "view")).toBe(true);
    expect(canCurrent("accounting", "view")).toBe(false);
  });
});

describe("U6 — prodPerms dari izin", () => {
  test("{production: [view, create]} → hanya Buat WO", () => {
    const p = prodPerms({ production: ["view", "create"] });
    expect(p.createWo).toBe(true);
    expect([p.manageBom, p.release, p.complete, p.cancel]).toEqual([false, false, false, false]);
  });
  test("peran kustom tanpa peran dasar dengan semua aksi Produksi → semua tombol", () => {
    const p = prodPerms({ production: ["view", "manage_bom", "create", "release", "complete", "cancel"] });
    expect(Object.values(p)).toEqual([true, true, true, true, true]);
  });
});

// MN-T1 — sub-tab CRM "Persetujuan Kredit" & "Skema (Arsip)" kini tab hub sendiri (Keuangan › Piutang › Kredit & Plafon,
// SDM › Kinerja & Insentif › Skema (Arsip)); CRM tinggal tiga sub-tab. Gerbang izin PR-T7 TETAP, pindah tempat:
// Skema = sumber izin `sales_force` (katalog akses `VIEW_RESOURCE_OVERRIDES`), memutus kredit = `credit_override.approve`
// (tombol di CreditOverridesPanel — diuji `mnt1Pembungkus.test.js`; daftarnya kini dibaca pemegang `customer.view`).
describe("U7/U8 — tab bekas CRM dari izin (MN-T1: kini tab hub)", () => {
  const crm = (user) => {
    const html = renderToStaticMarkup(<CrmView currentUser={user} selectedEntity="ent_ksc" />);
    return { kredit: html.includes('data-testid="crm-tab-approvals"'), skema: html.includes('data-testid="crm-tab-schemes"') };
  };
  const NAV = ["keuangan", "ar-aging", "credit-overrides", "hrd", "hr-kpi-hub"];
  const tabHub = (role, permissions) => {
    setAccessContext({ role, permissions, view_resources: BUILTIN.view_resources, hidden_views: [], view_actions: BUILTIN.view_actions });
    return { kredit: hubTabsForRole("ar-aging", role).some((t) => t.view === "credit-overrides"),
             // KM-T3 — "Skema (Arsip)" tab tersembunyi; KM-T5 — layar lamanya dihapus: jenjang komisi kini bagian "Komisi
             // otomatis (cara lama)" di Target & Aturan (alias `incentive-schemes` → `incentive-setup`), gerbang izin
             // `sales_force` di dalam bagian itu (uji `kmt5KartuSales.test.js`). Yang diuji di sini: tidak ada lagi tab
             // Skema di hub mana pun.
             skema: Object.values(HUB_TABS).flat().some((t) => t.view === "incentive-schemes") };
  };
  // CR-T5 — tab Kredit & Plafon kini daftar kerja kredit: syarat tampil `credit_profile.view` (dulu `customer.view`,
  // MN-T1); `customer.view` saja tidak lagi membukanya.
  test("U7 peran kustom tanpa peran dasar + credit_profile.view + credit_override.approve → tab Kredit & Plafon, tanpa Skema", () => {
    registerDynamicRoles([{ id: "cr_tagih", custom: true, base_role: "", label: "Staf Penagihan Uji", nav: { add: NAV, remove: [] } }]);
    const perms = { customer: ["view"], credit_profile: ["view"], credit_override: ["approve"] };
    expect(crm({ role: "cr_tagih", permissions: perms })).toEqual({ kredit: false, skema: false });
    expect(tabHub("cr_tagih", perms)).toEqual({ kredit: true, skema: false });
    expect(tabHub("cr_tagih", { customer: ["view"], credit_override: ["approve"] })).toEqual({ kredit: false, skema: false });
  });
  test("U8 peran kustom berdasar Manajer dengan izin {customer: [view]} → Skema & Kredit & Plafon tidak ada", () => {
    registerDynamicRoles([{ id: "cr_mgr", custom: true, base_role: "manager", label: "Manajer Kosong", nav: { add: NAV, remove: [] } }]);
    expect(tabHub("cr_mgr", { customer: ["view"] })).toEqual({ kredit: false, skema: false });
    expect(tabHub("cr_mgr", { customer: ["view"], credit_profile: ["view"] })).toEqual({ kredit: true, skema: false });
    // CR-T3 (digabung) — pembaca izin kredit saja tetap membuka tabnya (daftar izin kredit, tanpa antrean).
    expect(tabHub("cr_mgr", { credit_override: ["view"] })).toEqual({ kredit: true, skema: false });
  });
  test("Manajer bawaan (izin bawaan) tetap melihat Kredit & Plafon; Skema (Arsip) tidak lagi tab (KM-T5)", () => {
    expect(tabHub("manager", BUILTIN.permissions.manager)).toEqual({ kredit: true, skema: false });
    expect(crm({ role: "manager", permissions: BUILTIN.permissions.manager })).toEqual({ kredit: false, skema: false });
  });
});

describe("U9 — tombol Tanya KN dari izin ai.view", () => {
  const masuk = (user) => { setAccessContext(user); localStorage.setItem("kn_user", JSON.stringify(user)); };
  const html = () => renderToStaticMarkup(<AskKnButton type="customer" id="cust_1" label="Toko A" />);
  test("peran kustom dengan {ai: [view]} → tampil", () => {
    masuk({ role: "cr_ai", permissions: { ai: ["view"] } });
    expect(html()).toContain('data-testid="ask-kn-customer"');
  });
  test("Manajer tanpa izin ai → tidak tampil", () => {
    masuk({ role: "manager", permissions: { customer: ["view"] } });
    expect(html()).toBe("");
  });
});

describe("Tabel 2 — panggilan kerangka aplikasi dijaga izin", () => {
  test("Keep & Pending: tanpa order.verify/order.view → tidak memanggil dan tidak menggambar", async () => {
    setAccessContext({ role: "cr_tagih", permissions: { ar: ["view", "create"], customer: ["view"], approval: ["view"] } });
    const host = await mount(<KeepPendingPanel selectedEntity="ent_ksc" />);
    expect(calledPaths()).not.toContain("/sales/keep-pending");
    expect(host.innerHTML).toBe("");
  });
  test("Keep & Pending: dengan order.view → memanggil", async () => {
    setAccessContext({ role: "sales", permissions: { order: ["view"] } });
    await mount(<KeepPendingPanel selectedEntity="ent_ksc" />);
    expect(calledPaths()).toContain("/sales/keep-pending");
  });
  test("Profil Saya: akun tanpa employee_id → tidak memanggil /hr/employees/me dan memberi petunjuk", async () => {
    const host = await mount(<EmployeeSelfService currentUser={{ id: "u1", role: "cr_tagih", employee_id: "" }} />);
    expect(calledPaths()).not.toContain("/hr/employees/me");
    expect(host.textContent).toContain("Akun ini belum ditautkan ke data karyawan. Minta Admin menautkannya di Akun & Akses.");
  });
  test("Profil Saya: akun tertaut → memanggil /hr/employees/me", async () => {
    mockGet.mockImplementation(() => Promise.resolve({ data: { id: "emp_1", name: "Rina", allowances: [] } }));
    await mount(<EmployeeSelfService currentUser={{ id: "u1", role: "sales", employee_id: "emp_1" }} />);
    expect(calledPaths()).toContain("/hr/employees/me");
  });
  test("Pusat Persetujuan: hanya kategori yang izin lihatnya dipegang yang dipanggil; sisanya bukan 'belum lengkap'", async () => {
    // Server tiruan: kategori di luar izin peran → 403 (seperti hasil uji jalan audit butir C3).
    // CR-T3 — daftar izin kredit kini dijaga `credit_override.view` (dulu `customer.view`).
    const izin = { ar: ["view", "create"], customer: ["view"], approval: ["view"], credit_override: ["view"] };
    const boleh = ["/approvals/queue", "/approvals/backlog", "/credit-overrides"];
    mockGet.mockImplementation((url) => (boleh.includes(String(url).replace(/^\/api/, ""))
      ? Promise.resolve({ data: [] }) : Promise.reject(Object.assign(new Error("403"), { response: { status: 403 } }))));
    const res = await loadInbox(izin);
    expect(calledPaths().sort()).toEqual([...boleh].sort());
    expect(res.unavailable).toEqual([]);
  });
});

// ── Tabel 3 #1/#2 (rincian sample) dan #24 (aplikasi HP) ───────────────────────────────────────────────────────────
import { sampleButtonPerms } from "../rnd/SampleDetailPanel";
import { mobileAppKind, isSalesAdminLayout } from "../mobile/mobileLayout";

describe("#1/#2 — tombol rincian sample dari izin + bendera server", () => {
  const ALL = ["view", "create", "submit", "assess", "decide", "manage", "pic_decide", "override_fail"];
  test("Tanpa Acuan dengan semua aksi R&D + caps server → semua tombol kerja", () => {
    const b = sampleButtonPerms({ rnd: ALL }, { caps: { pick_winner: true, approve_spec: true } }, ["labdip"]);
    expect([b.canSubmit, b.canAssess, b.canDecide, b.canPic, b.canOverride, b.canCancel, b.canEdit,
      b.canApproveSpecBtn, b.canReleaseBtn, b.mayPickWinner]).toEqual(Array(10).fill(true));
  });
  test("berdasar MD dengan R&D 'Lihat saja' → tidak ada tombol (dulu Nilai/Putuskan/Batalkan tampil lewat peran dasar)", () => {
    registerDynamicRoles([{ id: "cr_md_lihat", custom: true, base_role: "md", label: "MD Lihat" }]);
    const b = sampleButtonPerms({ rnd: ["view"] }, { caps: { pick_winner: true, approve_spec: true } }, ["labdip"]);
    expect([b.canSubmit, b.canAssess, b.canDecide, b.canPic, b.canCancel, b.canEdit, b.canApproveSpecBtn])
      .toEqual(Array(7).fill(false));
  });
  test("aksi per jenis uji: assess_<jenis> untuk SEMUA jenis sample (= _require_typed server)", () => {
    expect(sampleButtonPerms({ rnd: ["view", "assess_labdip"] }, {}, ["labdip"]).canAssess).toBe(true);
    expect(sampleButtonPerms({ rnd: ["view", "assess_labdip"] }, {}, ["labdip", "handfeel"]).canAssess).toBe(false);
  });
  test("boleh memilih pemenang = bendera server caps.pick_winner, bukan daftar peran di pengaturan", () => {
    expect(sampleButtonPerms({ rnd: ALL }, { caps: { pick_winner: false, approve_spec: true } }).mayPickWinner).toBe(false);
    expect(sampleButtonPerms({ rnd: ALL }, {}).mayPickWinner).toBe(false);
  });
});

describe("#24 — aplikasi HP dari halaman awal peran", () => {
  const LAMA = { admin: "ops", manager: "ops", sales_admin: "sales", finance: "ops", sales: "sales", warehouse: "warehouse",
    designer: "ops", driver: "driver", md: "md", warehouse_admin: "warehouse", sample_admin: "ops", md_quality: "ops", qc: "ops" };
  test("13 peran bawaan → aplikasi yang sama dengan pemilihan lama", () => {
    for (const [r, app] of Object.entries(LAMA)) expect([r, mobileAppKind(r)]).toEqual([r, app]);
    expect(isSalesAdminLayout("sales_admin")).toBe(true);
    expect(isSalesAdminLayout("sales")).toBe(false);
  });
  test("peran kustom: ikut halaman awal peran dasar; tanpa peran dasar → aplikasi umum", () => {
    registerDynamicRoles([
      { id: "cr_adm_sales", custom: true, base_role: "sales_admin", label: "Admin Sales 2" },
      { id: "cr_kurir", custom: true, base_role: "driver", label: "Kurir" },
      { id: "cr_bebas", custom: true, base_role: "", label: "Tanpa Acuan" },
    ]);
    expect([mobileAppKind("cr_adm_sales"), isSalesAdminLayout("cr_adm_sales")]).toEqual(["sales", true]);
    expect(mobileAppKind("cr_kurir")).toBe("driver");
    expect(mobileAppKind("cr_bebas")).toBe("ops");
    expect(mobileAppKind("peran_tak_dikenal")).toBe("ops");
  });
});

// ── U14 (lapis B, padanan statik uji jalan) — 13 peran bawaan dengan izin bawaan: daftar tombol lama (nama peran) vs
// baru (izin endpoint). Manajer tidak boleh kehilangan tombol; tombol yang hilang hanya bila server memang menolak. ──
import BUILTIN from "../../config/__tests__/fixtures/access_builtin_fixture.json";
import { can as canPerm } from "../../config/roles";

describe("U14 (lapis B) — peran bawaan tidak kehilangan tombol yang diizinkan server", () => {
  const P = BUILTIN.permissions;
  const ok = (r, m, a) => canPerm(P[r], m, a);
  const caps = { caps: { pick_winner: true, approve_spec: true } };
  // [gerbang, daftar peran lama (HEAD), gerbang baru]
  const GATES = [
    ["sample.kirim", ["admin", "manager", "warehouse", "md"], (r) => sampleButtonPerms(P[r], caps).canSubmit],
    ["sample.nilai", ["admin", "manager", "md"], (r) => sampleButtonPerms(P[r], caps).canAssess],
    ["sample.putuskan", ["admin", "manager", "md"], (r) => sampleButtonPerms(P[r], caps).canDecide],
    ["sample.pic", ["admin", "manager", "md"], (r) => sampleButtonPerms(P[r], caps).canPic],
    ["sample.paksa", ["admin", "manager"], (r) => sampleButtonPerms(P[r], caps).canOverride],
    ["sample.ubah", ["admin", "manager", "sales", "md"], (r) => sampleButtonPerms(P[r], caps).canEdit],
    ["sample.batal", ["admin", "manager", "md"], (r) => sampleButtonPerms(P[r], caps).canCancel],
    ["dsr.putuskan", ["admin", "manager", "md"], (r) => ok(r, "design_request", "decide")],
    ["dsr.tugaskan", ["admin", "manager", "md"], (r) => ok(r, "design_request", "assign")],
    ["dsr.batal", ["admin", "manager", "md"], (r) => ok(r, "design_request", "cancel")],
    ["dsr.kerjakan", ["admin", "manager", "designer"], (r) => ok(r, "design_request", "deliver")],
    ["dsr.buat", ["admin", "manager", "sales_admin", "md"], (r) => ok(r, "design_request", "create")],
    ["dsr.rapor", ["admin", "manager"], (r) => ok(r, "design_request", "report")],
    ["produksi", ["admin", "manager", "warehouse"], (r) => prodPerms(P[r]).createWo && prodPerms(P[r]).release && prodPerms(P[r]).complete],
    ["produksi.bom+batal", ["admin", "manager"], (r) => prodPerms(P[r]).manageBom && prodPerms(P[r]).cancel],
    ["dokumen.tandatangan", ["admin", "manager", "sales", "warehouse"], (r) => ok(r, "esign", "sign")],
    ["dokumen.wa", ["admin", "manager"], (r) => ok(r, "document_delivery", "manage")],
    ["crm.tab-kredit", ["admin", "manager"], (r) => ok(r, "credit_override", "approve")],
    ["crm.tab-skema", ["admin", "manager"], (r) => ok(r, "sales_force", "view")],
    ["crm.pindah-sales", ["admin", "manager"], (r) => ok(r, "sales_force", "assign")],
    ["crm.set-target", ["admin", "manager"], (r) => ok(r, "sales_force", "update")],
    ["tutup-buku.buka-kembali", ["admin"], (r) => ok(r, "accounting", "manage") && ok(r, "accounting", "reopen")],
    ["tanya-kn", ["admin", "manager", "sales_admin", "finance", "md", "warehouse_admin", "sales"], (r) => ok(r, "ai", "view")],
  ];
  const ROLES = Object.keys(P);
  const hilang = [];
  for (const [g, lama, baru] of GATES) for (const r of ROLES) if (lama.includes(r) && !baru(r)) hilang.push(`${r}:${g}`);
  test("13 peran bawaan termuat dari katalog", () => { expect(ROLES.length).toBe(13); });
  test("Manajer & Admin: tidak ada tombol yang hilang", () => {
    expect(hilang.filter((x) => x.startsWith("manager:") || x.startsWith("admin:"))).toEqual([]);
  });
  test("tombol yang hilang hanya yang pasti ditolak server (izinnya tidak dipegang peran itu)", () => {
    // MD memegang design_request.decide tetapi tidak .cancel → `POST /design-requests/{id}/cancel` = 403 (koreksi "A").
    expect(hilang).toEqual(["md:dsr.batal"]);
    expect(ok("md", "design_request", "cancel")).toBe(false);
  });
});
