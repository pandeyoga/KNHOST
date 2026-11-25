// MEJA-6 — kerangka meja (§5.1): satu kepala, ? di samping judul, tab Antrean/Pantau, urutan kartu, toast, muat ulang
// per kartu, muat ulang global, pemulihan tab & gulir (Review Focus #4).
// R4 (pengendali): Meja Keuangan TIDAK memakai tab di dalam tab hub — Pantau Keuangan = tab hub saudara
// `finance-desk-pantau`; `FinanceDesk` di dalam hub hanya menggambar tab yang dipilih hub.
import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";
import SalesAdminDesk from "../sales_admin/SalesAdminDesk";
import FinanceDesk from "../finance/FinanceDesk";
import RoleDesk from "../desks/RoleDesk";
import SampleAdminDesk from "../samples/SampleAdminDesk";
import { PageHelpProvider, PageHelpButton, usePageHelp } from "../../context/PageHelpContext";
import { MUAT_ULANG_EVENT, kirimMuatUlang } from "../../utils/refreshSignal";
import { orderDeskQueues, splitPantau, PANTAU_QUEUE_IDS } from "../sales_admin/deskQueueOrder";
import { DESK_GRID_CLASS } from "../desks/DeskFrame";
import { HUB_TABS, PAGE_META } from "../../config/navigationConfig";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockToast = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), defaults: { headers: { common: {} } } },
  API: "/api",
  setActiveEntity: () => {}, setAuthToken: () => {},
}));
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: (...a) => mockToast(...a) }));
jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid, className }) => (
    <select data-testid={tid} className={className} value={value ?? ""} onChange={(e) => onValueChange(e.target.value)}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>);
  return { __esModule: true, default: M, KNSelect: M };
});
jest.mock("../sales_admin/SoTrackerCard", () => () => <div data-testid="so-tracker-stub" />);
jest.mock("../sales_admin/KeepPendingPanel", () => () => <div data-testid="kp-stub" />);
jest.mock("../sales_admin/CustomerGradeRulesCard", () => () => <div data-testid="grade-stub" />);
jest.mock("../home/ReturnDeskSummaryCard", () => () => <div data-testid="return-desk-stub" />);
jest.mock("../sales_admin/VerifyOrderDialog", () => () => null);
jest.mock("../sales_admin/FulfillmentDecisionDialog", () => () => null);
jest.mock("../finance/payments/ReceivePaymentModal", () => () => null);

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const teks = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");
let roots = [];
async function mount(el) {
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host); roots.push(root);
  await act(async () => { root.render(el); }); await act(async () => {}); await act(async () => {});
  return host;
}
const klik = async (id) => act(async () => { q(id).dispatchEvent(new MouseEvent("click", { bubbles: true })); });
const lepasSemua = async () => { for (const r of roots) await act(async () => r.unmount()); roots = []; };
function routeGet(peta) {
  mockGet.mockImplementation((u) => {
    const k = Object.keys(peta).find((x) => u.includes(x));
    return Promise.resolve({ data: k ? peta[k] : [] });
  });
}
afterEach(async () => {
  await lepasSemua(); document.body.innerHTML = "";
  mockGet.mockReset(); mockPost.mockReset(); mockToast.mockReset();
  sessionStorage.clear();
});

const DESK = { queues: [
  { id: "perlu_verifikasi", label: "Perlu diperiksa", count: 0, rows: [] },
  { id: "siap_dikonfirmasi", label: "Ditahan", count: 1, oldest_age_days: 2, rows: [
    { ref_type: "sales_order", ref_id: "so7", number: "SO-7", title: "Toko T", value: 1, age_days: 2,
      action: "Lepas ke gudang", action_kind: "release", entity_id: "ent_ksc" }] },
  { id: "jatuh_tempo", label: "Jatuh tempo", count: 1, oldest_age_days: 9, rows: [
    { ref_type: "sales_order", ref_id: "so9", number: "SO-9", title: "Toko J", value: 5, age_days: 9, age_kind: "overdue",
      action: "Follow-up", action_kind: "open", entity_id: "ent_ksc" }] },
  { id: "menunggu_manajer", label: "Menunggu manajer", count: 0, rows: [] }],
  not_my_desk: ["Faktur Pajak keluaran", "Pencatatan uang masuk (kwitansi AR)"] };
