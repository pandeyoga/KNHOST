// Keputusan owner 2026-10-21 — antrean "Retur menunggu terima / QC" di meja Gudang: baris retur dibuka di layar
// Retur Pelanggan lewat menu "Retur" (returns-hub) — menu yang dimiliki Gudang/QC sejak F-11-layar — dengan fokus
// ke dokumennya; Meja Admin Sales tetap memakai peta barisnya sendiri.
import { rowLink } from "../sales_admin/workDeskApi";

jest.mock("../../services/apiClient", () => ({ __esModule: true, default: { get: jest.fn() }, API: "/api" }));

const ROW = { ref_type: "sales_return", ref_id: "sret_9", number: "SRET-9" };

test("meja Gudang & Admin Gudang: baris retur → layar Retur Pelanggan di menu Retur, fokus dokumen", () => {
  for (const desk of ["me", "warehouse_admin"]) {
    expect(rowLink(ROW, "retur_terima_qc", desk)).toEqual(expect.objectContaining({
      view: "returns", nav_id: "returns-hub", focus_type: "sales_return", focus_id: "sret_9", number: "SRET-9" }));
  }
});

test("Meja Admin Sales tidak berubah (peta baris sendiri)", () => {
  expect(rowLink(ROW, "", "sales_admin")).toEqual(expect.objectContaining({ view: "returns", focus_type: "sales_return" }));
});
