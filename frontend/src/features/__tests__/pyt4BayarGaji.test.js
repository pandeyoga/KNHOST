// PY-T4 — sisi layar tanpa peramban (uji jalan U16 di lingkungan A):
//  · Setoran & Pajak › Gaji siap dibayar: kolom spesifikasi, keadaan kosong, "Semua PT" → Bayar mati + "Pilih satu PT
//    dulu." tertulis; PT tanpa rekening gaji → Bayar mati + pesan cara mengatur.
//  · Pop-up Bayar gaji: pilihan hanya rekening berperuntukan Gaji (satu → terpilih), ringkasan "Total bersih … (1 tanpa
//    rekening, dibayar tunai)", konfirmasi menyebut "Rp 12.750.000", nama rekening, nama PT; kirim ber-kunci
//    {account_id, paid_date}; sesudah bayar daftar transfer (tombol "Unduh Excel") terbuka.
//  · Daftar transfer: 6 kolom, baris tunai bertanda "Tanpa rekening — bayar tunai" (ikon + teks), kaki "Total … · 3 penerima".
//  · Setoran BPJS dan PPh 21: tombol Batalkan hanya untuk pemegang `payroll.void` (alasan wajib, kirim ber-kunci); rekap
//    setahun 12 masa per jenis; menu Finance: hub Penggajian hanya tab Setoran & Pajak.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import PayrollRemittancesView from "../hr/PayrollRemittancesView";
import { alasanTidakBisaBayar, konfirmasiBayar, ringkasBayar, TEKS_PILIH_PT, TEKS_TANPA_REKENING_GAJI } from "../hr/PayrollPayPanel";
import { kakiTransfer, TEKS_TUNAI } from "../hr/TransferListPanel";
import { AppNavProvider } from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { setAccessContext } from "../../config/roles";
import { hubTabsForRole } from "../../config/navigationConfig";
import builtin from "../../config/__tests__/fixtures/access_builtin_fixture.json";

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
jest.mock("../../components/KNSelect", () => (p) => (
  <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange?.(e.target.value)}>
    <option value="" />
    {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
  </select>));
jest.mock("../../components/KNDatePicker", () => (p) => (
  <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange?.(e.target.value)} />));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const ENT = [{ id: "ent_kanda", legal_name: "CV Kanda", short_name: "Kanda" }];
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const teks = (el) => (el?.textContent || "").replace(/ /g, " ");
async function settle() { for (let i = 0; i < 8; i += 1) await act(async () => {}); }
async function mount(el, { entity = "ent_kanda" } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(
      <EntityScopeProvider selectedEntity={entity} entities={ENT} canSwitch>
        <AppNavProvider role="finance">{el}</AppNavProvider>
      </EntityScopeProvider>);
  });
  await settle();
  return { host, root };
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
}

const RUN = { id: "prun_nov", number: "KND/PAY-00001", period: "2026-11", run_type: "regular", employees: 3,
  net_total: 12750000, posted_at: "2026-12-01T02:00:00+00:00", entity_id: "ent_kanda", journal_date: "2026-11-30" };
const R_GAJI = { id: "rek_gaji", name: "R-GAJI BCA Kanda", bank_name: "BCA", account_number: "7001",
  holder_name: "CV Kanda", cash_type: "kas_besar" };
