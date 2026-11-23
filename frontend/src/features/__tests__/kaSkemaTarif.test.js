// KA-9 — SDM › Kinerja & Insentif › Skema & Tarif (`incentive-scheme`), sisi layar tanpa peramban
// (rancangan `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md` §6.5–§6.6):
//  · pemetaan pilihan ① Sumber insentif ↔ `hr.payroll_commission_mode` (satu tempat konstanta mode);
//  · tab "Skema & Tarif" sesudah Lembar Insentif; id lama `incentive-rates` / `incentive-schemes` dan deep link kunci
//    `commission.*` mengarah ke sana;
//  · ② pohon tarif tiga tingkat Kategori → Artikel → Varian ("ikut kategori" / "ikut artikel" / tarif sendiri), satu
//    pop-up ubah tarif, "Hapus tarif" beralasan, kategori tanpa tarif berkalimat, Excel (pratinjau berstatus → Terapkan
//    beralasan, nomor baris Excel dikirim balik);
//  · izin: tanpa `sales_force.view` → kalimat izin tanpa panggilan API; tanpa `sales_force.update` → tombol ubah tidak ada;
//  · ① simpan sumber insentif: peringatan "keduanya", konfirmasi cara pembukuan dari `pay_on_invoice`, PUT lapisan PT;
//  · ③④⑤ Pusat Pengaturan tertanam per bagian (`includeKeys`), `commission.incentive_unit`/`strategy` tidak tampil;
//  · simulasi: Sekarang vs Dengan perubahan + catatan server; 403 berkalimat;
//  · Target & Aturan tanpa bagian "Komisi otomatis (cara lama)" (tautan ke tab baru); jenjang lama tanpa "Bonus per
//    produk fokus".
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import IncentiveSchemeView, { bagianUntukKunci, TEKS_SALES_TANPA_IZIN, TEKS_SEMUA_PT, TEKS_SUMBER_TANPA_IZIN, TEKS_TANPA_LIHAT }
  from "../incentive/IncentiveSchemeView";
import { gabungSimulasi, TEKS_ARTIKEL_TERPOTONG } from "../incentive/SchemeSimulation";
import SettingsBrowserAsli from "../settings/config/SettingsBrowser";
import { butuhKonfirmasiAkru, komisiOtomatisJalan, MODE_AKRU, MODE_KEDUANYA, MODE_TANPA_MESIN, modeDariPilihan,
  pilihanSumber } from "../incentive/incentiveModes";
