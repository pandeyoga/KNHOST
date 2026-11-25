// Meja gelombang 2 · Tugas 6 — registri panel meja per antrean + pratinjau dokumen di pop-up meja.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import AppNavContext from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import DeskRowDetail from "../desks/DeskRowDetail";
import { DESK_DOC_OF, DESK_PANELS, docOfRow, panelFor } from "../desks/deskPanels";
import { trackerRowToDeskRow } from "../sales_admin/SoTrackerCard";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
Element.prototype.scrollIntoView = () => {};

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), defaults: { headers: { common: {} } } },
  API: "/api",
}));

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const semua = (id) => document.body.querySelectorAll(`[data-testid="${id}"]`);
const teks = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");
let roots = [];
async function mount(el) {
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host); roots.push(root);
  await act(async () => { root.render(el); }); await act(async () => {}); await act(async () => {});
  return host;
}
const klik = async (el) => act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
afterEach(async () => { for (const r of roots) await act(async () => r.unmount()); roots = []; document.body.innerHTML = ""; mockGet.mockReset(); });

const ENTS = [{ id: "ent_ksc", short_name: "KSC" }];
const wrap = (el) => (
  <AppNavContext.Provider value={{ openDocument: () => {}, openCustomerCard: () => {}, openSupplierCard: () => {}, cardsEnabled: true }}>
    <EntityScopeProvider selectedEntity="all" entities={ENTS}>{el}</EntityScopeProvider>
  </AppNavContext.Provider>
);
const PERMS = { order: ["view"], ar_receipt: ["view"], contra_bon: ["view"], purchase_order: ["view"] };
const USER = { permissions: PERMS };
const SO1 = { id: "so1", number: "KSC/SO-00001", customer_id: "c1", customer_name: "Toko A", entity_id: "ent_ksc", status: "confirmed",
  created_at: "2026-11-20T03:00:00Z", items: [{ product_name: "Katun A", sku: "KA-01", quantity: 10, unit: "meter", price: 25000, subtotal: 250000 }],
  total_amount: 250000, grand_total: 277500, ppn_amount: 27500, paid_total: 0 };
const ROW = { ref_type: "sales_order", ref_id: "so1", number: "KSC/SO-00001", title: "Toko A", subtitle: "Menunggu verifikasi sales", value: 277500,
  age_days: 3, entity_id: "ent_ksc", action: "Lihat", action_kind: "open" };
const QUEUE = { id: "menunggu_manajer", label: "Menunggu manajer", value_label: "Nilai" };
const buka = (row, queue = QUEUE, user = USER, extra = {}) => mount(wrap(
  <DeskRowDetail row={row} queue={queue} currentUser={user} onClose={() => {}} onAction={() => {}} onOpenFull={() => {}} {...extra} />));

test("registri: tabel pemetaan dan pencarian kunci antrean lebih dulu, lalu ref_type", () => {
  expect(DESK_DOC_OF["queue:uang_masuk"]).toBeTruthy();
  expect(DESK_DOC_OF.customer).toBeUndefined();          // dua arti → Tugas 8
  expect(panelFor(ROW, QUEUE)).toBe(DESK_PANELS.sales_order);
  expect(panelFor({ ref_type: "customer", ref_id: "c1" }, { id: "pelanggan_tanpa_sales" })).toBeNull();
  expect(panelFor({ ref_type: "customer", ref_id: "c1" }, { id: "uang_masuk" })).toBe(DESK_PANELS["queue:uang_masuk"]);
  expect(docOfRow({ ref_type: "customer", ref_id: "c1", order_id: "so9" }, { id: "uang_masuk" })).toEqual({ docType: "sales_order", docId: "so9" });
  expect(docOfRow({ ref_type: "penalty", doc_type: "sales_order", doc_id: "so5" }, { id: "denda_draft" })).toEqual({ docType: "sales_order", docId: "so5" });
  expect(docOfRow({ ref_type: "penalty", doc_type: "plan", doc_id: "p5" }, { id: "denda_draft" })).toBeNull();
});

test("baris SO membuka pratinjau pesanan di pop-up meja", async () => {
  mockGet.mockResolvedValue({ data: SO1 });
  await buka(ROW);
  expect(mockGet).toHaveBeenCalledWith("/api/sales-orders/so1");
  expect(teks(q("doc-preview-lines"))).toContain("Katun A");
  // fakta ringkas baris tetap di atas, kaki pop-up tetap punya aksi + layar penuh
  expect(teks(q("desk-detail-field-subtitle"))).toContain("Menunggu verifikasi sales");
  expect(q("desk-detail-action")).toBeTruthy();
  expect(q("desk-detail-open-full")).toBeTruthy();
  expect(teks(q("desk-detail-title"))).toContain("KSC/SO-00001 · Toko A");
});

