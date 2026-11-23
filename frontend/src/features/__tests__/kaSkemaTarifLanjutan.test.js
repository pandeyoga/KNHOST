// KA-9 — SDM › Kinerja & Insentif › Skema & Tarif, bagian LANJUTAN (dipecah dari `kaSkemaTarif.test.js` di KA-11 karena
// batas keras ukuran berkas `validate_compliance`; pengaturan tiruan & pembantu sama dengan berkas itu):
//  · R15: pop-up "Berlaku untuk" PT ini / Semua PT, mode Semua PT (tarif Semua PT), Lanjutan `commission.strategy`;
//  · R16: pohon segar sesudah simpan, halaman berikutnya tanpa kembar, pita terlambat diabaikan, sumber insentif
//    (berlaku mulai, riwayat), kalimat izin, simulasi (terpotong, jawaban basi), Pusat Pengaturan tertanam di mode
//    Semua PT (aturan grup / hanya baca);
//  · Target & Aturan tanpa bagian "Komisi otomatis (cara lama)"; LegacySchemeEditor tanpa "Bonus per produk fokus".
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import IncentiveSchemeView, { TEKS_SALES_TANPA_IZIN, TEKS_SUMBER_TANPA_IZIN } from "../incentive/IncentiveSchemeView";
import { TEKS_ARTIKEL_TERPOTONG } from "../incentive/SchemeSimulation";
import SettingsBrowserAsli from "../settings/config/SettingsBrowser";
import IncentiveSetupView from "../incentive/IncentiveSetupView";
import LegacySchemeEditor from "../incentive/LegacySchemeEditor";
import { AppNavProvider } from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { setAccessContext } from "../../config/roles";
import { todayWib } from "../../utils/formatters";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockPut = jest.fn();
const mockPatch = jest.fn();
const mockDelete = jest.fn();
const mockConfirm = jest.fn();
const mockReason = jest.fn();
const mockSettings = [];
const mockHarga = { lintasPt: true, items: [] };   // M3/M5 — caps.global_write & isi bagian 3 (dasar pengali harga)
const mockBrowsers = [];
const mockAsli = { pakai: false };   // true = mesin & tampilan Pusat Pengaturan yang asli (uji simpan cakupan grup)
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), put: (...a) => mockPut(...a),
    patch: (...a) => mockPatch(...a), delete: (...a) => mockDelete(...a), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: (...a) => mockConfirm(...a),
  askReason: (...a) => mockReason(...a),
  default: {},
}));
// Pustaka radix/cmdk tidak termuat di lingkungan uji ini — diganti <select> polos yang meneruskan pilihan.
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value ?? ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      <option value="">{p.placeholder || ""}</option>
      {(p.options || []).filter((o) => o.value !== "").map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/EntityScopeBanner", () => () => <div data-testid="scope" />);
jest.mock("../../components/KNDatePicker", () => (p) => (
  <input id={p.id} data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled} onChange={(e) => p.onChange(e.target.value)} />));
