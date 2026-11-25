// Meja gelombang 2 · Task 7 — aksi di tempat Meja Keuangan: putuskan selisih bayar, terbitkan denda, setujui bayar sample,
// catat sudah ditagih. Endpoint & pemeriksaan sama dengan layar asal; satu sumber kode (dialog/hook/fungsi bersama).
import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";
import FinanceDesk from "../finance/FinanceDesk";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockToast = jest.fn();
const mockConfirm = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } } },
  API: "/api",
  setActiveEntity: () => {}, setAuthToken: () => {},
}));
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: (...a) => mockToast(...a) }));
jest.mock("../../services/confirmService", () => ({
  __esModule: true, askConfirm: (...a) => mockConfirm(...a), askReason: jest.fn(async () => null),
  askText: jest.fn(async () => null), askChoice: jest.fn(async () => null), default: {},
}));
// Isi form keputusan selisih diuji di layar asalnya; di sini cukup bukti bahwa dialog bersama memuat & mengirim.
jest.mock("../finance/payments/PaymentVarianceDialog", () => ({ onConfirm, onCancel, error, assessment }) => (
  <div data-testid="payment-variance-dialog">
    <span data-testid="pvd-delta">{assessment?.delta}</span>
    <span data-testid="pvd-error">{error}</span>
    <button type="button" data-testid="pvd-confirm" onClick={() => onConfirm({ kind: "writeoff", reason_code: "pembulatan" })}>ok</button>
    <button type="button" data-testid="pvd-cancel" onClick={onCancel}>batal</button>
  </div>));
jest.mock("../sales_admin/SoTrackerCard", () => () => <div data-testid="so-tracker-stub" />);
jest.mock("../finance/payments/ReceivePaymentModal", () => () => null);
jest.mock("../finance/TaxIssueDialog", () => () => null);

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const teks = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");
let roots = [];
async function mount(el) {
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host); roots.push(root);
  await act(async () => { root.render(el); }); await act(async () => {}); await act(async () => {});
  return host;
}
const klik = async (id) => act(async () => { q(id).dispatchEvent(new MouseEvent("click", { bubbles: true })); });
const tunggu = async () => { for (let i = 0; i < 4; i += 1) await act(async () => { await new Promise((r) => setTimeout(r, 0)); }); };   // eslint-disable-line no-await-in-loop
function routeGet(peta) {
  mockGet.mockImplementation((u) => {
    const k = Object.keys(peta).find((x) => u.includes(x));
    return Promise.resolve({ data: k ? peta[k] : [] });
  });
}
afterEach(async () => {
  for (const r of roots) await act(async () => r.unmount());
  roots = []; document.body.innerHTML = "";
  mockGet.mockReset(); mockPost.mockReset(); mockToast.mockReset(); mockConfirm.mockReset();
  sessionStorage.clear();
});
const jumlahMuatMeja = () => mockGet.mock.calls.filter(([u]) => String(u).includes("/finance/desk")).length;

const SELISIH = { ref_type: "ar_receipt", ref_id: "rc1", number: "KW-1", title: "Toko A", value: 50, entity_id: "ent_ksc",
  action: "Putuskan", action_kind: "decide_variance", age_days: 2, badge: "perlu keputusan" };
const DENDA = { ref_type: "penalty", ref_id: "pn1", number: "DN-1", title: "Toko B", value: 50000, entity_id: "ent_ksc",
  action: "Terbitkan", action_kind: "issue_penalty", age_days: 3, badge: "draf" };
const SAMPLE = { ref_type: "sample_order", ref_id: "s1", number: "SOS-1", title: "Toko C", value: 10000, entity_id: "ent_ksc",
  action: "Setujui bayar", action_kind: "approve_payment", age_days: 1, badge: "ACC bayar",
  sample_billing: "paid", grand_total: 10000, paid_total: 4000, sample_payment_status: "awaiting_approval" };
const TAGIH = { ref_type: "sales_order", ref_id: "so1", number: "SO-1", title: "Toko D", value: 700000, entity_id: "ent_ksc",
  action: "Tagih", action_kind: "open", age_days: 9, age_kind: "overdue", badge: "lewat", customer_id: "cus1", order_id: "so1" };
