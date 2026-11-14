// PM-T3 — kwitansi ber-rekening & ber-referensi; status "terverifikasi bank"; rekonsiliasi per rekening lewat kode bayar.
// Uji komponen (bagian layar U18; uji jalan peramban terpisah): form kwitansi (rekening penerima dari instruksi pesanan,
// peringatan tidak sesuai instruksi + catatan wajib, nomor referensi wajib menurut pengaturan, konfirmasi menyebut
// nominal · PT · rekening), riwayat kwitansi (kolom Rekening & No. referensi, lencana status, saringan belum
// terverifikasi), Rekonsiliasi Bank (lencana kode bayar, "Catat kwitansi dari mutasi ini" → kwitansi lalu tautan mutasi).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";
import { EntityScopeProvider } from "../../context/EntityScopeContext";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    put: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      <option value="" />
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange?.(e.target.value)} />,
  formatDateId: (v) => String(v || ""),
}));
jest.mock("../../components/AskKnButton", () => ({ __esModule: true, AskKnButton: () => null, PENDING_KEY: "x" }));
jest.mock("../finance/payments/paymentApi", () => ({
  assessVariance: () => Promise.resolve({ direction: "none" }),
  directionMeta: () => ({ label: "", bg: "", fg: "" }), varianceMeta: () => Promise.resolve({ reasons: [] }),
  varianceKindMeta: () => ({ label: "", bg: "", fg: "" }),
}));
jest.mock("../documents/DocumentActionsBar", () => () => null);

/* eslint-disable import/first */
import ARReceiptModal from "../crm/ARReceiptModal";
import ARReceiptsHistory, { receiptStatus } from "../crm/ARReceiptsHistory";
import ReconLinesTable from "../finance/bank/ReconLinesTable";
import { invalidatePaymentMethods } from "../../config/paymentMethods";
/* eslint-enable import/first */

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const M = (code, name, need = "bank", due = false) => ({ code, name, needs_account: need, needs_reference: need === "bank",
  needs_due_date: due });
const MASUK = [M("transfer", "Transfer bank"), M("cash", "Tunai", "kas"), M("giro", "Giro / cek", "bank", true)];
const ENT = [{ id: "ent_ksc", short_name: "Sukacita", legal_name: "PT Kain Suka Cita" }];
const A = { id: "rek_a", name: "BCA Penerimaan KSC", bank_name: "BCA", account_number: "123-456-7890",
  holder_name: "PT Kain Suka Cita", is_default: true };
const A2 = { id: "rek_a2", name: "Mandiri Penerimaan KSC", bank_name: "Mandiri", account_number: "140-00-7777",
  holder_name: "PT Kain Suka Cita", is_default: false };
const S1 = { order_id: "so1", number: "KSC/SO-0001", outstanding: 1500000, receiving_account_id: "rek_a",
  receiving_account: { bank_name: "BCA", account_number: "123-456-7890", holder_name: "PT Kain Suka Cita" },
  payment_code: "KN-7F3K2" };

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 10) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(<EntityScopeProvider selectedEntity="ent_ksc" entities={ENT} canSwitch>{el}<ConfirmHost /></EntityScopeProvider>);
  });
  await flush();
  return host;
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
async function type(el, value) {
  const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new Event("input", { bubbles: true })); });
  await flush(3);
}
async function pick(el, value) {
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set;
    setter.call(el, value);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}
function routeGet(map) {
  mockGet.mockImplementation((url, cfg) => {
    const key = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.includes(k));
    const v = key ? map[key] : [];
    return Promise.resolve({ data: typeof v === "function" ? v(cfg) : v });
  });
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  [mockGet, mockPost].forEach((m) => m.mockReset());
  invalidatePaymentMethods();
  document.body.innerHTML = "";
});

const dasar = (extra = {}) => ({
  "/payment-methods": MASUK, "/ar-receipts/open-orders": [S1], "/ar-receipts/deposit": {},
  "/bank-accounts/receiving": (cfg) => (cfg?.params?.method === "transfer" ? [A, A2] : []),
  "/settings/effective": { payment: { wajib_nomor_referensi: false } }, ...extra });

