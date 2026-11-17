// MN-T2 — penyatuan layar keuangan (docs/blueprint/unit/MN-T2.md), uji komponen:
//   U1–U2  Titipan & Saldo Kredit satu tabel per pelanggan; mode Semua PT → aksi saldo mati dengan petunjuk.
//   U9     Tutup Buku: "Buka" pada butir akun sementara membuka seksinya di layar yang sama (tanpa navigasi).
//   U10    Preset lama Jurnal {tab: suspense|recon} → Tutup Buku dengan seksinya.
//   U12    Layar Jurnal tinggal 3 tab; hub Penggajian tanpa `hr-payslips`.   U13  `hr-payslips` → Proses Gaji.
//   U14    Perlu Tindakan: kelompok mengikuti izin sumbernya (Finance tanpa izin hutang).
//   + padanan uji jalan U16 (Kas Kecil satu daftar bertahap) dan U17 (alias lama → chip/seksi yang benar).
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    patch: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (   // pola UI 16 Nov — opsi ikut dirender supaya nilai saringan dropdown terbaca
    <select data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}}>
      {!(p.options || []).some((o) => o.value === "") && <option value="" />}
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../finance/InventoryReconTab", () => () => <div data-testid="layar-rekon-persediaan" />);
jest.mock("../finance/SuspensePanel", () => () => <div data-testid="layar-akun-sementara" />);
jest.mock("../sales_admin/SoTrackerCard", () => () => null);
jest.mock("../finance/payments/ReceivePaymentModal", () => () => null);   // MN-T3 — dulu crm/ARReceiptModal
jest.mock("../pettycash/CashAdvanceDetail", () => (p) => <div data-testid="layar-rincian-pd">{p.ca?.number}</div>);
jest.mock("../pettycash/SettlementDetail", () => (p) => <div data-testid="layar-rincian-lpj">{p.stl?.number}</div>);
jest.mock("../pettycash/CashAdvanceForm", () => () => <div data-testid="layar-form-pd" />);
jest.mock("../pettycash/SettlementForm", () => (p) => <div data-testid="layar-form-lpj">{p.preselectPd?.number}</div>);
jest.mock("../../components/AskKnButton", () => ({ __esModule: true, AskKnButton: () => null, default: () => null }));

import CustomerCreditView, { PETUNJUK_SATU_PT, gabungPelanggan } from "../finance/CustomerCreditView";
import ClosingView from "../finance/ClosingView";
import GeneralLedger from "../finance/GeneralLedger";
import FinanceDesk, { TEKS_KOSONG } from "../finance/FinanceDesk";
import PettyCashView from "../pettycash/PettyCashView";
import { AppNavProvider } from "../../context/AppNavContext";
import { ViewPresetProvider } from "../../context/ViewPresetContext";
import { HUB_TABS, hubTabsForRole, resolveDeepLinkTarget } from "../../config/navigationConfig";
import { setAccessContext } from "../../config/roles";
import builtin from "../../config/__tests__/fixtures/access_builtin_fixture.json";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  for (let i = 0; i < 6; i += 1) await act(async () => {});
  roots.push(root);
  return host;
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  for (let i = 0; i < 4; i += 1) await act(async () => {});
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = []; document.body.innerHTML = ""; setAccessContext(null); mockGet.mockReset();
});
/** `map`: potongan URL → data. Kunci terpanjang menang. */
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.includes(k));
    return Promise.resolve({ data: hit ? map[hit] : [] });
  });
}
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const user = (role) => ({ role, permissions: builtin.permissions[role] || {} });
const ADMIN = { role: "admin", permissions: { accounting: ["*"], ar_receipt: ["*"], penalty: ["*"], cash_advance: ["*"],
  cash_settlement: ["*"] } };

