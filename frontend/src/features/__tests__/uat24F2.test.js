// UAT 24 Okt — fase F2: P11 status cek roll (MDQ / 4-point) · P10.6 roll PT lain di gudang khusus tidak bisa dipilih.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import RollCheckChips, { rollCheckState } from "../../components/RollCheckChips";
import FulfillmentLineCard from "../sales_admin/FulfillmentLineCard";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.querySelector(`[data-testid="${id}"]`);
const mount = async (el) => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  return root;
};

test("P11 — chip MDQ ✓ / MDQ sampling / belum dan 4-pt ✓ / belum dibaca dari penanda datar roll", async () => {
  expect(rollCheckState({ md_quality_checked: true, inspected_4point: true })).toEqual({ md: "ok", fp: "ok" });
  expect(rollCheckState({ md_quality_via_sampling: { spk: "INS-1" } })).toEqual({ md: "sampling", fp: "none" });
  expect(rollCheckState({})).toEqual({ md: "none", fp: "none" });
  const root = await mount(<RollCheckChips roll={{ md_quality_via_sampling: { spk: "INS-9" } }} testId="rc" />);
  expect(q("rc-md").textContent).toBe("MDQ sampling");
  expect(q("rc-md").getAttribute("title")).toMatch(/INS-9/);
  expect(q("rc-4p").textContent).toBe("4-pt belum");
  act(() => root.unmount());
});

test("P10.6 — roll PT lain di gudang khusus tidak bisa dicentang; qty dibatasi stok gudang bersama", async () => {
  let value = { stock: 0, reorder: 0, wait: 0, ic: {}, stockRolls: [], icRolls: {} };
  const line = { product_id: "p1", product_name: "Batik", sku: "BTK", unit: "yard", backorder_qty: 100, planned_qty: 0,
    own_available: 0, own_by_warehouse: [], own_rolls: [], incoming_total: 0, incoming_claimed_by_older: 0,
    other_entities: [{ entity_id: "e2", entity_name: "KANDA", available: 90, usable_available: 40, needs_move: 50, price_ready: true,
      unit_price: 1000, rolls: [
        { id: "rb", roll_no: "RB-1", length_remaining: 40, warehouse_name: "Gudang Bersama", site_name: "Rancamalang", usable: true },
        { id: "rk", roll_no: "RK-1", length_remaining: 50, warehouse_name: "Gudang KANDA", site_name: "Soreang", usable: false }] }] };
  const root = await mount(<FulfillmentLineCard line={line} value={value} onChange={(v) => { value = v; }} />);
  await act(async () => { q("fulfill-ic-pick-p1-e2-toggle").click(); });
  expect(q("fulfill-ic-pick-p1-e2-roll-rk").disabled).toBe(true);
  expect(q("fulfill-ic-pick-p1-e2-roll-rk-blocked").textContent).toMatch(/pindahkan dulu/);
  expect(q("fulfill-ic-pick-p1-e2-roll-rb").disabled).toBe(false);
  expect(document.body.textContent).toMatch(/50 di gudang khusus KANDA/);
  act(() => root.unmount());
});
