// Keputusan owner 2026-10-21 — nota kredit otomatis dari batal item OD pada SO terbit: status & kelebihan bayar
// tampil di jejak SO; tombol Terbitkan / Koreksi nilai / Batalkan hanya untuk pemegang
// finance_amendment.review_credit_note selama nota menunggu Finance; koreksi & pembatalan wajib alasan.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import OdCancelNoteActions, { OdCancelNoteInfo } from "../finance/amendments/OdCancelNoteActions";
import { rowLink } from "../sales_admin/workDeskApi";

jest.mock("../finance/amendments/amendmentApi", () => ({ reviewCreditNote: jest.fn(), errText: (e, d) => d }));
const api = require("../finance/amendments/amendmentApi");

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const NOTE = { id: "cn1", number: "KSC/CN-00001", status: "pending_finance", gross_amount: 120000, excess_payment: 120000,
  source: "od_item_cancel", corrections: [] };
const FIN = { role: "finance", permissions: { finance_amendment: ["propose", "review_credit_note"] } };
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  return { host, root };
}

test("info: status menunggu Finance & kelebihan bayar", async () => {
  const { host, root } = await mount(<OdCancelNoteInfo note={NOTE} />);
  expect(q(host, "od-note-status-cn1").textContent).toBe("Menunggu Finance");
  expect(q(host, "od-note-excess-cn1").textContent).toMatch(/Kelebihan bayar/);
  await act(async () => { root.unmount(); });
});

test("Finance: terbitkan langsung; koreksi butuh alasan ≥5 huruf lalu dikirim sebagai adjust", async () => {
  api.reviewCreditNote.mockResolvedValue({ ...NOTE, status: "issued" });
  const onDone = jest.fn();
  const { host, root } = await mount(<OdCancelNoteActions note={NOTE} currentUser={FIN} onDone={onDone} />);
  await act(async () => { q(host, "od-note-adjust-cn1").click(); });
  const amount = q(host, "od-note-amount-cn1");
  const reason = q(host, "od-note-reason-cn1");
  const setVal = (el, v) => {
    const proto = Object.getPrototypeOf(el);
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, v);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  };
  await act(async () => { setVal(amount, "100000"); setVal(reason, "abc"); });
  expect(q(host, "od-note-confirm-cn1").disabled).toBe(true);                  // alasan terlalu pendek
  await act(async () => { setVal(reason, "Potongan biaya pembatalan"); });
  await act(async () => { q(host, "od-note-confirm-cn1").click(); });
  expect(api.reviewCreditNote).toHaveBeenLastCalledWith("cn1", { action: "adjust", gross_amount: 100000, note: "Potongan biaya pembatalan" });
  await act(async () => { q(host, "od-note-issue-cn1").click(); });
  expect(api.reviewCreditNote).toHaveBeenLastCalledWith("cn1", { action: "issue" });
  expect(onDone).toHaveBeenCalledTimes(2);
  await act(async () => { root.unmount(); });
});

test("tanpa izin atau nota sudah terbit → tidak ada tombol", async () => {
  let m = await mount(<OdCancelNoteActions note={NOTE} currentUser={{ role: "sales", permissions: {} }} />);
  expect(q(m.host, "od-note-actions-cn1")).toBeNull();
  await act(async () => { m.root.unmount(); });
  m = await mount(<OdCancelNoteActions note={{ ...NOTE, status: "issued" }} currentUser={FIN} />);
  expect(q(m.host, "od-note-actions-cn1")).toBeNull();
  await act(async () => { m.root.unmount(); });
});

test("Meja Finance → Tinjau menyaring daftar pesanan dengan nomor SO, bukan nomor nota (cek UI 2026-10-21)", () => {
  const row = { ref_type: "sales_order", ref_id: "so1", number: "KSC/CN-00016", order_id: "so1", order_number: "KSC/SO-00136" };
  const link = rowLink(row, "nota_batal_item", "finance");
  expect(link).toMatchObject({ view: "orders", focus_type: "sales_order", focus_id: "so1", number: "KSC/SO-00136" });
});
