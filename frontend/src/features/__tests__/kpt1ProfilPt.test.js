// KP-T1 — profil PT yang jujur dan bisa diubah: wizard Tambah Badan Usaha + layar detail (uji komponen; U17 uji jalan
// peramban terpisah). Wizard: tanpa "Skema penomoran"/"Penanggung insentif sales", mata uang & tahun buku dari Pusat
// Pengaturan (bawaan nilai grup), NPWP diperiksa di tempat, PT induk + persen kepemilikan. Detail: bagian Pajak dengan
// pop-up Ubah Status PKP (panel Dampak, tombol mati selama `can_apply` salah), jadwal bisa dibatalkan, Tahun buku &
// mata uang (sumber + editor baku lapisan PT), Grup & konsolidasi.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockPatch = jest.fn();
const mockPut = jest.fn();
const mockDelete = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: (...a) => mockPatch(...a),
    put: (...a) => mockPut(...a), delete: (...a) => mockDelete(...a), defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
// Pemilih bawaan (cmdk/radix) diganti elemen polos.
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"] || p.testId} value={p.value ?? ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      {(p.options || []).map((o) => <option key={String(o.value)} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange(e.target.value)} />,
  formatDateId: (v) => (v ? `tgl ${String(v).slice(0, 10)}` : ""),
}));

import EntityWizard from "../settings/entities/EntityWizard";
import EntityDetailDrawer from "../settings/entities/EntityDetailDrawer";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const NPWP_MSG = "NPWP harus 15 atau 16 digit angka. Periksa kembali nomor yang diketik.";
const ITEMS = (fyValue = 12, fySource = "code_default") => [
  { key: "finance.base_currency", label: "Mata uang pembukuan", type: "enum", value: "IDR", source_layer: "code_default",
    options: [{ value: "IDR", label: "Rupiah (IDR)" }, { value: "USD", label: "Dolar AS (USD)" }], can_edit: true,
    requires_reason: false, impact: "Mengubah simbol & format angka." },
  { key: "finance.fiscal_year_end_month", label: "Bulan tutup tahun buku", type: "int", value: fyValue, min: 1, max: 12,
    source_layer: fySource, can_edit: true, requires_reason: true, impact: "Menentukan periode tahun fiskal." },
];

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
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new Event("input", { bubbles: true })); });
  await flush(2);
}
async function choose(el, value) {
  const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new Event("change", { bubbles: true })); });
  await flush(2);
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  document.body.innerHTML = "";
  jest.clearAllMocks();
});

// ─── Wizard ───────────────────────────────────────────────────────────────────────────────────────────────────────
function wizardGets({ settingsFail = false } = {}) {
  mockGet.mockImplementation((url) => {
    if (url === "/api/enums/entity_type") return Promise.resolve({ data: { values: [{ value: "PT", label: "PT" }] } });
    if (url === "/api/config/effective") {
      return settingsFail ? Promise.reject({ response: { status: 403, data: { detail: "tanpa akses" } } })
        : Promise.resolve({ data: { items: ITEMS() } });
    }
    return Promise.resolve({ data: [] });
  });
}

async function keLangkah2(host) {
  await type(q("entity-wizard-legal-input"), "PT Uji Satu");
  await type(q("entity-wizard-short-input"), "UJI1");
  await click(q("entity-wizard-next"));
  expect(q("entity-wizard-panel-2")).not.toBeNull();
}

