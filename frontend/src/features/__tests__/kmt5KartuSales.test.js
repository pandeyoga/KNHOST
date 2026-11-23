// KM-T5 — kartu "Capaian & Insentif Saya" dan pencabutan layar insentif lama (sisi layar tanpa peramban):
//  · U13: kartu dengan data U2 — "Insentif Bulanan — Okt 2026", "Rp 2.000.000", "Dibayar bersama gaji November 2026";
//    tanpa kata "Komisi"; angka dasar dari potret; penyesuaian; dibayar; target 0; kosong; memuat; galat; komisi otomatis;
//  · U14: CRM tanpa sub-tab Kinerja Sales / Skema (Arsip); hub Pengaturan › Penjualan dan SDM › Kinerja & Insentif tanpa
//    `incentive-rates`; id lama = alias (sales tidak mendapat pintu ke Capaian);
//  · U15 pengganti uji jalan: Beranda Sales PT Lembar Insentif → kartu tampil, "Komisi MTD" tidak; Profil Saya → kartu di
//    bawah slip hanya bila berisi; HP Target → kartu + komisi otomatis hanya untuk PT bermode otomatis;
//  · U16 pengganti uji jalan: kartu akrual komisi bulanan tampil di PT bermode bawaan, tidak di PT Lembar Insentif;
//    tombol akrual dengan konfirmasi yang menyebut nominal & PT. KA-9 — bagian "Komisi otomatis (cara lama)" dicabut
//    dari Target & Aturan: kartu akrual kini di tab Skema & Tarif (`IncentiveSchemeView`), alias `incentive-rates` /
//    `incentive-schemes` mengarah ke tab itu, dan catatan kartu sales tidak lagi menulis "sampai PT ini beralih".
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import MyIncentiveCard, { adaIsi, jamWib, persen, pilihanBulan } from "../incentive/MyIncentiveCard";
import IncentiveSchemeView from "../incentive/IncentiveSchemeView";
import { rencanaAkrual } from "../incentive/KartuAkrual";
import { komisiOtomatisJalan } from "../incentive/incentiveModes";
import SalesHome from "../home/SalesHome";
import EmployeeSelfService from "../hr/EmployeeSelfService";
import MobileCollectionTargets from "../sales/mobile/MobileCollectionTargets";
import CrmView from "../crm/CrmView";
import { HUB_TABS, resolveDeepLinkTarget } from "../../config/navigationConfig";
import { AppNavProvider } from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { setAccessContext } from "../../config/roles";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockConfirm = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), put: () => Promise.resolve({ data: {} }),
    patch: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: (...a) => mockConfirm(...a),
  askReason: () => Promise.resolve("alasan uji"),
  default: {},
}));
// Pustaka radix/cmdk tidak termuat di lingkungan uji ini — diganti elemen polos.
jest.mock("../../components/KNSelect", () => {
  const S = (p) => <select data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />;
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/KNDatePicker", () => () => null);
jest.mock("../../components/EntityScopeBanner", () => () => <div data-testid="scope" />);
jest.mock("../incentive/LegacySchemeEditor", () => () => <div data-testid="legacy-scheme" />);
// KA-9 — Pusat Pengaturan tertanam di Skema & Tarif tidak diuji di sini (suite kaSkemaTarif / Pengaturan).
jest.mock("../settings/config/SettingsHub", () => ({ useSettingsBrowser: () => ({ items: [] }), SettingsBrowser: () => null,
  SettingsNotice: () => null }));
jest.mock("../incentive/ArticleRatesTable", () => () => <div data-testid="rates-tree" />);
jest.mock("../sales_admin/KeepPendingPanel", () => () => null);
jest.mock("../home/HomeWaitingBoards", () => () => null);
jest.mock("../crm/CustomerList", () => () => null);
jest.mock("../crm/LeadsPipeline", () => () => null);
jest.mock("../crm/OmnichannelInteractions", () => () => null);
jest.mock("../crm/promiseUi", () => ({ PromiseFields: () => null, promiseError: () => "" }));
jest.mock("../hr/AttendanceView", () => ({ STATUS_PILL: {}, fmtTime: () => "", fmtMin: () => "" }));
jest.mock("../hr/MyPayslipCard", () => ({ MyPayslipCard: () => <div data-testid="slip-card" /> }));
jest.mock("../hr/MyLeaveCard", () => ({ MyLeaveCard: () => null }));
jest.mock("../hr/MyKpiCard", () => ({ MyKpiCard: () => null }));
jest.mock("../hr/MyDesignerKpiSection", () => ({ __esModule: true, default: () => null, showMyDesignerKpi: () => false }));
jest.mock("recharts", () => {
  const P = ({ children }) => <div>{children}</div>;
  return { LineChart: P, Line: () => null, XAxis: () => null, YAxis: () => null, CartesianGrid: () => null,
    Tooltip: () => null, ResponsiveContainer: P };
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView || function scrollIntoView() {};   // jsdom

const ENT = [{ id: "ent_kanda", legal_name: "CV Kanda Suka", short_name: "Kanda" }];
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const txt = (el) => (el?.textContent || "").replace(/ /g, " ");
async function settle() { for (let i = 0; i < 10; i += 1) await act(async () => {}); }
const klik = async (el) => { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await settle(); };
async function mount(node, { entity = "ent_kanda" } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(
      <EntityScopeProvider selectedEntity={entity} entities={ENT} canSwitch>
        <AppNavProvider role="manager" onOpenDocument={() => {}} onNavigateTo={() => {}}>{node}</AppNavProvider>
      </EntityScopeProvider>);
  });
  await settle();
  return host;
}
const dipanggil = () => mockGet.mock.calls.map((c) => String(c[0]).replace(/^\/api/, ""));

const POTRET = { target_sales: 800000000, omzet_bersih: 1000000000, target_collection: 750000000, uang_masuk: 700000000,
  realisasi_harga_pct: 86.2 };
const BARIS = (over = {}) => ({ component_name: "Insentif Bulanan", basis_label: "Okt 2026", amount: 2000000,
  is_adjustment: false, note: "", paid_run_number: "", snapshot: POTRET, ...over });
/** Jawaban `GET /api/incentive/me?period=2026-11` sesudah L1 disahkan (data U2). */
const KARTU = (over = {}) => ({
  period: "2026-11", entity_id: "ent_kanda", mode: "sheet",
  achievement: { target_sales: 900000000, omzet_bersih: 450000000, pct_omzet: 50.0, target_collection: 0, uang_masuk: 0,
    pct_pencairan: null, realisasi_harga_pct: 91.5, facts_as_of: "2026-11-05T03:00:00+00:00" },
  sheets: [{ sheet_number: "KANDA/LIN-00001", pay_period: "2026-11", status: "approved",
    lines: [BARIS(), BARIS({ component_name: "Insentif Triwulan", basis_label: "Triwulan III 2026", amount: 3000000 })] }],
  auto_commission: null, ...over,
});
const rute = (map) => mockGet.mockImplementation((url) => {
  const k = Object.keys(map).find((p) => String(url).includes(p));
  return k ? (map[k] instanceof Error ? Promise.reject(map[k]) : Promise.resolve({ data: map[k] })) : Promise.resolve({ data: {} });
});

beforeEach(() => { mockGet.mockReset(); mockPost.mockReset(); mockConfirm.mockReset(); document.body.innerHTML = ""; });

// ═══ U13 — kartu dengan data U2 ════════════════════════════════════════════════════════════════════════════════════
test("U13 kartu: baris lembar disahkan, dibayar bersama gaji November, tanpa kata Komisi", async () => {
  rute({ "/incentive/me": KARTU() });
  const host = await mount(<MyIncentiveCard period="2026-11" />);
  expect(mockGet).toHaveBeenCalledWith("/api/incentive/me", { params: { period: "2026-11" } });
  const t = txt(host);
  expect(txt(q(host, "my-incentive-title"))).toBe("Capaian & Insentif Saya — November 2026");
  expect(t).toContain("Insentif Bulanan — Okt 2026");
  expect(t).toContain("Rp 2.000.000");
  expect(t).toContain("Dibayar bersama gaji November 2026");
  expect(t).not.toMatch(/Komisi/);
  expect(txt(q(host, "my-incentive-sheet-0-total"))).toBe("Rp 5.000.000");
  expect(q(host, "my-incentive-sheet-0-pay").querySelector(".status-pill.status-done svg")).not.toBeNull();
  // capaian: "Rp … dari target Rp … (persen %)"; target 0 → "target belum diisi"; persen satu desimal berkoma
  expect(txt(q(host, "my-incentive-omzet"))).toBe("OmzetRp 450.000.000 dari target Rp 900.000.000 (50,0 %)");
  expect(txt(q(host, "my-incentive-uang"))).toBe("Uang masukRp 0, target belum diisi");
  expect(txt(q(host, "my-incentive-harga"))).toBe("Realisasi harga91,5 %");
  expect(txt(q(host, "my-incentive-asof"))).toMatch(/^Data per pukul 10[.:]00 WIB$/);
  expect(txt(q(host, "my-incentive-note"))).toBe("Nominal insentif diputuskan pimpinan dengan melihat capaian. Tidak ada rumus otomatis.");
  // angka dasar (potret) dibuka dari tautan "Angka dasar"
  expect(q(host, "my-incentive-sheet-0-line-0-snapshot")).toBeNull();
  await klik(q(host, "my-incentive-sheet-0-line-0-basis"));
  expect(txt(q(host, "my-incentive-sheet-0-line-0-snapshot"))).toBe(
    "Omzet Rp 1.000.000.000 / target Rp 800.000.000Uang masuk Rp 700.000.000 / target Rp 750.000.000Realisasi harga 86,2 %");
  // rupiah tidak patah: setiap nominal dalam span ber-`whitespace-nowrap`
  expect(q(host, "my-incentive-sheet-0-line-0-amount").className).toContain("whitespace-nowrap");
});

test("U13 kartu: lembar dibayar, penyesuaian negatif, kosong, memuat, galat, komisi otomatis", async () => {
  rute({ "/incentive/me": KARTU({ sheets: [{ sheet_number: "KANDA/LIN-00002", pay_period: "2026-12", status: "paid",
    lines: [BARIS({ amount: -500000, is_adjustment: true, note: "retur Oktober dikoreksi", paid_run_number: "KANDA/PAY-00008" })] }] }) });
  let host = await mount(<MyIncentiveCard period="2026-12" />);
  expect(txt(q(host, "my-incentive-sheet-0-pay"))).toBe("DibayarkanSudah dibayar (gaji Desember 2026)");
  expect(txt(q(host, "my-incentive-sheet-0-line-0-adj"))).toBe("Penyesuaian");
  expect(txt(host)).toContain("retur Oktober dikoreksi");
  expect(txt(q(host, "my-incentive-sheet-0-line-0-amount"))).toBe("-Rp 500.000");
  document.body.innerHTML = "";
  rute({ "/incentive/me": KARTU({ sheets: [] }) });
  host = await mount(<MyIncentiveCard period="2026-11" />);
  expect(txt(q(host, "my-incentive-sheets-empty"))).toBe("Belum ada insentif yang disahkan untuk Anda.");
  document.body.innerHTML = "";
  mockGet.mockImplementation(() => new Promise(() => {}));
  host = await mount(<MyIncentiveCard period="2026-11" />);
  expect(txt(q(host, "my-incentive-loading"))).toBe("Memuat capaian…");
  document.body.innerHTML = "";
  mockGet.mockImplementation(() => Promise.reject(Object.assign(new Error("x"), { response: { status: 500 } })));
  host = await mount(<MyIncentiveCard period="2026-11" />);
  expect(txt(q(host, "my-incentive-error"))).toMatch(/^Capaian belum bisa dimuat\..*Coba lagi/);
  document.body.innerHTML = "";
  rute({ "/incentive/me": KARTU({ mode: "accrue_then_settle", sheets: [], auto_commission: { mtd: 500000, projection_month_end: 1500000 } }) });
  host = await mount(<MyIncentiveCard period="2026-11" />);
  expect(txt(q(host, "my-incentive-auto"))).toBe("Komisi berjalan (hitungan otomatis)Rp 500.000");
  expect(txt(q(host, "my-incentive-note"))).toMatch(/Komisi berjalan dihitung otomatis dari tarif komisi PT ini\.$/);
  // KA-9 — PT "keduanya dibayar": catatan menyebut kedua sumber, bukan "sampai PT ini beralih"
  document.body.innerHTML = "";
  rute({ "/incentive/me": KARTU({ mode: "auto_and_sheet", sheets: [], auto_commission: { mtd: 500000, projection_month_end: 1500000 } }) });
  host = await mount(<MyIncentiveCard period="2026-11" />);
  expect(txt(q(host, "my-incentive-note"))).toMatch(/^PT ini membayar keduanya: komisi berjalan dihitung otomatis/);
  expect(txt(host)).not.toMatch(/beralih ke Lembar Insentif/);
});

test("pembantu kartu: pilihan bulan, persen, jam WIB, isi", () => {
  expect(pilihanBulan("2026-02", 3).map((o) => o.value)).toEqual(["2026-02", "2026-01", "2025-12", "2025-11"]);
  expect(pilihanBulan("2026-02", 0)[0].label).toBe("Februari 2026");
  expect([persen(93.3), persen(null), persen(125)]).toEqual(["93,3 %", "—", "125,0 %"]);
  expect(jamWib("2026-11-05T03:00:00+00:00")).toMatch(/^10[.:]00$/);
  expect(jamWib("")).toBe("");
  expect(adaIsi(KARTU({ sheets: [] }))).toBe(true);
  expect(adaIsi({ achievement: { target_sales: 0, omzet_bersih: 0, target_collection: 0, uang_masuk: 0 }, sheets: [] })).toBe(false);
});

// ═══ U14 — sub-tab & tab lama dicabut ══════════════════════════════════════════════════════════════════════════════
test("U14 CRM manajer tanpa Kinerja Sales / Skema (Arsip); hub tanpa incentive-rates; id lama = alias (KA-9: ke Skema & Tarif)", () => {
  setAccessContext({ role: "manager", permissions: {}, view_resources: {}, hidden_views: [], view_actions: {} });
  const html = renderToStaticMarkup(<CrmView currentUser={{ role: "manager", permissions: {} }} selectedEntity="ent_ksc" />);
  expect(html).not.toMatch(/Kinerja Sales|Skema \(Arsip\)/);
  expect(HUB_TABS["settings-sales"].map((t) => t.view)).not.toContain("incentive-rates");
  const kpi = HUB_TABS["hr-kpi-hub"];
  // KA-9 — + tab Skema & Tarif (`incentive-scheme`) sesudah Lembar Insentif.
  expect(kpi.map((t) => t.view)).toEqual(["incentive-capaian", "incentive-sheets", "incentive-scheme", "incentive-setup", "cs-kpi"]);
  expect(kpi.map((t) => t.label).join(" | ")).not.toMatch(/Kinerja Sales|Skema \(Arsip\)|Komisi Otomatis/);
  expect(Object.values(HUB_TABS).flat().some((t) => ["incentive-rates", "sales-performance", "incentive-schemes"].includes(t.view))).toBe(false);
  expect(resolveDeepLinkTarget("incentive-rates", "manager")).toMatchObject({ view: "incentive-scheme", navId: "hr-kpi-hub" });
  expect(resolveDeepLinkTarget("incentive-schemes", "admin")).toMatchObject({ view: "incentive-scheme", navId: "hr-kpi-hub" });
  expect(resolveDeepLinkTarget("sales-performance", "manager")).toMatchObject({ view: "incentive-capaian", navId: "hr-kpi-hub" });
  expect(resolveDeepLinkTarget("sales-performance", "sales")).toBeNull();   // tidak ada pintu baru ke Capaian
  expect(resolveDeepLinkTarget("hr-kpi-hub", "sales_admin")).toMatchObject({ view: "incentive-sheets" });
});

// ═══ U15 pengganti — Beranda Sales, Profil Saya, HP ═══════════════════════════════════════════════════════════════
const BERANDA = (over = {}) => ({ period: "2026-11", incentive_mode: "sheet", commission: null,
  target: { sales_amount: 0, sales_pct: 0 }, kpi: { total_sales: 1000, total_collected: 0, overdue_amount: 0 },
  history: [], customers: [], collections: [], recent_orders: [], waiting_boards: [], ...over });

test("U15 Beranda Sales PT Lembar Insentif: kartu Capaian & Insentif Saya tampil, Komisi MTD tidak", async () => {
  rute({ "/home/sales": BERANDA(), "/incentive/me": KARTU() });
  const host = await mount(<SalesHome token="t" user={{ id: "u1", role: "sales", name: "Andi" }} onNavigate={() => {}} />);
  expect(q(host, "sales-home-my-incentive")).not.toBeNull();
  expect(txt(q(host, "sales-home-my-incentive-title"))).toMatch(/^Capaian & Insentif Saya — /);
  expect(txt(host)).not.toMatch(/Komisi MTD|Tren Komisi|Rincian Komisi/);
  expect(q(host, "kpi-penjualan-mtd")).not.toBeNull();   // kartu lain tetap
});

test("U15 Beranda Sales PT bermode komisi otomatis: kartu lama tetap + kartu baru", async () => {
  rute({ "/home/sales": BERANDA({ incentive_mode: "accrue_then_settle", target: { amount: 0, achievement_pct: 0 },
    commission: { mtd_accrual: 500000, projection_month_end: 1500000, strategy: "per_sku", breakdown: [], base_amount: 0 } }),
  "/incentive/me": KARTU({ mode: "accrue_then_settle", auto_commission: { mtd: 500000, projection_month_end: 1500000 } }) });
  const host = await mount(<SalesHome token="t" user={{ id: "u1", role: "sales", name: "Citra" }} onNavigate={() => {}} />);
  expect(q(host, "kpi-komisi-mtd")).not.toBeNull();
  expect(txt(q(host, "sales-home-my-incentive-auto"))).toBe("Komisi berjalan (hitungan otomatis)Rp 500.000");
});

test("U15 Profil Saya: kartu di bawah slip bila berisi; tidak tampil bila kosong", async () => {
  const EMP = { id: "emp_1", name: "Andi", code: "EMP-1", allowances: [] };
  rute({ "/hr/employees/me": EMP, "/incentive/me": KARTU() });
  let host = await mount(<EmployeeSelfService currentUser={{ id: "u1", role: "sales", employee_id: "emp_1" }} />);
  const slip = q(host, "slip-card");
  const kartu = q(host, "ess-my-incentive");
  expect(kartu).not.toBeNull();
  expect(slip.compareDocumentPosition(kartu) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  document.body.innerHTML = "";
  rute({ "/hr/employees/me": EMP, "/incentive/me": KARTU({ sheets: [],
    achievement: { target_sales: 0, omzet_bersih: 0, target_collection: 0, uang_masuk: 0, pct_omzet: null } }) });
  host = await mount(<EmployeeSelfService currentUser={{ id: "u2", role: "warehouse", employee_id: "emp_2" }} />);
  expect(q(host, "ess-my-incentive")).toBeNull();
});

test("U15 HP Target: kartu versi HP; komisi otomatis dipanggil hanya untuk PT bermode otomatis", async () => {
  rute({ "/incentive/me": KARTU(), "/sales/my-rank": { rank: 1, total: 2, total_sales: 100 } });
  let host = await mount(<MobileCollectionTargets selectedEntity="ent_kanda" initialTab="targets" />);
  expect(txt(q(host, "m-ct-tab-targets"))).toBe("Target & Insentif");
  expect(q(host, "m-targets-card")).not.toBeNull();
  expect(q(host, "m-targets-card").className).toContain("m-card");
  expect(q(host, "m-targets-card-sheet-0-line-0-basis").className).toContain("btn-touch");   // tombol sentuh ≥ 48 px
  expect(txt(q(host, "m-targets-rank-value"))).toBe("#1 dari 2 sales");
  expect(dipanggil().some((u) => u.startsWith("/sales/commission"))).toBe(false);
  expect(host.querySelector('input[type="month"]')).toBeNull();
  document.body.innerHTML = "";
  mockGet.mockReset();
  rute({ "/incentive/me": KARTU({ mode: "accrue_then_settle", auto_commission: { mtd: 500000, projection_month_end: 1500000 } }),
    "/sales/commission-history": [], "/sales/commission": { total_incentive: 500000, kpi: {}, breakdown: [] },
    "/sales/my-rank": { rank: null, total: 2, total_sales: 0 } });
  host = await mount(<MobileCollectionTargets selectedEntity="ent_ksc" initialTab="targets" />);
  expect(dipanggil().some((u) => u.startsWith("/sales/commission"))).toBe(true);
  expect(txt(q(host, "m-targets-incentive"))).toContain("Rp 500.000");
});

// ═══ U16 pengganti — kartu akrual komisi bulanan menurut sakelar PT (KA-9: kini di tab Skema & Tarif) ═══════════
const TARGETS = (mode) => ({ period_type: "month", period: "2026-11", period_label: "November 2026", previous_period: "2026-10",
  entity_id: "ent_kanda", all_pt: false, items: [], roster: [], commission_mode: mode, commission_modes: { ent_kanda: mode },
  period_types: [] });

test("U16 Skema & Tarif: kartu akrual komisi tampil di PT bermode bawaan, tidak di PT Lembar Insentif", async () => {
  setAccessContext({ role: "manager", permissions: { incentive: ["view", "configure"], sales_force: ["view", "update", "post"] },
    view_resources: {}, hidden_views: [], view_actions: {} });
  rute({ "/incentive/targets": TARGETS("accrue_then_settle"), "/config/explain": { value: "per_sku" },
    "/sales/incentive/gl-status": { posted: false, amount: 0, estimate: 1250000, mode: "accrue_then_settle" } });
  mockConfirm.mockResolvedValue(true);
  mockPost.mockResolvedValue({ data: { created: true, message: "Akrual insentif 2026-11 diposting (JE KANDA/JE-1)." } });
  let host = await mount(<IncentiveSchemeView />);
  expect(q(host, "scheme-accrual-card")).not.toBeNull();
  expect(q(host, "rates-tree")).not.toBeNull();
  expect(q(host, "legacy-scheme")).toBeNull();                         // jenjang arsip hanya untuk achievement_tiered
  const tombol = q(host, "ins-accrual-post");
  expect(txt(tombol)).toMatch(/^Bukukan akrual komisi \S+ \d{4}$/);
  await klik(tombol);
  const arg = mockConfirm.mock.calls[0][0];
  expect(arg.message.replace(/\u00a0/g, " ")).toContain("Beban komisi Rp 1.250.000 dibukukan ke buku CV Kanda Suka");
  expect(mockPost.mock.calls[0][0]).toBe("/api/sales/incentive/post-gl");
  document.body.innerHTML = "";
  rute({ "/incentive/targets": TARGETS("sheet") });
  host = await mount(<IncentiveSchemeView />);
  expect(q(host, "scheme-accrual-card")).toBeNull();
  expect(q(host, "ins-accrual")).toBeNull();
});

test("U16 aturan komisi otomatis & tombol akrual", () => {
  expect(komisiOtomatisJalan("")).toBe(false);
  expect(komisiOtomatisJalan("sheet")).toBe(false);
  expect(komisiOtomatisJalan("off")).toBe(false);
  expect(komisiOtomatisJalan("pay_on_invoice")).toBe(true);
  expect(komisiOtomatisJalan("auto_and_sheet")).toBe(true);
  expect(rencanaAkrual({ posted: false, estimate: 0 }, "2026-11", true).alasan).toBe("Tidak ada komisi untuk dibukukan pada November 2026.");
  expect(rencanaAkrual({ posted: true, amount: 100, estimate: 100 }, "2026-11", true).alasan).toBe("Akrual komisi November 2026 sudah dibukukan.");
  expect(rencanaAkrual({ posted: true, amount: 100, estimate: 250 }, "2026-11", true)).toEqual(
    { label: "Bukukan koreksi akrual komisi November 2026", nilai: 150, alasan: "" });
  expect(rencanaAkrual({ posted: false, estimate: 9 }, "2026-11", false).alasan).toMatch(/^Membukukan akrual butuh akses/);
});
