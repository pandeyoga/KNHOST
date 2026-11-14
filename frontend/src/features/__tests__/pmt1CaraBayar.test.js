// PM-T1 — satu daftar cara bayar (`config/paymentMethods.js`) dan rekening ber-peruntukan (layar Rekening & Saldo).
// Uji komponen (U15 bagian layar; uji jalan peramban terpisah): pilihan kwitansi dari master per PT (QRIS hilang bila
// dimatikan), form rekening (atas nama, peruntukan, cara bayar, bawaan, tampil di dokumen + alasan tertulis bila mati,
// 202 = pengajuan), bagian "Perubahan menunggu persetujuan" (lama → baru, konfirmasi menyebut rekening & PT, tombol
// mati beralasan untuk pengaju sendiri, tidak tampil bila kosong).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockPatch = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: (...a) => mockPatch(...a),
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
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../finance/payments/paymentApi", () => ({
  assessVariance: () => Promise.resolve({ direction: "none" }),
  directionMeta: () => ({ label: "", bg: "", fg: "" }), varianceMeta: () => Promise.resolve({ reasons: [] }),
}));

/* eslint-disable import/first */
import ARReceiptModal from "../crm/ARReceiptModal";
import BankAccountForm from "../finance/BankAccountForm";
import BankAccountChangesPanel from "../finance/BankAccountChangesPanel";
import { canonicalMethod, invalidatePaymentMethods } from "../../config/paymentMethods";
/* eslint-enable import/first */

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const M = (code, name, need = "bank") => ({ code, name, needs_account: need, needs_reference: need === "bank", needs_due_date: false });
const MASUK = [M("transfer", "Transfer bank"), M("cash", "Tunai", "kas"), M("giro", "Giro / cek"), M("qris", "QRIS"),
  M("deposit", "Titipan / saldo kredit", "tidak")];
const SEMUA = MASUK;

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 8) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(<>{el}<ConfirmHost /></>); });
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
  await flush(2);
}
function routeGet(map) {
  mockGet.mockImplementation((url, cfg) => {
    const key = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.includes(k));
    const v = key ? map[key] : [];
    return Promise.resolve({ data: typeof v === "function" ? v(cfg) : v });
  });
}
afterEach(async () => {
  const openCancel = document.body.querySelector(".modal-overlay [data-testid$='-cancel']");
  if (openCancel) await click(openCancel);
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  [mockGet, mockPost, mockPatch].forEach((m) => m.mockReset());
  invalidatePaymentMethods();
  document.body.innerHTML = "";
});

test("kata lama dibaca sebagai kode kanonik", () => {
  expect(canonicalMethod("Tunai")).toBe("cash");
  expect(canonicalMethod("kontan")).toBe("cash");
  expect(canonicalMethod("")).toBe("");
  expect(canonicalMethod("", "transfer")).toBe("transfer");
  expect(canonicalMethod("qris")).toBe("qris");
});

test("kwitansi: pilihan dari master arah masuk (tanpa titipan), QRIS tidak ada bila dimatikan untuk PT", async () => {
  routeGet({ "/payment-methods": (cfg) => (cfg?.params?.direction === "masuk" ? MASUK.filter((m) => m.code !== "qris") : []),
    "/ar-receipts/open-orders": [], "/ar-receipts/deposit": {} });
  await mount(<ARReceiptModal customerId="c1" customerName="Toko A" onClose={() => {}} onDone={() => {}} />);
  expect(mockGet).toHaveBeenCalledWith("/api/payment-methods", { params: { direction: "masuk" } });
  const opts = [...q("ar-receipt-method").options].map((o) => [o.value, o.textContent]);
  expect(opts).toEqual([["transfer", "Transfer bank"], ["cash", "Tunai"], ["giro", "Giro / cek"]]);
  expect(q("ar-receipt-cash-hint").textContent).toBe("Transfer bank → masuk Kas Besar (bank).");
});

