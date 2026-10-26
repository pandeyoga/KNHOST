// Fase 3 · P3 — Penjualan & persetujuan: D-05 satu form pelanggan (POS = form CRM lengkap), D-07 papan beranda PO
// Custom = tautan + satu dialog keputusan (approvalDecisions), D-06 Pusat Persetujuan (tab Matriks divisi, tab
// Amandemen = kartu tautan, preset tab, chip beranda → tab jenis).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CreateCustomerModal from "../pos/CreateCustomerModal";
import HomeWaitingBoards from "../home/HomeWaitingBoards";
import SpecialOrderDetail from "../sales/SpecialOrderDetail";
import ApprovalInbox from "../approvals/ApprovalInbox";
import { queueLink, canSeeMatrix } from "../approvals/inboxTabs";
import { AppNavProvider } from "../../context/AppNavContext";
import { ViewPresetProvider } from "../../context/ViewPresetContext";
import { askReason } from "../../services/confirmService";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true, REASON_MIN_LENGTH: 5,
  askReason: jest.fn(), askConfirm: jest.fn(async () => true), askText: jest.fn(), askChoice: jest.fn(), default: {},
}));
// Panel anak rincian Pesanan Khusus yang memuat data sendiri — di luar cakupan uji ini.
jest.mock("../sales/SpecialOrderChainPanel", () => () => null);
jest.mock("../sales/SpecialOrderCustomerApprovalPanel", () => () => null);
jest.mock("../sales/SpecialOrderPricingPanel", () => () => null);
jest.mock("../sales/SpecialOrderShippingPanel", () => () => null);
jest.mock("../sales/SpecialOrderFulfillmentPanel", () => () => null);
jest.mock("../sales/SpecialOrderItemsPanel", () => () => null);
jest.mock("../sales/SpecialOrderInfoPanels", () => ({ SpecialOrderInfoPanels: () => null }));
jest.mock("../documents/DocumentActionsBar", () => () => null);
jest.mock("../approvals/MyApprovalsPanel", () => () => <div data-testid="stub-matrix">matriks</div>);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
let mounted = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  await act(async () => {});
  mounted.push({ host, root });
  return { host, root };
}
async function click(el) { await act(async () => { el.click(); }); await act(async () => {}); }
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const key = Object.keys(map).find((k) => url.endsWith(k));
    return Promise.resolve({ data: key ? map[key] : [] });
  });
}
afterEach(async () => {
  for (const m of mounted) { await act(async () => { m.root.unmount(); }); m.host.remove(); }
  mounted = [];
  mockGet.mockReset(); mockPost.mockReset(); askReason.mockReset();
});

// ── D-05 ────────────────────────────────────────────────────────────────────
test("D-05: Pelanggan Baru di POS (admin) = form CRM LENGKAP — segmen, sales PJ, NPWP, limit, lot, metode bayar", async () => {
  routeGet({ "/sales-users": [{ id: "u_s1", name: "Ayu Sales" }] });
  const { host } = await mount(<CreateCustomerModal open onClose={() => {}} onCreated={() => {}} user={{ role: "admin", name: "Adi" }} />);
  const dlg = q(host, "create-customer");
  expect(dlg.getAttribute("role")).toBe("dialog");
  for (const id of ["customer-name", "customer-segment", "customer-assigned-sales", "customer-npwp", "customer-credit-limit",
    "customer-email", "customer-tags", "customer-pic", "customer-phone", "customer-address", "customer-lot-policy",
    "customer-method-tempo", "customer-method-dp", "customer-default-method"]) {
    expect(q(host, id)).not.toBeNull();
  }
  // varian kasir: dua seksi opsional terlipat DENGAN ringkasan — isian tetap terpasang (tidak diringkas).
  expect(q(host, "customer-section-pay-body").hidden).toBe(true);
  expect(q(host, "customer-section-pay-summary").textContent).toMatch(/Tunai/);
  expect(mockGet.mock.calls.some(([u]) => u.endsWith("/sales-users"))).toBe(true);
  await click(q(host, "create-customer-button"));
  expect(q(host, "create-customer-missing").textContent).toMatch(/nama toko.*sales penanggung jawab/);
  expect(mockPost).not.toHaveBeenCalled();
});

test("D-05: sales = penanggung jawab otomatis (tanpa pemilih), tombol 'Buat Pelanggan'", async () => {
  routeGet({});
  const { host } = await mount(<CreateCustomerModal open onClose={() => {}} user={{ id: "u_me", role: "sales", name: "Ayu" }} />);
  expect(q(host, "customer-assigned-sales-self").textContent).toContain("Ayu");
  expect(q(host, "customer-assigned-sales")).toBeNull();
  expect(q(host, "create-customer-button").textContent).toMatch(/Buat Pelanggan/);
});