test("Wizard: isian mati hilang; mata uang & tahun buku dari Pusat Pengaturan; NPWP diperiksa; badan kirim bersih", async () => {
  wizardGets();
  mockPost.mockResolvedValue({ data: { id: "ent_baru" } });
  const onCreated = jest.fn();
  const host = await mount(<EntityWizard entities={[]} onClose={() => {}} onCreated={onCreated} />);
  await keLangkah2(host);
  expect(q("entity-wizard-incentive")).toBeNull();
  expect(host.textContent).not.toMatch(/Penanggung insentif|Awal tahun fiskal|id_standard/);
  expect(q("entity-wizard-currency").textContent).toContain("Mata uang pembukuan");
  expect(q("entity-wizard-currency-select").value).toBe("IDR");                  // bawaan = nilai grup
  expect([...q("entity-wizard-currency-select").options].map((o) => o.textContent)).toEqual(["Rupiah (IDR)", "Dolar AS (USD)"]);
  expect(q("entity-wizard-fiscal").textContent).toContain("Tahun buku berakhir pada bulan");
  expect(q("entity-wizard-fiscal").textContent).toContain("Menentukan batas tahun buku pada laporan dan tutup buku tahunan.");
  expect(q("entity-wizard-fiscal-select").value).toBe("12");
  expect(q("entity-wizard-fiscal-select").options.length).toBe(12);
  expect(q("entity-wizard-coa-note").textContent).toBe("Bagan akun dipakai bersama semua PT — kode akun sama, bukunya terpisah.");
  expect(q("entity-wizard-group").textContent).toContain("PT induk (konsolidasi)");
  expect(q("entity-wizard-ownership").textContent).toContain("bagian non-pengendali");

  await type(q("entity-wizard-npwp-input"), "12345");
  expect(q("entity-wizard-step-errors").textContent).toContain(NPWP_MSG);
  expect(q("entity-wizard-next").disabled).toBe(true);
  await type(q("entity-wizard-npwp-input"), "01.234.567.8-901.000");
  expect(q("entity-wizard-step-errors")).toBeNull();

  await click(q("entity-wizard-group-input"));
  expect(q("entity-wizard-ownership-input").disabled).toBe(true);
  await click(q("entity-wizard-group-input"));
  await type(q("entity-wizard-ownership-input"), "0");
  expect(q("entity-wizard-step-errors").textContent).toContain("Persen kepemilikan harus lebih dari 0");
  await type(q("entity-wizard-ownership-input"), "60");
  await choose(q("entity-wizard-currency-select"), "USD");
  await choose(q("entity-wizard-fiscal-select"), "3");
  await click(q("entity-wizard-next"));

  expect(q("entity-wizard-scheme")).toBeNull();
  expect(host.textContent).not.toMatch(/Skema penomoran|Deret bersama grup/);
  expect(q("entity-wizard-prefix").textContent).toContain(
    "Dipakai sebagai awalan nomor dokumen yang bernomor per PT, mis. pesanan, faktur pajak, kwitansi.");
  await click(q("entity-wizard-next"));
  const ring = q("entity-wizard-summary").textContent;
  expect(ring).toContain("April–Maret");
  expect(ring).toContain("Dolar AS (USD)");
  expect(ring).toContain("60 %");
  await click(q("entity-wizard-submit"));
  // KP-T5 — wizard juga meminta pratinjau nomor (`/api/doc-numbering/preview`); yang dihitung hanya simpan PT.
  const simpanPt = mockPost.mock.calls.filter(([u]) => u !== "/api/doc-numbering/preview");
  expect(simpanPt).toHaveLength(1);
  const [url, body] = simpanPt[0];
  expect(url).toBe("/api/entities");
  expect(body).toEqual(expect.objectContaining({ base_currency: "USD", fiscal_year_end_month: 3, ownership_pct: 60,
    is_group: false, npwp: "01.234.567.8-901.000", doc_prefix: "UJI1" }));
  for (const k of ["numbering_scheme", "incentive_payer", "coa_template", "fiscal_year_start", "currency"]) {
    expect(body).not.toHaveProperty(k);
  }
  expect(onCreated).toHaveBeenCalled();
});

test("Wizard: tanpa akses baca pengaturan → keterangan 'mengikuti pengaturan grup', tahun buku/mata uang tidak dikirim", async () => {
  wizardGets({ settingsFail: true });
  mockPost.mockResolvedValue({ data: { id: "ent_baru" } });
  const host = await mount(<EntityWizard entities={[]} onClose={() => {}} onCreated={() => {}} />);
  await keLangkah2(host);
  expect(q("entity-wizard-currency-select")).toBeNull();
  expect(q("entity-wizard-profile-readonly").textContent).toContain("mengikuti pengaturan grup");
  await type(q("entity-wizard-npwp-input"), "1234567890123456");
  await click(q("entity-wizard-next"));
  await click(q("entity-wizard-next"));
  await click(q("entity-wizard-submit"));
  const body = mockPost.mock.calls.find(([u]) => u === "/api/entities")[1];   // KP-T5 — selain pratinjau nomor
  expect(body).not.toHaveProperty("base_currency");
  expect(body).not.toHaveProperty("fiscal_year_end_month");
  expect(body.ownership_pct).toBe(100);
});

// ─── Detail PT ────────────────────────────────────────────────────────────────────────────────────────────────────
const ENT = (over = {}) => ({
  id: "ent_kanda", legal_name: "CV Kanda Suka", short_name: "Kanda", type: "CV", status: "active", doc_prefix: "KANDA",
  npwp: "02.345.678.9-012.000", address: "", city: "", phone: "", email: "", logo_url: "", default_tax_mode: "non_ppn",
  is_pkp: false, is_group: false, ownership_pct: 100, tax_status_pending: null, tax_status_history: [],
  base_currency: "IDR", base_currency_source: "code_default", fiscal_year_end_month: 3,
  fiscal_year_end_month_source: "entity", currency: "IDR", prefix_lock: { locked: false },
  country: "", country_code: "", province: "", province_code: "", city_code: "", district: "", district_code: "",
  postal_code: "", ...over,
});