import { ringkasTarif, TEKS_KATEGORI_TANPA_TARIF } from "../incentive/ArticleRatesTable";
import IncentiveSetupView from "../incentive/IncentiveSetupView";
import LegacySchemeEditor from "../incentive/LegacySchemeEditor";
import { HUB_TABS, resolveDeepLinkTarget } from "../../config/navigationConfig";
import { PAGE_META } from "../../config/navMeta";
import { COMMISSION_HOME, configTargetFor } from "../settings/config/configGroupViews";
import { COMMISSION_LINK } from "../settings/config/SettingsHub";
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
    return { items: batas ? [{ key: "commission.default_margin_cap_pct", value: 45 }] : [] };
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
async function mount(node, { entity = "ent_kanda", pick } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
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
afterEach(() => setAccessContext(null));

// ═══ Pemetaan ① ═══════════════════════════════════════════════════════════════════════════════════════════════════
test("KA9 pemetaan sumber insentif", () => {
  expect(pilihanSumber("accrue_then_settle")).toBe("otomatis");
  expect(pilihanSumber("sheet")).toBe("lembar");
  expect(pilihanSumber("auto_and_sheet")).toBe("keduanya");
  expect(pilihanSumber("pay_on_invoice")).toBe("lain");
  expect(pilihanSumber("off")).toBe("lain");
  expect(pilihanSumber("")).toBe("lain");
  expect(modeDariPilihan("otomatis", "pay_on_invoice")).toBe("pay_on_invoice");
  expect(modeDariPilihan("otomatis", "sheet")).toBe("accrue_then_settle");
  expect(modeDariPilihan("otomatis", "off")).toBe("accrue_then_settle");
  expect(modeDariPilihan("lembar", "pay_on_invoice")).toBe("sheet");
  expect(modeDariPilihan("keduanya", "sheet")).toBe("auto_and_sheet");
  expect(butuhKonfirmasiAkru("keduanya", "pay_on_invoice")).toBe(true);
  expect(butuhKonfirmasiAkru("otomatis", "pay_on_invoice")).toBe(false);   // nilai PT dipertahankan
  expect(butuhKonfirmasiAkru("lembar", "pay_on_invoice")).toBe(false);
  expect(butuhKonfirmasiAkru("keduanya", "sheet")).toBe(false);
  // satu tempat konstanta mode (dipakai kartu sales, Target & Aturan, tab baru, beranda & HP sales)
  expect(MODE_TANPA_MESIN).toEqual(["sheet", "off"]);
  expect(MODE_AKRU).toEqual(["accrue_then_settle", "auto_and_sheet"]);
  expect(MODE_KEDUANYA).toBe("auto_and_sheet");
  expect([komisiOtomatisJalan("pay_on_invoice"), komisiOtomatisJalan("auto_and_sheet"), komisiOtomatisJalan("sheet"),
    komisiOtomatisJalan("off"), komisiOtomatisJalan("")]).toEqual([true, true, false, false, false]);
});

test("KA9 tab Skema & Tarif terdaftar dan alias lama mengarah ke sana", () => {
  const kpi = HUB_TABS["hr-kpi-hub"];
  expect(kpi.map((t) => t.view)).toEqual(["incentive-capaian", "incentive-sheets", "incentive-scheme", "incentive-setup", "cs-kpi"]);
  expect(kpi.find((t) => t.view === "incentive-scheme")).toMatchObject({ label: "Skema & Tarif", roles: ["admin", "manager", "finance"] });
  expect(resolveDeepLinkTarget("incentive-scheme", "manager")).toMatchObject({ view: "incentive-scheme", navId: "hr-kpi-hub" });
  expect(resolveDeepLinkTarget("incentive-rates", "manager")).toMatchObject({ view: "incentive-scheme", navId: "hr-kpi-hub" });
  expect(resolveDeepLinkTarget("incentive-schemes", "admin")).toMatchObject({ view: "incentive-scheme", navId: "hr-kpi-hub" });
  expect(PAGE_META["incentive-scheme"]).toMatchObject({ kicker: "SDM · Kinerja & Insentif", title: "Skema & Tarif Komisi" });
  expect(COMMISSION_HOME).toEqual({ view: "incentive-scheme", nav: "hr-kpi-hub" });
  expect(configTargetFor({ key: "commission.price_bands" })).toEqual({ view: "incentive-scheme", nav: "hr-kpi-hub" });
  expect(COMMISSION_LINK).toMatchObject({ view: "incentive-scheme", where: "SDM › Kinerja & Insentif › Skema & Tarif" });
  // deep link kunci komisi → bagian yang memuat kuncinya
  expect(["commission.price_bands", "commission.discount_factor", "commission.achievement_tiers",
    "commission.default_margin_cap_pct", "commission.strategy", "commission.incentive_unit"].map(bagianUntukKunci)).toEqual(
    ["harga", "harga", "capaian", "batas", "lanjutan", ""]);   // R15 — strategi di bagian Lanjutan; satuan tetap tersembunyi
});

// ═══ ② pohon tarif ═══════════════════════════════════════════════════════════════════════════════════════════════
test("KA9 pohon tarif: kategori → artikel (ikut kategori / sendiri) → varian (ikut artikel)", async () => {
  izin(PENUH);
  api();
  const host = await mount(<IncentiveSchemeView />);
  expect(dipanggil("/incentive-rates/categories")[0][1]).toEqual({ params: { entity_id: "ent_kanda" } });
  expect(txt(q(host, "rates-cat-rate-Batik"))).toBe("Rp 3.000tarif kategori");
  expect(txt(q(host, "rates-cat-Batik"))).toContain("2 artikel · 1 bertarif sendiri");
  expect(q(host, "rates-art-t_mega")).toBeNull();                       // artikel belum dimuat sebelum kategori dibuka
  await klik(q(host, "rates-cat-toggle-Batik"));
  expect(dipanggil("/incentive-rates/articles")[0][1]).toEqual(
    { params: { entity_id: "ent_kanda", category: "Batik", page: 1, page_size: 50 } });
  expect(txt(q(host, "rates-art-rate-t_mega"))).toBe("Rp 3.500tarif sendiri");
  expect(txt(q(host, "rates-art-t_mega"))).toContain("1 varian bertarif sendiri");
  expect(txt(q(host, "rates-art-rate-t_prg"))).toBe("ikut kategori Rp 3.000");
  expect(txt(q(host, "rates-art-edit-t_prg"))).toBe("Atur tarif");
  expect(q(host, "rates-art-delete-t_prg")).toBeNull();                 // tanpa tarif sendiri: tidak ada yang dihapus
  await klik(q(host, "rates-art-toggle-t_mega"));
  expect(dipanggil("/incentive-rates/articles/t_mega/variants")[0][1]).toEqual({ params: { entity_id: "ent_kanda" } });
  expect(txt(q(host, "rates-var-rate-p_red"))).toBe("ikut artikel Rp 3.500");
  expect(txt(q(host, "rates-var-rate-p_blu"))).toBe("Rp 3.800tarif sendiri");
  expect(txt(host)).toContain("Tarif berlaku untuk pesanan yang dibuat sesudah disimpan; pesanan lama memakai tarif saat pesanan dibuat.");

  // satu pop-up untuk ketiga tingkat — artikel tanpa tarif sendiri → POST tarif baru (batas margin bawaan PT ⑤ = 45 %)
  await klik(q(host, "rates-art-edit-t_prg"));
  expect(txt(q(host, "rate-form-title"))).toBe("Atur tarif artikel Batik Parang");
  expect(q(host, "rate-form-margin").value).toBe("45");
  expect(q(host, "rate-form-bands-own")).not.toBeNull();               // pengali khusus hanya tingkat artikel
  await isi(q(host, "rate-form-amount"), "3200");
  await kirim(host, "rate-form");
  expect(mockPost).toHaveBeenCalledWith("/api/incentive-rates", { entity_id: "ent_kanda", template_id: "t_prg",
    per_unit_amount: 3200, margin_cap_pct: 45, price_bands: null, price_source_rules: null });
  expect(q(host, "rate-form")).toBeNull();

  // varian bertarif sendiri → PATCH tarifnya; tanpa isian pengali khusus
  await klik(q(host, "rates-var-edit-p_blu"));
  expect(txt(q(host, "rate-form-title"))).toBe("Ubah tarif varian BTK-MEGA-001-BLU");
  expect(txt(q(host, "rate-form-scope-fixed"))).toBe("PT ini (CV Kanda Suka)");   // tarif milik PT ini: diubah di tempat
  expect(q(host, "rate-form-bands-own")).toBeNull();
  expect(q(host, "rate-form-margin").value).toBe("40");
  await isi(q(host, "rate-form-amount"), "3900");
  await kirim(host, "rate-form");
  expect(mockPatch).toHaveBeenCalledWith("/api/incentive-rates/r_blu", { data: { per_unit_amount: 3900, margin_cap_pct: 40 } });

  // "Hapus tarif" artikel = kembali ikut kategori; alasan wajib
  await klik(q(host, "rates-art-delete-t_mega"));
  expect(mockReason.mock.calls[0][0].message).toContain("ikut tarif kategori Batik");
  expect(mockDelete).toHaveBeenCalledWith("/api/incentive-rates/r_mega", { params: { reason: "alasan uji" } });

  // ubah banyak: pilih dua artikel → satu tarif, alasan di pop-up
  await klik(q(host, "rates-art-pick-t_mega"));
  await klik(q(host, "rates-art-pick-t_prg"));
  expect(txt(q(host, "rates-bulk"))).toBe("Ubah banyak (2)");
  await klik(q(host, "rates-bulk"));
  await isi(q(host, "rates-bulk-amount"), "3300");
  await isi(q(host, "rates-bulk-reason"), "Penyesuaian tarif Batik");
  mockPost.mockResolvedValueOnce({ data: { created: 1, updated: 1 } });
  await kirim(host, "rates-bulk-form");
  expect(mockPost).toHaveBeenLastCalledWith("/api/incentive-rates/bulk", { entity_id: "ent_kanda",
    template_ids: ["t_mega", "t_prg"], per_unit_amount: 3300, margin_cap_pct: null, reason: "Penyesuaian tarif Batik" });
  expect(txt(q(host, "rates-notice"))).toBe("Tarif 2 artikel disimpan: 1 baru, 1 diubah.");
});

test("KA9 kategori tanpa tarif menulis 'Belum ada tarif' dan tombol Atur tarif kategori", async () => {
  izin(PENUH);
  api();
  const host = await mount(<IncentiveSchemeView />);
  expect(txt(q(host, "rates-cat-rate-Tenun"))).toBe(TEKS_KATEGORI_TANPA_TARIF);
  expect(TEKS_KATEGORI_TANPA_TARIF).toBe("Belum ada tarif — sales tidak mendapat komisi untuk kategori ini");
  expect(txt(q(host, "rates-cat-edit-Tenun"))).toBe("Atur tarif kategori");
  expect(txt(q(host, "rates-cat-edit-Batik"))).toBe("Ubah");
  await klik(q(host, "rates-cat-edit-Tenun"));
  expect(txt(q(host, "rate-form-title"))).toBe("Atur tarif kategori Tenun");
  await isi(q(host, "rate-form-amount"), "2500");
  await kirim(host, "rate-form");
  expect(mockPost).toHaveBeenCalledWith("/api/incentive-rates", { entity_id: "ent_kanda", category: "Tenun",
    per_unit_amount: 2500, margin_cap_pct: 45 });
  // pembantu ringkasan: tarif Semua PT dan ikut kategori Semua PT
  const nb = (o) => ({ ...o, teks: o.teks.replace(/\u00a0/g, " ") });
  expect(nb(ringkasTarif("kategori", TARIF(3000, { asal_lingkup: "semua_pt" })))).toMatchObject(
    { teks: "Rp 3.000", sub: "tarif Semua PT", sendiri: false });
  expect(nb(ringkasTarif("artikel", TARIF(3000, { asal_tingkat: "kategori", asal_lingkup: "semua_pt" })))).toMatchObject(
    { teks: "ikut kategori Rp 3.000 (Semua PT)", sendiri: false });
  expect(ringkasTarif("varian", null)).toMatchObject({ teks: "Belum ada tarif — kategorinya belum bertarif", kosong: true });
});

test("KA9 cari artikel lintas kategori: daftar datar berkategori, pilih untuk Ubah banyak", async () => {
  izin(PENUH);
  api();
  const host = await mount(<IncentiveSchemeView />);
  await isi(q(host, "rates-search"), "batik");
  await act(async () => { await new Promise((r) => setTimeout(r, 350)); });   // jeda ketik 300 ms
  await settle();
  const cari = dipanggil("/incentive-rates/articles");
  expect(cari[cari.length - 1][1]).toEqual({ params: { entity_id: "ent_kanda", search: "batik", page: 1, page_size: 50 } });
  expect(q(host, "rates-cat-Batik")).toBeNull();                       // mode cari = daftar artikel, bukan pohon
  expect(txt(q(host, "rates-art-t_prg"))).toContain("BTK-PRG-002 · Batik");
  expect(txt(q(host, "rates-toolbar-count"))).toBe("2 artikel");
  await klik(q(host, "rates-art-pick-t_prg"));
  expect(txt(q(host, "rates-bulk"))).toBe("Ubah banyak (1)");
});

test("KA9 unggah Excel: pratinjau berstatus, Terapkan meminta alasan", async () => {
  izin(PENUH);
  api();
  const BARIS = [
    { baris: 2, kode_artikel: "BTK-MEGA-001", kode_varian: "", nama: "Batik Mega", lama: 3500, baru: 3600, lama_batas: 40,
      baru_batas: null, status: "ubah", pesan: "", template_id: "t_mega", product_id: "" },
    { baris: 3, kode_artikel: "BTK-PRG-002", kode_varian: "", nama: "Batik Parang", lama: 3000, baru: 3000, lama_batas: 50,
      baru_batas: null, status: "sama", pesan: "", template_id: "t_prg", product_id: "" },
    { baris: 4, kode_artikel: "BTK-MEGA-001", kode_varian: "BTK-MEGA-001-RED", nama: "Batik Mega Merah", lama: 3500,
      baru: 3700, lama_batas: 40, baru_batas: 45, status: "baru", pesan: "Tarif sendiri baru untuk PT ini.", template_id: "",
      product_id: "p_red" },
  ];
  mockPost.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/import/preview") ? { rows: BARIS }
    : { created: 1, updated: 1 } }));
  const host = await mount(<IncentiveSchemeView />);
  await klik(q(host, "rates-upload"));
  const file = new File(["xlsx"], "tarif.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
  const inp = q(host, "rates-import-file");
  Object.defineProperty(inp, "files", { value: [file] });
  await act(async () => { inp.dispatchEvent(new Event("change", { bubbles: true })); });
  await settle();
  const [url, body] = mockPost.mock.calls[0];
  expect(url).toBe("/api/incentive-rates/import/preview");
  expect(body.get("entity_id")).toBe("ent_kanda");
  expect(body.get("file").name).toBe("tarif.xlsx");
  expect(txt(q(host, "rates-import-summary"))).toBe("1 baru · 1 diubah · 1 sama · 0 galat");
  expect(txt(q(host, "rates-import-status-2"))).toBe("Diubah");
  expect(txt(q(host, "rates-import-status-4"))).toBe("Baru");
  expect(q(host, "rates-import-row-3")).toBeNull();                     // baris "sama" disembunyikan bawaan
  expect(txt(q(host, "rates-import-apply"))).toBe("Terapkan 2 perubahan");
  await klik(q(host, "rates-import-apply"));
  expect(mockReason).toHaveBeenCalledTimes(1);
  expect(mockPost).toHaveBeenLastCalledWith("/api/incentive-rates/import/apply", { entity_id: "ent_kanda", rows: [
    { baris: 2, template_id: "t_mega", per_unit_amount: 3600, margin_cap_pct: null },
    { baris: 4, product_id: "p_red", per_unit_amount: 3700, margin_cap_pct: 45 }], reason: "alasan uji" });
  expect(q(host, "rates-import")).toBeNull();
  expect(txt(q(host, "rates-notice"))).toBe("Excel diterapkan: 1 tarif baru, 1 diubah.");

  // baris bergalat → Terapkan mati dengan alasan tertulis
  mockPost.mockReset();
  mockPost.mockResolvedValue({ data: { rows: [{ ...BARIS[0], status: "galat", pesan: "Artikel BTK-X tidak ditemukan." }] } });
  await klik(q(host, "rates-upload"));
  const inp2 = q(host, "rates-import-file");
  Object.defineProperty(inp2, "files", { value: [file] });
  await act(async () => { inp2.dispatchEvent(new Event("change", { bubbles: true })); });
  await settle();
  expect(q(host, "rates-import-apply").disabled).toBe(true);
  expect(txt(q(host, "rates-import-why"))).toBe("Perbaiki baris bergalat di Excel lalu unggah ulang.");
  expect(txt(q(host, "rates-import-row-2"))).toContain("Artikel BTK-X tidak ditemukan.");
});