// ── D-07 ────────────────────────────────────────────────────────────────────
const BOARDS = [
  { key: "special_order", view: "special-orders", count: 1,
    rows: [{ id: "sord1", number: "SORD-1", title: "Kain custom", days_waiting: 3, action: { label: "Setujui", path: "/special-orders/sord1/approve" } }] },
  { key: "contra_bon_dispute", view: "contra-bons", count: 1,
    rows: [{ id: "kb1", number: "KB-1", title: "Sengketa", days_waiting: 1, action: { label: "Putuskan", path: "/contra-bons/kb1/x" } }] },
];
const ids = (b) => ({ testIdBase: `b-${b.key}`, rowTestIdBase: `b-${b.key}-row` });

test("D-07: papan beranda PO Custom = TAUTAN (tanpa Setujui, baris membuka SORD); papan lain tetap bisa ditindak", async () => {
  const open = jest.fn();
  const { host } = await mount(<HomeWaitingBoards boards={BOARDS} onOpenDocument={open} ids={ids} />);
  expect(q(host, "b-special_order").getAttribute("data-board-mode")).toBe("link");
  expect(q(host, "b-special_order-row-act-sord1")).toBeNull();
  expect(q(host, "b-special_order-goto").textContent).toContain("Buka Pesanan Khusus");
  await click(q(host, "b-special_order-row-sord1"));
  expect(open).toHaveBeenCalledWith({ view: "special-orders", focus_type: "special_order", focus_id: "sord1", number: "SORD-1" });
  expect(q(host, "b-contra_bon_dispute").getAttribute("data-board-mode")).toBe("act");
  expect(q(host, "b-contra_bon_dispute-row-act-kb1")).not.toBeNull();
});

test("D-07: tombol 'Buka Pesanan Khusus' membawa preset tab Menunggu Persetujuan", async () => {
  const toView = jest.fn();
  const { host } = await mount(
    <AppNavProvider role="admin" onNavigateTo={toView} onOpenDocument={() => {}}>
      <HomeWaitingBoards boards={BOARDS} ids={ids} onNavigate={() => {}} />
    </AppNavProvider>);
  await click(q(host, "b-special_order-goto"));
  expect(toView).toHaveBeenCalledWith("special-orders", expect.objectContaining({ preset: { status: "pending_approval" } }));
});

const SORD = { id: "sord1", number: "SORD-1", status: "pending_approval", customer_name: "Toko Ayu", chain: {}, items: [],
  total_amount: 1500000, custom_item: { description: "Kain custom" } };
const MGR = { role: "manager", permissions: { order: ["view", "approve", "update", "create"] } };

test("D-07: Setujui di Pesanan Khusus = dialog bersama (catatan opsional) + pesan hasil berantai", async () => {
  askReason.mockResolvedValue("");
  mockPost.mockResolvedValue({ data: { ...SORD, status: "confirmed", chain: { design_request: { number: "DSR-0012" }, samples: [{ number: "SMP-0031" }] } } });
  const onUpdate = jest.fn();
  const { host } = await mount(<SpecialOrderDetail order={SORD} currentUser={MGR} onUpdate={onUpdate} onBack={() => {}} />);
  await click(q(host, "approve-special-order-btn"));
  expect(askReason).toHaveBeenCalledWith(expect.objectContaining({ testId: "sord-approve-dialog", reasonRequired: false }));
  expect(mockPost).toHaveBeenCalledWith("/api/special-orders/sord1/approve", { notes: "" });
  expect(q(host, "special-order-ok-notice").textContent).toContain("Diteruskan otomatis: DSR-0012, SMP-0031");
  expect(onUpdate).toHaveBeenCalled();
});

test("D-07: Tolak = alasan wajib ≥5 huruf lewat dialog bersama (pop-up tolak lama hilang)", async () => {
  askReason.mockResolvedValue("Harga tidak sesuai");
  mockPost.mockResolvedValue({ data: { ...SORD, status: "cancelled" } });
  const { host } = await mount(<SpecialOrderDetail order={SORD} currentUser={MGR} onUpdate={() => {}} onBack={() => {}} />);
  await click(q(host, "reject-special-order-btn"));
  expect(askReason).toHaveBeenCalledWith(expect.objectContaining({ testId: "sord-reject-dialog", reasonRequired: true, reasonMinLength: 5 }));
  expect(mockPost).toHaveBeenCalledWith("/api/special-orders/sord1/reject", { reason: "Harga tidak sesuai" });
  expect(q(host, "reject-modal")).toBeNull();
});

