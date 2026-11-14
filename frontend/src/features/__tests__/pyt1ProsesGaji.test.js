// PY-T1 — layar Proses Gaji sesudah pengalihan (uji jalan U17 di lingkungan A):
//  · tab "Proses Gaji" ada, tab "Slip Gaji" tidak ada; id lama `hr-payslips` = alias ke Proses Gaji (panel Cari slip);
//  · form buat punya "Jenis proses"; tabel slip lima kolom "Karyawan · Pendapatan · Potongan · PPh 21 · Gaji bersih";
//  · baris dibuka → komponen dikelompokkan Pendapatan · Potongan · Tanggungan perusahaan (dua bonus = dua baris);
//  · teks konfirmasi sahkan; proses yang perlu dihitung ulang: Ajukan mati + alasan tertulis.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import PayrollRunsView, { TEKS_SAHKAN, TEKS_KEMBALIKAN, TEKS_PERLU_HITUNG_ULANG } from "../hr/PayrollRunsView";
import { SlipDetail } from "../hr/PayslipsView";
import { slipGroups } from "../hr/payrollUtils";
import { HUB_TABS } from "../../config/hubTabs";
import { VIEW_ALIASES } from "../../config/viewAliases";
import { AppNavProvider } from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { setAccessContext } from "../../config/roles";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockConfirm = jest.fn();
const mockReason = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({
  askConfirm: (...a) => mockConfirm(...a), askReason: (...a) => mockReason(...a) }));
jest.mock("../../components/KNSelect", () => (p) => <span data-testid={p["data-testid"]} data-value={p.value} />);
jest.mock("../../components/EntityBadge", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const ENT = [{ id: "ent_kanda", legal_name: "CV Kanda", short_name: "Kanda" }];
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function settle() { for (let i = 0; i < 6; i += 1) await act(async () => {}); }
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(
      <EntityScopeProvider selectedEntity="ent_kanda" entities={ENT} canSwitch>
        <AppNavProvider role="admin">{el}</AppNavProvider>
      </EntityScopeProvider>);
  });
  await settle();
  return { host, root };
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
}

const C = (code, label, kind, amount, extra = {}) => ({ code, name: label, label, kind, amount, bucket: "other_earnings", ...extra });
const SLIP = { id: "slip_e1", employee_id: "e1", employee_name: "E1 Uji", period: "2026-11", gross: 13800000, bpjs_emp_total: 0,
  other_deductions: 0, pph21: 621000, pph21_rate: 0.045, net: 13179000, run_type: "regular",
  components: [C("GAJI_POKOK", "Gaji Pokok", "pendapatan", 8000000), C("TUNJANGAN", "Tunjangan — Transport", "pendapatan", 500000),
    C("TUNJANGAN", "Tunjangan — Makan", "pendapatan", 300000), C("BONUS", "Bonus A", "pendapatan", 2000000),
    C("BONUS", "Bonus B", "pendapatan", 3000000), C("PPH21", "PPh 21", "potongan", 621000, { rate: 4.5, statutory_code: "pph21" })] };
const RUN = (extra = {}) => ({ id: "prun_nov", number: "KND/PAY-00002", entity_id: "ent_kanda", period: "2026-11", status: "draft",
  run_type: "regular", seq: 1, totals: { employees: 1, gross: 13800000, bpjs_emp: 0, pph21: 621000, net: 13179000 }, payslips: [SLIP], ...extra });

function api(run) {
  mockGet.mockImplementation((url) => {
    if (url === "/api/entities") return Promise.resolve({ data: ENT });
    if (url === "/api/hr/payroll/runs") return Promise.resolve({ data: [run] });
    if (url === `/api/hr/payroll/runs/${run.id}`) return Promise.resolve({ data: run });
    if (url === "/api/hr/payslips") return Promise.resolve({ data: [SLIP] });
    return Promise.resolve({ data: {} });
  });
}

afterEach(() => {
  mockGet.mockReset(); mockPost.mockReset(); mockConfirm.mockReset(); mockReason.mockReset();
  document.body.innerHTML = "";
});

describe("menu", () => {
  test("U17 — tab Proses Gaji ada, Slip Gaji tidak ada; hr-payslips = alias ke Proses Gaji", () => {
    const labels = HUB_TABS["hr-payroll-hub"].map((t) => t.label);
    expect(labels).toContain("Proses Gaji");
    expect(labels).not.toContain("Slip Gaji");
    expect(HUB_TABS["hr-payroll-hub"].map((t) => t.view)).not.toContain("hr-payslips");
    expect(VIEW_ALIASES["hr-payslips"]).toMatchObject({ to: "hr-payroll-runs", preset: { cari: true } });
  });
});

