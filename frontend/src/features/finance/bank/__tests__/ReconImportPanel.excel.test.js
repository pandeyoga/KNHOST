// Rekonsiliasi Bank — unggah rekening koran Excel (.xlsx), 18 Nov 2026: berkas dibaca sebagai biner dan dikirim base64
// (`file_b64`, `raw` kosong) ke pratinjau & impor; .xls lama ditolak di layar dengan arahan, tanpa permintaan ke server.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ReconImportPanel from "../ReconImportPanel";

const mockPost = jest.fn();
jest.mock("../../../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid }) => (
    <select data-testid={tid} value={value ?? ""} onChange={(e) => onValueChange(e.target.value)}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: M, KNSelect: M };
});
jest.mock("../../../../services/apiClient", () => ({
  __esModule: true,
  default: { post: (...a) => mockPost(...a), get: () => Promise.resolve({ data: [] }) },
  API: "/api",
}));
jest.mock("../../../../components/FormModal", () => ({ title, footer, children, testId }) => (
  <div data-testid={testId}><h2>{title}</h2>{children}{footer}</div>
));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};   // jsdom — dipakai ErrorNotice
const q = (host, tid) => host.querySelector(`[data-testid="${tid}"]`);
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });

// jsdom lama tidak punya Blob.arrayBuffer/text — dibaca lewat FileReader seperti peramban.
function berkas(isi, nama) {
  const f = new File([isi], nama);
  const baca = (cara) => new Promise((res) => { const fr = new FileReader(); fr.onload = () => res(fr.result); fr[cara](f); });
  if (!f.arrayBuffer) f.arrayBuffer = () => baca("readAsArrayBuffer");
  if (!f.text) f.text = () => baca("readAsText");
  return f;
}

async function pilih(host, f) {
  const input = q(host, "recon-file-input");
  Object.defineProperty(input, "files", { value: [f], configurable: true });
  await act(async () => { input.dispatchEvent(new Event("change", { bubbles: true })); });
  await flush();
}

async function render() {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const done = jest.fn();
  await act(async () => {
    createRoot(host).render(<ReconImportPanel accountId="ba_1" formats={[{ id: "f_bca", name: "BCA", file_kind: "csv" }]}
      onDone={done} onClose={() => {}} />);
  });
  return { host, done };
}

beforeEach(() => { mockPost.mockReset(); });

test("berkas .xlsx dikirim base64 ke pratinjau & impor; kotak tempel disembunyikan", async () => {
  const { host, done } = await render();
  expect(q(host, "recon-file-input").getAttribute("accept")).toMatch(/\.xlsx/);
  await pilih(host, berkas(new Uint8Array([0x50, 0x4b, 0x03, 0x04, 0x01]), "mutasi_bca.xlsx"));
  expect(q(host, "recon-file-excel").textContent).toContain("mutasi_bca.xlsx");
  expect(q(host, "recon-raw")).toBeNull();
  expect(q(host, "recon-preview-btn").disabled).toBe(false);

  mockPost.mockResolvedValueOnce({ data: { total: 1, rows: [], format: { name: "BCA" }, sum_in: 0, sum_out: 0,
    source: { file_kind: "xlsx", sheet: "Mutasi", header_row: 7 } } });
  await act(async () => { q(host, "recon-preview-btn").click(); });
  await flush();
  const [url, body] = mockPost.mock.calls[0];
  expect(url).toBe("/api/bank-reconciliation/preview");
  expect(body.file_b64).toBe(btoa(String.fromCharCode(0x50, 0x4b, 0x03, 0x04, 0x01)));
  expect(body.raw).toBe("");
  expect(q(host, "recon-preview-sheet").textContent).toContain("lembar Mutasi, judul kolom di baris 7");

  mockPost.mockResolvedValueOnce({ data: { format_name: "BCA", imported: 3, skipped: 0 } });
  await act(async () => { q(host, "recon-import-submit").click(); });
  await flush();
  const imp = mockPost.mock.calls[1][1];
  expect(imp).toMatchObject({ bank_account_id: "ba_1", file_name: "mutasi_bca.xlsx", raw: "" });
  expect(imp.file_b64).toBe(body.file_b64);
  expect(done).toHaveBeenCalledWith(expect.stringContaining("3 baris baru"));
});

test("Batal pilih mengembalikan kotak tempel; berkas CSV tetap dikirim sebagai teks", async () => {
  const { host } = await render();
  await pilih(host, berkas(new Uint8Array([0x50, 0x4b, 0x03, 0x04]), "a.xlsx"));
  await act(async () => { q(host, "recon-file-clear").click(); });
  expect(q(host, "recon-raw")).not.toBeNull();
  await pilih(host, berkas("Tanggal,Keterangan,Jumlah\n18/11/2026,X,\"1.000,00\"", "a.csv"));
  expect(q(host, "recon-raw").value).toContain("Tanggal,Keterangan");
  mockPost.mockResolvedValueOnce({ data: { total: 0, rows: [], format: {}, sum_in: 0, sum_out: 0 } });
  await act(async () => { q(host, "recon-preview-btn").click(); });
  await flush();
  expect(mockPost.mock.calls[0][1].file_b64).toBeUndefined();
  expect(mockPost.mock.calls[0][1].raw).toContain("Tanggal,Keterangan");
});

test(".xls lama ditolak di layar dengan arahan, tanpa permintaan ke server", async () => {
  const { host } = await render();
  await pilih(host, berkas(new Uint8Array([0xd0, 0xcf, 0x11, 0xe0]), "mutasi_lama.xls"));
  expect(host.textContent).toContain("Simpan Sebagai 'Excel Workbook (.xlsx)'");
  expect(mockPost).not.toHaveBeenCalled();
  expect(q(host, "recon-preview-btn").disabled).toBe(true);
});