const USER = { permissions: { order: ["view", "confirm"] } };

test("satu kepala: tanpa h2/kartu angka/'Paling lama'; ? berisi alur + bukan wewenang", async () => {
  routeGet({ "/sales-admin/desk": DESK });
  await mount(<PageHelpProvider><PageHelpButton /><SalesAdminDesk currentUser={USER} onOpenDocument={() => {}} /></PageHelpProvider>);
  expect(q("desk-title")).toBeNull(); expect(q("desk-metrics")).toBeNull();
  expect(q("desk-refresh")).toBeNull(); expect(q("desk-not-mine")).toBeNull();
  expect(document.body.textContent).not.toMatch(/Paling lama menunggu|Bukan wewenang meja ini/);
  await klik("page-help");
  expect(teks(q("page-help-text"))).toMatch(/periksa kelengkapan/);
  expect(teks(q("page-help-text"))).toMatch(/Bukan wewenang meja ini: Faktur Pajak keluaran · Pencatatan uang masuk/);
  expect(teks(q("page-help-text"))).not.toMatch(/Meja Finance/);
  expect(q("page-help").getAttribute("aria-label")).toBe("Tentang layar ini");
});

test("? halaman: dilepas saat meja dilepas; di luar provider tidak berbuat apa-apa", async () => {
  function Isi({ teksBantu }) { usePageHelp(<span>{teksBantu}</span>, "uji"); return null; }
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host); roots.push(root);
  await act(async () => { root.render(<PageHelpProvider><PageHelpButton /><Isi teksBantu="Bantuan A" /></PageHelpProvider>); });
  expect(q("page-help")).not.toBeNull();
  await act(async () => { root.render(<PageHelpProvider><PageHelpButton /></PageHelpProvider>); });
  expect(q("page-help")).toBeNull();                               // dilepas saat unmount
  await mount(<Isi teksBantu="Tanpa provider" />);                  // tidak melempar
  await mount(<PageHelpButton />);
  expect(q("page-help")).toBeNull();
});

test("urutan kartu: berisi paling mendesak dulu, lalu kosong; grid tidak meregang; menunggu_manajer hanya di Pantau", async () => {
  routeGet({ "/sales-admin/desk": DESK });
  await mount(<SalesAdminDesk currentUser={USER} onOpenDocument={() => {}} />);
  const ids = [...document.body.querySelectorAll('[data-testid^="desk-queue-"]')].map((e) => e.getAttribute("data-testid"));
  expect(ids).toEqual(["desk-queue-jatuh_tempo", "desk-queue-siap_dikonfirmasi", "desk-queue-perlu_verifikasi"]);
  expect(q("desk-antrean").firstElementChild.className).toContain("items-start");
  expect(q("so-tracker-stub")).toBeNull();
  await klik("desk-tabs-pantau");
  expect(q("desk-antrean")).toBeNull();                              // hanya panel aktif yang dirender
  expect(q("so-tracker-stub")).not.toBeNull(); expect(q("kp-stub")).not.toBeNull(); expect(q("grade-stub")).not.toBeNull();
  expect(q("desk-queue-menunggu_manajer")).not.toBeNull();
});

test("Pelacak SO di Pantau hanya dengan izin order.view (RoleDesk MD)", async () => {
  routeGet({ "/md/desk": { queues: [] } });
  await mount(<RoleDesk desk="md" currentUser={{ permissions: { design_request: ["view"] } }} onOpenDocument={() => {}} />);
  expect(q("md-desk-title")).toBeNull(); expect(q("md-desk-oldest-card")).toBeNull(); expect(q("md-desk-metrics")).toBeNull();
  expect(teks(q("md-desk-empty"))).toMatch(/untuk PT yang sedang Anda lihat/);
  await klik("md-desk-tabs-pantau");
  expect(q("so-tracker-stub")).toBeNull(); expect(teks(q("md-desk-pantau-empty"))).toContain("Tidak ada pantauan untuk meja ini.");
});

