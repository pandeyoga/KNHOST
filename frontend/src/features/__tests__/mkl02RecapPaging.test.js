// AUD-MKL-02 (review 2026-10-19) — rincian rekap klaim mitra tidak dipotong diam-diam: layar menampilkan
// rentang "a–b dari N", berpindah halaman lewat rows_offset, dan memberi tahu bahwa Excel memuat semua rincian.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import MakloonClaimRecapView from "../purchasing/makloon/MakloonClaimRecapView";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
const axios = require("../../services/apiClient").default;

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const TOTAL = 450;
const row = (i) => ({ kind: "susut", mko_id: `m${i}`, mko_number: `MKO-${i}`, step_seq: 1, makloon_id: "mk1",
  makloon_name: "Mitra A", status: "posted", at: "2026-10-15", qty: 1, unit: "kg", expense: 0, claim: 10, settle: "tagih_ganti" });

test("MKL-02: rentang rincian + total jelas, halaman berikutnya memakai rows_offset", async () => {
  axios.get.mockImplementation((_url, { params }) => {
    const off = params.rows_offset || 0;
    const n = Math.max(0, Math.min(params.rows_limit, TOTAL - off));
    return Promise.resolve({ data: { partners: [], totals: { receivable_total: 4500 }, rows_total: TOTAL, rows_offset: off,
      rows_limit: params.rows_limit, rows: Array.from({ length: n }, (_, i) => row(off + i)) } });
  });
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<MakloonClaimRecapView selectedEntity="ent_ksc" />); });
  await flush();
  expect(axios.get.mock.calls[0][1].params).toMatchObject({ rows_offset: 0, rows_limit: 200 });
  expect(q(host, "recap-rows-range").textContent).toMatch(/1–200 dari 450/);
  expect(q(host, "recap-rows-range").textContent).toContain("Excel memuat semua rincian");
  expect(q(host, "recap-rows-prev").disabled).toBe(true);
  await act(async () => { q(host, "recap-rows-next").click(); });
  await flush();
  expect(axios.get.mock.calls.at(-1)[1].params.rows_offset).toBe(200);
  expect(q(host, "recap-rows-range").textContent).toMatch(/201–400 dari 450/);
  await act(async () => { q(host, "recap-rows-next").click(); });
  await flush();
  expect(q(host, "recap-rows-range").textContent).toMatch(/401–450 dari 450/);
  expect(q(host, "recap-rows-next").disabled).toBe(true);
  expect(host.querySelectorAll('[data-testid^="recap-row-"]').length).toBe(50);
  await act(async () => { root.unmount(); });
});
