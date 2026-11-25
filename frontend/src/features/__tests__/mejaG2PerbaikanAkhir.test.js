// Meja gelombang 2 · gelombang perbaikan akhir — satu pembuka aktif (kartu ↔ pratinjau), "Jejak" di HP, gaya sel, alasan opsional.
import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";
import { AppNavProvider } from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { PartyCardHost } from "../finance/cards/partyCards";
import { DocPreviewHost } from "../documents/preview/DocPreviewModal";
import DocLink from "../documents/preview/DocLink";
import MobileSalesAdminDesk from "../sales/mobile/MobileSalesAdminDesk";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
Element.prototype.scrollIntoView = () => {};

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: jest.fn(), patch: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } } },
  API: "/api", setActiveEntity: () => {}, setAuthToken: () => {},
}));
// Panel kartu diganti rintisan yang memuat satu DocLink (dokumen dibuka DARI kartu).
jest.mock("../crm/Customer360Panel", () => {
  const DocLinkLocal = require("../documents/preview/DocLink").default;
  return { __esModule: true, default: ({ currentUser }) => (
    <div data-testid="stub-customer-panel">
      <DocLinkLocal docType="sales_order" docId="so1" number="KSC/SO-00001" perms={currentUser?.permissions} testId="kartu-doc" />
    </div>) };
});
jest.mock("../purchasing/Supplier360Panel", () => ({ __esModule: true, default: () => <div data-testid="stub-supplier-panel" /> }));
jest.mock("../sales_admin/SoTrackerCard", () => () => null);
jest.mock("../sales_admin/KeepPendingPanel", () => () => null);
jest.mock("../sales_admin/CustomerGradeRulesCard", () => () => null);

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
let roots = [];
async function mount(el) {
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host); roots.push(root);
  await act(async () => { root.render(el); }); await act(async () => {}); await act(async () => {});
  return host;
}
const klik = async (id) => act(async () => { q(id).dispatchEvent(new MouseEvent("click", { bubbles: true })); });
const tunggu = async () => { for (let i = 0; i < 4; i += 1) await act(async () => { await new Promise((r) => setTimeout(r, 0)); }); };   // eslint-disable-line no-await-in-loop
afterEach(async () => { for (const r of roots) await act(async () => r.unmount()); roots = []; document.body.innerHTML = ""; mockGet.mockReset(); });

const SO1 = { id: "so1", number: "KSC/SO-00001", customer_id: "c1", customer_name: "Toko A", entity_id: "ent_ksc", status: "confirmed",
  items: [], total_amount: 0, grand_total: 0, ppn_amount: 0, paid_total: 0, created_at: "2026-11-20T03:00:00Z" };
const PERMS = { order: ["view"], customer: ["view"] };
const USER = { permissions: PERMS };

function Hosts({ buka }) {
  return (
    <AppNavProvider role="admin" onNavigateTo={() => {}} onOpenDocument={() => {}}>
      <EntityScopeProvider selectedEntity="all" entities={[]}>
        <DocLink docType="sales_order" docId="so1" number="KSC/SO-00001" perms={PERMS} testId="awal-doc" />
        {buka}
        <PartyCardHost currentUser={USER} selectedEntity="all" />
        <DocPreviewHost currentUser={USER} />
      </EntityScopeProvider>
    </AppNavProvider>
  );
}

test("dari pratinjau: klik nama pelanggan → pratinjau tertutup, kartu terbuka (satu pembuka aktif)", async () => {
  mockGet.mockResolvedValue({ data: SO1 });
  await mount(<Hosts />);
  await klik("awal-doc"); await tunggu();
  expect(q("doc-preview")).not.toBeNull();
  await klik("doc-preview-customer"); await tunggu();
  expect(q("doc-preview")).toBeNull();
  expect(q("customer-card")).not.toBeNull();
});

test("dari kartu: klik nomor dokumen → pratinjau di atas kartu; tutup pratinjau → kartu masih ada", async () => {
  mockGet.mockResolvedValue({ data: SO1 });
  await mount(<Hosts />);
  await klik("awal-doc"); await tunggu();
  await klik("doc-preview-customer"); await tunggu();
  expect(q("customer-card")).not.toBeNull();
  await klik("kartu-doc"); await tunggu();
  expect(q("doc-preview")).not.toBeNull();
  expect(q("customer-card")).not.toBeNull();
  // pratinjau digambar sesudah kartu (di atasnya)
  const semua = Array.from(document.body.querySelectorAll('[data-testid="customer-card"],[data-testid="doc-preview"]')).map((e) => e.getAttribute("data-testid"));
  expect(semua).toEqual(["customer-card", "doc-preview"]);
  const tutup = q("doc-preview-close-x");
  expect(tutup).not.toBeNull();
  await act(async () => { tutup.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  expect(q("doc-preview")).toBeNull();
  expect(q("customer-card")).not.toBeNull();
});

test("HP Admin Sales: pop-up baris SO menampilkan pratinjau pesanan tanpa tombol Jejak", async () => {
  const SO_ROW = { ref_type: "sales_order", ref_id: "so1", number: "SO-1", title: "Toko D", value: 700000, entity_id: "ent_ksc",
    action: "Follow-up", action_kind: "open", age_days: 9, age_kind: "overdue", badge: "lewat", customer_id: "c1", order_id: "so1" };
  mockGet.mockImplementation((u) => {
    if (String(u).includes("/sales-admin/desk")) {
      return Promise.resolve({ data: { queues: [{ id: "jatuh_tempo", label: "Jatuh tempo", count: 1, rows: [SO_ROW] }], not_my_desk: [] } });
    }
    if (String(u).includes("/sales-orders/so1")) return Promise.resolve({ data: SO1 });
    return Promise.resolve({ data: [] });
  });
  await mount(<MobileSalesAdminDesk selectedEntity="ent_ksc" currentUser={USER} />);
  await klik("m-desk-number-jatuh_tempo-so1"); await tunggu();
  expect(q("m-desk-detail")).not.toBeNull();
  expect(q("m-desk-doc-panel")).not.toBeNull();
  expect(q("m-desk-doc-trace")).toBeNull();
});

test("sel nomor tidak berwarna biru mentah (teks biasa tak tampak tautan)", () => {
  const baca = (f) => fs.readFileSync(path.join(__dirname, f), "utf8");
  const pv = baca("../finance/payments/PaymentVarianceQueue.jsx");
  expect(pv).not.toMatch(/<td className="px-2 py-2 font-semibold text-\[#0058CC\]">/);
  const ar = baca("../finance/ARAgingDetail.jsx");
  expect(ar).not.toMatch(/<td className="px-3 py-2 font-semibold text-\[#0058CC\] whitespace-nowrap">/);
});

test("label kolom tabel panel umum 12/600 (font-semibold)", () => {
  const src = fs.readFileSync(path.join(__dirname, "../desks/GenericDeskPanel.jsx"), "utf8");
  expect(src).toMatch(/const TH = "[^"]*font-semibold/);
  expect(src).not.toMatch(/const TH = "[^"]*font-medium/);
});
