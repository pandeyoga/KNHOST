// Review adversarial S5 (Hutang per Pemasok, commit ac25d81) — temuan sisi layar:
//  · R-S5-03 — tanpa izin lihat kontrabon server kini hanya mengirim FAKTA "dipegang kontrabon" (id/nomor/status kosong,
//    `ap_party_service.supplier_detail`). Layar & CSV tidak boleh menulis "Bayar lewat kontrabon undefined" /
//    "undefined (undefined)"; tagihan itu tetap tidak bisa dicentang/dibayar langsung.
//  · R-S5-04 — form "Bayar beberapa tagihan": bila TIDAK ada satu pun yang terbayar, rincian pemasok tidak diberi pesan
//    sukses (dulu "Tidak ada tagihan yang terbayar: n gagal." tampil di bilah hijau).
//  · R-S5-05 — rincian pemasok: "pilih semua" hanya mencentang tagihan yang TAMPIL menurut saringan/cari (dulu juga yang
//    disembunyikan saringan → "Bayar terpilih" ikut membayar tagihan yang belum jatuh tempo).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { AppNavProvider } from "../../context/AppNavContext";
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
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: jest.fn(), askReason: jest.fn(), askText: jest.fn(), askChoice: jest.fn(), default: {},
}));
jest.mock("../../components/KNSelect", () => {
  // eslint-disable-next-line global-require
  const React = require("react");
  const M = ({ value, onValueChange, options = [], "data-testid": tid }) => React.createElement("select",
    { "data-testid": tid, value: value || "", onChange: (e) => onValueChange && onValueChange(e.target.value) },
    [React.createElement("option", { key: "", value: "" }, "-"),
      ...options.map((o) => React.createElement("option", { key: o.value, value: o.value }, o.label))]);
  return { __esModule: true, default: M, KNSelect: M };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange?.(e.target.value)} />,
  formatDateId: (v) => String(v || ""),
}));

/* eslint-disable import/first */
import { askConfirm } from "../../services/confirmService";
import { buildCsv } from "../../utils/csvExport";
import { CSV_TAGIHAN } from "../finance/ap/apPartyApi";
import APSupplierDetail from "../finance/ap/APSupplierDetail";
import PayManyBillsModal from "../finance/ap/PayManyBillsModal";
/* eslint-enable import/first */

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 8) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
const ENT = [{ id: "ent_ksc", short_name: "Sukacita", legal_name: "PT Kain Suka Cita" }];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(<AppNavProvider role="finance"><EntityScopeProvider selectedEntity="ent_ksc" entities={ENT} canSwitch>{el}</EntityScopeProvider></AppNavProvider>);
  });
  await flush();
  return host;
}
async function click(el) { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await flush(); }
async function pick(el, value) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(el, value);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = []; document.body.innerHTML = "";
});

const B1 = { bill_id: "vb18", bill_number: "VB-00018", entity_id: "ent_ksc", due_date: "2026-12-17", days_past_due: -30,
  aging_bucket: "not_due", aging_label: "Belum jatuh tempo", grand_total: 1864800, amount_paid: 0, outstanding: 1864800,
  contra_bon: null, payment_tolerance: 5000 };
// Bentuk server tanpa `contra_bon.view`: dipegang kontrabon, identitas kosong.
const DIPEGANG = { ...B1, bill_id: "vb20", bill_number: "VB-00020", outstanding: 500000, grand_total: 500000,
  contra_bon: { id: "", number: "", status: "", status_label: "" } };

