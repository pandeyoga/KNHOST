// FE-04/FE-05 (review 2026-10-20) — tombol mengikuti izin efektif; Data Gudang non-master tanpa "Semua gudang".
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import WarehouseMasterView from "../wms/warehouses/WarehouseMasterView";
import SpecialOrders from "../sales/SpecialOrders";

describe("Data Gudang", () => {
  const render = (user) => renderToStaticMarkup(<WarehouseMasterView entities={[]} selectedEntity="ent_ksc" currentUser={user} />);
  test("Admin Gudang berizin: tombol buat ada, filter 'Semua gudang' tidak (bukan scope master)", () => {
    const html = render({ role: "warehouse_admin", permissions: { warehouse: ["view", "create", "update"] } });
    expect(html).toContain("wh-toggle-create");
    expect(html).toContain("wh-scope-usable");
    expect(html).not.toContain("wh-scope-all");
  });
  test("Manager hanya-lihat: tanpa tombol buat; tetap scope master", () => {
    const html = render({ role: "manager", permissions: { warehouse: ["view"] } });
    expect(html).not.toContain("wh-toggle-create");
    expect(html).toContain("wh-scope-all");
  });
});

describe("Pesanan Khusus", () => {
  const render = (user) => renderToStaticMarkup(<SpecialOrders currentUser={user} />);
  test("peran kustom berizin order.create melihat tombol Buat", () => {
    expect(render({ role: "cr_sales", permissions: { order: ["view", "create"] } })).toContain("create-special-order-btn");
  });
  test("Manager hanya-lihat tidak melihat tombol Buat", () => {
    expect(render({ role: "manager", permissions: { order: ["view"] } })).not.toContain("create-special-order-btn");
  });
});
