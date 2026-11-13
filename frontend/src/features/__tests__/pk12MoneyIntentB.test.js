// PK-12 (kelompok B: Tagihan Pemasok, Kontrabon) — kunci idempotensi form uang di layar.
//  · U14: wizard kontrabon — langkah 2 putus jaringan, rantai diulang → langkah 1 dikirim ulang dengan Idempotency-Key
//    yang SAMA, server tiruan memutar ulang jawabannya, sehingga kontrabon hanya terbit SATU.
//  · Aksi alur Tagihan Pemasok (Setujui & Posting) mengirim Idempotency-Key dan tombolnya mati selama menunggu
//    (sesudah dialog konfirmasi PK-13 dijawab "lanjut").
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ContraBonCreateWizard from "../purchasing/contrabon/ContraBonCreateWizard";
import VendorBillDetailPanel from "../purchasing/VendorBillDetailPanel";
import { askConfirm } from "../../services/confirmService";

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
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: jest.fn(async () => true),
  askReason: jest.fn(async () => null),
  askText: jest.fn(async () => null),
  askChoice: jest.fn(async () => null),
  default: {},
}));
// Pemilih bawaan (cmdk/radix) diganti elemen polos — yang diuji di sini logika kirim, bukan komponen pilihannya.
jest.mock("../../components/KNSelect", () => {
  const S = (p) => <select data-testid={p["data-testid"]} value={p.value} onChange={() => {}} />;
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/KNDatePicker", () => (p) => (
  <input data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />));
jest.mock("../../components/AskKnButton", () => ({ __esModule: true, AskKnButton: () => null }));
jest.mock("../documents/DocumentActionsBar", () => () => null);
jest.mock("../documents/trace/DocRefsPanel", () => () => null);
jest.mock("../purchasing/GrnDocVariance", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function settle() { await act(async () => {}); await act(async () => {}); await act(async () => {}); }
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await settle();
  return { host, root };
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
}
const keyOf = (call) => call?.[2]?.headers?.["Idempotency-Key"];

afterEach(() => {
  mockGet.mockReset(); mockPost.mockReset();
  document.body.innerHTML = "";
});

const PREP = {
  entity_id: "ent_ksc",
  supplier: { name: "Solo Weave", invoice_exchange: { mode: "none" } },
  bills: [{ bill_id: "b1", bill_number: "INV-1", po_number: "PO-1", outstanding: 1000, due_date: "2026-12-01" }],
  bills_total: 1000,
  credits: { purchase_returns: [{ ref_id: "pr1", ref_number: "RB-1", kind: "purchase_return", label: "Retur RB-1",
    amount: 200 }], supplier_advances: [] },
  credits_total: 200,
  suggested: { cycle_date: "2026-11-13", due_date: "2026-12-13", term_days: 30 },
};

