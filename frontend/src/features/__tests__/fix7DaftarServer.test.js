/**
 * FIX-7 (audit WMS-RFID 9 Nov 2026 — B3b LST-01/07/09) — daftar berbatas server di layar:
 *  · LST-09 — Antrean periksa gate memakai kursor `next_before`: "Muat lebih lama" menambah kasus lama (dulu baris
 *    ke-101 dst. tak terjangkau);
 *  · LST-01 — riwayat opname RFID menyebut jumlah sungguhan + "Muat berikutnya" (`skip` = sudah dimuat); galat muat tidak
 *    lagi ditelan (LST-06);
 *  · LST-01/07 — kotak persetujuan meminta HANYA sesi opname `submitted` dari server dan membaca `item_count` (baris
 *    daftar sesi tidak lagi memuat `items` utuh).
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import GateReviewQueue from "../rfid/GateReviewQueue";
import CycleCountPanel from "../rfid/CycleCountPanel";
import { loadInbox } from "../approvals/approvalInboxData";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(), put: jest.fn(), patch: jest.fn(), delete: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
jest.mock("../../config/roles", () => ({ canCurrent: jest.fn(() => true), can: jest.fn(() => true) }));
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
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
let host; let root;
async function mount(el) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(el); });
  await flush(); await flush();
}
afterEach(async () => {
  if (root) await act(async () => { root.unmount(); });
  host?.remove(); root = null;
  document.body.innerHTML = "";
  jest.clearAllMocks();
});
const $ = (sel) => document.body.querySelector(sel);
const click = async (el) => { await act(async () => { el.click(); }); await flush(); await flush(); };

const kase = (id, at) => ({ case_id: id, kind: "passage", status: "open", verdict: "REVIEW", direction: "in",
  device_name: "Gate IN", created_at: at, reason_codes: [], sources: [], rolls: [] });

test("LST-09: antrean periksa gate memuat kasus lebih lama lewat kursor next_before", async () => {
  axios.get.mockImplementation((url, cfg = {}) => {
    if (/reviews\/summary/.test(url)) return Promise.resolve({ data: { open: 101, red: 0, review: 101 } });
    if (/reviews/.test(url) && cfg.params?.before) {
      return Promise.resolve({ data: { reviews: [kase("old1", "2026-10-01T00:00:00Z")], next_before: null } });
    }
    return Promise.resolve({ data: { reviews: [kase("new1", "2026-11-09T00:00:00Z")], next_before: "2026-11-09T00:00:00Z" } });
  });
  await mount(<GateReviewQueue whId="" devices={[]} />);
  expect($('[data-testid="gate-review-row-new1"]')).not.toBeNull();
  const btn = $('[data-testid="gate-review-more-btn"]');
  expect(btn).not.toBeNull();
  await click(btn);
  const call = axios.get.mock.calls.find(([u, c]) => /reviews$/.test(u) && c?.params?.before);
  expect(call[1].params).toMatchObject({ before: "2026-11-09T00:00:00Z", status: "open", limit: 100 });
  expect($('[data-testid="gate-review-row-old1"]')).not.toBeNull();
  expect($('[data-testid="gate-review-row-new1"]')).not.toBeNull();
  expect($('[data-testid="gate-review-more"]')).toBeNull();   // kursor habis → tombol hilang
});

test("LST-01: riwayat opname RFID menyebut jumlah sungguhan & memuat berikutnya dengan skip", async () => {
  const row = (i) => ({ id: `cc${i}`, cc_number: `CC-${i}`, warehouse_name: "Jakarta", created_at: "2026-11-01T00:00:00Z",
    created_by: "x", accuracy_pct: 100, missing_count: 0, extra_count: 0 });
  axios.get.mockImplementation((url, cfg = {}) => {
    if (/rfid\/cycle-counts/.test(url)) {
      const skip = cfg.params?.skip || 0;
      return Promise.resolve({ data: { counts: skip ? [row(31)] : Array.from({ length: 30 }, (_, i) => row(i)),
        total: 31, truncated: !skip, skip, limit: 30 } });
    }
    return Promise.resolve({ data: {} });
  });
  await mount(<CycleCountPanel whId="wh1" selectedEntity="all" />);
  const note = $('[data-testid="cc-rfid-limit"]');
  expect(note).not.toBeNull();
  expect(note.textContent).toMatch(/1–30 dari\s*31/);
  await click($('[data-testid="cc-rfid-limit-more"]'));
  const call = axios.get.mock.calls.find(([u, c]) => /rfid\/cycle-counts/.test(u) && c?.params?.skip);
  expect(call[1].params).toMatchObject({ skip: 30, warehouse_id: "wh1" });
  expect($('[data-testid="cc-rfid-limit"]')).toBeNull();   // semua 31 sudah dimuat
});

test("LST-06: galat muat riwayat opname RFID tampil (tidak ditelan)", async () => {
  axios.get.mockImplementation(() => Promise.reject({ response: { data: { detail: "Server sibuk" } } }));
  await mount(<CycleCountPanel whId="wh1" selectedEntity="all" />);
  expect($('[data-testid="cc-error"]')?.textContent || "").toMatch(/Server sibuk/);
});

test("LST-01/07: kotak persetujuan meminta sesi opname submitted dari server & membaca item_count", async () => {
  axios.get.mockImplementation((url) => {
    if (/cycle-count\/sessions/.test(url)) {
      return Promise.resolve({ data: [{ id: "s1", status: "submitted", name: "Opname A", warehouse_name: "Jakarta",
        item_count: 7, created_at: "2026-11-01T00:00:00Z" }] });
    }
    return Promise.resolve({ data: [] });
  });
  const res = await loadInbox();
  const call = axios.get.mock.calls.find(([u]) => /cycle-count\/sessions/.test(u));
  expect(call[1]?.params).toMatchObject({ status: "submitted" });
  const items = res.items || [];
  const cyc = items.find((x) => x.kind === "cycle");
  expect(cyc.meta).toBe("7 item dihitung");
});
