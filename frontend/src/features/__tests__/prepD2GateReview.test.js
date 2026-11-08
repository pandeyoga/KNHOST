// PREP-D2 — antrean periksa gate V2 (AUD-MW-10) + kios kuning (K-RFID-09): daftar kuning/merah berbahasa Indonesia
// (tanpa kode mentah), rincian bukti per roll (antena, RSSI puncak, waktu), tindakan beralasan (FormModal, min. 5
// huruf) ke endpoint yang benar, tanpa izin approve tombol tindakan disembunyikan, akui kunci gate, layar kios KUNING.
import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";

import GateReviewQueue from "../rfid/GateReviewQueue";
import GateLiveVerdict, { gateStatusUrl } from "../rfid/GateLiveVerdict";
import { REASON, ROLL_STATE, codesText, reasonText } from "../rfid/u300Labels";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(), put: jest.fn(), patch: jest.fn(), delete: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
jest.mock("../../config/roles", () => ({ canCurrent: jest.fn(() => true) }));
jest.mock("../../components/KNSelect", () => {
  const Sel = ({ value, onValueChange, options = [], "data-testid": tid }) => (
    <select data-testid={tid} value={value} onChange={(e) => onValueChange?.(e.target.value)}>
      {options.map((o) => <option key={`${o.value}`} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: Sel, KNSelect: Sel };
});
const axios = require("../../services/apiClient").default;
const roles = require("../../config/roles");

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
let host; let root;
async function mount(el) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(el); });
  await flush();
}
beforeEach(() => { roles.canCurrent.mockImplementation(() => true); });   // CRA resetMocks: pasang ulang tiap uji
afterEach(async () => {
  if (root) await act(async () => { root.unmount(); });
  host?.remove(); root = null;
  document.body.innerHTML = "";
  jest.clearAllMocks();
});
const $ = (sel) => document.body.querySelector(sel);
const click = async (el) => { await act(async () => { el.click(); }); await flush(); };
const typeText = async (el, value) => {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new Event("input", { bubbles: true })); });
};

const CASE = {
  case_id: "c1", kind: "passage", status: "open", verdict: "REVIEW", direction: "in", device_name: "Gate IN Woven",
  created_at: "2026-11-09T03:00:00Z", reason_codes: ["AREA_FROZEN", "HANDHELD_MODE"], txn_mode: "gate",
  sources: [{ source_type: "putaway", source_id: "pa1", display_ref: "PA-0007" }], latch_open: false,
  reasons: [{ code: "CAPTURE_INCOMPLETE", level: "REVIEW", message: "Agent melaporkan bukti lintasan tidak lengkap." }],
  rolls: [
    { key: "r1", roll_id: "r1", roll_no: "R-001", epc: "E2001", state: "open", codes: ["AREA_FROZEN"],
      messages: ["Gudang sedang dibekukan."], source_ref: { display_ref: "PA-0007" }, actions: [],
      evidence: { peak_rssi: -48, count: 16, first_seen: "2026-11-09T03:00:01Z", last_seen: "2026-11-09T03:00:03Z",
        antennas: [{ antenna: "1", peak_rssi: -48, count: 8 }, { antenna: "2", peak_rssi: -51, count: 8 }] } },
    { key: "r2", roll_id: "r2", roll_no: "R-002", state: "recorded", codes: ["RECORDED"], actions: [], evidence: null },
  ],
};
const RED = { ...CASE, case_id: "c2", verdict: "RED", latch_open: true, latch_id: "L1", reason_codes: ["NO_DOCUMENT"] };

function mockApi(cases = [CASE, RED]) {
  axios.get.mockImplementation((url) => {
    if (url.endsWith("/reviews/summary")) return Promise.resolve({ data: { open: 2, red: 1, review: 1 } });
    if (url.endsWith("/reviews")) return Promise.resolve({ data: { reviews: cases } });
    const id = url.split("/").pop();
    return Promise.resolve({ data: cases.find((c) => c.case_id === id) });
  });
  axios.post.mockResolvedValue({ data: { case: CASE } });
}

