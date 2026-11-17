// Uji peran kustom 18 Nov 2026 (agen A, perburuan cacat) — bilah aksi dokumen & panel Dokumen Terkait mengikuti izin.
//
// Langkah ulang di layar: peran kustom TANPA peran dasar, hanya Hutang (tagihan & kontrabon: lihat + bayar), membuka
// Keuangan › Hutang › Tagihan › rincian → [Pratinjau] [Unduh PDF] [Kirim WA] tampil (server: `document.print` /
// `document_delivery.send` → 403, layar menulis "Gagal mengunduh PDF."), status tanda tangan dipanggil (`esign.view` → 403),
// dan panel "Dokumen Terkait" menjadi bilah merah "Anda belum punya akses untuk melihat Dokumen & Cetak…" + [Coba lagi]
// di setiap rincian tagihan/kontrabon.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import DocumentActionsBar from "../documents/DocumentActionsBar";
import DocRefsPanel from "../documents/trace/DocRefsPanel";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../documents/ESignModal", () => () => null);
jest.mock("../documents/WhatsAppModal", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  for (let i = 0; i < 5; i += 1) await act(async () => {});
  return host;
}
const TOLAK = { response: { status: 403, data: { detail: "Anda belum punya akses untuk melihat Dokumen & Cetak. Minta Admin "
  + "menambahkan akses 'Dokumen, Cetak & Tanda Tangan'." } } };
beforeEach(() => {
  mockGet.mockImplementation((url) => {
    if (url.includes("/esign/signatures/") || url.includes("/documents/refs/")) return Promise.reject(TOLAK);
    if (url.includes("/pdf/doc-types")) return Promise.resolve({ data: [{ doc_type: "vendor_bill", label: "Tagihan", esignable: true }] });
    return Promise.resolve({ data: {} });
  });
});
afterEach(() => { document.body.innerHTML = ""; mockGet.mockReset(); });

const HUTANG = { id: "u1", role: "cr_uji_hutang", permissions: { vendor_bill: ["view", "pay"], contra_bon: ["view", "pay"] } };
const AKSI = ["doc-act-preview", "doc-act-download", "doc-act-wa"];

test("tanpa izin Dokumen: Pratinjau, Unduh PDF, Kirim WA tidak tampil dan status tanda tangan tidak dipanggil", async () => {
  const host = await mount(<DocumentActionsBar docType="vendor_bill" sourceId="vb1" label="Tagihan" esignable currentUser={HUTANG} />);
  expect(AKSI.filter((id) => q(host, id))).toEqual([]);
  expect(mockGet.mock.calls.some(([u]) => u.includes("/esign/signatures/"))).toBe(false);
});

test("pemegang izin Dokumen (cetak, kirim, lihat tanda tangan): ketiga tombol tampil seperti dulu", async () => {
  const dok = { ...HUTANG, permissions: { ...HUTANG.permissions, document: ["view", "print"],
    document_delivery: ["view", "send"], esign: ["view"] } };
  const host = await mount(<DocumentActionsBar docType="vendor_bill" sourceId="vb1" label="Tagihan" esignable currentUser={dok} />);
  expect(AKSI.filter((id) => !q(host, id))).toEqual([]);
  expect(mockGet.mock.calls.some(([u]) => u.includes("/esign/signatures/"))).toBe(true);
});

test("Dokumen Terkait 403: keterangan tenang, bukan bilah galat merah + Coba lagi", async () => {
  const host = await mount(<DocRefsPanel docType="vendor_bill" docId="vb1" />);
  expect(q(host, "docrefs-error")).toBeNull();
  expect(q(host, "docrefs-noaccess").textContent).toMatch(/belum punya akses untuk melihat Dokumen/);
});

test("Dokumen Terkait galat lain (500) tetap bilah galat dengan Coba lagi", async () => {
  mockGet.mockImplementation(() => Promise.reject({ response: { status: 500, data: { detail: "Galat server." } } }));
  const host = await mount(<DocRefsPanel docType="vendor_bill" docId="vb1" />);
  expect(q(host, "docrefs-error")).not.toBeNull();
  expect(q(host, "docrefs-noaccess")).toBeNull();
});
