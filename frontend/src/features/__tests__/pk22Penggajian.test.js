// PK-22 — sisi layar tanpa peramban (uji jalan U16 di lingkungan A):
//  · Proses Gaji: tombol mengikuti izin `payroll.*` dan status (Hitung Ulang/Ajukan/Batalkan di draf, Anulir di
//    diposting); lencana Dibatalkan & Dianulir berikon; langkah tertahan izin ditulis alasannya; konfirmasi anulir menyebut
//    periode, karyawan, gaji bersih, PT, dan "Jurnal gaji akan dibalik."; anulir ber-Idempotency-Key.
//  · Setoran Kewajiban: "Semua PT" → tombol mati + "Pilih satu PT dulu"; kartu BPJS/PPh 21 (Kewajiban · Sudah disetor ·
//    Sisa); memuat · galat · kosong dibedakan; Catat Setoran → konfirmasi menyebut nominal & PT, kirim ber-kunci.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import PayrollRunsView, { nextStepHint, PayrollRunStatus } from "../hr/PayrollRunsView";
import PayrollRemittancesView, { alasanTidakBisaSetor, galatForm, TEKS_SEMUA_PT } from "../hr/PayrollRemittancesView";
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
jest.mock("../../components/EntityScopeBanner", () => () => <div data-testid="remit-scope" />);
jest.mock("../../components/KNSelect", () => () => null);
jest.mock("../../components/EntityBadge", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const ENT = [{ id: "ent_ksc", legal_name: "PT Kain Suka Cita", short_name: "KSC" },
  { id: "ent_kanda", legal_name: "CV Kanda", short_name: "Kanda" }];
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function settle() { for (let i = 0; i < 6; i += 1) await act(async () => {}); }
async function mount(el, { entity = "ent_ksc" } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(
      <EntityScopeProvider selectedEntity={entity} entities={ENT} canSwitch>
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

const TOTALS = { employees: 2, gross: 9000000, bpjs_emp: 360000, pph21: 150000, net: 8490000 };
const RUN = (status, extra = {}) => ({ id: `prun_${status}`, number: `KSC/PAY-${status}`, entity_id: "ent_ksc",
  period: "2026-10", status, totals: TOTALS, payslips: [], ...extra });

function apiRuns(run) {
  mockGet.mockImplementation((url) => {
    if (url === "/api/entities") return Promise.resolve({ data: ENT });
    if (url === "/api/hr/payroll/runs") return Promise.resolve({ data: [run] });
    if (url === `/api/hr/payroll/runs/${run.id}`) return Promise.resolve({ data: run });
    return Promise.resolve({ data: {} });
  });
}

afterEach(() => {
  mockGet.mockReset(); mockPost.mockReset(); mockConfirm.mockReset(); mockReason.mockReset();
  document.body.innerHTML = "";
});

describe("Proses Gaji", () => {
  beforeEach(() => setAccessContext({ role: "admin" }));

  test("draf: Ajukan, Hitung Ulang, Batalkan; tanpa Anulir", async () => {
    apiRuns(RUN("draft"));
    const { host } = await mount(<PayrollRunsView selectedEntity="ent_ksc" />);
    await click(q(host, "payroll-run-prun_draft"));
    expect(q(host, "payroll-submit")).not.toBeNull();
    expect(q(host, "payroll-recalc")).not.toBeNull();
    expect(q(host, "payroll-cancel")).not.toBeNull();
    expect(q(host, "payroll-void")).toBeNull();
    // Hitung ulang: konfirmasi dulu
    mockConfirm.mockResolvedValue(true);
    mockPost.mockResolvedValue({ data: RUN("draft", { recalc_count: 1, recalculated_by: "Budi" }) });
    await click(q(host, "payroll-recalc"));
    expect(mockConfirm.mock.calls[0][0].message).toContain("Slip dihitung lagi dari data karyawan, lembur, dan komisi terbaru.");
    expect(mockPost.mock.calls[0][0]).toBe("/api/hr/payroll/runs/prun_draft/recalculate");
    expect(q(host, "payroll-recalc-info").textContent).toContain("Dihitung ulang 1×");
  });

  test("diposting: Anulir menyebut periode, karyawan, gaji bersih, PT; kirim ber-kunci; lencana Dianulir", async () => {
    apiRuns(RUN("posted"));
    const { host } = await mount(<PayrollRunsView selectedEntity="ent_ksc" />);
    await click(q(host, "payroll-run-prun_posted"));
    expect(q(host, "payroll-pay")).not.toBeNull();
    expect(q(host, "payroll-cancel")).toBeNull();
    mockReason.mockResolvedValue("salah tunjangan transport");
    mockPost.mockResolvedValue({ data: RUN("void", { void_reason: "salah tunjangan transport", voided_by: "Budi",
      void_journal_number: "KSC/JE-00009" }) });
    await click(q(host, "payroll-void"));
    const pesan = mockReason.mock.calls[0][0].description;
    expect(pesan).toContain("Oktober 2026 · 2 karyawan · gaji bersih");
    expect(pesan).toContain("8.490.000");
    expect(pesan).toContain("PT Kain Suka Cita");
    expect(pesan).toContain("Jurnal gaji akan dibalik.");
    const [url, body, conf] = mockPost.mock.calls[0];
    expect(url).toBe("/api/hr/payroll/runs/prun_posted/void");
    expect(body).toEqual({ reason: "salah tunjangan transport" });
    expect(conf.headers["Idempotency-Key"]).toMatch(/^gaji-/);
    expect(q(host, "payroll-detail-status").textContent).toBe("Dianulir");
    expect(q(host, "payroll-detail-status").querySelector("svg")).not.toBeNull();
    expect(q(host, "payroll-void-reason").textContent).toContain("KSC/JE-00009");
  });

  test("izin menyiapkan saja: draf bisa diajukan, yang diajukan menulis alasan langkah berikutnya", async () => {
    setAccessContext({ role: "cr_siap", permissions: { payroll: ["create"], hr: ["view"] } });
    apiRuns(RUN("pending_approval"));
    const { host } = await mount(<PayrollRunsView selectedEntity="ent_ksc" />);
    await click(q(host, "payroll-run-prun_pending_approval"));
    expect(q(host, "payroll-approve")).toBeNull();
    expect(q(host, "payroll-cancel")).toBeNull();   // batal yang diajukan butuh payroll.approve
    expect(q(host, "payroll-next-hint").textContent).toBe("Mengesahkan penggajian butuh izin mengesahkan gaji.");
    expect(nextStepHint("draft", { create: true })).toBe("");
  });

  test("lencana Dibatalkan berikon + teks", async () => {
    const { host } = await mount(<PayrollRunStatus status="cancelled" testId="st" />);
    expect(q(host, "st").textContent).toBe("Dibatalkan");
    expect(q(host, "st").querySelector("svg")).not.toBeNull();
  });
});

const OUT = { entity_id: "ent_ksc", period: "2026-10", period_label: "Oktober 2026", runs: 1,
  items: [{ kind: "bpjs", label: "BPJS", kewajiban: 900000, disetor: 0, sisa: 900000 },
    { kind: "pph21", label: "PPh 21", kewajiban: 150000, disetor: 0, sisa: 150000 }] };
OUT.bpjs = OUT.items[0]; OUT.pph21 = OUT.items[1];

function apiSetoran({ out = OUT, list = { items: [], total: 0 }, outFail = false } = {}) {
  mockGet.mockImplementation((url) => {
    if (url === "/api/hr/payroll/remittances/outstanding") {
      return outFail ? Promise.reject({ response: { status: 500, data: { detail: "boom" } } }) : Promise.resolve({ data: out });
    }
    if (url === "/api/hr/payroll/remittances") return Promise.resolve({ data: list });
    if (url === "/api/bank-accounts") {
      return Promise.resolve({ data: [{ id: "rek_b1", name: "BCA KSC", entity_id: "ent_ksc", account_type: "bank",
        cash_type: "kas_besar", bank_name: "BCA", account_number: "111", is_active: true }] });
    }
    return Promise.resolve({ data: {} });
  });
}

describe("Setoran Kewajiban", () => {
  beforeEach(() => setAccessContext({ role: "admin" }));

  test("Semua PT: tombol mati dengan alasan tertulis, kewajiban tidak dimuat", async () => {
    apiSetoran();
    const { host } = await mount(<PayrollRemittancesView />, { entity: "all" });
    expect(q(host, "remit-create").disabled).toBe(true);
    expect(q(host, "remit-create-why").textContent).toBe(TEKS_SEMUA_PT);
    expect(q(host, "remit-all-pt")).not.toBeNull();
    expect(mockGet.mock.calls.map((c) => c[0])).not.toContain("/api/hr/payroll/remittances/outstanding");
    expect(alasanTidakBisaSetor({ canWrite: true, canPay: false })).toBe("Mencatat setoran butuh izin membayar gaji.");
  });

  test("kartu BPJS: Kewajiban · Sudah disetor · Sisa; riwayat kosong satu kali", async () => {
    apiSetoran();
    const { host } = await mount(<PayrollRemittancesView />);
    expect(q(host, "remit-card-bpjs-kewajiban").textContent).toContain("900.000");
    expect(q(host, "remit-card-bpjs-disetor").textContent).toContain("0");
    expect(q(host, "remit-card-bpjs-sisa").textContent).toContain("900.000");
    expect(q(host, "remit-card-bpjs-status").textContent).toBe("Masih ada sisa");
    expect(q(host, "remit-list-empty").textContent).toBe("Belum ada setoran untuk masa ini.");
    expect(host.querySelectorAll("[data-testid='remit-list-empty']").length).toBe(1);
    expect(q(host, "remit-create").disabled).toBe(false);
  });

  test("galat memuat kewajiban: kotak galat + Coba lagi, bukan kartu nol", async () => {
    apiSetoran({ outFail: true });
    const { host } = await mount(<PayrollRemittancesView />);
    expect(q(host, "remit-out-error")).not.toBeNull();
    expect(q(host, "remit-card-bpjs")).toBeNull();
  });

  test("Catat Setoran: konfirmasi menyebut nominal & PT, kirim ber-kunci, sisa jadi 0", async () => {
    apiSetoran();
    const { host } = await mount(<PayrollRemittancesView />);
    await click(q(host, "remit-create"));
    expect(q(host, "remit-form-amount").value).toBe("900000");
    mockConfirm.mockResolvedValue(true);
    mockPost.mockResolvedValue({ data: { id: "strm_1", number: "KSC/STR-00001", status: "done" } });
    const lunas = { ...OUT, items: [{ ...OUT.bpjs, disetor: 900000, sisa: 0 }, OUT.pph21] };
    lunas.bpjs = lunas.items[0]; lunas.pph21 = lunas.items[1];
    apiSetoran({ out: lunas, list: { items: [{ id: "strm_1", number: "KSC/STR-00001", kind: "bpjs", paid_date: "2026-11-10",
      amount: 900000, reference: "", status: "done", gl_status: "posted" }], total: 1 } });
    await click(q(host, "remit-form-submit"));
    const c = mockConfirm.mock.calls[0][0];
    expect(c.title).toContain("BPJS");
    expect(c.title).toContain("900.000");
    expect(c.message).toContain("PT Kain Suka Cita");
    const [url, body, conf] = mockPost.mock.calls[0];
    expect(url).toBe("/api/hr/payroll/remittances");
    expect(body).toMatchObject({ kind: "bpjs", period: expect.any(String), amount: 900000 });
    expect(conf.headers["Idempotency-Key"]).toMatch(/^setor-/);
    expect(q(host, "remit-card-bpjs-sisa").textContent).toContain("0");
    expect(q(host, "remit-card-bpjs-status").textContent).toBe("Sudah disetor penuh");
    expect(q(host, "remit-count").textContent).toBe("1 setoran");
  });

  test("galat isian: nominal melebihi sisa ditolak sebelum kirim", () => {
    expect(galatForm({ kind: "pph21", period: "2026-10", amount: "200000", paid_date: "2026-11-10" }, 150000))
      .toContain("melebihi sisa kewajiban");
    expect(galatForm({ kind: "bpjs", period: "2026-10", amount: "0", paid_date: "2026-11-10" }, 1)).toBe("Nominal harus lebih dari 0.");
  });
});