test("form kwitansi: rekening penerima dari instruksi pesanan; beda instruksi → peringatan + catatan wajib; konfirmasi N5", async () => {
  routeGet(dasar());
  mockPost.mockResolvedValue({ data: { id: "arc_1", number: "AR-1", amount: 1500000, applied_total: 1500000 } });
  const onDone = jest.fn();
  await mount(<ARReceiptModal customerId="c1" customerName="Toko Maju" preselectOrderId="so1" onClose={() => {}} onDone={onDone} />);
  expect(q("ar-receipt-account").value).toBe("rek_a");                       // rekening tujuan pesanan S1
  expect(q("ar-receipt-mismatch")).toBeNull();
  expect(q("ar-receipt-notes").getAttribute("placeholder")).not.toMatch(/referensi/i);   // referensi punya isian sendiri
  expect(q("ar-receipt-instruction-so1").textContent).toContain("KN-7F3K2");
  await pick(q("ar-receipt-account"), "rek_a2");
  expect(q("ar-receipt-mismatch").textContent).toContain("Tidak sesuai instruksi bayar pesanan KSC/SO-0001 (BCA 123-456-7890 a.n. PT Kain Suka Cita)");
  expect(q("ar-receipt-submit").disabled).toBe(true);
  expect(q("ar-receipt-account-reason").textContent).toBe("Isi catatan alasan — rekening berbeda dari instruksi bayar pesanan.");
  await type(q("ar-receipt-mismatch-note"), "Pelanggan salah transfer");
  await type(q("ar-receipt-reference"), "TRX-1");
  expect(q("ar-receipt-submit").disabled).toBe(false);
  await click(q("ar-receipt-submit"));
  // Konfirmasi menyebut nominal, PT, dan rekening penerima; belum ada POST sebelum disetujui.
  expect(mockPost).not.toHaveBeenCalled();
  expect(q("ar-receipt-confirm").textContent).toMatch(/Rp\s?1\.500\.000/);
  expect(q("ar-receipt-confirm-message").textContent).toContain("Sukacita");
  expect(q("ar-receipt-confirm-message").textContent).toContain("Mandiri Penerimaan KSC · Mandiri 140-00-7777");
  await click(q("ar-receipt-confirm-confirm"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  const [url, body, cfg] = mockPost.mock.calls[0];
  expect(url).toBe("/api/ar-receipts");
  expect(body).toMatchObject({ amount: 1500000, method: "transfer", account_id: "rek_a2", reference_no: "TRX-1",
    mismatch_note: "Pelanggan salah transfer", allocations: [{ order_id: "so1", amount: 1500000 }] });
  expect(cfg.headers["Idempotency-Key"]).toBeTruthy();
  expect(onDone).toHaveBeenCalled();
});

test("form kwitansi: nomor referensi bertanda wajib bila pengaturan PT menyala; giro meminta jatuh tempo", async () => {
  routeGet(dasar({ "/settings/effective": { payment: { wajib_nomor_referensi: true } },
    "/bank-accounts/receiving": () => [A] }));
  await mount(<ARReceiptModal customerId="c1" customerName="Toko Maju" preselectOrderId="so1" onClose={() => {}} onDone={() => {}} />);
  expect(document.body.querySelector("label[for='ar-receipt-reference']").textContent).toBe("No. referensi *");
  expect(q("ar-receipt-account").disabled).toBe(true);                        // satu-satunya rekening → terkunci
  expect(q("ar-receipt-account-locked")).not.toBeNull();
  expect(q("ar-receipt-submit").disabled).toBe(true);
  expect(q("ar-receipt-account-reason").textContent).toBe("Isi nomor referensi (wajib untuk Transfer bank).");
  await type(q("ar-receipt-reference"), "TRX-2");
  expect(q("ar-receipt-submit").disabled).toBe(false);
  await pick(q("ar-receipt-method"), "giro");
  expect(q("ar-receipt-giro-due")).not.toBeNull();
  expect(q("ar-receipt-account-reason").textContent).toBe("Isi jatuh tempo giro.");
});

test("form kwitansi dari mutasi bank: nominal, rekening mutasi, referensi, tanggal terisi", async () => {
  routeGet(dasar());
  await mount(<ARReceiptModal customerId="c1" customerName="Toko Maju" preselectOrderId="so1" onClose={() => {}} onDone={() => {}}
    preset={{ amount: 1400000, accountId: "rek_a2", reference: "KN-7F3K2", date: "2026-11-12" }} />);
  expect(q("ar-receipt-alloc-so1").value).toMatch(/^1.?400.?000$/);
  expect(q("ar-receipt-account").value).toBe("rek_a2");
  expect(q("ar-receipt-reference").value).toBe("KN-7F3K2");
  expect(q("ar-receipt-mismatch")).not.toBeNull();                          // mutasi masuk ke rekening lain dari instruksi
});

test("riwayat kwitansi: kolom rekening & referensi, lencana status, tanda tidak sesuai instruksi, saringan belum terverifikasi", async () => {
  const rows = [
    { id: "r1", number: "AR-1", customer_name: "Toko Maju", method: "transfer", payment_method_code: "transfer",
      amount: 1500000, status: "posted", bank_verified: true, reference_no: "TRX-1",
      account_snapshot: { name: "BCA", bank_name: "BCA", account_number: "123" } },
    { id: "r2", number: "AR-2", customer_name: "Toko Maju", method: "transfer", payment_method_code: "transfer",
      amount: 1111000, status: "posted", bank_verified: false, instruction_mismatch: true, mismatch_note: "salah transfer",
      account_snapshot: { name: "Mandiri", bank_name: "Mandiri", account_number: "140" } },
    { id: "r3", number: "AR-3", customer_name: "Toko Maju", method: "cash", amount: 230000, status: "posted" },
    { id: "r4", number: "AR-4", customer_name: "Toko Maju", method: "transfer", amount: 99000, status: "void" },
  ];
  routeGet({ "/payment-methods": MASUK, "/settings/effective": { payment: { hari_wajar_verifikasi_bank: 3 } },
    "/ar-receipts": (cfg) => ({ items: cfg?.params?.bank_verified === "false" ? [rows[1]] : rows,
      total: cfg?.params?.bank_verified === "false" ? 1 : 4, page: 1, page_size: 25, has_more: false }) });
  await mount(<ARReceiptsHistory refreshKey={0} selectedEntity="ent_ksc" currentUser={{ permissions: {} }} />);
  const head = [...document.body.querySelectorAll("[data-testid='ar-history-table'] th")].map((t) => t.textContent);
  expect(head).toEqual(expect.arrayContaining(["Rekening", "No. referensi"]));
  expect(head).not.toContain("Metode");
  const st = (id) => q(`ar-history-status-${id}`).textContent;
  expect([st("r1"), st("r2"), st("r3"), st("r4")]).toEqual(["Terverifikasi bank", "Tercatat", "Tunai", "Dianulir"]);
  for (const id of ["r1", "r2", "r3", "r4"]) expect(q(`ar-history-status-${id}`).querySelector("svg")).not.toBeNull();
  expect(q("ar-history-account-r1").textContent).toContain("Transfer bank");
  expect(q("ar-history-ref-r1").textContent).toBe("TRX-1");
  expect(q("ar-history-mismatch-r2").textContent).toBe("Tidak sesuai instruksi");
  expect(q("ar-history-unverified").textContent).toContain("Belum terverifikasi lebih dari 3 hari");
  await click(q("ar-history-unverified-toggle"));
  const call = mockGet.mock.calls.filter((c) => c[0] === "/api/ar-receipts").pop();
  expect(call[1].params).toMatchObject({ bank_verified: "false", older_than_days: "", entity_id: "ent_ksc" });
  expect(q("ar-history-row-r1")).toBeNull();
  expect(receiptStatus({ amount: 0, method: "deposit", status: "posted" }).label).toBe("Tercatat");
});

test("rekonsiliasi: lencana kode bayar; tombol catat kwitansi hanya bila pesanan belum punya kwitansi yang menunggu", async () => {
  const onRecord = jest.fn();
  const hit = { code: "KN-7F3K2", order_id: "so1", order_number: "KSC/SO-0001", customer_id: "c1", customer_name: "Toko Maju",
    has_open_receipt: false };
  const lines = [
    { id: "l1", stmt_date: "2026-11-14", amount: 1500000, direction: "in", status: "unmatched", description: "TRSF KN-7F3K2",
      pay_code_hits: [hit] },
    { id: "l2", stmt_date: "2026-11-14", amount: 1400000, direction: "in", status: "unmatched", description: "TRSF KN-8H4M3",
      pay_code_hits: [{ ...hit, code: "KN-8H4M3", has_open_receipt: true }] },
    { id: "l3", stmt_date: "2026-11-14", amount: 900000, direction: "in", status: "unmatched", description: "SETORAN" },
  ];
  await mount(<ReconLinesTable lines={lines} busy="" onAction={() => {}} onOpenMatch={() => {}} onReload={() => {}}
    onError={() => {}} onNotify={() => {}} onRecordReceipt={onRecord} />);
  expect(q("recon-paycode-l1-KN-7F3K2").textContent).toBe("Kode bayar KN-7F3K2");
  expect(q("recon-paycode-l1-KN-7F3K2").querySelector("svg")).not.toBeNull();
  expect(q("recon-paycode-l2-KN-8H4M3")).not.toBeNull();
  expect(q("recon-record-receipt-l2")).toBeNull();                         // sudah ada kwitansi → cocokkan saja
  expect(q("recon-paycodes-l3")).toBeNull();
  expect(q("recon-record-receipt-l1").textContent).toContain("Catat kwitansi dari mutasi ini");
  await click(q("recon-record-receipt-l1"));
  expect(onRecord).toHaveBeenCalledWith(lines[0], hit);
});

test("rekonsiliasi mode Semua PT: tombol catat kwitansi mati dengan alasan tertulis", async () => {
  const lines = [{ id: "l1", stmt_date: "2026-11-14", amount: 1500000, direction: "in", status: "unmatched",
    pay_code_hits: [{ code: "KN-7F3K2", order_id: "so1", customer_id: "c1", has_open_receipt: false }] }];
  await mount(<ReconLinesTable lines={lines} busy="" onAction={() => {}} onOpenMatch={() => {}} onReload={() => {}}
    onError={() => {}} onNotify={() => {}} onRecordReceipt={() => {}} recordBlockReason="Pilih satu PT dulu." />);
  expect(q("recon-record-receipt-l1").disabled).toBe(true);
  expect(q("recon-record-receipt-reason-l1").textContent).toBe("Pilih satu PT dulu.");
});
