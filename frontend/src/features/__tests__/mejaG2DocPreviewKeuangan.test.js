// Meja gelombang 2 · Tugas 2 — isi pratinjau dokumen keuangan: tagihan pemasok, PO, kwitansi, kontrabon.
import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";
import AppNavContext from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import DocPreviewModal from "../documents/preview/DocPreviewModal";
import { canPreview, previewFor } from "../documents/preview/docPreviewRegistry";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
Element.prototype.scrollIntoView = () => {};

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), defaults: { headers: { common: {} } } },
  API: "/api",
}));

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
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
const wrap = (el, nav = {}) => (
  <AppNavContext.Provider value={{ openDocument: () => {}, openCustomerCard: () => {}, openSupplierCard: () => {}, cardsEnabled: true, ...nav }}>
    <EntityScopeProvider selectedEntity="all" entities={ENTS}>{el}</EntityScopeProvider>
  </AppNavContext.Provider>
);
const PERMS = { order: ["view"], vendor_bill: ["view"], purchase_order: ["view"], ar_receipt: ["view"], contra_bon: ["view"], supplier: ["view"] };
const buka = (docType, docId, nav, perms = PERMS) => mount(wrap(
  <DocPreviewModal target={{ docType, docId }} onClose={() => {}} currentUser={{ permissions: perms }} />, nav));

test("registri: empat jenis keuangan terdaftar dengan izin baca", () => {
  expect(previewFor("vendor_bill").perm).toEqual(["vendor_bill", "view"]);
  expect(previewFor("purchase_order").perm).toEqual(["purchase_order", "view"]);
  expect(previewFor("ar_receipt").perm).toEqual(["ar_receipt", "view"]);
  expect(previewFor("contra_bon").perm).toEqual(["contra_bon", "view"]);
  expect(canPreview({}, "vendor_bill")).toBe(false);
  expect(canPreview(PERMS, "contra_bon")).toBe(true);
});

test("tagihan pemasok: kolom barang", async () => {
  mockGet.mockResolvedValue({ data: { id: "vb1", bill_number: "VB-1", supplier_id: "s1", supplier_name: "CV Benang", status: "approved", entity_id: "ent_ksc",
    po_number: "PO-9", supplier_invoice_no: "INV-77", grand_total: 1110000, ppn_amount: 110000,
    items: [{ product_name: "Benang A", sku: "BA-1", billed_qty: 10, price: 100000, line_total: 1000000 }] } });
  await buka("vendor_bill", "vb1");
  expect(mockGet).toHaveBeenCalledWith("/api/vendor-bills/vb1");
  const lines = teks(q("doc-preview-lines"));
  expect(lines).toContain("Benang A");
  expect(lines).toContain("BA-1");
  expect(lines).toContain("Rp 100.000");
  expect(lines).toContain("Rp 1.000.000");
  expect(teks(q("doc-preview-totals"))).toContain("Rp 1.110.000");
  expect(teks(q("doc-preview-facts"))).toContain("CV Benang");
  expect(teks(q("doc-preview-facts"))).toContain("INV-77");
});

test("PO: baris barang + status terima", async () => {
  mockGet.mockResolvedValue({ data: { id: "po1", po_number: "PO-1", supplier_id: "s1", supplier_name: "CV Benang", status: "approved", entity_id: "ent_ksc",
    items: [{ product_name: "Benang A", sku: "BA-1", quantity: 10, unit: "kg", price: 100000, received_qty: 4 }],
    total_amount: 1000000, ppn_amount: 110000, grand_total: 1110000 } });
  await buka("purchase_order", "po1");
  expect(mockGet).toHaveBeenCalledWith("/api/purchase-orders/po1");
  const lines = teks(q("doc-preview-lines"));
  expect(lines).toContain("Benang A");
  expect(lines).toContain("10 kg");
  expect(lines).toContain("4 dari 10");
  expect(teks(q("doc-preview-totals"))).toContain("Rp 1.110.000");
  expect(q("doc-preview-full")).toBeTruthy();
});

test("kwitansi: alokasi bisa dibuka; baris tanpa order_id teks biasa", async () => {
  mockGet.mockResolvedValue({ data: { id: "r1", number: "KSC/RC-1", customer_id: "c1", customer_name: "Toko A", amount: 105000, status: "posted", entity_id: "ent_ksc",
    receipt_date: "2026-11-20", allocations: [
      { order_id: "so1", order_number: "KSC/SO-00001", applied: 100000 },
      { order_number: "LAMA-1", applied: 5000 }] } });
  await buka("ar_receipt", "r1");
  expect(mockGet).toHaveBeenCalledWith("/api/ar-receipts/r1");
  const baris = document.body.querySelectorAll('[data-testid="doc-preview-lines"] tbody tr');
  expect(baris.length).toBe(2);
  expect(baris[0].querySelector("button")).toBeTruthy();
  expect(baris[1].querySelector("button")).toBeNull();
  expect(baris[1].textContent).toContain("LAMA-1");
  expect(teks(baris[0])).toContain("Rp 100.000");
  // tumpuk: kwitansi → pesanan → Kembali
  mockGet.mockResolvedValueOnce({ data: { id: "so1", number: "KSC/SO-00001", items: [], total_amount: 100000 } });
  await klik(baris[0].querySelector("button")); await act(async () => {});
  expect(mockGet).toHaveBeenCalledWith("/api/sales-orders/so1");
  expect(q("doc-preview-back")).toBeTruthy();
  await klik(q("doc-preview-back")); await act(async () => {});
  expect(teks(q("doc-preview-title"))).toContain("KSC/RC-1");
});

