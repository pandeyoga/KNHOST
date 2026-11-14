// PM-T2 — cara bayar & rekening tujuan di checkout, kartu "Instruksi Pembayaran" di detail pesanan, dua isian override.
// Uji komponen (U16 bagian layar; uji jalan peramban terpisah): pilihan cara bayar dari daftar induk (PM-T1) dengan
// "Belum ditentukan" kecuali diwajibkan; rekening dari GET /bank-accounts/receiving PT pesanan, terisi bawaan, terkunci
// bila satu (dengan alasan tertulis), tersembunyi untuk tunai, kalimat kosong bila tidak ada; tombol "Salin instruksi
// bayar" menyalin teks blok + pemberitahuan; kalimat sebab bila belum ada kode.
import React, { act, useState } from "react";
import { createRoot } from "react-dom/client";

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
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/KNDatePicker", () => ({ __esModule: true, default: () => <input data-testid="tgl" /> }));

import CheckoutPaymentDestination, { PESAN_REKENING_KOSONG } from "../pos/CheckoutPaymentDestination";
import OrderPaymentInstructionCard, { PESAN_DISALIN } from "../orders/OrderPaymentInstructionCard";
import SalesOrderOverrideDialog from "../orders/SalesOrderOverrideDialog";
import { invalidatePaymentMethods } from "../../config/paymentMethods";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const M = (code, name, need = "bank") => ({ code, name, needs_account: need, needs_reference: need === "bank", needs_due_date: false });
const MASUK = [M("transfer", "Transfer bank"), M("cash", "Tunai", "kas"), M("giro", "Giro / cek"),
  M("deposit", "Titipan / saldo kredit", "tidak")];
const A = { id: "bank_a", name: "BCA Penerimaan", bank_name: "BCA", account_number: "123-456-7890",
  holder_name: "PT Kain Suka Cita", is_default: true };
const D = { id: "bank_d", name: "Mandiri Penerimaan", bank_name: "Mandiri", account_number: "140-00-7777",
  holder_name: "PT Kain Suka Cita", is_default: false };

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 8) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(el); });
  await flush();
  return host;
}
async function pilih(el, value) {
  await act(async () => { el.value = value; el.dispatchEvent(new Event("change", { bubbles: true })); });
  await flush();
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
function routeGet(map) {
  mockGet.mockImplementation((url, cfg) => {
    const key = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.includes(k));
    const v = key ? map[key] : [];
    if (v instanceof Error) return Promise.reject(v);
    return Promise.resolve({ data: typeof v === "function" ? v(cfg) : v });
  });
}

function Harness({ required = false, onSpy }) {
  const [v, setV] = useState({ method: "", account: "" });
  return (
    <>
      <CheckoutPaymentDestination entityId="ent_ksc" value={v} required={required}
        onChange={(n) => { setV(n); onSpy && onSpy(n); }} />
      <output data-testid="nilai">{JSON.stringify(v)}</output>
    </>
  );
}

beforeEach(() => { mockGet.mockReset(); mockPost.mockReset(); invalidatePaymentMethods(); });
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  document.body.innerHTML = "";
});

describe("PM-T2 checkout — cara bayar & rekening tujuan", () => {
  test("pilihan dari daftar induk + 'Belum ditentukan'; transfer → rekening bawaan PT pesanan terisi otomatis", async () => {
    const minta = [];
    routeGet({ "/payment-methods": MASUK, "/bank-accounts/receiving": (cfg) => { minta.push(cfg.params); return [A, D]; } });
    await mount(<Harness />);
    const opsi = [...q("payment-method-select").options].map((o) => o.textContent);
    expect(opsi).toEqual(["Belum ditentukan", "Transfer bank", "Tunai", "Giro / cek", "Titipan / saldo kredit"]);
    expect(q("receiving-account-field")).toBeNull();
    await pilih(q("payment-method-select"), "transfer");
    expect(minta[0]).toEqual({ method: "transfer", entity_id: "ent_ksc" });
    expect(JSON.parse(q("nilai").textContent)).toEqual({ method: "transfer", account: "bank_a" });
    const rek = [...q("receiving-account-select").options].map((o) => o.textContent);
    expect(rek).toEqual(["BCA 123-456-7890 a.n. PT Kain Suka Cita", "Mandiri 140-00-7777 a.n. PT Kain Suka Cita"]);
    expect(q("receiving-account-select").disabled).toBe(false);
    await pilih(q("receiving-account-select"), "bank_d");
    expect(JSON.parse(q("nilai").textContent).account).toBe("bank_d");
    // tunai → rekening bank tersembunyi dan dikosongkan
    await pilih(q("payment-method-select"), "cash");
    expect(q("receiving-account-field")).toBeNull();
    expect(JSON.parse(q("nilai").textContent)).toEqual({ method: "cash", account: "" });
  });

  test("satu rekening → terkunci dengan alasan tertulis; tidak ada rekening → kalimat untuk Finance", async () => {
    routeGet({ "/payment-methods": MASUK, "/bank-accounts/receiving": (cfg) => (cfg.params.method === "giro" ? [] : [A]) });
    await mount(<Harness />);
    await pilih(q("payment-method-select"), "transfer");
    expect(q("receiving-account-select").disabled).toBe(true);
    expect(q("receiving-account-locked").textContent).toContain("Satu-satunya rekening penerimaan");
    await pilih(q("payment-method-select"), "giro");
    expect(q("receiving-account-select")).toBeNull();
    expect(q("receiving-account-empty").textContent).toContain(PESAN_REKENING_KOSONG);
    expect(JSON.parse(q("nilai").textContent)).toEqual({ method: "giro", account: "" });
  });

  test("diwajibkan PT → tanpa 'Belum ditentukan' + petunjuk tertulis", async () => {
    routeGet({ "/payment-methods": MASUK, "/bank-accounts/receiving": [A] });
    await mount(<Harness required />);
    const opsi = [...q("payment-method-select").options].map((o) => o.value);
    expect(opsi).not.toContain("");
    expect(q("payment-method-required").textContent).toContain("mewajibkan cara bayar");
  });
});