// ── U1–U2 — Titipan & Saldo Kredit ─────────────────────────────────────────────────────────────────────────────────
// Pelanggan C: uang muka pesanan belum dikirim 2.000.000, deposit 500.000 (laporan uang muka), saldo kredit 300.000 di
// ent_ksc (buku saldo kredit) → jumlah 2.000.000 + 500.000 + 300.000 = 2.800.000.
const ADV = { totals: {}, rows: [{ customer_id: "cust_c", customer_name: "Pelanggan C", advance_orders: 2000000,
  deposit_balance: 500000, total: 2500000, oldest_days: 12, orders: [{ order_id: "so_c1", order_number: "SO-C1",
    status: "confirmed", advance_unrecognized: 2000000, grand_total: 5000000, revenue_recognized_pct: 0, age_days: 12,
    oldest_receipt_date: "2026-11-03", receipts: [{ receipt_number: "KW-C1" }] }] }] };
const SC = [{ customer_id: "cust_c", customer_name: "Pelanggan C", entity_id: "ent_ksc", balance: 300000, entries: 2,
  last_at: "2026-11-10T03:00:00Z" }];
const LEDGER = [{ id: "sce_1", type: "adjust", amount: 300000, balance_after: 300000, ref_number: "", note: "uji",
  created_at: "2026-11-10T03:00:00Z" }];
const CC_ROUTES = { "/ar/advance-report": ADV, "/store-credit/ledger": LEDGER, "/store-credit": SC };

describe("U1–U2 — Titipan & Saldo Kredit (customer-credit)", () => {
  test("U1 — satu baris C: 2.000.000 · 500.000 · 300.000 · jumlah 2.800.000; kepala kolom berlabel sumber", async () => {
    routeGet(CC_ROUTES);
    const host = await mount(<CustomerCreditView currentUser={ADMIN} selectedEntity="ent_ksc" />);
    expect(host.querySelectorAll('[data-testid^="cc-row-"]')).toHaveLength(1);
    expect(q(host, "cc-advance-cust_c").textContent).toContain("2.000.000");
    expect(q(host, "cc-deposit-cust_c").textContent).toContain("500.000");
    expect(q(host, "cc-credit-cust_c").textContent).toContain("300.000");
    expect(q(host, "cc-total-cust_c").textContent).toContain("2.800.000");
    expect(q(host, "cc-head-deposit").textContent).toBe("Satu angka per pelanggan, tanpa PT");
    expect(q(host, "cc-head-saldo").textContent).toBe("Per PT, ada riwayat");
    // baris bisa dibuka: pesanan penyumbang uang muka + riwayat saldo kredit
    await click(q(host, "cc-toggle-cust_c"));
    expect(q(host, "cc-order-so_c1")).not.toBeNull();
    expect(q(host, "cc-ledger-row-sce_1")).not.toBeNull();
    expect(q(host, "cc-redeem-cust_c").disabled).toBe(false);
    expect(q(host, "cc-reverse-sce_1").disabled).toBe(false);
    expect(q(host, "cc-one-pt-hint")).toBeNull();
  });
  test("U2 — Semua PT: Pakai saldo, Sesuaikan, Balik mati dengan petunjuk tertulis", async () => {
    routeGet(CC_ROUTES);
    const host = await mount(<CustomerCreditView currentUser={ADMIN} selectedEntity="all" />);
    await click(q(host, "cc-toggle-cust_c"));
    for (const id of ["cc-redeem-cust_c", "cc-adjust-cust_c", "cc-reverse-sce_1"]) {
      expect(q(host, id).disabled).toBe(true);
      expect(q(host, id).title).toBe(PETUNJUK_SATU_PT);
    }
    expect(q(host, "cc-one-pt-hint").textContent).toBe("Pilih satu PT untuk mengubah saldo.");
  });
  test("saringan chip, kosong satu pesan, kolom tanpa izin tidak ditampilkan (bukan 0)", async () => {
    expect(gabungPelanggan(ADV.rows, SC)[0].jumlah).toBe(2800000);
    routeGet({ ...CC_ROUTES, "/ar/advance-report": { rows: [] }, "/store-credit": [] });
    const kosong = await mount(<CustomerCreditView currentUser={ADMIN} selectedEntity="ent_ksc" />);
    expect(q(kosong, "cc-empty").textContent).toBe("Tidak ada titipan maupun saldo kredit.");
    expect(kosong.querySelectorAll('[data-testid="cc-empty"]')).toHaveLength(1);
    routeGet(CC_ROUTES);
    mockGet.mockClear();
    const sales = await mount(<CustomerCreditView currentUser={{ role: "sales", permissions: { ar_receipt: ["view"] } }}
      selectedEntity="ent_ksc" />);
    expect(q(sales, "cc-advance-cust_c")).toBeNull();
    expect(q(sales, "cc-credit-cust_c").textContent).toContain("300.000");
    expect(q(sales, "cc-partial-note")).not.toBeNull();
    expect(mockGet.mock.calls.some(([u]) => u.includes("/ar/advance-report"))).toBe(false);
  });
  test("U17 padanan — preset alias `store-credit` {bagian: saldo} → saringan Punya saldo kredit", async () => {
    routeGet(CC_ROUTES);
    const host = await mount(
      <ViewPresetProvider preset={{ view: "customer-credit", bagian: "saldo", nonce: 3 }}>
        <CustomerCreditView currentUser={ADMIN} selectedEntity="ent_ksc" />
      </ViewPresetProvider>);
    expect(q(host, "cc-filter").value).toBe("saldo_kredit");   // pola UI 16 Nov — saringan = dropdown
  });
});

