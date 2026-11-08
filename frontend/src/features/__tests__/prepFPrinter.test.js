// PREP-F — antrean printer label RFID (CP30EN): kesehatan connector ≠ printer, tindak lanjut hasil tidak pasti
// (izin approve, bukti C72 untuk sukses RFID, alasan wajib), cetak ulang teks vs ganti tag, pratinjau 70 × 22 mm,
// daftar berhalaman bisa diunduh, status job/label berbahasa Indonesia.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import PrinterQueuePanel from "../rfid/PrinterQueuePanel";
import LabelPreview from "../rfid/LabelPreview";
import { RollTagActionModal } from "../rfid/PrinterModals";
import { actionsFor, evidenceRequired, jobProgress, printerHealth, JOB_STATUS, ITEM_STATUS } from "../rfid/printerLabels";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(), put: jest.fn(), patch: jest.fn(), delete: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
jest.mock("../../config/roles", () => ({ canCurrent: jest.fn(() => true) }));
jest.mock("../../components/KNSelect", () => {
  const Sel = ({ value, onValueChange, options = [], "data-testid": tid }) => (
    <select data-testid={tid} value={value} onChange={(e) => onValueChange?.(e.target.value)}>
      {options.map((o) => <option key={`${o.value}`} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: Sel, KNSelect: Sel };
});
const axios = require("../../services/apiClient").default;
const roles = require("../../config/roles");

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
let host; let root;
async function mount(el) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(el); });
  await flush();
}
beforeEach(() => { roles.canCurrent.mockImplementation(() => true); });
afterEach(async () => {
  if (root) await act(async () => { root.unmount(); });
  host?.remove(); root = null;
  document.body.innerHTML = "";
  jest.clearAllMocks();
});
const $ = (sel) => document.body.querySelector(sel);
const click = async (el) => { await act(async () => { el.click(); }); await flush(); };
const typeText = async (el, value) => {
  const proto = el.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new Event("input", { bubbles: true })); });
};
const choose = async (el, value) => {
  await act(async () => {
    Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, "value").set.call(el, value);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
};

const JOBS = [
  { id: "j1", job_number: "PJ-0001", kind: "rfid_tag", status: "needs_review", item_count: 10, warehouse_name: "RCM Woven",
    counts: { confirmed: 7, failed: 2, unknown: 1, pending: 0, started: 0 }, review_open: 3, created_at: "2026-11-09T02:00:00Z",
    created_by: "Admin", lease: null, printed_by_device: "rdev1" },
  { id: "j2", job_number: "PJ-0002", kind: "rfid_tag", status: "printing", item_count: 2, warehouse_name: "RCM Woven",
    counts: { confirmed: 1, pending: 1 }, created_at: "2026-11-09T03:00:00Z", created_by: "Admin",
    lease: { device_name: "CP30EN-1", expires_at: "2999-01-01T00:00:00Z" }, lease_live: true },
];
const FOLLOW = [
  { job_id: "j1", job_number: "PJ-0001", kind: "rfid_tag", item_id: "i3", roll_no: "R-003", epc: "E200000000000000AABBCCDD",
    reason: "unknown", print_status: "unknown", encode_status: "unknown", warehouse_name: "RCM Woven",
    started_at: "2026-11-09T02:01:00Z", evidence: { detail: "timeout" } },
  { job_id: "j1", job_number: "PJ-0001", kind: "rfid_tag", item_id: "i4", roll_no: "R-004", epc: "E200000000000000AABBCCEE",
    reason: "failed", print_status: "failed", encode_status: "confirmed", chip_written: true, warehouse_name: "RCM Woven" },
];
const STATUS = { warehouses: [{ warehouse_id: "wh1", warehouse_name: "RCM Woven", printers: [
  { id: "rdev1", name: "CP30EN-1", online: true, last_heartbeat: new Date().toISOString(), printer_state: "paper_out",
    printer_ready: false, printer_checked_at: new Date().toISOString(), connector: { version: "0.1.0", host: "PC-GDG",
      ledger: { pending_results: 2 } }, connector_conflict: null }] }] };

function mockApi() {
  axios.get.mockImplementation((url) => {
    if (url.endsWith("/rfid/printers/queue")) return Promise.resolve({ data: { jobs: JOBS } });
    if (url.endsWith("/rfid/printers/follow-up")) return Promise.resolve({ data: { items: FOLLOW } });
    if (url.endsWith("/rfid/printer-status")) return Promise.resolve({ data: STATUS });
    if (url.endsWith("/rfid/print-jobs/j1")) return Promise.resolve({ data: { ...JOBS[0], items: [
      { item_id: "i1", roll_no: "R-001", epc: "E2000000000000000000AA01", status: "confirmed", print_status: "confirmed",
        encode_status: "confirmed", evidence: { source: "printer_readback" } },
      { item_id: "i3", roll_no: "R-003", epc: "E200000000000000AABBCCDD", status: "unknown", print_status: "unknown",
        encode_status: "unknown", evidence: { source: "connector_recovery", detail: "Connector berhenti" } }] } });
    return Promise.reject(new Error(`tak terduga ${url}`));
  });
  axios.post.mockResolvedValue({ data: { status: "confirmed" } });
}

test("label status & aturan tindakan sama dengan server", () => {
  expect(JOB_STATUS.needs_review[1]).toBe("Perlu Ditinjau");
  expect(ITEM_STATUS.unknown[1]).toBe("Tidak pasti");
  expect(actionsFor({ reason: "failed" })).toEqual(["reprint", "close"]);
  expect(actionsFor({ reason: "unknown" })).toEqual(["confirm_success", "confirm_failed", "reprint"]);
  expect(evidenceRequired("rfid_tag", "confirm_success")).toBe("c72_scan");
  expect(evidenceRequired("qr_label", "confirm_success")).toBeNull();
  expect(jobProgress(JOBS[0])).toBe("7 tercetak · 2 gagal · 1 tidak pasti");
  const h = printerHealth(STATUS.warehouses[0].printers[0]);
  expect(h.connector[1]).toBe("Connector aktif");
  expect(h.printer[1]).toBe("Kertas habis");
});

test("panel: connector aktif TERPISAH dari status printer; tindak lanjut & job; unduh CSV tersedia", async () => {
  mockApi();
  await mount(<PrinterQueuePanel whId="wh1" />);
  const health = $("[data-testid='printer-health-rdev1']").textContent;
  expect(health).toContain("Connector aktif");
  expect(health).toContain("Kertas habis");
  expect(health).toContain("2 hasil menunggu terkirim");
  const fu = $("[data-testid='printer-follow-up']").textContent;
  expect(fu).toContain("Hasil tidak pasti");
  expect(fu).toContain("chip sudah tertulis");
  expect($("[data-testid='printer-follow-up-pager-export']")).not.toBeNull();
  expect($("[data-testid='printer-jobs-pager-export']")).not.toBeNull();
  expect($("[data-testid='printer-job-j2']")).not.toBeNull();         // saringan bawaan: sedang berjalan
  expect($("[data-testid='printer-job-j1']")).toBeNull();
  await click($("[data-testid='printer-jobs-filter-review']"));
  expect($("[data-testid='printer-job-j1']").textContent).toContain("Perlu Ditinjau");
  expect($("[data-testid='printer-queue-panel']").textContent).not.toMatch(/needs_review|stale_started|confirm_success/);
  expect(axios.get).toHaveBeenCalledWith("/api/rfid/printers/follow-up", { params: { warehouse_id: "wh1" } });
});

test("tinjau hasil tidak pasti: sukses RFID wajib bukti C72 + alasan, lalu POST ke endpoint resolve", async () => {
  mockApi();
  await mount(<PrinterQueuePanel whId="wh1" />);
  await click($("[data-testid='printer-follow-up-resolve-i3']"));
  const ev = $("[data-testid='print-resolve-evidence']");
  expect([...ev.options].map((o) => o.value)).toEqual(["c72_scan"]);  // dipaksa bukti baca EPC
  expect($("[data-testid='print-resolve-submit']").disabled).toBe(true);
  await typeText($("[data-testid='print-resolve-note']"), "C72 membaca EPC di meja");
  await click($("[data-testid='print-resolve-submit']"));
  expect(axios.post).toHaveBeenCalledWith("/api/rfid/print-jobs/j1/items/i3/resolve",
    { action: "confirm_success", note: "C72 membaca EPC di meja", evidence_type: "c72_scan", evidence_ref: "" });
});

test("item gagal: pilihan cetak ulang (EPC baru) / tutup; peringatan chip tertulis", async () => {
  mockApi();
  await mount(<PrinterQueuePanel whId="wh1" />);
  await click($("[data-testid='printer-follow-up-resolve-i4']"));
  expect([...$("[data-testid='print-resolve-action']").options].map((o) => o.value)).toEqual(["reprint", "close"]);
  expect($("[data-testid='print-resolve-chip-written']").textContent).toContain("musnahkan");
  expect($("[data-testid='print-resolve-hint']").textContent).toContain("EPC BARU");
});

test("tanpa izin approve: tombol Tinjau disembunyikan, ada petunjuk", async () => {
  roles.canCurrent.mockImplementation((m, a) => !(m === "wms" && a === "approve"));
  mockApi();
  await mount(<PrinterQueuePanel whId="wh1" />);
  expect($("[data-testid='printer-follow-up-resolve-i3']")).toBeNull();
  expect($("[data-testid='printer-follow-up-noperm']").textContent).toContain("izin persetujuan");
});

test("rincian job: tiga dimensi (job · printer · verifikasi C72) dan bukti per label", async () => {
  mockApi();
  await mount(<PrinterQueuePanel whId="wh1" />);
  await click($("[data-testid='printer-jobs-filter-review']"));
  await click($("[data-testid='printer-job-j1']"));
  const dims = $("[data-testid='print-job-dims']").textContent;
  expect(dims).toContain("Perlu Ditinjau");
  expect(dims).toContain("Belum diverifikasi");
  const row = $("[data-testid='print-item-i3']").textContent;
  expect(row).toContain("Tidak pasti");
  expect(row).toContain("Pemulihan connector");
  expect($("[data-testid='print-item-resolve-i3']")).not.toBeNull();
  expect($("[data-testid='print-item-resolve-i1']")).toBeNull();
});

test("ganti tag vs cetak ulang teks: endpoint berbeda, alasan wajib, ganti tag butuh approve", async () => {
  axios.post.mockResolvedValue({ data: { job: { job_number: "PJ-0009" }, new_tag: { epc: "E2NEW" }, old_tag: { epc: "E2OLD" } } });
  await mount(<RollTagActionModal roll={{ roll_id: "r1", roll_no: "R-001", epc: "E2OLD" }} mode="replace" />);
  expect($("[data-testid='roll-tag-action-mode']").value).toBe("replace");
  expect($("[data-testid='roll-tag-action-submit']").disabled).toBe(true);
  await typeText($("[data-testid='roll-tag-action-note']"), "tag sobek kena forklift");
  await click($("[data-testid='roll-tag-action-submit']"));
  expect(axios.post).toHaveBeenCalledWith("/api/rfid/rolls/r1/replace-tag", { reason_code: "damaged", note: "tag sobek kena forklift" });
  expect($("[data-testid='roll-tag-action-result']").textContent).toContain("E2OLD dipensiunkan");
  await act(async () => { root.unmount(); }); root = null; document.body.innerHTML = "";
  roles.canCurrent.mockImplementation((m, a) => !(m === "wms" && a === "approve"));
  axios.post.mockResolvedValue({ data: { job_number: "PJ-0010", items: [{ epc: "E2000000000000000000BEEF" }] } });
  await mount(<RollTagActionModal roll={{ roll_id: "r1", roll_no: "R-001", epc: "E2OLD" }} mode="replace" />);
  const opts = [...$("[data-testid='roll-tag-action-mode']").options].map((o) => o.value);
  expect(opts).toEqual(["reprint"]);                                  // tanpa approve: hanya cetak ulang teks
  await choose($("[data-testid='roll-tag-action-reason']"), "text_lost");
  await typeText($("[data-testid='roll-tag-action-note']"), "label teks hilang");
  await click($("[data-testid='roll-tag-action-submit']"));
  expect(axios.post).toHaveBeenCalledWith("/api/rfid/rolls/r1/reprint-label", { reason_code: "text_lost", note: "label teks hilang" });
  expect($("[data-testid='roll-tag-action-result']").textContent).toContain("…0000BEEF");
});

test("pratinjau 70 × 22 mm memakai dot dari server dan menandai tulis chip", async () => {
  const layout = { width_dots: 559, height_dots: 176, width_mm: 70, height_mm: 22, dpi: 203, rfid: true,
    epc_display: "E200-0000-0000-0000-1234-5678", warnings: ["Teks terpotong agar muat: title"], elements: [
      { type: "qr", x: 8, y: 13, size: 150, mag: 6 },
      { type: "text", x: 170, y: 66, h: 26, w: 24, text: "Roll RL-0001", role: "roll_no" }] };
  await mount(<LabelPreview layout={layout} />);
  expect($("[data-testid='label-preview-caption']").textContent).toContain("70 × 22 mm · 203 dpi = 559 × 176 dot");
  expect($("[data-testid='label-preview-caption']").textContent).toContain("menulis EPC ke chip");
  expect($("[data-testid='label-preview-roll_no']").textContent).toBe("Roll RL-0001");
  expect($("[data-testid='label-preview-warnings']").textContent).toContain("terpotong");
});