const DESK = { queues: [
  { id: "selisih_bayar", label: "Selisih", count: 1, rows: [SELISIH] },
  { id: "denda_draft", label: "Denda", count: 1, rows: [DENDA] },
  { id: "sample_acc_bayar", label: "Sample", count: 1, rows: [SAMPLE] },
  { id: "jatuh_tempo", label: "Jatuh tempo", count: 1, rows: [TAGIH] },
], not_my_desk: [] };
const PERMS = { payment_variance: ["decide", "view"], penalty: ["issue"], sample_order: ["approve_payment"],
  accounting: ["view"], order: ["update"] };
const FIN = { permissions: PERMS };
const FIN_TANPA_UPDATE = { permissions: { ...PERMS, order: [] } };
const PETA = {
  "/finance/desk": DESK,
  "/payment-variances/receipt/": { assessment: { delta: -50, funds: 950, expected: 1000 }, variance: { delta: -50 } },
  "/payment-variances/meta": { reasons: [{ code: "pembulatan", label: "Pembulatan" }] },
};

test("selisih bayar: Putuskan membuka dialog bersama; kirim memanggil endpoint keputusan dengan kunci intent; kartu dimuat ulang", async () => {
  routeGet(PETA);
  mockPost.mockResolvedValue({ data: {} });
  await mount(<FinanceDesk currentUser={FIN} selectedEntity="ent_ksc" />);
  const awal = jumlahMuatMeja();
  await klik("fin-desk-selisih_bayar-action-rc1"); await tunggu();
  expect(teks(q("pvd-delta"))).toBe("-50");
  expect(mockPost).not.toHaveBeenCalled();
  await klik("pvd-confirm");
  expect(mockPost).toHaveBeenCalledWith("/api/payment-variances/receipt/rc1/decide",
    { kind: "writeoff", reason_code: "pembulatan" },
    { headers: { "Idempotency-Key": expect.stringMatching(/^pv-putus-/) } });
  expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: expect.stringContaining("KW-1") }));
  expect(q("payment-variance-dialog")).toBeNull();
  expect(jumlahMuatMeja()).toBeGreaterThan(awal);
});

test("selisih bayar: galat server tampil di dalam dialog; dialog tetap terbuka; tanpa toast", async () => {
  routeGet(PETA);
  mockPost.mockRejectedValue({ response: { status: 409, data: { detail: "Selisih sudah diputus orang lain." } } });
  await mount(<FinanceDesk currentUser={FIN} selectedEntity="ent_ksc" />);
  await klik("fin-desk-selisih_bayar-action-rc1"); await tunggu();
  await klik("pvd-confirm");
  expect(teks(q("pvd-error"))).toContain("Selisih sudah diputus orang lain.");
  expect(q("payment-variance-dialog")).not.toBeNull();
  expect(mockToast).not.toHaveBeenCalled();
});

test("selisih bayar: kwitansi ternyata sudah diputus → pesan di pop-up, bukan layar kosong", async () => {
  routeGet({ ...PETA, "/payment-variances/receipt/": { assessment: null } });
  await mount(<FinanceDesk currentUser={FIN} selectedEntity="ent_ksc" />);
  await klik("fin-desk-selisih_bayar-action-rc1"); await tunggu();
  expect(teks(q("pv-decide-load-text"))).toContain("sudah diputus");
  expect(q("payment-variance-dialog")).toBeNull();
});

test("denda: Terbitkan minta konfirmasi dulu; batal = tidak ada panggilan; setuju = POST issue dengan kunci intent", async () => {
  routeGet(PETA);
  mockPost.mockResolvedValue({ data: {} });
  await mount(<FinanceDesk currentUser={FIN} selectedEntity="ent_ksc" />);
  mockConfirm.mockResolvedValueOnce(false);
  await klik("fin-desk-denda-action-pn1"); await tunggu();
  expect(mockConfirm).toHaveBeenCalledWith(expect.objectContaining({ title: "Terbitkan denda DN-1?", confirmLabel: "Terbitkan",
    message: expect.stringContaining("Toko B") }));
  expect(mockPost).not.toHaveBeenCalled();
  mockConfirm.mockResolvedValueOnce(true);
  await klik("fin-desk-denda-action-pn1"); await tunggu();
  expect(mockPost).toHaveBeenCalledWith("/api/penalties/pn1/issue", null,
    { headers: { "Idempotency-Key": expect.stringMatching(/^pnl-terbit-/) } });
  expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: "Denda DN-1 diterbitkan." }));
});