const TRANSFER = {
  run: { id: "prun_nov", number: "KND/PAY-00001", period: "2026-11", status: "posted", entity_id: "ent_kanda" },
  pay_account: null, paid_date: "", count: 3, total: 12750000, without_account: 1,
  items: [
    { no: 1, employee_id: "e1", employee_name: "Ani", slip_number: "SLIP-1", bank_name: "BCA", account_number: "111",
      account_holder: "Ani", amount: 5000000, cash: false },
    { no: 2, employee_id: "e2", employee_name: "Bayu", slip_number: "SLIP-2", bank_name: "Mandiri", account_number: "222",
      account_holder: "Bayu", amount: 4500000, cash: false },
    { no: 3, employee_id: "e3", employee_name: "Cici", slip_number: "SLIP-3", bank_name: "", account_number: "",
      account_holder: "", amount: 3250000, cash: true },
  ],
};
const YEAR = { entity_id: "ent_kanda", year: 2026, kinds: ["bpjs", "pph21"].map((k) => ({
  kind: k, label: k === "bpjs" ? "BPJS" : "PPh 21", total: { kewajiban: 900000, disetor: 0, sisa: 900000 },
  rows: Array.from({ length: 12 }, (_, i) => ({ period: `2026-${String(i + 1).padStart(2, "0")}`,
    period_label: `Masa ${i + 1}`, kewajiban: i === 9 ? 900000 : 0, disetor: 0, sisa: i === 9 ? 900000 : 0 })) })) };
const OUT = { entity_id: "ent_kanda", period: "2026-12", runs: 0, items: [
  { kind: "bpjs", label: "BPJS", kewajiban: 0, disetor: 0, sisa: 0 },
  { kind: "pph21", label: "PPh 21", kewajiban: 0, disetor: 0, sisa: 0 }] };
OUT.bpjs = OUT.items[0]; OUT.pph21 = OUT.items[1];
const SETORAN = { id: "strm_1", number: "KND/STR-00001", kind: "bpjs", period: "2026-12", paid_date: "2026-11-10",
  amount: 900000, reference: "", status: "done", gl_status: "posted" };

function api({ queue = [RUN], accounts = [R_GAJI], list = [] } = {}) {
  mockGet.mockImplementation((url, cfg) => {
    if (url === "/api/hr/payroll/pay-queue") return Promise.resolve({ data: { items: queue, total: queue.length } });
    if (url === "/api/hr/payroll/pay-accounts") return Promise.resolve({ data: accounts });
    if (url === "/api/hr/payroll/runs/prun_nov/transfer-list") return Promise.resolve({ data: TRANSFER });
    if (url === "/api/hr/payroll/remittances/outstanding") {
      return Promise.resolve({ data: cfg?.params?.year ? YEAR : OUT });
    }
    if (url === "/api/hr/payroll/remittances") return Promise.resolve({ data: { items: list, total: list.length } });
    return Promise.resolve({ data: {} });
  });
}
const FINANCE = { role: "finance", permissions: builtin.permissions.finance };

afterEach(() => {
  mockGet.mockReset(); mockPost.mockReset(); mockConfirm.mockReset(); mockReason.mockReset();
  document.body.innerHTML = "";
  setAccessContext(null);
});

