// PK-12 (kelompok C) — form uang antar-PT, rencana bayar/denda/selisih, dan kasus keuangan mengirim header
// `Idempotency-Key` lewat `utils/moneyRequest.js`: klik ganda = satu panggilan, kirim ulang sesudah koneksi putus memakai
// kunci yang sama, aksi berantai memegang kunci langkah pertama sampai seluruh rantai selesai.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import IntercoCreateModal from "../finance/interco/IntercoCreateModal";
import IntercoReturnModal from "../finance/interco/IntercoReturnModal";
import CaseCreateModal from "../finance/cases/CaseCreateModal";
import { createPlan, decideVariance, issuePenalty, updatePlan } from "../finance/payments/paymentApi";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockPatch = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: (...a) => mockPatch(...a),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: jest.fn(async () => true),
  askReason: jest.fn(async () => null),
  askText: jest.fn(async () => null),
  askChoice: jest.fn(async () => null),
  default: {},
}));
// Pemilih bawaan (cmdk/radix) diganti <select> polos yang meneruskan pilihan — yang diuji logika kirim, bukan pemilihnya.
jest.mock("../../components/KNSelect", () => {
  const Sel = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange?.(e.target.value)}>
      <option value="">-</option>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: Sel, KNSelect: Sel };
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  await act(async () => {});
  return { host, root };
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await act(async () => {});
  await act(async () => {});
}
async function choose(sel, value) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(sel, value);
    sel.dispatchEvent(new Event("change", { bubbles: true }));
  });
}
async function type(el, value) {
  await act(async () => {
    const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
}
const keyOf = (call) => call?.[2]?.headers?.["Idempotency-Key"];
const netErr = () => Object.assign(new Error("Network Error"), { code: "ERR_NETWORK" });   // tanpa `response`

afterEach(() => {
  mockGet.mockReset(); mockPost.mockReset(); mockPatch.mockReset();
  document.body.innerHTML = "";
});

test("Antar-PT baru: header Idempotency-Key terkirim, tombol mati selama menunggu, klik ganda = 1 panggilan", async () => {
  mockGet.mockImplementation(() => Promise.resolve({ data: [{ id: "P1", sku: "K-01", name: "Katun" }] }));
  let release;
  mockPost.mockImplementation(() => new Promise((res) => { release = res; }));
  const onCreated = jest.fn();
  const ents = [{ id: "ent_a", short_name: "Sukacita" }, { id: "ent_b", short_name: "Cipta" }];
  const { host } = await mount(<IntercoCreateModal entities={ents} currentEntityId="ent_a" onClose={() => {}}
    onCreated={onCreated} />);
  await choose(q(host, "interco-create-buyer"), "ent_b");
  await choose(q(host, "interco-create-line-0").querySelector("select"), "P1");
  const btn = q(host, "interco-create-submit");
  expect(btn.disabled).toBe(false);

  await click(btn);
  expect(btn.disabled).toBe(true);                       // sibuk selama jawaban belum datang
  expect(q(host, "interco-create-cancel").disabled).toBe(true);
  await click(btn);                                       // klik kedua saat sibuk
  expect(mockPost).toHaveBeenCalledTimes(1);
  const [url, body, cfg] = mockPost.mock.calls[0];
  expect(url).toBe("/api/interco/transactions");
  expect(body).toMatchObject({ seller_entity_id: "ent_a", buyer_entity_id: "ent_b", items: [{ product_id: "P1", quantity: 1 }] });
  expect(cfg.headers["Idempotency-Key"]).toMatch(/^ic-trx-/);

  await act(async () => { release({ data: { id: "ic1" } }); });
  await act(async () => {});
  expect(onCreated).toHaveBeenCalledTimes(1);
  expect(mockPost).toHaveBeenCalledTimes(1);
});

test("paymentApi: fungsi tulis meneruskan argumen akhir `key` sebagai header Idempotency-Key", async () => {
  mockPost.mockResolvedValue({ data: { id: "x" } });
  mockPatch.mockResolvedValue({ data: { id: "pl1" } });
  const hdr = (k) => expect.objectContaining({ headers: expect.objectContaining({ "Idempotency-Key": k }) });

  await createPlan({ doc_type: "sales_order", doc_id: "so1", mode: "net", lines: [] }, "k-plan-1");
  expect(mockPost).toHaveBeenLastCalledWith("/api/payment-plans",
    { doc_type: "sales_order", doc_id: "so1", mode: "net", lines: [] }, hdr("k-plan-1"));

  await updatePlan("pl1", { mode: "net", lines: [] }, "k-plan-2");
  expect(mockPatch).toHaveBeenLastCalledWith("/api/payment-plans/pl1", { mode: "net", lines: [] }, hdr("k-plan-2"));

  await issuePenalty("pn1", "k-pen-1");
  expect(mockPost).toHaveBeenLastCalledWith("/api/penalties/pn1/issue", null, hdr("k-pen-1"));

  await decideVariance("rc1", { kind: "writeoff", reason_code: "bank_charge" }, "k-pv-1");
  expect(mockPost).toHaveBeenLastCalledWith("/api/payment-variances/receipt/rc1/decide",
    { kind: "writeoff", reason_code: "bank_charge" }, hdr("k-pv-1"));
});

test("Kasus baru: kirim ulang sesudah gagal jaringan memakai kunci SAMA; sesudah jawaban 400 kunci BARU", async () => {
  mockPost
    .mockRejectedValueOnce(netErr())
    .mockRejectedValueOnce({ response: { status: 400, data: { detail: "Kasus kembar" } } })
    .mockResolvedValueOnce({ data: { id: "fc1" } });
  const onCreated = jest.fn();
  const { host } = await mount(<CaseCreateModal playbooks={[{ code: "double_payment", label: "Bayar ganda", question: "?" }]}
    customers={[]} suppliers={[]} onClose={() => {}} onCreated={onCreated} />);
  await type(q(host, "case-create-desc"), "Transfer dobel");
  const btn = q(host, "case-create-submit");

  await click(btn);                                       // 1) koneksi putus
  expect(q(host, "case-create-error")).not.toBeNull();
  await click(btn);                                       // 2) kirim ulang, isi sama → server menjawab 400
  await click(btn);                                       // 3) coba lagi sesudah 400 → kunci baru
  expect(mockPost).toHaveBeenCalledTimes(3);
  const [k1, k2, k3] = mockPost.mock.calls.map(keyOf);
  expect(k1).toMatch(/^fc-baru-/);
  expect(k2).toBe(k1);                                    // kirim ulang sesudah gagal jaringan: kunci sama
  expect(k3).not.toBe(k2);                                // sesudah 4xx: kunci baru
  expect(mockPost.mock.calls[1][1]).toEqual(mockPost.mock.calls[0][1]);
  expect(onCreated).toHaveBeenCalledWith({ id: "fc1" });
});

test("Retur antar-PT (berantai): unggah foto gagal jaringan → ulangi memutar ulang retur dengan kunci sama", async () => {
  mockGet.mockImplementation(() => Promise.resolve({ data: {
    can_return: true, origin_number: "IC-1", tax_apply: false,
    lines: [{ product_id: "P1", product_name: "Katun", sku: "K-01", unit: "yard", unit_price: 1000, qty_total: 10,
      qty_returned: 0, qty_returnable: 10, rolls: [{ roll_id: "R1", roll_no: "RL-1", lot: "L1", qty: 5, unit: "yard" }] }],
  } }));
  const created = { returner: { id: "RET1", number: "RT-1" } };
  mockPost
    .mockResolvedValueOnce({ data: created })            // langkah 1: dokumen retur
    .mockRejectedValueOnce(netErr())                     // langkah 2: foto — koneksi putus
    .mockResolvedValueOnce({ data: created })            // ulangi langkah 1 (server memutar ulang)
    .mockResolvedValueOnce({ data: { id: "att1" } });   // ulangi langkah 2
  const onCreated = jest.fn();
  const { host } = await mount(<IntercoReturnModal doc={{ id: "ic1", number: "IC-1" }} onClose={() => {}}
    onCreated={onCreated} />);
  await click(q(host, "interco-return-roll-R1").querySelector("input"));
  const rt = "interco-return-claims-P1-roll-R1";
  await type(q(host, `${rt}-reason`), "noda kain");
  const photo = q(host, `${rt}-photo-input`);
  const file = new File(["x"], "bukti.jpg", { type: "image/jpeg" });
  await act(async () => {
    Object.defineProperty(photo, "files", { value: [file], configurable: true });
    photo.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await type(q(host, "interco-return-reason"), "warna tidak sesuai");
  const submit = q(host, "interco-return-submit");

  await click(submit);                                   // rantai 1: retur dibuat, foto gagal
  expect(mockPost).toHaveBeenCalledTimes(2);
  expect(onCreated).not.toHaveBeenCalled();
  await click(submit);                                   // rantai 2: ulangi
  expect(mockPost).toHaveBeenCalledTimes(4);
  const urls = mockPost.mock.calls.map((c) => c[0]);
  expect(urls).toEqual(["/api/interco/returns", "/api/interco/returns/RET1/attachments",
    "/api/interco/returns", "/api/interco/returns/RET1/attachments"]);
  const k1 = keyOf(mockPost.mock.calls[0]);
  expect(k1).toMatch(/^icr-/);
  expect(keyOf(mockPost.mock.calls[2])).toBe(k1);       // retur yang sama, bukan retur kedua
  expect(keyOf(mockPost.mock.calls[1])).toBeUndefined(); // multipart tanpa kunci (batas acak per kirim)
  expect(onCreated).toHaveBeenCalledWith(created);
});
