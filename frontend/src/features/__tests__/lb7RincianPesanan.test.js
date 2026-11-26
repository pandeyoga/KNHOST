// Lapor Bayar CBD & DP · Tugas 7 — layar rincian pesanan: lapor bayar (dialog + bukti), daftar laporan (bukti, terima/tolak
// Finance), panel "Bayar sebelum gudang", tombol kwitansi langsung yang disembunyikan, Faktur Komersial sejak disetujui,
// langkah Perjalanan "Bayar dicek Finance" (desktop & HP), dan label status ber-Indonesia.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import DispatchPaymentGatePanel from "../orders/DispatchPaymentGatePanel";
import LaporBayarDialog from "../orders/payReport/LaporBayarDialog";
import PayReportList from "../orders/payReport/PayReportList";
import OrderJourneyPanel from "../orders/OrderJourneyPanel";
import MobileOrderJourney from "../sales/mobile/MobileOrderJourney";
import { OrderDetailPanel } from "../orders/OrderDetailPanel";
import { ORDER_PRINT_DOCS, printDocsForOrder } from "../documents/orderPrintDocs";
import { docStatusLabel } from "../../utils/docStatus";
import { askConfirm, askReason } from "../../services/confirmService";
import { notifySuccess } from "../../utils/feedback";
import { toast } from "../../hooks/use-toast";
import { todayWib } from "../../utils/formatters";

jest.mock("../../services/apiClient", () => ({
  __esModule: true, default: { get: jest.fn(), post: jest.fn(), patch: jest.fn(), defaults: { headers: { common: {} } } }, API: "/api",
}));
jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid, disabled }) => (
    <select data-testid={tid} value={value ?? ""} disabled={disabled} onChange={(e) => onValueChange(e.target.value)}>
      <option value="" />
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: M, KNSelect: M };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: ({ value, onChange, "data-testid": tid }) => <input data-testid={tid} value={value || ""} onChange={(e) => onChange(e.target.value)} />,
}));
jest.mock("../../services/confirmService", () => ({ askConfirm: jest.fn(), askReason: jest.fn() }));
jest.mock("../../utils/feedback", () => ({ notifySuccess: jest.fn() }));
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: jest.fn() }));   // LB-T8 (R15 M4): unggah gagal = toast galat
jest.mock("../../hooks/useBlobUrl", () => ({
  ...jest.requireActual("../../hooks/useBlobUrl"),
  useBlobUrl: () => ({ src: "blob:bukti", type: "image/png", status: "ok" }),   // fungsi biasa: `resetMocks` CRA mengosongkan jest.fn
}));
jest.mock("../documents/DocumentActionsBar", () => ({ docType }) => <i data-testid={`dab-${docType}`} />);
jest.mock("../documents/RelatedDocsPanel", () => ({ docs = [] }) => (
  <div data-testid="related-docs">{docs.map((d) => <i key={d.docType} data-testid={`rd-${d.docType}`}>{d.label}</i>)}</div>));
jest.mock("../documents/ProcessTimeline", () => () => null);
jest.mock("../documents/trace/DocRefsPanel", () => () => null);
jest.mock("../finance/payments/SoPaymentPanel", () => () => null);
jest.mock("../orders/PodProgressNote", () => () => null);
jest.mock("../orders/SoApprovalsPanel", () => () => null);
jest.mock("../orders/OrderFulfillmentBadges", () => () => null);
jest.mock("../orders/OrderIntercoSupplyPanel", () => () => null);
jest.mock("../orders/OrderTransferLinks", () => () => null);
jest.mock("../orders/RestockPanel", () => () => null);
jest.mock("../finance/amendments/AmendmentTrailPanel", () => () => null);
jest.mock("../orders/OrderFeedbackPanel", () => () => null);
jest.mock("../finance/payments/ReceivePaymentModal", () => () => <div data-testid="ar-receipt-modal" />);

const axios = require("../../services/apiClient").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
const q = (id, host = document) => host.querySelector(`[data-testid="${id}"]`);
const tick = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
const setVal = (el, v) => {
  Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), "value").set.call(el, v);
  el.dispatchEvent(new Event(el.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
};
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await tick();
  return { host, root };
}
afterEach(() => { document.body.innerHTML = ""; });

