// UAT 24 Okt — fase F1 (P8): gerbang "Mulai jualan" — lokasi + pelanggan wajib sebelum katalog.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import PosStartGate from "../pos/PosStartGate";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
jest.mock("../../components/KNSelect", () => (props) => (
  <select data-testid={props["data-testid"]} value={props.value} onChange={(e) => props.onValueChange(e.target.value)}>
    <option value="">-</option>
    {(props.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
  </select>
));
const axios = require("../../services/apiClient").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.querySelector(`[data-testid="${id}"]`);
const wait = (ms) => act(async () => { await new Promise((r) => setTimeout(r, ms)); });
const change = (el, v) => act(async () => { el.value = v; el.dispatchEvent(new Event("change", { bubbles: true })); });

test("P8 — 'Buka katalog' terkunci sampai lokasi & pelanggan dipilih; lokasi bawaan = lokasi akun; walk-in tersedia", async () => {
  axios.get.mockImplementation(() => Promise.resolve({ data: { sites: [{ id: "s_jkt", name: "Jakarta", city: "Jakarta" }, { id: "s_rcm", name: "Rancamalang", city: "Bandung" }] } }));
  const onStart = jest.fn();
  const customers = [{ id: "c1", name: "Konveksi Maju", code: "C1" }, { id: "cw", name: "Pelanggan Umum (Walk-in)", shared_walk_in: true }];
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<PosStartGate user={{ location_site_ids: ["s_jkt"] }} customers={customers} onStart={onStart} onCreateCustomer={() => {}} />); });
  await wait(10);
  expect(q("pos-gate-site").value).toBe("s_jkt");                 // lokasi akun jadi bawaan
  expect(q("pos-gate-start").disabled).toBe(true);                 // pelanggan belum dipilih
  expect(q("pos-gate-site").textContent).toMatch(/Rancamalang · Bandung/);
  expect(q("pos-gate-site").textContent).not.toMatch(/Jakarta · Jakarta/);
  await act(async () => { q("pos-gate-walkin").click(); });
  expect(q("pos-gate-start").disabled).toBe(false);
  await act(async () => { q("pos-gate-start").click(); });
  expect(onStart).toHaveBeenCalledWith({ siteId: "s_jkt", customer: customers[1] });
  await change(q("pos-gate-customer"), "c1");
  await change(q("pos-gate-site"), "s_rcm");
  await act(async () => { q("pos-gate-start").click(); });
  expect(onStart).toHaveBeenLastCalledWith({ siteId: "s_rcm", customer: customers[0] });
  act(() => root.unmount());
});
