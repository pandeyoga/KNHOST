// UAT 24 Okt — fase F0 (ANALISIS_TEMUAN_UAT_23OKT.md): bug pasti yang terbukti di uji alur nyata.
import React, { act, useState } from "react";
import { createRoot } from "react-dom/client";
import SampleSpecFields, { EMPTY_SPEC } from "../rnd/SampleSpecFields";

jest.mock("../catalog/catalogApi", () => {
  const rows = [{ id: "tpl1", name: "KATUN POLOS", status: "active", fabric_type: "woven", sku_prefix: "KNWVN0001" }];
  return { catalogApi: { list: (p) => Promise.resolve(p && p.paginate ? { items: rows } : rows), detail: () => Promise.resolve({}) },
    catalogError: () => "galat" };
});
jest.mock("../../components/KNSelect", () => (props) => <select data-testid={props["data-testid"]} />);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const wait = (ms) => act(async () => { await new Promise((r) => setTimeout(r, ms)); });
const q = (id) => document.querySelector(`[data-testid="${id}"]`);

let lastSp = null;
function Harness() {
  const [sp, setSp] = useState({ ...EMPTY_SPEC });
  lastSp = sp;
  return <SampleSpecFields sp={sp} setSp={setSp} catalog={{}} setCatalog={() => {}} f={{}} set={() => {}}
    sampleTypes={["proofing"]} types={[{ value: "proofing", requires_design: true }]} colors={[]} designs={[]} />;
  // UAT 24 Okt (P4.5) — kain dasar kini hanya untuk proofing/printing (labdip saja → tanpa desain & kain dasar).
}

test("P4.8 — memilih kain dasar di form sampel menyimpan id + nama (bukan objek) dan tidak membuat layar galat", async () => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<Harness />); });
  await act(async () => { q("sample-spec-base-fabric-trigger").click(); });
  await wait(400);
  await act(async () => { q("sample-spec-base-fabric-option-tpl1").click(); });
  await wait(20);
  expect(lastSp.base_fabric_template_id).toBe("tpl1");
  expect(lastSp.base_fabric_name).toBe("KATUN POLOS");
  expect(q("sample-spec-base-fabric-value").textContent).toBe("KATUN POLOS");
  act(() => root.unmount());
});

// P16.1b — Rekonsiliasi GRN sebelum "Selesai hitung" tidak boleh menulis "Tidak ada selisih — cocok".
jest.mock("../wms/grn/grnApi", () => ({ ACTION_LABEL: {}, KIND_LABEL: {}, allowedActions: () => [], errText: () => "", grnApi: { post: jest.fn() } }));
const GrnReconPanel = require("../wms/grn/GrnReconPanel").default;

test("P16.1b — rekonsiliasi saat masih menghitung menampilkan selisih sementara, bukan 'cocok'", async () => {
  const line = { line_no: 1, target: { unit: "yard", product_name: "Kain" }, converted: { qty: 1000 }, declared: { rolls: 4 },
    counted: { qty: 50, rolls: 2 }, recon: {} };
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<GrnReconPanel grn={{ id: "g1", status: "counting", lines: [line], discrepancies: [] }} onChange={() => {}} canReview canClose />); });
  expect(host.textContent).not.toMatch(/Tidak ada selisih/);
  expect(q("grn-recon-pending").textContent).toMatch(/Selesai hitung/);
  expect(q("grn-recon-pending-rows").textContent).toMatch(/950 yard · 2 roll/);
  await act(async () => { root.render(<GrnReconPanel grn={{ id: "g1", status: "reconcile", lines: [{ ...line, counted: { qty: 1000, rolls: 4 } }], discrepancies: [] }} onChange={() => {}} canReview canClose />); });
  expect(host.textContent).toMatch(/Tidak ada selisih/);
  act(() => root.unmount());
});