const ORDER = { id: "so1", number: "KSC/SO-1", entity_id: "ent1", status: "approved", customer_id: "c1", customer_name: "Toko",
  receiving_account_id: "acc1", pay_hold: { since: "2026-11-25T03:00:00Z", due_at: new Date(Date.now() + 2.5 * 86400000).toISOString(), required: 1000000 } };
const GATE = { applies: true, blocked: true, term_code: "CBD", term_name: "CBD", dp_percent: 100, grand_total: 1000000,
  required: 1000000, paid: 400000, shortfall: 600000, released: null, mode: "block" };
const METHODS = [
  { code: "transfer", name: "Transfer Bank", needs_account: "bank", needs_reference: true },
  { code: "cash", name: "Tunai", needs_account: "kas" },
  { code: "giro", name: "Giro", needs_account: "bank", needs_due_date: true },
];
const ACCOUNTS = [
  { id: "acc1", name: "BCA Utama", bank_name: "BCA", account_number: "123", holder_name: "PT A" },
  { id: "acc2", name: "Mandiri", bank_name: "Mandiri", account_number: "456", holder_name: "PT A" },
];
const REPORT = { id: "lb1", number: "LB-1", order_id: "so1", order_number: "KSC/SO-1", amount: 600000, transfer_date: "2026-11-25",
  method: "transfer", account_id: "acc1", account_name: "BCA Utama", status: "menunggu", created_by_name: "Sari", note: "",
  attachments: [{ id: "att1", original_filename: "bukti.png", content_type: "image/png" }], attachment_count: 1 };

