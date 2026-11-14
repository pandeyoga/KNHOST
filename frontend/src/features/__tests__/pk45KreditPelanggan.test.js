// PK-45 (CR-01, K-28) → CR-T1 — form pelanggan TIDAK lagi memuat plafon kredit maupun pilihan status "Diblokir"
// (perilaku SENGAJA diubah unit CR-T1: plafon & blokir diajukan di tab Kredit kartu pelanggan, jalur PUT
// /customers/{id}/credit dijawab 410). Uji ini menjaga pengganti PK-45:
//   (a) form ubah: tanpa isian plafon, tanpa "Diblokir"; PATCH tidak membawa `credit_limit`; tidak ada PUT;
//   (b) status Aktif/Nonaktif lewat PATCH hanya bila diubah (status lama "blocked" tidak dikirim balik);
//   (c) pelanggan baru: pemegang `credit_profile.update` mengisi "Usulan plafon" → POST membawa `credit_limit` (server
//       membuat pengajuan); tanpa izin itu isian tidak tampil dan POST membawa 0.
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

// Pelanggan `cus_s` milik Sales: status lama "blocked", plafon lama 5.000.000 (fixture uji PK-45, sebelum migrasi CR-T1).
const CUS_S = {
  id: "cus_s", name: "Toko Milik Sales", segment: "Retail", pic_name: "Andi", phone: "081234567890",
  credit_limit: 5000000, status: "blocked", assigned_sales_id: "u_sls", entity_id: "ent_ksc",
  province_code: "32", city_code: "3273", postal_code: "40111",
  addresses: [{ id: "a1", address: "Jl. Uji No. 1", is_primary: true, province_code: "32", city_code: "3273", postal_code: "40111" }],
};
const CUS_A = { ...CUS_S, id: "cus_a", status: "active" };
const SLS = { id: "u_sls", name: "Ayu", role: "sales",
  permissions: { customer: ["view", "create", "update"], credit_profile: ["view", "update"] } };
const SLS_TANPA_KREDIT = { id: "u_sls2", name: "Budi", role: "sales", permissions: { customer: ["view", "create", "update"] } };
const MGR = { id: "u_mgr", name: "Mira", role: "manager",
  permissions: { customer: ["view", "create", "update", "export"], credit_profile: ["view", "update", "approve"] } };

function form(user, { editTarget = CUS_S, onSaved = jest.fn() } = {}) {
  return <CustomerFormModal open editTarget={editTarget} currentUser={user} salesUsers={[{ id: "u_sls", name: "Ayu" }]}
    selectedEntity="ent_ksc" onClose={() => {}} onSaved={onSaved} />;
}

test("CR-T1 (form ubah): tanpa isian plafon & tanpa 'Diblokir'; PATCH tanpa plafon/status; tanpa PUT", async () => {
  mockPatch.mockResolvedValue({ data: { ...CUS_S, pic_name: "Budi" } });
  const onSaved = jest.fn();
  await mount(form(MGR, { onSaved }));
  expect(q("customer-credit-limit")).toBeNull();
  expect(q("customer-credit-reason")).toBeNull();
  expect(q("customer-credit-note").textContent).toBe("Plafon dan blokir kredit diatur lewat pengajuan di tab Kredit pada kartu pelanggan.");
  // Status lama "blocked" (sebelum migrasi profil kredit) hanya-baca: tidak bisa dibuka lewat form ini.
  expect(q("customer-status").getAttribute("data-readonly")).toBe("true");
  expect(q("customer-status").textContent).toMatch(/Diblokir \(data lama\)/);
  await type(q("customer-pic"), "Budi");
  await click(q("customer-form-submit"));
  expect(mockPatch).toHaveBeenCalledTimes(1);
  const [url, body] = mockPatch.mock.calls[0];
  expect(url).toBe("/api/customers/cus_s");
  expect(body.data.pic_name).toBe("Budi");
  expect(body.data).not.toHaveProperty("credit_limit");
  expect(body.data).not.toHaveProperty("status");       // status lama "blocked" tidak dikirim balik
  expect(mockPut).not.toHaveBeenCalled();
  expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ pic_name: "Budi" }), true);
});

test("CR-T1 (status): Aktif → Nonaktif dikirim lewat PATCH", async () => {
  mockPatch.mockResolvedValue({ data: { ...CUS_A, status: "inactive" } });
  await mount(form(SLS, { editTarget: CUS_A }));
  expect([...q("customer-status").querySelectorAll("option")].map((o) => o.textContent)).toEqual(["Aktif", "Nonaktif"]);
  await type(q("customer-status"), "inactive");
  await click(q("customer-form-submit"));
  expect(mockPatch.mock.calls[0][1].data.status).toBe("inactive");
  expect(mockPut).not.toHaveBeenCalled();
});

test("CR-T1 (pelanggan baru): usulan plafon dikirim di POST; tanpa izin mengajukan → tidak tampil, POST 0", async () => {
  mockPost.mockResolvedValue({ data: { id: "cust_baru", name: "Toko Baru", credit_limit: 0 } });
  const onSaved = jest.fn();
  await mount(form(MGR, { editTarget: null, onSaved }));
  expect(q("customer-status")).toBeNull();
  await type(q("customer-name"), "Toko Baru");
  await type(q("customer-pic"), "Sinta");
  await type(q("customer-phone"), "081234567845");
  await type(q("customer-address"), "Jl. Uji No. 45");
  await type(q("customer-assigned-sales"), "u_sls");
  await type(q("customer-credit-limit"), "25000000");
  await click(q("customer-form-submit"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  expect(mockPost.mock.calls[0][0]).toBe("/api/customers");
  expect(mockPost.mock.calls[0][1].credit_limit).toBe(25000000);
  expect(mockPut).not.toHaveBeenCalled();
  expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ id: "cust_baru" }), false);

  for (const { root, host } of roots) { await act(async () => { root.unmount(); }); host.remove(); }
  roots = [];
  mockPost.mockClear();
  await mount(form(SLS_TANPA_KREDIT, { editTarget: null }));
  expect(q("customer-credit-limit")).toBeNull();
  await type(q("customer-name"), "Toko Sales");
  await type(q("customer-pic"), "Rina");
  await type(q("customer-phone"), "081234567846");
  await type(q("customer-address"), "Jl. Uji No. 46");
  await click(q("customer-form-submit"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  expect(mockPost.mock.calls[0][1].credit_limit).toBe(0);
});
