// PR-T4 — editor peran: bagian "Sifat peran" (`RoleTraitsPanel`) dan baris dialog "Periksa sebelum menyimpan".
// Uji komponen untuk U17 (bagian layar; uji jalan peramban terpisah): editor Sales → "Data yang terlihat" diubah ke
// "Milik sendiri dan timnya" → dialog memuat baris "Data yang terlihat: Milik sendiri → Milik sendiri dan timnya" →
// simpan mengirim `traits: {data_scope: "tim"}` saja; isian turunan tampil "Mengikuti …"; halaman awal yang izinnya
// tidak dimiliki tampil mati; peran terkunci hanya-baca.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockPatch = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: () => Promise.resolve({ data: {} }), patch: (...a) => mockPatch(...a),
    post: (...a) => mockPost(...a), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
// Pemilih bawaan (cmdk/radix) diganti <select> polos; opsi mati ikut mati.
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      {(p.options || []).map((o) => <option key={o.value} value={o.value} disabled={o.disabled}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});

// eslint-disable-next-line import/first
import RoleEditorDrawer from "../settings/entities/RoleEditorDrawer";
// eslint-disable-next-line import/first
import { traitChangeLines, traitPayload, shownTraits } from "../settings/entities/RoleTraitsPanel";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const CHOICES = [
  { view: "hr-my-profile", label: "Profil Saya", requires: null, needs_category: false },
  { view: "my-desk", label: "Meja Saya", requires: null, needs_category: true },
  { view: "sales-home", label: "Performa Saya", requires: ["order", "view"], needs_category: false },
  { view: "finance-desk", label: "Meja Finance", requires: ["payment_variance", "decide"], needs_category: false },
];
const SALES_TRAITS = { data_scope: "milik_sendiri", home_view: "sales-home", kategori_kerja: "sales", notify_like: [] };
const SALES = {
  id: "sales", label: "Sales", custom: false, locked: false, can_manage: true, users: 3, version: "v1",
  description: "Menjual.", permissions: { order: ["view", "create"], customer: ["view"] }, hidden_views: [],
  cross_entity: false, cross_entity_default: false, traits: SALES_TRAITS, traits_default: SALES_TRAITS,
  traits_overridden: [], home_choices: CHOICES, turn_alerts: [], modified: false,
};
const WAREHOUSE = { ...SALES, id: "warehouse", label: "Gudang", traits: { ...SALES_TRAITS, kategori_kerja: "gudang" } };
const ADMIN = { ...SALES, id: "admin", label: "Admin", locked: true };
const MODULES = [{ id: "penjualan", label: "Penjualan", group: "Penjualan", resources: ["order", "customer"],
                   actions: { order: ["view", "create"], customer: ["view"] }, nav: [] }];

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(props = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(<RoleEditorDrawer role={SALES} roles={[ADMIN, SALES, WAREHOUSE]} modules={MODULES}
                                  labels={{ resource_labels: {}, action_labels: {} }} onClose={() => {}}
                                  onSaved={() => {}} {...props} />);
  });
  await flush();
  return host;
}
async function pick(el, value) {
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set;
    setter.call(el, value);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}

afterEach(() => {
  roots.forEach((r) => act(() => r.unmount()));
  roots = [];
  document.body.innerHTML = "";
  mockPatch.mockReset();
  mockPost.mockReset();
});

test("U17 — Sales: ubah Data yang terlihat ke tim → dialog memuat baris perubahan, simpan mengirim traits saja", async () => {
  mockPatch.mockResolvedValue({ data: { ...SALES, label: "Sales", users: 3 } });
  await mount();
  const sel = q("role-traits-data-scope-select");
  expect(sel).toBeTruthy();
  // Turunan tampil "Mengikuti bawaan sistem (Milik sendiri)".
  expect(sel.options[sel.selectedIndex].textContent).toBe("Mengikuti bawaan sistem (Milik sendiri)");
  await pick(sel, "tim");
  await click(q("role-editor-save"));
  expect(q("role-editor-confirm-trait-data_scope").textContent)
    .toBe("Data yang terlihat: Milik sendiri → Milik sendiri dan timnya");
  await click(q("role-editor-confirm-save"));
  expect(mockPatch).toHaveBeenCalledTimes(1);
  const [url, body] = mockPatch.mock.calls[0];
  expect(url).toBe("/api/access/roles/sales");
  expect(body.traits).toEqual({ data_scope: "tim" });
});

test("halaman awal: pilihan tanpa izin tampil mati dengan petunjuk; kategori menampilkan akibatnya", async () => {
  await mount();
  const home = q("role-traits-home-select");
  const finance = [...home.options].find((o) => o.value === "finance-desk");
  expect(finance.disabled).toBe(true);
  expect(finance.textContent).toBe("Meja Finance · Butuh akses yang belum dimiliki peran ini");
  expect([...home.options].find((o) => o.value === "sales-home").disabled).toBe(false);
  expect(q("role-traits-category-effect").textContent).toMatch(/daftar pilih sales/);
  await pick(q("role-traits-category-select"), "sopir");
  expect(q("role-traits-category-effect").textContent).toBe("Akun bisa ditugaskan sebagai pengemudi; Meja Pengemudi.");
});

test("peran terkunci (Admin) hanya-baca", async () => {
  await mount({ role: ADMIN });
  expect(q("role-traits-data-scope-select").disabled).toBe(true);
  expect(q("role-traits-notify-warehouse").disabled).toBe(true);
});

test("ikut menerima notifikasi: centang Gudang → baris dialog dan isi simpan", async () => {
  mockPatch.mockResolvedValue({ data: { ...SALES } });
  await mount();
  await click(q("role-traits-notify-warehouse"));
  await click(q("role-editor-save"));
  expect(q("role-editor-confirm-trait-notify_like").textContent)
    .toBe("Ikut menerima notifikasi untuk: Tidak ada → Gudang");
  await click(q("role-editor-confirm-save"));
  expect(mockPatch.mock.calls[0][1].traits).toEqual({ notify_like: ["warehouse"] });
});

test("pembantu: nilai tersimpan, kembali ke turunan (null), dan peran baru berdasar peran dasar", () => {
  const stored = { ...SALES, traits: { ...SALES_TRAITS, data_scope: "semua" }, traits_overridden: ["data_scope"] };
  expect(shownTraits({ role: stored, roles: [SALES], draft: {} }).isDerived.data_scope).toBe(false);
  expect(traitPayload({ role: stored, draft: { data_scope: null } })).toEqual({ data_scope: null });
  expect(traitPayload({ role: SALES, draft: { data_scope: null } })).toEqual({});
  expect(traitChangeLines({ role: stored, roles: [SALES], draft: { data_scope: null } })[0].text)
    .toBe("Data yang terlihat: Semua di PT yang boleh dibuka → Milik sendiri");
  // Peran baru berdasar Sales: turunan = sifat Sales, alamat notifikasi = [sales].
  const baru = shownTraits({ role: null, baseRole: "sales", roles: [SALES], draft: {} });
  expect(baru.values).toEqual({ ...SALES_TRAITS, notify_like: ["sales"] });
  const kosong = shownTraits({ role: null, baseRole: "", roles: [SALES], draft: {} });
  expect(kosong.values).toEqual({ data_scope: "semua", home_view: "hr-my-profile", kategori_kerja: "", notify_like: [] });
});
