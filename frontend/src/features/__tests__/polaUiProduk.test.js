// Pola UI gelombang Produk (docs/blueprint/04_POLA_UI.md; masukan pemilik 16 Nov — M20 Produk & Harga, M22 Rincian produk).
// M20 — layar kerja katalog = katalog bersih: alat admin data master (tata kelola/preview legacy, lembar kerja perbaikan,
//       sumber restock, Data SKU & impor) TIDAK tampil di atas daftar; dibuka dari "Alat data master ▾" hanya oleh
//       pemegang izinnya; satu tombol buat di bilah daftar.
// M22 — rincian induk: kepala nama · prefix · status · aksi; tanpa kartu angka kosong; label tahap/jenis kain ringkas;
//       peringatan desain satu baris kecil (hanya bagi yang bisa memperbaiki); "Hapus permanen" di menu "Lainnya".
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import CatalogWorkspace from "../catalog/CatalogWorkspace";
import { askConfirm } from "../../services/confirmService";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const mockGet = jest.fn();
const mockDelete = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), patch: () => Promise.resolve({ data: {} }),
    put: () => Promise.resolve({ data: {} }), delete: (...a) => mockDelete(...a), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true, askConfirm: jest.fn(async () => true), askReason: jest.fn(async () => "alasan uji"),
  askText: jest.fn(async () => null), askChoice: jest.fn(async () => null), default: {},
}));
jest.mock("../../components/ProductGallery", () => ({
  __esModule: true, mediaUrl: (u) => u, ProductGallery: () => <div data-testid="stub-gallery" />,
}));
jest.mock("../catalog/VariantMedia", () => ({ VariantMedia: () => <div data-testid="stub-variant-media" /> }));
jest.mock("../catalog/FamilyRoutesTab", () => () => <div data-testid="stub-routes" />);
jest.mock("../../components/AuditHistoryPanel", () => () => <div data-testid="stub-history" />);
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const ENUMS = { enums: {
  stage: { values: [{ value: "yarn", label: "Benang (Yarn)" }, { value: "grey", label: "Grey / Greige (Kain Mentah)" },
    { value: "finished", label: "Finished (Jadi — Dyed/Printed)" }] },
  fabric_type: { values: [{ value: "woven", label: "Woven (Tenun)" }, { value: "knit", label: "Knit (Rajut)" }] },
  product_line: { values: [{ value: "woven", label: "Woven" }, { value: "knit", label: "Knit" }, { value: "printing", label: "Printing" }] },
} };
const LIST_ITEM = { id: "t1", name: "Songket Merah", category: "Kain", fabric_type: "woven", axes: [], variant_count: 1, price_min: 145000, price_max: 145000 };
const FAMILY = {
  id: "t1", name: "Songket Merah", category: "Kain", stage: "finished", fabric_type: "woven", sku_prefix: "MTO-260829",
  status: "active", base_unit: "yard", base_price: 0, gramasi: null, lebar: null, description: "", axes: [], variant_count: 1,
  harga_pokok: 90000,
  variants: [{ id: "p1", sku: "MTO-260829-0001", name: "custom", price: 145000, media: [], lifecycle: "produksi", status: "active" }],
};
const SUMMARY = { variants: [{ id: "p1", rolls: 0, available: 0, reserved: 0 }], totals: { hpp: 88000, hpp_qty_costed: 120 } };

