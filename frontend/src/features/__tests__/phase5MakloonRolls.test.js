// Kasus celup (20 roll Esmica Blue → mitra celup → Esmica Hitam): pop-up Issue makloon punya mode "Pilih roll"
// (centang / pindai nomor roll atau EPC, total terpilih, galat di DALAM pop-up), mode lama "Berdasarkan jumlah" tidak
// berubah, dan pop-up Terima memberi tahu bahwa hasil langkah terakhir masuk karantina QC.
import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";

import { IssueModal, ReceiveModal } from "../purchasing/makloon/MkoStepModals";
import { canonCode, matchCodes } from "../purchasing/makloon/MkoIssueRollPicker";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
jest.mock("../../components/KNSelect", () => {
  const Sel = ({ value, onValueChange, options = [], "data-testid": tid }) => (
    <select data-testid={tid} value={value} onChange={(e) => onValueChange?.(e.target.value)}>
      <option value="" />
      {options.map((o) => <option key={`${o.value}`} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: Sel, KNSelect: Sel };
});
const axios = require("../../services/apiClient").default;

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};   // jsdom (ErrorNotice menggulir)
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
let host; let root;
async function mount(el) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(el); });
  await flush();
}
afterEach(async () => {
  if (root) await act(async () => { root.unmount(); });
  host?.remove(); root = null;
  axios.get.mockReset(); axios.post.mockReset();
});
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const type = async (el, value) => {
  Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(el, value);
  await act(async () => { el.dispatchEvent(new Event("input", { bubbles: true })); });
};
const choose = async (el, value) => {
  Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, "value").set.call(el, value);
  await act(async () => { el.dispatchEvent(new Event("change", { bubbles: true })); });
  await flush();
};

const EPC = "E2000000000000000000ABCD";
const STEP = { seq: 1, input_qty: 50, input_unit: "yard", input_name: "Esmica Blue", makloon_name: "Mitra Celup",
  source_stock: [{ warehouse_id: "w1", available_qty: 80 }], expected_output_qty: 50, output_unit: "yard", output_sku: "OUT" };
const ROLLS = {
  seq: 1, warehouse_id: "w1", unit: "yard", planned_qty: 50, total_qty: 80,
  rolls: [
    { id: "r1", roll_no: "RL-0001", lot: "L1", length_remaining: 25, unit: "yard", epc: "" },
    { id: "r2", roll_no: "RL-0002", lot: "L1", length_remaining: 25, unit: "yard", epc: "" },
    { id: "r3", roll_no: "RL-0003", lot: "L2", length_remaining: 30, unit: "yard", epc: EPC },
  ],
  blocked: [{ id: "r9", roll_no: "RL-0009", length_remaining: 20, unit: "yard", reason: "Roll RL-0009 sedang Karantina QC" }],
};
const WH = [{ id: "w1", name: "Gudang Simpan", code: "GS" }];

describe("Issue makloon — mode lama tetap", () => {
  test("default 'Berdasarkan jumlah': onConfirm(wh, uom, qty) tanpa daftar roll & tanpa memuat roll", async () => {
    const onConfirm = jest.fn(() => Promise.resolve());
    await mount(<IssueModal step={STEP} warehouses={WH} defaultWh="w1" busy={false} mkoId="mko1"
      onClose={() => {}} onConfirm={onConfirm} />);
    expect(q("mko-issue-mode").value).toBe("qty");
    expect(q("mko-issue-roll-picker")).toBeNull();
    await act(async () => { q("mko-issue-confirm").click(); });
    expect(onConfirm).toHaveBeenCalledWith("w1", "", "");
    expect(axios.get.mock.calls.some(([u]) => String(u).includes("issue-rolls"))).toBe(false);
  });
  test("tanpa mkoId (pemanggil lama) pilihan mode tidak muncul", async () => {
    await mount(<IssueModal step={STEP} warehouses={WH} defaultWh="w1" busy={false} onClose={() => {}} onConfirm={jest.fn()} />);
    expect(q("mko-issue-mode")).toBeNull();
  });
});

