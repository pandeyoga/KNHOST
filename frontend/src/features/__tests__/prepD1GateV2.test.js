// PREP-D1 — panel Integrasi reader U300 (gate V2): status kuning/merah/batal berbahasa Indonesia, daftar alasan
// (reason_codes) tanpa kode mentah, satu kunci per gate (catatan wajib → buka kunci dengan latch_id), sesi dokumen
// bertahap, simulator hanya admin, dan panel dibuka lewat DetailModal di layar Perangkat RFID.
import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";

import U300Operations from "../rfid/U300Operations";
import { REASON, SCENARIOS, reasonText, verdictInfo } from "../rfid/u300Labels";
import { setAccessContext } from "../../config/roles";

// PR-T7 — `canCurrent` kini "tidak" selama konteks izin belum dimuat; panel diuji sebagai Admin yang sudah masuk
// (hanya penyiapan uji; logika gerbang RFID tidak berubah).
beforeAll(() => setAccessContext({ role: "admin" }));
afterAll(() => setAccessContext(null));

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(), put: jest.fn(), patch: jest.fn(), delete: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
jest.mock("../../services/confirmService", () => ({ askConfirm: jest.fn(() => Promise.resolve(true)) }));
jest.mock("../../components/KNSelect", () => {
  const Sel = ({ value, onValueChange, options = [], "data-testid": tid }) => (
    <select data-testid={tid} value={value} onChange={(e) => onValueChange?.(e.target.value)}>
      {options.map((o) => <option key={`${o.value}`} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: Sel, KNSelect: Sel };
});
const axios = require("../../services/apiClient").default;

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
afterEach(async () => {
  if (root) await act(async () => { root.unmount(); });
  host?.remove(); root = null;
  jest.clearAllMocks();
});
const $ = (sel) => host.querySelector(sel);
const setValue = async (el, value) => {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new Event("input", { bubbles: true })); });
};

const decision = (verdict, reasons, extra = {}) => ({
  decision_id: `d-${verdict}`, verdict, reasons, reason_codes: reasons.map((r) => r.code),
  counts: { matched: 2, pending: 2, extra: 0, unknown: 0, weak: 1, background: 0 }, sources: [{ display_ref: "SJ-001" }],
  binding_mode: "auto", ...extra,
});
const OVERVIEW = {
  device_id: "dev1", protocol: "v2", contract_version: "2.1.0", config_version: "v1",
  config: { logical_gates: [{ logical_gate_id: "G1", direction: "out" }] },
  gate_parameters: { calibration_status: "initial", auto_match: true, rssi_default_strong_dbm: -65, pre_buffer_ms: 3000 },
  telemetry: { pending_event_count: 0, radio_state: "ready" },
  health: [{ rule: "READER_STOPPED", active: true, message: "Status radio: stopped" }, { rule: "TELEMETRY_STALE", active: false }],
  gate_latch: { latch_id: "L1", since: "2026-11-08T10:00:00Z", reason_codes: ["QUARANTINE"], passages: [{}] },
  bindings: [],
  sessions: [{ source_ref: { source_type: "shipment", source_id: "s1", display_ref: "SJ-001" }, direction: "out",
    total: 4, passed: 2, remaining: 2, status: "open", rolls: [{ roll_id: "r1", roll_no: "R-1", passed: true }, { roll_id: "r2", roll_no: "R-2", passed: false }] }],
  passages: [
    { local_passage_id: "p-red", created_at: "2026-11-08T10:00:00Z", state: "FINAL", acknowledged: false,
      decision: decision("RED", [{ code: "QUARANTINE", level: "RED" }, { code: "TIME_UNVERIFIED", level: "REVIEW" }]) },
    { local_passage_id: "p-review", created_at: "2026-11-08T10:01:00Z", state: "FINAL", acknowledged: false,
      decision: decision("REVIEW", [{ code: "CAPTURE_OVERFLOW", level: "REVIEW" }]) },
    { local_passage_id: "p-cancel", created_at: "2026-11-08T10:02:00Z", state: "FINAL", acknowledged: false,
      decision: decision("CANCELLED", [{ code: "EMPTY_PASSAGE", level: "INFO" }]) },
    { local_passage_id: "sim-full", created_at: "2026-11-08T10:03:00Z", state: "FINAL", simulated: true,
      decision: decision("GREEN", [], { reason_codes: ["MANIFEST_MATCH"] }) },
  ],
  next_cursor: null,
};

function mockApi(overview = OVERVIEW) {
  axios.get.mockImplementation((url) => {
    if (url.endsWith("/sources")) return Promise.resolve({ data: { sources: [{ id: "s1", label: "SJ-001", status: "dispatched" }] } });
    return Promise.resolve({ data: overview });
  });
  axios.post.mockResolvedValue({ data: { latch_released: true, latched: false, passages: [], as_expected: true } });
  require("../../services/confirmService").askConfirm.mockResolvedValue(true);   // CRA resetMocks: set ulang per tes
}