let usage = { name: "MTO-260829-0001", refs: [], policy: "Belum pernah dipakai: boleh dihapus permanen oleh pemegang akses.", can_delete: true };
let caps = { create: true, update: true };
function routeGet(url) {
  if (url === "/api/enums") return { enums: ENUMS.enums };
  if (url === "/api/product-catalog/meta") return { permissions: caps, variant_axes: [] };
  if (url === "/api/product-templates") return { items: [LIST_ITEM], total: 1 };
  if (url === "/api/suppliers") return [];
  if (url === "/api/product-templates/t1") return FAMILY;
  if (url === "/api/product-templates/t1/summary") return SUMMARY;
  if (url === "/api/master/usage/product/p1") return usage;
  if (url === "/api/master-governance/preview") {
    return { product_count: 3, missing: [], non_canonical: [], conflicts: [], duplicate_candidates: [], proposals: [],
      policy: { naming_standard: "belum ditetapkan" }, preview_signature: "x" };
  }
  if (url === "/api/master-governance/batches") return [];
  if (url === "/api/restock-sources") return { items: [{ id: "t1", name: "Songket Merah", sku_prefix: "MTO-260829", line_code: "woven" }], mapped: 0, unmapped: 1 };
  if (url.startsWith("/api/master-cleanup")) return [];
  return {};
}

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const qa = (id) => document.body.querySelectorAll(`[data-testid="${id}"]`);
let mounted = [];
async function settle() {
  for (let i = 0; i < 4; i += 1) {
    await act(async () => { jest.advanceTimersByTime(300); });
  }
}
async function mount(user) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  mounted.push(root);
  await act(async () => { root.render(<CatalogWorkspace currentUser={user} selectedEntity="ent_ksc" focus={null}
    legacyView={<div data-testid="stub-legacy-admin" />} />); });
  await settle();
  return host;
}
async function click(el) { await act(async () => { el.click(); }); await settle(); }

beforeEach(() => {
  jest.useFakeTimers();
  mockGet.mockImplementation((url) => Promise.resolve({ data: routeGet(url) }));
  mockDelete.mockResolvedValue({ data: {} });
  askConfirm.mockResolvedValue(true);   // CRA `resetMocks` membuang implementasi bawaan jest.fn sebelum tiap tes
});
afterEach(async () => {
  for (const r of mounted) await act(async () => { r.unmount(); });
  mounted = [];
  mockGet.mockReset(); mockDelete.mockReset();
  document.body.innerHTML = "";
  jest.useRealTimers();
  caps = { create: true, update: true };
  usage = { ...usage, can_delete: true, refs: [] };
});

const MD = { name: "MD", role: "md", permissions: { product: ["view", "create", "update", "export", "retire"], audit: ["view"] } };
const SALES = { name: "Sales", role: "sales", permissions: { product: ["view"] } };
const MANAGER = { name: "Mgr", role: "manager", permissions: { product: ["view", "export"] } };