test("R-S5-03: tagihan dipegang kontrabon tanpa izin lihat kontrabon — tanpa 'undefined', tetap tidak bisa dibayar langsung", async () => {
  const user = { id: "u1", role: "custom_ap", permissions: { vendor_bill: ["view", "pay"] } };
  const detail = { supplier: { id: "s1", name: "Pemasok R" }, entities: [], bills: [B1, DIPEGANG], contra_bons: null,
    credits: [], totals: { outstanding: 2364800, payable_direct: 1864800, held: 500000, bill_count: 2 } };
  await mount(<APSupplierDetail detail={detail} currentUser={user} allPt={false} ptName="Sukacita" onPayMany={() => {}} onPayOne={() => {}} />);
  expect(q("ap-detail-held-vb20").textContent.trim()).toBe("Bayar lewat kontrabon");
  expect(q("ap-detail-check-vb20")).toBeNull();
  expect(q("ap-detail-pay-vb20")).toBeNull();
  expect(q("ap-detail-contra-bons")).toBeNull();
  const csv = buildCsv([B1, DIPEGANG], CSV_TAGIHAN);
  expect(csv).not.toMatch(/undefined/);
  expect(csv.trim().split("\n").pop()).toMatch(/Ya\s*"?$/);
  // Dengan izin lihat kontrabon: nomor & status tetap ditulis.
  const penuh = { ...DIPEGANG, contra_bon: { id: "cb1", number: "KB-0001", status: "approved", status_label: "Disetujui" } };
  expect(buildCsv([penuh], CSV_TAGIHAN)).toMatch(/KB-0001 \(Disetujui\)/);
});

test("R-S5-04: semua tagihan gagal dibayar → rincian pemasok tidak diberi pesan sukses", async () => {
  mockGet.mockImplementation((url) => {
    if (url.endsWith("/ap-payments/accounts")) return Promise.resolve({ data: [{ id: "rek1", name: "BCA Operasional KSC", bank_name: "BCA" }] });
    if (url.endsWith("/ap-payments/pending")) return Promise.resolve({ data: null });
    return Promise.resolve({ data: [] });
  });
  mockPost.mockImplementation(() => Promise.reject(Object.assign(new Error("ditolak"), {
    response: { status: 409, data: { detail: "Tagihan VB-00018 sedang dipegang kontrabon KB-9." } } })));
  askConfirm.mockImplementation(async () => true);
  const done = jest.fn();
  await mount(<PayManyBillsModal supplierName="Pemasok R" entityId="ent_ksc" ptName="Sukacita" bills={[B1]} onClose={() => {}} onDone={done} />);
  await pick(q("pay-many-account"), "rek1");
  await click(q("pay-many-submit"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  expect(q("pay-many-summary").textContent).toMatch(/Tidak ada tagihan yang terbayar/);   // rincian tetap di form
  expect(done).toHaveBeenCalledTimes(1);
  expect(done.mock.calls[0][1]).toBe("");   // bukan pesan sukses untuk bilah hijau rincian pemasok
});

test("R-S5-05: saring 'Lewat jatuh tempo' lalu pilih semua → hanya tagihan yang tampil yang dicentang", async () => {
  const user = { id: "u1", role: "finance", permissions: { vendor_bill: ["view", "pay"], contra_bon: ["view", "pay"] } };
  const LEWAT = { ...B1, bill_id: "vb30", bill_number: "VB-00030", days_past_due: 12, aging_bucket: "1-30", outstanding: 700000,
    grand_total: 700000 };
  const detail = { supplier: { id: "s1", name: "Pemasok R" }, entities: [], bills: [B1, LEWAT], contra_bons: [], credits: [],
    totals: { outstanding: 2564800, overdue: 700000, payable_direct: 2564800, held: 0, bill_count: 2 } };
  let dipilih = null;
  await mount(<APSupplierDetail detail={detail} currentUser={user} allPt={false} ptName="Sukacita"
    onPayMany={(b) => { dipilih = b; }} onPayOne={() => {}} />);
  await pick(q("ap-detail-filter"), "lewat");
  expect(q("ap-detail-bill-vb18")).toBeNull();
  await click(q("ap-detail-check-all"));
  expect(q("ap-detail-pay-many").textContent).toMatch(/Bayar terpilih \(1\)/);
  await click(q("ap-detail-pay-many"));
  expect(dipilih.map((b) => b.bill_id)).toEqual(["vb30"]);
  // Kembali ke semua tagihan: centang tadi tetap; pilih semua sekarang mencentang sisanya, klik lagi melepas semuanya.
  await pick(q("ap-detail-filter"), "semua");
  expect(q("ap-detail-check-all").checked).toBe(false);
  await click(q("ap-detail-check-all"));
  expect(q("ap-detail-pay-many").textContent).toMatch(/Bayar terpilih \(2\)/);
  await click(q("ap-detail-check-all"));
  expect(q("ap-detail-pay-many").disabled).toBe(true);
});