test("Gudang: kartu retur internal & Pelacak SO (izin) di Pantau", async () => {
  routeGet({ "/warehouse-admin/desk": { queues: [] } });
  await mount(<RoleDesk desk="warehouse_admin" currentUser={{ permissions: { wms: ["view"], order: ["view"] } }} onOpenDocument={() => {}} />);
  expect(q("return-desk-stub")).toBeNull();
  await klik("wh-desk-tabs-pantau");
  expect(q("return-desk-stub")).not.toBeNull(); expect(q("so-tracker-stub")).not.toBeNull();
});

test("Keuangan (R4): di dalam tab hub tanpa tab sendiri; Pantau = tab hub saudara berisi retur internal & Pelacak SO", async () => {
  routeGet({ "/finance/desk": { queues: [], not_my_desk: [] } });
  const user = { permissions: { payment_variance: ["decide"], order: ["view"] } };
  await mount(<FinanceDesk currentUser={user} selectedEntity="ent_ksc" />);
  expect(q("fin-desk-title")).toBeNull(); expect(q("fin-desk-summary")).toBeNull();
  expect(q("fin-desk-tabs")).toBeNull();                              // tidak ada tab tingkat ketiga
  expect(q("fin-desk-antrean")).not.toBeNull();
  expect(q("return-desk-stub")).toBeNull(); expect(q("so-tracker-stub")).toBeNull();
  await lepasSemua();
  mockGet.mockClear();
  await mount(<FinanceDesk currentUser={user} selectedEntity="ent_ksc" tab="pantau" />);
  expect(q("fin-desk-tabs")).toBeNull(); expect(q("fin-desk-antrean")).toBeNull();
  expect(q("return-desk-stub")).not.toBeNull(); expect(q("so-tracker-stub")).not.toBeNull();
  expect(mockGet.mock.calls.some(([u]) => u.includes("/finance/desk"))).toBe(false);   // Pantau tidak memuat antrean
});

test("R4: hub Beranda Keuangan punya tab 'Pantau' tepat sesudah tab meja; router & judul layar tersedia", () => {
  const views = HUB_TABS["finance-tower"].map((t) => t.view);
  expect(views.indexOf("finance-desk-pantau")).toBe(views.indexOf("finance-desk") + 1);
  const tab = HUB_TABS["finance-tower"].find((t) => t.view === "finance-desk-pantau");
  expect(tab.label).toBe("Pantau");
  expect(tab.roles).toEqual(HUB_TABS["finance-tower"].find((t) => t.view === "finance-desk").roles);
  expect(PAGE_META["finance-desk-pantau"]).toEqual(expect.objectContaining({ title: expect.any(String), kicker: expect.any(String) }));
  const router = fs.readFileSync(path.join(__dirname, "../../AppViewRouter.jsx"), "utf8");
  expect(router).toMatch(/activeView === "finance-desk-pantau" && \(\s*<FinanceDesk[^>]*tab="pantau"/);
  expect(router).not.toMatch(/"finance-desk", "warehouse-admin-desk"\]\.includes\(activeView\)/);
  // PageTabs hanya di DeskFrame; berkas meja Keuangan sendiri tidak memuatnya (penjaga INV-UI-14 tidak diakali).
  const fin = fs.readFileSync(path.join(__dirname, "../finance/FinanceDesk.jsx"), "utf8");
  expect(fin).not.toMatch(/PageTabs|tab-bar/);
  expect(fin).toMatch(/tabsInHub/);
});

