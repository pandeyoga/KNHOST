// KF-T5 — "Aturan khusus pelanggan ini" / "Aturan khusus barang ini" (`ScopedRulesSection`) dan baris jumlah aturan
// khusus di kartu Pusat Pengaturan (`ScopedRulesSummary` di `SettingCard`). Uji komponen (bagian layar U14/U15; uji jalan
// peramban terpisah): status "Mengikuti aturan PT" ↔ "Khusus pelanggan ini", Atur khusus → Simpan (satu PUT lapisan
// pelanggan), Kembali ikut aturan PT (konfirmasi → POST clear), hanya-baca, 403/kosong tidak tampil, galat + coba lagi.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";

const mockGet = jest.fn();
const mockPut = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), put: (...a) => mockPut(...a), post: (...a) => mockPost(...a),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
// Pemilih bawaan (cmdk/radix) diganti <select> polos; pemilih tanggal tidak diuji di sini.
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("@/components/KNDateTimePicker", () => () => null);

// eslint-disable-next-line import/first
import ScopedRulesSection, { kalimatStatus, ScopedRulesSummary } from "../settings/config/ScopedRulesSection";
// eslint-disable-next-line import/first
import SettingCard from "../settings/config/SettingCard";
// eslint-disable-next-line import/first
import { SCOPE_LABEL, scopeText } from "../settings/config/configApi";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const GRACE = {
  key: "ar.grace_days", label: "Masa tenggang sebelum denda", type: "duration", unit: "hari", min: 0, max: 180,
  help: "Jumlah hari setelah jatuh tempo yang masih bebas denda. Bisa dibedakan per pelanggan dari kartu pelanggan.",
  impact: "", scopes: ["global", "entity", "customer"], status: "active", risk: "low", requires_reason: false,
  can_edit: true, layer_value: null, inherited_value: 0,
};
const TOL = {
  key: "payment.variance_tolerance_rupiah", label: "Toleransi selisih pembayaran", type: "money", unit: "Rp",
  help: "Selisih rupiah yang masih dianggap wajar.", impact: "", scopes: ["global", "entity", "customer"],
  status: "active", risk: "high", requires_reason: true, can_edit: true, layer_value: null, inherited_value: 5000,
};
const efektif = (items) => ({ data: { items, total: items.length, context: {} } });

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(<>{el}<ConfirmHost /></>); });
  await flush();
  return host;
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
async function type(el, value) {
  const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
  await act(async () => {
    setter.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await flush();
}
const pelanggan = (props = {}) => (
  <ScopedRulesSection scopeType="customer" scopeId="cus_a" scopeLabel="Toko Abadi" entityId="ent_ksc" {...props} />
);

afterEach(async () => {
  const openCancel = document.body.querySelector(".modal-overlay [data-testid$='-cancel']");
  if (openCancel) await click(openCancel);
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockReset(); mockPut.mockReset(); mockPost.mockReset();
  document.body.innerHTML = "";
});

test("U14 (komponen): Atur khusus 10 hari → Simpan → Khusus pelanggan ini → Kembali ikut aturan PT", async () => {
  mockGet.mockResolvedValueOnce(efektif([GRACE]))
    .mockResolvedValueOnce(efektif([{ ...GRACE, layer_value: 10 }]))
    .mockResolvedValueOnce(efektif([GRACE]));
  mockPut.mockResolvedValue({ data: { count: 1 } });
  mockPost.mockResolvedValue({ data: {} });
  await mount(pelanggan());
  expect(mockGet).toHaveBeenCalledWith("/api/config/effective",
    { params: { scope: "customer", customer_id: "cus_a", entity_id: "ent_ksc" } });
  expect(q("scoped-rules-customer").textContent).toContain("Aturan khusus pelanggan ini");
  expect(q("scoped-rules-customer").textContent).toContain("Kosong berarti pelanggan mengikuti aturan PT-nya.");
  expect(q("scoped-ar.grace_days-status").textContent).toBe("Mengikuti aturan PT: 0 hari");
  expect(q("scoped-ar.grace_days-clear")).toBeNull();                      // belum punya nilai sendiri

  await click(q("scoped-ar.grace_days-edit"));
  await type(q("scoped-ar.grace_days-input"), "10");
  await click(q("scoped-ar.grace_days-save"));
  expect(mockPut).toHaveBeenCalledTimes(1);
  expect(mockPut.mock.calls[0]).toEqual(["/api/config/values", { items: [
    { key: "ar.grace_days", value: 10, scope_type: "customer", scope_id: "cus_a", reason: "" }] }]);
  expect(q("scoped-ar.grace_days-status").textContent).toBe("Khusus pelanggan ini: 10 hari (aturan PT: 0 hari)");
  expect(q("scoped-rules-customer-ok").textContent).toContain("Aturan khusus tersimpan.");

  await click(q("scoped-ar.grace_days-clear"));
  expect(q("scoped-ar.grace_days-clear-confirm").textContent).toContain("Hapus aturan khusus ini?");
  expect(q("scoped-ar.grace_days-clear-confirm-message").textContent)
    .toBe("Toko Abadi akan kembali mengikuti aturan PT.");
  await click(q("scoped-ar.grace_days-clear-confirm-confirm"));
  expect(mockPost).toHaveBeenCalledWith("/api/config/values/clear",
    { key: "ar.grace_days", scope_type: "customer", scope_id: "cus_a", reason: "Kembali ikut aturan PT" });
  expect(q("scoped-ar.grace_days-status").textContent).toBe("Mengikuti aturan PT: 0 hari");
  expect(document.body.textContent).not.toContain("cus_a");
  expect(document.body.textContent).not.toContain("ar.grace_days");
});

test("Batal di konfirmasi tidak mencabut apa pun", async () => {
  mockGet.mockResolvedValue(efektif([{ ...GRACE, layer_value: 7 }]));
  await mount(pelanggan());
  await click(q("scoped-ar.grace_days-clear"));
  await click(q("scoped-ar.grace_days-clear-confirm-cancel"));
  expect(mockPost).not.toHaveBeenCalled();
});

test("kunci berisiko tinggi: Simpan mati sampai alasan diisi; alasan ikut terkirim", async () => {
  mockGet.mockResolvedValue(efektif([TOL]));
  mockPut.mockResolvedValue({ data: {} });
  await mount(pelanggan());
  expect(q("scoped-payment.variance_tolerance_rupiah-status").textContent).toBe("Mengikuti aturan PT: Rp 5.000");
  await click(q("scoped-payment.variance_tolerance_rupiah-edit"));
  await type(q("scoped-payment.variance_tolerance_rupiah-input"), "20000");
  expect(q("scoped-payment.variance_tolerance_rupiah-save").disabled).toBe(true);
  await type(q("scoped-payment.variance_tolerance_rupiah-reason"), "Biaya transfer bank pelanggan ini");
  expect(q("scoped-payment.variance_tolerance_rupiah-save").disabled).toBe(false);
  await click(q("scoped-payment.variance_tolerance_rupiah-save"));
  expect(mockPut.mock.calls[0][1].items[0]).toEqual({ key: "payment.variance_tolerance_rupiah", value: 20000,
    scope_type: "customer", scope_id: "cus_a", reason: "Biaya transfer bank pelanggan ini" });
});

test("tanpa izin ubah: kartu hanya-baca, tombol tidak tampil", async () => {
  mockGet.mockResolvedValue(efektif([{ ...GRACE, can_edit: false, layer_value: 10 }]));
  await mount(pelanggan());
  expect(q("scoped-ar.grace_days-status").textContent).toBe("Khusus pelanggan ini: 10 hari (aturan PT: 0 hari)");
  expect(q("scoped-ar.grace_days-edit")).toBeNull();
  expect(q("scoped-ar.grace_days-clear")).toBeNull();
});

test("403 atau tanpa kartu: bagian tidak ditampilkan", async () => {
  mockGet.mockRejectedValueOnce({ response: { status: 403, data: { detail: "Anda belum punya akses." } } });
  await mount(pelanggan());
  expect(q("scoped-rules-customer")).toBeNull();
  expect(document.body.textContent).not.toContain("Anda belum punya akses");
  mockGet.mockResolvedValueOnce(efektif([]));
  await mount(pelanggan({ scopeId: "cus_b" }));
  expect(q("scoped-rules-customer")).toBeNull();
});

test("galat memuat: ErrorNotice + Coba lagi", async () => {
  mockGet.mockRejectedValueOnce({ response: { status: 500, data: { detail: "Server sedang sibuk." } } });
  mockGet.mockResolvedValueOnce(efektif([GRACE]));
  await mount(pelanggan());
  expect(q("scoped-rules-customer-error").textContent).toContain("Server sedang sibuk.");
  await click(q("scoped-rules-customer-error-retry"));
  expect(q("scoped-rules-customer-error")).toBeNull();
  expect(q("scoped-ar.grace_days-status")).not.toBeNull();
});

test("memuat: Memuat aturan…", async () => {
  mockGet.mockReturnValue(new Promise(() => {}));
  await mount(pelanggan());
  expect(q("scoped-rules-customer-loading").textContent).toContain("Memuat aturan…");
});

test("U15 (komponen): barang — PT terpilih ikut dikirim; Semua PT → aturan semua PT", async () => {
  const WASTE = { key: "cutting.waste_limit_pct", label: "Susut potong", type: "pct", unit: "", help: "", impact: "",
    scopes: ["global", "entity", "product"], status: "active", risk: "low", can_edit: true,
    layer_value: 7, inherited_value: 3 };
  mockGet.mockResolvedValue(efektif([WASTE]));
  await mount(<ScopedRulesSection scopeType="product" scopeId="prd_a" scopeLabel="Kain A" entityId="ent_ksc" />);
  expect(mockGet).toHaveBeenCalledWith("/api/config/effective",
    { params: { scope: "product", product_id: "prd_a", entity_id: "ent_ksc" } });
  expect(q("scoped-rules-product").textContent).toContain("Aturan khusus barang ini");
  expect(q("scoped-rules-product").textContent).toContain("Kosong berarti barang mengikuti aturan PT-nya.");
  expect(q("scoped-cutting.waste_limit_pct-status").textContent).toBe("Khusus barang ini: 7 % (aturan PT: 3 %)");
  mockGet.mockClear();
  await mount(<ScopedRulesSection scopeType="product" scopeId="prd_b" scopeLabel="Kain B" entityId="all" />);
  expect(mockGet).toHaveBeenCalledWith("/api/config/effective", { params: { scope: "product", product_id: "prd_b" } });
  expect(document.body.textContent).toContain("Khusus barang ini: 7 % (aturan semua PT: 3 %)");
});

test("Pusat Pengaturan: 'Bisa dibedakan per pelanggan — 1 pelanggan diatur khusus' → klik → nama dan nilai", async () => {
  mockGet.mockResolvedValue({ data: { rows: [{ scope_id: "cus_a", scope_label: "Toko Abadi", value: 10 }], total: 1 } });
  await mount(<ScopedRulesSummary item={GRACE} />);
  expect(mockGet).toHaveBeenCalledWith("/api/config/layers", { params: { key: "ar.grace_days", scope_type: "customer" } });
  expect(q("cfg-scoped-ar.grace_days").textContent).toBe("Bisa dibedakan per pelanggan — 1 pelanggan diatur khusus");
  expect(q("cfg-scoped-list-ar.grace_days")).toBeNull();
  await click(q("cfg-scoped-count-ar.grace_days"));
  expect(q("cfg-scoped-list-ar.grace_days").textContent).toBe("Toko Abadi: 10 hari");
});

test("kartu Pusat Pengaturan: baris 'Bisa diatur pada level' hilang; kunci tanpa lapisan pelanggan/barang tanpa baris", async () => {
  mockGet.mockResolvedValue({ data: { rows: [], total: 0 } });
  const noop = () => {};
  const kartu = (over) => ({ label: "Uji", help: "", impact: "", example: "", type: "bool", value: false, default: false,
    status: "active", source_layer: "code_default", source_label: "Default sistem", risk: "low", consumers: [],
    scheduled: [], ...over });
  const card = (item) => <SettingCard item={item} scopeType="global" scopeId="" canEdit onSave={async () => true}
    onReset={noop} onClearEntity={noop} onWhy={noop} onSimulate={noop} onHistory={noop} />;
  await mount(card(kartu({ key: "uji.biasa", scopes: ["global", "entity"] })));
  await click(q("cfg-more-uji.biasa"));
  expect(document.body.textContent).not.toContain("Bisa diatur pada level");
  expect(q("cfg-scoped-uji.biasa")).toBeNull();
  expect(mockGet).not.toHaveBeenCalled();
  await mount(card(kartu({ key: "cutting.remnant_threshold", scopes: ["global", "entity", "product"] })));
  expect(q("cfg-scoped-cutting.remnant_threshold").textContent).toBe("Bisa dibedakan per barang — 0 barang diatur khusus");
});

test("label lapisan & cakupan riwayat tanpa id", () => {
  expect(SCOPE_LABEL.customer).toBe("Pelanggan ini");
  expect(SCOPE_LABEL.product).toBe("Barang ini");
  expect(scopeText("customer", "cus_a", "Toko Abadi")).toBe("Pelanggan: Toko Abadi");
  expect(scopeText("product", "prd_a")).toBe("Barang");
  expect(kalimatStatus({ ...GRACE, layer_value: 0 }, "customer")).toBe("Khusus pelanggan ini: 0 hari (aturan PT: 0 hari)");
});
