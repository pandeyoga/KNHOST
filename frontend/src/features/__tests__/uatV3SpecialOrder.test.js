// Cek UI UAT v3 (2026-10-22) — celah antarmuka dari skenario S13 (Pesanan Khusus): riwayat memakai jam lokal
// (bukan potongan string UTC); status dokumen tertaut berbahasa Indonesia; tombol ACC pemenang yang nonaktif
// menyebut isian yang kurang; tanggal "Sample jadi" bawaan = tanggal lokal hari ini; HP menampilkan harga final per item;
// harga khusus yang diajukan tanpa SO menjadi harga langganan.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { formatStamp } from "../../utils/formatters";
import { docStatus } from "../sales/SpecialOrderShared";
import DecideModal from "../rnd/DecideModal";
import SampleFinishModal from "../rnd/SampleFinishModal";
import { MobileSpecialOrderDetail } from "../sales/mobile/MobileSalesFlows";
import SpecialPriceRequestForm from "../pricing/SpecialPriceRequestForm";

jest.mock("../rnd/rndApi", () => ({ sampleRequiredTests: () => Promise.resolve({ missing: [] }) }));   // bukan jest.fn: resetMocks CRA
jest.mock("../../services/apiClient", () => ({ __esModule: true, API: "/api", default: { get: jest.fn(), post: jest.fn() } }));
jest.mock("@/components/KNDatePicker", () => (p) => <input data-testid={p["data-testid"]} value={p.value} readOnly />);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const tick = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });

async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await tick();
  return root;
}
const localToday = () => {
  const d = new Date(); const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};

test("stempel riwayat: ISO UTC → jam lokal; teks tanpa zona waktu apa adanya", () => {
  const iso = "2026-10-21T22:36:12.5+00:00";
  const d = new Date(iso); const p = (n) => String(n).padStart(2, "0");
  expect(formatStamp(iso)).toBe(`${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`);
  expect(formatStamp("2026-10-22T05:36")).toBe("2026-10-22 05:36");
  expect(formatStamp("")).toBe("");
});

test("status dokumen tertaut OD tidak tampil sebagai kode mentah", () => {
  expect(docStatus("waiting_stock")).toBe("Menunggu stok");
  expect(docStatus("pending")).toBe("Belum diterima");
  expect(docStatus("approved")).toBe("Disetujui");
});

test("ACC pemenang: tombol nonaktif menyebut isian yang kurang", async () => {
  const sample = { id: "smp1", number: "SMP-1", title: "Uji", rounds: [{ supplier_id: "sup1", result: "acc", score: 90 }],
    participants: [{ supplier_id: "sup1", supplier_name: "PT Uji" }] };
  const root = await mount(<DecideModal sample={sample} reasons={[]} onClose={() => {}} onConfirm={() => {}} busy={false} />);
  expect(q("decide-missing").textContent).toMatch(/alasan keputusan, harga kesepakatan/);
  expect(q("decide-confirm").disabled).toBe(true);
  act(() => root.unmount());
});

test("Sample jadi: tanggal bawaan = tanggal lokal hari ini (bukan kosong → tanggal UTC server)", async () => {
  const root = await mount(<SampleFinishModal mode="finish" sample={{ number: "SMP-1" }} onClose={() => {}} onConfirm={() => {}} />);
  expect(q("sample-finish-date").value).toBe(localToday());
  act(() => root.unmount());
});

test("HP: OD multi-item menampilkan harga final per item (bukan Rp 0/meter)", async () => {
  const axios = require("../../services/apiClient").default;
  axios.get.mockResolvedValue({ data: { id: "sord1", number: "SORD-1", status: "in_production", customer_name: "Toko", items: [],
    chain: { review: {}, pricing: { locked: true, mode: "items", total: 19500000, final_unit_price: 0, unit: "meter",
      items: [{ line_no: 1, unit: "meter", final_unit_price: 84500 }, { line_no: 2, unit: "meter", final_unit_price: 55250 }] } } } });
  const root = await mount(<MobileSpecialOrderDetail id="sord1" onBack={() => {}} />);
  const txt = q("m-od-final-price").textContent;
  expect(txt).toMatch(/84\.500\/meter/);
  expect(txt).toMatch(/55\.250\/meter/);
  expect(txt).not.toMatch(/Rp\s?0\/meter/);
  act(() => root.unmount());
});

test("harga khusus tanpa SO = harga langganan (catatan tampil, tanpa pilihan 'pesanan ini saja'); dari SO pilihan tetap ada", async () => {
  const product = { id: "p1", name: "ALICE", price: 44000 };
  const customer = { id: "c1", name: "Toko" };
  let root = await mount(<SpecialPriceRequestForm product={product} customer={customer} />);
  expect(q("spr-standing-note").textContent).toMatch(/harga langganan/);
  await act(async () => { q("spr-more-toggle").click(); });
  expect(q("spr-standing-toggle")).toBeNull();
  expect(document.body.textContent).toMatch(/Berlaku sampai/);          // berlaku sampai bisa diatur
  act(() => root.unmount());
  root = await mount(<SpecialPriceRequestForm product={product} customer={customer} soId="so1" />);
  expect(q("spr-standing-note")).toBeNull();
  await act(async () => { q("spr-more-toggle").click(); });
  expect(q("spr-standing-toggle").checked).toBe(false);              // dari SO: bawaan untuk pesanan ini saja
  act(() => root.unmount());
});
