// PK-23 — layar Aset Tetap (docs/blueprint/unit/PK-23.md · U15 bagian komponen; uji jalan peramban oleh integrator).
// Form Tambah Aset Tetap: sumber dana wajib dipilih (tanpa bawaan), pilihan yang akun lawannya belum dipetakan mati
// beralasan, kas/bank memunculkan Rekening (rekening tunggal terisi otomatis), simpan mengirim sumber dana + rekening.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
// Pemilih bawaan (cmdk/radix) diganti <select> polos.
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      <option value="">{p.placeholder || ""}</option>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange?.(e.target.value)} />,
}));

jest.mock("../../components/KNMonthPicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />,
}));
jest.mock("../../services/confirmService", () => ({ __esModule: true, askConfirm: jest.fn(async () => true) }));

// eslint-disable-next-line import/first
import { AddAssetDialog } from "../finance/FixedAssetsParts";
// eslint-disable-next-line import/first
import FixedAssetsView from "../finance/FixedAssetsView";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const ENTS = [{ id: "ent_kanda", short_name: "Kanda", legal_name: "CV Kanda Suka" }];
const META = {
  categories: ["Peralatan & Mesin"], category_account: { "Peralatan & Mesin": "1-2100" },
  asset_accounts: [{ code: "1-2100", name: "Peralatan & Mesin" }],
  funding_sources: [
    { value: "kas", label: "Dibayar dari kas/bank", available: true, reason: "" },
    { value: "hutang", label: "Dibeli secara hutang", available: false,
      reason: "Akun lawannya belum ditetapkan di Pemetaan Akun." },
    { value: "saldo_awal", label: "Saldo awal (aset lama)", available: false,
      reason: "Akun lawannya belum ditetapkan di Pemetaan Akun." },
  ],
};

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(onSubmit) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(<AddAssetDialog meta={META} entities={ENTS} selectedEntity="ent_kanda" busy={false}
      onCancel={() => {}} onSubmit={onSubmit} />);
  });
  await flush();
  return host;
}
function ketik(el, v) {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  setter.call(el, v);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}
async function klik(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}

beforeEach(() => { mockGet.mockReset(); mockPost.mockReset(); });
afterEach(() => {
  roots.forEach((r) => act(() => r.unmount()));
  roots = [];
  document.body.innerHTML = "";
});

test("U15: sumber dana wajib; hutang mati beralasan; kas/bank memunculkan Rekening; simpan mengirim rekening", async () => {
  mockGet.mockResolvedValue({ data: [{ id: "rek_x", name: "BCA Kanda", bank_name: "BCA", account_number: "333",
    entity_id: "ent_kanda", account_type: "bank", cash_type: "kas_besar" }] });
  const onSubmit = jest.fn();
  await mount(onSubmit);
  expect(document.body.textContent).toContain("Perolehan dijurnal otomatis: debit akun aset, kredit sesuai sumber dana.");
  expect(document.body.textContent).not.toContain("Cr Kas-Bank");
  expect(q("asset-entity-line").textContent).toContain("CV Kanda Suka");
  await act(async () => { ketik(q("asset-name-input"), "Mesin Tenun"); });
  await act(async () => { ketik(q("asset-cost-input"), "12000000"); });
  await flush();
  // tanpa bawaan: tidak ada pilihan tercentang; simpan mati dengan alasan tertulis
  expect([...document.querySelectorAll('input[name="asset-funding"]')].some((r) => r.checked)).toBe(false);
  expect(q("add-asset-submit-btn").disabled).toBe(true);
  expect(q("add-asset-save-reason").textContent).toContain("Pilih sumber dana perolehan.");
  // hutang belum dipetakan → mati + petunjuk
  expect(q("asset-funding-hutang").disabled).toBe(true);
  expect(q("asset-funding-reason-hutang").textContent).toBe("Akun lawannya belum ditetapkan di Pemetaan Akun.");
  expect(q("asset-cash-account")).toBeNull();
  // kas/bank → Rekening; satu rekening PT → terisi otomatis & terkunci
  await klik(q("asset-funding-kas"));
  expect(q("asset-cash-account")).not.toBeNull();
  expect(mockGet).toHaveBeenCalledWith("/api/bank-accounts", { params: { entity_id: "ent_kanda" } });
  expect(q("asset-cash-account-sole")).not.toBeNull();
  expect(q("asset-cash-account-select").value).toBe("rek_x");
  expect(q("add-asset-submit-btn").disabled).toBe(false);
  await klik(q("add-asset-submit-btn"));
  expect(onSubmit).toHaveBeenCalledTimes(1);
  const isi = onSubmit.mock.calls[0][0];
  expect(isi).toMatchObject({ funding_source: "kas", account_id: "rek_x", entity_id: "ent_kanda",
    gl_account_asset: "1-2100", acquisition_cost: 12000000 });
  expect(isi).not.toHaveProperty("funding_account");
});

