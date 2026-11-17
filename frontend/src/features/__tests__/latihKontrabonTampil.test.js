// Pelatihan Keuangan 18 Nov (F12) — rincian kontrabon: nominal kartu dulu terbelah ("Rp 1.287.60" + "0") karena
// `break-words`, dan penerimaan barang tampil "tugas 945058 · completed" (potongan id tugas + status mentah).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { ReceiptSection, TotalsGrid } from "../purchasing/contrabon/ContraBonParts";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => { createRoot(host).render(el); });
  return host;
}
afterEach(() => { document.body.innerHTML = ""; });

test("kartu nominal satu baris (tidak terbelah)", async () => {
  const host = await mount(<TotalsGrid totals={{ bills_total: 1287600, deductions_total: 0, net_payable: 1287600,
    paid_total: 0, outstanding: 1287600 }} />);
  for (const id of ["cb-total-bills", "cb-total-net", "cb-total-outstanding"]) {
    const el = host.querySelector(`[data-testid="${id}"]`);
    expect(el.className).toContain("whitespace-nowrap");
    expect(el.className).not.toContain("break-words");
  }
});

test("penerimaan barang: status Indonesia, tanpa potongan id tugas", async () => {
  const host = await mount(<ReceiptSection loading={false} receipt={{ goods_receipts: [
    { grn_task_id: "task_abc945058", bill_number: "VB-1", po_number: "KSC/PO-00028", status: "completed",
      completed_at: "2026-11-17T03:00:00Z" }] }} />);
  const t = host.textContent;
  expect(t).toContain("KSC/PO-00028 · penerimaan gudang · Selesai");
  expect(t).not.toMatch(/tugas|completed|945058/);
});