test("antrean menampilkan kuning/merah berbahasa Indonesia tanpa kode mentah", async () => {
  mockApi();
  await mount(<GateReviewQueue whId="wh1" devices={[{ id: "d1", code: "G-IN" }]} />);
  const text = $("[data-testid='gate-review-queue']").textContent;
  expect(text).toContain("Kuning");
  expect(text).toContain("Merah");
  expect(text).toContain("gate terkunci");
  expect(text).toContain(REASON.AREA_FROZEN);
  expect(text).not.toMatch(/AREA_FROZEN|HANDHELD_MODE|NO_DOCUMENT|K-RFID|AUD-MW/);
  expect(axios.get).toHaveBeenCalledWith("/api/rfid/v2/ops/reviews", { params: { status: "open", limit: 100, warehouse_id: "wh1" } });
});

test("rincian: bukti per roll + terima beralasan memanggil endpoint terima", async () => {
  mockApi();
  await mount(<GateReviewQueue whId="" />);
  await click($("[data-testid='gate-review-open-c1']"));
  const detail = $("[data-testid='gate-review-detail']").textContent;
  expect(detail).toContain("R-001");
  expect(detail).toContain("-48.0 dBm");
  expect(detail).toContain("antena 2: -51.0 dBm");
  expect(detail).toContain(ROLL_STATE.recorded.label);
  expect(detail).toContain(reasonText("CAPTURE_INCOMPLETE"));
  expect(detail).not.toMatch(/CAPTURE_INCOMPLETE|AREA_FROZEN|RECORDED/);
  expect($("[data-testid='gate-review-accept']").disabled).toBe(true);           // belum ada roll dipilih
  expect($("[data-testid='gate-review-roll-r2'] input")).toBeNull();               // roll tercatat tidak bisa dipilih
  await click($("[data-testid='gate-review-roll-r1'] input"));
  await click($("[data-testid='gate-review-accept']"));
  expect($("[data-testid='gate-review-form-submit']").disabled).toBe(true);        // alasan wajib
  await typeText($("[data-testid='gate-review-reason']"), "Dicek fisik, roll ada");
  await click($("[data-testid='gate-review-form-submit']"));
  expect(axios.post).toHaveBeenCalledWith("/api/rfid/v2/ops/reviews/c1/rolls/accept",
    { roll_keys: ["r1"], reason: "Dicek fisik, roll ada" });
});

test("tolak, pindai ulang, dan akui kunci gate memakai endpoint masing-masing", async () => {
  mockApi();
  await mount(<GateReviewQueue whId="" />);
  await click($("[data-testid='gate-review-open-c2']"));
  expect($("[data-testid='gate-review-latch']").textContent).toContain("TERKUNCI");
  expect($("[data-testid='gate-review-dismiss']").disabled).toBe(true);            // tutup kasus menunggu kunci diakui
  await click($("[data-testid='gate-review-ack']"));
  await typeText($("[data-testid='gate-review-reason']"), "roll asing dikembalikan");
  await click($("[data-testid='gate-review-form-submit']"));
  expect(axios.post).toHaveBeenCalledWith("/api/rfid/v2/ops/reviews/c2/acknowledge-latch", { note: "roll asing dikembalikan" });
  await click($("[data-testid='gate-review-roll-r1'] input"));
  await click($("[data-testid='gate-review-reject']"));
  await typeText($("[data-testid='gate-review-reason']"), "roll tertinggal");
  await click($("[data-testid='gate-review-form-submit']"));
  expect(axios.post).toHaveBeenCalledWith("/api/rfid/v2/ops/reviews/c2/rolls/reject",
    { roll_keys: ["r1"], reason: "roll tertinggal", mode: "reject" });
  await click($("[data-testid='gate-review-roll-r1'] input"));
  await click($("[data-testid='gate-review-rescan']"));
  await typeText($("[data-testid='gate-review-reason']"), "pindai ulang di rak R2");
  await click($("[data-testid='gate-review-form-submit']"));
  expect(axios.post).toHaveBeenCalledWith("/api/rfid/v2/ops/reviews/c2/rolls/rescan",
    { roll_keys: ["r1"], note: "pindai ulang di rak R2" });
});

