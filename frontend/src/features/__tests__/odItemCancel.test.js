// FE-01 lanjutan (keputusan owner 2026-10-21) — batal per item Pesanan Khusus: tombol mengikuti aturan server,
// item batal tetap tampil (dicoret + alasan).
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import SpecialOrderItemsPanel from "../sales/SpecialOrderItemsPanel";

const item = (n, extra = {}) => ({ id: `soi${n}`, line_no: n, description: `Kain ${n}`, quantity: 100, unit: "yard",
  source_type_label: "Turunan produk", request_types: ["labdip"], samples: [], ...extra });
const render = (order, canCancelItem = true) =>
  renderToStaticMarkup(<SpecialOrderItemsPanel order={order} canEdit={false} canCancelItem={canCancelItem} />);

describe("Pesanan Khusus — batal per item", () => {
  test("dua item aktif & berizin: tombol batal di setiap item", () => {
    const html = render({ id: "od1", status: "confirmed", items: [item(1), item(2)] });
    expect(html).toContain("special-order-item-cancel-1");
    expect(html).toContain("special-order-item-cancel-2");
  });
  test("item batal tampil dicoret dengan alasan; item aktif terakhir tidak bisa dibatalkan", () => {
    const html = render({ id: "od1", status: "confirmed",
      items: [item(1), item(2, { status: "cancelled", cancel_reason: "Pelanggan batal", cancelled_by: "Admin" })] });
    expect(html).toContain("special-order-item-cancelled-2");
    expect(html).toContain("Pelanggan batal");
    expect(html).toContain("1 aktif · 1 batal");
    expect(html).not.toContain("special-order-item-cancel-1");
    expect(html).not.toContain("special-order-item-cancel-2");
  });
  test("sesudah SO lahir, OD selesai, atau tanpa order.update: tidak ada tombol batal", () => {
    expect(render({ id: "od1", status: "confirmed", linked_sales_order_id: "so1", items: [item(1), item(2)] }))
      .not.toContain("special-order-item-cancel-");
    expect(render({ id: "od1", status: "done", items: [item(1), item(2)] })).not.toContain("special-order-item-cancel-");
    expect(render({ id: "od1", status: "confirmed", items: [item(1), item(2)] }, false)).not.toContain("special-order-item-cancel-");
  });
});
