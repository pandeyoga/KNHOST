// KM-T4 — Lembar Insentif ke gaji & buku besar; tagihan insentif antar-PT; tarif komisi tanpa Satuan (sisi layar tanpa
// peramban; U17 pengganti uji jalan):
//  · rincian lembar: konfirmasi Sahkan di PT bermode Lembar Insentif menyebut beban, tanggal jurnal, banyak baris, dan
//    bulan gaji; lembar dibayar → lencana "Dibayarkan", "Dibayar lewat {nomor proses}", bilah Jurnal + "Lihat jurnal";
//    PT belum dialihkan → pita "PT ini masih memakai komisi otomatis…";
//  · Target & Aturan: kartu Kesiapan beralih (butir ikon + teks + warna, tautan Pusat Pengaturan, tanpa tombol alih);
//  · Antar-PT: daftar tagihan (status ikon + teks, kolom aksi menempel) dan konfirmasi pelunasan menyebut nominal & dua PT;
//  · tarif komisi: kolom/isian "Satuan" tidak ada lagi.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import IncentiveSheetDetail, { teksPitaGaji, teksSahkanGaji } from "../incentive/IncentiveSheetDetail";
import IncentiveSetupView, { ButirKesiapan } from "../incentive/IncentiveSetupView";
import IntercoChargesPanel, { alasanLunas, teksKonfirmasiLunas } from "../finance/interco/IntercoChargesPanel";
import { AppNavProvider } from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { setAccessContext } from "../../config/roles";

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
jest.mock("../../components/EntityScopeBanner", () => () => <div data-testid="scope" />);
jest.mock("../../components/KNSelect", () => () => null);
jest.mock("../../components/KNDatePicker", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const ENT = [{ id: "ent_kanda", legal_name: "CV Kanda Suka", short_name: "Kanda" }];
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const txt = (el) => (el?.textContent || "").replace(/\u00a0/g, " ");
async function settle() { for (let i = 0; i < 8; i += 1) await act(async () => {}); }
const klik = async (el) => { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await settle(); };
const dibuka = [];
async function mount(node, { entity = "ent_kanda" } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(
      <EntityScopeProvider selectedEntity={entity} entities={ENT} canSwitch>
        <AppNavProvider role="manager" onOpenDocument={(l) => dibuka.push(l)} onNavigateTo={() => {}}>{node}</AppNavProvider>
      </EntityScopeProvider>);
  });
  await settle();
  return host;
}
const izin = (perms) => setAccessContext({ role: "manager", permissions: perms, view_resources: {}, hidden_views: [],
  view_actions: {} });

const BARIS = (over = {}) => ({ id: "l_andi", sales_id: "u_andi", sales_name: "Andi", component_id: "c_bln",
  component_name: "Insentif Bulanan", basis_period_type: "month", basis_period: "2026-10", basis_label: "Okt 2026",
  amount: 2000000, note: "", snapshot: {}, ...over });
const LEMBAR = (over) => ({
  id: "isheet_1", number: "KANDA/LIN-00001", entity_id: "ent_kanda", pay_period: "2026-11", title: "", status: "submitted",
  prepared_by: { id: "u_sa", name: "Sari" }, submitted_by: { id: "u_sa", name: "Sari" }, history: [],
  lines: [BARIS(), BARIS({ id: "l_andi_tw", component_name: "Insentif Triwulan", basis_period_type: "quarter",
    basis_period: "2026-Q3", basis_label: "Triwulan III 2026", amount: 3000000 }),
  BARIS({ id: "l_budi", sales_id: "u_budi", sales_name: "Budi", amount: 3500000 })],
  totals: { lines: 3, amount: 8500000 }, drift: [],
  payroll: { mode: "sheet", mode_label: "Dari Lembar Insentif yang disahkan", sheet_mode: true, linked: false,
    journal_date: "2026-10-31", lines_to_payroll: 3, pay_period: "2026-11" },
  ...over,
});

beforeEach(() => { mockGet.mockReset(); mockPost.mockReset(); mockConfirm.mockReset(); dibuka.length = 0; });