const INSTRUKSI = {
  order_number: "KSC/SO-00003", method_name: "Transfer bank",
  account: { bank_name: "BCA", account_number: "123-456-7890", holder_name: "PT Kain Suka Cita" },
  items: [{ label: "Pembayaran sebelum kirim", amount: 2000000, due_date: "", due_label: "sebelum barang dikirim",
    pay_code: "KN-7F3K2" }],
  text: "Pembayaran untuk pesanan KSC/SO-00003\nJumlah        : Rp 2.000.000\nJatuh tempo   : sebelum barang dikirim\n"
    + "Transfer ke   : BCA 123-456-7890 a.n. PT Kain Suka Cita\nBerita/kode   : KN-7F3K2",
  note: "",
};
const ORDER = { id: "so_1", number: "KSC/SO-00003", entity_id: "ent_ksc", status: "confirmed",
  payment_method_code: "transfer", receiving_account_id: "bank_a",
  receiving_account: { bank_name: "BCA", account_number: "123-456-7890", holder_name: "PT Kain Suka Cita" } };

describe("PM-T2 detail pesanan — kartu Instruksi Pembayaran", () => {
  test("baris cara bayar & rekening; blok berkode; Salin instruksi bayar menyalin teks + pemberitahuan", async () => {
    routeGet({ "/payment-methods": MASUK, "/payment-instruction": INSTRUKSI });
    const tulis = jest.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "clipboard", { value: { writeText: tulis }, configurable: true });
    await mount(<OrderPaymentInstructionCard order={ORDER} />);
    expect(q("order-payment-method").textContent).toBe("Transfer bank");
    expect(q("order-receiving-account").textContent).toBe("BCA 123-456-7890 a.n. PT Kain Suka Cita");
    expect(q("order-pay-code-KN-7F3K2").textContent).toBe("KN-7F3K2");
    expect(q("order-payment-instruction-items").textContent).toContain("sebelum barang dikirim");
    await click(q("copy-payment-instruction"));
    expect(tulis).toHaveBeenCalledWith(INSTRUKSI.text);
    expect(q("copy-payment-instruction-flash").textContent).toContain(PESAN_DISALIN);
  });

  test("belum ada kode → kalimat sebab dari server, tanpa tombol salin", async () => {
    routeGet({ "/payment-methods": MASUK, "/payment-instruction": { ...INSTRUKSI, items: [], text: "",
      note: "Instruksi bayar tersedia setelah pesanan dikonfirmasi." } });
    await mount(<OrderPaymentInstructionCard order={{ ...ORDER, status: "reserved", payment_method_code: "" }} />);
    expect(q("order-payment-method").textContent).toBe("Belum ditentukan");
    expect(q("order-payment-instruction-note").textContent).toContain("setelah pesanan dikonfirmasi");
    expect(q("copy-payment-instruction")).toBeNull();
  });
});

describe("PM-T2 override pesanan — dua isian yang sama", () => {
  test("cara bayar dari konteks override; ganti cara bayar → rekening bawaan; dikirim di header", async () => {
    routeGet({
      "/override-context": { locked_reason: "", addresses: [], can_loosen_term: true, current_term: null,
        payment_methods: MASUK, receiving_accounts: { transfer: [A, D], giro: [], cash: [] } },
      "/payment-terms": [],
    });
    mockPost.mockResolvedValue({ data: { changes: [{}], price_amendment: null } });
    const selesai = jest.fn();
    await mount(<SalesOrderOverrideDialog order={{ ...ORDER, payment_method_code: "", receiving_account_id: "" }}
      onClose={() => {}} onDone={selesai} />);
    expect(q("override-account-none").textContent).toContain("Pilih cara bayar dulu");
    await pilih(q("override-payment-method"), "transfer");
    expect(q("override-receiving-account").value).toBe("bank_a");
    await pilih(q("override-receiving-account"), "bank_d");
    await pilih(q("override-payment-method"), "giro");
    expect(q("override-account-empty").textContent).toContain(PESAN_REKENING_KOSONG);
    await pilih(q("override-payment-method"), "transfer");
    const alasan = q("override-reason");
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
    await act(async () => { setter.call(alasan, "ganti rekening tujuan"); alasan.dispatchEvent(new Event("input", { bubbles: true })); });
    await flush();
    await click(q("so-override-submit"));
    expect(mockPost).toHaveBeenCalledWith("/api/sales-orders/so_1/override", expect.objectContaining({
      header: expect.objectContaining({ payment_method_code: "transfer", receiving_account_id: "bank_a" }) }));
  });
});
