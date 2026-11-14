// PK-45 (CR-01, K-28) — form pelanggan: plafon kredit & status blokir hanya diubah pemegang izin
// `customer.manage_credit`, lewat PUT /customers/{id}/credit dengan alasan (spesifikasi docs/blueprint/unit/PK-45.md,
// bagian Layar; uji jalan U17 diwakili di sini dengan izin dari server: `currentUser.permissions`).
//   (a) tanpa izin: plafon & status hanya-baca + keterangan; PATCH tidak membawa keduanya; tidak ada PUT;
//   (b) dengan izin: mengubah plafon/status memunculkan isian wajib "Alasan perubahan kredit"; simpan memanggil PUT
//       sesudah PATCH; galat PUT tampil di form;
//   (c) pelanggan baru oleh pemegang izin: plafon & status dikirim lewat endpoint kredit sesudah pelanggan terbuat.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CustomerFormModal from "../crm/CustomerFormModal";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockPatch = jest.fn();
const mockPut = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: (...a) => mockPatch(...a),
    put: (...a) => mockPut(...a), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
// Pemilih bawaan (cmdk/radix) diganti <select> polos; isian wilayah (memuat data wilayah) diganti tiruan lengkap.
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange?.(e.target.value)}>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/LocationFields", () => ({
  __esModule: true, default: () => <div data-testid="stub-location" />, locationIncomplete: () => "",
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const flush = async (n = 4) => { for (let i = 0; i < n; i += 1) await act(async () => {}); };
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push({ root, host });
  await act(async () => { root.render(el); });
  await flush();
}
async function type(el, value) {
  const proto = el.tagName === "SELECT" ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
    el.dispatchEvent(new Event(el.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
  });
  await flush();
}
async function click(el) { await act(async () => { el.click(); }); await flush(); }
afterEach(async () => {
  for (const { root, host } of roots) { await act(async () => { root.unmount(); }); host.remove(); }
  roots = [];
  [mockGet, mockPost, mockPatch, mockPut].forEach((m) => m.mockReset());
});

// Pelanggan `cus_s` milik Sales: diblokir, plafon 5.000.000 (fixture uji PK-45).
const CUS_S = {
  id: "cus_s", name: "Toko Milik Sales", segment: "Retail", pic_name: "Andi", phone: "081234567890",
  credit_limit: 5000000, status: "blocked", assigned_sales_id: "u_sls", entity_id: "ent_ksc",
  province_code: "32", city_code: "3273", postal_code: "40111",
  addresses: [{ id: "a1", address: "Jl. Uji No. 1", is_primary: true, province_code: "32", city_code: "3273", postal_code: "40111" }],
};
const SLS = { id: "u_sls", name: "Ayu", role: "sales", permissions: { customer: ["view", "create", "update"] } };
const FIN = { id: "u_fin", name: "Fina", role: "finance", permissions: { customer: ["view", "manage_credit"] } };
const MGR = { id: "u_mgr", name: "Mira", role: "manager",
  permissions: { customer: ["view", "create", "update", "export", "manage_credit"] } };

function form(user, { editTarget = CUS_S, onSaved = jest.fn() } = {}) {
  return <CustomerFormModal open editTarget={editTarget} currentUser={user} salesUsers={[{ id: "u_sls", name: "Ayu" }]}
    selectedEntity="ent_ksc" onClose={() => {}} onSaved={onSaved} />;
}

test("PK-45 U17 (sales): plafon & status hanya-baca + keterangan; PATCH tanpa plafon/status; tanpa PUT", async () => {
  mockPatch.mockResolvedValue({ data: { ...CUS_S, pic_name: "Budi" } });
  const onSaved = jest.fn();
  await mount(form(SLS, { onSaved }));
  const limit = q("customer-credit-limit");
  expect(limit.getAttribute("data-readonly")).toBe("true");
  expect(limit.tagName).not.toBe("INPUT");
  expect(limit.textContent).toMatch(/Plafon kredit:\s*Rp\s5\.000\.000/);
  expect(q("customer-status").getAttribute("data-readonly")).toBe("true");
  expect(q("customer-status").textContent).toMatch(/Status:\s*Blokir/);
  expect(q("customer-credit-readonly-note").textContent).toBe("Plafon dan status blokir diubah oleh pemegang akses kredit.");
  expect(q("customer-credit-reason")).toBeNull();
  await type(q("customer-pic"), "Budi");
  await click(q("customer-form-submit"));
  expect(mockPatch).toHaveBeenCalledTimes(1);
  const [url, body] = mockPatch.mock.calls[0];
  expect(url).toBe("/api/customers/cus_s");
  expect(body.data.pic_name).toBe("Budi");
  expect(body.data).not.toHaveProperty("credit_limit");
  expect(body.data).not.toHaveProperty("status");
  expect(mockPut).not.toHaveBeenCalled();
  expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ pic_name: "Budi" }), true);
});

