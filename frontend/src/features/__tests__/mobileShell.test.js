// Fase 3 · P7 — aplikasi HP satu kerangka (L-09) + D-26 satu pintu desktop + bagian HP D-05/D-06/D-07/D-27/D-28,
// permintaan P2 (Kebijakan Retur → Pengaturan › Penjualan) & P5 (papan tautan membawa preset).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import MobileOpsApp, { canOpenFull, decidableQueue, dedupQueue, queueFullTarget } from "../mobile/MobileOpsApp";
import { setAccessContext } from "../../config/roles";
import MobileWarehouseApp from "../mobile/MobileWarehouseApp";
import MobileApprovalInbox from "../mobile/MobileApprovalInbox";
import MobileMdApp from "../sales/mobile/MobileMdApp";
import MobileSalesApp from "../sales/mobile/MobileSalesApp";
import MobileMore, { fullViewsFor } from "../sales/mobile/MobileMore";
import MobileSalesHome from "../sales/mobile/MobileSalesHome";
import MobileCustomerForm from "../sales/mobile/MobileCustomerForm";
import { MobileDesignRequests } from "../sales/mobile/MobileMdViews";
import MobileInternalRequests from "../sales/mobile/MobileInternalRequests";
import { humanizeNotif, groupNotifications } from "../mobile/notifText";

const mockGet = jest.fn();
const mockSync = jest.fn();
const mockApproveSo = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), patch: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } } },
  API: "/api",
  setActiveEntity: () => {},
}));
jest.mock("../tanya/TanyaKnView", () => () => null);
jest.mock("../sales/mobile/MobilePwa", () => ({
  MobilePushBanner: () => null, MobilePushCard: () => null, MobileInstallCard: () => null,
  syncPushSubscription: (...a) => mockSync(...a), dropPushSubscription: async () => {},
}));
jest.mock("../sales/mobile/MobilePendingQueue", () => () => null);
jest.mock("../sales/mobile/MobileCatalog", () => () => <div data-testid="stub-catalog" />);
jest.mock("../sales/mobile/MobileOrders", () => () => <div data-testid="stub-orders" />);
jest.mock("../../services/approvalDecisions", () => ({
  approveSpecialOrder: (...a) => mockApproveSo(...a),
  rejectSpecialOrder: async () => null, approvePrice: async () => null, rejectPrice: async () => null,
  decisionErrorText: () => "galat",
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
if (!window.matchMedia) window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const all = (host, sel) => [...host.querySelectorAll(sel)];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  await act(async () => {});
  return { host, root };
}
const click = async (el) => { await act(async () => { el.click(); }); await act(async () => {}); };
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.includes(k));
    if (!hit) return Promise.resolve({ data: [] });
    const v = map[hit];
    return v instanceof Error ? Promise.reject(v) : Promise.resolve({ data: v });
  });
}
afterEach(() => { mockGet.mockReset(); mockSync.mockReset(); mockApproveSo.mockReset(); document.body.innerHTML = ""; window.history.replaceState(null, "", "/"); });

const ADMIN = { id: "u1", role: "admin", name: "Budi Santoso", permissions: { price_approval: ["*"], order: ["*"], approval: ["*"], makloon_order: ["*"], qc: ["*"] } };
const WH = { id: "u2", role: "warehouse", name: "Gita Gudang", permissions: {} };
const MD = { id: "u3", role: "md", name: "Rina Merchandiser", permissions: { product: ["view"] } };
const SALES = { id: "u4", role: "sales", name: "Sari Sales", permissions: {} };
const SALES_ADMIN = { id: "u5", role: "sales_admin", name: "Ani Admin", permissions: {} };

/** Kerangka yang SAMA: app bar + lonceng + bilah tab ≤ 5 berakhiran "Lainnya", tanpa ikon desktop/keluar di app bar. */
function expectShell(host, { tab = "mobile-tab-btn-", notif = "mobile-notif-btn" } = {}) {
  const bar = q(host, "mobile-appbar");
  expect(bar).not.toBeNull();
  expect(bar.querySelector(`[data-testid="${notif}"]`)).not.toBeNull();
  expect(bar.querySelectorAll("button").length).toBe(1);               // hanya lonceng (D-26: monitor/keluar dicabut)
  const tabs = all(host, `[data-testid^="${tab}"]`).filter((b) => b.tagName === "BUTTON");
  expect(tabs.length).toBeGreaterThanOrEqual(2);
  expect(tabs.length).toBeLessThanOrEqual(5);
  expect(tabs[tabs.length - 1].getAttribute("data-testid")).toBe(`${tab}more`);
  expect(tabs[tabs.length - 1].textContent).toBe("Lainnya");
  return tabs.map((b) => b.getAttribute("data-testid").replace(tab, ""));
}

