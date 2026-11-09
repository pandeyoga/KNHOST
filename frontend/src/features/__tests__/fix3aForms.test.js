// FIX-3a (audit 9 Nov B2a/B3b) — isian alur barang masuk terikat data & tombol simulasi hanya di mode simulasi:
// BinSelect (bin dari struktur gudang, bukan teks bebas — INP-01/02/05), daftar pola regex satu per baris (FRM-19),
// "Simulasi Scan Semua" hanya bila PT bermode simulasi RFID (FRM-10, K-B3b-09), kartu HP tugas yang sudah diputus QC
// tidak menawarkan Terima/Selesai (FLW-IN-01), persetujuan pendaftaran awal dua langkah.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import BinSelect from "../../components/BinSelect";
import SettingEditor from "../settings/config/SettingEditor";
import PutawayOrdersPanel from "../wms/PutawayOrdersPanel";
import { InboundActions } from "../mobile/MobileTaskActions";
import RegistrationDetail from "../inventory/registration/RegistrationDetail";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(), patch: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
jest.mock("../../components/KNSelect", () => ({ value, onValueChange, options = [], "data-testid": tid }) => (
  <select data-testid={tid} value={value} onChange={(e) => onValueChange(e.target.value)}>
    {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
  </select>
));
jest.mock("../../hooks/useDomainEnums", () => () => ({ options: () => [{ value: "A", label: "A" }, { value: "B", label: "B" }], labelOf: (_k, v) => v }));
jest.mock("../../hooks/useReceivingMode", () => () => ({ isGrn: () => false, data: {} }));
jest.mock("../../services/confirmService", () => ({ askReason: jest.fn(), askConfirm: jest.fn() }));
jest.mock("../../config/roles", () => ({ ...jest.requireActual("../../config/roles"), canCurrent: (m, a) => !(m === "inventory" && a === "approve_value") }));
jest.mock("../wms/PutawayDraftsPanel", () => () => null);
const axios = require("../../services/apiClient").default;

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await flush();
  return host;
}

test("BinSelect memuat bin dari struktur gudang dan mengirim id kanonik (bukan teks bebas)", async () => {
  axios.get.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/warehouses/wh1/locations")
    ? { bins: [{ bin_id: "bin_a1", code: "A1-01", path: "Zona A / Rak 1" }] } : {} }));
  const picked = [];
  const host = await mount(<BinSelect data-testid="b" warehouseId="wh1" value="" onChange={(v) => picked.push(v)} />);
  const sel = q(host, "b");
  expect(sel.tagName).toBe("SELECT");
  expect([...sel.options].map((o) => o.value)).toEqual(["", "bin_a1"]);
  expect(sel.textContent).toContain("A1-01");
});

test("daftar pola regex: satu butir per baris — koma di dalam kuantor tidak memecah pola", async () => {
  const got = [];
  const entry = { key: "receiving.client_po_patterns", type: "list", value_format: "regex" };
  const host = await mount(<SettingEditor entry={entry} value={["(?P<core>\\d{3,5})/CST/\\d{4}"]} onChange={(v) => got.push(v)} testId="cfg" />);
  const ta = q(host, "cfg");
  expect(ta.tagName).toBe("TEXTAREA");
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set.call(ta, "(?P<core>\\d{3,5})/CST/\\d{4}\n[A-Z]+/PO-(?P<core>\\d+)");
    ta.dispatchEvent(new Event("input", { bubbles: true }));
  });
  expect(got[got.length - 1]).toEqual(["(?P<core>\\d{3,5})/CST/\\d{4}", "[A-Z]+/PO-(?P<core>\\d+)"]);
});

test("Simulasi Scan Semua hanya tampil bila PT bermode simulasi RFID", async () => {
  const orders = [
    { id: "pa1", pa_number: "PA-1", status: "open", items: [{ roll_id: "r1", epc: "E1", status: "pending" }], rfid_simulation: false },
    { id: "pa2", pa_number: "PA-2", status: "open", items: [{ roll_id: "r2", epc: "E2", status: "pending" }], rfid_simulation: true },
  ];
  axios.get.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/putaway-orders") ? { orders } : null }));
  const host = await mount(<PutawayOrdersPanel whId="" selectedEntity="all" />);
  expect(q(host, "pa-panel")).not.toBeNull();
  await act(async () => { q(host, "pa-confirm-pa1").click(); });
  expect(q(host, "pa-confirm-box-pa1")).not.toBeNull();
  expect(q(host, "pa-confirm-sim-pa1")).toBeNull();          // PT tanpa mode simulasi → tombol tidak ada
  await act(async () => { q(host, "pa-confirm-pa2").click(); });
  expect(q(host, "pa-confirm-sim-pa2")).not.toBeNull();      // mode simulasi aktif → tombol tampil
});

test("kartu HP: tugas yang sudah diputus QC tidak menawarkan Terima/Selesai", async () => {
  axios.get.mockResolvedValue({ data: null });
  const host = await mount(<InboundActions task={{ id: "t1", status: "qc_rejected", product_id: "p1", unit: "yard" }} />);
  expect(q(host, "mw-receive-btn-t1")).toBeNull();
  expect(q(host, "mw-complete-btn-t1")).toBeNull();
  expect(q(host, "mw-inbound-locked-t1")).not.toBeNull();
});

test("pendaftaran awal dua langkah: langkah 1 menampilkan 'Setujui hitungan', bukan persetujuan nilai", async () => {
  const session = { id: "s1", number: "REG-1", name: "Uji", status: "pending_approval", approval_step: "count",
    finance_approval_required: true, warehouse_name: "Woven", registration: { node_labels: ["Zona A"], groups: {} },
    freeze: { active: true, label: "Zona A" }, progress: { racks: [], racks_total: 0, racks_done: 0, lines: 0, unmapped: 0, unverified_length: 0 } };
  const rec = { totals: {}, policy: "", groups: [{ key: "p1|e", product_id: "p1", sku: "S", product_name: "K", owner_entity_id: "e",
    unit: "yard", old_rolls: 1, old_qty: 1, registered_rolls: 1, registered_qty: 1, reuse: 0, new: 1, missing_rolls: 0,
    unit_cost: 1, cost_basis: "x", value_net: 1, notes: [], result: null }], unmapped: [] };
  axios.get.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/reconcile") ? rec : session }));
  const host = await mount(<RegistrationDetail sessionId="s1" />);
  await flush();
  expect(q(host, "reg-approve-count")).not.toBeNull();
  expect(q(host, "reg-approve-all")).toBeNull();
  expect(q(host, "reg-approve-p1")).toBeNull();
  expect(q(host, "reg-step-count")).not.toBeNull();
});
