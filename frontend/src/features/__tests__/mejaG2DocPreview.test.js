// Meja gelombang 2 · Tugas 1 — fondasi pratinjau dokumen (registri, DocPreviewModal, DocLink) + isi pesanan penjualan.
import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";
import AppNavContext from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import DocPreviewModal from "../documents/preview/DocPreviewModal";
import DocLink from "../documents/preview/DocLink";
import { DOC_PREVIEWS, canPreview, previewFor } from "../documents/preview/docPreviewRegistry";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
Element.prototype.scrollIntoView = () => {};   // jsdom tidak punya; ErrorNotice menggulir dirinya ke tampilan

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
  await act(async () => { root.render(el); }); await act(async () => {});
  return host;
}
const klik = async (el) => act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
afterEach(async () => { for (const r of roots) await act(async () => r.unmount()); roots = []; document.body.innerHTML = ""; mockGet.mockReset(); });

const ENTS = [{ id: "ent_ksc", short_name: "KSC" }];
const wrap = (el, nav = {}) => (
  <AppNavContext.Provider value={{ openDocument: () => {}, openCustomerCard: () => {}, cardsEnabled: true, ...nav }}>
    <EntityScopeProvider selectedEntity="all" entities={ENTS}>{el}</EntityScopeProvider>
  </AppNavContext.Provider>
);
const SO1 = { id: "so1", number: "KSC/SO-00001", customer_id: "c1", customer_name: "Toko A", entity_id: "ent_ksc", status: "confirmed",
  sales_name: "Ayu", payment_status: "unpaid", created_at: "2026-11-20T03:00:00Z",
  items: [{ product_name: "Katun A", sku: "KA-01", quantity: 10, unit: "meter", price: 25000, subtotal: 250000 }],
  total_amount: 250000, grand_total: 277500, ppn_amount: 27500, paid_total: 0 };
const PERMS = { order: ["view"] };

test("pratinjau pesanan menampilkan baris barang", async () => {
  mockGet.mockResolvedValue({ data: SO1 });
  await mount(wrap(<DocPreviewModal target={{ docType: "sales_order", docId: "so1" }} onClose={() => {}} currentUser={{ permissions: PERMS }} />));
  expect(mockGet).toHaveBeenCalledWith("/api/sales-orders/so1");
  const lines = teks(q("doc-preview-lines"));
  expect(lines).toContain("Katun A");
  expect(lines).toContain("KA-01");
  expect(lines).toContain("10 meter");
  expect(lines).toContain("Rp 25.000");
  expect(teks(q("doc-preview-totals"))).toContain("Rp 277.500");
  expect(teks(q("doc-preview-facts"))).toContain("Toko A");
  expect(teks(q("doc-preview-facts"))).toContain("KSC");
  expect(q("doc-preview-trace")).toBeTruthy();
  expect(q("doc-preview-full")).toBeTruthy();
});

test("galat muat menampilkan ErrorNotice dan coba lagi", async () => {
  mockGet.mockRejectedValueOnce({ response: { status: 404, data: { detail: "Order tidak ditemukan" } } });
  mockGet.mockResolvedValueOnce({ data: SO1 });
  await mount(wrap(<DocPreviewModal target={{ docType: "sales_order", docId: "so1" }} onClose={() => {}} currentUser={{ permissions: PERMS }} />));
  expect(q("doc-preview-error")).toBeTruthy();
  expect(teks(q("doc-preview-error"))).toContain("Order tidak ditemukan");
  const retry = Array.from(q("doc-preview-error").querySelectorAll("button")).find((b) => /Coba lagi/.test(b.textContent));
  await klik(retry);
  expect(mockGet).toHaveBeenCalledTimes(2);
  expect(q("doc-preview-lines")).toBeTruthy();
});

test("izin berubah (403) tetap menampilkan pesan, bukan kosong", async () => {
  mockGet.mockRejectedValue({ response: { status: 403, data: { detail: "Anda tidak punya izin membuka pesanan." } } });
  await mount(wrap(<DocPreviewModal target={{ docType: "sales_order", docId: "so1" }} onClose={() => {}} currentUser={{ permissions: PERMS }} />));
  expect(teks(q("doc-preview-error"))).toContain("tidak punya izin");
});

test("target PT lain: PT dokumen diingat untuk pemuatan (header lewat interseptor apiClient)", async () => {
  const { docEntityFor } = require("../../services/docEntityRegistry");
  mockGet.mockResolvedValue({ data: { ...SO1, id: "so9", entity_id: "ent_kanda" } });
  await mount(wrap(<DocPreviewModal target={{ docType: "sales_order", docId: "so9", entityId: "ent_kanda" }} onClose={() => {}} currentUser={{ permissions: PERMS }} />));
  expect(docEntityFor("/api/sales-orders/so9")).toBe("ent_kanda");
});