test("KA9 tanpa izin ubah: tombol ubah/ubah banyak/unggah tidak tampil", async () => {
  izin({ sales_force: ["view"], incentive: ["view"] });
  api();
  let host = await mount(<IncentiveSchemeView />);
  await klik(q(host, "rates-cat-toggle-Batik"));
  ["rates-cat-edit-Batik", "rates-cat-edit-Tenun", "rates-art-edit-t_mega", "rates-art-delete-t_mega",
    "rates-art-pick-t_mega", "rates-bulk", "rates-upload", "rates-art-history-t_mega"].forEach((id) => expect([id, q(host, id)]).toEqual([id, null]));
  expect(q(host, "rates-download")).not.toBeNull();
  expect(txt(q(host, "rates-why"))).toBe("Mengubah tarif komisi butuh akses Ubah di modul Pengawasan Tim Sales & Kredit.");
  // tanpa `sales_force.view`: kalimat izin, tanpa panggilan API
  document.body.innerHTML = "";
  mockGet.mockClear();
  izin({ incentive: ["view"] });
  host = await mount(<IncentiveSchemeView />);
  expect(txt(q(host, "scheme-no-access"))).toBe(TEKS_TANPA_LIHAT);
  expect(mockGet).not.toHaveBeenCalled();
  // "Semua PT": kalimat "Pilih satu PT …" + daftar tarif Semua PT (R15); tanpa izin ubah = hanya baca
  document.body.innerHTML = "";
  mockGet.mockClear();
  izin({ sales_force: ["view"], incentive: ["view"] });
  api({ extra: { "/api/incentive-rates": TARIF_GRUP } });
  host = await mount(<IncentiveSchemeView />, { entity: "all" });
  expect(txt(q(host, "scheme-all-pt"))).toContain(TEKS_SEMUA_PT);
  expect(TEKS_SEMUA_PT).toMatch(/^Pilih satu PT/);
  const urlSemua = mockGet.mock.calls.map((c) => c[0]);
  expect(urlSemua).toContain("/api/incentive-rates");                  // daftar tarif Semua PT
  expect(urlSemua.filter((u) => /incentive-rates\/(categories|articles)/.test(u))).toEqual([]);   // rute pohon menolak "Semua PT"
  expect(q(host, "group-rates-row-r_cat_all")).not.toBeNull();
  expect(q(host, "group-rates-edit-r_cat_all")).toBeNull();
  expect(q(host, "group-rates-delete-r_cat_all")).toBeNull();
});