test("aksi sukses: toast (bukan bilah puncak) dan hanya kartu terkait dimuat ulang", async () => {
  let lepasMuat;
  mockGet.mockResolvedValueOnce({ data: DESK }).mockImplementationOnce(() => new Promise((r) => { lepasMuat = r; }));
  mockPost.mockResolvedValue({ data: { released: true, order: { number: "SO-7", status: "confirmed" } } });
  await mount(<SalesAdminDesk currentUser={USER} onOpenDocument={() => {}} />);
  await klik("desk-action-so7");
  expect(mockPost).toHaveBeenCalledWith("/api/sales-orders/so7/release");
  expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: expect.stringContaining("SO-7") }));
  expect(q("desk-toast")).toBeNull();
  expect(q("desk-refreshing-siap_dikonfirmasi")).not.toBeNull();
  expect(q("desk-refreshing-jatuh_tempo")).toBeNull();
  expect(q("desk-queue-jatuh_tempo")).not.toBeNull();                 // halaman tidak dikosongkan
  await act(async () => lepasMuat({ data: DESK }));
  expect(q("desk-refreshing-siap_dikonfirmasi")).toBeNull();
});

test("Sample: aksi di tempat → toast + kartu terkait dimuat ulang", async () => {
  const SD = { queues: [{ id: "bayar_sampel", label: "Bayar", count: 1, oldest_age_days: 1, rows: [
    { ref_type: "sample_order", ref_id: "sos1", number: "SOS-1", title: "Butik", value: 10, age_days: 1,
      action: "Setujui bayar", action_kind: "approve_payment" }] },
    { id: "siap_gudang", label: "Siap", count: 1, oldest_age_days: 1, rows: [
      { ref_type: "sample_order", ref_id: "sos2", number: "SOS-2", title: "Butik 2", value: 10, age_days: 1,
        action: "Teruskan", action_kind: "confirm" }] }] };
  let lepasMuat;
  mockGet.mockResolvedValueOnce({ data: SD }).mockImplementationOnce(() => new Promise((r) => { lepasMuat = r; }));
  mockPost.mockResolvedValue({ data: {} });
  await mount(<SampleAdminDesk currentUser={{ permissions: { sample_order: ["view"] } }} onOpenDocument={() => {}} />);
  await klik("sample-desk-action-sos1");
  expect(mockPost).toHaveBeenCalledWith("/api/sample-orders/sos1/approve-payment", { note: "" });
  expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: expect.stringContaining("SOS-1") }));
  expect(q("sample-desk-toast")).toBeNull();
  expect(q("sample-desk-refreshing-bayar_sampel")).not.toBeNull();
  expect(q("sample-desk-refreshing-siap_gudang")).toBeNull();
  await act(async () => lepasMuat({ data: SD }));
});

test("muat ulang global memuat ulang meja", async () => {
  routeGet({ "/sales-admin/desk": DESK });
  await mount(<SalesAdminDesk currentUser={USER} onOpenDocument={() => {}} />);
  const n = mockGet.mock.calls.filter(([u]) => u.includes("/sales-admin/desk")).length;
  await act(async () => { window.dispatchEvent(new Event("kn:muat-ulang")); });
  expect(mockGet.mock.calls.filter(([u]) => u.includes("/sales-admin/desk")).length).toBe(n + 1);
  expect(MUAT_ULANG_EVENT).toBe("kn:muat-ulang");
  await act(async () => { kirimMuatUlang(); });
  expect(mockGet.mock.calls.filter(([u]) => u.includes("/sales-admin/desk")).length).toBe(n + 2);
});

