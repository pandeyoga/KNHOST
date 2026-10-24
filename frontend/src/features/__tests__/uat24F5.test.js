// UAT 24 Okt — fase F5: P17 pratinjau lampiran di halaman (tanpa unduh/tanpa token di URL) · P12 strip sorotan POS.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { kindOf, fileNameOf } from "../../hooks/useBlobUrl";
import AttachmentGallery from "../../components/AttachmentThumb";
import { ProductStrip } from "../pos/PosHighlightStrips";

jest.mock("axios", () => {
  const get = jest.fn(() => Promise.resolve({ data: new Blob(["x"], { type: "image/png" }) }));
  const inst = { get, post: jest.fn(), defaults: { headers: { common: {} } }, interceptors: { response: { use: jest.fn() }, request: { use: jest.fn() } } };
  return { __esModule: true, default: inst, ...inst };
});
jest.mock("../../services/apiClient", () => ({ __esModule: true, default: { get: () => Promise.resolve({ data: [] }) }, API: "/api" }));
jest.mock("@/utils/escapeLayers", () => ({ useEscapeClose: () => {} }));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
globalThis.URL.createObjectURL = jest.fn(() => "blob:uji");

test("P17 — jenis lampiran dikenali dari content-type atau ekstensi", () => {
  expect(kindOf({ content_type: "image/jpeg" })).toBe("image");
  expect(kindOf({ filename: "bukti.MP4" })).toBe("video");
  expect(kindOf({ original_filename: "surat.pdf" })).toBe("pdf");
  expect(kindOf({ filename: "data.xlsx" })).toBe("file");
  expect(fileNameOf({ original_filename: "a.png" })).toBe("a.png");
});

test("P17 — galeri lampiran: thumbnail dimuat lewat axios (blob), klik membuka lightbox di halaman yang sama", async () => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  const items = [{ url: "/api/sales-returns/r1/attachments/a1/download", filename: "cacat.jpg", content_type: "image/jpeg" },
    { url: "/api/sales-returns/r1/attachments/a2/download", filename: "sj.pdf", content_type: "application/pdf" }];
  await act(async () => { root.render(<AttachmentGallery items={items} testId="uji" />); });
  await act(async () => { await Promise.resolve(); });
  const axios = require("axios").default;
  expect(axios.get).toHaveBeenCalledWith(items[0].url, { responseType: "blob" });
  expect(document.querySelectorAll("a[href]").length).toBe(0);                 // tidak ada href mentah
  await act(async () => { document.querySelector('[data-testid="uji-thumb-0"]').click(); });
  expect(document.querySelector('[data-testid="uji-lightbox"]')).not.toBeNull();
  expect(document.querySelector('[data-testid="uji-lightbox-download"]').textContent).toMatch(/Unduh asli/);
  await act(async () => { document.querySelector('[data-testid="uji-lightbox-next"]').click(); });
  expect(document.querySelector('[data-testid="uji-lightbox-caption"]').textContent).toMatch(/sj\.pdf/);
  act(() => root.unmount());
});

test("P12 — strip sorotan kosong tidak dirender; berisi menampilkan lencana alasan", async () => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<ProductStrip title="Rekomendasi" icon={() => null} items={[]} loading={false} onAdd={() => {}} testId="rec" />); });
  expect(host.innerHTML).toBe("");
  const it = { product_id: "p1", sku: "KN-1", product_name: "Rayon", price: 25000, available_qty: 10, reason: "desain sama" };
  await act(async () => { root.render(<ProductStrip title="Rekomendasi" icon={() => null} items={[it]} loading={false} onAdd={() => {}} testId="rec" badge={(p) => p.reason} />); });
  expect(host.querySelector('[data-testid="rec-p1"]').textContent).toMatch(/desain sama/);
  act(() => root.unmount());
});
