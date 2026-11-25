// MEJA-14 — §5.6: Cetak membuka pop-up dokumen pesanan; Buat SPK QC membuka pembuatan SPK dengan pesanan terpilih.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import SalesAdminDesk from "../sales_admin/SalesAdminDesk";
import RoleDesk from "../desks/RoleDesk";
import { ORDER_PRINT_DOCS } from "../documents/orderPrintDocs";
import { EntityScopeProvider } from "../../context/EntityScopeContext";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockToast = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } } },
  API: "/api",
  setActiveEntity: () => {}, setAuthToken: () => {},
}));
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: (...a) => mockToast(...a) }));
jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid, className }) => (
    <select data-testid={tid} className={className} value={value ?? ""} onChange={(e) => onValueChange(e.target.value)}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>);
  return { __esModule: true, default: M, KNSelect: M };
});
jest.mock("../documents/RelatedDocsPanel", () => (p) => (
  <div data-testid="rdp-stub" data-source={p.sourceId}>{p.docs.map((d) => d.docType).join(",")}</div>));
jest.mock("../sales_admin/SoTrackerCard", () => () => <div data-testid="so-tracker-stub" />);
jest.mock("../sales_admin/KeepPendingPanel", () => () => null);
jest.mock("../sales_admin/CustomerGradeRulesCard", () => () => null);
jest.mock("../sales_admin/VerifyOrderDialog", () => () => null);
jest.mock("../sales_admin/FulfillmentDecisionDialog", () => () => null);
jest.mock("../home/ReturnDeskSummaryCard", () => ({
  __esModule: true, ...jest.requireActual("../home/ReturnDeskSummaryCard"),
  default: () => <div data-testid="return-desk-stub" />,
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const teks = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");
let roots = [];
async function mount(el) {
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host); roots.push(root);
  await act(async () => { root.render(
    <EntityScopeProvider selectedEntity="all" entities={[{ id: "ent_ksc", short_name: "KSC" }]}>{el}</EntityScopeProvider>); });
  await act(async () => {}); await act(async () => {});
  return host;
}
const klik = async (id) => act(async () => { q(id).dispatchEvent(new MouseEvent("click", { bubbles: true })); });
function routeGet(peta) {
  mockGet.mockImplementation((u) => {
    const k = Object.keys(peta).sort((a, b) => b.length - a.length).find((x) => u.includes(x));
    return Promise.resolve({ data: k ? peta[k] : [] });
  });
}
afterEach(async () => {
  for (const r of roots) await act(async () => r.unmount());
  roots = []; document.body.innerHTML = "";
  mockGet.mockReset(); mockPost.mockReset(); mockToast.mockReset();
  sessionStorage.clear();
});

test("ORDER_PRINT_DOCS: empat dokumen pesanan, satu sumber", () => {
  expect(ORDER_PRINT_DOCS.map((d) => d.docType)).toEqual(["picking_list", "packing_list", "delivery_note", "invoice"]);
});

test("Cetak: pop-up dokumen pesanan di tempat, tanpa pindah ke daftar Pesanan", async () => {
  const open = jest.fn();
  routeGet({ "/sales-admin/desk": { queues: [{ id: "siap_cetak_dokumen", label: "Siap cetak", count: 1, rows: [
    { ref_type: "sales_order", ref_id: "so9", number: "SO-9", title: "Toko C", entity_id: "ent_ksc", age_days: 1,
      action: "Cetak", action_kind: "print" }] }] } });
  await mount(<SalesAdminDesk currentUser={{ permissions: { order: ["view", "confirm"] } }} onOpenDocument={open} />);
  await klik("desk-action-so9");
  expect(open).not.toHaveBeenCalled();
  expect(teks(q("order-print-title"))).toContain("SO-9");
  expect(q("rdp-stub").getAttribute("data-source")).toBe("so9");
  expect(teks(q("rdp-stub"))).toBe("picking_list,packing_list,delivery_note,invoice");
});

const WH = { "/warehouse-admin/desk": { queues: [{ id: "qc_pesanan", label: "QC", count: 1, value_kind: "count", rows: [
    { ref_type: "sales_order", ref_id: "so5", number: "SO-5", title: "Toko Q", entity_id: "ent_ksc", age_days: 0,
      action: "Buat SPK QC", action_kind: "create_qc_spk", link_view: "inspections" }] }] },
  "/inspections/meta/ref-docs": { items: [{ value: "so5", label: "SO-5 · Toko Q" }] },
  "/inspections/meta": { kinds: [{ value: "sales_order", label: "QC Permintaan Pesanan (SO)" }], officers: [] } };

test("Buat SPK QC: pembuatan SPK terbuka dengan jenis QC Pesanan dan pesanan terpilih", async () => {
  routeGet(WH);
  mockPost.mockResolvedValue({ data: { id: "ins1", number: "INS-1" } });
  await mount(<RoleDesk desk="warehouse_admin" currentUser={{ permissions: { wms: ["view"], inspection: ["create"] } }} onOpenDocument={() => {}} />);
  await klik("wh-desk-action-so5");
  expect(q("ins-kind-select").value).toBe("sales_order");
  expect(q("ins-ref-select").value).toBe("so5");
  await klik("ins-create-submit");
  expect(mockPost).toHaveBeenCalledWith("/api/inspections", expect.objectContaining({ kind: "sales_order", ref_doc_id: "so5" }));
  expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: expect.stringContaining("SO-5") }));
});

test("tanpa izin inspection.create: aksi membuka rincian, bukan pembuatan SPK", async () => {
  routeGet(WH);
  await mount(<RoleDesk desk="warehouse_admin" currentUser={{ permissions: { wms: ["view"] } }} onOpenDocument={() => {}} />);
  await klik("wh-desk-action-so5");
  expect(q("ins-create-modal")).toBeNull(); expect(q("wh-desk-detail")).not.toBeNull();
});