// ── U9 — Tutup Buku: "Buka" butir akun sementara membuka seksinya di layar yang sama ─────────────────────────────────
const CEKLIS = { period_type: "month", period_key: "2026-10", period_label: "Oktober 2026", start_date: "2026-10-01",
  end_date: "2026-10-31", entity_id: "ent_ksc", can_close: false, items: [
    { key: "suspense_nol", label: "Saldo akun penampung nol", status: "blocking", value: 10000000, detail: "uji",
      link: { view: "closing", preset: { seksi: "akun-sementara" } } },
    { key: "stok_cocok", label: "Nilai stok sama dengan akun persediaan", status: "ok", value: 0, detail: "",
      link: { view: "closing", preset: { seksi: "persediaan" } } },
    { key: "posting_gagal", label: "Tidak ada jurnal yang gagal diposting", status: "warning", value: 1, detail: "",
      link: { view: "posting-failures", preset: null } },
  ] };
const PREVIEW = { can_close: true, period_ended: true, suspense_warning: true, suspense_balance: 10000000,
  revenue_total: 0, expense_total: 0, net_income: 0, residual_net_income: 0, closing_lines: [] };

test("U9 — klik Buka pada butir akun sementara: seksi Akun sementara terbuka, tanpa navigasi keluar hub", async () => {
  routeGet({ "/finance/closing/checklist": CEKLIS, "/finance/closing/preview": PREVIEW, "/finance/closing": [],
    "/gl/accounts": [] });
  const nav = jest.fn();
  const host = await mount(
    <AppNavProvider role="admin" onNavigateTo={nav}>
      <ClosingView selectedEntity="ent_ksc" entities={[{ id: "ent_ksc", short_name: "KSC" }]} currentUser={ADMIN} />
    </AppNavProvider>);
  expect(q(host, "closing-section-akun-sementara").getAttribute("data-open")).toBe("0");
  await click(q(host, "closing-preview-btn"));
  await click(q(host, "closing-check-suspense_nol-open"));
  expect(nav).not.toHaveBeenCalled();
  expect(q(host, "closing-section-akun-sementara").getAttribute("data-open")).toBe("1");
  expect(q(host, "layar-akun-sementara")).not.toBeNull();
  expect(q(host, "layar-rekon-persediaan")).toBeNull();
  // butir posting gagal = tab lain di hub yang sama (navigasi ke view `posting-failures`)
  await click(q(host, "closing-check-posting_gagal-open"));
  expect(nav).toHaveBeenCalledWith("posting-failures", expect.objectContaining({ preset: { from: { view: "closing" } } }));
  expect(resolveDeepLinkTarget("posting-failures", "admin").navId).toBe("closing");
});