describe("Gaji siap dibayar", () => {
  beforeEach(() => setAccessContext(FINANCE));

  test("kolom antrean; Bayar membuka pop-up berekening gaji; konfirmasi menyebut nominal, rekening, PT", async () => {
    api();
    const { host } = await mount(<PayrollRemittancesView />);
    const head = [...q(host, "pay-queue-table").querySelectorAll("thead th")].map((th) => th.textContent);
    expect(head).toEqual(["Nomor", "Periode", "Jenis", "Karyawan", "Total bersih", "Aksi"]);
    expect(teks(q(host, "pay-queue-row-prun_nov"))).toContain("Rp 12.750.000");
    expect(q(host, "pay-queue-row-prun_nov").lastElementChild.className).toContain("col-sticky-end");
    await click(q(host, "pay-queue-pay-prun_nov"));
    const pilih = q(host, "pay-form-account");
    expect([...pilih.querySelectorAll("option")].map((o) => o.textContent).filter(Boolean)).toEqual(["R-GAJI BCA Kanda · BCA · 7001"]);
    expect(pilih.value).toBe("rek_gaji");   // satu-satunya rekening gaji → terpilih
    expect(teks(q(host, "pay-form-summary"))).toContain("Total bersih Rp 12.750.000 untuk 3 karyawan (1 tanpa rekening, dibayar tunai)");
    mockConfirm.mockResolvedValue(true);
    mockPost.mockResolvedValue({ data: { id: "prun_nov", number: "KND/PAY-00001", status: "paid", transfer_total: 12750000,
      pay_account_name: "R-GAJI BCA Kanda", cash_txn_number: "KND/CASH-00009" } });
    const sesudah = { ...TRANSFER, run: { ...TRANSFER.run, status: "paid" }, pay_account: R_GAJI, paid_date: "2026-12-02" };
    mockGet.mockImplementation((url) => {
      if (url === "/api/hr/payroll/pay-queue") return Promise.resolve({ data: { items: [], total: 0 } });
      if (url === "/api/hr/payroll/runs/prun_nov/transfer-list") return Promise.resolve({ data: sesudah });
      if (url === "/api/hr/payroll/pay-accounts") return Promise.resolve({ data: [R_GAJI] });
      return Promise.resolve({ data: { items: [], total: 0 } });
    });
    await click(q(host, "pay-form-submit"));
    const c = mockConfirm.mock.calls[0][0];
    expect(teks({ textContent: c.title })).toBe("Bayar gaji KND/PAY-00001 — November 2026?");
    expect(teks({ textContent: c.message })).toContain("Rp 12.750.000 dari R-GAJI BCA Kanda · CV Kanda.");
    const [url, body, conf] = mockPost.mock.calls[0];
    expect(url).toBe("/api/hr/payroll/runs/prun_nov/pay");
    expect(body).toEqual({ account_id: "rek_gaji", paid_date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/) });
    expect(conf.headers["Idempotency-Key"]).toMatch(/^bayar-gaji-/);
    // Sesudah dibayar: daftar transfer terbuka dengan tombol Unduh Excel; antrean kosong.
    expect(q(host, "transfer-download").textContent).toContain("Unduh Excel");
    expect(teks(q(host, "transfer-source"))).toContain("dari R-GAJI BCA Kanda");
    expect(q(host, "pay-queue-empty").textContent).toBe("Tidak ada penggajian yang menunggu dibayar.");
  });

  test("daftar transfer: baris tunai bertanda, kaki total & penerima", async () => {
    api();
    const { host } = await mount(<PayrollRemittancesView />);
    await click(q(host, "pay-queue-transfer-prun_nov"));
    const head = [...q(host, "transfer-table").querySelectorAll("thead th")].map((th) => th.textContent);
    expect(head).toEqual(["No.", "Nama penerima", "Bank", "Nomor rekening", "Nominal", "Slip"]);
    expect(q(host, "transfer-cash-3").textContent).toBe(TEKS_TUNAI);
    expect(q(host, "transfer-cash-3").querySelector("svg")).not.toBeNull();
    expect(teks(q(host, "transfer-foot"))).toContain("Total Rp 12.750.000 · 3 penerima");
    expect(kakiTransfer({ total: 0, count: 0 }).replace(/ /g, " ")).toBe("Total Rp 0 · 0 penerima");
  });

  test("Semua PT: Bayar mati, alasan tertulis; PT tanpa rekening gaji: pesan cara mengatur", async () => {
    api();
    const { host } = await mount(<PayrollRemittancesView />, { entity: "all" });
    expect(q(host, "pay-queue-pay-prun_nov").disabled).toBe(true);
    expect(q(host, "pay-queue-why").textContent).toBe(`Bayar: ${TEKS_PILIH_PT}`);
    document.body.innerHTML = "";
    api({ accounts: [] });
    const b = await mount(<PayrollRemittancesView />);
    expect(q(b.host, "pay-queue-pay-prun_nov").disabled).toBe(true);
    expect(q(b.host, "pay-queue-why").textContent).toBe(`Bayar: ${TEKS_TANPA_REKENING_GAJI}`);
    expect(alasanTidakBisaBayar({ canWrite: true, canPay: true, adaRekening: true })).toBe("");
  });

  test("antrean kosong satu kali; tanpa izin bayar bagian ini tidak tampil", async () => {
    api({ queue: [] });
    const { host } = await mount(<PayrollRemittancesView />);
    expect(host.querySelectorAll("[data-testid='pay-queue-empty']").length).toBe(1);
    document.body.innerHTML = "";
    setAccessContext({ role: "cr_lihat", permissions: { hr: ["view"] } });
    api();
    const b = await mount(<PayrollRemittancesView />);
    expect(q(b.host, "pay-queue")).toBeNull();
  });

  test("teks bantu", () => {
    expect(ringkasBayar({ net: 1000, count: 2, withoutAccount: 0 }).replace(/ /g, " ")).toBe("Total bersih Rp 1.000 untuk 2 karyawan");
    expect(konfirmasiBayar({ number: "A", period: "2026-11", net: 5 }, "R", "PT X").title).toBe("Bayar gaji A — November 2026?");
  });
});

