// FIX-6 (keputusan pemilik 10 Nov 2026) — layar yang berubah:
// D2 tolak QC + retur supplier → pilihan WAJIB "Ganti barang" / "Potong tagihan" + alasan (antrean karantina & SPK),
// D9 satu SJ supplier untuk beberapa PT → wizard kedatangan memecah GRN per PT,
// D5 roll retur yang baru dipindai (karantina retur, nilai saat penyelesaian) tidak bisa di-release,
// penanda "minta inspeksi" di baris PO.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ReturnRemedyChoice, { remedyProblem } from "../wms/ReturnRemedyChoice";
import InspectionDetailPanel from "../inspections/InspectionDetailPanel";
import GrnCreateWizard from "../wms/grn/GrnCreateWizard";
import ReturnQuarantinePanel from "../sales/ReturnQuarantinePanel";
import PODetailPanel from "../admin/po/PODetailPanel";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(), patch: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
jest.mock("../../components/KNSelect", () => {
  const C = ({ value, onValueChange, options = [], "data-testid": tid }) => (
    <select data-testid={tid} value={value} onChange={(e) => onValueChange(e.target.value)}>
      <option value="" />
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: C, KNSelect: C };
});
jest.mock("../../hooks/useDomainEnums", () => () => ({ options: () => [{ value: "A", label: "A" }], labelOf: (_k, v) => v }));
jest.mock("../documents/DocumentActionsBar", () => () => null);
jest.mock("../inspections/InspectLineModal", () => () => null);
jest.mock("../../services/confirmService", () => ({ askReason: jest.fn(), askConfirm: jest.fn(() => Promise.resolve(true)) }));
jest.mock("../../utils/feedback", () => ({ notifySuccess: jest.fn() }));
jest.mock("../inspections/inspectionsApi", () => ({
  ...jest.requireActual("../inspections/inspectionsApi"),
  finishInspection: jest.fn(),
  getInspection: jest.fn(),
}));
jest.mock("../../hooks/useReceivingMode", () => () => ({ isGrn: () => false, data: {} }));
jest.mock("../../components/AskKnButton", () => ({ AskKnButton: () => null }));
jest.mock("../admin/po/POTimeline", () => () => null);
jest.mock("../admin/po/POVarianceTasksPanel", () => ({ POVarianceTasksPanel: () => null }));
jest.mock("../admin/po/POCloseSettlementPanel", () => ({ POCloseSettlementPanel: () => null }));
jest.mock("../admin/po/POVersionHistory", () => () => null);
jest.mock("../admin/po/PODeviationBanner", () => () => null);
jest.mock("../admin/po/POReceiptVariancePanel", () => () => null);
jest.mock("../documents/ProcessTimeline", () => () => null);
jest.mock("../documents/trace/DocRefsPanel", () => () => null);
jest.mock("../documents/RelatedDocsPanel", () => () => null);
jest.mock("../wms/grn/grnApi", () => ({
  ...jest.requireActual("../wms/grn/grnApi"),
  grnApi: { partners: jest.fn(), arrivalCandidates: jest.fn(), createArrival: jest.fn(), create: jest.fn(), upload: jest.fn() },
  photoCheck: jest.fn(() => Promise.resolve({ checked: false })),
}));
const axios = require("../../services/apiClient").default;
const api = require("../inspections/inspectionsApi");
const { grnApi } = require("../wms/grn/grnApi");

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await flush();
  return { host, root };
}
const pick = async (el, value) => {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(el, value);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
};
const type = async (el, value) => {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
};

test("D2 — pilihan retur ke supplier wajib: ganti barang / potong tagihan + alasan ≥ 5 huruf", async () => {
  expect(remedyProblem("", "Supplier kirim ganti")).toMatch(/Ganti barang atau Potong tagihan/);
  expect(remedyProblem("replace", "....")).toMatch(/minimal 5 huruf/);
  expect(remedyProblem("bill_cut", "Potong tagihan saja")).toBe("");
  const got = [];
  const { host, root } = await mount(<ReturnRemedyChoice value="" reason="" onChange={(v) => got.push(v)} onReason={() => {}} />);
  expect(q(host, "return-remedy-replace")).not.toBeNull();
  expect(q(host, "return-remedy-bill_cut")).not.toBeNull();
  await act(async () => { q(host, "return-remedy-bill_cut").click(); });
  expect(got).toEqual(["bill_cut"]);
  await act(async () => { root.unmount(); });
});

