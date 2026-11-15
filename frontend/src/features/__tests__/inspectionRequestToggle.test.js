// Keputusan pemilik 10 Nov 2026 (sisa FIX-6) — tombol "Minta inspeksi" di panel tugas penerimaan (desktop & HP).
// API FIX-6: POST /inbound/tasks/{id}/inspection-request {requested, reason}; alasan wajib (askReason), hanya sebelum
// barang lepas karantina; penanda dari baris PO tampil & bisa dibatalkan.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import InspectionRequestToggle from "../wms/inbound/InspectionRequestToggle";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
jest.mock("../../services/confirmService", () => ({ askReason: jest.fn() }));
jest.mock("../../utils/feedback", () => ({ notifySuccess: jest.fn() }));
const axios = require("../../services/apiClient").default;
const { askReason } = require("../../services/confirmService");

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
let host; let root;
async function mount(el) {
  host = document.createElement("div"); document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(el); });
  return host;
}
afterEach(() => { act(() => root.unmount()); host.remove(); jest.clearAllMocks(); });

test("tugas sedang diterima: tombol Minta inspeksi → alasan → POST requested:true → tugas diperbarui", async () => {
  const onTaskUpdated = jest.fn();
  askReason.mockResolvedValueOnce("Supplier baru, cek cacat warna");
  axios.post.mockResolvedValueOnce({ data: { inspection_request: { requested: true, source: "receiving", by: "Rina", reason: "Supplier baru, cek cacat warna" }, rolls_marked: 3 } });
  const h = await mount(<InspectionRequestToggle task={{ id: "t1", status: "receiving" }} onTaskUpdated={onTaskUpdated} />);
  expect(q(h, "inbound-inspection-badge-t1")).toBeNull();
  await act(async () => { q(h, "inbound-inspection-toggle-t1").click(); });
  await flush();
  expect(axios.post).toHaveBeenCalledWith("/api/inbound/tasks/t1/inspection-request", { requested: true, reason: "Supplier baru, cek cacat warna" });
  expect(onTaskUpdated).toHaveBeenCalledWith(expect.objectContaining({ id: "t1", inspection_request: expect.objectContaining({ requested: true }) }));
});

test("batal di dialog alasan → tidak ada permintaan ke server", async () => {
  askReason.mockResolvedValueOnce(null);
  const h = await mount(<InspectionRequestToggle task={{ id: "t2", status: "waiting_goods" }} />);
  await act(async () => { q(h, "inbound-inspection-toggle-t2").click(); });
  await flush();
  expect(axios.post).not.toHaveBeenCalled();
});

test("penanda dari baris PO tampil sebagai lencana + bisa dibatalkan (requested:false)", async () => {
  askReason.mockResolvedValueOnce("Barang sudah dicek di pabrik");
  axios.post.mockResolvedValueOnce({ data: { inspection_request: { requested: false }, rolls_marked: 0 } });
  const h = await mount(<InspectionRequestToggle task={{ id: "t3", status: "qc_pending", inspection_request: { requested: true, source: "po_line" } }} />);
  expect(q(h, "inbound-inspection-badge-t3")).not.toBeNull();
  expect(h.textContent).toContain("dari baris PO");
  expect(q(h, "inbound-inspection-toggle-t3").textContent).toContain("Batalkan");
  await act(async () => { q(h, "inbound-inspection-toggle-t3").click(); });
  await flush();
  expect(axios.post).toHaveBeenCalledWith("/api/inbound/tasks/t3/inspection-request", { requested: false, reason: "Barang sudah dicek di pabrik" });
});

test("sesudah barang lepas karantina: tanpa penanda tidak tampil; dengan penanda tampil tanpa tombol", async () => {
  let h = await mount(<InspectionRequestToggle task={{ id: "t4", status: "completed" }} />);
  expect(q(h, "inbound-inspection-t4")).toBeNull();
  act(() => root.unmount()); host.remove();
  h = await mount(<InspectionRequestToggle task={{ id: "t5", status: "completed", inspection_request: { requested: true, source: "receiving", by: "Rina" } }} />);
  expect(q(h, "inbound-inspection-badge-t5")).not.toBeNull();
  expect(q(h, "inbound-inspection-toggle-t5")).toBeNull();
});

test("server menolak (409) → pesan galat tampil di dekat tombol", async () => {
  askReason.mockResolvedValueOnce("Cek cacat warna kain");
  axios.post.mockRejectedValueOnce({ response: { status: 409, data: { detail: "Tugas baru saja berubah — muat ulang." } } });
  const h = await mount(<InspectionRequestToggle task={{ id: "t6", status: "receiving" }} touch />);
  expect(q(h, "inbound-inspection-toggle-t6").className).toContain("btn-touch");
  await act(async () => { q(h, "inbound-inspection-toggle-t6").click(); });
  await flush();
  expect(q(h, "inbound-inspection-error-t6").textContent).toContain("muat ulang");
});
