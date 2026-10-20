// AUD-RET-01 (review 2026-10-19) — buang BS yang terhenti di tengah tampil sebagai tahap tersendiri dan bisa
// DILANJUTKAN (tanpa alasan/foto baru — memakai keputusan awal); tahap lain tidak berubah.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { DispositionActionBar, DispositionRow } from "../sales/ReturnDispositionPanel";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
jest.mock("../sales/ReturnCameraButton", () => () => null);
const axios = require("../../services/apiClient").default;

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  return { host, root };
}
const ROW = { roll_id: "r1", roll_no: "RTN-1", stage: "supplier_dispose_failed", qty: 0, unit: "yard", status: "damaged",
  supplier: { decision: "dispose", status: "failed", error: "gangguan movement" } };

test("RET-01: baris terhenti bisa dipilih, menampilkan label & penyebab", async () => {
  const { host, root } = await mount(<table><tbody><DispositionRow r={ROW} checked={false} onToggle={() => {}} /></tbody></table>);
  expect(q(host, "disposition-stage-r1").textContent).toContain("terhenti");
  expect(q(host, "disposition-check-r1")).not.toBeNull();
  expect(q(host, "disposition-error-r1").textContent).toContain("gangguan movement");
  await act(async () => { root.unmount(); });
});

test("RET-01: tombol Lanjutkan mengirim keputusan buang untuk roll terpilih tanpa alasan/foto baru", async () => {
  axios.post.mockResolvedValue({ data: { decision: "dispose", resumed: true, writeoff_total: 1000 } });
  const onDone = jest.fn();
  const { host, root } = await mount(<DispositionActionBar returnId="ret1" imgs={[]} stage="supplier_dispose_failed"
    sel={["r1"]} rows={[ROW]} onDone={onDone} />);
  expect(q(host, "disposition-reason")).toBeNull();
  await act(async () => { q(host, "disposition-dispose-resume").click(); });
  expect(axios.post).toHaveBeenCalledWith("/api/sales-returns/ret1/disposition/supplier",
    expect.objectContaining({ roll_ids: ["r1"], decision: "dispose" }));
  expect(onDone).toHaveBeenCalled();
  await act(async () => { root.unmount(); });
});

test("RET-01: tahap 2 normal tetap meminta alasan & foto", async () => {
  const { host, root } = await mount(<DispositionActionBar returnId="ret1" imgs={[]} stage="supplier_pending"
    sel={["r1"]} rows={[{ ...ROW, stage: "supplier_pending" }]} onDone={() => {}} />);
  expect(q(host, "disposition-reason")).not.toBeNull();
  expect(q(host, "disposition-dispose").disabled).toBe(true);
  await act(async () => { root.unmount(); });
});