// ═══ ① sumber insentif, ③④⑤ pengaturan, akrual, jenjang arsip ═════════════════════════════════════════════════════
test("KA9 sumber insentif: keduanya dari pay_on_invoice → peringatan + konfirmasi cara pembukuan, simpan lapisan PT", async () => {
  izin(PENUH);
  api({ mode: "pay_on_invoice" });
  const host = await mount(<IncentiveSchemeView />);
  expect(txt(q(host, "scheme-source-current"))).toContain("Dibayar saat faktur terbit");
  expect(q(host, "scheme-source-open-config")).not.toBeNull();
  ["otomatis", "lembar", "keduanya"].forEach((p) => expect(q(host, `scheme-source-${p}`).checked).toBe(false));
  expect(q(host, "scheme-source-save").disabled).toBe(true);
  await klik(q(host, "scheme-source-keduanya"));
  expect(txt(q(host, "scheme-source-warning"))).toBe("Insentif dari dua sumber dibayar bersama.");
  await klik(q(host, "scheme-source-save"));
  const arg = mockReason.mock.calls[0][0];
  expect(arg.message).toContain("Cara pembukuan berubah menjadi dicadangkan tiap bulan.");
  expect(mockPut).toHaveBeenCalledWith("/api/config/values", { items: [{ key: "hr.payroll_commission_mode",
    value: "auto_and_sheet", scope_type: "entity", scope_id: "ent_kanda", reason: "alasan uji", effective_from: "" }] });
  // ③ ④ ⑤ — kunci Pusat Pengaturan per bagian; incentive_unit & strategy tidak ikut
  const kunci = mockSettings.map((o) => (o.includeKeys || []).join(","));
  expect(kunci).toEqual(expect.arrayContaining([
    "commission.price_basis,commission.price_bands,commission.price_source_rules,commission.discount_",
    "commission.achievement_multiplier,commission.achievement_basis,commission.achievement_tiers",
    "commission.default_margin_cap_pct"]));
  expect(kunci.join(",")).not.toMatch(/incentive_unit|commission\.strategy/);
  expect(mockSettings.every((o) => o.selectedEntity === "ent_kanda")).toBe(true);
  // R16 — tertanam: tanpa kotak cari & pemilih cakupan per bagian; awalan testid unik; cakupan PT ditulis sekali
  expect(mockBrowsers.map((b) => b.embedded)).toEqual(expect.arrayContaining(["scheme-price-cfg", "scheme-achievement-cfg", "scheme-cap-cfg"]));
  expect(mockBrowsers.every((b) => !!b.embedded && !b.searchPlaceholder)).toBe(true);
  expect(txt(q(host, "scheme-settings-scope"))).toContain("CV Kanda Suka");
  expect(host.querySelectorAll('[data-testid="scheme-settings-scope"]')).toHaveLength(1);
  expect(q(host, "legacy-scheme-editor")).toBeNull();                  // strategi per_sku
});