test("D2 — SPK penerimaan: Ditolak + retur ke supplier baru bisa ditutup sesudah memilih penyelesaian beralasan", async () => {
  const doc = { id: "ins1", number: "KSC/INS-00031", kind: "po_receipt", task_id: "t1", status: "in_progress",
    lines: [{ id: "l1", roll_id: "r1", roll_no: "RL-1", quantity: 50, unit: "yard", grade_after: "A" }] };
  api.finishInspection.mockResolvedValue({ ...doc, status: "done" });
  api.getInspection.mockResolvedValue({ ...doc, status: "done" });
  require("../../services/confirmService").askReason.mockResolvedValue("Belang di seluruh roll");
  const qcUser = { role: "qc", permissions: { qc: ["view", "inspect", "release"], inspection: ["view"] } };
  const { host, root } = await mount(<InspectionDetailPanel doc={doc} meta={{ can_qc_release: true, decisions: [
    { value: "terima", label: "Diterima seluruhnya" }, { value: "tolak", label: "Ditolak" }] }}
    currentUser={qcUser} onChanged={jest.fn()} onClose={jest.fn()} />);
  await pick(q(host, "ins-decision-select"), "tolak");
  await pick(q(host, "ins-reject-disposition"), "return");
  expect(q(host, "ins-return-remedy")).not.toBeNull();
  expect(q(host, "ins-finish-button").disabled).toBe(true);                     // penyelesaian belum dipilih
  await act(async () => { q(host, "ins-return-remedy-replace").click(); });
  await type(q(host, "ins-return-remedy-reason"), "Supplier sanggup kirim ganti");
  expect(q(host, "ins-finish-button").disabled).toBe(false);
  await act(async () => { q(host, "ins-finish-button").click(); });
  await flush();
  expect(api.finishInspection).toHaveBeenCalledWith("ins1", "tolak", "Belang di seluruh roll", expect.objectContaining({
    reject_disposition: "return", return_remedy: "replace", return_remedy_reason: "Supplier sanggup kirim ganti" }));
  await act(async () => { root.unmount(); });
});

test("D9 — wizard: satu SJ beberapa PT → pilih PO lintas PT satu lokasi → GRN per PT", async () => {
  grnApi.partners.mockResolvedValue([{ partner_id: "sup1", partner_name: "Supplier A", open_docs: [{ id: "po1", number: "PO-1", warehouse_id: "w1" }] }]);
  grnApi.arrivalCandidates.mockResolvedValue({ partner_id: "sup1", sites: [
    { site_id: "s1", site_name: "Rancamalang", pos: [
      { id: "po1", number: "PO-1", entity_id: "ent_ksc", entity_name: "Sukacita", warehouse_id: "w1", warehouse_name: "Transit" },
      { id: "po2", number: "PO-2", entity_id: "ent_kanda", entity_name: "Kanda", warehouse_id: "w1", warehouse_name: "Transit" }] },
    { site_id: "s2", site_name: "Soreang", pos: [
      { id: "po3", number: "PO-3", entity_id: "ent_kanda", entity_name: "Kanda", warehouse_id: "w9", warehouse_name: "Kanda" }] }] });
  grnApi.createArrival.mockResolvedValue({ arrival_id: "arr1", grns: [
    { id: "g1", entity_id: "ent_ksc", version: 1 }, { id: "g2", entity_id: "ent_kanda", version: 1 }] });
  axios.get.mockResolvedValue({ data: [{ id: "w1", name: "Transit" }] });
  const onCreated = jest.fn();
  const { host, root } = await mount(<GrnCreateWizard preset={{ partner_type: "supplier" }} onClose={jest.fn()} onCreated={onCreated} />);
  await pick(q(host, "grn-wizard-partner"), "sup1");
  await act(async () => { q(host, "grn-wizard-multipt").click(); });
  await flush();
  expect(grnApi.arrivalCandidates).toHaveBeenCalledWith("sup1");
  await act(async () => { q(host, "grn-wizard-arr-po-po1").querySelector("input").click(); });
  await act(async () => { q(host, "grn-wizard-arr-po-po2").querySelector("input").click(); });
  expect(q(host, "grn-wizard-arr-po-po3").querySelector("input").disabled).toBe(true);   // lokasi lain terkunci
  expect(q(host, "grn-wizard-arrival-summary").textContent).toMatch(/2 kedatangan.*Sukacita, Kanda/);
  await act(async () => { q(host, "grn-wizard-next").click(); });
  await act(async () => { q(host, "grn-wizard-submit").click(); });
  await flush();
  expect(grnApi.createArrival).toHaveBeenCalledWith({ partner_id: "sup1", po_ids: ["po1", "po2"] });
  expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ id: "g1" }));
  await act(async () => { root.unmount(); });
});

test("D5 — roll retur yang baru dipindai (karantina retur belum dinilai) tidak bisa di-release", async () => {
  axios.get.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/quarantine") ? [
    { id: "r1", roll_no: "RL-1", status: "quarantine", grade: "A", length_remaining: 10, unit: "yard", intake_pending_valuation: true },
  ] : [] }));
  const { host, root } = await mount(<ReturnQuarantinePanel ret={{ id: "sr1", number: "SRET-1", status: "approved" }} canApprove onReleased={jest.fn()} />);
  expect(q(host, "roll-intake-pending-r1").textContent).toMatch(/nilai saat penyelesaian/);
  expect(q(host, "regrade-r1")).toBeNull();                                    // tidak ada pilihan grade/release
  expect(q(host, "release-quarantine-btn")).toBeNull();
  await act(async () => { root.unmount(); });
});

test("minta inspeksi & retur tolak QC tampil di baris PO", async () => {
  axios.get.mockResolvedValue({ data: {} });
  const po = { id: "po1", po_number: "PO-1", status: "partial", supplier_name: "Supplier A", items: [
    { product_id: "p1", sku: "S1", product_name: "Kain", quantity: 50, received_qty: 0, unit: "yard", price: 1,
      inspection_requested: true, replaced_qty: 50 }] };
  const { host, root } = await mount(<PODetailPanel po={po} onClose={jest.fn()} />);
  expect(q(host, "po-item-0-fix6").textContent).toMatch(/minta inspeksi/);
  expect(q(host, "po-item-0-replaced").textContent).toMatch(/ganti barang 50 yard/);
  await act(async () => { root.unmount(); });
});
