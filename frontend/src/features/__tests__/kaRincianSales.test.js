// KA-10 — rincian faktor komisi untuk sales (sisi layar tanpa peramban): kartu "Capaian & Insentif Saya" (daftar
// "Rincian komisi otomatis") dan tabel "Rincian Komisi per Artikel" di Beranda Sales. Pengali berformat koma (×0,8);
// baris yang dibatasi hanya menulis "dibatasi batas margin" — tidak pernah angka margin/HPP.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import MyIncentiveCard from "../incentive/MyIncentiveCard";
import { formatPengali, ringkasRincian, TEKS_DIBATASI } from "../incentive/rincianKomisi";
import SalesHome from "../home/SalesHome";
import { AppNavProvider } from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockConfirm = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), put: () => Promise.resolve({ data: {} }),
    patch: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: (...a) => mockConfirm(...a),
  askReason: () => Promise.resolve("alasan uji"),
  default: {},
}));
// Pustaka radix/cmdk tidak termuat di lingkungan uji ini — diganti elemen polos.
jest.mock("../../components/KNSelect", () => {
  const S = (p) => <select data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />;
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/KNDatePicker", () => () => null);
jest.mock("../../components/EntityScopeBanner", () => () => <div data-testid="scope" />);
jest.mock("../incentive/LegacySchemeEditor", () => () => <div data-testid="legacy-scheme" />);
// KA-9 — Pusat Pengaturan tertanam di Skema & Tarif tidak diuji di sini (suite kaSkemaTarif / Pengaturan).
jest.mock("../settings/config/SettingsHub", () => ({ useSettingsBrowser: () => ({ items: [] }), SettingsBrowser: () => null,
  SettingsNotice: () => null }));
jest.mock("../incentive/ArticleRatesTable", () => () => <div data-testid="rates-tree" />);
jest.mock("../sales_admin/KeepPendingPanel", () => () => null);
jest.mock("../home/HomeWaitingBoards", () => () => null);
jest.mock("../crm/CustomerList", () => () => null);
jest.mock("../crm/LeadsPipeline", () => () => null);
jest.mock("../crm/OmnichannelInteractions", () => () => null);
jest.mock("../crm/promiseUi", () => ({ PromiseFields: () => null, promiseError: () => "" }));
jest.mock("../hr/AttendanceView", () => ({ STATUS_PILL: {}, fmtTime: () => "", fmtMin: () => "" }));
jest.mock("../hr/MyPayslipCard", () => ({ MyPayslipCard: () => <div data-testid="slip-card" /> }));
jest.mock("../hr/MyLeaveCard", () => ({ MyLeaveCard: () => null }));
jest.mock("../hr/MyKpiCard", () => ({ MyKpiCard: () => null }));
jest.mock("../hr/MyDesignerKpiSection", () => ({ __esModule: true, default: () => null, showMyDesignerKpi: () => false }));
jest.mock("recharts", () => {
  const P = ({ children }) => <div>{children}</div>;
  return { LineChart: P, Line: () => null, XAxis: () => null, YAxis: () => null, CartesianGrid: () => null,
    Tooltip: () => null, ResponsiveContainer: P };
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView || function scrollIntoView() {};   // jsdom

const ENT = [{ id: "ent_kanda", legal_name: "CV Kanda Suka", short_name: "Kanda" }];
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const txt = (el) => (el?.textContent || "").replace(/ /g, " ");
async function settle() { for (let i = 0; i < 10; i += 1) await act(async () => {}); }
const klik = async (el) => { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await settle(); };
async function mount(node, { entity = "ent_kanda" } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(
      <EntityScopeProvider selectedEntity={entity} entities={ENT} canSwitch>
        <AppNavProvider role="manager" onOpenDocument={() => {}} onNavigateTo={() => {}}>{node}</AppNavProvider>
      </EntityScopeProvider>);
  });
  await settle();
  return host;
}
const dipanggil = () => mockGet.mock.calls.map((c) => String(c[0]).replace(/^\/api/, ""));

const rute = (map) => mockGet.mockImplementation((url) => {
  const k = Object.keys(map).find((p) => String(url).includes(p));
  return k ? (map[k] instanceof Error ? Promise.reject(map[k]) : Promise.resolve({ data: map[k] })) : Promise.resolve({ data: {} });
});

const BARIS_A = { name: "Batik Mega", sku: "BTK-MEGA", qty_base: 120, unit: "yard", rate: 3500, rate_origin: "Tarif artikel (PT ini)",
  price_factor: 0.8, price_reason_label: "diskon 2–3%", achievement_factor: 1.2, capped: false, commission: 336000 };
const BARIS_B = { ...BARIS_A, name: "Batik Kawung", sku: "BTK-KWG", unit: "", rate: 500, rate_origin: "", price_factor: 1, price_reason_label: "",
  achievement_factor: null, capped: true, commission: 50000 };
const KARTU = (breakdown) => ({ period: "2026-11", entity_id: "ent_kanda", mode: "accrue_then_settle",
  achievement: { target_sales: 0, omzet_bersih: 0, target_collection: 0, uang_masuk: 0 }, sheets: [],
  auto_commission: { mtd: 386000, projection_month_end: 900000, breakdown } });

test("KA10 pengali berformat koma id-ID; kosong jadi tanda strip", () => {
  expect(formatPengali(0.8)).toBe("×0,8");
  expect(formatPengali(1)).toBe("×1");
  expect(formatPengali(null)).toBe("—");
  const r = ringkasRincian(BARIS_A);
  expect(r.pengaliHarga).toBe("×0,8 · diskon 2–3%");
  expect(r.pengaliCapaian).toBe("×1,2");
  expect(r.dibatasi).toBe(false);
  expect(r.asal).toBe("Tarif artikel (PT ini)");
  expect(ringkasRincian(BARIS_B).catatanBatas).toBe(TEKS_DIBATASI);
});

test("KA10 kartu: baris rincian menulis 'dibatasi batas margin' tanpa angka margin", async () => {
  rute({ "/incentive/me": KARTU([BARIS_A, BARIS_B]) });
  const host = await mount(<MyIncentiveCard period="2026-11" />);
  const a = txt(q(host, "my-incentive-auto-rincian-0"));
  expect(a).toContain("Batik Mega");
  expect(a).toContain("harga ×0,8 · diskon 2–3%");
  expect(a).toContain("capaian ×1,2");
  expect(a).toContain("120 yard · tarif Rp 3.500/yard (Tarif artikel (PT ini)) · harga");   // KA-11 — asal tarif tertulis
  expect(q(host, "my-incentive-auto-rincian-1-asal")).toBeNull();
  expect(txt(q(host, "my-incentive-auto-rincian-1"))).toContain("100 satuan".replace("100", "120") + " · tarif Rp 500/satuan");
  expect(a).not.toContain("dibatasi");
  expect(q(host, "my-incentive-auto-rincian-0-batas")).toBeNull();
  expect(txt(q(host, "my-incentive-auto-rincian-1-batas"))).toBe(" · dibatasi batas margin");
  expect(txt(q(host, "my-incentive-auto-rincian"))).not.toMatch(/margin\s*\d|HPP|%\s*margin/i);
});

test("KA10 kartu: tanpa rincian atau tanpa komisi otomatis, daftar tidak tampil", async () => {
  rute({ "/incentive/me": KARTU([]) });
  expect(q(await mount(<MyIncentiveCard period="2026-11" />), "my-incentive-auto-rincian")).toBeNull();
  document.body.innerHTML = "";
  rute({ "/incentive/me": { ...KARTU([BARIS_A]), mode: "sheet", auto_commission: null } });
  expect(q(await mount(<MyIncentiveCard period="2026-11" />), "my-incentive-auto-rincian")).toBeNull();
});

test("KA10 beranda sales: kolom tarif dan pengali tampil", async () => {
  const BERANDA = { period: "2026-11", incentive_mode: "accrue_then_settle", target: { amount: 0, achievement_pct: 0 },
    kpi: { total_sales: 1000, total_collected: 0, overdue_amount: 0 }, history: [], customers: [], collections: [],
    recent_orders: [], waiting_boards: [],
    commission: { mtd_accrual: 386000, projection_month_end: 900000, strategy: "per_sku", base_amount: 0,
      breakdown: [{ ...BARIS_A, category: "Batik" }, { ...BARIS_B, category: "Batik" }] } };
  rute({ "/home/sales": BERANDA, "/incentive/me": KARTU([]) });
  const host = await mount(<SalesHome token="t" user={{ id: "u1", role: "sales", name: "Citra" }} onNavigate={() => {}} />);
  const kotak = q(host, "sales-home-commission-breakdown");
  expect(txt(kotak)).toContain("Rincian Komisi per Artikel");
  const th = txt(q(host, "commission-breakdown-table").querySelector("thead"));
  expect(th).toMatch(/Tarif.*Pengali harga.*Pengali capaian.*Komisi/);
  expect(txt(q(host, "commission-breakdown-rate-0"))).toBe("Rp 3.500/yard");
  expect(txt(q(host, "commission-breakdown-rate-1"))).toBe("Rp 500/satuan");
  expect(txt(q(host, "commission-breakdown-origin-0"))).toBe("Tarif artikel (PT ini)");   // KA-11 — asal tarif tertulis
  expect(q(host, "commission-breakdown-origin-1")).toBeNull();
  expect(txt(q(host, "commission-breakdown-table"))).toMatch(/120 yard.*120 satuan/);
  expect(txt(q(host, "commission-breakdown-price-0"))).toBe("×0,8 · diskon 2–3%");
  expect(txt(q(host, "commission-breakdown-ach-0"))).toBe("×1,2");
  expect(q(host, "commission-breakdown-capped-0")).toBeNull();
  expect(txt(q(host, "commission-breakdown-capped-1"))).toBe("dibatasi batas margin");
  expect(txt(q(host, "commission-breakdown-ach-1"))).toBe("—");
});

// BTP-5 (A1-6) — komisi barang yang tidak jadi dikirim dipotong di bulan penutupan: baris koreksi menulis pesanan &
// alasannya; saldo potongan (terbawa / dibawa) tampil sebagai baris keterangan tanpa tarif & pengali.
test("BTP5 baris koreksi & saldo potongan berlabel pesanan dan alasannya", async () => {
  const KOREKSI = { ...BARIS_A, qty_base: -60, commission: -210000, price_factor: 1, achievement_factor: 1,
    price_reason: "koreksi_tutup_sisa", price_reason_label: "Koreksi komisi: sisa pesanan SO-BTP5-1 ditutup" };
  const DIBAWA = { name: "Sisa potongan komisi dibawa ke bulan berikutnya", sku: "", qty_base: 0, unit: "", rate: 0,
    rate_origin: "", price_factor: null, achievement_factor: null, capped: false, commission: 210000,
    price_reason: "potongan_dibawa", price_reason_label: "Sisa potongan komisi dibawa ke bulan berikutnya" };
  const k = ringkasRincian(KOREKSI);
  expect(k.jenis).toBe("koreksi");
  expect(k.pengaliHarga).toBe("×1");
  expect(k.keterangan).toBe("Koreksi komisi: sisa pesanan SO-BTP5-1 ditutup");
  const s = ringkasRincian(DIBAWA);
  expect([s.jenis, s.tarif, s.pengaliHarga, s.keterangan]).toEqual(
    ["saldo", "—", "—", "Sisa potongan komisi dibawa ke bulan berikutnya"]);
  expect(ringkasRincian(BARIS_A).jenis).toBe("biasa");

  rute({ "/incentive/me": KARTU([BARIS_A, KOREKSI, DIBAWA]) });
  const host = await mount(<MyIncentiveCard period="2026-11" />);
  expect(txt(q(host, "my-incentive-auto-rincian-1-ket"))).toBe("Koreksi komisi: sisa pesanan SO-BTP5-1 ditutup");
  expect(txt(q(host, "my-incentive-auto-rincian-1"))).toContain("-60 yard");
  const saldo = txt(q(host, "my-incentive-auto-rincian-2"));
  expect(saldo).toContain("Sisa potongan komisi dibawa ke bulan berikutnya");
  expect(saldo).not.toMatch(/tarif|capaian/);
  expect(q(host, "my-incentive-auto-rincian-0-ket")).toBeNull();
});