// Pusat Pengaturan tertanam: yang diuji di sini = kunci yang dikunci tiap bagian (mesinnya diuji di suite Pengaturan).
jest.mock("../settings/config/SettingsHub", () => {
  const asli = jest.requireActual("../settings/config/SettingsHub");
  return {
  ...asli,
  useSettingsBrowser: (opts) => {
    mockSettings.push(opts);
    if (mockAsli.pakai) return asli.useSettingsBrowser(opts);
    const batas = (opts.includeKeys || []).includes("commission.default_margin_cap_pct");
    // tinjauan akhir M3 — kemampuan menulis tarif/aturan grup (`caps.global_write`) dibaca dari mesin pengaturan bagian 3
    return { items: batas ? [{ key: "commission.default_margin_cap_pct", value: 45 }] : [...mockHarga.items],
      caps: { global_write: mockHarga.lintasPt } };
  },
  SettingsBrowser: (p) => {
    mockBrowsers.push(p);
    return mockAsli.pakai ? <asli.SettingsBrowser {...p} /> : <div data-testid={`cfg-browser-${p.embedded || "lepas"}`} />;
  },
  SettingsNotice: (p) => (mockAsli.pakai ? <asli.SettingsNotice {...p} /> : null),
  };
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView || function scrollIntoView() {};   // jsdom

const ENT = [{ id: "ent_kanda", legal_name: "CV Kanda Suka", short_name: "Kanda" }];
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const txt = (el) => (el?.textContent || "").replace(/ /g, " ");
async function settle() { for (let i = 0; i < 12; i += 1) await act(async () => {}); }
const klik = async (el) => { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await settle(); };
async function isi(el, value) {
  const proto = el.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype
    : el.tagName === "SELECT" ? window.HTMLSelectElement.prototype : window.HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
    el.dispatchEvent(new Event(el.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
  });
  await settle();
}
async function kirim(host, formId) {
  const form = q(host, formId).querySelector("form");
  await act(async () => { form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
  await settle();
}
const akar = [];   // akar React tiap uji — dilepas di afterEach
async function mount(node, { entity = "ent_kanda", pick } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  akar.push(root);
  await act(async () => {
    root.render(
      <EntityScopeProvider selectedEntity={entity} entities={ENT} canSwitch pickEntity={pick}>
        <AppNavProvider role="manager" onOpenDocument={() => {}} onNavigateTo={() => {}}>{node}</AppNavProvider>
      </EntityScopeProvider>);
  });
  await settle();
  return host;
}
const izin = (perms) => setAccessContext({ role: "manager", permissions: perms, view_resources: {}, hidden_views: [], view_actions: {} });
const PENUH = { sales_force: ["view", "update", "delete", "post"], incentive: ["view"], audit: ["view"] };

// ── Data acuan (PT Kanda): Batik bertarif Rp 3.000; Batik Mega bertarif sendiri Rp 3.500 + varian biru Rp 3.800;
//    Batik Parang ikut kategori; Tenun belum bertarif.
const TARIF = (n, over = {}) => ({ per_unit_amount: n, margin_cap_pct: 50, asal_lingkup: "pt", rate_id: "r_cat_batik", ...over });
const KATEGORI = { items: [
  { category: "Batik", rate: TARIF(3000), articles: 2, articles_own_rate: 1 },
  { category: "Tenun", rate: null, articles: 1, articles_own_rate: 0 },
] };
const ARTIKEL = { items: [
  { template_id: "t_mega", name: "Batik Mega", code: "BTK-MEGA-001", category: "Batik",
    rate: TARIF(3500, { margin_cap_pct: 40, asal_tingkat: "artikel", rate_id: "r_mega" }), own_rate_id: "r_mega", variant_exceptions: 1 },
  { template_id: "t_prg", name: "Batik Parang", code: "BTK-PRG-002", category: "Batik",
    rate: TARIF(3000, { asal_tingkat: "kategori" }), own_rate_id: null, variant_exceptions: 0 },
], total: 2, page: 1, page_size: 50 };
const VARIAN = { items: [
  { product_id: "p_red", sku: "BTK-MEGA-001-RED", name: "Batik Mega Merah", follows: "artikel",
    rate: TARIF(3500, { margin_cap_pct: 40, asal_tingkat: "artikel", rate_id: "r_mega" }) },
  { product_id: "p_blu", sku: "BTK-MEGA-001-BLU", name: "Batik Mega Biru", follows: "varian",
    rate: TARIF(3800, { margin_cap_pct: 40, asal_tingkat: "varian", rate_id: "r_blu" }) },
] };
/** `GET /api/incentive-rates?entity_id=all`: tarif Semua PT (kategori Batik, artikel Batik Mega) + satu tarif PT lain. */
const TARIF_GRUP = [
  { id: "r_cat_all", entity_id: "all", category: "Batik", template_id: "", product_id: "", target_name: "", target_code: "",
    per_unit_amount: 3000, margin_cap_pct: 50, status: "active" },
  { id: "r_art_all", entity_id: "all", category: "Batik", template_id: "t_mega", product_id: "", target_name: "Batik Mega",
    target_code: "BTK-MEGA-001", per_unit_amount: 3500, margin_cap_pct: 40, status: "active", price_bands: null, price_source_rules: null },
  { id: "r_pt", entity_id: "ent_kanda", category: "Tenun", template_id: "", product_id: "", per_unit_amount: 2000,
    margin_cap_pct: 50, status: "active" },
];
const TARGETS = (mode) => ({ period_type: "month", period: "2026-11", entity_id: "ent_kanda", all_pt: false, items: [],
  roster: [{ id: "u_andi", name: "Andi" }], commission_mode: mode, commission_modes: { ent_kanda: mode } });
const REGISTRI = { entries: [{ key: "hr.payroll_commission_mode", can_edit: true, options: [
  { value: "accrue_then_settle", label: "Komisi otomatis: dicadangkan, dilunasi lewat gaji" },
  { value: "pay_on_invoice", label: "Dibayar saat faktur terbit" },
  { value: "off", label: "Tidak ada komisi di gaji" },
  { value: "sheet", label: "Dari Lembar Insentif yang disahkan" },
  { value: "auto_and_sheet", label: "Komisi otomatis + Lembar Insentif (keduanya dibayar)" }] }] };

function api({ mode = "accrue_then_settle", strategy = "per_sku", extra = {} } = {}) {
  mockGet.mockImplementation((url, cfg) => {
    const map = {
      "/api/incentive/targets": TARGETS(mode),
      "/api/config/registry": REGISTRI,
      "/api/config/explain": { value: strategy },
      "/api/incentive-rates/categories": KATEGORI,
      "/api/incentive-rates/articles": ARTIKEL,
      "/api/incentive-rates/articles/t_mega/variants": VARIAN,
      "/api/sales/incentive/gl-status": { posted: false, amount: 0, estimate: 1250000 },
      "/api/sales-users": [{ id: "u_andi", name: "Andi" }],
      "/api/sales-incentives": [],
      ...extra,
    };
    const v = map[url];
    if (typeof v === "function") return v(cfg);
    if (v instanceof Error) return Promise.reject(v);
    return Promise.resolve({ data: v === undefined ? {} : v });
  });
}
const dipanggil = (path) => mockGet.mock.calls.filter((c) => c[0] === `/api${path}`);

beforeEach(() => {
  [mockGet, mockPost, mockPut, mockPatch, mockDelete, mockConfirm, mockReason].forEach((m) => m.mockReset());
  mockSettings.length = 0;
  mockHarga.lintasPt = true;
  mockHarga.items = [];
  mockBrowsers.length = 0;
  mockAsli.pakai = false;
  document.body.innerHTML = "";
  mockReason.mockResolvedValue("alasan uji");
  mockConfirm.mockResolvedValue(true);
  mockPost.mockResolvedValue({ data: {} });
  mockPatch.mockResolvedValue({ data: {} });
  mockDelete.mockResolvedValue({ data: { deleted: true } });
  mockPut.mockResolvedValue({ data: { count: 1 } });
});
// Akar React dilepas tiap uji: akar yang tertinggal ikut menggambar ulang saat jawaban async uji lama tiba sesudah tiruan
// pengaturan berganti (uji berikutnya) → urutan hook berbeda (terlihat di jest penuh yang lambat).
afterEach(async () => {
  await act(async () => { akar.splice(0).forEach((r) => r.unmount()); });
  setAccessContext(null);
});

// ═══ R15 — tarif Semua PT & strategi komisi tetap bisa diubah ═══════════════════════════════════════════════════════
test("KA9 R15 pop-up Berlaku untuk: Semua PT → POST entity_id all; tarif Semua PT diubah di tempat atau diganti tarif PT", async () => {
  izin(PENUH);
  api({ extra: { "/api/incentive-rates/categories": { items: [
    { category: "Batik", rate: TARIF(3000, { asal_lingkup: "semua_pt", rate_id: "r_cat_all" }), articles: 2, articles_own_rate: 1 },
    { category: "Tenun", rate: null, articles: 1, articles_own_rate: 0 }] } } });
  const host = await mount(<IncentiveSchemeView />);
  expect(txt(q(host, "rates-cat-rate-Batik"))).toBe("Rp 3.000tarif Semua PT");
  expect(txt(q(host, "rates-cat-edit-Batik"))).toBe("Ubah");
  expect(q(host, "rates-cat-delete-Batik")).toBeNull();                 // tarif grup dihapus dari mode "Semua PT"
  // kategori tanpa tarif → pilih Semua PT → POST entity_id "all"
  await klik(q(host, "rates-cat-edit-Tenun"));
  expect(q(host, "rate-form-scope-pt").checked).toBe(true);
  await klik(q(host, "rate-form-scope-semua_pt"));
  expect(txt(q(host, "rate-form-scope-warning"))).toBe("Tarif Semua PT berlaku untuk setiap PT yang tidak punya tarif sendiri di tingkat ini.");
  await isi(q(host, "rate-form-amount"), "2500");
  await kirim(host, "rate-form");
  expect(mockPost).toHaveBeenLastCalledWith("/api/incentive-rates", { entity_id: "all", category: "Tenun",
    per_unit_amount: 2500, margin_cap_pct: 45 });
  // R16 — tarif Semua PT yang terlihat dari satu PT: bawaan "PT ini"; "Semua PT" dipilih sendiri → diubah di tempat (PATCH)
  await klik(q(host, "rates-cat-edit-Batik"));
  expect(q(host, "rate-form-scope-pt").checked).toBe(true);
  expect(q(host, "rate-form-scope-warning")).toBeNull();
  expect(txt(q(host, "rate-form-inherit"))).toBe("Sekarang memakai tarif Semua PT Rp 3.000.");
  await klik(q(host, "rate-form-scope-semua_pt"));
  expect(txt(q(host, "rate-form-title"))).toBe("Ubah tarif kategori Batik");
  expect(txt(q(host, "rate-form-scope-warning"))).toBe("Mengubah tarif ini berlaku untuk semua PT.");
  expect(q(host, "rate-form-amount").value).toBe("3000");
  await isi(q(host, "rate-form-amount"), "3100");
  await kirim(host, "rate-form");
  expect(mockPatch).toHaveBeenLastCalledWith("/api/incentive-rates/r_cat_all", { data: { per_unit_amount: 3100, margin_cap_pct: 50 } });
  // … bawaannya = tarif khusus PT ini (POST lapisan PT)
  await klik(q(host, "rates-cat-edit-Batik"));
  expect(txt(q(host, "rate-form-title"))).toBe("Atur tarif kategori Batik");
  expect(q(host, "rate-form-amount").value).toBe("");
  await isi(q(host, "rate-form-amount"), "3300");
  await kirim(host, "rate-form");
  expect(mockPost).toHaveBeenLastCalledWith("/api/incentive-rates", { entity_id: "ent_kanda", category: "Batik",
    per_unit_amount: 3300, margin_cap_pct: 45 });
});

test("KA9 R15 mode Semua PT: tarif Semua PT diubah lewat pop-up yang sama; tarif per PT tidak tampil", async () => {
  izin(PENUH);
  api({ extra: { "/api/incentive-rates": TARIF_GRUP, "/api/incentive-rates/r_art_all": TARIF_GRUP[1] } });
  const host = await mount(<IncentiveSchemeView />, { entity: "all" });
  expect(dipanggil("/incentive-rates")[0][1]).toEqual({ params: { entity_id: "all" } });
  expect(dipanggil("/incentive-rates/categories")).toHaveLength(0);
  expect(txt(q(host, "group-rates-row-r_cat_all"))).toContain("Kategori");
  expect(txt(q(host, "group-rates-row-r_art_all"))).toContain("BTK-MEGA-001");
  expect(q(host, "group-rates-row-r_pt")).toBeNull();
  await klik(q(host, "group-rates-edit-r_art_all"));
  expect(txt(q(host, "rate-form-title"))).toBe("Ubah tarif artikel Batik Mega");
  expect(txt(q(host, "rate-form-scope-fixed"))).toBe("Semua PT");
  expect(q(host, "rate-form-scope-pt")).toBeNull();
  expect(q(host, "rate-form-amount").value).toBe("3500");
  await isi(q(host, "rate-form-amount"), "3600");
  await kirim(host, "rate-form");
  expect(mockPatch).toHaveBeenLastCalledWith("/api/incentive-rates/r_art_all", { data: { per_unit_amount: 3600,
    margin_cap_pct: 40, price_bands: null, price_source_rules: null } });
  await klik(q(host, "group-rates-delete-r_cat_all"));
  expect(mockReason.mock.calls[0][0].message).toContain("semua PT");
  expect(mockDelete).toHaveBeenCalledWith("/api/incentive-rates/r_cat_all", { params: { reason: "alasan uji" } });
});

test("KA9 R15 Lanjutan: commission.strategy di bagian tertutup (Per SKU); jenjang arsip hanya strategi arsip", async () => {
  izin(PENUH);
  const OPSI = [{ value: "per_sku", label: "Per SKU (tarif per barang)" },
    { value: "achievement_tiered", label: "Berjenjang dari pencapaian target" }];
  api({ extra: { "/api/config/explain": { value: "per_sku", entry: { key: "commission.strategy", options: OPSI } } } });
  let host = await mount(<IncentiveSchemeView />);
  expect(txt(q(host, "scheme-advanced-toggle"))).toContain("Cara menghitung komisi: Per SKU (tarif per barang)");
  expect(q(host, "scheme-advanced-toggle").getAttribute("aria-expanded")).toBe("false");
  expect(mockSettings.some((o) => (o.includeKeys || []).includes("commission.strategy"))).toBe(false);   // tertutup = belum dimuat
  await klik(q(host, "scheme-advanced-toggle"));
  const lanjut = mockSettings.filter((o) => (o.includeKeys || []).includes("commission.strategy"));
  expect(lanjut.length).toBeGreaterThan(0);
  expect(lanjut[0].includeKeys).toEqual(["commission.strategy"]);
  expect(lanjut[0].selectedEntity).toBe("ent_kanda");
  expect(q(host, "scheme-advanced").querySelector('[data-testid="cfg-browser-scheme-advanced-cfg"]')).not.toBeNull();
  expect(txt(q(host, "scheme-advanced-help"))).toContain("Per SKU");
  expect(mockSettings.map((o) => (o.includeKeys || []).join(",")).join(",")).not.toMatch(/incentive_unit/);
  expect(q(host, "legacy-scheme-editor")).toBeNull();
  expect(q(host, "scheme-rates-strategy")).toBeNull();
  // strategi arsip: tarif tidak dipakai (kalimat di bagian 2) + jenjang per sales tampil
  document.body.innerHTML = "";
  api({ extra: { "/api/config/explain": { value: "achievement_tiered", entry: { key: "commission.strategy", options: OPSI } } } });
  host = await mount(<IncentiveSchemeView />);
  expect(txt(q(host, "scheme-rates-strategy"))).toContain("Berjenjang dari pencapaian target");
  expect(q(host, "legacy-scheme-editor")).not.toBeNull();
});

// ═══ R16 — temuan tinjauan putaran 1 ═══════════════════════════════════════════════════════════════════════════════
test("KA9 R16 sesudah simpan: daftar tertutup dimuat baru saat dibuka lagi; pesan berhasil hilang pada aksi berikutnya", async () => {
  izin(PENUH);
  let tarifKat = 3000;
  api({ extra: { "/api/incentive-rates/articles": () => Promise.resolve({ data: { ...ARTIKEL,
    items: [ARTIKEL.items[0], { ...ARTIKEL.items[1], rate: TARIF(tarifKat, { asal_tingkat: "kategori" }) }] } }) } });
  const host = await mount(<IncentiveSchemeView />);
  await klik(q(host, "rates-cat-toggle-Batik"));
  expect(txt(q(host, "rates-art-rate-t_prg"))).toBe("ikut kategori Rp 3.000");
  await klik(q(host, "rates-cat-toggle-Batik"));                        // tutup Batik
  tarifKat = 3200;                                                       // tarif kategori Batik diubah
  await klik(q(host, "rates-cat-edit-Batik"));
  await isi(q(host, "rate-form-amount"), "3200");
  await kirim(host, "rate-form");
  expect(q(host, "rates-notice")).not.toBeNull();
  const sebelum = dipanggil("/incentive-rates/articles").length;
  await klik(q(host, "rates-cat-toggle-Batik"));                        // buka lagi → dimuat baru, bukan simpanan lama
  expect(dipanggil("/incentive-rates/articles")).toHaveLength(sebelum + 1);
  expect(txt(q(host, "rates-art-rate-t_prg"))).toBe("ikut kategori Rp 3.200");
  expect(q(host, "rates-notice")).toBeNull();
});

test("KA9 R16 'artikel berikutnya' sesudah simpan: halaman benar, tanpa baris kembar", async () => {
  izin(PENUH);
  const SEMUA = Array.from({ length: 120 }, (_, i) => ({ template_id: `t_${i}`, name: `Artikel ${i}`, code: `A-${i}`,
    category: "Batik", rate: TARIF(3000, { asal_tingkat: "kategori" }), own_rate_id: null, variant_exceptions: 0 }));
  api({ extra: { "/api/incentive-rates/articles": ({ params }) => Promise.resolve({ data: { total: 120, page: params.page,
    page_size: params.page_size, items: SEMUA.slice((params.page - 1) * params.page_size, params.page * params.page_size) } }) } });
  const host = await mount(<IncentiveSchemeView />);
  const baris = () => [...host.querySelectorAll('[data-testid^="rates-art-t_"]')].map((e) => e.getAttribute("data-testid"));
  await klik(q(host, "rates-cat-toggle-Batik"));
  await klik(q(host, "rates-more-Batik"));
  expect(baris()).toHaveLength(100);
  await klik(q(host, "rates-art-edit-t_5"));
  await isi(q(host, "rate-form-amount"), "3100");
  await kirim(host, "rate-form");
  let p = dipanggil("/incentive-rates/articles");
  expect(p[p.length - 1][1].params).toMatchObject({ category: "Batik", page: 1, page_size: 100 });   // muat ulang sebanyak yang termuat
  await klik(q(host, "rates-more-Batik"));
  p = dipanggil("/incentive-rates/articles");
  expect(p[p.length - 1][1].params).toMatchObject({ page: 3, page_size: 50 });
  expect(baris()).toHaveLength(120);
  expect(new Set(baris()).size).toBe(120);
  expect(q(host, "rates-more-Batik")).toBeNull();
});

test("KA9 R16 pop-up tarif: muat pita yang terlambat diabaikan bila sasaran berganti", async () => {
  izin(PENUH);
  let lepas;
  api({ extra: { "/api/incentive-rates/r_mega": () => new Promise((r) => { lepas = r; }) } });
  const host = await mount(<IncentiveSchemeView />);
  await klik(q(host, "rates-cat-toggle-Batik"));
  await klik(q(host, "rates-art-edit-t_mega"));                         // tarif sendiri → pita dimuat (tertahan)
  expect(txt(q(host, "rate-form-special-locked"))).toBe("Memuat pengali khusus…");
  await klik(q(host, "rate-form-close"));
  await klik(q(host, "rates-art-edit-t_prg"));
  expect(txt(q(host, "rate-form-title"))).toBe("Atur tarif artikel Batik Parang");
  await act(async () => { lepas({ data: { id: "r_mega", price_bands: [{ sampai_pct: null, pengali: 0.5 }], price_source_rules: null } }); });
  await settle();
  expect(q(host, "rate-form-bands-own").checked).toBe(false);            // jawaban lama tidak mengisi artikel lain
  expect(q(host, "rate-form-bands")).toBeNull();
});

test("KA9 R16 sumber insentif: Berlaku mulai, Riwayat, pesan tetap sesudah simpan (muat ulang diam)", async () => {
  izin(PENUH);
  api({ mode: "pay_on_invoice" });
  const host = await mount(<IncentiveSchemeView />);
  const kartuAkrual = q(host, "ins-accrual-na");
  expect(kartuAkrual).not.toBeNull();
  const buka = jest.fn();
  window.addEventListener("kn-open-config", buka);
  await klik(q(host, "scheme-source-history"));
  window.removeEventListener("kn-open-config", buka);
  expect(buka.mock.calls[0][0].detail.key).toBe("hr.payroll_commission_mode");
  expect(host.querySelector('label[for="scheme-source-from"]')).not.toBeNull();   // label terikat ke pemilih tanggal
  expect(q(host, "scheme-source-from").id).toBe("scheme-source-from");
  const nanti = `${Number(todayWib().slice(0, 4)) + 1}-01-15`;
  await klik(q(host, "scheme-source-lembar"));
  await isi(q(host, "scheme-source-from"), nanti);
  const nTarget = dipanggil("/incentive/targets").length;
  await klik(q(host, "scheme-source-save"));
  expect(mockReason.mock.calls[0][0].message).toContain("berlaku mulai");
  expect(mockPut).toHaveBeenLastCalledWith("/api/config/values", { items: [{ key: "hr.payroll_commission_mode", value: "sheet",
    scope_type: "entity", scope_id: "ent_kanda", reason: "alasan uji", effective_from: nanti }] });
  expect(dipanggil("/incentive/targets")).toHaveLength(nTarget + 1);
  // berjadwal: ditulis "Dijadwalkan: …"; pilihan kembali ke yang berlaku sekarang; Simpan mati sampai ada pilihan baru
  expect(txt(q(host, "scheme-source-scheduled"))).toMatch(/^Dijadwalkan: Dari Lembar Insentif yang disahkan mulai \S+/);
  ["otomatis", "lembar", "keduanya"].forEach((x) => expect(q(host, `scheme-source-${x}`).checked).toBe(false));
  expect(q(host, "scheme-source-save").disabled).toBe(true);
  expect(q(host, "scheme-source-from").value).toBe("");
  expect(q(host, "scheme-source-msg")).toBeNull();
  expect(q(host, "scheme-source-loading")).toBeNull();
  expect(q(host, "ins-accrual-na")).toBe(kartuAkrual);                   // kartu akrual tidak dipasang ulang
  // tanggal hari ini = langsung berlaku (tanpa "Dijadwalkan")
  await klik(q(host, "scheme-source-lembar"));
  await isi(q(host, "scheme-source-from"), todayWib());
  await klik(q(host, "scheme-source-save"));
  expect(mockPut.mock.calls[mockPut.mock.calls.length - 1][1].items[0].effective_from).toBe("");
  expect(txt(q(host, "scheme-source-msg"))).toBe("Sumber insentif CV Kanda Suka kini: Dari Lembar Insentif yang disahkan.");
  expect(q(host, "scheme-source-scheduled")).toBeNull();
});

test("KA9 R16 tanpa incentive.view: kalimat izin di bagian 1 dan di pemilih sales simulasi", async () => {
  izin({ sales_force: ["view"] });
  api({ extra: { "/api/incentive/targets": Object.assign(new Error("x"), { response: { status: 403,
    data: { detail: "Anda belum punya akses." } } }) } });
  const host = await mount(<IncentiveSchemeView />);
  expect(txt(q(host, "scheme-source-denied"))).toBe(TEKS_SUMBER_TANPA_IZIN);
  expect(TEKS_SUMBER_TANPA_IZIN).toBe("Melihat sumber insentif butuh akses Lihat di modul Kinerja & Insentif.");
  expect(q(host, "scheme-source-load-error")).toBeNull();
  expect(txt(q(host, "scheme-sim-sales-denied"))).toBe(TEKS_SALES_TANPA_IZIN);
  expect(q(host, "scheme-sim-sales")).toBeNull();
  expect(q(host, "scheme-sim-run").disabled).toBe(true);
});

test("KA9 R16 simulasi: daftar artikel terpotong ditulis + bisa dicari; galat baca strategi tertulis", async () => {
  izin(PENUH);
  api({ extra: {
    "/api/incentive-rates/articles": ({ params }) => Promise.resolve({ data: { ...ARTIKEL, total: params.search ? 1 : 250 } }),
    "/api/config/explain": Object.assign(new Error("x"), { response: { status: 500, data: { detail: "Server sibuk." } } }),
  } });
  const host = await mount(<IncentiveSchemeView />);
  expect(txt(q(host, "scheme-strategy-error"))).toContain("Cara menghitung komisi PT ini tidak bisa dibaca.");
  await klik(q(host, "scheme-sim-draft-add"));
  await isi(q(host, "scheme-sim-draft-cat-0"), "Batik");
  let p = dipanggil("/incentive-rates/articles");
  expect(p[p.length - 1][1].params).toMatchObject({ category: "Batik", page: 1, page_size: 200 });
  expect(txt(q(host, "scheme-sim-draft-capped-0"))).toBe(TEKS_ARTIKEL_TERPOTONG);
  expect(TEKS_ARTIKEL_TERPOTONG).toBe("Menampilkan 200 artikel pertama — cari untuk mempersempit");
  await isi(q(host, "scheme-sim-draft-search-0"), "mega");
  await act(async () => { q(host, "scheme-sim-draft-search-0").dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })); });
  await settle();
  p = dipanggil("/incentive-rates/articles");
  expect(p[p.length - 1][1].params).toMatchObject({ category: "Batik", search: "mega", page_size: 200 });
  expect(q(host, "scheme-sim-draft-capped-0")).toBeNull();
});

test("KA9 R16 kecil: fokus deep link dilepas di cabang tanpa isi; label isian tarif terikat ke isiannya", async () => {
  const lepas = jest.fn();
  izin(PENUH);
  api({ extra: { "/api/incentive-rates": TARIF_GRUP } });
  // "Semua PT": kunci yang tidak tampil di tab ini (satuan) langsung dilepas; kunci bagian diteruskan ke bagian grup
  let host = await mount(<IncentiveSchemeView focusKey="commission.incentive_unit" focusNonce={1} onFocusConsumed={lepas} />, { entity: "all" });
  expect(lepas).toHaveBeenCalledTimes(1);
  document.body.innerHTML = "";
  izin({ incentive: ["view"] });
  host = await mount(<IncentiveSchemeView focusKey="commission.price_bands" focusNonce={2} onFocusConsumed={lepas} />);
  expect(q(host, "scheme-no-access")).not.toBeNull();
  expect(lepas).toHaveBeenCalledTimes(2);
  document.body.innerHTML = "";
  izin(PENUH);
  api();
  host = await mount(<IncentiveSchemeView />);
  await klik(q(host, "rates-cat-edit-Tenun"));
  expect(host.querySelector('label[for="rate-form-amount"]')).not.toBeNull();
  expect(q(host, "rate-form-amount").id).toBe("rate-form-amount");
  expect(host.querySelector('label[for="rate-form-margin"]')).not.toBeNull();
  expect(q(host, "rate-form-margin").id).toBe("rate-form-margin");
});

test("KA9 R16 mode Semua PT: bagian 3–5 & Lanjutan tampil pada cakupan aturan grup; simpan = scope_type global", async () => {
  izin(PENUH);
  const KARTU = { key: "commission.achievement_multiplier", group: "penjualan", section: "komisi-pengali",
    label: "Kalikan komisi dengan pengali capaian target", type: "bool", value: false, default: false, stored_value: false,
    can_edit: true, source_layer: "code_default", scopes: ["global", "entity"], status: "active", risk: "medium",
    entity_overrides: [{ entity_id: "ent_kanda", entity_label: "Kanda", value: true }] };
  const OPSI = [{ value: "per_sku", label: "Per SKU (tarif per barang)" }];
  const pilihPt = jest.fn();
  api({ extra: {
    "/api/incentive-rates": TARIF_GRUP,
    "/api/config/registry": { groups: [{ id: "penjualan", label: "Penjualan & harga", count: 1,
      sections: [{ id: "komisi-pengali", label: "Komisi sales: pengali", advanced: false }] }],
    entries: [{ key: KARTU.key, group: "penjualan" }], caps: { global_write: true, settings_manage: true, settings_view: true } },
    "/api/config/effective": { groups: [], items: [KARTU] },
    "/api/config/explain": { value: "per_sku", entry: { key: "commission.strategy", options: OPSI } },
  } });
  mockAsli.pakai = true;
  const host = await mount(<IncentiveSchemeView />, { entity: "all", pick: pilihPt });
  // Lanjutan grup: label opsi registri, bukan kode mentah
  expect(txt(q(host, "scheme-advanced-toggle"))).toContain("Cara menghitung komisi: Per SKU (tarif per barang)");
  expect(txt(q(host, "scheme-advanced-toggle"))).not.toContain("per_sku");
  expect(dipanggil("/config/explain")[0][1]).toEqual({ params: { key: "commission.strategy", entity_id: "" } });
  expect(q(host, "scheme-group-readonly")).toBeNull();                 // peran lintas PT (global_write)
  expect(q(host, "scheme-group-rates-card")).not.toBeNull();
  expect(txt(q(host, "scheme-settings-scope"))).toContain("aturan grup (Semua PT)");
  const grupKunci = mockSettings.filter((o) => o.selectedEntity === "all").map((o) => (o.includeKeys || []).join());
  expect(grupKunci).toEqual(expect.arrayContaining([
    "commission.price_basis,commission.price_bands,commission.price_source_rules,commission.discount_",
    "commission.achievement_multiplier,commission.achievement_basis,commission.achievement_tiers",
    "commission.default_margin_cap_pct"]));
  const eff = dipanggil("/config/effective");
  expect(eff.length).toBeGreaterThan(0);
  expect(eff.every((c) => c[1].params.scope === "global" && c[1].params.entity_id === "")).toBe(true);
  expect(q(host, "scheme-advanced")).not.toBeNull();                   // Lanjutan (strategi) juga di cakupan grup
  expect(host.querySelectorAll('[data-testid="cfg-search"]')).toHaveLength(0);
  // kartu di bagian 4 (pengali capaian): buka → ubah → simpan pada aturan grup
  const kartu = q(host, "scheme-achievement-card");
  await klik(kartu.querySelector('[data-testid="cfg-card-toggle-commission.achievement_multiplier"]'));
  // R16 — "PT dengan nilai sendiri: Kanda" memindah seluruh tab lewat pemilih PT halaman, bukan satu bagian diam-diam
  await klik(kartu.querySelector('[data-testid="cfg-entity-override-commission.achievement_multiplier-ent_kanda"]'));
  expect(pilihPt).toHaveBeenCalledWith("ent_kanda");
  expect(dipanggil("/config/effective").every((c) => c[1].params.scope === "global" && c[1].params.entity_id === "")).toBe(true);
  await klik(kartu.querySelector('[data-testid="cfg-input-commission.achievement_multiplier"]'));
  await klik(kartu.querySelector('[data-testid="cfg-save-commission.achievement_multiplier"]'));
  expect(mockPut).toHaveBeenCalledTimes(1);
  expect(mockPut.mock.calls[0][0]).toBe("/api/config/values");
  expect(mockPut.mock.calls[0][1].items[0]).toMatchObject({ key: "commission.achievement_multiplier", value: true,
    scope_type: "global", scope_id: "" });
});

test("KA9 R16 mode Semua PT tanpa hak aturan grup: kalimat hub + kartu hanya baca", async () => {
  izin(PENUH);
  const KARTU = { key: "commission.achievement_multiplier", group: "penjualan", section: "komisi-pengali",
    label: "Kalikan komisi dengan pengali capaian target", type: "bool", value: false, default: false, stored_value: false,
    can_edit: true, source_layer: "code_default", scopes: ["global", "entity"], status: "active", risk: "medium" };
  api({ extra: {
    "/api/incentive-rates": TARIF_GRUP,
    "/api/config/registry": { groups: [{ id: "penjualan", label: "Penjualan & harga", count: 1,
      sections: [{ id: "komisi-pengali", label: "Komisi sales: pengali", advanced: false }] }],
    entries: [{ key: KARTU.key, group: "penjualan" }], caps: { global_write: false, settings_manage: true, settings_view: true } },
    "/api/config/effective": { groups: [], items: [KARTU] },
  } });
  mockAsli.pakai = true;
  const host = await mount(<IncentiveSchemeView />, { entity: "all" });
  expect(txt(q(host, "scheme-group-readonly"))).toBe("Aturan grup hanya dapat diubah peran lintas PT. Pilih satu PT di pemilih PT untuk mengubah nilai khusus PT Anda.");
  const kartu = q(host, "scheme-achievement-card");
  await klik(kartu.querySelector('[data-testid="cfg-card-toggle-commission.achievement_multiplier"]'));
  expect(kartu.querySelector('[data-testid="cfg-save-commission.achievement_multiplier"]')).toBeNull();
  expect(kartu.querySelector('[data-testid="cfg-input-commission.achievement_multiplier"]')).toBeNull();
});

test("KA9 R16 simulasi: jawaban yang datang sesudah masukan berubah diabaikan", async () => {
  izin(PENUH);
  api();
  let lepas;
  mockPost.mockImplementation(() => new Promise((r) => { lepas = r; }));
  const host = await mount(<IncentiveSchemeView />);
  await isi(q(host, "scheme-sim-sales"), "u_andi");
  await klik(q(host, "scheme-sim-run"));
  const bulanLain = q(host, "scheme-sim-month").querySelectorAll("option")[3].value;
  await isi(q(host, "scheme-sim-month"), bulanLain);                    // masukan berubah selagi menghitung
  await act(async () => { lepas({ data: { sekarang: { total_incentive: 1, breakdown: [] }, dengan_perubahan: { total_incentive: 2, breakdown: [] },
    catatan: "x" } }); });
  await settle();
  expect(q(host, "scheme-sim-result")).toBeNull();
  expect(q(host, "scheme-sim-run").disabled).toBe(false);
});

test("KA9 R16 SettingsBrowser tertanam: tanpa kotak cari & pemilih cakupan, testid berawalan", async () => {
  const s = { items: [], term: "", groups: [{ id: "penjualan", label: "Penjualan & harga", count: 0 }], group: "penjualan",
    filter: "all", health: {}, caps: { settings_view: true, settings_manage: true }, openKeys: new Set(), lockedGroup: "",
    locked: true, highlight: "", section: "", setEntities: () => {}, cardRefs: { current: {} }, q: "", setQ: () => {},
    scopeType: "entity", scopeId: "ent_kanda", loading: false, error: "", denied: "", restore: null };
  let host = await mount(<SettingsBrowserAsli s={s} entities={ENT} groupNav="chips" embedded="scheme-price-cfg" />);
  expect(q(host, "cfg-search")).toBeNull();
  expect(q(host, "cfg-scope-box")).toBeNull();
  expect(q(host, "cfg-group-head")).toBeNull();
  expect(q(host, "scheme-price-cfg-empty")).not.toBeNull();
  expect(q(host, "cfg-empty")).toBeNull();
  document.body.innerHTML = "";
  host = await mount(<SettingsBrowserAsli s={s} entities={ENT} groupNav="chips" />);   // bawaan layar lain tidak berubah
  expect(q(host, "cfg-search")).not.toBeNull();
  expect(q(host, "cfg-scope-box")).not.toBeNull();
  expect(q(host, "cfg-empty")).not.toBeNull();
});

// ═══ Layar lama ══════════════════════════════════════════════════════════════════════════════════════════════════
test("KA9 Target & Aturan tidak lagi memuat bagian Komisi otomatis (cara lama)", async () => {
  izin({ incentive: ["view", "configure"], sales_force: ["view", "update", "post"] });
  api();
  const host = await mount(<IncentiveSetupView />);
  expect(q(host, "ins-legacy")).toBeNull();
  expect(q(host, "ins-accrual")).toBeNull();
  expect(txt(host)).not.toContain("Komisi otomatis (cara lama)");
  expect(txt(q(host, "ins-scheme-link"))).toContain("SDM › Kinerja & Insentif › Skema & Tarif");
  expect(dipanggil("/incentive-rates")).toHaveLength(0);
  expect(dipanggil("/sales/incentive/gl-status")).toHaveLength(0);
});

test("KA9 LegacySchemeEditor tanpa isian Bonus per produk fokus", async () => {
  izin(PENUH);
  api();
  const host = await mount(<LegacySchemeEditor />);
  expect(q(host, "legacy-scheme-editor")).not.toBeNull();
  expect(q(host, "legacy-bonus-new")).not.toBeNull();
  expect(q(host, "legacy-bonus-focus")).toBeNull();
  expect(txt(host)).not.toMatch(/produk fokus/i);
});