test("denda: galat server tampil di kotak galat meja, tanpa toast sukses", async () => {
  routeGet(PETA);
  mockConfirm.mockResolvedValue(true);
  mockPost.mockRejectedValue({ response: { status: 409, data: { detail: "Denda sudah diterbitkan." } } });
  await mount(<FinanceDesk currentUser={FIN} selectedEntity="ent_ksc" />);
  await klik("fin-desk-denda-action-pn1"); await tunggu();
  expect(teks(q("fin-desk-error-aksi"))).toContain("Denda sudah diterbitkan.");
  expect(mockToast).not.toHaveBeenCalled();
});

test("bayar sample: Setujui bayar membuka dialog konfirmasi (uang kurang tampil); submit memanggil approve-payment", async () => {
  routeGet(PETA);
  mockPost.mockResolvedValue({ data: {} });
  await mount(<FinanceDesk currentUser={FIN} selectedEntity="ent_ksc" />);
  await klik("fin-desk-sample_bayar-action-s1"); await tunggu();
  expect(mockPost).not.toHaveBeenCalled();
  expect(q("sample-approve")).not.toBeNull();
  expect(teks(q("sample-approve-short"))).toContain("kurang");
  expect(teks(q("sample-approve-submit"))).toBe("Tetap setujui");
  await klik("sample-approve-submit"); await tunggu();
  expect(mockPost).toHaveBeenCalledWith("/api/sample-orders/s1/approve-payment", { note: "" });
  expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: expect.stringContaining("SOS-1") }));
  expect(q("sample-approve")).toBeNull();
});

test("piutang lewat tempo: 'Catat sudah ditagih' memanggil POST collection-reminders/mark (customer_id, order_id); kartu dimuat ulang", async () => {
  routeGet(PETA);
  mockPost.mockResolvedValue({ data: {} });
  await mount(<FinanceDesk currentUser={FIN} selectedEntity="ent_ksc" />);
  const awal = jumlahMuatMeja();
  expect(teks(q("fin-desk-piutang_lewat_tempo-action-so1"))).toContain("Catat sudah ditagih");
  await klik("fin-desk-piutang_lewat_tempo-action-so1"); await tunggu();
  expect(mockPost).toHaveBeenCalledWith("/api/collection-reminders/mark",
    { customer_id: "cus1", order_id: "so1", note: "Pengingat penagihan SO-1" });
  expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: "Toko D ditandai sudah diingatkan." }));
  expect(jumlahMuatMeja()).toBeGreaterThan(awal);
});

test("piutang lewat tempo tanpa izin order.update: tombol tetap menavigasi seperti dulu (pop-up rincian + ikon pindah layar), tanpa POST", async () => {
  routeGet(PETA);
  await mount(<FinanceDesk currentUser={FIN_TANPA_UPDATE} selectedEntity="ent_ksc" />);
  expect(teks(q("fin-desk-piutang_lewat_tempo-action-so1"))).not.toContain("Catat sudah ditagih");
  await klik("fin-desk-piutang_lewat_tempo-action-so1"); await tunggu();
  expect(mockPost).not.toHaveBeenCalled();
  expect(q("fin-desk-detail-action-nav")).not.toBeNull();
});

// ── Satu sumber: salinan lama dihapus, layar asal memakai komponen/hook bersama ──────────────────────────────────────
const SRC = path.join(__dirname, "..");
const baca = (rel) => fs.readFileSync(path.join(SRC, rel), "utf8");

test("satu sumber kebenaran: tidak ada salinan inline keputusan selisih / terbit denda / tandai diingatkan", () => {
  const antrean = baca("finance/payments/PaymentVarianceQueue.jsx");
  expect(antrean).toContain("PaymentVarianceDecideDialog");
  expect(antrean).not.toMatch(/decideVariance|varianceByReceipt|pv-putus|openDecide/);
  for (const f of ["finance/CreditDeskView.jsx", "finance/payments/PenaltyPanel.jsx"]) {
    const s = baca(f);
    expect(s).toContain("useIssuePenalty");
    expect(s).not.toMatch(/issuePenalty\(|pnl-terbit|Terbitkan denda \$\{/);
  }
  expect(baca("finance/payments/penaltyIssue.js")).toMatch(/pnl-terbit/);
  for (const f of ["crm/CollectionWorklist.jsx", "sales/mobile/MobileCollectionTargets.jsx"]) {
    const s = baca(f);
    expect(s).toContain("markReminded");
    expect(s).not.toContain("collection-reminders/mark");
  }
  expect(baca("crm/collectionMark.js")).toContain("collection-reminders/mark");
});