// ── U10 — preset lama Jurnal → Tutup Buku dengan seksinya ─────────────────────────────────────────────────────────
describe("U10 — general-ledger {tab: suspense|recon} → Tutup Buku", () => {
  test.each([["suspense", "akun-sementara", "Akun sementara"], ["recon", "persediaan", "Persediaan vs buku besar"]])(
    "tab %s → seksi %s", async (tab, seksi, judul) => {
      routeGet({ "/gl/summary": { journal_count: 0, scope_meta: null }, "/gl/accounts": [], "/gl/journal": { items: [], total: 0 },
        "/finance/closing": [] });
      const nav = jest.fn();
      await mount(
        <AppNavProvider role="admin" onNavigateTo={nav}>
          <ViewPresetProvider preset={{ view: "general-ledger", tab, nonce: 10 }}>
            <GeneralLedger selectedEntity="ent_ksc" entities={[]} />
          </ViewPresetProvider>
        </AppNavProvider>);
      expect(nav).toHaveBeenCalledWith("closing", expect.objectContaining({ preset: { seksi } }));
      // mendarat: layar Tutup Buku dengan preset itu membuka seksinya
      const host = await mount(
        <AppNavProvider role="admin" onNavigateTo={jest.fn()}>
          <ViewPresetProvider preset={{ view: "closing", seksi, nonce: 11 }}>
            <ClosingView selectedEntity="ent_ksc" entities={[{ id: "ent_ksc", short_name: "KSC" }]} currentUser={ADMIN} />
          </ViewPresetProvider>
        </AppNavProvider>);
      expect(q(host, `closing-section-${seksi}`).getAttribute("data-open")).toBe("1");
      expect(q(host, `closing-section-${seksi}`).textContent).toContain(judul);
    });
});

// ── U12 / U13 — tab Jurnal & hub Penggajian ───────────────────────────────────────────────────────────────────────
test("U12 — layar Jurnal 3 tab (+ tautan ke Tutup Buku); hub Penggajian tanpa hr-payslips", async () => {
  routeGet({ "/gl/summary": { journal_count: 0 }, "/gl/accounts": [], "/gl/journal": { items: [], total: 0 } });
  const host = await mount(
    <AppNavProvider role="admin" onNavigateTo={jest.fn()}><GeneralLedger selectedEntity="ent_ksc" entities={[]} /></AppNavProvider>);
  const tabs = [...host.querySelectorAll('[data-testid^="gl-tab-"]')].map((b) => b.textContent.trim());
  expect(tabs).toEqual(["Jurnal", "Neraca Saldo", "Buku Besar"]);
  expect(q(host, "gl-moved-link").textContent).toContain("Rekonsiliasi persediaan dan akun sementara kini di Tutup Buku");
  expect(HUB_TABS["hr-payroll-hub"].filter((t) => !t.hidden).map((t) => t.view)).not.toContain("hr-payslips");
  expect(hubTabsForRole("hr-payroll-hub", "admin").map((t) => t.view)).not.toContain("hr-payslips");
});
test("U13 — resolveDeepLinkTarget('hr-payslips', 'admin') → Proses Gaji", () => {
  expect(resolveDeepLinkTarget("hr-payslips", "admin").view).toBe("hr-payroll-runs");
});

// ── U14 — Perlu Tindakan mengikuti izin sumber ──────────────────────────────────────────────────────────────────────
const DESK = { queues: [
  { id: "uang_masuk", label: "Uang masuk", count: 1, oldest_age_days: 3, total_value: 1500000, rows: [
    { ref_type: "customer", ref_id: "cust_a", number: "SO-1", title: "Pelanggan A", value: 1500000, age_days: 3,
      action: "Catat kwitansi", action_kind: "receipt", order_id: "so_1", row_key: "so_1" }] },
  { id: "hutang_jatuh_tempo", label: "Hutang", count: 1, oldest_age_days: 2, total_value: 900000, rows: [
    { ref_type: "purchase_order", ref_id: "po_1", number: "PO-1", title: "Pemasok B", value: 900000, age_days: 2,
      action: "Bayar", action_kind: "open" }] },
  { id: "denda_draft", label: "Denda", count: 0, rows: [] },
], totals: {} };
const BOARDS = { waiting_boards: [{ key: "contra_bon_approve", label: "Kontrabon", view: "contra-bons", count: 1,
  rows: [{ id: "cb_1", number: "KB-1", title: "Pemasok B", amount: 900000, days_waiting: 4 }] }] };