test("uang masuk memakai order_id, bukan ref_id pelanggan", async () => {
  mockGet.mockResolvedValue({ data: SO1 });
  await buka({ ref_type: "customer", ref_id: "cus_9", order_id: "so1", number: "KSC/SO-00001", title: "Toko A", value: 1, action: "Terima pembayaran", action_kind: "receipt" },
    { id: "uang_masuk", label: "Uang masuk" });
  expect(mockGet).toHaveBeenCalledTimes(1);
  expect(mockGet).toHaveBeenCalledWith("/api/sales-orders/so1");
  expect(q("doc-preview-lines")).toBeTruthy();
});

test("tanpa izin baca → panel umum, tanpa memuat", async () => {
  await buka(ROW, QUEUE, { permissions: {} });
  expect(mockGet).not.toHaveBeenCalled();
  expect(q("desk-detail-field-subtitle")).toBeTruthy();
  expect(q("doc-preview-lines")).toBeNull();
});

test("baris tanpa id dokumen → panel umum", async () => {
  await buka({ ...ROW, ref_type: "customer", ref_id: "c1" }, { id: "bayar_sebelum_kirim" });   // tanpa order_id
  expect(mockGet).not.toHaveBeenCalled();
  expect(q("desk-detail-field-subtitle")).toBeTruthy();
});

test("Pelacak SO ikut pratinjau", async () => {
  mockGet.mockResolvedValue({ data: SO1 });
  const row = trackerRowToDeskRow({ id: "so1", number: "KSC/SO-00001", customer_name: "Toko A", next_step: "Kirim", owner_label: "Gudang",
    grand_total: 277500, idle_days: 2, created_at: "2026-11-20T03:00:00Z", status: "confirmed", entity_id: "ent_ksc", can_act: false });
  await buka(row, { id: "pelacak_so", title: "Pelacak SO", value_label: "Nilai", value_kind: "money" });
  expect(mockGet).toHaveBeenCalledWith("/api/sales-orders/so1");
  expect(teks(q("doc-preview-lines"))).toContain("Katun A");
});

test("pemetaan antrean lain: selisih → kwitansi, kontrabon papan, PO, denda berdasar doc_id", async () => {
  mockGet.mockResolvedValue({ data: { id: "x", number: "N-1", items: [], allocations: [] } });
  await buka({ ref_type: "ar_receipt", ref_id: "rc1", number: "KW-1", title: "Toko A", order_ids: ["so1"] }, { id: "selisih_bayar" });
  expect(mockGet).toHaveBeenLastCalledWith("/api/ar-receipts/rc1");
  document.body.innerHTML = "";
  await buka({ ref_type: "contra_bon_verify", ref_id: "cb1", number: "KB-1", title: "Pemasok" }, { id: "kontrabon" });
  expect(mockGet).toHaveBeenLastCalledWith("/api/contra-bons/cb1");
  document.body.innerHTML = "";
  await buka({ ref_type: "purchase_order", ref_id: "po1", number: "PO-1", title: "Pemasok" }, { id: "hutang_jatuh_tempo" });
  expect(mockGet).toHaveBeenLastCalledWith("/api/purchase-orders/po1");
  document.body.innerHTML = "";
  await buka({ ref_type: "penalty", ref_id: "pn1", doc_type: "sales_order", doc_id: "so7", number: "DN-1", title: "Toko A" }, { id: "denda_draft" });
  expect(mockGet).toHaveBeenLastCalledWith("/api/sales-orders/so7");
  document.body.innerHTML = "";
  mockGet.mockClear();
  await buka({ ref_type: "penalty", ref_id: "pn1", doc_type: "payment_plan", doc_id: "pl1", number: "DN-1", title: "Toko A" }, { id: "denda_draft" });
  expect(mockGet).not.toHaveBeenCalled();
  expect(q("desk-detail-field-value") || q("desk-detail-title")).toBeTruthy();
});

test("galat muat → ErrorNotice di panel dengan Coba lagi, fakta baris tetap tampil", async () => {
  mockGet.mockRejectedValueOnce({ response: { status: 404, data: { detail: "Order tidak ditemukan" } } });
  mockGet.mockResolvedValueOnce({ data: SO1 });
  await buka(ROW);
  expect(teks(q("doc-preview-error"))).toContain("Order tidak ditemukan");
  expect(q("desk-detail-field-subtitle")).toBeTruthy();
  const retry = Array.from(q("doc-preview-error").querySelectorAll("button")).find((b) => /Coba lagi/.test(b.textContent));
  await klik(retry);
  expect(q("doc-preview-lines")).toBeTruthy();
});