function drawerGets(entities, preview) {
  let i = 0;
  mockGet.mockImplementation((url) => {
    if (url === "/api/entities/ent_kanda") {
      const e = entities[Math.min(i, entities.length - 1)];
      i += 1;
      return Promise.resolve({ data: e });
    }
    if (url.endsWith("/readiness")) return Promise.resolve({ data: { items: [], percent: 0 } });
    if (url.endsWith("/audit")) return Promise.resolve({ data: [] });
    if (url === "/api/config/effective") return Promise.resolve({ data: { items: ITEMS(3, "entity") } });
    if (url.endsWith("/tax-status/preview")) return Promise.resolve({ data: preview });
    return Promise.resolve({ data: [] });
  });
}

const PREVIEW = (over = {}) => ({
  entity_id: "ent_kanda", current: "non_ppn", to: "ppn", effective_date: "2026-11-14", applies: "sekarang",
  npwp_ok: true, open_documents: [{ collection: "sales_orders", label: "Pesanan penjualan", count: 1, examples: ["X"] }],
  documents_since: [], tax_invoices_issued: 0,
  setting_layers: [{ key: "tax.ppn_rate", label: "Tarif PPN", value: 12, effect: "mulai dipakai" },
    { key: "tax.efaktur_enabled", label: "E-faktur aktif", value: true, effect: "mulai dipakai" }],
  blockers: [], can_apply: true, ...over,
});

test("Detail PT: Pajak, Tahun buku & mata uang (nilai mesin + sumber), tanpa isian 'Awal tahun fiskal'", async () => {
  drawerGets([ENT()], PREVIEW());
  await mount(<EntityDetailDrawer entityId="ent_kanda" canManage onClose={() => {}} />);
  expect(q("entity-detail-fiscal_year_start-input")).toBeNull();
  expect(document.body.textContent).not.toContain("Awal tahun fiskal");
  expect(q("entity-detail-tax-status").textContent).toBe("Status: Non-PKP (tanpa PPN)");
  expect(q("entity-detail-profile-fiscal").textContent).toContain("Tahun buku: April–Maret");
  expect(q("entity-detail-profile-fiscal").textContent).toContain("(khusus PT ini)");
  expect(q("entity-detail-profile-currency").textContent).toContain("Mata uang pembukuan: Rupiah (IDR)");
  expect(q("entity-detail-profile-currency").textContent).toContain("(mengikuti pengaturan grup)");
  expect(q("entity-detail-group").textContent).toContain("PT induk (konsolidasi)");
  expect(q("entity-detail-ownership_pct-input").value).toBe("100");
});