test("U14 — wizard kontrabon: langkah 2 putus jaringan, ulangi → langkah 1 memakai kunci sama, kontrabon terbit sekali", async () => {
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/contra-bons/prepare") ? PREP : [] }));
  // Server tiruan ber-idempotensi: kunci + jalur yang pernah dijawab → jawaban pertama diputar ulang.
  const replay = new Map();
  const created = [];
  let dedDropped = false;
  mockPost.mockImplementation(async (url, body, config) => {
    const key = config?.headers?.["Idempotency-Key"];
    const slot = key ? `${key}|${url}` : "";
    if (slot && replay.has(slot)) return replay.get(slot);
    let res;
    if (url === "/api/contra-bons") {
      created.push(body);
      const n = created.length;
      res = { data: { id: `cb${n}`, number: `KSC/CB-0000${n}`, bills: body.bills, deductions: [] } };
    } else if (url.endsWith("/deductions")) {
      if (!dedDropped) { dedDropped = true; throw new Error("Network Error"); }   // tanpa `response`
      const id = url.split("/")[3];
      res = { data: { id, number: `KSC/CB-0000${id.slice(2)}`, bills: [], deductions: [{ ref_id: body.ref_id }] } };
    } else {
      res = { data: {} };
    }
    if (slot) replay.set(slot, res);
    return res;
  });
  const onCreated = jest.fn();
  const { host } = await mount(<ContraBonCreateWizard suppliers={[{ id: "s1", name: "Solo Weave" }]}
    presetSupplierId="s1" selectedEntity="ent_ksc" onClose={() => {}} onCreated={onCreated} onError={() => {}} />);

  await click(q(host, "cb-create-cred-pr1"));     // potongan retur dipilih → langkah 2 ikut berjalan
  await click(q(host, "cb-create-next"));
  await click(q(host, "cb-create-submit"));        // percobaan 1: langkah 1 sukses, langkah 2 putus

  const cbCalls = () => mockPost.mock.calls.filter(([u]) => u === "/api/contra-bons");
  const dedCalls = () => mockPost.mock.calls.filter(([u]) => u.endsWith("/deductions"));
  expect(cbCalls()).toHaveLength(1);
  expect(onCreated).not.toHaveBeenCalled();
  expect(q(host, "cb-create-error")).not.toBeNull();

  await click(q(host, "cb-create-submit"));        // percobaan 2: rantai diulang
  expect(cbCalls()).toHaveLength(2);
  const [k1, k2] = cbCalls().map(keyOf);
  expect(typeof k1).toBe("string");
  expect(k1.length).toBeGreaterThan(0);
  expect(k2).toBe(k1);                             // kunci langkah 1 SAMA
  expect(created).toHaveLength(1);                 // server memutar ulang → kontrabon terbit sekali
  const [d1, d2] = dedCalls().map(keyOf);
  expect(typeof d1).toBe("string");
  expect(d2).toBe(d1);                             // langkah 2 juga memakai kunci yang sama
  expect(onCreated).toHaveBeenCalledTimes(1);
  expect(onCreated.mock.calls[0][0].id).toBe("cb1");
  expect(onCreated.mock.calls[0][1]).toEqual([]);
});

test("Tagihan Pemasok — Setujui & Posting mengirim Idempotency-Key; tombol mati selama menunggu, klik kedua tidak mengirim", async () => {
  mockGet.mockResolvedValue({ data: [] });
  let release;
  mockPost.mockImplementation(() => new Promise((res) => {
    release = () => res({ data: { id: "vb1", bill_number: "VB-1", status: "posted" } });
  }));
  const onAction = jest.fn();
  const bill = { id: "vb1", bill_number: "VB-1", status: "pending_approval", match_status: "matched",
    supplier_name: "Solo Weave", po_number: "PO-1", items: [], timeline: [], payments: [],
    financials: { grand_total: 1000, outstanding: 1000, amount_paid: 0 } };
  const { host } = await mount(<VendorBillDetailPanel bill={bill} canApprove currentUser={{ permissions: {} }}
    onClose={() => {}} onAction={onAction} onError={() => {}} />);

  // PK-13 — Setujui & Posting kini bertanya dulu (dialog `vb-approve-confirm`); di sini dijawab "lanjut".
  askConfirm.mockResolvedValue(true);
  const btn = q(host, "vb-action-approve");
  await click(btn);
  expect(askConfirm).toHaveBeenCalledTimes(1);
  expect(askConfirm.mock.calls[0][0]).toEqual(expect.objectContaining({ testId: "vb-approve-confirm" }));
  expect(mockPost).toHaveBeenCalledTimes(1);
  expect(mockPost.mock.calls[0][0]).toBe("/api/vendor-bills/vb1/approve");
  expect(typeof keyOf(mockPost.mock.calls[0])).toBe("string");
  expect(keyOf(mockPost.mock.calls[0]).length).toBeGreaterThan(0);
  expect(q(host, "vb-action-approve").disabled).toBe(true);
  expect(q(host, "vb-action-reject").disabled).toBe(true);
  await click(q(host, "vb-action-approve"));       // klik kedua saat sibuk
  expect(mockPost).toHaveBeenCalledTimes(1);

  await act(async () => { release(); });
  await settle();
  expect(onAction).toHaveBeenCalledWith("approve", expect.objectContaining({ id: "vb1" }));
});
