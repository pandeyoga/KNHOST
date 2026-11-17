// S3 (pelatihan keuangan 18 Nov) — kasus "Pengembalian dana ke pelanggan" (uang muka pesanan batal dikembalikan).
// Aksi yang memindahkan uang lewat rekening (`needs` memuat `account_id`) kini punya isian "Rekening kas/bank". Dulu tidak
// ada: server memakai rekening tunggal PT, sehingga PT dengan lebih dari satu rekening (mis. BCA + Kas Toko, atau
// rekening latihan K04 yang masih aktif) ditolak "Pilih rekening kas/bank" tanpa cara memilihnya.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CasePlaybookWizard from "../finance/cases/CasePlaybookWizard";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../../utils/moneyRequest", () => ({ moneyPost: (...a) => mockPost(...a) }));
jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid }) => (
    <select data-testid={tid} value={value ?? ""} onChange={(e) => onValueChange(e.target.value)}>
      <option value="" />
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: M, KNSelect: M };
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function settle() { for (let i = 0; i < 6; i += 1) await act(async () => {}); }
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => { createRoot(host).render(el); });
  await settle();
}
async function pilih(el, v) {
  await act(async () => { el.value = v; el.dispatchEvent(new Event("change", { bubbles: true })); });
  await settle();
}

const KASUS = {
  id: "fcs_1", number: "KSC/CASE-00001", entity_id: "ent_ksc", customer_id: "c1", amount: 1313796,
  case_type: "refund_pelanggan", case_type_label: "Pengembalian dana ke pelanggan", reason_codes: ["customer_refund_request"],
  playbook: [], actions: [
    { code: "refund_pelanggan", label: "Kembalikan dari uang muka pelanggan", effect: "Kas keluar", produces: "Kas keluar",
      needs: ["customer_id", "amount", "account_id"], sensitive: true },
  ],
};
const REK = [
  { id: "bank_bca", name: "BCA Operasional KSC", entity_id: "ent_ksc" },
  { id: "bank_toko", name: "Kas Toko KSC", entity_id: "ent_ksc" },
  { id: "bank_lama", name: "Rekening Latihan 05", entity_id: "ent_ksc", is_active: false },
  { id: "bank_lain", name: "BCA Kanda", entity_id: "ent_kanda" },
];
const props = { reasons: [{ code: "customer_refund_request", label: "Pelanggan minta uang kembali" }], entities: [],
  customers: [{ id: "c1", name: "Latihan 75" }], suppliers: [], policy: {}, onClose() {}, onError() {} };

beforeEach(() => {
  mockGet.mockImplementation(() => Promise.resolve({ data: [] }));
  mockPost.mockImplementation(() => Promise.resolve({ data: { status: "resolved" } }));
});
afterEach(() => { document.body.innerHTML = ""; });

test("dua rekening PT: isian rekening tampil (tanpa rekening nonaktif & PT lain), wajib dipilih, terkirim sebagai account_id", async () => {
  const onDone = jest.fn();
  await mount(<CasePlaybookWizard caseData={KASUS} accounts={REK} onDone={onDone} {...props} />);
  const sel = q("case-field-account");
  expect(sel).not.toBeNull();
  expect([...sel.options].map((o) => o.textContent).filter(Boolean)).toEqual(["BCA Operasional KSC", "Kas Toko KSC"]);
  await pilih(q("case-field-reason"), "customer_refund_request");
  expect(q("case-wizard-missing").textContent).toContain("rekening kas/bank");
  expect(q("case-wizard-submit").disabled).toBe(true);
  await pilih(sel, "bank_bca");
  expect(q("case-wizard-missing").textContent).toBe("Siap diselesaikan");
  await act(async () => { q("case-wizard-submit").dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
  const [url, body] = mockPost.mock.calls.at(-1);
  expect(url).toBe("/api/finance-cases/fcs_1/resolve");
  expect(body.account_id).toBe("bank_bca");
  expect(body.action).toBe("refund_pelanggan");
});

test("satu rekening PT: terisi sendiri dan tidak menghalangi", async () => {
  await mount(<CasePlaybookWizard caseData={KASUS} accounts={[REK[0], REK[3]]} onDone={() => {}} {...props} />);
  expect(q("case-field-account").value).toBe("bank_bca");
  await pilih(q("case-field-reason"), "customer_refund_request");
  expect(q("case-wizard-missing").textContent).toBe("Siap diselesaikan");
});
