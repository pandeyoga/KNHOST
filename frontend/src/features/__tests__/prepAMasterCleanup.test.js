// PREP-A (K-OPN-06) — lembar perbaikan master produk: panel unduh/unggah/pratinjau/terapkan/batalkan + petunjuk
// "SKU X digantikan oleh Y" di pemilih produk.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import MasterCleanupPanel from "../catalog/MasterCleanupPanel";
import MasterCleanupPreview from "../catalog/MasterCleanupPreview";
import { SupersedeHintList, localSupersedeHints } from "../../components/SupersedeHint";
import { blobErrorText } from "../catalog/masterCleanupApi";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), defaults: { headers: { common: {} } } },
  API: "/api",
}));
const mockConfirm = jest.fn();
const mockReason = jest.fn();
jest.mock("../../services/confirmService", () => ({
  askConfirm: (...a) => mockConfirm(...a), askReason: (...a) => mockReason(...a), REASON_MIN_LENGTH: 5,
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  return { host, root };
}
const setInput = async (el, value) => {
  const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), "value").set;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new Event("input", { bubbles: true })); });
};
const click = async (el) => { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await act(async () => {}); };

const PV = {
  source_filename: "lembar.xlsx", can_apply: true, preview_signature: "sig1", general_errors: [],
  summary: { rows_read: 6, pertahankan: 1, GANTI_NAMA: 1, GANTI_KODE: 1, GABUNG_KE: 2, NONAKTIFKAN: 1, errors: 0, warnings: 1, changes: 5 },
  actions: [{ row: 2, sku: "A", tindakan: "GANTI_NAMA" }],
  rows: [
    { row: 2, sku: "A", name: "Kain A", tindakan: "GANTI_NAMA", detail: "nama → Kain A benar", errors: [], warnings: [] },
    { row: 3, sku: "B", name: "Kain B", tindakan: "GANTI_KODE", detail: "kode baru B2", errors: [], warnings: ["Stok lama 3 roll · 90 meter tetap tercatat di SKU lama"] },
  ],
};
const BATCHES = [
  { id: "mcb_1", status: "applied", changed: 5, applied_by: "Admin", applied_at: "2026-11-09T01:00:00Z", note: "Perapian" },
  { id: "mcb_0", status: "rolled_back", changed: 2, applied_by: "Admin", rollback_reason: "salah lembar" },
];

afterEach(() => { mockGet.mockReset(); mockPost.mockReset(); mockConfirm.mockReset(); mockReason.mockReset(); document.body.innerHTML = ""; });

test("izin: unduh hanya dengan product.export, unggah/terapkan hanya dengan product.update", async () => {
  mockGet.mockResolvedValue({ data: [] });
  const a = await mount(<MasterCleanupPanel canExport canUpdate={false} />);
  expect(q(a.host, "mc-download")).not.toBeNull();
  expect(q(a.host, "mc-file")).toBeNull();
  expect(mockGet).not.toHaveBeenCalled();                        // riwayat batch butuh product.update
  const b = await mount(<MasterCleanupPanel canExport={false} canUpdate />);
  expect(q(b.host, "mc-download")).toBeNull();
  expect(q(b.host, "mc-file")).not.toBeNull();
  const c = await mount(<MasterCleanupPanel />);
  expect(q(c.host, "mc-no-access")).not.toBeNull();
});