test("form rekening baru: atas nama, peruntukan, cara bayar & bawaan terkirim; tampil di dokumen mati beralasan", async () => {
  routeGet({ "/payment-methods": (cfg) => (cfg?.params?.direction === "masuk" ? MASUK : SEMUA) });
  mockPost.mockResolvedValue({ status: 200, data: { id: "bank_1" } });
  const onSaved = jest.fn();
  await mount(<BankAccountForm open entityId="ent_ksc" entityLabel="Sukacita" onClose={() => {}} onSaved={onSaved} />);
  expect(q("bank-form-show-docs").disabled).toBe(true);
  expect(q("bank-form-show-docs-reason").textContent).toBe("Isi atas nama dan nomor rekening lebih dulu.");
  expect([...document.body.querySelectorAll("[data-testid^='bank-form-method-']")].map((e) => e.dataset.testid))
    .toEqual(["bank-form-method-transfer", "bank-form-method-giro", "bank-form-method-qris"]);   // kas & titipan tidak
  await type(q("bank-form-name"), "BCA Penerimaan");
  await type(q("bank-form-accountno"), "1234567");
  await type(q("bank-form-holder"), "PT Kain Suka Cita");
  expect(q("bank-form-show-docs").disabled).toBe(false);
  await click(q("bank-form-show-docs"));
  await click(q("bank-form-purpose-gaji"));                    // lepas "Gaji"
  await click(q("bank-form-method-giro"));                     // lepas giro
  await click(q("bank-form-default-transfer"));                // bawaan transfer
  await click(q("bank-form-submit"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  const [url, body, cfg] = mockPost.mock.calls[0];
  expect(url).toBe("/api/bank-accounts");
  expect(body).toMatchObject({ name: "BCA Penerimaan", account_type: "bank", holder_name: "PT Kain Suka Cita",
    account_number: "1234567", purposes: ["penerimaan_pelanggan", "pembayaran_pemasok", "operasional"],
    payment_method_codes: ["transfer", "qris"], default_receiving_methods: ["transfer"], show_on_documents: true });
  expect(cfg.headers["Idempotency-Key"]).toBeTruthy();
  expect(onSaved).toHaveBeenCalledWith({ pending: false, data: { id: "bank_1" } });
});

test("ubah rekening: hanya isian yang berubah; 202 → pengajuan (onSaved pending)", async () => {
  routeGet({ "/payment-methods": (cfg) => (cfg?.params?.direction === "masuk" ? MASUK : SEMUA) });
  mockPatch.mockResolvedValue({ status: 202, data: { change: { id: "bac_1", status: "menunggu" } } });
  const onSaved = jest.fn();
  const acc = { id: "bank_9", entity_id: "ent_ksc", name: "BCA", account_type: "bank", bank_name: "BCA",
    account_number: "111", holder_name: "PT A", purposes: ["penerimaan_pelanggan", "pembayaran_pemasok", "gaji", "operasional"],
    payment_method_codes: ["transfer"], default_receiving_methods: [], show_on_documents: false, is_active: true };
  await mount(<BankAccountForm open account={acc} onClose={() => {}} onSaved={onSaved} />);
  await type(q("bank-form-accountno"), "222");
  await click(q("bank-form-submit"));
  const [url, body] = mockPatch.mock.calls[0];
  expect(url).toBe("/api/bank-accounts/bank_9");
  expect(body).toEqual({ account_number: "222" });
  expect(onSaved).toHaveBeenCalledWith({ pending: true, data: { change: { id: "bac_1", status: "menunggu" } } });
});

const CH = (over = {}) => ({ id: "bac_1", action: "ubah", account_name: "BCA Operasional", entity_name: "Sukacita",
  requested_by: "Rina", created_at: "2026-11-14T03:00:00Z", status: "menunggu", blocked_reason: "",
  label_changes: [{ field: "account_number", label: "Nomor rekening", from: "111", to: "222" },
    { field: "default_receiving_methods", label: "Bawaan penerimaan", from: [], to: ["transfer"] }], ...over });

test("perubahan menunggu: lama → baru, konfirmasi menyebut rekening & PT, Setujui mengirim keputusan", async () => {
  routeGet({ "/bank-account-changes": { items: [CH()], total: 1 }, "/payment-methods": SEMUA });
  mockPost.mockResolvedValue({ data: {} });
  const onDecided = jest.fn();
  await mount(<BankAccountChangesPanel entityParam="ent_ksc" canApprove onDecided={onDecided} />);
  expect(mockGet).toHaveBeenCalledWith("/api/bank-account-changes",
    { params: { status: "menunggu", page: 1, page_size: 50, entity_id: "ent_ksc" } });
  expect(q("bank-changes-count").textContent).toBe("1 menunggu");
  expect(q("bank-change-lines-bac_1").textContent).toBe("Nomor rekening: 111 → 222Bawaan penerimaan: — → Transfer bank");
  await click(q("bank-change-approve-bac_1"));
  const msg = q("bank-change-approve-confirm-message").textContent;
  expect(msg).toContain("BCA Operasional");
  expect(msg).toContain("Sukacita");
  expect(msg).toContain("111 → 222");
  await click(q("bank-change-approve-confirm-confirm"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  const [url, body, cfg] = mockPost.mock.calls[0];
  expect(url).toBe("/api/bank-account-changes/bac_1/decision");
  expect(body).toEqual({ decision: "approve", note: "" });
  expect(cfg.headers["Idempotency-Key"]).toBeTruthy();
  expect(onDecided).toHaveBeenCalled();
});

test("perubahan menunggu: pengaju sendiri → tombol mati + alasan tertulis; tanpa izin → keterangan; kosong → tidak tampil", async () => {
  routeGet({ "/bank-account-changes": { items: [CH({ blocked_reason: "Ubah rekening kas/bank harus diputuskan orang lain" })], total: 1 },
    "/payment-methods": SEMUA });
  await mount(<BankAccountChangesPanel canApprove />);
  expect(q("bank-change-approve-bac_1").disabled).toBe(true);
  expect(q("bank-change-reject-bac_1").disabled).toBe(true);
  expect(q("bank-change-blocked-bac_1").textContent).toBe("Anda yang mengajukan — rekan lain yang memutus.");
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  document.body.innerHTML = "";
  await mount(<BankAccountChangesPanel canApprove={false} />);
  expect(q("bank-change-approve-bac_1")).toBeNull();
  expect(q("bank-changes-readonly")).not.toBeNull();
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  document.body.innerHTML = "";
  routeGet({ "/bank-account-changes": { items: [], total: 0 } });
  await mount(<BankAccountChangesPanel canApprove />);
  expect(q("bank-changes")).toBeNull();
});