test("PT tanpa rekening: kas/bank dipilih → simpan mati dengan alasan rekening", async () => {
  mockGet.mockResolvedValue({ data: [] });
  await mount(jest.fn());
  await act(async () => { ketik(q("asset-name-input"), "Mesin"); });
  await act(async () => { ketik(q("asset-cost-input"), "1000000"); });
  await klik(q("asset-funding-kas"));
  expect(q("asset-cash-account-none")).not.toBeNull();
  expect(q("add-asset-submit-btn").disabled).toBe(true);
  expect(q("add-asset-save-reason").textContent).toContain("belum punya rekening");
});

// ── Daftar aset (FixedAssetsView) ────────────────────────────────────────────────────────────────────────────────
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.endsWith(k));
    return Promise.resolve({ data: hit ? map[hit] : [] });
  });
}
const ASET = (o) => ({ id: "fa1", number: "KSC/FA-00001", name: "Mesin Tenun", category: "Peralatan & Mesin",
  entity_id: "ent_ksc", acquisition_date: "2026-01-10", useful_life_months: 48, acquisition_cost: 12000000,
  accumulated_depreciation: 3000000, book_value: 9000000, depreciated_months: 12, status: "active",
  gl_status: "posted", ...o });

async function mountView(assets, summary = {}) {
  routeGet({ "/fixed-assets": assets, "/fixed-assets/summary": summary, "/fixed-assets/meta": META });
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(<FixedAssetsView selectedEntity="ent_ksc" entities={ENTS} />); });
  await flush();
  return host;
}

test("Daftar: tabel baku; aset sudah pindah → Pindah PT & Lepas mati dengan alasan tertulis, Catat Pembayaran ada",
  async () => {
    await mountView([
      ASET({ id: "fa1", status: "transferred", book_value: 0,
        transfer: { to_entity_id: "ent_kanda", to_entity_name: "Kanda", settled: false, price: 9000000,
          new_asset_number: "KANDA/FA-00001" } }),
      ASET({ id: "fa2", number: "KSC/FA-00002", gl_status: "failed", gl_error: "Akun 1-2100 nonaktif" }),
      ASET({ id: "fa3", number: "KSC/FA-00003" }),
    ], { count: 3, transferred: 1, transferred_book_value: 9000000, gross_cost: 420000000 });
    const tabel = q("fa-table");
    expect(tabel.className).toContain("data-table");
    expect(tabel.className).toContain("head-wrap");
    expect(tabel.querySelector("th:last-child").className).toContain("col-sticky-end");
    expect(q("transfer-btn-fa1").disabled).toBe(true);
    expect(q("dispose-btn-fa1").disabled).toBe(true);
    expect(q("transfer-btn-fa1").className).toContain("btn-sm");
    expect(q("asset-block-fa1").textContent).toContain("Aset ini sudah dipindahkan ke Kanda.");
    expect(q("settle-transfer-fa1")).not.toBeNull();
    expect(q("asset-status-fa1").textContent).toContain("Pindah PT");
    expect(q("asset-status-fa1").querySelector("svg")).not.toBeNull();    // ikon + teks + warna
    // belum berjurnal → mati beralasan; aset biasa → aktif tanpa alasan
    expect(q("transfer-btn-fa2").disabled).toBe(true);
    expect(q("asset-block-fa2").textContent).toContain("Jurnal perolehan belum terbit");
    expect(q("transfer-btn-fa3").disabled).toBe(false);
    expect(q("asset-block-fa3")).toBeNull();
  });

test("Kartu ringkasan: angka rupiah tidak dipotong (tanpa truncate; angka satu baris utuh)", async () => {
  await mountView([], { count: 0, gross_cost: 420000000, net_book_value: 0 });
  const nilai = q("summary-gross-cost-value");
  expect(nilai.className).not.toContain("truncate");
  const angka = nilai.querySelector(".whitespace-nowrap");
  expect(angka && angka.textContent).toMatch(/^420\.000\.000/);
  expect(q("summary-net-book-value-value").className).toContain("text-kn-text-2");   // nol tidak mendominasi
});

test("Jalankan Penyusutan: jumlah gagal dijurnal ditampilkan", async () => {
  await mountView([ASET({ id: "fa3", number: "KSC/FA-00003" })], { count: 1 });
  mockPost.mockResolvedValue({ data: { period: "2026-11", posted: 0, skipped: 0, total_amount: 0,
    failed: [{ asset_id: "fa3", number: "KSC/FA-00003", error: "uji" }] } });
  // CRA `resetMocks`: tiruan dikosongkan tiap uji → jawaban konfirmasi dipasang di sini.
  require("../../services/confirmService").askConfirm.mockResolvedValue(true);
  expect(q("run-depreciation-btn").disabled).toBe(false);
  await klik(q("run-depreciation-btn"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  expect(q("fa-dep-failed").textContent).toContain("1 gagal dijurnal");
  expect(q("fa-dep-failed").textContent).toContain("KSC/FA-00003");
});
