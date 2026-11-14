// PK-27 (IV-06, IV-07) — sisi layar tanpa peramban:
//  · "Roll berbiaya 0" (tab rekonsiliasi persediaan): memuat · galat (kotak merah + Coba lagi) · kosong (satu teks, hanya
//    sesudah muat berhasil); dua daftar berhalaman (Masih di gudang / Sudah terkirim) dengan jumlah total dari server;
//    status roll ikon + teks + warna, tanpa kode mentah.
//  · Rincian retur beli: "Nilai buku roll" + "Selisih terhadap nota"; keterangan bila selisih belum masuk jurnal.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ZeroCostRollsSection, { TEKS_GALAT, TEKS_KOSONG, TEKS_MEMUAT } from "../finance/ZeroCostRollsSection";
import ReturnBookValue, { TEKS_BELUM_JURNAL } from "../purchasing/ReturnBookValue";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../../components/EntityBadge", () => (p) => <span data-testid="pt">{p.entityId}</span>);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function settle() { for (let i = 0; i < 4; i += 1) await act(async () => {}); }
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await settle();
  return { host, root };
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
}

const ISI = {
  in_stock: { total: 51, items: [{ roll_id: "r_nol", roll_no: "RL-00005", product_name: "Batik Mega Mendung",
    entity_id: "ent_ksc", length_remaining: 30, status: "available" },
  { roll_id: "r_wip", roll_no: "RL-00009", product_name: "Tenun", entity_id: "ent_ksc", length_remaining: 12.5,
    status: "in_transit_transfer" }] },
  shipped: { total: 1, items: [{ shipment_no: "SJ-00007", order_number: "SO-00012", roll_no: "RL-00002", length: 100,
    shipped_at: "2026-11-14T01:00:00+00:00", entity_id: "ent_ksc" }] },
  page: 1, page_size: 50,
};

afterEach(() => { mockGet.mockReset(); document.body.innerHTML = ""; });

test("U15 — memuat lalu dua daftar dengan jumlah total, status berlabel, tanpa kode mentah", async () => {
  let selesai;
  mockGet.mockReturnValueOnce(new Promise((r) => { selesai = r; }));
  const { host } = await mount(<ZeroCostRollsSection />);
  expect(q(host, "zc-loading").textContent).toBe(TEKS_MEMUAT);
  await act(async () => { selesai({ data: ISI }); });
  await settle();
  expect(mockGet).toHaveBeenCalledWith("/api/gl/zero-cost-rolls", { params: { page: 1, page_size: 50 } });
  expect(q(host, "zc-stock-title").textContent).toContain("Masih di gudang · 51 roll");
  expect(q(host, "zc-shipped-title").textContent).toContain("Sudah terkirim · 1 roll");
  const head = [...q(host, "zc-stock-table").querySelectorAll("th")].map((t) => t.textContent);
  expect(head).toEqual(["Roll", "Barang", "PT", "Sisa", "Status"]);
  const headKirim = [...q(host, "zc-shipped-table").querySelectorAll("th")].map((t) => t.textContent);
  expect(headKirim).toEqual(["Surat Jalan", "Pesanan", "Roll", "Panjang", "Tanggal"]);
  const baris = q(host, "zc-stock-row-r_nol");
  expect(baris.textContent).toContain("RL-00005");
  expect(baris.querySelector(".status-pill").textContent).toBe("Tersedia");
  expect(baris.querySelector(".status-pill svg")).not.toBeNull();
  expect(q(host, "zc-stock-row-r_wip").textContent).toContain("Dalam transfer gudang");
  expect(host.textContent).not.toMatch(/in_transit_transfer|available/);
  expect(q(host, "zc-shipped-row-0").textContent).toContain("SJ-00007");
  expect(q(host, "zc-shipped-row-0").textContent).toContain("14 Nov 2026");
  expect(q(host, "zc-empty")).toBeNull();
  // 51 roll → dua halaman: halaman 2 daftar gudang memuat ulang dengan page=2, daftar terkirim tetap halaman 1
  mockGet.mockResolvedValue({ data: { ...ISI, in_stock: { total: 51, items: [] }, page: 2 } });
  await click(q(host, "zc-stock-pager-next"));
  expect(mockGet).toHaveBeenCalledWith("/api/gl/zero-cost-rolls", { params: { page: 2, page_size: 50 } });
  expect(mockGet).toHaveBeenCalledWith("/api/gl/zero-cost-rolls", { params: { page: 1, page_size: 50 } });
});

test("U15 — galat: kotak merah + Coba lagi, teks kosong TIDAK tampil; coba lagi memuat ulang", async () => {
  mockGet.mockRejectedValueOnce({ response: { status: 503, data: { detail: "Server sibuk" } } });
  const { host } = await mount(<ZeroCostRollsSection />);
  const galat = q(host, "zc-error");
  expect(galat).not.toBeNull();
  expect(galat.textContent).toContain(TEKS_GALAT);
  expect(host.textContent).not.toContain(TEKS_KOSONG);
  mockGet.mockResolvedValueOnce({ data: ISI });
  const tombol = [...galat.querySelectorAll("button")].find((b) => /Coba lagi/.test(b.textContent));
  await click(tombol);
  expect(q(host, "zc-error")).toBeNull();
  expect(q(host, "zc-stock-row-r_nol")).not.toBeNull();
});

test("U15 — kosong: satu teks kosong, tanpa tabel dan tanpa angka 0 ganda", async () => {
  mockGet.mockResolvedValueOnce({ data: { in_stock: { items: [], total: 0 }, shipped: { items: [], total: 0 } } });
  const { host } = await mount(<ZeroCostRollsSection />);
  expect(q(host, "zc-empty").textContent).toBe(TEKS_KOSONG);
  expect(host.querySelectorAll("table")).toHaveLength(0);
  expect(q(host, "zc-stock")).toBeNull();
});

test("retur beli — nilai buku & selisih; keterangan bila selisih belum masuk jurnal", async () => {
  const { host } = await mount(<ReturnBookValue ret={{ book_value: 525000, book_value_diff: 25000,
    book_value_posted: false }} />);
  expect(q(host, "pr-book-value").textContent).toContain("Nilai buku roll");
  expect(q(host, "pr-book-value-amount").textContent).toMatch(/525\.000/);
  expect(q(host, "pr-book-value-diff").textContent).toMatch(/25\.000/);
  expect(q(host, "pr-book-value-unposted").textContent).toBe(TEKS_BELUM_JURNAL);
  const ok = await mount(<ReturnBookValue ret={{ book_value: 525000, book_value_diff: 25000, book_value_posted: true }} />);
  expect(q(ok.host, "pr-book-value-unposted")).toBeNull();
  const lama = await mount(<ReturnBookValue ret={{ total_amount: 500000 }} />);
  expect(q(lama.host, "pr-book-value")).toBeNull();
  const sama = await mount(<ReturnBookValue ret={{ book_value: 500000, book_value_diff: 0, book_value_posted: true }} />);
  expect(q(sama.host, "pr-book-value-diff").textContent).toBe("Tidak ada");
});
