// FIX-3b (audit 9 Nov B2b/B3b) — layar keluar: ambil HP WAJIB pindai roll (ketik qty = jalur darurat + alasan,
// K-B1-05/K-B3b-01), tugas dieskalasi tanpa aksi (STM-OUT-2), cek muat: EPC tempel manual bukan bukti (K-B3b-02) +
// batal sesi (FLW-OUT-6) + reader gate OUT tidak sehat (RFID-12).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { OutboundActions } from "../mobile/MobileTaskActions";
import LoadingCheckPanel from "../wms/LoadingCheckPanel";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(), patch: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
jest.mock("../../utils/offlineQueue", () => ({ offlinePost: jest.fn(() => Promise.resolve({ data: {} })) }));
jest.mock("../wms/PickListPanel", () => ({ task, onPick }) => (
  <button data-testid={`pl-${task.id}`} onClick={() => onPick("RL-0007")}>pick list</button>
));
jest.mock("../../hooks/useReceivingMode", () => () => ({ isGrn: () => false, data: {} }));
jest.mock("../../hooks/useDomainEnums", () => () => ({ options: () => [], labelOf: (_k, v) => v }));
const axios = require("../../services/apiClient").default;
const { offlinePost } = require("../../utils/offlineQueue");

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
const typeInto = async (el, v) => {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, v);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
};

test("HP Ambil: wajib pindai roll — tanpa isian qty bawaan; kirim kode roll, bukan qty", async () => {
  offlinePost.mockClear();
  const task = { id: "t1", status: "created", quantity: 20, picked_qty: 0, unit: "yard" };
  const host = await mount(<OutboundActions task={task} onDone={() => {}} />);
  expect(q(host, "mw-pick-qty-t1")).toBeNull();                  // qty tidak lagi jalur utama
  expect(q(host, "mw-pick-btn-t1").disabled).toBe(true);
  await act(async () => { q(host, "pl-t1").click(); });         // pilih dari daftar roll → kode terisi
  expect(q(host, "mw-pick-code-t1").value).toBe("RL-0007");
  await act(async () => { q(host, "mw-pick-btn-t1").click(); });
  await flush();
  const [, , opts] = offlinePost.mock.calls[0];
  expect(opts.params).toEqual({ roll_id: "RL-0007" });
});

test("HP Ambil darurat: qty + alasan ≥ 5 huruf, terkirim sebagai jalur darurat", async () => {
  offlinePost.mockClear();
  const task = { id: "t2", status: "picking", quantity: 20, picked_qty: 5, unit: "yard" };
  const host = await mount(<OutboundActions task={task} onDone={() => {}} />);
  await act(async () => { q(host, "mw-pick-emergency-toggle-t2").click(); });
  await typeInto(q(host, "mw-pick-qty-t2"), "5,5");
  await typeInto(q(host, "mw-pick-reason-t2"), ".....");
  expect(q(host, "mw-pick-emergency-btn-t2").disabled).toBe(true);   // tanda baca bukan alasan
  await typeInto(q(host, "mw-pick-reason-t2"), "label rusak scanner mati");
  expect(q(host, "mw-pick-emergency-btn-t2").disabled).toBe(false);
  await act(async () => { q(host, "mw-pick-emergency-btn-t2").click(); });
  await flush();
  expect(offlinePost.mock.calls[0][2].params).toEqual({ actual_qty: 5.5, reason: "label rusak scanner mati" });
});

test("HP: tugas dieskalasi tidak menawarkan Ambil/Berangkatkan", async () => {
  const task = { id: "t3", status: "escalated", quantity: 20, picked_qty: 10, unit: "yard" };
  const host = await mount(<OutboundActions task={task} onDone={() => {}} />);
  expect(q(host, "mw-outbound-escalated-t3")).not.toBeNull();
  expect(q(host, "mw-pick-btn-t3")).toBeNull();
  expect(q(host, "mw-dispatch-btn-t3")).toBeNull();
});

test("cek muat: hasil EPC manual bukan bukti, reader gate tidak sehat tampil, sesi bisa dibatalkan", async () => {
  axios.get.mockImplementation(() => Promise.resolve({ data: {
    open_session: null, last_result: { result: "manual_unverified", matched: 1, expected: 1 }, last_scan_log: [],
    by_warehouse: [], rfid_simulation: false, untagged_rolls: [], gate_out_primary: false,
    gate_out_reason: "Reader gate OUT tidak sehat (DEV-1: Laporan terakhir 900 detik lalu) — cek muat handheld kembali WAJIB." } }));
  const host = await mount(<LoadingCheckPanel orderId="so1" warehouseId="wh1" soNumber="SO-1" />);
  expect(q(host, "lc-last-result").textContent).toContain("bukan bukti fisik");
  expect(q(host, "lc-gate-unhealthy").textContent).toContain("WAJIB");
  axios.post.mockImplementation(() => Promise.resolve({ data: { id: "rvs1", expected: [], untagged: [], status: "open" } }));
  await act(async () => { q(host, "lc-start").click(); });
  await flush();
  expect(q(host, "lc-scan").textContent).toContain("manual");
  const cancelBtn = q(host, "lc-cancel");
  expect(cancelBtn.disabled).toBe(true);
  await typeInto(q(host, "lc-cancel-reason"), "salah mulai sesi");
  expect(cancelBtn.disabled).toBe(false);
  await act(async () => { cancelBtn.click(); });
  await flush();
  expect(axios.post.mock.calls.some(([url, body]) => url === "/api/outbound/loading-check/rvs1/cancel" && body.reason === "salah mulai sesi")).toBe(true);
});