test("KA9 akrual bulanan pindah ke Skema & Tarif; jenjang arsip hanya untuk strategi achievement_tiered", async () => {
  izin(PENUH);
  api({ mode: "auto_and_sheet", strategy: "achievement_tiered" });
  mockPost.mockResolvedValue({ data: { created: true, message: "Akrual insentif 2026-11 diposting (JE KANDA/JE-1)." } });
  let host = await mount(<IncentiveSchemeView />);
  const tombol = q(host, "ins-accrual-post");
  expect(txt(tombol)).toMatch(/^Bukukan akrual komisi \S+ \d{4}$/);   // KA-7: keduanya dibayar = akrual jalan
  await klik(tombol);
  expect(mockConfirm.mock.calls[0][0].message.replace(/ /g, " ")).toContain("Beban komisi Rp 1.250.000 dibukukan ke buku CV Kanda Suka");
  expect(mockPost.mock.calls[0][0]).toBe("/api/sales/incentive/post-gl");
  expect(q(host, "legacy-scheme-editor")).not.toBeNull();
  expect(dipanggil("/config/explain")[0][1]).toEqual({ params: { key: "commission.strategy", entity_id: "ent_kanda" } });
  document.body.innerHTML = "";
  api({ mode: "sheet" });
  host = await mount(<IncentiveSchemeView />);
  expect(q(host, "ins-accrual")).toBeNull();
  expect(txt(q(host, "scheme-rates-unused"))).toContain("tidak dipakai");
});

