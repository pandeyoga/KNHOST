// Uji variasi isian pelatihan keuangan 18 Nov — MoneyInput menerima "3.374.123" / "Rp 3.374.122,50" / "3,374,123",
// menampilkan teks yang diketik, dan mengirim nilai KANONIK ke pemanggil. Tiga pola pemanggil yang ada di kode:
//  (A) memegang teks apa adanya (`set({ amount: v })` — kas, LPJ, anggaran);
//  (B) memegang angka yang DIBATASI (`Math.min(Number(v), sisa)` — alokasi kwitansi, titipan);
//  (C) mengisi ulang nilainya sendiri (tombol isi otomatis / reset form).
import React, { act, useState } from "react";
import { createRoot } from "react-dom/client";
import MoneyInput from "../MoneyInput";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
let host; let root;
afterEach(async () => { await act(async () => { root.unmount(); }); host.remove(); });
async function mount(el) {
  host = document.createElement("div"); document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(el); });
}
const q = (id) => host.querySelector(`[data-testid="${id}"]`);
async function type(el, value) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new Event("input", { bubbles: true })); });
}
/** Ketik huruf demi huruf seperti peserta (tiap huruf = satu event input). */
async function ketik(el, teks) {
  for (let i = 1; i <= teks.length; i++) await type(el, teks.slice(0, i));
}

const seen = [];
function PegangTeks({ init = "" }) {           // pola A
  const [v, setV] = useState(init);
  return (<><MoneyInput testId="m" value={v} onChange={(x) => { seen.push(x); setV(x); }} />
    <span data-testid="held">{String(v)}</span><button data-testid="reset" onClick={() => setV("250000")} /></>);
}
function PegangAngka({ max }) {                 // pola B (ReceivePaymentModal.setAllocFor)
  const [v, setV] = useState(max);
  return (<><MoneyInput testId="m" value={v} onChange={(x) => setV(Math.min(Math.max(Number(x) || 0, 0), max))} />
    <span data-testid="held">{String(v)}</span></>);
}

beforeEach(() => { seen.length = 0; });

test.each([
  ["3.374.123", 3374123, "Rp 3.374.123"],
  ["3374122,5", 3374122.5, "Rp 3.374.122,50"],   // pratinjau = nilai tersimpan (sen tampil)
  ["3.374.122,50", 3374122.5, "Rp 3.374.122,50"],
  ["3,374,123", 3374123, "Rp 3.374.123"],
  ["1.000.000", 1000000, "Rp 1.000.000"],
])("pola A · ketik %s huruf demi huruf → kotak tetap '%s', pemanggil memegang %d", async (teks, n, pv) => {
  await mount(<PegangTeks />);
  await ketik(q("m"), teks);
  expect(q("m").value).toBe(teks);
  expect(Number(q("held").textContent)).toBe(n);
  expect(q("m-preview").textContent.replace(/\s/g, " ")).toBe(pv);
});

test("pola A · tempel 'Rp 3.374.122,50' sekaligus diterima (dulu ditolak diam-diam); awalan Rp dibuang dari kotak", async () => {
  await mount(<PegangTeks />);
  await type(q("m"), "Rp 3.374.122,50");
  expect(q("m").value).toBe("3.374.122,50");
  expect(seen).toEqual(["3374122.5"]);
  await type(q("m"), "IDR 1,500,000.00");
  expect(q("m").value).toBe("1,500,000.00");
  expect(seen[1]).toBe("1500000");
});

test("pola A · ketik 'Rp 1.000' huruf demi huruf → kotak '1.000', pemanggil 1000", async () => {
  await mount(<PegangTeks />);
  await ketik(q("m"), "Rp 1.000");
  expect(q("m").value).toBe("1.000");
  expect(q("held").textContent).toBe("1000");
});

test("pola A · huruf ditolak, kotak tidak berubah; kosongkan → ''", async () => {
  await mount(<PegangTeks init="1500" />);
  await type(q("m"), "15a00");
  expect(q("m").value).toBe("1500");
  expect(seen).toEqual([]);
  await type(q("m"), "");
  expect(seen).toEqual([""]);
  expect(q("held").textContent).toBe("");
});

test("pola A · minus diterima sebagai angka negatif dan kotak bergaris merah", async () => {
  await mount(<PegangTeks />);
  await ketik(q("m"), "-100");
  expect(q("held").textContent).toBe("-100");
  expect(q("m").className).toContain("border-[#D14343]");
});

test("pola B · nilai dibatasi pemanggil → kotak menampilkan batasnya", async () => {
  await mount(<PegangAngka max={3184867.5} />);
  expect(q("m").value).toBe("3184867.5");
  await type(q("m"), "");
  await ketik(q("m"), "3.374.123");
  expect(q("held").textContent).toBe("3184867.5");
  expect(q("m").value).toBe("3184867.5");
});

test("pola B · koma desimal di bawah batas: '1.000.000,5' tetap 1000000.5 (dulu koma → 0 lalu '5')", async () => {
  await mount(<PegangAngka max={3184867.5} />);
  await type(q("m"), "");
  await ketik(q("m"), "1.000.000,5");
  expect(q("held").textContent).toBe("1000000.5");
  expect(q("m").value).toBe("1.000.000,5");
});

test("pola B · '3,374,123' (gaya Inggris) → batas, bukan 123", async () => {
  await mount(<PegangAngka max={9000000} />);
  await type(q("m"), "");
  await ketik(q("m"), "3,374,123");
  expect(q("held").textContent).toBe("3374123");
});

test("pola C · pemanggil mengisi ulang nilai → kotak menampilkan nilai pemanggil", async () => {
  await mount(<PegangTeks />);
  await ketik(q("m"), "1.000");
  expect(q("m").value).toBe("1.000");
  await act(async () => { q("reset").dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  expect(q("m").value).toBe("250000");
  expect(q("m-preview").textContent.replace(/\s/g, " ")).toBe("Rp 250.000");
});

test("nilai angka dari pemanggil (mis. sisa 3359692.5) tampil & berpratinjau benar", async () => {
  await mount(<MoneyInput testId="m" value={3359692.5} onChange={() => {}} />);
  expect(q("m").value).toBe("3359692.5");
  expect(q("m-preview").textContent.replace(/\s/g, " ")).toBe("Rp 3.359.692,50");
});
