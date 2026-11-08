// PREP-C (keputusan pemilik 8 Nov 2026 — K-GDG-01…10, K-RFID-04/10): profil gedung bisa diatur (peran inspeksi/bahan,
// mode stok, bentuk simpan, gate per gedung + pasangan IN/OUT), draf putaway otomatis (terbitkan yang siap), tiba
// bertahap per trip. Uji utilitas murni + render laci profil & panel draf.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import WarehouseProfileDrawer from "../wms/warehouses/WarehouseProfileDrawer";
import PutawayDraftsPanel from "../wms/PutawayDraftsPanel";
import { gatePayload, gateSummary, needsArbitration, normalizeGate, rulesSummary } from "../wms/warehouses/warehouseProfileUtils";
import { PA_STATUS, draftReadiness, parseCodes, pendingCount, statusOf, tripMessage } from "../wms/putawayUtils";
import { normalizeZones, ruleSummary } from "../wms/location/locUtils";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(), patch: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
jest.mock("../../components/KNSelect", () => ({ value, onValueChange, options = [], "data-testid": tid }) => (
  <select data-testid={tid} value={value} onChange={(e) => onValueChange(e.target.value)}>
    <option value="" />
    {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
  </select>
));
jest.mock("../../components/FormModal", () => ({ children, footer, error }) => (
  <div>{error ? <p data-testid="modal-error">{error}</p> : null}{children}{footer}</div>
));
jest.mock("../../hooks/useDomainEnums", () => () => ({ options: () => [{ value: "A" }, { value: "B" }], labelOf: (_k, v) => v }));
jest.mock("../../services/confirmService", () => ({ askReason: jest.fn(), askConfirm: jest.fn() }));
jest.mock("../wms/warehouses/warehouseApi", () => ({
  ...jest.requireActual("../wms/warehouses/warehouseApi"),
  patchWarehouse: jest.fn(), listGateDevices: jest.fn(), listTemplates: jest.fn(),
}));
const axios = require("../../services/apiClient").default;
const whApi = require("../wms/warehouses/warehouseApi");

beforeEach(() => {   // CRA mereset implementasi mock per uji — pasang ulang di sini
  whApi.patchWarehouse.mockResolvedValue({});
  whApi.listGateDevices.mockResolvedValue([
    { id: "dev_in", code: "G-IN", name: "Gate IN", type: "gate", direction: "in" },
    { id: "dev_out", code: "G-OUT", name: "Gate OUT", type: "gate", direction: "out" }]);
  whApi.listTemplates.mockResolvedValue([{ id: "tpl1", name: "ALICE KNIT" }]);
});

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  return { host, root };
}
const pick = async (el, value) => {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(el, value);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
};
const click = async (el) => { await act(async () => { el.click(); }); };

test("gate: data lama {physical_gate} terbaca; tanpa gate = handheld; ringkasan & penengah pasangan berdampingan", () => {
  expect(normalizeGate({ physical_gate: true })).toMatchObject({ has_gate: true, confirm_mode: "gate", pairs: [] });
  expect(gatePayload({ has_gate: false, confirm_mode: "gate", pairs: [] }).confirm_mode).toBe("handheld");
  expect(gateSummary({ stock_mode: "quantity", gate_config: { has_gate: true } })).toMatch(/gate tidak berlaku/);
  expect(gateSummary({ gate_config: { has_gate: true, pairs: [{ in_device_id: "a" }] } })).toMatch(/1 pasang/);
  expect(gateSummary({ gate_config: {} })).toBe("pindai genggam");
  expect(needsArbitration({ has_gate: true, pairs: [{ layout: "berdampingan_sekat" }] })).toBe(true);
  expect(needsArbitration({ has_gate: true, pairs: [{ layout: "terpisah" }] })).toBe(false);
});

test("aturan simpan: artikel & PT ikut ringkasan; zona menyimpan bentuk simpan", () => {
  expect(rulesSummary({ mode: "combined", template_ids: ["t1", "t2"], owner_entity_ids: ["ent_ksc"] }, { ent_ksc: "KSC" }))
    .toBe("aturan simpan: 2 artikel · PT KSC");
  expect(rulesSummary({ mode: "none", categories: ["Batik"] })).toBe("tanpa aturan simpan");
  expect(ruleSummary({ template_ids: ["t1"], owner_entity_ids: ["a", "b"] })).toBe("1 artikel · 2 PT");
  const z = normalizeZones([{ id: "z1", name: "A", storage_form: "floor", racks: [] }, { id: "z2", name: "B", racks: [] }]);
  expect(z[0].storage_form).toBe("floor");
  expect(z[1].storage_form).toBeUndefined();
});