// ── D-06 ────────────────────────────────────────────────────────────────────
const INBOX = {
  "/amendments": [{ id: "amd1", number: "AMD-1", doc_number: "KSC/INV-1", proposed_at: "2026-10-20T00:00:00Z" }],
  "/approvals/backlog": {
    total: 1, items: [{ key: "amendment", label: "Koreksi & amandemen menunggu ACC", view: "amendments", count: 1 }],
    all_items: [{ key: "amendment", count: 1 }],
    oldest: [{ key: "amendment", id: "amd1", number: "AMD-1", title: "Koreksi faktur", queue_label: "Koreksi & amandemen menunggu ACC", view: "amendments", days_waiting: 2 }],
  },
};

test("D-06: inbox admin — tab Matriks divisi, amandemen tidak didaftar/diputus di sini (kartu tautan berhitungan)", async () => {
  routeGet(INBOX);
  const { host } = await mount(
    <AppNavProvider role="admin" onNavigateTo={() => {}} onOpenDocument={() => {}}>
      <ApprovalInbox currentUser={{ role: "admin" }} onNavigate={() => {}} />
    </AppNavProvider>);
  expect(q(host, "approval-inbox-tab-matrix")).not.toBeNull();
  expect(q(host, "approval-inbox-item-amd1")).toBeNull();                       // tidak lagi di daftar keputusan
  expect(q(host, "approval-inbox-other-amd1")).not.toBeNull();                  // "menunggu di layar lain"
  expect(q(host, "approval-inbox-backlog-elsewhere").textContent).toContain("0 di daftar bawah · 1 ditangani di layar lain");
  expect(q(host, "approval-inbox-tab-amendment").textContent).toContain("1");
  await click(q(host, "approval-inbox-tab-amendment"));
  expect(q(host, "approval-inbox-amendments-link-count").textContent).toBe("1");
  expect(q(host, "approval-inbox-amendments-link-open")).not.toBeNull();
  await click(q(host, "approval-inbox-tab-matrix"));
  expect(q(host, "stub-matrix")).not.toBeNull();
});

test("D-06: preset {tab:'matrix'} (alias my-approvals) membuka tab Matriks; Admin Sales tanpa tab Matriks", async () => {
  routeGet(INBOX);
  const { host } = await mount(
    <ViewPresetProvider preset={{ view: "approval-inbox", tab: "matrix", nonce: 1 }}>
      <ApprovalInbox currentUser={{ role: "manager" }} onNavigate={() => {}} />
    </ViewPresetProvider>);
  expect(q(host, "stub-matrix")).not.toBeNull();
  expect(q(host, "approval-inbox-tab-matrix").getAttribute("aria-selected")).toBe("true");

  const sa = await mount(
    <ViewPresetProvider preset={{ view: "approval-inbox", tab: "matrix", nonce: 2 }}>
      <ApprovalInbox currentUser={{ role: "sales_admin" }} onNavigate={() => {}} />
    </ViewPresetProvider>);
  expect(q(sa.host, "approval-inbox-tab-matrix")).toBeNull();
  expect(q(sa.host, "stub-matrix")).toBeNull();
  expect(canSeeMatrix("sales_admin")).toBe(false);
  expect(canSeeMatrix("manager")).toBe(true);
});

test("D-06: chip antrean beranda → inbox di tab jenisnya (bila didaftar inbox), selain itu layar kerjanya", () => {
  const can = (v) => v === "approval-inbox";
  expect(queueLink({ key: "purchase_order", view: "purchase-approval" }, can)).toEqual({ view: "approval-inbox", preset: { tab: "po" } });
  expect(queueLink({ key: "sales_return", view: "returns" }, can)).toEqual({ view: "approval-inbox", preset: { tab: "returns" } });
  expect(queueLink({ key: "amendment", view: "amendments" }, can)).toEqual({ view: "amendments" });
  expect(queueLink({ key: "transfer", view: "operations" }, can)).toEqual({ view: "operations" });
  expect(queueLink({ key: "price", view: "price-approvals" }, () => false)).toEqual({ view: "price-approvals" });
});

// ── Prasyarat D-27 (P7) — Permintaan Internal = FormModal baku ──────────────
test("InternalRequestCreateModal: FormModal (dialog), galat validasi di dalam pop-up, prefill dari papan stok", async () => {
  const InternalRequestCreateModal = require("../internal_requests/InternalRequestCreateModal").default;
  routeGet({ "/products": [{ id: "p1", sku: "KN-1", name: "Rayon Navy", base_unit: "meter" }], "/sales-orders": [] });
  const { host } = await mount(<InternalRequestCreateModal open onClose={() => {}} />);
  expect(q(host, "pin-create-modal").getAttribute("role")).toBe("dialog");
  await click(q(host, "pin-create-submit"));
  expect(q(host, "pin-create-modal-error").textContent).toContain("minimal satu barang");
  expect(mockPost).not.toHaveBeenCalled();
  const pre = await mount(<InternalRequestCreateModal open prefillProductId="p1" prefillQty="12" onClose={() => {}} />);
  expect(q(pre.host, "pin-qty-p1").value).toBe("12");
});