describe("PREP-D1 panel U300", () => {
  test("hasil & alasan tampil dalam istilah Indonesia, tanpa kode mentah", async () => {
    mockApi();
    await mount(<U300Operations device={{ id: "dev1", name: "Gate Keluar" }} isAdmin={false} />);
    expect($('[data-testid="u300-verdict-p-red"]').textContent).toBe("Merah");
    expect($('[data-testid="u300-verdict-p-review"]').textContent).toBe("Kuning");
    expect($('[data-testid="u300-verdict-p-cancel"]').textContent).toBe("Batal");
    expect($('[data-testid="u300-verdict-sim-full"]').textContent).toBe("Hijau");
    const red = $('[data-testid="u300-passage-p-red"]').textContent;
    expect(red).toContain("Roll karantina QC");
    expect(red).toContain("Waktu reader tidak tervalidasi");          // alasan kuning tidak tertimpa merah
    expect(red).not.toMatch(/QUARANTINE|TIME_UNVERIFIED/);
    expect($('[data-testid="u300-passage-p-review"]').textContent).toContain("barang jalan · gate tidak terkunci");
    expect($('[data-testid="u300-passage-sim-full"]').textContent).toContain("simulasi");
    expect($('[data-testid="u300-health-READER_STOPPED"]').textContent).toBe("Reader berhenti membaca");
    expect($('[data-testid="u300-protocol"]').textContent).toBe("Protokol U300 V2");
    expect($('[data-testid="u300-session-s1"]').textContent).toContain("2/4 roll lewat");
    expect($('[data-testid="u300-params"]').textContent).toContain("titik awal kalibrasi");
    expect($('[data-testid="u300-simulate"]')).toBeNull();                 // simulator hanya admin
    expect($('[data-testid="u300-ack-p-cancel"]')).toBeNull();             // lintasan batal tidak perlu tindak lanjut
  });

  test("satu kunci per gate: catatan ≥ 5 karakter lalu buka kunci dengan latch_id", async () => {
    mockApi();
    await mount(<U300Operations device={{ id: "dev1", name: "Gate Keluar" }} isAdmin />);
    expect($('[data-testid="u300-latch"]').textContent).toContain("Gate TERKUNCI");
    const btn = $('[data-testid="u300-latch-ack"]');
    expect(btn.disabled).toBe(true);
    await setValue(host.querySelector('input[aria-label="Catatan pemeriksaan kunci gate"]'), "dicek fisik ok");
    expect(btn.disabled).toBe(false);
    await act(async () => { btn.click(); });
    await flush();
    const call = axios.post.mock.calls.find(([u]) => u.endsWith("/gate-latch/acknowledge"));
    expect(call[1]).toMatchObject({ device_id: "dev1", latch_id: "L1", logical_gate_id: "G1", note: "dicek fisik ok" });
  });

  test("simulator admin mengirim skenario terpilih; galat server tampil lewat ErrorNotice", async () => {
    mockApi();
    await mount(<U300Operations device={{ id: "dev1", name: "Gate Keluar" }} isAdmin />);
    const sel = $('[data-testid="u300-scenario"]');
    await act(async () => { sel.value = "empty"; sel.dispatchEvent(new Event("change", { bubbles: true })); });
    axios.post.mockRejectedValueOnce({ response: { data: { detail: { code: "NO_DOCUMENT_ROLLS", message: "Tidak ada dokumen aktif" } } } });
    await act(async () => { $('[data-testid="u300-simulate"]').click(); });
    await flush(); await flush(); await flush();
    const call = axios.post.mock.calls.find(([u]) => u.endsWith("/simulate"));
    expect(call[1]).toEqual({ scenario: "empty" });
    expect(host.textContent).toContain("Tidak ada dokumen aktif");
  });

  test("tanpa profil V2: tidak ada kontrol gate", async () => {
    mockApi({ ...OVERVIEW, config: null, gate_latch: null, passages: [], sessions: [], protocol: "legacy" });
    await mount(<U300Operations device={{ id: "dev2", name: "Gate Lama" }} isAdmin />);
    expect($('[data-testid="u300-no-profile"]')).not.toBeNull();
    expect($('[data-testid="u300-latch"]')).toBeNull();
    expect($('[data-testid="u300-passages-empty"]')).not.toBeNull();
  });
});

describe("PREP-D1 label & integrasi layar", () => {
  test("label verdict, alasan, skenario lengkap", () => {
    expect(verdictInfo({ verdict: "REVIEW" }).color).toBe("orange");
    expect(verdictInfo(null, "OPEN").short).toBe("Merekam");
    expect(reasonText("TIDAK_ADA")).toMatch(/Alasan lain/);
    ["NOT_IN_DOCUMENT", "UNKNOWN_EPC", "REPLAY_EXIT", "CAPTURE_OVERFLOW", "EMPTY_PASSAGE", "ROLLS_MISSING", "SENSOR_FAULT"]
      .forEach((c) => expect(REASON[c]).toBeTruthy());
    expect(SCENARIOS.map((s) => s.value)).toEqual(["full_load", "partial_trip", "reversed", "reversed_with_rolls", "empty",
      "foreign_roll", "quarantine_roll", "background_tag", "overflow", "sensor_fault"]);
  });

  test("Perangkat RFID membuka panel U300 lewat DetailModal (bukan <details> mentah)", () => {
    const src = fs.readFileSync(path.join(__dirname, "../rfid/RfidDevicesView.jsx"), "utf8");
    expect(src).toMatch(/<DetailModal open=\{!!readerDevice\}/);
    expect(src).toMatch(/testId="rfid-u300-modal"/);
    expect(src).not.toMatch(/<details/);
    const ops = fs.readFileSync(path.join(__dirname, "../rfid/U300Operations.jsx"), "utf8");
    expect(ops).not.toMatch(/<select/);
    expect(ops).toMatch(/ErrorNotice/);
  });
});