describe("U14 — Beranda Keuangan › Perlu Tindakan", () => {
  test("Finance (izin fixture) tanpa vendor_bill.view & contra_bon.view: tanpa kelompok hutang & kontrabon", async () => {
    const perms = { ...builtin.permissions.finance };
    delete perms.vendor_bill; delete perms.contra_bon;
    routeGet({ "/finance/desk": DESK, "/home/finance": BOARDS });
    const host = await mount(<FinanceDesk currentUser={{ role: "finance", permissions: perms }} selectedEntity="ent_ksc" />);
    const judul = [...host.querySelectorAll('[data-testid^="fin-desk-queue-"]')].map((s) => s.getAttribute("data-testid"));
    expect(judul).toContain("fin-desk-queue-uang_masuk");
    expect(host.textContent).toContain("Uang masuk perlu dicatat");
    expect(host.textContent).not.toContain("Hutang jatuh tempo");
    expect(host.textContent).not.toContain("Kontrabon menunggu");
    expect(mockGet.mock.calls.some(([u]) => u.includes("/home/finance"))).toBe(false);
    expect(q(host, "fin-desk-queue-denda")).toBeNull();   // kelompok kosong tidak digambar
  });
  test("Finance berizin penuh (fixture): kelompok hutang & kontrabon tampil, satu tombol per baris", async () => {
    routeGet({ "/finance/desk": DESK, "/home/finance": BOARDS });
    const nav = jest.fn();
    const open = jest.fn();
    const host = await mount(
      <AppNavProvider role="finance" onNavigateTo={nav} onOpenDocument={open}>
        <FinanceDesk currentUser={user("finance")} selectedEntity="ent_ksc" onOpenDocument={open} />
      </AppNavProvider>);
    expect(host.textContent).toContain("Hutang jatuh tempo");
    expect(host.textContent).toContain("Kontrabon menunggu");
    await click(q(host, "fin-desk-kontrabon-action-contra_bon_approve-cb_1"));
    expect(open).toHaveBeenCalledWith(expect.objectContaining({ view: "contra-bons" }));
  });
  test("semua sumber kosong → satu pesan; galat sumber → tidak berbunyi kosong", async () => {
    routeGet({ "/finance/desk": { queues: [], totals: {} }, "/home/finance": { waiting_boards: [] } });
    const host = await mount(<FinanceDesk currentUser={user("finance")} selectedEntity="ent_ksc" />);
    expect(q(host, "fin-desk-empty").textContent).toBe(TEKS_KOSONG);
    mockGet.mockImplementation((url) => (url.includes("/finance/desk")
      ? Promise.reject(Object.assign(new Error("x"), { response: { status: 500, data: {} } }))
      : Promise.resolve({ data: { waiting_boards: [] } })));
    const gagal = await mount(<FinanceDesk currentUser={user("finance")} selectedEntity="ent_ksc" />);
    expect(q(gagal, "fin-desk-error-desk")).not.toBeNull();
    expect(q(gagal, "fin-desk-empty")).toBeNull();
  });
});

// ── Kas Kecil — padanan U16 (satu daftar bertahap) & U17 (alias lama → chip) ───────────────────────────────────────
const WL = { items: [
  { id: "ca_1", number: "PD-1", entity_id: "ent_ksc", requester: "Staf", purpose: "ATK", divisi: "Umum", amount: 1000000,
    stage: "diajukan", status: "approved", settlement: null, updated_at: "2026-11-10T03:00:00Z" },
  { id: "ca_3", number: "PD-3", entity_id: "ent_ksc", requester: "Staf", purpose: "Bensin", divisi: "", amount: 1500000,
    stage: "dipertanggungjawabkan", status: "settled", updated_at: "2026-11-11T03:00:00Z",
    settlement: { id: "stl_3", number: "STL-3", status: "posted_to_gl", spent: 1800000, refund_due: 0, reimburse_due: 300000 } },
], total: 2, page: 1, page_size: 25, stage_counts: { diajukan: 1, dicairkan: 1, dipertanggungjawabkan: 1, selesai: 1 } };

