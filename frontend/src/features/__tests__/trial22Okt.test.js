// Trial 22 Okt 2026 — perbaikan temuan (docs/uat/2026-10-21/CATATAN_TEMUAN_TRIAL_22OKT.md).
// D2: hitung fisik GRN — panjang boleh diketik dalam satuan SJ/PO atau satuan dasar produk; satuan yang dipilih
//     ikut dikirim (server mengonversi ke satuan dasar). Dulu label "Panjang (meter)" tetapi angka disimpan sebagai yard.
// E8/E10: alur pesanan baru — ringkasan "Sebelum masuk gudang" (normal → diminta + dua total + batas booking),
//     harga ditolak → tiga pilihan sales, dialog Admin Sales "Periksa & lepas ke gudang" (+ tahan dulu).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import GrnCountPanel from "../wms/grn/GrnCountPanel";
import OrderReleaseSummary from "../orders/OrderReleaseSummary";
import SoApprovalsPanel from "../orders/SoApprovalsPanel";
import VerifyOrderDialog from "../sales_admin/VerifyOrderDialog";
import { releaseMessage } from "../sales_admin/workDeskApi";

const posted = [];
jest.mock("../wms/grn/grnApi", () => ({
  grnApi: {
    rolls: () => Promise.resolve([{ id: "r1", roll_no: "RL-1", grn_line_no: 1, length_initial: 109.36, unit: "yard",
      actual_task_qty: 100, lot: "L1", grade: "A", status: "receiving", scan_source: "count" }]),
    post: (...a) => { posted.push(a); return Promise.resolve({ grn: null }); },
    del: () => Promise.resolve({}),
  },
  errText: () => "gagal",
}));   // bukan jest.fn: resetMocks CRA
jest.mock("../../hooks/useDomainEnums", () => () => ({ options: () => [{ value: "A", label: "A" }] }));
const apiCalls = [];
jest.mock("../../services/apiClient", () => ({
  __esModule: true, API: "/api",
  default: {
    defaults: { headers: { common: {} } },
    get: (url) => {
      apiCalls.push(["get", url]);
      return Promise.resolve({ data: { verifiable: true, ready: true, checks: [], blocking_gaps: [], warnings: [],
        order_preview: { customer_name: "Toko Uji", items: [], totals: {} } } });
    },
    post: (url, body) => {
      apiCalls.push(["post", url, body]);
      return Promise.resolve({ data: { order: { number: "SO-UJI", status: "waiting_approval" }, released: false,
        release_state: { waiting: "acc", hold: false } } });
    },
  },
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const tick = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });

async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await tick();
  return root;
}

const grn = (target) => ({ id: "grn1", status: "counting", version: 1, lines: [{ line_no: 1, decision: "accept",
  target: { type: "po_task", po_number: "PO-1", sku: "LRK", product_name: "Lurik", ...target }, counted: { rolls: 1, qty: 100 } }] });

test("D2: hitung GRN — pilihan satuan SJ/PO vs stok, satuan terpilih dikirim, roll tampil dua satuan", async () => {
  posted.length = 0;
  const root = await mount(<GrnCountPanel grn={grn({ unit: "meter", base_unit: "yard" })} onChange={() => {}} canCount />);
  expect(q("grn-count-unit-1")).not.toBeNull();
  expect(q("grn-count-length-1").placeholder).toBe("Panjang (meter)");
  expect(q("grn-count-roll-r1").textContent).toMatch(/109\.36 yard \(= 100 meter\)/);
  const input = q("grn-count-length-1");
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, "100");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => { q("grn-count-add-1").click(); });
  await tick();
  expect(posted[0][1]).toBe("lines/1/rolls");
  expect(posted[0][2]).toMatchObject({ length: 100, length_unit: "meter" });
  act(() => root.unmount());
});

test("D2: satuan SJ = satuan stok → tanpa pemilih satuan", async () => {
  const root = await mount(<GrnCountPanel grn={grn({ unit: "yard", base_unit: "yard" })} onChange={() => {}} canCount />);
  expect(q("grn-count-unit-1")).toBeNull();
  expect(q("grn-count-length-1").placeholder).toBe("Panjang (yard)");
  act(() => root.unmount());
});


