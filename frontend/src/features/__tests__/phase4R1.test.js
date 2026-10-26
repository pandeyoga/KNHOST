// Fase 4 · R1 — form HP = form desktop (keputusan pemilik: form INPUT di HP tidak diringkas).
// Kwitansi (ARReceiptModal), Amandemen (AmendmentProposeModal), PR bahan MD (PrCreateModal), Ubah SKU MD (VariantEditor),
// lembar alamat & tindak lanjut → FormModal, menu HP MD Labdip/Handfeel/Proofing → satu baris R&D Produk Baru.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ARReceiptModal from "../crm/ARReceiptModal";
import MobileArReceipt from "../sales/mobile/MobileArReceipt";
import MobileAmendSheet from "../sales/mobile/MobileAmendSheet";
import AmendmentProposeModal from "../finance/amendments/AmendmentProposeModal";
import { autoReasonFor } from "../finance/amendments/AmendmentItemRows";
import { MobilePurchaseRequisitions, prCreatedText, prRealizationText } from "../sales/mobile/MobileMdViews";
import { MobileMdProducts } from "../sales/mobile/MobileMdProducts";
import { CustomerAddressSheet, CustomerFollowupSheet } from "../sales/mobile/MobileSalesFlows";
import MobileMdApp from "../sales/mobile/MobileMdApp";
import MobileOrders from "../sales/mobile/MobileOrders";
import { HUB_TABS } from "../../config/hubTabs";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockOfflinePost = jest.fn();
const mockPreview = jest.fn();
const mockPropose = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } } },
  API: "/api",
  setActiveEntity: () => {},
}));
jest.mock("../../utils/offlineQueue", () => ({ ...jest.requireActual("../../utils/offlineQueue"), offlinePost: (...a) => mockOfflinePost(...a) }));
jest.mock("../sales/mobile/MobilePendingQueue", () => () => null);
jest.mock("../finance/payments/paymentApi", () => ({
  assessVariance: async () => ({ needs_decision: false, direction: "none" }),
  varianceMeta: async () => ({ reasons: [] }),
  directionMeta: () => ({ label: "", bg: "#fff", fg: "#000" }),
}));
jest.mock("../finance/amendments/amendmentApi", () => ({
  ...jest.requireActual("../finance/amendments/amendmentApi"),
  errText: (e, fb) => fb,
  listReasons: async () => [
    { code: "qty_adjustment", label: "Penyesuaian jumlah", help: "Jumlah keliru" },
    { code: "price_correction", label: "Koreksi harga", help: "" },
    { code: "discount_grant", label: "Pemberian diskon", help: "" },
  ],
  previewAmendment: (...a) => mockPreview(...a),
  proposeAmendment: (...a) => mockPropose(...a),
  statusMeta: () => ({ label: "Diterapkan otomatis", bg: "#fff", fg: "#000" }),
}));
jest.mock("../catalog/VariantEditor", () => ({
  VariantEditor: (p) => { global.__r1Variant = p; return <div data-testid="stub-variant-editor" />; },
}));
jest.mock("../tanya/TanyaKnView", () => () => null);
jest.mock("../sales/mobile/MobileOrderJourney", () => () => null);
jest.mock("../sales/mobile/MobilePwa", () => ({
  MobilePushBanner: () => null, MobilePushCard: () => null, MobileInstallCard: () => null,
  syncPushSubscription: () => {}, dropPushSubscription: async () => {},
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
if (!window.matchMedia) window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
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
const wait = async (ms) => { await act(async () => { await new Promise((r) => setTimeout(r, ms)); }); };
function typeInto(el, value) {
  const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), "value").set;
  setter.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.includes(k));
    if (!hit) return Promise.resolve({ data: [] });
    return Promise.resolve({ data: map[hit] });
  });
}
afterEach(() => {
  [mockGet, mockPost, mockOfflinePost, mockPreview, mockPropose].forEach((m) => m.mockReset());
  document.body.innerHTML = "";
  delete global.__r1Variant;
});

const OPEN = [{ order_id: "so1", number: "KSC/SO-0001", outstanding: 50000 }, { order_id: "so2", number: "KSC/SO-0002", outstanding: 75000 }];