describe("Proses Gaji", () => {
  beforeEach(() => setAccessContext({ role: "admin" }));

  test("U17 — tabel slip lima kolom; baris E1 dibuka → dua bonus tampil terpisah, dikelompokkan", async () => {
    api(RUN());
    const { host } = await mount(<PayrollRunsView selectedEntity="ent_kanda" />);
    expect(q(host, "payroll-create-type")).not.toBeNull();
    await click(q(host, "payroll-run-prun_nov"));
    const heads = [...q(host, "payroll-payslips-table").querySelectorAll("thead th")].map((th) => th.textContent);
    expect(heads).toEqual(["Karyawan", "Pendapatan", "Potongan", "PPh 21", "Gaji bersih"]);
    expect(q(host, "payslip-detail-slip_e1")).toBeNull();
    await click(q(host, "payslip-toggle-slip_e1"));
    const pend = q(host, "payslip-group-slip_e1-pendapatan").textContent;
    expect(pend).toContain("Bonus A");
    expect(pend).toContain("Bonus B");
    expect(pend).toContain("Tunjangan — Transport");
    expect(q(host, "payslip-group-slip_e1-potongan").textContent).toContain("PPh 21");
    expect(q(host, "payslip-group-slip_e1-tanggungan_perusahaan")).not.toBeNull();
    expect(q(host, "payroll-detail-empty")).toBeNull();
  });

  test("teks konfirmasi sahkan sesuai spesifikasi", async () => {
    api(RUN({ status: "pending_approval" }));
    mockConfirm.mockResolvedValue(false);
    const { host } = await mount(<PayrollRunsView selectedEntity="ent_kanda" />);
    await click(q(host, "payroll-run-prun_nov"));
    await click(q(host, "payroll-approve"));
    expect(mockConfirm.mock.calls[0][0].message).toContain(TEKS_SAHKAN);
    expect(TEKS_KEMBALIKAN).toBe("Penggajian kembali menjadi draf dan bisa dihitung ulang. Alasannya tersimpan di dokumen.");
    mockReason.mockResolvedValue(null);
    await click(q(host, "payroll-reject"));
    expect(mockReason.mock.calls[0][0].description).toBe(TEKS_KEMBALIKAN);
  });

  test("masukan dibatalkan sesudah dihitung: Ajukan mati, alasan tertulis", async () => {
    api(RUN({ inputs_stale_at: "2026-12-15T03:00:00Z" }));
    const { host } = await mount(<PayrollRunsView selectedEntity="ent_kanda" />);
    await click(q(host, "payroll-run-prun_nov"));
    expect(q(host, "payroll-submit").disabled).toBe(true);
    expect(q(host, "payroll-stale-hint").textContent).toBe(TEKS_PERLU_HITUNG_ULANG);
  });

  test("Cari slip: panel menggantikan tab Slip Gaji; rute cadangan membukanya", async () => {
    api(RUN());
    const { host } = await mount(<PayrollRunsView selectedEntity="ent_kanda" cariAwal />);
    expect(q(host, "payroll-slip-search")).not.toBeNull();
    expect(q(host, "payslips-view")).not.toBeNull();
    expect(q(host, "payslips-search")).not.toBeNull();
  });
});

describe("rincian slip", () => {
  test("SlipDetail menampilkan daftar komponen, bukan empat baris tetap", async () => {
    const { host } = await mount(<SlipDetail slip={SLIP} busy={false} onPdf={() => {}} />);
    const pend = q(host, "payslip-detail-group-pendapatan").textContent;
    expect(pend).toContain("Bonus A");
    expect(pend).toContain("Bonus B");
    expect(pend).not.toContain("Lembur");
    expect(q(host, "payslip-detail-net").textContent).toContain("13.179.000");
  });
  test("slip lama tanpa komponen disusun dari kolomnya", () => {
    const g = slipGroups({ base_salary: 5000000, allowances: 0, overtime: 0, commission: 0, pph21: 0, bpjs_emp: {}, bpjs_er_total: 0 });
    expect(g.map((x) => x.key)).toEqual(["pendapatan", "potongan", "tanggungan_perusahaan"]);
    expect(g[0].rows.map((r) => r.label)).toEqual(["Gaji Pokok"]);
    expect(g[1].rows.map((r) => r.label)).toEqual(["PPh 21"]);
  });
});
