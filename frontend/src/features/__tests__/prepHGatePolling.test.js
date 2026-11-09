// PREP-H — polling layar gate: berhenti saat tab tersembunyi, langsung segar saat terlihat lagi, mundur bertahap
// (×2 s.d. batas) saat galat lalu kembali normal, tidak menumpuk permintaan; layar gate memakai hook ini.
import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";

import usePolling, { nextDelay } from "../rfid/usePolling";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
let visibility = "visible";
Object.defineProperty(document, "visibilityState", { configurable: true, get: () => visibility });
const setVisible = (v) => { visibility = v; document.dispatchEvent(new Event("visibilitychange")); };

function Probe({ fn, intervalMs = 1000, maxMs = 8000, enabled = true }) {
  usePolling(fn, { intervalMs, maxMs, enabled });
  return null;
}

let host; let root;
async function mount(el) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root.render(el);
    for (let i = 0; i < 10; i += 1) await Promise.resolve();
  });
}
async function advance(ms) {
  await act(async () => {
    jest.advanceTimersByTime(ms);
    for (let i = 0; i < 10; i += 1) await Promise.resolve();   // tuntaskan rantai await di dalam tick
  });
}

beforeEach(() => { jest.useFakeTimers(); visibility = "visible"; });
afterEach(async () => { await act(async () => root?.unmount()); host?.remove(); jest.useRealTimers(); });

test("nextDelay: berhasil → interval dasar; gagal → dobel s.d. batas", () => {
  expect(nextDelay(1000, 1000, 8000, false)).toBe(2000);
  expect(nextDelay(4000, 1000, 8000, false)).toBe(8000);
  expect(nextDelay(8000, 1000, 8000, false)).toBe(8000);
  expect(nextDelay(8000, 1000, 8000, true)).toBe(1000);
});

test("berhenti saat tab tersembunyi dan langsung memuat saat terlihat lagi", async () => {
  const fn = jest.fn(async () => {});
  await mount(<Probe fn={fn} />);
  expect(fn).toHaveBeenCalledTimes(1);           // segera saat dipasang
  await advance(1000);
  expect(fn).toHaveBeenCalledTimes(2);
  await act(async () => setVisible("hidden"));
  await advance(10000);
  expect(fn).toHaveBeenCalledTimes(2);           // tersembunyi → tidak ada permintaan
  await act(async () => setVisible("visible"));
  await advance(0);
  expect(fn).toHaveBeenCalledTimes(3);           // terlihat → langsung segar
  await advance(1000);
  expect(fn).toHaveBeenCalledTimes(4);
});

test("galat → mundur bertahap, berhasil → kembali ke interval normal", async () => {
  let fail = true;
  const fn = jest.fn(async () => { if (fail) throw new Error("x"); });
  await mount(<Probe fn={fn} />);
  expect(fn).toHaveBeenCalledTimes(1);           // gagal ke-1 → jeda 2000
  await advance(1999);
  expect(fn).toHaveBeenCalledTimes(1);
  await advance(1);
  expect(fn).toHaveBeenCalledTimes(2);           // gagal ke-2 → jeda 4000
  await advance(4000);
  expect(fn).toHaveBeenCalledTimes(3);           // gagal ke-3 → jeda 8000 (batas)
  await advance(8000);
  expect(fn).toHaveBeenCalledTimes(4);
  fail = false;
  await advance(8000);
  expect(fn).toHaveBeenCalledTimes(5);           // berhasil → kembali 1000
  await advance(1000);
  expect(fn).toHaveBeenCalledTimes(6);
});

test("tidak aktif → tanpa permintaan; layar gate memakai usePolling (bukan setInterval jaringan)", async () => {
  const fn = jest.fn(async () => {});
  await mount(<Probe fn={fn} enabled={false} />);
  await advance(10000);
  expect(fn).not.toHaveBeenCalled();
  const dir = path.join(__dirname, "../rfid");
  for (const f of ["GateLiveVerdict.jsx", "RfidGateMonitorView.jsx", "U300Operations.jsx", "GateReviewQueue.jsx"]) {
    const src = fs.readFileSync(path.join(dir, f), "utf8");
    expect(src).toMatch(/usePolling\(/);
    expect(src).not.toMatch(/setInterval\((load|loadReads)\b/);
  }
});