test("teks bantu: kalimat gaji di konfirmasi Sahkan, pita PT belum dialihkan, konfirmasi pelunasan, alasan tombol", () => {
  const s = LEMBAR();
  expect(teksSahkanGaji(s.payroll, 8500000, s.lines).replace(/\u00a0/g, " ")).toBe(
    "Beban insentif Rp 8.500.000 dibukukan per 31 Okt 2026 dan 3 baris masuk gaji November 2026.");
  expect(teksSahkanGaji({ ...s.payroll, sheet_mode: false, mode: "accrue_then_settle" }, 1, s.lines)).toBe("");
  expect(teksPitaGaji(LEMBAR({ payroll: { mode: "accrue_then_settle", sheet_mode: false } }))).toBe(
    "PT ini masih memakai komisi otomatis. Lembar ini tercatat sebagai keputusan dan tidak masuk gaji.");
  expect(teksPitaGaji(LEMBAR({ payroll: { mode: "off", sheet_mode: false } }))).toMatch(/^PT ini tidak membayar insentif lewat gaji/);
  expect(teksPitaGaji(LEMBAR({ payroll_linked: true }))).toBe("");
  expect(teksPitaGaji(LEMBAR({ status: "approved", payroll_linked: false }))).toMatch(/disahkan sebelum PT beralih/);
  const c = { number: "KSC/ICC-00001", to_entity_name: "Kanda", from_entity_name: "KSC", status: "open", to_entity_id: "ent_kanda" };
  expect(teksKonfirmasiLunas(c, 2000000).replace(/\u00a0/g, " ")).toBe("Catat pelunasan Rp 2.000.000 untuk tagihan "
    + "KSC/ICC-00001: kas keluar dari Kanda dan masuk ke KSC. Jurnal terbit di buku kedua PT.");
  expect(alasanLunas(c, { canSettle: false })).toBe("Butuh akses Catat pelunasan antar-PT.");
  expect(alasanLunas(c, { canSettle: true, allowed: ["ent_ksc"] })).toBe("Dicatat oleh Kanda.");
  expect(alasanLunas(c, { canSettle: true, allowed: ["ent_kanda"] })).toBe("");
  expect(alasanLunas({ ...c, status: "settled" }, { canSettle: false })).toBe("");
});

test("U17 pengganti: Sahkan di PT bermode Lembar Insentif — konfirmasi menyebut beban, tanggal jurnal, baris, bulan gaji", async () => {
  izin({ incentive: ["view", "approve"] });
  mockGet.mockResolvedValue({ data: LEMBAR() });
  mockConfirm.mockResolvedValue(true);
  mockPost.mockResolvedValue({ data: LEMBAR({ status: "approved", payroll_linked: true, gl_status: "posted",
    journal_entry_id: "je_1", journal_date: "2026-10-31" }) });
  const host = await mount(<IncentiveSheetDetail sheetId="isheet_1" onClose={() => {}} />);
  expect(q(host, "isheet-payroll-note")).toBeNull();   // PT sudah dialihkan → tidak ada pita
  await klik(q(host, "isheet-approve"));
  const msg = String(mockConfirm.mock.calls[0][0].message).replace(/\u00a0/g, " ");
  expect(msg).toContain("3 baris · total Rp 8.500.000 · CV Kanda Suka");
  expect(msg).toContain("Beban insentif Rp 8.500.000 dibukukan per 31 Okt 2026 dan 3 baris masuk gaji November 2026.");
  expect(txt(q(host, "isheet-status"))).toBe("Disahkan");
  expect(txt(q(host, "isheet-journal"))).toBe("Jurnal terbit");
});

test("U17 pengganti: lembar dibayar — lencana Dibayarkan, 'Dibayar lewat {nomor}', Lihat jurnal membuka Buku Besar", async () => {
  izin({ incentive: ["view"], accounting: ["view"] });
  const bayar = { paid_run_id: "prun_1", paid_run_number: "KANDA/PAY-00007" };
  mockGet.mockResolvedValue({ data: LEMBAR({ status: "paid", payroll_linked: true, gl_status: "posted",
    journal_entry_id: "je_1", journal_date: "2026-10-31", lines: LEMBAR().lines.map((x) => ({ ...x, ...bayar })) }) });
  const host = await mount(<IncentiveSheetDetail sheetId="isheet_1" onClose={() => {}} />);
  expect(txt(q(host, "isheet-status"))).toBe("Dibayarkan");
  expect(q(host, "isheet-status").className).toContain("status-shipped");
  expect(txt(q(host, "isheet-paid-l_andi"))).toBe("Dibayar lewat KANDA/PAY-00007");
  expect(txt(q(host, "isheet-journal-row"))).toContain("per 31 Okt 2026");
  await klik(q(host, "isheet-journal-link"));
  expect(dibuka).toEqual([{ view: "general-ledger", focus_type: "journal_entry", focus_id: "je_1" }]);
});

test("PT belum dialihkan: pita keterangan, tanpa bilah jurnal", async () => {
  izin({ incentive: ["view"] });
  mockGet.mockResolvedValue({ data: LEMBAR({ status: "approved", payroll_linked: false, gl_status: "not_required",
    payroll: { mode: "accrue_then_settle", sheet_mode: false, linked: false, journal_date: "", lines_to_payroll: 3, pay_period: "2026-11" } }) });
  const host = await mount(<IncentiveSheetDetail sheetId="isheet_1" onClose={() => {}} />);
  expect(txt(q(host, "isheet-payroll-note"))).toBe(
    "PT ini masih memakai komisi otomatis. Lembar ini tercatat sebagai keputusan dan tidak masuk gaji.");
  expect(q(host, "isheet-journal-row")).toBeNull();
});

