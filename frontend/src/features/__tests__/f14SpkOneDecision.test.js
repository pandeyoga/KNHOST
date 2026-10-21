// F-14 (keputusan owner Q-03a, 2026-10-21) — SATU keputusan: SPK penerimaan memutus karantina.
// Antrean karantina menunjuk SPK terbuka ("Putuskan di SPK"); panel SPK penerimaan meminta tindakan untuk roll
// ditolak + roll mana yang ditolak (Diterima sebagian) dan mengirimnya bersama keputusan; QC (qc.release) boleh menutup.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import QCInspection from "../wms/QCInspection";
import InspectionDetailPanel from "../inspections/InspectionDetailPanel";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
jest.mock("../../components/KNSelect", () => ({ value, onValueChange, options = [], "data-testid": tid }) => (
  <select data-testid={tid} value={value} onChange={(e) => onValueChange(e.target.value)}>
    <option value="" />
    {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
  </select>
));
jest.mock("../wms/QcPlanPanel", () => () => null);
jest.mock("../wms/RollInspectionModal", () => () => null);
jest.mock("../../hooks/useDomainEnums", () => () => ({ options: () => [], labelOf: (_k, v) => v }));
jest.mock("../documents/DocumentActionsBar", () => () => null);
jest.mock("../inspections/InspectLineModal", () => () => null);
jest.mock("../../services/confirmService", () => ({ askReason: jest.fn() }));
jest.mock("../../utils/feedback", () => ({ notifySuccess: jest.fn() }));
jest.mock("../inspections/inspectionsApi", () => ({
  ...jest.requireActual("../inspections/inspectionsApi"),
  finishInspection: jest.fn(),
  getInspection: jest.fn(),
}));
const axios = require("../../services/apiClient").default;
const api = require("../inspections/inspectionsApi");

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

test("antrean karantina: tugas dengan SPK terbuka → tombol 'Putuskan di SPK', tanpa form keputusan kedua", async () => {
  const task = { id: "t1", product_name: "GREY POPLIN", quarantine_qty: 150, quarantine_unit: "yard",
    inspection: { id: "ins1", number: "KSC/INS-00031", status: "assigned" } };
  axios.get.mockImplementation((url) => Promise.resolve({ data: url === "/api/inbound/qc/queue" ? [task] : [] }));
  const onOpenSpk = jest.fn();
  const { host, root } = await mount(<QCInspection currentUser={{ role: "qc", permissions: {} }} selectedEntity="ent_ksc" onOpenSpk={onOpenSpk} />);
  expect(q(host, "qc-inspect-btn-0")).toBeNull();
  expect(q(host, "qc-spk-number-0").textContent).toBe("KSC/INS-00031");
  await act(async () => { q(host, "qc-open-spk-btn-0").click(); });
  expect(onOpenSpk).toHaveBeenCalledWith(task.inspection);
  await act(async () => { root.unmount(); });
});

test("SPK penerimaan: Diterima sebagian wajib tindakan + roll ditolak, lalu dikirim bersama keputusan (QC qc.release)", async () => {
  const doc = { id: "ins1", number: "KSC/INS-00031", kind: "po_receipt", task_id: "t1", status: "in_progress",
    lines: [{ id: "l1", roll_id: "r1", roll_no: "RL-1", quantity: 50, unit: "yard", grade_after: "A" },
            { id: "l2", roll_id: "r2", roll_no: "RL-2", quantity: 50, unit: "yard", grade_after: "B" }] };
  api.finishInspection.mockResolvedValue({ ...doc, status: "done" });
  api.getInspection.mockResolvedValue({ ...doc, status: "done" });
  const qcUser = { role: "qc", permissions: { qc: ["view", "inspect", "release"], inspection: ["view"] } };
  const { host, root } = await mount(<InspectionDetailPanel doc={doc} meta={{ can_qc_release: true, decisions: [
    { value: "terima", label: "Diterima seluruhnya" }, { value: "terima_sebagian", label: "Diterima sebagian" },
    { value: "tolak", label: "Ditolak" }] }} currentUser={qcUser} onChanged={jest.fn()} onClose={jest.fn()} />);
  expect(q(host, "ins-quarantine-note").textContent).toMatch(/langsung memutus karantina/);
  await pick(q(host, "ins-decision-select"), "terima_sebagian");
  expect(q(host, "ins-finish-button").disabled).toBe(true);                     // tindakan & roll belum dipilih
  await pick(q(host, "ins-reject-disposition"), "return");
  expect(q(host, "ins-finish-button").disabled).toBe(true);                     // roll ditolak belum dicentang
  await act(async () => { q(host, "ins-reject-roll-l2").click(); });
  expect(q(host, "ins-finish-button").disabled).toBe(false);
  await act(async () => { q(host, "ins-finish-button").click(); });
  expect(api.finishInspection).toHaveBeenCalledWith("ins1", "terima_sebagian", "",
    { reject_disposition: "return", rejected_roll_ids: ["r2"] });
  await act(async () => { root.unmount(); });
});

test("SPK sudah memutus karantina: ringkasan tampil, tombol buka kembali tidak ada", async () => {
  const doc = { id: "ins2", number: "KSC/INS-00032", kind: "po_receipt", task_id: "t2", status: "done", lines: [],
    quarantine_result: { accepted_qty: 100, rejected_qty: 50, purchase_return: { number: "KSC/PRT-00004" } } };
  const admin = { role: "admin", permissions: { inspection: ["view", "decide", "reopen"] } };
  const { host, root } = await mount(<InspectionDetailPanel doc={doc} meta={{}} currentUser={admin} onChanged={jest.fn()} onClose={jest.fn()} />);
  expect(q(host, "ins-quarantine-result").textContent).toMatch(/diterima 100 · ditolak 50 → retur KSC\/PRT-00004/);
  expect(q(host, "ins-reopen-button")).toBeNull();
  await act(async () => { root.unmount(); });
});

// F-13 (keputusan owner Q-06b) — MD Quality baru boleh mengisi SESUDAH SPK ditugaskan: di SPK draft tombolnya tidak ada.
test("F-13: SPK draft → tombol MD Quality/Periksa tidak tampil + petunjuk; sesudah ditugaskan tombol MD Quality ada", async () => {
  const line = { id: "l1", roll_id: "r1", roll_no: "RL-1", quantity: 50, unit: "yard" };
  const mdq = { role: "md_quality", permissions: { inspection: ["view"] } };
  const meta = { can_md_quality: true, md_quality_kinds: ["po_receipt"] };
  let m = await mount(<InspectionDetailPanel doc={{ id: "i1", number: "KSC/INS-1", kind: "po_receipt", task_id: "t", status: "draft", lines: [line] }}
    meta={meta} currentUser={mdq} onChanged={jest.fn()} onClose={jest.fn()} />);
  expect(q(m.host, "ins-line-mdq-l1")).toBeNull();
  expect(q(m.host, "ins-draft-hint").textContent).toMatch(/belum ditugaskan/);
  await act(async () => { m.root.unmount(); });
  m = await mount(<InspectionDetailPanel doc={{ id: "i1", number: "KSC/INS-1", kind: "po_receipt", task_id: "t", status: "assigned", lines: [line] }}
    meta={meta} currentUser={mdq} onChanged={jest.fn()} onClose={jest.fn()} />);
  expect(q(m.host, "ins-line-mdq-l1")).not.toBeNull();
  await act(async () => { m.root.unmount(); });
});