test("satu DetailModal: pop-up meja tidak merender DocPreviewModal; push bertumpuk di dalam panel + Kembali", async () => {
  mockGet.mockImplementation(async (url) => {
    if (url.endsWith("/ar-receipts/rc1")) return { data: { id: "rc1", number: "KW-1", entity_id: "ent_ksc", status: "posted", amount: 1000,
      allocations: [{ order_id: "so1", order_number: "KSC/SO-00001", applied: 1000 }] } };
    return { data: SO1 };
  });
  await buka({ ref_type: "ar_receipt", ref_id: "rc1", number: "KW-1", title: "Toko A", subtitle: "lebih bayar" }, { id: "selisih_bayar" });
  expect(semua("desk-detail")).toHaveLength(1);
  expect(document.body.querySelectorAll('[role="dialog"]')).toHaveLength(1);
  expect(q("doc-preview")).toBeNull();
  await klik(q("doc-preview-alloc-0"));
  expect(teks(q("doc-preview-lines"))).toContain("Katun A");
  expect(document.body.querySelectorAll('[role="dialog"]')).toHaveLength(1);
  expect(q("doc-preview")).toBeNull();
  await klik(q("desk-doc-back"));
  expect(q("doc-preview-alloc-0")).toBeTruthy();
  expect(document.body.querySelectorAll('[role="dialog"]')).toHaveLength(1);
});

test("kelompok Meja Keuangan: antrean asal dibaca dari row._queue (id kelompok 'denda' ≠ 'denda_draft')", async () => {
  mockGet.mockResolvedValue({ data: SO1 });
  await buka({ ref_type: "penalty", ref_id: "pn1", doc_type: "sales_order", doc_id: "so1", number: "DN-1", title: "Toko A", _queue: "denda_draft" },
    { id: "denda", label: "Denda perlu diterbitkan" });
  expect(mockGet).toHaveBeenCalledWith("/api/sales-orders/so1");
});

test("fakta baris lengkap di atas pratinjau: Batas cadangan, Masuk, Kota; tanpa lencana/PT/umur (ada di judul)", async () => {
  mockGet.mockResolvedValue({ data: SO1 });
  await buka({ ...ROW, badge: "reserved", booking_until: "2026-11-30T10:00:00Z", at: "2026-11-20T03:00:00Z", customer_city: "Bandung" },
    { id: "perlu_verifikasi", value_label: "Nilai" });
  expect(teks(q("desk-detail-field-booking_until"))).toMatch(/Batas cadangan/);
  expect(teks(q("desk-detail-field-at"))).toMatch(/Masuk/);
  expect(teks(q("desk-detail-field-customer_city"))).toContain("Bandung");
  expect(q("desk-detail-field-badge")).toBeNull();
  expect(q("desk-detail-field-entity_id")).toBeNull();
  expect(q("desk-detail-field-age")).toBeNull();
  expect(q("doc-preview-lines")).toBeTruthy();
});

test("perlu_dipenuhi: tabel kurang stok tetap; siap_dikonfirmasi: tabel order_lines tidak diulang", async () => {
  mockGet.mockResolvedValue({ data: SO1 });
  await buka({ ...ROW, lines: [{ product_name: "Kain K", backorder_qty: 5, unit: "yard" }] }, { id: "perlu_dipenuhi" });
  expect(teks(q("desk-detail-shortage"))).toContain("Kain K");
  document.body.innerHTML = "";
  await buka({ ...ROW, order_lines: [{ product_name: "Kain G", quantity: 3, unit: "yard", warehouse: "Gudang A" }] }, { id: "siap_dikonfirmasi" });
  expect(q("desk-detail-lines")).toBeNull();
  expect(q("doc-preview-lines")).toBeTruthy();
});

test("papan vendor_bill membuka pratinjau tagihan", async () => {
  mockGet.mockResolvedValue({ data: { id: "vb1", bill_number: "TG-1", items: [], lines: [] } });
  await buka({ ref_type: "vendor_bill", ref_id: "vb1", number: "TG-1", title: "Pemasok" }, { id: "hutang_jatuh_tempo" },
    { permissions: { vendor_bill: ["view"] } });
  expect(mockGet).toHaveBeenCalledWith("/api/vendor-bills/vb1");
});