describe("M20 — Produk & Harga: katalog bersih, alat admin dipindah", () => {
  test("layar kerja tanpa panel tata kelola/perbaikan/restock; satu bilah daftar dengan satu tombol buat", async () => {
    await mount(MD);
    expect(q("catalog-grid")).not.toBeNull();
    ["master-governance-panel", "master-cleanup-panel", "restock-source-panel", "catalog-governance-toggle",
      "catalog-cleanup-toggle", "catalog-restock-toggle", "catalog-legacy-view"].forEach((id) => expect(q(id)).toBeNull());
    const toolbar = q("catalog-toolbar");
    expect(toolbar.contains(q("catalog-search"))).toBe(true);
    expect(toolbar.contains(q("catalog-filters"))).toBe(true);
    expect(toolbar.contains(q("catalog-result-count"))).toBe(true);
    expect(q("catalog-result-count").textContent).toBe("1 produk");
    expect(qa("catalog-create")).toHaveLength(1);
    expect(toolbar.contains(q("catalog-create"))).toBe(true);
    expect(q("catalog-create").textContent).toContain("Tambah produk");
    // Kepala satu baris: tanpa tombol aksi di kepala, keterangan di "?".
    expect(q("catalog-heading").querySelector("button.primary-button")).toBeNull();
    expect(q("catalog-heading-help")).not.toBeNull();
  });

  test("Alat data master: menu berisi alat sesuai izin → halaman admin tersendiri (bukan di atas daftar) → kembali", async () => {
    await mount(MD);
    expect(q("catalog-tools-menu")).toBeNull();                       // tertutup bawaan
    await click(q("catalog-tools-button"));
    expect(q("catalog-legacy")).not.toBeNull();
    expect(q("catalog-tool-governance")).not.toBeNull();
    expect(q("catalog-tool-cleanup")).not.toBeNull();
    expect(q("catalog-tool-restock")).not.toBeNull();
    await click(q("catalog-tool-governance"));
    expect(q("catalog-tools-view")).not.toBeNull();
    expect(q("master-governance-panel")).not.toBeNull();
    expect(q("catalog-grid")).toBeNull();                              // daftar tidak bertumpuk di bawah alat
    expect(q("master-cleanup-panel")).toBeNull();                      // satu alat sekaligus
    await click(q("catalog-tools-back"));
    expect(q("catalog-tools-view")).toBeNull();
    expect(q("catalog-grid")).not.toBeNull();
  });

  test("tanpa izin ubah/ekspor produk: tidak ada tombol Alat data master dan tidak ada tombol buat", async () => {
    caps = { create: false, update: false };
    await mount(SALES);
    expect(q("catalog-grid")).not.toBeNull();
    expect(q("catalog-tools")).toBeNull();
    expect(q("catalog-create")).toBeNull();
  });

  test("ekspor saja: lembar kerja perbaikan (unduh) + sumber restock baca saja; alat ubah tertutup", async () => {
    caps = { create: false, update: false };
    await mount(MANAGER);
    await click(q("catalog-tools-button"));
    expect(q("catalog-tool-cleanup")).not.toBeNull();
    ["catalog-legacy", "catalog-tool-governance"].forEach((id) => expect(q(id)).toBeNull());
    await click(q("catalog-tool-restock"));
    expect(q("restock-row-t1")).not.toBeNull();
    expect(q("restock-unmapped-t1").textContent).toContain("belum diatur");
    expect(q("restock-save-t1")).toBeNull();                           // baca saja tanpa izin ubah produk
    expect(q("restock-filter")).not.toBeNull();                        // saringan status = dropdown, bukan deret chip
    expect(q("restock-filter-unmapped")).toBeNull();
  });

  test("saringan = dropdown ringkas sebaris; yang jarang dipakai di balik 'Saringan lain'", async () => {
    await mount(MD);
    expect(q("catalog-filters").className).toContain("contents");    // sebaris di bilah daftar, bukan baris sendiri
    ["catalog-filter-stage", "catalog-filter-line_code", "catalog-filter-lifecycle"].forEach((id) => expect(q(id)).not.toBeNull());
    ["catalog-filter-fabric_type", "catalog-filter-supplier_id", "catalog-filter-color"].forEach((id) => expect(q(id)).toBeNull());
    await click(q("catalog-filter-more"));
    ["catalog-filter-fabric_type", "catalog-filter-supplier_id", "catalog-filter-color"].forEach((id) => expect(q(id)).not.toBeNull());
    // Saringan tambahan yang TERISI tidak bisa tersembunyi: tombol lipat hilang, nilai dikirim ke server.
    const color = q("catalog-filter-color");
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(color, "merah");
      color.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await settle();
    expect(q("catalog-filter-more")).toBeNull();
    expect(q("catalog-filter-color").value).toBe("merah");
    const listCalls = mockGet.mock.calls.filter(([url]) => url === "/api/product-templates");
    expect(listCalls[listCalls.length - 1][1].params).toMatchObject({ color: "merah", offset: 0, paginate: true });
    expect(q("catalog-filter-reset")).not.toBeNull();
  });
});