test("Target & Aturan: kartu Kesiapan — mode berlaku, butir ikon + teks, tautan Pusat Pengaturan, tanpa tombol alih", async () => {
  izin({ incentive: ["view", "configure"] });
  mockGet.mockImplementation((url) => {
    if (url === "/api/incentive/switch-readiness") {
      return Promise.resolve({ data: { mode: "accrue_then_settle", mode_label: "Komisi otomatis: dicadangkan, dilunasi lewat gaji",
        checks: [{ code: "pencocokan", ok: true, text: "Pencocokan angka September 2026 dan Oktober 2026 cocok dengan buku besar." },
          { code: "saldo_hutang", ok: false, text: "Saldo hutang insentif PT ini masih Rp 1.500.000." }] } });
    }
    return Promise.resolve({ data: {} });
  });
  const host = await mount(<IncentiveSetupView />);
  expect(txt(q(host, "ins-ready-mode"))).toBe("Cara insentif sales masuk penggajian di PT ini: Komisi otomatis: dicadangkan, dilunasi lewat gaji");
  expect(q(host, "ins-ready-pencocokan").getAttribute("data-ok")).toBe("1");
  expect(txt(q(host, "ins-ready-saldo_hutang"))).toBe("BelumSaldo hutang insentif PT ini masih Rp 1.500.000.");
  expect(q(host, "ins-ready-saldo_hutang").querySelector(".status-pill.status-pending svg")).not.toBeNull();
  expect(txt(q(host, "ins-ready-summary"))).toBe("Selesaikan butir yang belum siap sebelum PT ini dialihkan.");
  expect(q(host, "ins-ready-open-config")).not.toBeNull();
  expect(host.querySelector("[data-testid^='ins-ready'] button.primary-button")).toBeNull();   // tidak ada tombol alih
  expect(txt(await mount(<ul><ButirKesiapan c={{ code: "x", ok: true, text: "Beres." }} /></ul>))).toBe("SiapBeres.");
});

test("Antar-PT: tagihan insentif — status ikon + teks, kolom aksi menempel, konfirmasi pelunasan + kunci idempotensi", async () => {
  izin({ interco: ["view", "settle"] });
  const C = { id: "icc_1", number: "KSC/ICC-00001", from_entity_id: "ent_ksc", from_entity_name: "KSC",
    to_entity_id: "ent_kanda", to_entity_name: "Kanda", amount: 2000000, outstanding: 2000000, status: "open",
    source: { run_number: "KSC/PAY-00003" } };
  mockGet.mockImplementation((url) => {
    if (url === "/api/interco/charges") {
      return Promise.resolve({ data: { items: [C, { ...C, id: "icc_0", number: "KSC/ICC-00000", status: "cancelled", outstanding: 0 }],
        total: 2, outstanding_total: 2000000 } });
    }
    if (url === "/api/bank-accounts") return Promise.resolve({ data: [] });
    return Promise.resolve({ data: {} });
  });
  mockConfirm.mockResolvedValue(true);
  mockPost.mockResolvedValue({ data: { ...C, outstanding: 0, status: "settled" } });
  const host = await mount(<IntercoChargesPanel entityId="ent_kanda" allowedEntityIds={["ent_kanda"]} />);
  expect(txt(q(host, "icc-count"))).toContain("2 dari 2 tagihan");
  expect(txt(q(host, "charge-status-icc_1"))).toBe("Belum lunas");
  expect(q(host, "charge-status-icc_1").querySelector("svg")).not.toBeNull();
  expect(q(host, "charge-status-icc_0").className).toContain("status-cancelled");
  expect(host.querySelector("th.col-sticky-end")).not.toBeNull();
  expect(q(host, "charge-settle-icc_0")).toBeNull();
  await klik(q(host, "charge-settle-icc_1"));
  expect(q(document.body, "icc-settle-from-auto")).not.toBeNull();   // rekening dipilih otomatis bila daftar kosong
  const form = q(document.body, "icc-settle-form");
  const tombol = Array.from(form.querySelectorAll("button")).find((b) => txt(b).includes("Catat pelunasan"));
  await klik(tombol);
  expect(String(mockConfirm.mock.calls[0][0].message).replace(/\u00a0/g, " ")).toContain("Rp 2.000.000 untuk tagihan KSC/ICC-00001: kas keluar dari Kanda dan masuk ke KSC");
  expect(mockPost.mock.calls[0][0]).toBe("/api/interco/charges/icc_1/settle");
  expect(mockPost.mock.calls[0][1].amount).toBe(2000000);
  expect(mockPost.mock.calls[0][2].headers["Idempotency-Key"]).toMatch(/^icc-lunas-/);
});
