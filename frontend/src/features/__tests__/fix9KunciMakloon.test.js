/**
 * FIX-9 (audit 9 Nov 2026 · B3a SSOT-4) — tampilan cadangan makloon yang DIKUNCI per roll:
 *  · lencana "Dicadangkan makloon · MKO-…" = StatusBadge baku (kosakata `statusVocab` ranah roll, ikon gembok, nada
 *    khusus) — di daftar roll (rincian roll) & penampil roll (kelompok), dari entri `length_reservations` bertipe makloon;
 *  · pemilih roll (desktop & HP) menandai roll yang sebagian terkunci dan catatan kuning hanya untuk sisa cadangan yang
 *    BELUM terkunci di roll (dulu: seluruh cadangan, karena belum ada kunci per roll);
 *  · pop-up Issue MKO menandai roll yang dikunci untuk MKO itu sendiri.
 * Uji ini GAGAL sebelum FIX-9 (komponen/kode status belum ada; catatan memakai `makloon_reserved_qty`).
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import MakloonLockBadge, { makloonLockOf } from "../../components/MakloonLockBadge";
import RollPicker from "../../components/RollPicker";
import RollsTable from "../wms/inventory/RollsTable";
import { statusLabel, statusMeta } from "../../utils/statusVocab";
import { MakloonLockBadge as ReExported } from "../wms/inventory/inventoryConstants";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
const axios = require("../../services/apiClient").default;

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
let host; let root;
async function mount(el) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(el); });
  await flush();
  return host;
}
afterEach(async () => {
  if (root) await act(async () => { root.unmount(); });
  host?.remove(); root = null;
  axios.get.mockReset();
});
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);

const LOCK = (qty, number = "MKO-00005") => ({ id: `rsv_${qty}`, qty, status: "reserved",
  ref: { type: "makloon", id: "mres_mko_x", number, mko_number: number } });
const ROLL_FULL = { id: "r1", roll_no: "RL-00001", product_name: "Greige", sku: "GRY", owner_entity_name: "Kanda",
  warehouse_name: "Soreang", length_remaining: 40, unit: "yard", status: "available", lot: "L1", lot_id: "lot1",
  length_reserved: 40, length_reservations: [LOCK(40)] };
const ROLL_PART = { ...ROLL_FULL, id: "r2", roll_no: "RL-00002", length_remaining: 30, length_reserved: 20,
  length_reservations: [LOCK(20)] };
const ROLL_SO = { ...ROLL_FULL, id: "r3", roll_no: "RL-00003", length_reserved: 10,
  length_reservations: [{ id: "x", qty: 10, status: "reserved", ref: { type: "sales_order", id: "so1" } }] };

describe("kosakata & lencana kunci makloon", () => {
  test("kode status makloon_reserved: label KN_32, nada khusus, ikon gembok", () => {
    expect(statusLabel("makloon_reserved", "roll")).toBe("Dicadangkan makloon");
    expect(statusMeta("makloon_reserved", { domain: "roll" })).toEqual(
      { label: "Dicadangkan makloon", tone: "special", icon: "lock" });
  });

  test("dibaca dari length_reservations bertipe makloon (bukan reservasi potong SO) atau ringkasan server", () => {
    expect(makloonLockOf(ROLL_FULL)).toEqual({ qty: 40, numbers: ["MKO-00005"] });
    expect(makloonLockOf(ROLL_SO)).toBeNull();
    expect(makloonLockOf({ id: "z", makloon_lock: { qty: 5, numbers: [] } })).toEqual({ qty: 5, numbers: [] });
    expect(ReExported).toBe(MakloonLockBadge);
  });

  test("lencana StatusBadge: penuh = nomor MKO; sebagian = nomor + panjang; tanpa kunci = kosong", async () => {
    await mount(<div>
      <MakloonLockBadge roll={ROLL_FULL} />
      <MakloonLockBadge roll={ROLL_PART} />
      <MakloonLockBadge roll={ROLL_SO} />
    </div>);
    const full = q("roll-makloon-lock-r1");
    expect(full.className).toMatch(/kn-badge/);
    expect(full.getAttribute("data-tone")).toBe("special");
    expect(full.textContent).toBe("Dicadangkan makloon · MKO-00005");
    expect(q("roll-makloon-lock-r2").textContent).toBe("Dicadangkan makloon · MKO-00005 · 20 yard");
    expect(q("roll-makloon-lock-r3")).toBeNull();
  });

  test("rincian roll (daftar roll) menampilkan lencana di kolom Status", async () => {
    await mount(<RollsTable rolls={[ROLL_FULL, ROLL_SO]} loading={false} />);
    expect(q("roll-row-r1").textContent).toContain("Dicadangkan makloon · MKO-00005");
    expect(q("roll-row-r3").textContent).not.toContain("Dicadangkan makloon");
  });
});

describe("pemilih roll (desktop & HP)", () => {
  test("roll sebagian terkunci bertanda; catatan hanya untuk sisa cadangan BELUM terkunci", async () => {
    axios.get.mockResolvedValue({ data: {
      items: [{ id: "r2", roll_no: "RL-00002", lot: "L1", length_remaining: 10, physical_length: 30,
        length_reserved: 20, warehouse_name: "Soreang", owner_entity_name: "Kanda", owner_entity_id: "ent_kanda",
        makloon_lock: { qty: 20, numbers: ["MKO-00005"], visible: true } }],
      total: 1, available_total: 10, base_unit: "yard", makloon_reserved_qty: 300, makloon_locked_qty: 300,
      makloon_unlocked_qty: 0 } });
    await mount(<RollPicker productId="p1" entityId="ent_kanda" />);
    expect(q("roll-makloon-lock-r2").textContent).toBe("Dicadangkan makloon · MKO-00005 · 20 yd");
    expect(q("roll-picker-makloon-note")).toBeNull();          // semua cadangan sudah terkunci di roll
  });

  test("sisa belum terkunci tetap diperingatkan", async () => {
    axios.get.mockResolvedValue({ data: { items: [], total: 0, available_total: 0, base_unit: "kg",
      makloon_reserved_qty: 75, makloon_locked_qty: 50, makloon_unlocked_qty: 25 } });
    await mount(<RollPicker productId="p1" entityId="ent_ksc" />);
    expect(q("roll-picker-makloon-note").textContent).toMatch(/25 kg dicadangkan untuk makloon tetapi belum terkunci/);
  });
});
