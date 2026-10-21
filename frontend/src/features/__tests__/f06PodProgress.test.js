// F-06 (keputusan owner Q-01a, 2026-10-21) — SO "Dikirim" menampilkan progres bukti terima (POD) per Surat Jalan;
// tombol pelacak "Catat POD" membuka Logistik tersaring nomor SO (bukan Barang Keluar).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import PodProgressNote from "../orders/PodProgressNote";
import { soTrackerLink } from "../sales_admin/workDeskApi";

jest.mock("../../services/apiClient", () => ({ __esModule: true, default: { get: jest.fn() }, API: "/api" }));
const axios = require("../../services/apiClient").default;

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test("progres POD: x dari y + Surat Jalan yang belum", async () => {
  axios.get.mockResolvedValue({ data: { total: 2, with_pod: 1, complete: false, missing: ["KSC/SJ-00031"] } });
  const host = document.createElement("div");
  const root = createRoot(host);
  await act(async () => { root.render(<PodProgressNote orderId="so1" />); });
  expect(axios.get).toHaveBeenCalledWith("/api/sales-orders/so1/pod-progress");
  expect(host.querySelector('[data-testid="order-pod-count"]').textContent).toBe("1 dari 2");
  expect(host.textContent).toMatch(/tertutup otomatis/);
  expect(host.textContent).toMatch(/KSC\/SJ-00031/);
  await act(async () => { root.unmount(); });
});

test("pelacak: tahap POD → Logistik tersaring nomor SO; tahap gudang tetap Barang Keluar", () => {
  const pod = soTrackerLink({ id: "so1", number: "KSC/SO-00207", owner_roles: ["logistics", "warehouse_admin"] });
  expect(pod).toMatchObject({ view: "logistics", nav_id: "logistics", logistics: { search: "KSC/SO-00207" } });
  const wh = soTrackerLink({ id: "so2", number: "KSC/SO-00208", owner_roles: ["warehouse_admin", "warehouse"] });
  expect(wh).toMatchObject({ view: "wms-outbound", focus_id: "so2" });
});
