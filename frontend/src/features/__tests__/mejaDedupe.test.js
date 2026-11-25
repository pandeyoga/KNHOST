// MEJA-13 — §5.6 hapus ganda, Review Focus #5.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { dedupeFinanceGroups, dedupeTurnQueue } from "../desks/deskDedupe";
import FinanceDesk from "../finance/FinanceDesk";
import RoleDesk from "../desks/RoleDesk";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: jest.fn(), defaults: { headers: { common: {} } } },
  API: "/api",
  setActiveEntity: () => {}, setAuthToken: () => {},
}));
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: jest.fn() }));
jest.mock("../sales_admin/SoTrackerCard", () => () => <div data-testid="so-tracker-stub" />);
jest.mock("../finance/payments/ReceivePaymentModal", () => (p) => <div data-testid="rpm-stub">{p.preselectOrderId}</div>);

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
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
function routeGet(peta) {
  mockGet.mockImplementation((u) => {
    const k = Object.keys(peta).find((x) => u.includes(x));
    return Promise.resolve({ data: k ? peta[k] : [] });
  });
}
afterEach(async () => {
  for (const r of roots) await act(async () => r.unmount());
  roots = []; document.body.innerHTML = ""; mockGet.mockReset(); sessionStorage.clear();
});

const UM = (oid, lewat, extra = {}) => ({ ref_type: "customer", ref_id: "cus1", row_key: oid, order_id: oid, number: oid, title: "Toko A",
  value: 100, age_days: lewat ? 8 : 0, age_kind: lewat ? "overdue" : "wait", badge: lewat ? "lewat" : "segera",
  action: "Terima pembayaran", action_kind: "receipt", _queue: "uang_masuk", ...extra });
const JT = (oid) => ({ ref_type: "sales_order", ref_id: oid, order_id: oid, customer_id: "cus1", number: oid, title: "Toko A",
  value: 100, age_days: 8, age_kind: "overdue", badge: "lewat", action: "Tagih", action_kind: "open", _queue: "jatuh_tempo" });
const G = (id, rows, count = rows.length) => ({ id, label: id, rows, count, total_value: rows.length * 100,
  oldest_age_days: Math.max(0, ...rows.map((r) => r.age_days)) });

test("kedua kartu terlihat: lewat tempo hanya di Piutang, dengan Terima pembayaran; Uang masuk dihitung ulang", () => {
  const out = dedupeFinanceGroups([G("uang_masuk", [UM("so1", true), UM("so2", false)]), G("piutang_lewat_tempo", [JT("so1")])]);
  const um = out.find((g) => g.id === "uang_masuk"); const pt = out.find((g) => g.id === "piutang_lewat_tempo");
  expect(um.rows.map((r) => r.order_id)).toEqual(["so2"]);
  expect([um.count, um.total_value, um.oldest_age_days]).toEqual([1, 100, 0]);
  expect(pt.rows[0]._moreActions).toEqual([{ label: "Terima pembayaran", row: expect.objectContaining({ order_id: "so1", action_kind: "receipt" }) }]);
});

test("masukan tidak diubah", () => {
  const masukan = [G("uang_masuk", [UM("so1", true)]), G("piutang_lewat_tempo", [JT("so1")])];
  const salinan = JSON.stringify(masukan);
  dedupeFinanceGroups(masukan);
  expect(JSON.stringify(masukan)).toBe(salinan);
});

test("kartu Piutang tidak terlihat (tanpa izin): lewat tempo tetap di Uang masuk", () => {
  const masuk = [G("uang_masuk", [UM("so1", true)])];
  expect(dedupeFinanceGroups(masuk)).toEqual(masuk);
});

test("Uang masuk tidak terlihat: Piutang tanpa 'Terima pembayaran'", () => {
  const out = dedupeFinanceGroups([G("piutang_lewat_tempo", [JT("so1")])]);
  expect(out[0].rows[0]._moreActions).toBeUndefined();
});

test("Uang masuk habis → kelompoknya tidak digambar", () => {
  const out = dedupeFinanceGroups([G("uang_masuk", [UM("so1", true)]), G("piutang_lewat_tempo", [JT("so1")])]);
  expect(out.map((g) => g.id)).toEqual(["piutang_lewat_tempo"]);
});

test("Giliran saya tidak mengulang dokumen antrean lain; kartu tetap ada walau kosong", () => {
  const out = dedupeTurnQueue([{ id: "giliran_saya", count: 1, rows: [{ ref_type: "sales_order", ref_id: "so_1" }] },
                               { id: "so_acc", count: 1, rows: [{ ref_type: "sales_order", ref_id: "so_1" }] }]);
  expect(out[0]).toMatchObject({ id: "giliran_saya", count: 0, rows: [] });
});

test("FinanceDesk: pop-up Piutang menawarkan Terima pembayaran → ReceivePaymentModal", async () => {
  const tanpaQueue = ({ _queue, ...r }) => r;   // baris server belum ber-`_queue` (ditambah FinanceDesk)
  routeGet({ "/finance/desk": { queues: [
    { id: "uang_masuk", count: 1, rows: [tanpaQueue(UM("so1", true))] },
    { id: "jatuh_tempo", count: 1, rows: [tanpaQueue(JT("so1"))] }], not_my_desk: [] } });
  await mount(<FinanceDesk currentUser={{ permissions: { payment_variance: ["decide"], ar_receipt: ["create"], accounting: ["view"] } }}
    selectedEntity="ent_ksc" />);
  expect(q("fin-desk-uang_masuk-row-so1")).toBeNull();
  await klik("fin-desk-piutang_lewat_tempo-row-so1");
  expect(teks(q("fin-desk-detail-action-0"))).toContain("Terima pembayaran");
  await klik("fin-desk-detail-action-0");
  expect(teks(q("rpm-stub"))).toBe("so1");
});

test("RoleDesk: satu dokumen hanya sekali", async () => {
  routeGet({ "/desks/me": { queues: [
    { id: "giliran_saya", label: "Giliran saya", count: 1, value_kind: "count", rows: [{ ref_type: "sales_order", ref_id: "so_1", number: "SO-1", title: "G", age_days: 0, action: "Buka" }] },
    { id: "so_acc", label: "ACC", count: 1, rows: [{ ref_type: "sales_order", ref_id: "so_1", number: "SO-1", title: "Toko", age_days: 0, action: "Putuskan" }] }] } });
  await mount(<RoleDesk desk="me" currentUser={{ permissions: {} }} onOpenDocument={() => {}} />);
  expect(document.body.querySelectorAll('[data-testid="my-desk-row-so_1"]')).toHaveLength(1);
  expect(teks(q("my-desk-count-giliran_saya"))).toBe("0");
  expect(q("my-desk-queue-giliran_saya").className).toContain("sm:h-[412px]");
});