test("unggah → pratinjau (ringkasan + baris) → Terapkan lewat ConfirmDialog dengan tanda tangan pratinjau", async () => {
  mockGet.mockResolvedValue({ data: [] });
  mockPost.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/preview") ? PV : { id: "mcb_9", status: "applied", changed: 5, failed: [] } }));
  mockConfirm.mockResolvedValue(true);
  const { host } = await mount(<MasterCleanupPanel canExport canUpdate />);
  const file = new File(["x"], "lembar.xlsx");
  await act(async () => {
    Object.defineProperty(q(host, "mc-file"), "files", { value: [file] });
    q(host, "mc-file").dispatchEvent(new Event("change", { bubbles: true }));
  });
  expect(q(host, "mc-file-name").textContent).toBe("lembar.xlsx");
  await click(q(host, "mc-preview-btn"));
  expect(mockPost.mock.calls[0][0]).toBe("/api/master-governance/cleanup/preview");
  expect(q(host, "mc-summary-GABUNG_KE").textContent).toContain("2");
  expect(q(host, "mc-row-3").textContent).toContain("Stok lama 3 roll");
  expect(q(host, "mc-apply").disabled).toBe(true);               // catatan batch wajib
  await setInput(q(host, "mc-note"), "Perapian Gedung A");
  expect(q(host, "mc-apply").disabled).toBe(false);
  await click(q(host, "mc-apply"));
  expect(mockConfirm).toHaveBeenCalledTimes(1);
  const [url, body] = mockPost.mock.calls[1];
  expect(url).toBe("/api/master-governance/cleanup/apply");
  expect(body).toMatchObject({ preview_signature: "sig1", note: "Perapian Gedung A", actions: PV.actions });
  expect(q(host, "mc-notice").textContent).toContain("mcb_9");
});

test("pratinjau bergalat: Terapkan mati + pesan perbaiki; galat per baris tampil", async () => {
  const bad = { ...PV, can_apply: false, summary: { ...PV.summary, errors: 2 }, general_errors: ["Hanya Admin atau MD yang boleh menonaktifkan/menggantikan SKU"],
    rows: [{ row: 4, sku: "C", name: "", tindakan: "GANTI_KODE", detail: "", errors: ["Masih dipakai 1 dokumen terbuka: SO KSC/SO-1"], warnings: [] }] };
  const html = (await mount(<MasterCleanupPreview pv={bad} />)).host.innerHTML;
  expect(html).toContain("SO KSC/SO-1");
  expect(html).toContain("Hanya Admin atau MD");
});

test("riwayat batch: tombol Batalkan hanya untuk batch diterapkan; alasan wajib lewat askReason", async () => {
  mockGet.mockResolvedValue({ data: BATCHES });
  mockReason.mockResolvedValue("salah isi lembar");
  mockPost.mockResolvedValue({ data: { rollback_done: [1, 2], rollback_skipped: [] } });
  const { host } = await mount(<MasterCleanupPanel canUpdate />);
  expect(q(host, "mc-rollback-mcb_1")).not.toBeNull();
  expect(q(host, "mc-rollback-mcb_0")).toBeNull();
  expect(q(host, "mc-batch-status-mcb_0").textContent).toBe("Dibatalkan");
  await click(q(host, "mc-rollback-mcb_1"));
  expect(mockReason.mock.calls[0][0]).toMatchObject({ reasonRequired: true, reasonMinLength: 5 });
  expect(mockPost).toHaveBeenCalledWith("/api/master-governance/cleanup/batches/mcb_1/rollback", { reason: "salah isi lembar" });
});

test("galat unduhan (blob) tetap terbaca sebagai kalimat", async () => {
  const blob = { text: () => Promise.resolve(JSON.stringify({ detail: "Permission ditolak: product.export" })) };
  expect(await blobErrorText({ response: { data: blob } }, "x")).toBe("Permission ditolak: product.export");
});

test("petunjuk SKU lama → pengganti + tombol pilih (data lokal POS)", async () => {
  const products = [
    { id: "p1", sku: "KN-01-SALAH", name: "Lama", superseded_by: "p2", superseded_by_sku: "KN-01" },
    { id: "p2", sku: "KN-01", name: "Kain benar", status: "active" },
  ];
  const hints = localSupersedeHints("kn-01-salah", products);
  expect(hints).toHaveLength(1);
  expect(hints[0].superseded_by.sku).toBe("KN-01");
  expect(localSupersedeHints("KN-01", products)).toHaveLength(0);
  const onPick = jest.fn();
  const { host } = await mount(<SupersedeHintList hints={hints} pickable={[products[1]]} onPick={onPick} testId="h" />);
  expect(q(host, "h-KN-01-SALAH").textContent).toContain("digantikan oleh KN-01");
  await click(q(host, "h-pick-KN-01"));
  expect(onPick).toHaveBeenCalledWith(products[1]);
});