test("KA9 simulasi: Sekarang vs Dengan perubahan + catatan server; 403 berkalimat", async () => {
  const BARIS = (over) => ({ category: "Batik", sku: "BTK-MEGA-001", name: "Batik Mega", template_id: "t_mega", qty_base: 120,
    commission: 420000, rate: 3500, rate_origin: "artikel_pt", price_factor: 1, price_reason: "harga_penuh",
    price_reason_label: "Harga jual tidak di bawah harga acuan", achievement_factor: 1, capped: false, ...over });
  const rows = gabungSimulasi([BARIS()], [BARIS({ rate: 4000, commission: 480000 })]);
  expect(rows).toHaveLength(1);
  expect(rows[0]).toMatchObject({ kunci: "t_mega", nama: "Batik Mega", yard: 120 });
  expect(rows[0].a.komisi).toBe(420000);
  expect(rows[0].b).toMatchObject({ komisi: 480000, tarif: [4000] });
  izin(PENUH);
  api();
  mockPost.mockResolvedValue({ data: { sekarang: { total_incentive: 420000, breakdown: [BARIS()] },
    dengan_perubahan: { total_incentive: 480000, breakdown: [BARIS({ rate: 4000, commission: 480000 })] },
    catatan: "Perubahan tarif berlaku untuk pesanan yang dibuat sesudah disimpan." } });
  const host = await mount(<IncentiveSchemeView />);
  await isi(q(host, "scheme-sim-sales"), "u_andi");
  await klik(q(host, "scheme-sim-draft-add"));
  await isi(q(host, "scheme-sim-draft-cat-0"), "Batik");
  await isi(q(host, "scheme-sim-draft-rate-0"), "4000");
  await klik(q(host, "scheme-sim-run"));
  const [url, body] = mockPost.mock.calls[0];
  expect(url).toBe("/api/incentive-rates/simulate");
  expect(body).toMatchObject({ entity_id: "ent_kanda", sales_id: "u_andi", draft_rates: [{ category: "Batik", per_unit_amount: 4000 }] });
  expect(body.period).toMatch(/^\d{4}-\d{2}$/);
  expect(txt(q(host, "scheme-sim-row-t_mega"))).toContain("Rp 3.500 → Rp 4.000");
  expect(txt(q(host, "scheme-sim-total-now"))).toBe("Rp 420.000");
  expect(txt(q(host, "scheme-sim-total-new"))).toBe("Rp 480.000");
  expect(txt(q(host, "scheme-sim-note"))).toBe("Perubahan tarif berlaku untuk pesanan yang dibuat sesudah disimpan.");
  expect(txt(q(host, "scheme-sim-for"))).toMatch(/^Hasil untuk Andi · \S+ \d{4}$/);
  // R16 — masukan berubah = hasil lama dibuang
  await isi(q(host, "scheme-sim-draft-rate-0"), "4100");
  expect(q(host, "scheme-sim-result")).toBeNull();
  mockPost.mockRejectedValueOnce(Object.assign(new Error("x"), { response: { status: 403,
    data: { detail: "Anda tidak berwenang melihat komisi sales ini." } } }));
  await klik(q(host, "scheme-sim-run"));
  expect(txt(q(host, "scheme-sim-error"))).toContain("Anda tidak berwenang melihat komisi sales ini.");
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
  api({ extra: { "/api/incentive-rates": TARIF_GRUP } });
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
  api({ extra: { "/api/incentive-rates": () => new Promise((r) => { lepas = r; }) } });
  const host = await mount(<IncentiveSchemeView />);
  await klik(q(host, "rates-cat-toggle-Batik"));
  await klik(q(host, "rates-art-edit-t_mega"));                         // tarif sendiri → pita dimuat (tertahan)
  expect(txt(q(host, "rate-form-special-locked"))).toBe("Memuat pengali khusus…");
  await klik(q(host, "rate-form-close"));
  await klik(q(host, "rates-art-edit-t_prg"));
  expect(txt(q(host, "rate-form-title"))).toBe("Atur tarif artikel Batik Parang");
  await act(async () => { lepas({ data: [{ id: "r_mega", price_bands: [{ sampai_pct: null, pengali: 0.5 }], price_source_rules: null }] }); });
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