describe("M22 — Rincian produk (templat C)", () => {
  async function openDetail(user = MD) {
    await mount(user);
    await click(q("catalog-open-t1"));
    expect(q("catalog-family-hero")).not.toBeNull();
  }

  test("kepala: nama · prefix · status · aksi; label tahap & jenis kain ringkas (bukan istilah teknis)", async () => {
    await openDetail();
    expect(q("catalog-title").textContent).toContain("Songket Merah");
    expect(q("catalog-sku-prefix").textContent).toBe("MTO-260829");
    expect(q("catalog-status").textContent).toBe("Aktif");
    expect(q("catalog-subtitle").textContent).toBe("Kain · Kain jadi · Tenun");
    expect(document.body.textContent).not.toContain("Finished (Jadi");
    expect(q("catalog-hero-stage")).toBeNull();                        // lencana teknis di atas foto dihapus
    expect(q("catalog-edit-family")).not.toBeNull();
    expect(q("catalog-generate")).not.toBeNull();
    expect(q("catalog-link-existing")).toBeNull();                     // aksi jarang di "Lainnya", tertutup bawaan
    await click(q("catalog-more-button"));
    expect(q("catalog-link-existing")).not.toBeNull();
  });

  test("ringkasan tanpa kartu angka kosong (gramasi/lebar kosong, stok 0, foto 0)", async () => {
    await openDetail();
    expect(q("hero-fact-sku").textContent).toContain("1 SKU");
    expect(q("hero-fact-price")).not.toBeNull();
    ["hero-fact-gsm", "hero-fact-width", "hero-fact-stock", "hero-fact-media"].forEach((id) => expect(q(id)).toBeNull());
    expect(document.body.textContent).not.toContain("Belum ada deskripsi produk");
  });

  test("peringatan desain = satu baris kecil + tautan perbaiki; teks teknis di '?'; tidak tampil bagi yang tak bisa mengubah", async () => {
    await openDetail();
    expect(q("catalog-family-design-missing").textContent).toContain("Belum bertaut desain");
    expect(q("catalog-family-design-edit").textContent).toBe("Pilih desain");
    expect(document.body.textContent).not.toContain("kosong di POS");
    await click(q("catalog-family-design-help"));
    expect(q("catalog-family-design-help-text").textContent).toContain("kosong di POS");
  });

  test("tanpa izin ubah: baris desain kosong & alat SKU tidak tampil", async () => {
    caps = { create: false, update: false };
    await openDetail(SALES);
    expect(q("catalog-family-design")).toBeNull();
    expect(q("catalog-edit-variant")).toBeNull();
    expect(q("master-usage-product")).toBeNull();
    expect(q("catalog-more")).toBeNull();                              // tidak ada butir "Lainnya" untuk peran ini
  });

  test("Hapus permanen tidak lagi tombol merah di tengah halaman: butir menu 'Lainnya' SKU; kebijakan di '?'", async () => {
    await openDetail();
    expect(q("master-usage-product").textContent).toContain("belum dipakai");
    expect(document.body.textContent).not.toContain("boleh dihapus permanen oleh pemegang akses");
    expect(q("master-purge-product")).toBeNull();
    await click(q("catalog-variant-more-button"));
    const item = q("master-purge-product");
    expect(item).not.toBeNull();
    expect(item.getAttribute("role")).toBe("menuitem");
    expect(item.disabled).toBe(false);
    await click(item);
    expect(mockDelete).toHaveBeenCalledWith("/api/master/product/p1/purge");
  });

  test("SKU sudah dipakai: butir hapus nonaktif dengan alasan tertulis", async () => {
    usage = { ...usage, can_delete: false, refs: [{ collection: "sales_orders", label: "Pesanan", count: 3 }] };
    await openDetail();
    expect(q("master-usage-ref-sales_orders").textContent).toContain("3");
    await click(q("catalog-variant-more-button"));
    const item = q("master-purge-product");
    expect(item.disabled).toBe(true);
    expect(item.textContent).toContain("Sudah dipakai");
  });

  test("tab Informasi tetap menampilkan HPP hitungan & HPP perkiraan (M28)", async () => {
    await openDetail();
    await click(q("catalog-tab-info"));
    expect(q("family-hpp").textContent).toContain("dari 120");
    expect(q("family-hpp-fallback")).not.toBeNull();
  });
});

describe("M22 — galeri varian", () => {
  const { VariantMedia } = jest.requireActual("../catalog/VariantMedia");
  async function mountMedia(items) {
    mockGet.mockImplementation((url) => Promise.resolve({ data: url === "/api/products/p1/media" ? { items, cover_media_id: "" } : routeGet(url) }));
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    mounted.push(root);
    await act(async () => { root.render(<VariantMedia product={{ id: "p1", name: "x" }} meta={{ permissions: { update: true }, max_media: 30 }} />); });
    await settle();
  }

  test("jenis berkas disaring lewat dropdown (bukan deret chip); keterangan galeri di '?'", async () => {
    await mountMedia([{ id: "m1", kind: "photo", status: "approved", url: "/x.jpg", filename: "a.jpg" }]);
    expect(q("media-kind-filter")).not.toBeNull();
    expect(q("media-filter-all")).toBeNull();
    expect(document.body.textContent).not.toContain("yang dilihat tim sales");
    await click(q("media-help"));
    expect(q("media-help-text").textContent).toContain("yang dilihat tim sales");
  });

  test("galeri kosong: tanpa saringan jenis berisi angka nol", async () => {
    await mountMedia([]);
    expect(q("media-kind-filter")).toBeNull();
    expect(q("media-empty")).not.toBeNull();
  });
});