function route({ reports = [], bisaLapor = true, bisaPutuskan = false, refRequired = false } = {}) {
  axios.get.mockImplementation(async (url) => {
    if (url === "/api/payment-methods") return { data: METHODS };
    if (url === "/api/bank-accounts/receiving") return { data: ACCOUNTS };
    if (url === "/api/settings/effective") return { data: { payment: { wajib_nomor_referensi: refRequired } } };
    if (url === "/api/sales-orders/so1/payment-reports") return { data: { items: reports, bisa_lapor: bisaLapor, bisa_putuskan: bisaPutuskan } };
    if (url === "/api/sales-orders/so1/dispatch-payment-gate") return { data: GATE };
    if (url === "/api/cash-holdings/me/summary") return { data: { mode: "dilarang" } };   // LB-T8 (R15 M3): tunai dilarang → tombol kwitansi sales tetap tersembunyi (kasus tunai diuji di lb8MejaHp)
    return { data: [] };
  });
}
beforeEach(() => {
  axios.get.mockReset(); axios.post.mockReset(); askConfirm.mockReset(); askReason.mockReset(); notifySuccess.mockReset();
  route();
});
const file = (name = "bukti.png", type = "image/png") => new File(["x"], name, { type });
async function pickFile(f) {
  const input = q("lapor-bayar-file");
  await act(async () => {
    Object.defineProperty(input, "files", { value: [f], configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

describe("Lapor bayar — dialog", () => {
  test("bukti kosong → kirim mati; kirim → POST laporan lalu unggah bukti, toast, muat ulang", async () => {
    axios.post.mockImplementation(async (url) => (url.endsWith("/payment-reports") ? { data: { ...REPORT, attachments: [] } } : { data: REPORT }));
    const onDone = jest.fn();
    await mount(<LaporBayarDialog order={ORDER} shortfall={600000} onClose={() => {}} onDone={onDone} />);
    expect(q("lapor-bayar-amount").value).toMatch(/600000/);                  // bawaan = kurang
    expect(q("lapor-bayar-date").value).toBe(todayWib());                      // bawaan = hari ini
    // cara bayar: tunai & giro/cek (berjatuh tempo) tidak ditawarkan
    expect([...q("lapor-bayar-method").options].map((o) => o.value).filter(Boolean)).toEqual(["transfer"]);
    await act(async () => setVal(q("lapor-bayar-method"), "transfer"));
    await tick();
    expect(q("lapor-bayar-account").value).toBe("acc1");                       // rekening instruksi pesanan
    expect(q("lapor-bayar-submit").disabled).toBe(true);                       // belum ada bukti
    await pickFile(file());
    expect(q("lapor-bayar-submit").disabled).toBe(false);
    await act(async () => { q("lapor-bayar-submit").click(); });
    await tick();
    const [url1, body1, cfg1] = axios.post.mock.calls[0];
    expect(url1).toBe("/api/sales-orders/so1/payment-reports");
    expect(body1).toMatchObject({ amount: 600000, transfer_date: todayWib(), account_id: "acc1", method: "transfer" });
    expect(body1.mismatch_note).toBeUndefined();
    expect(cfg1.headers["Idempotency-Key"]).toBeTruthy();
    const [url2, body2] = axios.post.mock.calls[1];
    expect(url2).toBe("/api/payment-reports/lb1/attachments");
    expect(body2 instanceof FormData).toBe(true);
    expect(notifySuccess).toHaveBeenCalledWith("Laporan bayar dikirim ke Finance", expect.anything());
    expect(onDone).toHaveBeenCalled();
  });

  test("rekening ≠ rekening instruksi pesanan → 'Alasan rekening berbeda' wajib, dikirim sebagai mismatch_note", async () => {
    axios.post.mockResolvedValue({ data: REPORT });
    await mount(<LaporBayarDialog order={ORDER} shortfall={600000} onClose={() => {}} onDone={() => {}} />);
    await act(async () => setVal(q("lapor-bayar-method"), "transfer"));
    await tick();
    expect(q("lapor-bayar-mismatch-note")).toBeNull();
    await act(async () => setVal(q("lapor-bayar-account"), "acc2"));
    expect(q("lapor-bayar-mismatch-note")).not.toBeNull();
    expect(document.body.textContent).toMatch(/Alasan rekening berbeda/);
    await pickFile(file());
    expect(q("lapor-bayar-submit").disabled).toBe(true);                       // alasan masih kosong
    await act(async () => setVal(q("lapor-bayar-mismatch-note"), "Pelanggan salah transfer"));
    expect(q("lapor-bayar-submit").disabled).toBe(false);
    await act(async () => { q("lapor-bayar-submit").click(); });
    await tick();
    expect(axios.post.mock.calls[0][1]).toMatchObject({ account_id: "acc2", mismatch_note: "Pelanggan salah transfer" });
  });

  test("referensi wajib bila PT meminta (pengaturan) → kirim mati sampai diisi", async () => {
    route({ refRequired: true });
    await mount(<LaporBayarDialog order={ORDER} shortfall={600000} onClose={() => {}} onDone={() => {}} />);
    await act(async () => setVal(q("lapor-bayar-method"), "transfer"));
    await tick();
    await pickFile(file());
    expect(q("lapor-bayar-submit").disabled).toBe(true);
    await act(async () => setVal(q("lapor-bayar-reference"), "TRX-77"));
    expect(q("lapor-bayar-submit").disabled).toBe(false);
  });

  test("galat server (melebihi sisa) tampil di dalam dialog; tidak ada unggahan", async () => {
    axios.post.mockRejectedValue({ response: { status: 409, data: { detail: "Nominal melebihi sisa tagihan pesanan (Rp 600.000)." } } });
    const onDone = jest.fn();
    await mount(<LaporBayarDialog order={ORDER} shortfall={600000} onClose={() => {}} onDone={onDone} />);
    await act(async () => setVal(q("lapor-bayar-method"), "transfer"));
    await tick();
    await pickFile(file());
    await act(async () => { q("lapor-bayar-submit").click(); });
    await tick();
    expect(q("lapor-bayar-modal-error").textContent).toMatch(/melebihi sisa tagihan/);
    expect(axios.post).toHaveBeenCalledTimes(1);
    expect(onDone).not.toHaveBeenCalled();
  });

  test("laporan terbentuk tetapi unggah gagal → dialog menutup, kabar 'Bukti belum terunggah', daftar dimuat ulang", async () => {
    axios.post.mockImplementation(async (url) => {
      if (url.endsWith("/payment-reports")) return { data: { ...REPORT, attachments: [] } };
      throw { response: { status: 502, data: { detail: "Gagal mengunggah file" } } };
    });
    const onDone = jest.fn();
    await mount(<LaporBayarDialog order={ORDER} shortfall={600000} onClose={() => {}} onDone={onDone} />);
    await act(async () => setVal(q("lapor-bayar-method"), "transfer"));
    await tick();
    await pickFile(file());
    await act(async () => { q("lapor-bayar-submit").click(); });
    await tick();
    expect(onDone).toHaveBeenCalled();
    // R15 M4 — kabar GAGAL: toast galat, bukan notifySuccess.
    expect(toast).toHaveBeenCalledWith(expect.objectContaining({ variant: "destructive", description: expect.stringMatching(/Bukti belum terunggah/) }));
    expect(notifySuccess).not.toHaveBeenCalledWith("Laporan bayar dibuat", expect.anything());
  });
});

describe("Lapor bayar — daftar laporan", () => {
  const UP = { ...REPORT, attachments: [], attachment_count: 0 };
  const mountList = (reports, props = {}) => mount(
    <PayReportList reports={reports} canDecide={false} canCreate={false} onChanged={() => {}} {...props} />);

  test("baris: status, nominal, tanggal, pelapor, bukti lewat blob; alasan tolak tampil", async () => {
    const { host } = await mountList([REPORT, { ...REPORT, id: "lb2", number: "LB-2", status: "ditolak", reason: "Nominal tidak cocok" }]);
    expect(q("pay-report-lb1", host).textContent).toMatch(/Menunggu dicek/);
    expect(q("pay-report-lb1", host).textContent).toMatch(/600\.000/);
    expect(q("pay-report-lb1", host).textContent).toMatch(/Sari/);
    expect(q("pay-report-lb1-proof-att1", host).getAttribute("src")).toBe("blob:bukti");
    expect(q("pay-report-lb2", host).textContent).toMatch(/Nominal tidak cocok/);
  });

  test("tanpa payment_report.decide tidak ada tombol Terima/Tolak", async () => {
    const { host } = await mountList([REPORT]);
    expect(q("pay-report-lb1-terima", host)).toBeNull();
    expect(q("pay-report-lb1-tolak", host)).toBeNull();
  });

  test("Terima: pratinjau kwitansi → konfirmasi → POST terima; waiting_bank menampilkan 'Menunggu cocok mutasi bank'", async () => {
    askConfirm.mockResolvedValue(true);
    axios.post.mockResolvedValue({ data: { report: { ...REPORT, status: "diterima" }, receipt_number: "AR-0001", released: false, waiting_bank: true } });
    const onChanged = jest.fn();
    const { host } = await mountList([REPORT], { canDecide: true, onChanged });
    await act(async () => { q("pay-report-lb1-terima", host).click(); });
    await tick();
    expect(askConfirm.mock.calls[0][0].message).toMatch(/Kwitansi Rp\s?600\.000 ke rekening BCA Utama akan diterbitkan/);
    const [url, body, cfg] = axios.post.mock.calls[0];
    expect(url).toBe("/api/payment-reports/lb1/terima");
    expect(body).toBeNull();
    expect(cfg.headers["Idempotency-Key"]).toBeTruthy();
    expect(q("pay-report-notice", host).textContent).toMatch(/Menunggu cocok mutasi bank/);
    expect(onChanged).toHaveBeenCalled();
  });

  test("Terima dibatalkan di konfirmasi → tidak ada POST; galat 409 tampil di daftar", async () => {
    askConfirm.mockResolvedValueOnce(false);
    const { host } = await mountList([REPORT], { canDecide: true });
    await act(async () => { q("pay-report-lb1-terima", host).click(); });
    await tick();
    expect(axios.post).not.toHaveBeenCalled();
    askConfirm.mockResolvedValueOnce(true);
    axios.post.mockRejectedValue({ response: { status: 409, data: { detail: "Lampirkan bukti bayar dulu" } } });
    await act(async () => { q("pay-report-lb1-terima", host).click(); });
    await tick();
    expect(q("pay-report-error", host).textContent).toMatch(/Lampirkan bukti bayar dulu/);
  });

  test("Tolak: askReason dibatalkan → tidak ada POST; dengan alasan → POST tolak {reason}", async () => {
    askReason.mockResolvedValueOnce(null);
    axios.post.mockResolvedValue({ data: { ...REPORT, status: "ditolak", reason: "Salah rekening" } });
    const { host } = await mountList([REPORT], { canDecide: true });
    await act(async () => { q("pay-report-lb1-tolak", host).click(); });
    await tick();
    expect(axios.post).not.toHaveBeenCalled();
    askReason.mockResolvedValueOnce("Salah rekening");
    await act(async () => { q("pay-report-lb1-tolak", host).click(); });
    await tick();
    const [url, body] = axios.post.mock.calls[0];
    expect(url).toBe("/api/payment-reports/lb1/tolak");
    expect(body).toEqual({ reason: "Salah rekening" });
  });

  test("tanpa bukti: 'Bukti belum terunggah — unggah ulang' → unggah ulang ke laporan yang sama", async () => {
    axios.post.mockResolvedValue({ data: REPORT });
    const onChanged = jest.fn();
    const { host } = await mountList([UP], { canCreate: true, canDecide: true, onChanged });
    expect(q("pay-report-lb1-noproof", host).textContent).toMatch(/Bukti belum terunggah — unggah ulang/);
    const input = q("pay-report-lb1-retry-file", host);
    await act(async () => {
      Object.defineProperty(input, "files", { value: [file()], configurable: true });
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await tick();
    expect(axios.post.mock.calls[0][0]).toBe("/api/payment-reports/lb1/attachments");
    expect(axios.post.mock.calls[0][1] instanceof FormData).toBe(true);
    expect(onChanged).toHaveBeenCalled();
  });
});

describe("R18-b — laporan macet di 'memproses'", () => {
  const MACET = { ...REPORT, status: "memproses", claim_stale: true, claim_at: "2026-11-25T03:05:00+00:00", claim_by_name: "Finance X" };
  const mountList = (reports, props = {}) => mount(
    <PayReportList reports={reports} canDecide={false} canCreate={false} onChanged={() => {}} {...props} />);

  test("pemutus: 'Macet sejak … — ulangi Terima / Tolak' + tombol Ulangi Terima & Tolak; keduanya mengirim ke server", async () => {
    askConfirm.mockResolvedValue(true);
    axios.post.mockResolvedValue({ data: { report: { ...MACET, status: "diterima" }, receipt_number: "AR-9", released: true, waiting_bank: false } });
    const onChanged = jest.fn();
    const { host } = await mountList([MACET], { canDecide: true, onChanged });
    const note = q("pay-report-lb1-stale", host);
    expect(note.textContent).toMatch(/Macet sejak 25 Nov 2026,? 10[.:]05 WIB \(Finance X\) — ulangi Terima \/ Tolak/);
    expect(q("pay-report-lb1-status", host).textContent).toMatch(/Macet/);
    expect(q("pay-report-lb1-terima", host).textContent).toMatch(/Ulangi Terima/);
    await act(async () => { q("pay-report-lb1-terima", host).click(); });
    await tick();
    expect(axios.post.mock.calls[0][0]).toBe("/api/payment-reports/lb1/terima");
    expect(onChanged).toHaveBeenCalledWith(expect.objectContaining({ ok: true, kind: "terima" }));
    askReason.mockResolvedValueOnce("Bukti tidak cocok");
    axios.post.mockResolvedValue({ data: { ...MACET, status: "ditolak" } });
    await act(async () => { q("pay-report-lb1-tolak", host).click(); });
    await tick();
    expect(axios.post.mock.calls[1][0]).toBe("/api/payment-reports/lb1/tolak");
    expect(axios.post.mock.calls[1][1]).toEqual({ reason: "Bukti tidak cocok" });
  });

  test("memproses yang belum basi: 'Sedang diproses Finance', tanpa tombol", async () => {
    const { host } = await mountList([{ ...MACET, claim_stale: false }], { canDecide: true });
    expect(q("pay-report-lb1-status", host).textContent).toMatch(/Sedang diproses Finance/);
    expect(q("pay-report-lb1-stale", host)).toBeNull();
    expect(q("pay-report-lb1-terima", host)).toBeNull();
    expect(q("pay-report-lb1-tolak", host)).toBeNull();
  });

  test("bukan pemutus: laporan macet tanpa tombol dan tanpa ajakan mengulang", async () => {
    const { host } = await mountList([MACET], { canDecide: false });
    expect(q("pay-report-lb1-stale", host)).toBeNull();
    expect(q("pay-report-lb1-terima", host)).toBeNull();
    expect(q("pay-report-lb1-tolak", host)).toBeNull();
  });
});

describe("Panel Bayar sebelum gudang", () => {
  const SALES = { permissions: { order: ["view"], ar_receipt: ["create"], payment_report: ["create"] } };
  const FIN = { permissions: { order: ["view"], ar_receipt: ["create"], payment_report: ["create", "decide"] } };
  const panel = (user, order = ORDER, gate = GATE) => mount(
    <DispatchPaymentGatePanel orderId="so1" initial={gate} currentUser={user} order={order} customerId="c1" customerName="Toko" />);

  test("judul 'Bayar sebelum gudang' + batas bayar dengan sisa hari + tombol Lapor bayar", async () => {
    const { host } = await panel(SALES);
    expect(q("so-gate-title", host).textContent).toBe("Bayar sebelum gudang");
    expect(q("so-gate-batas", host).textContent).toMatch(/Batas bayar/);
    expect(q("so-gate-batas", host).textContent).toMatch(/sisa 3 hari/);
    expect(q("so-gate-lapor-open", host)).not.toBeNull();
  });

  test("pesanan tahan bayar: tombol kwitansi langsung tersembunyi untuk sales, tampil untuk Finance", async () => {
    const sales = await panel(SALES);
    expect(q("so-gate-receipt-open", sales.host)).toBeNull();
    const fin = await panel(FIN);
    expect(q("so-gate-receipt-open", fin.host)).not.toBeNull();
  });

  test("pesanan wajib bayar dulu yang belum sampai penanda tahan (reserved) juga tersembunyi bagi sales", async () => {
    const { host } = await panel(SALES, { ...ORDER, status: "reserved", pay_hold: undefined });
    expect(q("so-gate-receipt-open", host)).toBeNull();
    expect(q("so-gate-title", host).textContent).toBe("Bayar sebelum gudang");
  });

  test("pesanan sudah dilepas ke gudang (confirmed): perilaku lama — judul kirim, kwitansi langsung tampil", async () => {
    const { host } = await panel(SALES, { ...ORDER, status: "confirmed", pay_hold: undefined });
    expect(q("so-gate-title", host).textContent).toBe("Bayar sebelum kirim");
    expect(q("so-gate-receipt-open", host)).not.toBeNull();
  });

  test("tanpa payment_report.create tidak ada tombol Lapor bayar; daftar laporan dimuat dan Terima hanya untuk pemutus", async () => {
    route({ reports: [REPORT], bisaLapor: false, bisaPutuskan: true });
    const view = await panel({ permissions: { order: ["view"], payment_report: ["decide"] } });
    expect(q("so-gate-lapor-open", view.host)).toBeNull();
    expect(q("pay-report-lb1-terima", view.host)).not.toBeNull();
    route({ reports: [REPORT], bisaLapor: true, bisaPutuskan: false });
    const sales = await panel(SALES);
    expect(q("pay-report-lb1", sales.host)).not.toBeNull();
    expect(q("pay-report-lb1-terima", sales.host)).toBeNull();
  });

  test("Lapor bayar membuka dialog", async () => {
    const { host } = await panel(SALES);
    await act(async () => { q("so-gate-lapor-open", host).click(); });
    await tick();
    expect(q("lapor-bayar-modal")).not.toBeNull();
  });
});

describe("Faktur Komersial sejak disetujui", () => {
  test("printDocsForOrder: pesanan approved tertahan → hanya Faktur Komersial; lainnya tidak berubah", () => {
    expect(printDocsForOrder({ status: "approved", pay_hold: { since: "x" } }).map((d) => d.docType)).toEqual(["invoice"]);
    expect(printDocsForOrder({ status: "approved" })).toEqual([]);
    expect(printDocsForOrder({ status: "reserved", pay_hold: { since: "x" } })).toEqual([]);
    expect(printDocsForOrder({ status: "confirmed" })).toBe(ORDER_PRINT_DOCS);
    expect(printDocsForOrder({ status: "shipped", pay_hold: null })).toBe(ORDER_PRINT_DOCS);
  });

  const SO = { ...ORDER, payment_status: "unpaid", items: [{ product_id: "p1", product_name: "Kain", sku: "A", quantity: 10, unit: "yard", price: 100000 }],
    grand_total: 1000000, total_amount: 1000000, net_subtotal: 1000000, ppn_amount: 0, is_pkp: false, created_at: "2026-11-25T03:00:00Z" };
  const user = { role: "sales", permissions: { order: ["view"] } };

  test("rincian pesanan approved ber-tahan menampilkan Faktur Komersial; tanpa tahan tidak", async () => {
    const a = await mount(<OrderDetailPanel order={SO} user={user} embedded onGenerateDocument={() => {}} />);
    expect(q("rd-invoice", a.host)).not.toBeNull();
    expect(q("rd-delivery_note", a.host)).toBeNull();
    const b = await mount(<OrderDetailPanel order={{ ...SO, pay_hold: undefined }} user={user} embedded onGenerateDocument={() => {}} />);
    expect(q("related-docs", b.host)).toBeNull();
  });
});

describe("Perjalanan — Bayar dicek Finance", () => {
  const STEPS = [
    { key: "dipesan", label: "Dipesan", done: true, state: "done" },
    { key: "disetujui", label: "Disetujui", done: true, state: "done" },
    { key: "bayar_dicek", label: "Bayar dicek Finance", done: false, state: "" },
    { key: "dikonfirmasi", label: "Dikonfirmasi (tugas gudang lahir)", done: false, state: "" },
  ];
  const JOURNEY = { steps: STEPS, progress: { percent: 40 }, fulfillment: {}, warehouse_tasks: [], shipments: [], logistics: [], receipts: [],
    tax_invoices: [], commercial_invoice: { available: true, number: "KSC/SO-1" }, paid_total: 400000, outstanding: 600000 };

  test("desktop: langkah bayar_dicek tampil dengan labelnya; yang dilewati server memakai gaya dilewati", async () => {
    axios.get.mockResolvedValue({ data: JOURNEY });
    const a = await mount(<OrderJourneyPanel orderId="so1" orderNumber="KSC/SO-1" />);
    expect(q("journey-step-bayar_dicek", a.host).textContent).toMatch(/Bayar dicek Finance/);
    axios.get.mockResolvedValue({ data: { ...JOURNEY, steps: STEPS.map((s) => (s.key === "bayar_dicek" ? { ...s, state: "skipped" } : s)) } });
    const b = await mount(<OrderJourneyPanel orderId="so1" orderNumber="KSC/SO-1" />);
    expect(q("journey-step-bayar_dicek", b.host)).not.toBeNull();
  });

  test("HP: bayar_dicek tertahan = langkah aktif dengan labelnya", async () => {
    axios.get.mockResolvedValue({ data: JOURNEY });
    const { host } = await mount(<MobileOrderJourney orderId="so1" />);
    expect(q("m-journey-step-so1-bayar_dicek", host).textContent).toMatch(/Bayar dicek Finance/);
    expect(q("m-journey-step-so1-bayar_dicek", host).querySelector("p").className).toMatch(/text-kn-action/);
  });

  test("HP: langkah dilewati server (bayar_dicek tidak berlaku) tidak tampil dan bukan langkah aktif — langkah berikutnya yang aktif", async () => {
    axios.get.mockResolvedValue({ data: { ...JOURNEY, steps: STEPS.map((s) => (s.key === "bayar_dicek" ? { ...s, state: "skipped" } : s)) } });
    const { host } = await mount(<MobileOrderJourney orderId="so1" />);
    expect(q("m-journey-step-so1-bayar_dicek", host)).toBeNull();
    expect(host.textContent).not.toMatch(/dilewati/);
    expect(q("m-journey-step-so1-dikonfirmasi", host).querySelector("p").className).toMatch(/text-kn-action/);
  });

  test("HP: langkah lain yang dilewati server (diverifikasi) tampil 'dilewati' dan tidak pernah aktif", async () => {
    const steps = [
      { key: "dipesan", label: "Dipesan", done: true, state: "done" },
      { key: "diverifikasi", label: "Diverifikasi Admin Sales", done: false, state: "skipped" },
      { key: "disetujui", label: "Disetujui", done: false, state: "" },
    ];
    axios.get.mockResolvedValue({ data: { ...JOURNEY, steps } });
    const { host } = await mount(<MobileOrderJourney orderId="so1" />);
    expect(q("m-journey-skipped-so1-diverifikasi", host)).not.toBeNull();
    expect(q("m-journey-step-so1-diverifikasi", host).querySelector("p").className).not.toMatch(/text-kn-action/);
    expect(q("m-journey-step-so1-disetujui", host).querySelector("p").className).toMatch(/text-kn-action/);
  });
});

describe("Label status", () => {
  test("sebagian dikirim / sebagian disiapkan berbahasa Indonesia", () => {
    expect(docStatusLabel("partially_shipped")).toBe("Sebagian dikirim");
    expect(docStatusLabel("partially_picked")).toBe("Sebagian disiapkan");
  });
});