test("PK-45 U17 (finance): ubah plafon & buka blokir → alasan wajib → PUT kredit (tanpa PATCH: tidak punya izin ubah)", async () => {
  mockPut.mockResolvedValue({ data: { ...CUS_S, credit_limit: 20000000, status: "active" } });
  const onSaved = jest.fn();
  await mount(form(FIN, { onSaved }));
  const limit = q("customer-credit-limit");
  expect(limit.tagName).toBe("INPUT");
  expect(q("customer-credit-readonly-note")).toBeNull();
  expect(q("customer-credit-only-note")).not.toBeNull();
  expect(q("customer-credit-reason")).toBeNull();               // belum ada perubahan → belum diminta alasan
  await type(limit, "20000000");
  await type(q("customer-status"), "active");
  expect(q("customer-credit-reason")).not.toBeNull();
  await click(q("customer-form-submit"));
  expect(q("customer-form-modal-missing").textContent).toMatch(/alasan perubahan kredit/);
  expect(mockPut).not.toHaveBeenCalled();
  await type(q("customer-credit-reason"), "1234");                // tanpa huruf → tetap kurang
  await click(q("customer-form-submit"));
  expect(mockPut).not.toHaveBeenCalled();
  await type(q("customer-credit-reason"), "tinjauan triwulan");
  await click(q("customer-form-submit"));
  expect(mockPatch).not.toHaveBeenCalled();
  expect(mockPut).toHaveBeenCalledTimes(1);
  expect(mockPut).toHaveBeenCalledWith("/api/customers/cus_s/credit",
    { reason: "tinjauan triwulan", credit_limit: 20000000, status: "active" });
  expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ credit_limit: 20000000, status: "active" }), true);
});

test("PK-45 U17 (manajer): PATCH isian lain dulu, lalu PUT hanya isian kredit yang berubah; galat PUT tampil di form", async () => {
  const urutan = [];
  mockPatch.mockImplementation(async () => { urutan.push("patch"); return { data: CUS_S }; });
  mockPut.mockImplementation(async () => {
    urutan.push("put");
    const err = new Error("400");
    err.response = { status: 400, data: { detail: "Alasan perubahan wajib diisi (minimal 5 huruf)." } };
    throw err;
  });
  const onSaved = jest.fn();
  await mount(form(MGR, { onSaved }));
  await type(q("customer-status"), "inactive");
  await type(q("customer-credit-reason"), "toko tutup sementara");
  await click(q("customer-form-submit"));
  expect(urutan).toEqual(["patch", "put"]);
  expect(mockPatch.mock.calls[0][1].data).not.toHaveProperty("status");
  expect(mockPut.mock.calls[0][1]).toEqual({ reason: "toko tutup sementara", status: "inactive" });
  expect(q("customer-form-modal-error").textContent).toContain("Alasan perubahan wajib diisi (minimal 5 huruf).");
  expect(onSaved).not.toHaveBeenCalled();
});

test("PK-45 (pelanggan baru): pemegang izin → POST plafon 0 lalu PUT kredit beralasan; tanpa izin → hanya-baca, tanpa PUT", async () => {
  mockPost.mockResolvedValue({ data: { id: "cust_baru", name: "Toko Baru" } });
  mockPut.mockResolvedValue({ data: { id: "cust_baru", name: "Toko Baru", credit_limit: 50000000, status: "blocked" } });
  const onSaved = jest.fn();
  await mount(form(MGR, { editTarget: null, onSaved }));
  await type(q("customer-name"), "Toko Baru");
  await type(q("customer-pic"), "Sinta");
  await type(q("customer-phone"), "081234567845");
  await type(q("customer-address"), "Jl. Uji No. 45");
  await type(q("customer-assigned-sales"), "u_sls");
  await type(q("customer-credit-limit"), "50000000");
  await type(q("customer-status"), "blocked");
  await type(q("customer-credit-reason"), "pelanggan baru grosir");
  await click(q("customer-form-submit"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  expect(mockPost.mock.calls[0][0]).toBe("/api/customers");
  expect(mockPost.mock.calls[0][1].credit_limit).toBe(0);
  expect(mockPut).toHaveBeenCalledWith("/api/customers/cust_baru/credit",
    { reason: "pelanggan baru grosir", credit_limit: 50000000, status: "blocked" });
  expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ credit_limit: 50000000 }), false);

  for (const { root, host } of roots) { await act(async () => { root.unmount(); }); host.remove(); }
  roots = [];
  [mockPost, mockPut].forEach((m) => m.mockClear());
  await mount(form(SLS, { editTarget: null }));
  expect(q("customer-credit-limit").getAttribute("data-readonly")).toBe("true");
  expect(q("customer-credit-limit").textContent).toMatch(/tanpa batas/);
  await type(q("customer-name"), "Toko Sales");
  await type(q("customer-pic"), "Rina");
  await type(q("customer-phone"), "081234567846");
  await type(q("customer-address"), "Jl. Uji No. 46");
  await click(q("customer-form-submit"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  expect(mockPost.mock.calls[0][1].credit_limit).toBe(0);
  expect(mockPut).not.toHaveBeenCalled();
});