describe("Kas Kecil — satu daftar bertahap", () => {
  test("chip tahap berjumlah, baris berlabel tahap & sisa, membuka satu panel PD + LPJ", async () => {
    routeGet({ "/petty-cash/worklist": WL, "/cash-advances/ca_3": { id: "ca_3", number: "PD-3", status: "settled" },
      "/cash-advance-settlements/stl_3": { id: "stl_3", number: "STL-3" }, "/expense-categories": [] });
    const host = await mount(<PettyCashView currentUser={user("admin")} selectedEntity="ent_ksc" entities={[]} />);
    const chips = [...host.querySelectorAll('[data-testid="pc-stage"] button')].map((b) => b.textContent);
    expect(chips).toEqual(["Semua4", "Diajukan1", "Dicairkan1", "Dipertanggungjawabkan1", "Selesai1"]);
    expect(q(host, "pc-row-stage-ca_3").textContent).toBe("Dipertanggungjawabkan");
    expect(q(host, "pc-sisa-ca_3").textContent).toContain("Hutang reimburse");
    expect(q(host, "pc-sisa-ca_3").textContent).toContain("300.000");
    expect(q(host, "pc-total").textContent).toBe("2 pengajuan dana");
    // pemegang izin bayar: baris berhutang reimburse membawa tombol Bayar; membuka baris = klik barisnya
    expect(q(host, "pc-pay-ca_3")).not.toBeNull();
    expect(q(host, "pc-open-ca_1")).not.toBeNull();
    await click(q(host, "pc-row-ca_3"));
    expect(q(host, "layar-rincian-pd").textContent).toBe("PD-3");
    expect(q(host, "layar-rincian-lpj").textContent).toBe("STL-3");
    // klik chip → saringan tahap ikut kueri
    await click(q(host, "pc-stage-dicairkan"));
    expect(mockGet.mock.calls.some(([u, c]) => u.includes("/petty-cash/worklist") && c?.params?.stage === "dicairkan")).toBe(true);
  });
  test("PD dicairkan tanpa LPJ: tombol Pertanggungjawabkan membuka form LPJ dengan PD terpilih", async () => {
    routeGet({ "/petty-cash/worklist": { ...WL, items: [{ ...WL.items[0], id: "ca_2", number: "PD-2", stage: "dicairkan",
      status: "disbursed" }] }, "/cash-advances/ca_2": { id: "ca_2", number: "PD-2", status: "disbursed" },
    "/expense-categories": [] });
    const host = await mount(<PettyCashView currentUser={user("admin")} selectedEntity="ent_ksc" entities={[]} />);
    await click(q(host, "pc-open-ca_2"));
    await click(q(host, "pc-settle-btn"));
    expect(q(host, "layar-form-lpj").textContent).toBe("PD-2");
  });
  test("Semua PT: Ajukan dana mati dengan alasan tertulis; kosong satu pesan", async () => {
    routeGet({ "/petty-cash/worklist": { items: [], total: 0, page: 1, page_size: 25, stage_counts: {} } });
    const host = await mount(<PettyCashView currentUser={user("admin")} selectedEntity="all" entities={[]} />);
    expect(q(host, "pc-create-btn").disabled).toBe(true);
    expect(q(host, "pc-create-scope-note").textContent).toContain("mengajukan dana");
    expect(q(host, "pc-empty").textContent).toBe("Belum ada pengajuan dana.");
    expect(host.querySelectorAll('[data-testid="pc-empty"]')).toHaveLength(1);
  });
  test.each([["reimburse", "dipertanggungjawabkan"], ["pertanggungjawaban", "dipertanggungjawabkan"], ["pengajuan", "all"]])(
    "U17 padanan — preset alias bagian=%s → chip %s", async (bagian, chip) => {
      routeGet({ "/petty-cash/worklist": WL });
      const host = await mount(
        <ViewPresetProvider preset={{ view: "petty-cash", bagian, nonce: 20 }}>
          <PettyCashView currentUser={user("admin")} selectedEntity="ent_ksc" entities={[]} />
        </ViewPresetProvider>);
      expect(q(host, `pc-stage-${chip}`).getAttribute("aria-pressed")).toBe("true");
    });
  test("tanpa izin lihat kas kecil: pesan akses, tidak memanggil server", async () => {
    const host = await mount(<PettyCashView currentUser={{ role: "x", permissions: {} }} selectedEntity="ent_ksc" entities={[]} />);
    expect(q(host, "petty-cash-no-access")).not.toBeNull();
    expect(mockGet).not.toHaveBeenCalled();
  });
});