test("tanpa izin approve: tidak ada tombol tindakan, ada petunjuk", async () => {
  roles.canCurrent.mockImplementation((m, a) => !(m === "wms" && a === "approve"));
  mockApi();
  await mount(<GateReviewQueue whId="" />);
  await click($("[data-testid='gate-review-open-c2']"));
  expect($("[data-testid='gate-review-actions']")).toBeNull();
  expect($("[data-testid='gate-review-ack']")).toBeNull();
  expect($("[data-testid='gate-review-detail']").textContent).toContain("izin persetujuan gudang");
});

test("kios V2: KUNING tampil di samping hijau/merah, barang jalan tanpa kunci", async () => {
  expect(gateStatusUrl("d1", "v2")).toBe("/api/rfid/v2/ops/devices/d1/kiosk");
  expect(gateStatusUrl("d1", undefined)).toBe("/api/rfid/gate/d1/status");
  const status = {
    state: "yellow", fetchAge: 1, fetchError: "", reload: jest.fn(),
    data: { protocol: "v2", latched: false, device: { id: "d1", heartbeat_age_s: 3 },
      passage: { id: "p1", verdict: "yellow", started_at: "2026-11-09T03:00:00Z", red_count: 0, yellow_count: 1,
        green_count: 2, reads: [{ id: "r1", roll_no: "R-001", result: "yellow", reason: "Area beku", action: "Barang jalan" }] } },
  };
  await mount(<GateLiveVerdict gate={{ code: "G-IN" }} status={status} />);
  expect($("[data-testid='rfid-kiosk-verdict']").textContent).toContain("KUNING");
  expect($("[data-testid='rfid-kiosk-yellow-note']").textContent).toContain("gate tidak terkunci");
  expect($("[data-testid='rfid-passage-summary']").textContent).toContain("kuning 1");
  expect($("[data-testid='rfid-passage-ack-box']")).toBeNull();
});

test("kios V2 merah terkunci: buka kunci lewat endpoint kunci gate V2 (izin approve)", async () => {
  axios.post.mockResolvedValue({ data: {} });
  const status = {
    state: "red", fetchAge: 1, fetchError: "", reload: jest.fn(),
    data: { protocol: "v2", latched: true, latch_id: "L9", gate_id: "G1", device: { id: "d1", heartbeat_age_s: 3 },
      passage: { id: "p2", verdict: "red", red_count: 1, yellow_count: 0, green_count: 0, reads: [] } },
  };
  await mount(<GateLiveVerdict gate={{ code: "G-OUT" }} status={status} />);
  const input = $("[data-testid='rfid-passage-ack-note']");
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  await act(async () => { setter.call(input, "dicek satpam & admin"); input.dispatchEvent(new Event("input", { bubbles: true })); });
  await click($("[data-testid='rfid-passage-ack']"));
  expect(axios.post).toHaveBeenCalledWith("/api/rfid/v2/ops/devices/d1/gate-latch/acknowledge",
    { device_id: "d1", logical_gate_id: "G1", latch_id: "L9", note: "dicek satpam & admin" });
});

test("label D2 lengkap, tab antrean ada di Monitor Gerbang, tanpa kode keputusan internal", () => {
  ["AREA_FROZEN", "HANDHELD_MODE", "GATE_NOT_PAIRED", "TXN_FAILED", "ARRIVAL_EXCEPTION", "RULE_BLOCKED",
    "NOT_RECORDED", "RECORDED", "ROLLS_MISSING"].forEach((c) => expect(REASON[c]).toBeTruthy());
  expect(codesText(["AREA_FROZEN", "AREA_FROZEN", "UNKNOWN_X"])).toBe(`${REASON.AREA_FROZEN} · Alasan lain — lihat bukti lintasan`);
  const dir = path.join(__dirname, "../rfid");
  const monitor = fs.readFileSync(path.join(dir, "RfidGateMonitorView.jsx"), "utf8");
  expect(monitor).toContain('label: "Antrean periksa"');
  for (const f of ["GateReviewQueue.jsx", "GateReviewDetail.jsx", "u300Labels.js"]) {
    const src = fs.readFileSync(path.join(dir, f), "utf8");
    const code = src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");   // komentar boleh menyebut kode
    expect(code).not.toMatch(/K-RFID-\d|K-GDG-\d|AUD-MW-\d/);
    expect(src).toMatch(/FormModal|DetailModal|ROLL_STATE/);
  }
});
