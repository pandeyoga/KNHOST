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
// Berkas ini: pemetaan sumber, tab & alias, pohon tarif, Excel, izin, sumber insentif, akrual, simulasi dasar.
// Putaran tinjauan R15/R16 + Target & Aturan + LegacySchemeEditor di `kaSkemaTarifLanjutan.test.js` (dipecah KA-11:
// batas keras ukuran berkas `validate_compliance`). Pengaturan tiruan & pembantu di bawah sama di kedua berkas.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import IncentiveSchemeView, { bagianUntukKunci, TEKS_SEMUA_PT, TEKS_TANPA_LIHAT } from "../incentive/IncentiveSchemeView";
import { gabungSimulasi } from "../incentive/SchemeSimulation";
import { butuhKonfirmasiAkru, komisiOtomatisJalan, MODE_AKRU, MODE_KEDUANYA, MODE_TANPA_MESIN, modeDariPilihan,
  pilihanSumber } from "../incentive/incentiveModes";
import { ringkasTarif, TEKS_KATEGORI_TANPA_TARIF } from "../incentive/ArticleRatesTable";
import { HUB_TABS, resolveDeepLinkTarget } from "../../config/navigationConfig";
import { PAGE_META } from "../../config/navMeta";
import { COMMISSION_HOME, configTargetFor } from "../settings/config/configGroupViews";
import { COMMISSION_LINK } from "../settings/config/SettingsHub";
import { AppNavProvider } from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { setAccessContext } from "../../config/roles";

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
    rate: TARIF(3500, { margin_cap_pct: 40, asal_tingkat: "artikel", rate_id: "r_mega" }), own_rate_id: "r_mega", variant_exceptions: 1,
    fallback: { per_unit_amount: 3000, margin_cap_pct: 50, asal_tingkat: "kategori", asal_lingkup: "pt", rate_id: "r_cat_batik" } },
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

  // "Hapus tarif" artikel = tarif pengganti yang sebenarnya (server `fallback`, M6); alasan wajib
  await klik(q(host, "rates-art-delete-t_mega"));
  expect(mockReason.mock.calls[0][0].message.replace(/\u00a0/g, " ")).toBe("Sesudah dihapus, artikel ini memakai tarif kategori PT ini Rp 3.000. "
    + "Berlaku untuk pesanan yang dibuat sesudah dihapus.");
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

test("KA9 simulasi: Aturan sekarang vs Dengan perubahan + selisih, info potret, tanda, catatan server; 403 berkalimat", async () => {
  const BARIS = (over) => ({ category: "Batik", sku: "BTK-MEGA-001", name: "Batik Mega", template_id: "t_mega", qty_base: 120,
    commission: 420000, rate: 3500, rate_origin: "artikel_pt", price_factor: 1, price_reason: "harga_penuh",
    price_reason_label: "Harga jual tidak di bawah harga acuan", achievement_factor: 1, capped: false, ...over });
  const rows = gabungSimulasi([BARIS()], [BARIS({ rate: 4000, commission: 480000 })]);
  // KA-11 — kolom kanan memuat pesanan yang dipotret tanpa tarif (tidak berkomisi sekarang): yard dua sisi berbeda
  const lebih = gabungSimulasi([BARIS()], [BARIS(), BARIS({ qty_base: 30, rate: 4000, commission: 120000 })]);
  expect([lebih[0].a.yard, lebih[0].b.yard]).toEqual([120, 150]);
  expect(rows).toHaveLength(1);
  expect(rows[0]).toMatchObject({ kunci: "t_mega", nama: "Batik Mega", yard: 120 });
  expect(rows[0].a.komisi).toBe(420000);
  expect(rows[0].b).toMatchObject({ komisi: 480000, tarif: [4000] });
  izin(PENUH);
  api();
  mockPost.mockResolvedValue({ data: { sekarang: { total_incentive: 420000, breakdown: [BARIS()] },
    dengan_perubahan: { total_incentive: 480000, breakdown: [BARIS({ rate: 4000, commission: 480000 })] },
    komisi_menurut_potret: 350000, tanda: [],
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
  expect(txt(q(host, "scheme-sim-yard-t_mega"))).toBe("120");   // yard sama di dua sisi → satu angka
  expect(txt(q(host, "scheme-sim-total-now"))).toBe("Rp 420.000");
  expect(txt(q(host, "scheme-sim-total-new"))).toBe("Rp 480.000");
  expect(txt(q(host, "scheme-sim-total-diff"))).toBe("+Rp 60.000");
  expect(txt(q(host, "scheme-sim-diff-t_mega"))).toBe("+Rp 60.000");
  const kepala = [...q(host, "scheme-sim-table").querySelectorAll("th")].map((th) => txt(th));
  expect(kepala.slice(-3)).toEqual(["Aturan sekarang", "Dengan perubahan", "Selisih"]);
  expect(txt(q(host, "scheme-sim-total-now").previousSibling)).toBe("Aturan sekarang");
  // R18 — angka yang dibayar (aturan saat pesanan dibuat) = baris info, bukan kolom pembanding
  expect(txt(q(host, "scheme-sim-actual"))).toBe("Komisi bulan ini menurut aturan saat pesanan dibuat: Rp 350.000");
  expect(host.querySelector('[data-testid^="scheme-sim-flag-"]')).toBeNull();
  expect(txt(q(host, "scheme-sim-note"))).toBe("Perubahan tarif berlaku untuk pesanan yang dibuat sesudah disimpan.");
  expect(txt(q(host, "scheme-sim-for"))).toMatch(/^Hasil untuk Andi · \S+ \d{4}$/);
  // R16 — masukan berubah = hasil lama dibuang
  await isi(q(host, "scheme-sim-draft-rate-0"), "4100");
  expect(q(host, "scheme-sim-result")).toBeNull();
  // tanda server: strategi berjenjang / komisi otomatis tidak dibayar → peringatan tertulis
  mockPost.mockResolvedValueOnce({ data: { sekarang: { total_incentive: 1000, breakdown: [] },
    dengan_perubahan: { total_incentive: 1000, breakdown: [] }, komisi_menurut_potret: 1000, catatan: "",
    tanda: [{ kode: "strategi_berjenjang", pesan: "Draf tidak berpengaruh: PT ini memakai cara hitung berjenjang." },
      { kode: "tanpa_komisi_otomatis", pesan: "Komisi otomatis tidak dibayar di PT ini." }] } });
  await klik(q(host, "scheme-sim-run"));
  expect(txt(q(host, "scheme-sim-flag-strategi_berjenjang"))).toBe("Draf tidak berpengaruh: PT ini memakai cara hitung berjenjang.");
  expect(txt(q(host, "scheme-sim-flag-tanpa_komisi_otomatis"))).toBe("Komisi otomatis tidak dibayar di PT ini.");
  expect(txt(q(host, "scheme-sim-total-diff"))).toBe("+Rp 0");
  mockPost.mockRejectedValueOnce(Object.assign(new Error("x"), { response: { status: 403,
    data: { detail: "Anda tidak berwenang melihat komisi sales ini." } } }));
  await klik(q(host, "scheme-sim-run"));
  expect(txt(q(host, "scheme-sim-error"))).toContain("Anda tidak berwenang melihat komisi sales ini.");
});