test("Kwitansi HP = ARReceiptModal (FormModal): tanggal, deposit, mode alokasi, SO asal di atas & teralokasi", async () => {
  routeGet({ "/ar-receipts/open-orders": OPEN, "/ar-receipts/deposit": { deposit_balance: 20000 } });
  const { host } = await mount(<MobileArReceipt customer={{ id: "c1", name: "Toko A", focus_order_id: "so2" }} onClose={() => {}} onDone={() => {}} />);
  const card = q(host, "m-ar-receipt");
  expect(card.className).toMatch(/\bkn-modal-card\b/);                     // layar penuh di HP (FormModal)
  expect(q(host, "m-ar-receipt-title").textContent).toBe("Catat Pembayaran · Toko A");
  for (const id of ["ar-receipt-date", "ar-receipt-method", "ar-receipt-deposit-box", "ar-receipt-mode-auto", "ar-receipt-mode-manual",
    "ar-receipt-notes", "ar-receipt-total", "ar-receipt-submit", "ar-receipt-cancel"]) expect(q(host, id)).not.toBeNull();
  expect(q(host, "m-ar-amount")).toBeNull();                                 // form HP ringkas lama sudah tidak ada
  const rows = [...host.querySelectorAll('[data-testid^="ar-receipt-order-so"]')].map((e) => e.getAttribute("data-testid"));
  expect(rows[0]).toBe("ar-receipt-order-so2");                             // G2-21 — SO yang dibuka paling atas
  expect(q(host, "ar-receipt-order-so2").textContent).toContain("dibuka");
  expect(q(host, "ar-receipt-alloc-so2").value).toMatch(/^75.?000$/);
  expect(mockGet).toHaveBeenCalledWith("/api/ar-receipts/open-orders", { params: { customer_id: "c1" } });
});

test("Kwitansi HP offline-aware lewat prop `offline`: antrean → pesan offline; online → onDone(pesan, kwitansi)", async () => {
  routeGet({ "/ar-receipts/open-orders": OPEN, "/ar-receipts/deposit": {} });
  const onDone = jest.fn();
  mockOfflinePost.mockResolvedValueOnce({ queued: true, key: "k1" });
  const a = await mount(<MobileArReceipt customer={{ id: "c1", name: "Toko A" }} onClose={() => {}} onDone={onDone} />);
  await click(q(a.host, "ar-receipt-submit"));
  expect(mockOfflinePost).toHaveBeenCalledTimes(1);
  const [url, body, opts] = mockOfflinePost.mock.calls[0];
  expect(url).toBe("/api/ar-receipts");
  expect(body).toMatchObject({ customer_id: "c1", amount: 125000, method: "transfer", use_deposit_amount: 0 });
  expect(body.receipt_date).toBeTruthy();                                    // tanggal terima ikut dikirim dari HP
  expect(opts.idempotencyKey).toBeTruthy();
  expect(onDone).toHaveBeenCalledWith(expect.stringMatching(/^Offline/), null);
  expect(mockPost).not.toHaveBeenCalled();

  mockOfflinePost.mockResolvedValueOnce({ queued: false, data: { number: "AR-9", amount: 125000 } });
  const b = await mount(<MobileArReceipt customer={{ id: "c1", name: "Toko A" }} onClose={() => {}} onDone={onDone} />);
  await click(q(b.host, "ar-receipt-submit"));
  expect(onDone).toHaveBeenLastCalledWith(expect.stringContaining("Pembayaran AR-9"), { number: "AR-9", amount: 125000 });
});

test("Kwitansi desktop: FormModal, POST ber-Idempotency-Key (tanpa antrean offline), galat server di DALAM pop-up", async () => {
  routeGet({ "/ar-receipts/open-orders": OPEN, "/ar-receipts/deposit": {} });
  mockPost.mockRejectedValueOnce({ response: { status: 400, data: { detail: "Periode terkunci" } } });
  const onError = jest.fn();
  const { host } = await mount(<ARReceiptModal customerId="c1" customerName="Toko A" onClose={() => {}} onDone={() => {}} onError={onError} />);
  expect(q(host, "ar-receipt-modal").className).toMatch(/\bkn-modal-card\b/);
  expect(q(host, "ar-receipt-modal-close")).not.toBeNull();
  await click(q(host, "ar-receipt-submit"));
  expect(mockOfflinePost).not.toHaveBeenCalled();
  expect(mockPost.mock.calls[0][0]).toBe("/api/ar-receipts");
  expect(mockPost.mock.calls[0][2].headers["Idempotency-Key"]).toBeTruthy();
  expect(q(host, "ar-receipt-modal-error").textContent).toContain("Periode terkunci");   // di kaki pop-up
  expect(q(host, "ar-receipt-modal").contains(q(host, "ar-receipt-modal-error"))).toBe(true);
  expect(onError).toHaveBeenCalledWith("Periode terkunci");
});