test("L-09: Ops, Gudang, MD & Sales memakai kerangka yang sama (app bar, lonceng, ≤5 tab, Lainnya terakhir)", async () => {
  routeGet({ "/approvals/my-queue": { items: [] }, "/dashboard": {}, "/md/desk": { queues: [] } });
  const ops = await mount(<MobileOpsApp user={ADMIN} />);
  expect(expectShell(ops.host)).toEqual(["queue", "kpi", "catalog", "tanya", "more"]);
  expect(q(ops.host, "mobile-appbar-title").textContent).toBe("Halo, Budi");
  const wh = await mount(<MobileWarehouseApp user={WH} />);
  expect(expectShell(wh.host)).toEqual(["inbound", "outbound", "sample", "scan", "more"]);
  const md = await mount(<MobileMdApp user={MD} />);
  expect(expectShell(md.host, { tab: "m-md-tab-", notif: "m-md-notif-btn" })).toEqual(["desk", "design", "sample", "products", "more"]);
  const sales = await mount(<MobileSalesApp user={SALES} data={{}} cart={[{ id: "c1" }, { id: "c2" }]} />);
  expect(expectShell(sales.host)).toEqual(["home", "catalog", "cart", "orders", "more"]);
  expect(q(sales.host, "mobile-tab-cart-count").textContent).toBe("2");         // lencana per tab (keranjang)
  // Push disinkronkan SEKALI per aplikasi (dulu Sales/MD memanggil sendiri + cangkang lama untuk Ops/Gudang).
  expect(mockSync).toHaveBeenCalledTimes(4);
});

test("L-09: lonceng membuka NotifSheet di Gudang (dulu hanya pil merah) & teks tahap dirapikan", async () => {
  routeGet({});
  const notifications = [{ id: "n1", type: "turn", title: "Giliran Anda — Kirim pesanan: KSC/SO-00001", body: "tahap: picked", link: "operations" }];
  const onOpenFull = jest.fn();
  const { host } = await mount(<MobileWarehouseApp user={WH} notifications={notifications} unreadCount={120} onOpenFull={onOpenFull} />);
  expect(q(host, "mobile-notif-count").textContent).toBe("99+");
  await click(q(host, "mobile-notif-btn"));
  expect(q(host, "mobile-notif-n1").textContent).toContain("tahap: sudah diambil");
  await click(q(host, "mobile-notif-n1"));
  expect(onOpenFull).toHaveBeenCalledWith("operations", "operations", undefined);
  expect(q(host, "mobile-notif-sheet")).toBeNull();
});

test("D-26: satu pintu 'Tampilan desktop' — hanya di tab Lainnya, sama di keempat aplikasi", async () => {
  routeGet({ "/approvals/my-queue": { items: [] }, "/dashboard": {} });
  const onForceDesktop = jest.fn();
  const ops = await mount(<MobileOpsApp user={ADMIN} onForceDesktop={onForceDesktop} initialTab="kpi" />);
  expect(q(ops.host, "mo-open-desktop")).toBeNull();                  // dulu tombol di Ringkas
  expect(q(ops.host, "mobile-force-desktop")).toBeNull();
  await click(q(ops.host, "mobile-tab-btn-more"));
  expect(all(ops.host, '[data-testid="mobile-force-desktop"]').length).toBe(1);
  expect(q(ops.host, "mobile-account-profile").textContent).toContain("Budi Santoso");
  await click(q(ops.host, "mobile-force-desktop"));
  expect(onForceDesktop).toHaveBeenCalled();

  const md = await mount(<MobileMdApp user={MD} onForceDesktop={() => {}} />);
  await click(q(md.host, "m-md-tab-more"));
  expect(all(md.host, '[data-testid="mobile-force-desktop"]').length).toBe(1);
  expect(q(md.host, "m-md-desktop")).toBeNull();                       // baris desktop kedua MD dicabut
});

test("Gudang: 'Belum Tag' kini segmen di tab Pindai (bilah tetap ≤ 5 tab)", async () => {
  routeGet({ "/rfid/printer-status": { warehouses: [] }, "/rfid/untagged-rolls": [{ id: "r1", roll_no: "R-001", product_name: "Katun", warehouse_id: "w1", length_remaining: 10 }] });
  const { host } = await mount(<MobileWarehouseApp user={WH} />);
  expect(q(host, "mobile-tab-btn-untagged")).toBeNull();
  await click(q(host, "mobile-tab-btn-scan"));
  expect(q(host, "mw-scan")).not.toBeNull();
  await click(q(host, "mw-pindai-tabs-untagged"));
  expect(q(host, "mw-untagged-r1")).not.toBeNull();
});

