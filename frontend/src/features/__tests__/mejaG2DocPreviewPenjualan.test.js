// Meja gelombang 2 · Tugas 3 — isi pratinjau dokumen penjualan lain: retur, pesanan khusus, permintaan internal.
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
const wrap = (el) => (
  <AppNavContext.Provider value={{ openDocument: () => {}, openCustomerCard: () => {}, openSupplierCard: () => {}, cardsEnabled: true }}>
    <EntityScopeProvider selectedEntity="all" entities={ENTS}>{el}</EntityScopeProvider>
  </AppNavContext.Provider>
);
const PERMS = { order: ["view"], sales_return: ["view"], internal_request: ["view"], customer: ["view"] };
const buka = (docType, docId, perms = PERMS) => mount(wrap(
  <DocPreviewModal target={{ docType, docId }} onClose={() => {}} currentUser={{ permissions: perms }} />));

test("registri: tiga jenis penjualan terdaftar dengan izin baca sesuai rute GET", () => {
  expect(previewFor("sales_return").perm).toEqual(["sales_return", "view"]);
  // rute GET /special-orders/{id} memeriksa ("order","view"), bukan sumber daya terpisah
  expect(previewFor("special_order").perm).toEqual(["order", "view"]);
  expect(previewFor("internal_request").perm).toEqual(["internal_request", "view"]);
  expect(canPreview({}, "sales_return")).toBe(false);
  expect(canPreview(PERMS, "internal_request")).toBe(true);
});

const RET = { id: "rt1", number: "KSC/RT-00001", return_type: "retur", status: "pending_approval", entity_id: "ent_ksc",
  order_id: "so1", order_number: "KSC/SO-00001", customer_id: "c1", customer_name: "Toko A", created_at: "2026-11-20T03:00:00Z",
  created_by: "Sari", reason: "Warna tidak sesuai pesanan", notes: "Pelanggan minta ganti",
  items: [
    { product_id: "p1", product_name: "Katun Combed", sku: "KC-1", quantity_returned: 30, unit: "meter", qty_rolls: 2, condition: "damaged", reason: "Cacat tenun" },
    { product_id: "p2", product_name: "Rayon", sku: "RY-1", quantity_returned: 10, unit: "meter", condition: "ok", reason: "" }] };

test("retur: fakta berlabel Indonesia, alasan utuh, tabel barang dengan kondisi/alasan", async () => {
  mockGet.mockResolvedValue({ data: RET });
  await buka("sales_return", "rt1");
  expect(mockGet).toHaveBeenCalledWith("/api/sales-returns/rt1");
  const f = teks(q("doc-preview-facts"));
  expect(f).toContain("Toko A");
  expect(f).toContain("KSC/SO-00001");
  expect(f).toContain("Warna tidak sesuai pesanan");
  expect(f).toContain("Pelanggan minta ganti");
  expect(f).toContain("Retur");
  expect(teks(q("doc-preview-status"))).toBe("Menunggu Persetujuan");
  const lines = teks(q("doc-preview-lines"));
  expect(lines).toContain("Katun Combed");
  expect(lines).toContain("KC-1");
  expect(lines).toContain("30");
  expect(lines).toContain("Rusak");
  expect(lines).toContain("Cacat tenun");
  expect(lines).toContain("Rayon");
  expect(lines).toContain("Baik");
});

test("retur: pesanan asal bisa dibuka (tumpuk) bila ada izin pesanan", async () => {
  mockGet.mockResolvedValue({ data: RET });
  await buka("sales_return", "rt1");
  const tombol = q("doc-preview-return-order");
  expect(tombol.tagName).toBe("BUTTON");
  mockGet.mockResolvedValueOnce({ data: { id: "so1", number: "KSC/SO-00001", items: [], total_amount: 1000 } });
  await klik(tombol); await act(async () => {});
  expect(mockGet).toHaveBeenCalledWith("/api/sales-orders/so1");
  expect(q("doc-preview-back")).toBeTruthy();
  await klik(q("doc-preview-back")); await act(async () => {});
  expect(teks(q("doc-preview-title"))).toContain("KSC/RT-00001");
});

test("retur: tanpa izin pesanan atau tanpa order_id, nomor pesanan teks biasa", async () => {
  mockGet.mockResolvedValue({ data: RET });
  await buka("sales_return", "rt1", { sales_return: ["view"] });
  expect(q("doc-preview-return-order")).toBeNull();
  expect(teks(q("doc-preview-facts"))).toContain("KSC/SO-00001");
  await act(async () => {});
});