const ORDER = { id: "so1", number: "KSC/SO-0001", customer_name: "Toko A", grand_total: 100000, order_discount_percent: 0,
  items: [{ product_id: "p1", product_name: "Ceruty", sku: "CR-1", unit: "meter", quantity: 10, price: 10000, discount_percent: 0 }] };
const PREVIEW = { impact: { delta: -10000, amount_before: 100000, amount_after: 90000 }, method: "re_derive", requires_approval: false, policy: {} };

test("Amandemen HP = AmendmentProposeModal: diskon pesanan + tautan bukti, alasan otomatis (bisa diganti), hasil → onClose(true)", async () => {
  mockPreview.mockResolvedValue(PREVIEW);
  mockPropose.mockResolvedValue({ number: "AMD-1", status: "auto_applied", method_label: "Dihitung ulang", impact: { delta: -10000 } });
  const onClose = jest.fn();
  const { host } = await mount(<MobileAmendSheet order={ORDER} user={{ name: "Sari Sales" }} onClose={onClose} />);
  expect(q(host, "m-amd-sheet").className).toMatch(/\bkn-modal-card\b/);
  for (const id of ["amd-principle-banner", "amd-reason-select", "amd-order-discount", "amd-note", "amd-att-name", "amd-att-url", "amd-att-add",
    "amd-item-qty-p1", "amd-item-price-p1", "amd-item-disc-p1"]) expect(q(host, id)).not.toBeNull();
  expect(q(host, "m-amd-submit")).toBeNull();                                // lembar HP ringkas lama sudah tidak ada
  expect(host.textContent).toContain("Diusulkan oleh Sari Sales");
  await act(async () => { typeInto(q(host, "amd-item-qty-p1"), "9"); });
  await act(async () => { typeInto(q(host, "amd-order-discount"), "2"); });
  await act(async () => { typeInto(q(host, "amd-att-name"), "Chat WA"); });
  await act(async () => { typeInto(q(host, "amd-att-url"), "https://contoh/1"); });
  await click(q(host, "amd-att-add"));
  await wait(520);                                                           // pratinjau di-debounce 450 ms
  expect(q(host, "amd-reason-auto")).not.toBeNull();                         // alur HP: alasan dipilih otomatis
  expect(q(host, "amd-preview-impact")).not.toBeNull();
  await click(q(host, "amd-propose-submit"));
  expect(mockPropose).toHaveBeenCalledWith(expect.objectContaining({
    doc_id: "so1", reason_code: "discount_grant", order_discount_percent: 2,
    changes: [{ product_id: "p1", field: "quantity", to: 9 }],
    attachments: [{ name: "Chat WA", url: "https://contoh/1" }],
  }));
  expect(q(host, "amd-result-status")).not.toBeNull();
  await click(q(host, "amd-result-done"));
  expect(onClose).toHaveBeenCalledWith(true);
});

test("Amandemen desktop: tanpa `autoReason` alasan tetap wajib dipilih manual (perilaku lama)", async () => {
  mockPreview.mockResolvedValue(PREVIEW);
  const { host } = await mount(<AmendmentProposeModal order={ORDER} currentUser={{ name: "Budi" }} onClose={() => {}} />);
  expect(q(host, "amd-propose-modal").className).toMatch(/\bkn-modal-card\b/);
  await act(async () => { typeInto(q(host, "amd-item-qty-p1"), "9"); });
  await wait(520);
  expect(q(host, "amd-reason-auto")).toBeNull();
  expect(q(host, "amd-propose-submit").disabled).toBe(true);
  expect(autoReasonFor([{ field: "price" }], false, [{ code: "price_correction" }])).toBe("price_correction");
  expect(autoReasonFor([{ field: "quantity" }], false, [{ code: "price_correction" }])).toBe("");   // kode tak aktif → manual
});

test("PR MD HP = PrCreateModal desktop: artikel → warna, supplier, alasan jalur, lokasi kirim; master seperti desktop", async () => {
  routeGet({ "/purchase-requisitions": [], "/products": [{ id: "p1", sku: "CR-1", name: "Ceruty", base_unit: "meter" }],
    "/warehouses": [], "/suppliers": [{ id: "s1", name: "PT Benang" }] });
  const { host } = await mount(<MobilePurchaseRequisitions selectedEntity="ent_a" />);
  await click(q(host, "m-pr-new"));
  await act(async () => {});
  expect(q(host, "pr-create-modal").className).toMatch(/\bkn-modal-card\b/);
  for (const id of ["pr-article-select", "pr-product-select", "pr-add-line", "pr-supplier", "pr-needed-by", "pr-reason",
    "pr-route-reason", "pr-submit-now", "pr-submit"]) expect(q(host, id)).not.toBeNull();
  expect(q(host, "m-pr-create")).toBeNull();
  const urls = mockGet.mock.calls.map(([u]) => u);
  for (const u of ["/api/products", "/api/warehouses", "/api/suppliers"]) expect(urls).toContain(u);
  expect(prCreatedText({ number: "PR-7", status: "approved" })).toBe("PR-7 diajukan & langsung disetujui.");
  expect(prCreatedText({ number: "PR-8", status: "draft" })).toBe("PR-8 tersimpan sebagai draf.");
});