describe("Setoran BPJS dan PPh 21", () => {
  test("Finance (tanpa payroll.void): tanpa tombol Batalkan; rekap setahun 12 masa per jenis", async () => {
    setAccessContext(FINANCE);
    api({ list: [SETORAN] });
    const { host } = await mount(<PayrollRemittancesView />);
    expect(q(host, "remit-void-strm_1")).toBeNull();
    expect(q(host, "remit-row-status-strm_1").textContent).toBe("Tercatat");
    expect(q(host, "remit-row-status-strm_1").querySelector("svg")).not.toBeNull();
    for (const k of ["bpjs", "pph21"]) {
      expect(q(host, `remit-year-${k}`).querySelectorAll("tbody tr").length).toBe(12);
    }
    const thead = [...q(host, "remit-year-bpjs").querySelectorAll("thead th")].map((th) => th.textContent);
    expect(thead).toEqual(["BPJS · Masa", "Kewajiban", "Sudah disetor", "Sisa"]);
    expect(teks(q(host, "remit-year-bpjs-2026-10"))).toContain("Rp 900.000");
    expect(mockGet.mock.calls.some(([u, c]) => u === "/api/hr/payroll/remittances/outstanding" && c?.params?.year)).toBe(true);
  });

  test("Admin: Batalkan minta alasan, kirim ber-kunci; status Dibatalkan berikon", async () => {
    setAccessContext({ role: "admin" });
    api({ list: [SETORAN] });
    const { host } = await mount(<PayrollRemittancesView />);
    mockReason.mockResolvedValue("nominal salah ketik");
    mockPost.mockResolvedValue({ data: { ...SETORAN, status: "void" } });
    api({ list: [{ ...SETORAN, status: "void" }] });
    await click(q(host, "remit-void-strm_1"));
    const r = mockReason.mock.calls[0][0];
    expect(r.title).toBe("Batalkan setoran KND/STR-00001?");
    expect(teks({ textContent: r.description })).toContain("Rp 900.000");
    expect(r.description).toContain("CV Kanda");
    const [url, body, conf] = mockPost.mock.calls[0];
    expect(url).toBe("/api/hr/payroll/remittances/strm_1/void");
    expect(body).toEqual({ reason: "nominal salah ketik" });
    expect(conf.headers["Idempotency-Key"]).toMatch(/^batal-setor-/);
    expect(q(host, "remit-row-status-strm_1").textContent).toBe("Dibatalkan");
    expect(q(host, "remit-void-strm_1")).toBeNull();
  });

  test("menu Finance: hub Penggajian hanya tab Setoran & Pajak", () => {
    setAccessContext({ ...FINANCE, view_resources: builtin.view_resources, hidden_views: [], view_actions: builtin.view_actions });
    expect(hubTabsForRole("hr-payroll-hub", "finance").map((t) => [t.view, t.label]))
      .toEqual([["hr-payroll-remittances", "Setoran & Pajak"]]);
  });
});