test("D-06 HP: antrean lintas tahap tanpa PO custom yang sudah ada di daftar keputusan HP + 'Buka layar lengkap'", async () => {
  const items = [
    { stage: "po_custom", id: "sord_a", number: "SORD-1", view: "special-orders" },
    { stage: "po_custom", id: "sord_b", number: "SORD-2", view: "special-orders" },
    { stage: "purchase_request", id: "pr1", number: "PR-1", view: "purchase-requisitions" },
  ];
  expect(dedupQueue(items, [{ id: "sord_a" }]).map((x) => x.id)).toEqual(["sord_b", "pr1"]);
  expect(queueFullTarget(items[2], "admin")).toEqual({ nav: "approval-inbox", view: "approval-inbox", preset: { tab: "matrix" } });
  expect(queueFullTarget(items[2], "finance")).toEqual({ nav: "purchase-requisitions", view: "purchase-requisitions" });
  // Layar tujuan yang tidak boleh dibuka peran ini → tombol tidak tampil (bukan "Permission ditolak").
  expect(canOpenFull({ view: "approval-inbox" }, "admin")).toBe(true);
  expect(canOpenFull({ view: "purchase-requisitions" }, "designer")).toBe(false);
  expect(canOpenFull({ view: "" }, "admin")).toBe(false);
  // Finance dengan izin server tanpa `purchase_requisition` (kasus crawl) → tidak bisa membuka layar PR.
  setAccessContext({ role: "finance", permissions: { order: ["view"] }, view_resources: { "purchase-requisitions": ["purchase_requisition"] } });
  expect(canOpenFull({ view: "purchase-requisitions" }, "finance")).toBe(false);
  setAccessContext(null);

  routeGet({ "/approvals/my-queue": { items }, "/special-orders": [{ id: "sord_a", number: "SORD-1", status: "pending_approval", customer_name: "Toko" }], "/price-approvals": [] });
  const onOpenFull = jest.fn();
  const { host } = await mount(<MobileOpsApp user={ADMIN} onOpenFull={onOpenFull} />);
  expect(q(host, "mo-special-sord_a")).not.toBeNull();                 // diputus di HP
  expect(q(host, "mo-queue-sord_a")).toBeNull();                       // tidak ganda di antrean
  expect(q(host, "mo-queue-pr1")).not.toBeNull();
  // R5 — lencana tab = pesanan khusus di HP (1) + antrean lintas tahap yang bisa diputus (sord_b, pr1).
  expect(q(host, "mobile-tab-btn-queue-badge").textContent).toBe("3");
  await click(q(host, "mo-queue-open-pr1"));
  expect(onOpenFull).toHaveBeenCalledWith("approval-inbox", "approval-inbox", { preset: { tab: "matrix" } });
});

test("R5 HP: antrean lintas tahap hanya butir yang BISA diputus peran ini (can_decide); lencana & teks sama", async () => {
  const items = [
    { stage: "purchase_request", id: "pr1", number: "PR-1", view: "purchase-requisitions", stage_label: "Permintaan Pembelian (PR)", can_decide: true, requester: "Budi Santoso" },
    { stage: "po_custom", id: "sord_x", number: "SORD-9", view: "special-orders", can_decide: false },
    { stage: "purchase_request", id: "pr2", number: "PR-2", view: "purchase-requisitions", can_decide: false },
  ];
  expect(decidableQueue(items, []).map((x) => x.id)).toEqual(["pr1"]);
  expect(decidableQueue([{ id: "lama", stage: "design_acc" }], []).map((x) => x.id)).toEqual(["lama"]);   // server lama
  routeGet({ "/approvals/my-queue": { items }, "/special-orders": [], "/price-approvals": [] });
  const { host } = await mount(<MobileOpsApp user={ADMIN} onOpenFull={() => {}} />);
  expect(q(host, "mo-queue-pr1")).not.toBeNull();
  expect(q(host, "mo-queue-sord_x")).toBeNull();
  expect(q(host, "mo-queue-pr2")).toBeNull();
  expect(q(host, "mo-queue-stage-pr1").textContent).toBe("Permintaan Pembelian");   // label Matriks divisi desktop
  expect(q(host, "mo-queue-count").textContent).toBe("(1)");
  expect(q(host, "mobile-tab-btn-queue-badge").textContent).toBe("1");
  expect(q(host, "mo-queue-note").textContent).toContain("1 dokumen di atas menunggu keputusan Anda");
  expect(q(host, "mo-queue-note").textContent).toContain("2 dokumen lintas tahap menunggu peran lain");

  // Peran yang tidak bisa memutus apa pun (kasus crawl: Finance melihat PR) → kosong, tanpa lencana.
  const FIN = { id: "u9", role: "finance", name: "Fina", permissions: { approval: ["view"] } };
  routeGet({ "/approvals/my-queue": { items: items.map((x) => ({ ...x, can_decide: false })) } });
  const fin = await mount(<MobileOpsApp user={FIN} onOpenFull={() => {}} />);
  expect(q(fin.host, "mo-queue-empty").textContent).toContain("3 dokumen lintas tahap menunggu peran lain");
  expect(q(fin.host, "mo-queue-count")).toBeNull();
  expect(q(fin.host, "mobile-tab-btn-queue-badge")).toBeNull();
});