test("Detail PT: pop-up Ubah Status PKP — panel Dampak, tombol mati tanpa alasan, simpan → lencana berubah", async () => {
  drawerGets([ENT(), ENT({ default_tax_mode: "ppn", is_pkp: true, tax_status_history: [
    { from: "non_ppn", to: "ppn", effective_date: "2026-11-14", reason: "Dikukuhkan PKP", by: "Admin", at: "x" }] })],
  PREVIEW());
  mockPost.mockResolvedValue({ data: { id: "ent_kanda", default_tax_mode: "ppn", tax_status_pending: null } });
  await mount(<EntityDetailDrawer entityId="ent_kanda" canManage onClose={() => {}} />);
  expect(q("entity-detail-title").parentElement.textContent).toContain("non-PKP");
  await click(q("entity-detail-tax-change"));
  expect(q("entity-tax-dialog-title").textContent).toBe("Ubah Status PKP");
  expect(q("entity-tax-to").value).toBe("ppn");
  expect(q("entity-tax-npwp")).toBeNull();                          // NPWP sudah terisi
  expect(q("entity-tax-open-docs").textContent.replace(/\s+/g, " ").trim()).toBe(
    "1 pesanan penjualan dan 0 pesanan pembelian yang masih berjalan tetap memakai hitungan pajak lama.");
  expect(q("entity-tax-settings").textContent).toContain("Tarif PPN: 12 % — mulai dipakai");
  expect(q("entity-tax-submit").disabled).toBe(true);              // alasan kosong
  await type(q("entity-tax-reason"), "Dikukuhkan PKP");
  expect(q("entity-tax-submit").disabled).toBe(false);
  await click(q("entity-tax-submit"));
  const [url, body] = mockPost.mock.calls[0];
  expect(url).toBe("/api/entities/ent_kanda/tax-status");
  expect(body).toEqual(expect.objectContaining({ to: "ppn", reason: "Dikukuhkan PKP" }));
  expect(body.effective_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  expect(q("entity-tax-dialog")).toBeNull();
  expect(q("entity-detail-saved").textContent).toContain("Status PKP diperbarui.");
  expect(q("entity-detail-title").parentElement.textContent).toContain("PKP");
  expect(q("entity-detail-title").parentElement.textContent).not.toContain("non-PKP");   // lencana berubah
  expect(q("entity-detail-tax-status").textContent).toBe("Status: PKP (memungut PPN)");
  expect(q("entity-detail-tax-since").textContent).toContain("Dikukuhkan PKP");
});

test("Detail PT: can_apply salah → tombol tetap mati; NPWP diminta bila kosong dan diperiksa di tempat", async () => {
  drawerGets([ENT({ npwp: "" })], PREVIEW({ npwp_ok: false, can_apply: false,
    blockers: ["PT yang menjadi PKP wajib mengisi NPWP."] }));
  await mount(<EntityDetailDrawer entityId="ent_kanda" canManage onClose={() => {}} />);
  await click(q("entity-detail-tax-change"));
  expect(q("entity-tax-npwp")).not.toBeNull();
  expect(q("entity-tax-blockers").textContent).toContain("PT yang menjadi PKP wajib mengisi NPWP.");
  await type(q("entity-tax-reason"), "Dikukuhkan PKP");
  expect(q("entity-tax-submit").disabled).toBe(true);
  await type(q("entity-tax-npwp"), "123");
  expect(q("entity-tax-npwp-error").textContent).toBe(NPWP_MSG);
  const previewCalls = mockGet.mock.calls.filter(([u]) => u.endsWith("/tax-status/preview"));
  expect(previewCalls[previewCalls.length - 1][1].params).toEqual(
    expect.objectContaining({ to: "ppn", npwp: "123" }));
});

test("Detail PT: jadwal tampil 'Akan menjadi … mulai …' dan bisa dibatalkan (konfirmasi baku)", async () => {
  const pending = { to: "ppn", effective_date: "2026-12-01", reason: "Rencana", by: "Admin", at: "t" };
  drawerGets([ENT({ tax_status_pending: pending }), ENT()], PREVIEW());
  mockDelete.mockResolvedValue({ data: ENT() });
  await mount(<EntityDetailDrawer entityId="ent_kanda" canManage onClose={() => {}} />);
  expect(q("entity-detail-tax-pending").textContent).toContain("Akan menjadi PKP (memungut PPN) mulai tgl 2026-12-01");
  expect(q("entity-detail-tax-change")).toBeNull();
  await click(q("entity-detail-tax-cancel"));
  await click(q("entity-detail-tax-cancel-confirm-confirm"));
  expect(mockDelete).toHaveBeenCalledWith("/api/entities/ent_kanda/tax-status/pending");
  expect(q("entity-detail-tax-pending")).toBeNull();
});

test("Detail PT: Ubah tahun buku = editor baku lapisan PT (alasan wajib); Grup & konsolidasi ikut Simpan", async () => {
  drawerGets([ENT(), ENT()], PREVIEW());
  mockPut.mockResolvedValue({ data: { saved: [], count: 1 } });
  mockPatch.mockResolvedValue({ data: ENT() });
  await mount(<EntityDetailDrawer entityId="ent_kanda" canManage onClose={() => {}} />);
  await click(q("entity-detail-profile-fiscal-edit"));
  expect(q("entity-profile-dialog-title").textContent).toBe("Ubah Tahun Buku");
  await choose(q("entity-profile-input"), "6");
  expect(q("entity-profile-dialog-submit").disabled).toBe(true);    // alasan wajib (risiko tinggi)
  await type(q("entity-profile-reason"), "Ikut tahun buku induk");
  await click(q("entity-profile-dialog-submit"));
  expect(mockPut).toHaveBeenCalledWith("/api/config/values", { items: [{ key: "finance.fiscal_year_end_month", value: 6,
    scope_type: "entity", scope_id: "ent_kanda", reason: "Ikut tahun buku induk" }] });

  await click(q("entity-detail-is_group-input"));
  expect(q("entity-detail-ownership_pct-input").disabled).toBe(true);
  await click(q("entity-detail-save"));
  expect(mockPatch).toHaveBeenCalledWith("/api/entities/ent_kanda", { data: { is_group: true } });
});

test("Detail PT tanpa izin ubah: tanpa tombol Ubah status PKP / Ubah; isian grup terkunci", async () => {
  drawerGets([ENT()], PREVIEW());
  await mount(<EntityDetailDrawer entityId="ent_kanda" canManage={false} onClose={() => {}} />);
  expect(q("entity-detail-tax-change")).toBeNull();
  expect(q("entity-detail-profile-fiscal-edit")).toBeNull();
  expect(q("entity-detail-is_group-input").disabled).toBe(true);
});