test("Ubah SKU MD HP = VariantEditor desktop: varian dari induk (harga DASAR, versi supplier), bukan harga efektif PT", async () => {
  routeGet({
    "/products": [{ id: "p1", template_id: "t1", sku: "CR-1", name: "Ceruty Hitam", price: 120000, global_price: 100000, base_unit: "meter" },
      { id: "p2", sku: "LG-1", name: "Lawas", price: 90000, global_price: 80000, base_unit: "meter" }],
    "/product-templates/t1": { id: "t1", name: "Ceruty", variants: [{ id: "p1", sku: "CR-1", name: "Ceruty Hitam", price: 100000, source_name: "RAYON X" }] },
    "/stock-breakdown": {},
  });
  const { host } = await mount(<MobileMdProducts canEdit />);
  await click(q(host, "m-md-product-p1"));
  expect(q(host, "m-md-product-edit").textContent).toContain("Ubah SKU");
  expect(q(host, "m-md-product-form-name")).toBeNull();                      // 2 isian tanpa label lama sudah tidak ada
  await click(q(host, "m-md-product-edit"));
  expect(q(host, "stub-variant-editor")).not.toBeNull();
  expect(global.__r1Variant.template.id).toBe("t1");
  expect(global.__r1Variant.product).toMatchObject({ id: "p1", price: 100000, source_name: "RAYON X" });
  await click(q(host, "m-md-product-back"));
  await click(q(host, "m-md-product-p2"));                                   // produk lama tanpa induk → harga dasar global
  await click(q(host, "m-md-product-edit"));
  expect(global.__r1Variant.product).toMatchObject({ id: "p2", price: 80000 });
});

test("Alamat kirim & tindak lanjut HP → FormModal; pilihan hasil berlabel, isian ≥ desktop", async () => {
  routeGet({});
  const addr = await mount(<CustomerAddressSheet customer={{ id: "c1", name: "Toko A", pic_name: "Bu Ani" }} onClose={() => {}} />);
  expect(q(addr.host, "m-address-form").className).toMatch(/\bkn-modal-card\b/);
  expect(q(addr.host, "m-address-form-close")).not.toBeNull();
  expect(q(addr.host, "m-address-form-save").disabled).toBe(true);
  for (const t of ["Label alamat", "Nama penerima", "No. HP penerima", "Alamat lengkap", "Jadikan alamat utama"]) expect(addr.host.textContent).toContain(t);
  const fu = await mount(<CustomerFollowupSheet customer={{ id: "c1", name: "Toko A" }} orders={[{ id: "so1", number: "SO-1", grand_total: 1000 }]} onClose={() => {}} />);
  expect(q(fu.host, "m-followup-form").className).toMatch(/\bkn-modal-card\b/);
  expect(q(fu.host, "m-followup-form").querySelector("#m-followup-outcome-label").textContent).toBe("Hasil");
  expect(q(fu.host, "m-followup-outcome-paid").getAttribute("type")).toBe("button");   // di dalam <form>: tidak menyimpan
  for (const id of ["m-followup-order", "m-followup-note", "m-followup-date"]) expect(q(fu.host, id)).not.toBeNull();
  expect(q(fu.host, "m-followup-form-save").disabled).toBe(true);
});

