// Komisi per artikel — perbaikan tinjauan akhir di layar Skema & Tarif (ledger R19):
//  · I5 — pop-up tarif membaca pita khusus per id (`GET /api/incentive-rates/{id}`); tidak terbaca = isian khusus terkunci
//    dan TIDAK dikirim (dulu daftar terpotong → `price_bands: null` tersimpan diam-diam);
//  · M3 — "Berlaku untuk: Semua PT" dan ubah/hapus tarif Semua PT hanya untuk peran lintas PT (`caps.global_write`);
//  · M5 — petunjuk di bawah "Pita pengali sendiri" bila dasar pengali harga PT bukan "Selisih dari harga acuan";
//  · M6 — kalimat konfirmasi hapus menyebut tarif pengganti yang sebenarnya;
//  · T9 — tautan dalam ke bagian pengaturan tertanam membuka & menggulir kartunya, bukan menulis kunci mentah sebagai
//    istilah cari.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import RateFormModal, { TEKS_KHUSUS_TERKUNCI, TEKS_PITA_DASAR, TEKS_SEMUA_PT_TERKUNCI } from "../incentive/RateFormModal";
import GroupRatesList, { TEKS_GRUP_TARIF_TERKUNCI, akibatHapusGrup } from "../incentive/GroupRatesList";
import { akibatHapus } from "../incentive/ArticleRatesTable";
import { useSettingsBrowser } from "../settings/config/SettingsHub";
import { AppNavProvider } from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { setAccessContext } from "../../config/roles";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockPatch = jest.fn();
const mockDelete = jest.fn();
const mockReason = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), put: jest.fn(), patch: (...a) => mockPatch(...a),
    delete: (...a) => mockDelete(...a), defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true, askConfirm: jest.fn(), askReason: (...a) => mockReason(...a), default: {},
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value ?? ""} onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      <option value="">{p.placeholder || ""}</option>
      {(p.options || []).filter((o) => o.value !== "").map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const ENT = [{ id: "ent_kanda", legal_name: "CV Kanda Suka", short_name: "Kanda" }];
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const txt = (el) => (el?.textContent || "").replace(/\u00a0/g, " ");
async function settle() { for (let i = 0; i < 12; i += 1) await act(async () => {}); }
const klik = async (el) => { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await settle(); };
async function isi(el, value) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await settle();
}
async function kirim(host, formId) {
  await act(async () => { q(host, formId).querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
  await settle();
}
async function mount(node, entity = "ent_kanda") {
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => {
    createRoot(host).render(
      <EntityScopeProvider selectedEntity={entity} entities={ENT} canSwitch>
        <AppNavProvider role="manager" onOpenDocument={() => {}} onNavigateTo={() => {}}>{node}</AppNavProvider>
      </EntityScopeProvider>);
  });
  await settle();
  return host;
}
const MEGA = { tingkat: "artikel", nama: "Batik Mega", template_id: "t_mega", adaDiTingkat: true,
  rate: { per_unit_amount: 3500, margin_cap_pct: 40, asal_tingkat: "artikel", asal_lingkup: "pt", rate_id: "r_mega" } };

beforeEach(() => {
  [mockGet, mockPost, mockPatch, mockDelete, mockReason].forEach((m) => m.mockReset());
  document.body.innerHTML = "";
  mockPost.mockResolvedValue({ data: {} });
  mockPatch.mockResolvedValue({ data: {} });
  mockReason.mockResolvedValue("alasan uji");
  setAccessContext({ role: "manager", permissions: { sales_force: ["view", "update", "delete"], audit: ["view"] },
    view_resources: {}, hidden_views: [], view_actions: {} });
});
afterEach(() => setAccessContext(null));

test("I5 pita khusus dibaca per id; tarif tidak terbaca (404) = terkunci dan pita tidak dikirim", async () => {
  mockGet.mockImplementation((url) => (url === "/api/incentive-rates/r_mega"
    ? Promise.resolve({ data: { id: "r_mega", price_bands: [{ sampai_pct: null, pengali: 0.5 }], price_source_rules: null } })
    : Promise.reject(Object.assign(new Error("x"), { response: { status: 404, data: { detail: "Tarif tidak ditemukan." } } }))));
  const onSaved = jest.fn();
  let host = await mount(<RateFormModal sasaran={MEGA} entityId="ent_kanda" pt="CV Kanda Suka" bawaanBatas={50}
    onClose={() => {}} onSaved={onSaved} />);
  expect(mockGet).toHaveBeenCalledWith("/api/incentive-rates/r_mega");
  expect(mockGet.mock.calls.some((c) => c[0] === "/api/incentive-rates")).toBe(false);   // bukan daftar (dulu terpotong)
  expect(q(host, "rate-form-bands-own").checked).toBe(true);
  document.body.innerHTML = "";
  host = await mount(<RateFormModal sasaran={{ ...MEGA, rate: { ...MEGA.rate, rate_id: "r_hilang" } }} entityId="ent_kanda"
    pt="CV Kanda Suka" bawaanBatas={50} onClose={() => {}} onSaved={onSaved} />);
  expect(txt(q(host, "rate-form-special-locked"))).toBe(TEKS_KHUSUS_TERKUNCI);
  await isi(q(host, "rate-form-amount"), "3600");
  await kirim(host, "rate-form");
  expect(mockPatch).toHaveBeenLastCalledWith("/api/incentive-rates/r_hilang", { data: { per_unit_amount: 3600, margin_cap_pct: 40 } });
});

test("M3 tanpa kemampuan lintas PT: pilihan Semua PT tidak tampil, tarif Semua PT diganti tarif khusus PT ini", async () => {
  mockGet.mockResolvedValue({ data: {} });
  const grup = { tingkat: "kategori", nama: "Batik", category: "Batik", adaDiTingkat: true,
    rate: { per_unit_amount: 3000, margin_cap_pct: 50, asal_lingkup: "semua_pt", rate_id: "r_cat_all" } };
  let host = await mount(<RateFormModal sasaran={grup} entityId="ent_kanda" pt="CV Kanda Suka" bawaanBatas={45}
    bolehSemuaPt={false} onClose={() => {}} onSaved={jest.fn()} />);
  expect(q(host, "rate-form-scope-semua_pt")).toBeNull();
  expect(txt(q(host, "rate-form-scope-fixed"))).toBe("PT ini (CV Kanda Suka)");
  expect(txt(q(host, "rate-form-scope-locked"))).toBe(TEKS_SEMUA_PT_TERKUNCI);
  await isi(q(host, "rate-form-amount"), "3300");
  await kirim(host, "rate-form");
  expect(mockPost).toHaveBeenLastCalledWith("/api/incentive-rates", { entity_id: "ent_kanda", category: "Batik",
    per_unit_amount: 3300, margin_cap_pct: 45 });
  expect(mockPatch).not.toHaveBeenCalled();
  // dengan kemampuan lintas PT pilihan tetap ada
  document.body.innerHTML = "";
  host = await mount(<RateFormModal sasaran={grup} entityId="ent_kanda" pt="CV Kanda Suka" bawaanBatas={45}
    onClose={() => {}} onSaved={jest.fn()} />);
  expect(q(host, "rate-form-scope-semua_pt")).not.toBeNull();
  expect(q(host, "rate-form-scope-locked")).toBeNull();
});

test("M3 mode Semua PT tanpa kemampuan lintas PT: daftar tarif Semua PT hanya baca", async () => {
  const TARIF = [{ id: "r_cat_all", entity_id: "all", category: "Batik", template_id: "", product_id: "", per_unit_amount: 3000,
    margin_cap_pct: 50, status: "active" }];
  mockGet.mockResolvedValue({ data: TARIF });
  let host = await mount(<GroupRatesList bolehUbahGrup={false} />, "all");
  expect(q(host, "group-rates-row-r_cat_all")).not.toBeNull();
  expect(q(host, "group-rates-edit-r_cat_all")).toBeNull();
  expect(q(host, "group-rates-delete-r_cat_all")).toBeNull();
  expect(txt(q(host, "group-rates-locked"))).toBe(TEKS_GRUP_TARIF_TERKUNCI);
  document.body.innerHTML = "";
  host = await mount(<GroupRatesList bolehUbahGrup />, "all");
  expect(q(host, "group-rates-locked")).toBeNull();
  await klik(q(host, "group-rates-delete-r_cat_all"));
  expect(mockReason.mock.calls[0][0].message).toBe("Tarif ini berlaku untuk semua PT yang tidak punya tarif sendiri di "
    + "tingkat ini. Sesudah dihapus, PT itu tidak mendapat komisi untuk kategori ini. Berlaku untuk pesanan yang dibuat "
    + "sesudah dihapus.");
});

test("M5 petunjuk pita: hanya bila dasar pengali harga PT bukan selisih dari harga acuan", async () => {
  mockGet.mockResolvedValue({ data: { id: "r_mega", price_bands: null, price_source_rules: null } });
  let host = await mount(<RateFormModal sasaran={MEGA} entityId="ent_kanda" pt="CV Kanda Suka" dasarHarga="diskon_baris"
    onClose={() => {}} onSaved={jest.fn()} />);
  expect(txt(q(host, "rate-form-bands-basis"))).toBe(TEKS_PITA_DASAR);
  document.body.innerHTML = "";
  host = await mount(<RateFormModal sasaran={MEGA} entityId="ent_kanda" pt="CV Kanda Suka" dasarHarga="pricelist"
    onClose={() => {}} onSaved={jest.fn()} />);
  expect(q(host, "rate-form-bands-basis")).toBeNull();
});

test("M6 kalimat hapus menyebut tarif pengganti yang sebenarnya", () => {
  const n = (s) => s.replace(/\u00a0/g, " ");
  expect(n(akibatHapus("varian", { per_unit_amount: 3500, asal_tingkat: "artikel", asal_lingkup: "semua_pt" })))
    .toBe("Sesudah dihapus, varian ini memakai tarif artikel Semua PT Rp 3.500.");
  expect(n(akibatHapus("artikel", { per_unit_amount: 3000, asal_tingkat: "kategori", asal_lingkup: "pt" })))
    .toBe("Sesudah dihapus, artikel ini memakai tarif kategori PT ini Rp 3.000.");
  expect(akibatHapus("kategori", { tanpa_tarif: true }))
    .toBe("Sesudah dihapus, kategori ini tidak punya tarif lagi — sales tidak mendapat komisi untuknya.");
  expect(akibatHapus("artikel", undefined, "Batik")).toBe("Artikel ini kembali ikut tarif artikel Semua PT bila ada, atau tarif kategori Batik.");
  expect(akibatHapusGrup("artikel")).toBe("Sesudah dihapus, PT itu memakai tarif kategori artikel ini (tarif PT itu sendiri atau Semua PT).");
});

test("T9 tautan dalam ke bagian tertanam: kartu dibuka, bukan kunci mentah sebagai istilah cari", async () => {
  mockGet.mockImplementation((url) => Promise.resolve({ data: url === "/api/config/registry"
    ? { groups: [{ id: "penjualan", label: "Penjualan & harga", count: 1 }], entries: [{ key: "commission.price_bands", group: "penjualan" }],
      caps: { global_write: true } }
    : { groups: [], items: [] } }));
  const hasil = {};
  function Coba({ tanpaCari }) {
    const s = useSettingsBrowser({ selectedEntity: "ent_kanda", includeKeys: ["commission.price_bands"], focusKey: "commission.price_bands",
      focusNonce: 1, focusWithoutSearch: tanpaCari });
    hasil[tanpaCari ? "tertanam" : "biasa"] = s;
    return null;
  }
  await mount(<><Coba tanpaCari /><Coba tanpaCari={false} /></>);
  expect(hasil.tertanam.q).toBe("");
  expect(hasil.tertanam.term).toBe("");
  expect(hasil.tertanam.openKeys.has("commission.price_bands")).toBe(true);
  expect(hasil.tertanam.highlight).toBe("commission.price_bands");
  expect(hasil.biasa.q).toBe("commission.price_bands");            // layar Pusat Pengaturan biasa: perilaku lama
});