test("kwitansi: tanpa izin pesanan, alokasi teks biasa", async () => {
  mockGet.mockResolvedValue({ data: { id: "r1", number: "KSC/RC-1", amount: 100000,
    allocations: [{ order_id: "so1", order_number: "KSC/SO-00001", applied: 100000 }] } });
  await buka("ar_receipt", "r1", undefined, { ar_receipt: ["view"] });
  expect(document.body.querySelector('[data-testid="doc-preview-lines"] tbody button')).toBeNull();
  expect(teks(q("doc-preview-lines"))).toContain("KSC/SO-00001");
});

const CB = { id: "cb1", number: "CB-1", supplier_name: "CV Benang", status: "approved", entity_id: "ent_ksc",
  totals: { bills_total: 2000000, deductions_total: 0, net_payable: 2000000, paid_total: 0 },
  bills: [{ bill_id: "b1", bill_number: "VB-1" }, { bill_id: "b2", bill_number: "VB-2" }] };
const BILL = (id, nama) => ({ id, bill_number: `VB-${id.slice(1)}`, items: [{ product_name: nama, sku: "X", billed_qty: 1, price: 1000, line_total: 1000 }] });

test("kontrabon: gabungan baris faktur, dikelompokkan per faktur", async () => {
  mockGet.mockImplementation(async (url) => {
    if (url === "/api/contra-bons/cb1") return { data: CB };
    if (url === "/api/vendor-bills/b1") return { data: BILL("b1", "Benang A") };
    if (url === "/api/vendor-bills/b2") return { data: BILL("b2", "Benang B") };
    throw new Error(url);
  });
  await buka("contra_bon", "cb1");
  expect(mockGet).toHaveBeenCalledWith("/api/vendor-bills/b1");
  expect(mockGet).toHaveBeenCalledWith("/api/vendor-bills/b2");
  const isi = teks(q("doc-preview-cb-bills"));
  expect(isi).toContain("Benang A");
  expect(isi).toContain("Benang B");
  expect(isi.indexOf("VB-1")).toBeLessThan(isi.indexOf("Benang A"));
  expect(isi.indexOf("Benang A")).toBeLessThan(isi.indexOf("VB-2"));
  expect(teks(q("doc-preview-totals"))).toContain("Rp 2.000.000");
  // nomor faktur membuka pratinjau tagihan (tumpuk)
  await klik(q("doc-preview-cb-bill-b2")); await act(async () => {});
  expect(teks(q("doc-preview-title"))).toContain("VB-2");
  expect(q("doc-preview-back")).toBeTruthy();
});

test("kontrabon: satu faktur gagal → galat di kelompoknya saja", async () => {
  mockGet.mockImplementation(async (url) => {
    if (url === "/api/contra-bons/cb1") return { data: CB };
    if (url === "/api/vendor-bills/b1") return { data: BILL("b1", "Benang A") };
    throw { response: { status: 404, data: { detail: "Vendor Bill tidak ditemukan" } } };
  });
  await buka("contra_bon", "cb1");
  expect(teks(q("doc-preview-cb-bills"))).toContain("Benang A");
  expect(teks(q("doc-preview-cb-bill-error-b2"))).toContain("Vendor Bill tidak ditemukan");
  expect(q("doc-preview-cb-bill-error-b1")).toBeNull();
});

test("kontrabon: paling banyak 20 faktur dimuat", async () => {
  const bills = Array.from({ length: 25 }, (_, i) => ({ bill_id: `b${i + 1}`, bill_number: `VB-${i + 1}` }));
  mockGet.mockImplementation(async (url) => {
    if (url === "/api/contra-bons/cb1") return { data: { ...CB, bills } };
    const id = url.split("/").pop();
    return { data: BILL(id, `Barang ${id}`) };
  });
  await buka("contra_bon", "cb1");
  const faktur = mockGet.mock.calls.filter((c) => String(c[0]).startsWith("/api/vendor-bills/"));
  expect(faktur.length).toBe(20);
  expect(teks(q("doc-preview-cb-cap"))).toContain("Tampil 20 faktur pertama");
});

test("kontrabon tanpa izin tagihan: nomor faktur teks biasa", async () => {
  mockGet.mockImplementation(async (url) => (url === "/api/contra-bons/cb1" ? { data: CB } : { data: BILL(url.split("/").pop(), "Benang") }));
  await buka("contra_bon", "cb1", undefined, { contra_bon: ["view"] });
  expect(q("doc-preview-cb-bill-b1")).toBeNull();
  expect(teks(q("doc-preview-cb-bills"))).toContain("VB-1");
});

test("isi pratinjau keuangan bebas px, hex, button bergaya sendiri", () => {
  const dir = path.join(__dirname, "..", "documents", "preview", "bodies");
  ["VendorBillPreview", "PurchaseOrderPreview", "ArReceiptPreview", "ContraBonPreview"].forEach((n) => {
    const isi = fs.readFileSync(path.join(dir, `${n}.jsx`), "utf8");
    expect([n, /text-\[\d/.test(isi)]).toEqual([n, false]);
    expect([n, /#[0-9A-Fa-f]{3,6}\b/.test(isi)]).toEqual([n, false]);
    expect([n, /\|\|\s*\w+\.id\b/.test(isi)]).toEqual([n, false]);
  });
});