test("putaway: status draf/tiba sebagian/dikembalikan, hitung menunggu, pesan trip", () => {
  expect(PA_STATUS.draft[1]).toMatch(/Draf/);
  expect(statusOf({ status: "partially_received" })[1]).toBe("Tiba Sebagian");
  expect(statusOf({ status: "returned" })[1]).toMatch(/Dikembalikan/);
  const o = { status: "partially_received", btg_number: "BTG-1",
    items: [{ status: "arrived" }, { status: "pending" }, { status: "pending" }],
    trip: { arrived_roll_nos: ["R1"], already_roll_nos: ["R0"], unknown_epcs: ["X"] } };
  expect(pendingCount(o)).toBe(2);
  expect(tripMessage(o)).toBe("1 roll tiba · 1 sudah tiba sebelumnya · 1 kode bukan milik PA ini · 2 roll masih menunggu — BTG BTG-1");
  expect(tripMessage({ duplicate_trip: true })).toMatch(/sudah tercatat/);
  expect(parseCodes("A, B;C\nD  ")).toEqual(["A", "B", "C", "D"]);
  expect(draftReadiness({ items: [{ ready: true }, { ready: false, inspection_requested: true }] }))
    .toEqual({ ready: 1, notReady: 1, inspection: 1 });
});

test("laci profil: peran inspeksi, mode kuantitas (gate tidak berlaku), pasangan gate → dikirim utuh", async () => {
  const onSaved = jest.fn();
  const wh = { id: "wh1", name: "Gedung Uji", roles: ["storage"], gate_config: { physical_gate: false },
    storage_rules: { mode: "none" } };
  const { host, root } = await mount(<WarehouseProfileDrawer warehouse={wh} sites={[]} categories={[]}
    entities={[{ id: "ent_ksc", short_name: "KSC" }]} onClose={() => {}} onSaved={onSaved} />);
  await click(q(host, "wh-profile-role-inspection"));
  await pick(q(host, "wh-profile-stock-mode"), "quantity");
  expect(q(host, "wh-profile-gate-na")).not.toBeNull();
  await pick(q(host, "wh-profile-stock-mode"), "roll_tagged");
  await pick(q(host, "wh-profile-storage-form"), "floor");
  await click(q(host, "wh-profile-gate-toggle"));
  await click(q(host, "wh-gate-pair-add"));
  await pick(q(host, "wh-gate-pair-in-0"), "dev_in");
  await pick(q(host, "wh-gate-pair-out-0"), "dev_out");
  await pick(q(host, "wh-gate-pair-layout-0"), "berdampingan");
  expect(q(host, "wh-gate-arbitration")).not.toBeNull();
  await pick(q(host, "wh-profile-rulemode"), "combined");
  await click(q(host, "wh-profile-owner-ent_ksc"));
  await pick(q(host, "wh-profile-template-add"), "tpl1");
  await click(q(host, "wh-profile-save"));
  const body = whApi.patchWarehouse.mock.calls[0][1];
  expect(body.roles).toEqual(["storage", "inspection"]);
  expect(body.stock_mode).toBe("roll_tagged");
  expect(body.storage_form).toBe("floor");
  expect(body.storage_rules).toMatchObject({ mode: "combined", owner_entity_ids: ["ent_ksc"], template_ids: ["tpl1"] });
  expect(body.gate_config).toMatchObject({ has_gate: true, confirm_mode: "gate" });
  expect(body.gate_config.pairs[0]).toMatchObject({ in_device_id: "dev_in", out_device_id: "dev_out", layout: "berdampingan" });
  expect(onSaved).toHaveBeenCalled();
  await act(async () => { root.unmount(); });
});

test("panel draf: kesiapan per roll, terbitkan yang siap saja (split_unready)", async () => {
  const draft = { id: "pa1", pa_number: "PA-00001", status: "draft", purpose: "inspection", from_warehouse_name: "Transit",
    to_warehouse_name: "Gedung Retur", item_count: 2, auto: { trigger: { number: "PO-1" } } };
  const detail = { ...draft, to_warehouse_id: "wh_r", destination_options: [{ warehouse_id: "wh_r", warehouse_name: "Gedung Retur" }],
    items: [{ roll_id: "r1", roll_no: "R1", ready: true, qty: 10, unit: "yard" },
      { roll_id: "r2", roll_no: "R2", ready: false, block_reason: "belum terverifikasi", inspection_requested: true, qty: 5, unit: "yard" }] };
  axios.get.mockResolvedValue({ data: detail });
  axios.post.mockResolvedValue({ data: { pa_number: "PA-00001", item_count: 1 } });
  const onChanged = jest.fn(() => Promise.resolve());
  const { host, root } = await mount(<PutawayDraftsPanel drafts={[draft]} whId="wh_t" onChanged={onChanged} />);
  await click(q(host, "pa-draft-toggle-pa1"));
  expect(q(host, "pa-draft-readiness-pa1").textContent).toMatch(/1 siap · 1 belum siap · 1 diminta inspeksi/);
  expect(q(host, "pa-draft-publish-pa1").disabled).toBe(true);
  await click(q(host, "pa-draft-publish-ready-pa1"));
  expect(axios.post).toHaveBeenCalledWith("/api/putaway-orders/pa1/publish", { split_unready: true });
  expect(q(host, "pa-drafts-msg").textContent).toMatch(/PA-00001 diterbitkan/);
  expect(onChanged).toHaveBeenCalled();
  await act(async () => { root.unmount(); });
});
