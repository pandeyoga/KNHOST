// Fase 4 · R8 — label status SO (keputusan pemilik #2, 26 Okt 2026): "Menunggu stok (backorder)" HANYA untuk status
// `waiting_stock`; SO tahap lain yang masih bersisa kurang stok = "Sebagian menunggu stok" (mirror so_status.py).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { SubStatusChips } from "../../components/SoStatusBadges";
import { deriveStageSub, getSubStatus, subStatusLabel } from "../../utils/soStatus";
import { visibleSubs } from "../orders/soStatusView";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test("R8 derivasi: backorder penuh = waiting_stock; tahap lain bersisa = sebagian menunggu stok", () => {
  expect(deriveStageSub({ status: "waiting_stock" })).toEqual(["Reserved", ["menunggu_stok"]]);
  expect(deriveStageSub({ status: "approved", has_backorder: true })).toEqual(["Approved", ["sebagian_menunggu_stok"]]);
  expect(deriveStageSub({ status: "approved" })).toEqual(["Approved", ["siap_confirm"]]);
  expect(deriveStageSub({ status: "confirmed", has_backorder: true })[1]).toEqual(["siap_pick", "sebagian_menunggu_stok"]);
  expect(deriveStageSub({ status: "partially_picked", backorders: [{ backorder_qty: 5, status: "waiting_stock" }] })[1])
    .toEqual(["sebagian_dipick", "sebagian_menunggu_stok"]);
  expect(deriveStageSub({ status: "partially_shipped", has_backorder: true })[1])
    .toEqual(["sebagian_dikirim", "sebagian_menunggu_stok"]);
  // SO batal ber-penanda basi tidak berlabel stok sama sekali
  expect(deriveStageSub({ status: "cancelled", has_backorder: true })).toEqual(["Cancelled", ["dibatalkan"]]);
});

test("R8 label: dua kunci, dua kata", () => {
  expect(subStatusLabel("menunggu_stok")).toBe("Menunggu stok (backorder)");
  expect(subStatusLabel("sebagian_menunggu_stok")).toBe("Sebagian menunggu stok");
});

test("R8 sub_status tersimpan lama (`menunggu_stok` di tahap lain) dibaca 'sebagian menunggu stok'", () => {
  expect(getSubStatus({ status: "partially_shipped", sub_status: ["sebagian_dikirim", "menunggu_stok"] }))
    .toEqual(["sebagian_dikirim", "sebagian_menunggu_stok"]);
  expect(getSubStatus({ status: "approved", sub_status: ["menunggu_stok"] })).toEqual(["sebagian_menunggu_stok"]);
  // status waiting_stock & dokumen tanpa status dibiarkan apa adanya
  expect(getSubStatus({ status: "waiting_stock", sub_status: ["menunggu_stok"] })).toEqual(["menunggu_stok"]);
  expect(getSubStatus({ sub_status: ["menunggu_stok"] })).toEqual(["menunggu_stok"]);
  // tanpa duplikat bila dokumen sudah membawa keduanya
  expect(getSubStatus({ status: "confirmed", sub_status: ["siap_pick", "menunggu_stok", "sebagian_menunggu_stok"] }))
    .toEqual(["siap_pick", "sebagian_menunggu_stok"]);
  expect(visibleSubs({ status: "waiting_stock" })).toEqual(["menunggu_stok"]);
});

test("R8 chip sub-status di daftar: SO dikirim sebagian tidak lagi berbunyi 'Menunggu stok (backorder)'", async () => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  const order = { id: "so1", status: "partially_shipped", stage: "Shipped", sub_status: ["sebagian_dikirim", "menunggu_stok"] };
  await act(async () => { root.render(<SubStatusChips subs={visibleSubs(order)} testIdPrefix="row" />); });
  expect(host.textContent).toContain("Sebagian menunggu stok");
  expect(host.textContent).not.toContain("backorder");
  expect(host.querySelector('[data-testid="row-sebagian_menunggu_stok"]')).not.toBeNull();
  await act(async () => { root.render(<SubStatusChips order={{ status: "waiting_stock" }} testIdPrefix="row" />); });
  expect(host.textContent).toBe("Menunggu stok (backorder)");
  await act(async () => { root.unmount(); });
  host.remove();
});