test("D-07/D-27 HP: Setujui PO custom memakai dialog bersama approvalDecisions (catatan bawaan 'Disetujui dari HP')", async () => {
  routeGet({ "/special-orders": [{ id: "s1", number: "SORD-9", status: "pending_approval", customer_name: "Toko" }], "/price-approvals": [] });
  mockApproveSo.mockResolvedValue({ data: {}, message: "Pesanan disetujui. Diteruskan otomatis: DSR-0012." });
  const { host } = await mount(<MobileApprovalInbox canPrice canSpecial />);
  await click(q(host, "mo-special-approve-s1"));
  expect(mockApproveSo).toHaveBeenCalledWith(expect.objectContaining({ id: "s1" }), { defaultNote: "Disetujui dari HP" });
  expect(q(host, "mo-inbox-msg").textContent).toContain("DSR-0012");
});

test("D-07 HP: papan PO Custom di Beranda HP Sales = mode tautan (tanpa Setujui), baris membuka Pesanan Khusus HP", async () => {
  routeGet({ "/home/sales": { waiting_boards: [{ key: "special_order", view: "special-orders", count: 1, owner_scoped: true,
    rows: [{ id: "sord1", number: "SORD-1", title: "Kain custom", action: { label: "Setujui" } }] }] } });
  const onOpenSubWith = jest.fn();
  const { host } = await mount(<MobileSalesHome user={SALES} onOpenSubWith={onOpenSubWith} onOpenSub={() => {}} />);
  const board = q(host, "m-home-board-special_order");
  expect(board.getAttribute("data-board-mode")).toBe("link");
  expect(q(host, "m-home-board-special_order-row-act-sord1")).toBeNull();
  await click(q(host, "m-home-board-special_order-row-sord1"));
  expect(onOpenSubWith).toHaveBeenCalledWith("special", { id: "sord1" });
});

test("P5: papan tautan tanpa layar HP (Barang ditahan QC) dibuka layar penuh Inspeksi dengan preset {hold:true}", async () => {
  routeGet({ "/home/sales": { waiting_boards: [{ key: "special_order", view: "special-orders", count: 0, rows: [] },
    { key: "inspection_hold", view: "inspections", count: 1, rows: [{ id: "ins1", number: "INS-1", title: "Katun" }] }] } });
  const onOpenDocument = jest.fn();
  const onOpenFull = jest.fn();
  const { host } = await mount(<MobileSalesHome user={{ role: "manager" }} onOpenDocument={onOpenDocument} onOpenFull={onOpenFull} />);
  await click(q(host, "m-home-board-inspection_hold-row-ins1"));
  expect(onOpenDocument).toHaveBeenCalledWith({ view: "inspections", focus_type: "inspection", focus_id: "ins1", number: "INS-1", preset: { hold: true } });
  await click(q(host, "m-home-board-inspection_hold-goto"));
  expect(onOpenFull).toHaveBeenCalledWith("inspections", "inspections", { preset: { hold: true } });
});