const SO = { id: "sp1", number: "KSC/OD-00001", status: "confirmed", entity_id: "ent_ksc", customer_name: "Butik B", title: "Kain athena warna khusus",
  created_at: "2026-11-18T03:00:00Z", created_by_name: "Rani", total_amount: 5000000, expected_delivery: "2026-12-10", notes: "Sample dulu",
  items: [
    { id: "i1", description: "Athena biru dongker", quantity: 100, unit: "meter", target_price: 50000, notes: "Lebar 150" },
    { id: "i2", description: "Athena batal", quantity: 5, unit: "meter", target_price: 1000, status: "cancelled" }] };

test("pesanan khusus: fakta, catatan utuh, tabel item (item batal tidak ikut)", async () => {
  mockGet.mockResolvedValue({ data: SO });
  await buka("special_order", "sp1");
  expect(mockGet).toHaveBeenCalledWith("/api/special-orders/sp1");
  const f = teks(q("doc-preview-facts"));
  expect(f).toContain("Butik B");
  expect(f).toContain("Kain athena warna khusus");
  expect(f).toContain("Sample dulu");
  expect(teks(q("doc-preview-status"))).toBe("Terkonfirmasi");
  const lines = teks(q("doc-preview-lines"));
  expect(lines).toContain("Athena biru dongker");
  expect(lines).toContain("100 meter");
  expect(lines).toContain("Rp 50.000");
  expect(lines).not.toContain("Athena batal");
  expect(teks(q("doc-preview-totals"))).toContain("Rp 5.000.000");
});

test("pesanan khusus: status draf berlabel Indonesia; tanpa item → baris kosong", async () => {
  mockGet.mockResolvedValue({ data: { ...SO, status: "draft", items: [] } });
  await buka("special_order", "sp1");
  expect(teks(q("doc-preview-status"))).toBe("Draf");
  expect(q("doc-preview-lines-empty")).toBeTruthy();
});

const PIN = { id: "pin1", number: "KSC/PIN-00001", status: "submitted", entity_id: "ent_ksc", requested_by: "Budi", requester_entity_name: "PT Kain Satu",
  reason: "Stok habis, pelanggan menunggu", needed_date: "2026-12-01", source_order_number: "KSC/SO-00009", source_entity_name: "PT Kain Dua",
  est_value: 2500000, decision_reason: "",
  items: [{ product_id: "p1", product_name: "Katun Combed", sku: "KC-1", quantity: 50, unit: "meter", qty_rolls: 3, est_value: 2500000, notes: "warna putih" }] };

test("permintaan internal: fakta, alasan, tabel barang", async () => {
  mockGet.mockResolvedValue({ data: PIN });
  await buka("internal_request", "pin1");
  expect(mockGet).toHaveBeenCalledWith("/api/internal-requests/pin1");
  const f = teks(q("doc-preview-facts"));
  expect(f).toContain("Stok habis, pelanggan menunggu");
  expect(f).toContain("PT Kain Satu");
  expect(f).toContain("PT Kain Dua");
  expect(f).toContain("KSC/SO-00009");
  expect(teks(q("doc-preview-status"))).toBe("Menunggu ditindak");
  const lines = teks(q("doc-preview-lines"));
  expect(lines).toContain("Katun Combed");
  expect(lines).toContain("KC-1");
  expect(lines).toContain("50");
  expect(lines).toContain("warna putih");
  expect(teks(q("doc-preview-totals"))).toContain("Rp 2.500.000");
});

test("permintaan internal ditolak: alasan keputusan tampil", async () => {
  mockGet.mockResolvedValue({ data: { ...PIN, status: "rejected", decision_reason: "Stok sumber tidak cukup" } });
  await buka("internal_request", "pin1");
  expect(teks(q("doc-preview-status"))).toBe("Ditolak");
  expect(teks(q("doc-preview-facts"))).toContain("Stok sumber tidak cukup");
});

test("isi pratinjau penjualan bebas px, hex, || x.id", () => {
  const dir = path.join(__dirname, "..", "documents", "preview", "bodies");
  ["SalesReturnPreview", "SpecialOrderPreview", "InternalRequestPreview"].forEach((n) => {
    const isi = fs.readFileSync(path.join(dir, `${n}.jsx`), "utf8");
    expect([n, /text-\[\d/.test(isi)]).toEqual([n, false]);
    expect([n, /#[0-9A-Fa-f]{3,6}\b/.test(isi)]).toEqual([n, false]);
    expect([n, /\|\|\s*\w+\.id\b/.test(isi)]).toEqual([n, false]);
  });
});