test("RF#4 — tab & gulir pulih sesudah 'Buka layar penuh'; tanpa tanda kembali tidak menggulir", async () => {
  routeGet({ "/sales-admin/desk": DESK });
  window.scrollTo = jest.fn();
  Object.defineProperty(window, "scrollY", { value: 640, configurable: true });
  const open = jest.fn();
  await mount(<SalesAdminDesk currentUser={USER} onOpenDocument={open} />);
  await klik("desk-tabs-pantau"); await klik("desk-tabs-antrean");
  await klik("desk-row-so9"); await klik("desk-detail-open-full");
  expect(open).toHaveBeenCalledWith(expect.objectContaining({ view: "orders", focus_id: "so9" }));
  expect(JSON.parse(sessionStorage.getItem("kn.meja.sales_admin"))).toMatchObject({ scrollY: 640, returnPending: true, tab: "antrean" });
  for (const r of roots) await act(async () => r.unmount()); roots = [];
  await mount(<SalesAdminDesk currentUser={USER} onOpenDocument={open} />);
  expect(window.scrollTo).toHaveBeenCalledWith(0, 640);
  expect(JSON.parse(sessionStorage.getItem("kn.meja.sales_admin")).returnPending).toBe(false);
  window.scrollTo.mockClear();
  for (const r of roots) await act(async () => r.unmount()); roots = [];
  await mount(<SalesAdminDesk currentUser={USER} onOpenDocument={open} />);
  expect(window.scrollTo).not.toHaveBeenCalled();
});

test("tab Pantau tersimpan per meja dan pulih saat meja dibuka lagi", async () => {
  routeGet({ "/sales-admin/desk": DESK });
  await mount(<SalesAdminDesk currentUser={USER} onOpenDocument={() => {}} />);
  await klik("desk-tabs-pantau");
  expect(JSON.parse(sessionStorage.getItem("kn.meja.sales_admin")).tab).toBe("pantau");
  await lepasSemua();
  await mount(<SalesAdminDesk currentUser={USER} onOpenDocument={() => {}} />);
  expect(q("desk-pantau")).not.toBeNull(); expect(q("desk-antrean")).toBeNull();
});

test("Sample: antrean pantau di tab Pantau", async () => {
  routeGet({ "/sample-orders/desk": { queues: [
    { id: "bayar_sampel", label: "Bayar", count: 0, rows: [] }, { id: "di_gudang", label: "Di gudang", count: 0, rows: [] }] } });
  await mount(<SampleAdminDesk currentUser={{ permissions: { sample_order: ["view"] } }} onOpenDocument={() => {}} />);
  expect(q("sample-desk-queue-di_gudang")).toBeNull();
  expect(q("sample-desk-title")).toBeNull(); expect(q("sample-desk-metrics")).toBeNull();
  await klik("sample-desk-tabs-pantau");
  expect(q("sample-desk-queue-di_gudang")).not.toBeNull();
  expect(q("so-tracker-stub")).toBeNull();                            // tanpa izin order.view
});

test("memuat awal: empat kartu kerangka di grid meja", async () => {
  mockGet.mockImplementation(() => new Promise(() => {}));
  await mount(<SalesAdminDesk currentUser={USER} onOpenDocument={() => {}} />);
  expect(q("desk-loading")).not.toBeNull();
  expect(q("desk-loading").className).toBe(DESK_GRID_CLASS);
  expect(q("desk-loading").querySelectorAll('[data-testid^="desk-skeleton-"]')).toHaveLength(4);
});

test("orderDeskQueues & splitPantau: urutan dan pemisahan murni", () => {
  const qs = [{ id: "a", count: 0 }, { id: "b", count: 1, oldest_age_days: 1 }, { id: "c", count: 2, oldest_age_days: 5 },
    { id: "di_gudang", count: 3 }, { id: "selesai", count: 0 }];
  expect(orderDeskQueues(qs).map((x) => x.id)).toEqual(["c", "b", "di_gudang", "a", "selesai"]);
  expect(orderDeskQueues(null)).toEqual([]);
  expect(PANTAU_QUEUE_IDS).toEqual({ sales_admin: ["menunggu_manajer"], sample_admin: ["di_gudang", "kirim_ambil", "selesai"] });
  const s = splitPantau(qs, "sample_admin");
  expect(s.antrean.map((x) => x.id)).toEqual(["a", "b", "c"]);
  expect(s.pantau.map((x) => x.id)).toEqual(["di_gudang", "selesai"]);
  expect(splitPantau(qs, "md").pantau).toEqual([]);
});