test("D-26/P2: Lainnya Sales — satu seksi 'Layar lengkap' tanpa butir yang sudah ada di menu HP; Kebijakan Retur → settings-sales", async () => {
  routeGet({});
  const onOpenFull = jest.fn();
  const { host } = await mount(<MobileMore user={SALES_ADMIN} sub={null} setSub={() => {}} entities={[]} onOpenFull={onOpenFull} />);
  expect(q(host, "mobile-more-section-hubs")).toBeNull();
  expect(q(host, "mobile-more-section-full")).not.toBeNull();
  expect(q(host, "mobile-account-menu")).not.toBeNull();
  expect(fullViewsFor("sales_admin").find((m) => m.view === "return-policies")?.nav).toBe("settings-sales");
  const toggle = q(host, "mobile-more-section-toggle-full");
  if (!q(host, "mobile-more-section-body-full")) await click(toggle);
  expect(q(host, "mobile-hub-amendments")).toBeNull();                 // ada layar HP "Koreksi & Amandemen"
  expect(q(host, "mobile-hub-orders")).toBeNull();                     // tab bawah Pesanan
  expect(q(host, "mobile-hub-internal-requests")).toBeNull();          // layar HP Permintaan Internal
  await click(q(host, "mobile-full-return-policies"));
  expect(onOpenFull).toHaveBeenCalledWith("settings-sales", "return-policies");
});

test("D-28 HP: MD › Stok & ATP memakai MobileStockAtp (status-board), bukan daftar saldo lama", async () => {
  routeGet({ "/inventory/status-board": [] });
  const { host } = await mount(<MobileMdApp user={MD} />);
  await click(q(host, "m-md-tab-more"));
  expect(q(host, "m-md-menu-stock").textContent).toContain("Stok & ATP");
  expect(q(host, "m-md-full-rnd-designs").textContent).toBe("Desain & Pattern");      // D-09 HP
  await click(q(host, "m-md-menu-stock"));
  expect(q(host, "m-stock-tabs")).not.toBeNull();
  expect(mockGet.mock.calls.some(([u]) => String(u).includes("/inventory/status-board"))).toBe(true);
  expect(mockGet.mock.calls.some(([u]) => String(u).includes("/inventory/balances"))).toBe(false);
});

test("D-05 HP: form pelanggan HP = CustomerFormModal lengkap (segmen, sales PJ, profil bayar, lot) — tambah & ubah", async () => {
  routeGet({ "/sales-users": [{ id: "s1", name: "Sari" }] });
  const { host } = await mount(<MobileCustomerForm user={ADMIN} selectedEntity="ent_a" onClose={() => {}} />);
  expect(q(host, "m-customer-form")).not.toBeNull();
  for (const sec of ["customer-section-store", "customer-section-pay", "customer-section-lot"]) expect(q(host, sec)).not.toBeNull();
  expect(q(host, "m-customer-form-submit")).not.toBeNull();
  const edit = await mount(<MobileCustomerForm user={SALES} customer={{ id: "c1", name: "Toko A", addresses: [] }} onClose={() => {}} />);
  expect(edit.host.textContent).toContain("Ubah Pelanggan");
});

test("D-27 HP: Permintaan Desain & Permintaan Internal HP membuka form DESKTOP (FormModal)", async () => {
  routeGet({ "/design-requests/meta": { sources: [{ id: "internal", label: "Internal" }], categories: { pattern: [], design: [] }, designers: [] },
    "/design-requests": [], "/internal-requests/meta": {}, "/internal-requests": [] });
  const dsr = await mount(<MobileDesignRequests />);
  await click(q(dsr.host, "m-dsr-new"));
  expect(q(dsr.host, "m-dsr-create")).not.toBeNull();
  expect(q(dsr.host, "dsr-create-submit")).not.toBeNull();
  expect(q(dsr.host, "dsr-section-source")).not.toBeNull();
  const pin = await mount(<MobileInternalRequests user={SALES} />);
  await click(q(pin.host, "m-pin-new"));
  expect(q(pin.host, "pin-create-modal")).not.toBeNull();
  expect(q(pin.host, "pin-reason")).not.toBeNull();
});

test("Sales: pintasan PWA ?m= & ?notif= tetap berlaku di kerangka v2", async () => {
  routeGet({});
  window.history.replaceState(null, "", "/?m=orders&notif=1");
  const { host } = await mount(<MobileSalesApp user={SALES} data={{}} cart={[]} notifications={[]} />);
  expect(q(host, "mobile-view-orders")).not.toBeNull();
  expect(q(host, "mobile-notif-sheet")).not.toBeNull();
});

test("notifText: teks tahap & peran dirapikan; kartu identik digabung (G5-57)", () => {
  expect(humanizeNotif("Eskalasi · tahap: pending_approval oleh manager.")).toBe("Eskalasi · tahap: menunggu persetujuan oleh Manajer.");
  const g = groupNotifications([{ id: "a", type: "x", title: "T", body: "B" }, { id: "b", type: "x", title: "T", body: "B" }, { id: "c", type: "x", title: "U" }]);
  expect(g.map((x) => x.ids)).toEqual([["a", "b"], ["c"]]);
});