test("Menu HP MD: Labdip/Handfeel/Proofing → SATU baris R&D Produk Baru (label menu desktop) mode Galeri", async () => {
  routeGet({ "/md/desk": { queues: [] } });
  const onOpenFull = jest.fn();
  const { host } = await mount(<MobileMdApp user={{ id: "u3", role: "md", name: "Rina", permissions: { product: ["view"] } }} onOpenFull={onOpenFull} />);
  await click(q(host, "m-md-tab-more"));
  for (const v of ["rnd-labdip", "rnd-handfeel", "rnd-proofing"]) expect(q(host, `m-md-full-${v}`)).toBeNull();
  const row = q(host, "m-md-full-rnd-samples");
  const desktopLabel = HUB_TABS["rnd-hub"].find((t) => t.view === "rnd-samples").label;
  expect(row.textContent).toContain(desktopLabel);
  expect(desktopLabel).toBe("R&D Produk Baru");
  await click(row);
  expect(onOpenFull).toHaveBeenCalledWith("rnd-hub", "rnd-samples", { preset: { mode: "gallery", type: "", purpose: "all" } });
  await click(q(host, "m-md-full-rnd-designs"));
  expect(onOpenFull).toHaveBeenLastCalledWith("designer-hub", "rnd-designs");   // baris lain tetap tanpa preset
});

test("PR HP (G5-60, temuan R7): nomor dokumen realisasi dari data server — PO atau Order Makloon; 'belum tercatat' hanya bila kosong", () => {
  const mko = { status: "converted", po_ids: [], makloon_order_ids: ["m1"],
    items: [{ realizations: [{ type: "makloon_order", ref_id: "m1", ref_number: "KDA/MKO-00003", qty: 10 }] }] };
  expect(prRealizationText(mko)).toBe(" · Order Makloon KDA/MKO-00003");               // dulu: "nomor PO belum tercatat"
  const mix = { status: "converted", items: [
    { realizations: [{ type: "purchase_order", ref_number: "PO-1" }, { type: "purchase_order", ref_number: "PO-0", voided: true }] },
    { realizations: [{ type: "makloon_order", ref_number: "MKO-2" }, { type: "purchase_order", ref_number: "PO-1" }] }] };
  expect(prRealizationText(mix)).toBe(" · PO PO-1, Order Makloon MKO-2");             // PO batal diabaikan, tanpa dobel
  expect(prRealizationText({ status: "approved", po_number: "PO-9", items: [] })).toBe(" · PO PO-9");
  expect(prRealizationText({ status: "converted", po_ids: [], makloon_order_ids: ["m1"], items: [] })).toBe(" · nomor Order Makloon belum tercatat");
  expect(prRealizationText({ status: "converted", po_ids: ["p1"], items: [] })).toBe(" · nomor PO belum tercatat");
  expect(prRealizationText({ status: "pending_approval", items: [] })).toBe("");
});

test("Pesanan HP (keputusan pemilik R5): Backorder = status Menunggu stok saja; SO hidup bersisa kurang stok = Sebagian menunggu stok", async () => {
  routeGet({});
  const item = [{ product_id: "p1", product_name: "Ceruty", quantity: 5, unit: "meter", price: 1000 }];
  const orders = [
    { id: "w1", number: "SO-W", status: "waiting_stock", customer_name: "A", items: item },
    { id: "c1", number: "SO-C", status: "confirmed", has_backorder: true, customer_name: "B", items: item },
    { id: "r1", number: "SO-R", status: "reserved", has_backorder: true, customer_name: "C", items: item },
    { id: "x1", number: "SO-X", status: "cancelled", has_backorder: true, customer_name: "D", items: item },
    { id: "d1", number: "SO-D", status: "delivered", has_backorder: true, customer_name: "E", items: item },
  ];
  const { host } = await mount(<MobileOrders orders={orders} role="sales_admin" user={{ role: "sales_admin" }} />);
  expect(q(host, "mobile-order-backorder-chip-w1").textContent).toBe("Backorder");
  expect(q(host, "mobile-order-partial-stock-chip-w1")).toBeNull();
  for (const id of ["c1", "r1"]) {
    expect(q(host, `mobile-order-backorder-chip-${id}`)).toBeNull();                   // dulu: has_backorder mentah
    expect(q(host, `mobile-order-partial-stock-chip-${id}`).textContent).toBe("Sebagian menunggu stok");
  }
  for (const id of ["x1", "d1"]) {                                                      // SO tutup: penanda basi diabaikan
    expect(q(host, `mobile-order-backorder-chip-${id}`)).toBeNull();
    expect(q(host, `mobile-order-partial-stock-chip-${id}`)).toBeNull();
  }
  // Admin Sales: "Keputusan pemenuhan" mengikuti helper yang sama (Menunggu stok / sebagian menunggu stok).
  await click(q(host, "mobile-order-w1").querySelector("button"));
  expect(q(host, "mobile-order-fulfill-w1")).not.toBeNull();
  await click(q(host, "mobile-order-r1").querySelector("button"));
  expect(q(host, "mobile-order-fulfill-r1")).not.toBeNull();
});