const spOrder = (status) => ({
  id: "so1", number: "SO-UJI", status: "waiting_approval", order_type: "regular", customer_id: "c1", customer_name: "Toko Uji",
  total_amount: 60000000, grand_total: 66600000, reservation_expires_at: "2026-10-25T07:00:00+00:00",
  items: [{ product_id: "p1", product_name: "Batik Mega", quantity: 500, unit: "yard", price: 120000 }],
  release: { requested: true, by: "Rina" },
  pending_approvals: [{ id: "a1", type: "special_price", status, product_id: "p1", product_name: "Batik Mega",
    normal_price: 120000, requested_price: 105000, required_role: "manager", decision_notes: status === "rejected" ? "minimal 112.000" : "" }],
});

test("E10: ringkasan — harga normal → diminta, dua total berlabel, batas booking, label menunggu ACC", async () => {
  const root = await mount(<OrderReleaseSummary order={spOrder("pending")} />);
  expect(q("order-release-label").textContent).toBe("Menunggu ACC harga");
  expect(q("order-release-prices").textContent).toMatch(/Normal Rp\s?120\.000 → diminta Rp\s?105\.000/);
  expect(q("order-release-total-normal").textContent).toMatch(/66\.600\.000/);
  // 500 yd × (120.000 − 105.000) = 7,5 jt (sebelum PPN) × rasio grand/total 1,11 = 8.325.000
  expect(q("order-release-total-requested").textContent).toMatch(/58\.275\.000/);
  expect(q("order-release-booking").textContent).toMatch(/Booking stok berakhir/);
  expect(q("order-release-step-review").textContent).toMatch(/Diperiksa Rina/);
  act(() => root.unmount());
});

test("E10: harga ditolak → label pilih langkah + tiga tombol; Lanjut harga normal memanggil API", async () => {
  apiCalls.length = 0;
  const user = { role: "sales", permissions: { order: ["view", "update", "cancel"] } };
  const root = await mount(<SoApprovalsPanel order={spOrder("rejected")} user={user} onRefresh={() => {}} />);
  expect(q("order-release-label").textContent).toBe("Harga ditolak · pilih langkah");
  expect(q("so-appr-ask-again-a1")).not.toBeNull();
  expect(q("so-appr-cancel-order-a1")).not.toBeNull();
  await act(async () => { q("so-appr-keep-normal-a1").click(); });
  await tick();
  expect(apiCalls.some(([m, url]) => m === "post" && url === "/api/sales-orders/so1/approvals/a1/continue-normal-price")).toBe(true);
  act(() => root.unmount());
});

test("E8: dialog Admin Sales — Periksa & lepas, opsi Tahan dulu ikut terkirim", async () => {
  apiCalls.length = 0;
  let msg = "";
  const root = await mount(<VerifyOrderDialog orderId="so1" orderNumber="SO-UJI" customerName="Toko Uji"
    onClose={() => {}} onVerified={(m) => { msg = m; }} />);
  expect(q("verify-submit").textContent).toBe("Periksa & lepas ke gudang");
  await act(async () => { q("verify-hold").querySelector("input").click(); });
  expect(q("verify-submit").textContent).toBe("Periksa & tahan");
  await act(async () => { q("verify-submit").click(); });
  await tick();
  const call = apiCalls.find(([m, url]) => m === "post" && url === "/api/sales-orders/so1/review-release");
  expect(call[2]).toEqual({ note: "", hold: true });
  expect(msg).toMatch(/menunggu ACC Manajer; dilepas ke gudang otomatis sesudah ACC/);
  act(() => root.unmount());
});

test("E8: pesan sesudah periksa sesuai keadaan", () => {
  expect(releaseMessage({ released: true, order: { number: "SO-1", status: "confirmed" } })).toMatch(/dilepas ke gudang/);
  expect(releaseMessage({ order: { number: "SO-1", status: "approved" }, release_state: { hold: true } })).toMatch(/DITAHAN/);
  expect(releaseMessage({ order: { number: "SO-1", status: "waiting_approval" }, release_state: { waiting: "ditolak" } })).toMatch(/DITOLAK/);
});