test("DocLink tanpa izin = teks biasa", async () => {
  await mount(wrap(<DocLink docType="sales_order" docId="so1" number="KSC/SO-00001" perms={{}} testId="dl" />, { previewsEnabled: true, openDocPreview: jest.fn() }));
  expect(document.body.querySelector("button")).toBeNull();
  expect(document.body.textContent).toContain("KSC/SO-00001");
});

test("DocLink tanpa id dokumen atau di luar penyedia navigasi = teks biasa", async () => {
  await mount(wrap(<DocLink docType="sales_order" docId="" number="LAMA-1" perms={PERMS} />, { previewsEnabled: true, openDocPreview: jest.fn() }));
  await mount(wrap(<DocLink docType="sales_order" docId="so1" number="SO-X" perms={PERMS} />, { previewsEnabled: false }));
  expect(document.body.querySelector("button")).toBeNull();
  expect(document.body.textContent).toContain("LAMA-1");
  expect(document.body.textContent).toContain("SO-X");
});

test("DocLink dengan izin membuka pratinjau", async () => {
  const openDocPreview = jest.fn();
  await mount(wrap(<DocLink docType="sales_order" docId="so1" number="KSC/SO-00001" perms={PERMS} testId="dl" />, { previewsEnabled: true, openDocPreview }));
  await klik(q("dl"));
  expect(openDocPreview).toHaveBeenCalledWith({ docType: "sales_order", docId: "so1", number: "KSC/SO-00001" });
});

test("registri: previewFor dan canPreview memeriksa jenis dan izin", () => {
  expect(previewFor("sales_order").perm).toEqual(["order", "view"]);
  expect(previewFor("tak_ada")).toBeNull();
  expect(canPreview(PERMS, "sales_order")).toBe(true);
  expect(canPreview({}, "sales_order")).toBe(false);
  expect(canPreview(PERMS, "tak_ada")).toBe(false);
});

test("tumpukan: push lalu Kembali", async () => {
  DOC_PREVIEWS.uji_tumpuk = {
    label: "Uji", perm: ["order", "view"], full: null,
    load: async (id) => ({ id, number: `NO-${id}` }),
    Body: ({ doc, push }) => (
      <div data-testid="uji-body">
        <span data-testid="uji-id">{doc.id}</span>
        <button type="button" className="link-button" data-testid="uji-push" onClick={() => push({ docType: "uji_tumpuk", docId: "so2" })}>buka</button>
      </div>),
  };
  try {
    await mount(wrap(<DocPreviewModal target={{ docType: "uji_tumpuk", docId: "so1" }} onClose={() => {}} currentUser={{ permissions: PERMS }} />));
    expect(q("doc-preview-back")).toBeNull();
    await klik(q("uji-push")); await act(async () => {});
    expect(teks(q("uji-id"))).toBe("so2");
    expect(q("doc-preview-back")).toBeTruthy();
    await klik(q("doc-preview-back")); await act(async () => {});
    expect(teks(q("uji-id"))).toBe("so1");
    expect(q("doc-preview-back")).toBeNull();
  } finally { delete DOC_PREVIEWS.uji_tumpuk; }
});

test("Buka layar penuh menavigasi lalu menutup; Jejak membuka jejak dokumen", async () => {
  mockGet.mockResolvedValue({ data: SO1 });
  const openDocument = jest.fn(); const onClose = jest.fn(); const onTrace = jest.fn();
  window.addEventListener("kn-open-trace", onTrace);
  await mount(wrap(<DocPreviewModal target={{ docType: "sales_order", docId: "so1" }} onClose={onClose} currentUser={{ permissions: PERMS }} />, { openDocument }));
  await klik(q("doc-preview-full"));
  expect(openDocument).toHaveBeenCalledWith(expect.objectContaining({ view: "orders", focus_id: "so1", number: "KSC/SO-00001" }));
  expect(onClose).toHaveBeenCalled();
  await klik(q("doc-preview-trace"));
  expect(onTrace.mock.calls[0][0].detail).toEqual({ docType: "sales_order", docId: "so1", number: "KSC/SO-00001" });
  window.removeEventListener("kn-open-trace", onTrace);
});

test("berkas baru bebas px & hex", () => {
  const dir = path.join(__dirname, "..", "documents", "preview");
  const semua = (d) => fs.readdirSync(d, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? semua(path.join(d, e.name)) : [path.join(d, e.name)]));
  const berkas = semua(dir);
  expect(berkas.length).toBeGreaterThanOrEqual(5);
  berkas.forEach((f) => {
    const isi = fs.readFileSync(f, "utf8");
    expect([f, /text-\[\d/.test(isi)]).toEqual([f, false]);
    expect([f, /#[0-9A-Fa-f]{3,6}\b/.test(isi)]).toEqual([f, false]);
  });
});