describe("Issue makloon — mode 'Pilih roll'", () => {
  test("centang + pindai nomor roll / EPC → total & onConfirm membawa id roll", async () => {
    axios.get.mockResolvedValue({ data: ROLLS });
    const onConfirm = jest.fn(() => Promise.resolve());
    await mount(<IssueModal step={STEP} warehouses={WH} defaultWh="w1" busy={false} mkoId="mko1"
      onClose={() => {}} onConfirm={onConfirm} />);
    await choose(q("mko-issue-mode"), "rolls");
    expect(axios.get).toHaveBeenCalledWith("/api/makloon-orders/mko1/steps/1/issue-rolls", { params: { warehouse_id: "w1" } });
    expect(q("mko-issue-rolls").textContent).toContain("RL-0003");
    expect(q("mko-issue-confirm").disabled).toBe(true);                     // belum ada roll terpilih
    await act(async () => { q("mko-issue-roll-r1").click(); });
    expect(q("mko-issue-pick-total").textContent).toMatch(/1 roll/);
    expect(q("mko-issue-pick-total").textContent).toMatch(/berbeda dari rencana/);   // 25 ≠ rencana 50
    await type(q("mko-issue-scan"), "rl-0002  e200-0000-0000-0000-0000-abcd, RL-0009 TIDAK-ADA");
    await act(async () => { q("mko-issue-scan-apply").click(); });
    expect(q("mko-issue-roll-r2").checked).toBe(true);
    expect(q("mko-issue-roll-r3").checked).toBe(true);
    const msg = q("mko-issue-scan-msg").textContent;
    expect(msg).toContain("2 roll dicentang");
    expect(msg).toContain("RL-0009: Roll RL-0009 sedang Karantina QC");    // alasan tertahan dari server
    expect(msg).toContain("TIDAK-ADA: tidak ada di gudang sumber");
    expect(q("mko-issue-pick-total").textContent).toMatch(/3 roll/);
    await act(async () => { q("mko-issue-confirm").click(); });
    await flush();
    expect(onConfirm).toHaveBeenCalledWith("w1", "", "", ["r1", "r2", "r3"]);
  });

  test("Enter di kotak pindai mencentang (tidak mengirim form)", async () => {
    axios.get.mockResolvedValue({ data: ROLLS });
    const onConfirm = jest.fn(() => Promise.resolve());
    await mount(<IssueModal step={STEP} warehouses={WH} defaultWh="w1" busy={false} mkoId="mko1"
      onClose={() => {}} onConfirm={onConfirm} />);
    await choose(q("mko-issue-mode"), "rolls");
    await type(q("mko-issue-scan"), "RL-0001");
    await act(async () => {
      q("mko-issue-scan").dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    });
    expect(q("mko-issue-roll-r1").checked).toBe(true);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  test("gagal memuat roll → ErrorNotice di DALAM pop-up; galat issue tampil di kaki pop-up", async () => {
    axios.get.mockRejectedValueOnce({ response: { status: 403, data: { detail: "Gudang ini bukan milik PT Anda." } } });
    const onConfirm = jest.fn(() => Promise.reject(new Error("Roll RL-0001 berubah di proses lain")));
    await mount(<IssueModal step={STEP} warehouses={WH} defaultWh="w1" busy={false} mkoId="mko1"
      onClose={() => {}} onConfirm={onConfirm} />);
    await choose(q("mko-issue-mode"), "rolls");
    const notice = q("mko-issue-rolls-error");
    expect(notice).not.toBeNull();
    expect(notice.textContent).toContain("Gudang ini bukan milik PT Anda.");
    expect(q("mko-issue-modal").contains(notice)).toBe(true);
    axios.get.mockResolvedValue({ data: ROLLS });
    await act(async () => { q("mko-issue-rolls-error-retry").click(); });   // Coba lagi
    await flush();
    expect(q("mko-issue-rolls-error")).toBeNull();
    await act(async () => { q("mko-issue-pick-all").click(); });
    await act(async () => { q("mko-issue-confirm").click(); });
    await flush();
    expect(q("mko-issue-modal-error").textContent).toBe("Roll RL-0001 berubah di proses lain");
  });
});

describe("Terima hasil — langkah terakhir dikarantina", () => {
  test("catatan karantina QC tampil bila server menandai langkah terakhir", async () => {
    await mount(<ReceiveModal step={{ ...STEP, receipt_qc_expected: true }} warehouses={WH} defaultWh="w1" mkoNumber="MKO-1"
      busy={false} onClose={() => {}} onConfirm={jest.fn()} />);
    expect(q("mko-recv-qc-note").textContent).toMatch(/karantina QC/);
  });
  test("langkah tengah: tanpa catatan karantina", async () => {
    await mount(<ReceiveModal step={STEP} warehouses={WH} defaultWh="w1" mkoNumber="MKO-1"
      busy={false} onClose={() => {}} onConfirm={jest.fn()} />);
    expect(q("mko-recv-qc-note")).toBeNull();
  });
});

describe("Pencocokan kode pindai", () => {
  test("EPC kanonik (tanpa pemisah, huruf besar) & nomor roll tanpa peka huruf", () => {
    expect(canonCode(" e200-0000:0000.0000_0000 abcd ")).toBe(EPC);
    // Banyak kode sekaligus dipisah baris/spasi/koma (tempel dari pembaca RFID / daftar SJ).
    expect(matchCodes("rl-0001\ne200:0000:0000:0000:0000:abcd , X-9", ROLLS.rolls)).toEqual({ hit: ["r1", "r3"], miss: ["X-9"] });
    expect(matchCodes("E2000000000000000000ABCD;r2;RL-0001;RL-0001", ROLLS.rolls)).toEqual({ hit: ["r3", "r2", "r1"], miss: [] });
  });
  test("pemilih roll memakai komponen baku (ErrorNotice, QtyDual) tanpa pendengar papan tombol sendiri", () => {
    const src = fs.readFileSync(path.join(__dirname, "../purchasing/makloon/MkoIssueRollPicker.jsx"), "utf8");
    expect(src).toMatch(/<ErrorNotice message=/);
    expect(src).toMatch(/<QtyDual /);
    expect(src).not.toMatch(/addEventListener/);
    const ins = fs.readFileSync(path.join(__dirname, "../inspections/InspectionDetailPanel.jsx"), "utf8");
    expect(ins).toMatch(/isMakloonQc/);   // SPK hasil makloon ber-tugas QC memutus karantina (tanpa opsi Nota Debit)
  });
});
