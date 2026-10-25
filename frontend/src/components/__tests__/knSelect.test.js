// UAT 24 Okt (audit UI tahap 2) — P-03 (G0-04/05/06): KNSelect tanpa ✓ pada placeholder, sorotan awal di nilai aktif,
// nilai tak dikenal tampil berlabel, daftar kosong berpesan.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import KNSelect from "../KNSelect";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView || (() => {});
Element.prototype.hasPointerCapture = Element.prototype.hasPointerCapture || (() => false);
global.ResizeObserver = global.ResizeObserver || class { observe() {} unobserve() {} disconnect() {} };

const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await flush();
  return { host, root };
}
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const MONTHS = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
  .map((label, i) => ({ value: String(i + 1).padStart(2, "0"), label }));

async function openCombo(id) {
  await act(async () => { q(id).click(); });
  await flush();
}

test("combobox: sorotan awal di nilai aktif (bukan butir pertama) & ✓ hanya di nilai terpilih", async () => {
  const { root } = await mount(<KNSelect value="10" onValueChange={() => {}} options={MONTHS} data-testid="bulan" />);
  await openCombo("bulan");
  expect(q("bulan-option-10").getAttribute("aria-selected")).toBe("true");
  expect(q("bulan-option-01").getAttribute("aria-selected")).not.toBe("true");
  expect(q("bulan-option-10").getAttribute("data-kn-chosen")).toBe("true");
  expect(q("bulan-option-01").getAttribute("data-kn-chosen")).toBeNull();
  await act(async () => { root.unmount(); });
});

test("combobox: opsi bernilai '' tidak tercentang — disembunyikan saat kosong, abu saat nilai terisi", async () => {
  const opts = [{ value: "", label: "Semua divisi" }, ...MONTHS.slice(0, 6)];
  let r = await mount(<KNSelect value="" onValueChange={() => {}} options={opts} data-testid="div" />);
  expect(q("div-value").textContent).toBe("Semua divisi");
  await openCombo("div");
  expect(q("div-option-empty")).toBeNull();
  expect(document.body.querySelector('[data-testid="div-popover"] [data-kn-chosen="true"]')).toBeNull();
  await act(async () => { r.root.unmount(); });
  document.body.innerHTML = "";
  r = await mount(<KNSelect value="03" onValueChange={() => {}} options={opts} data-testid="div" />);
  await openCombo("div");
  expect(q("div-option-empty")).not.toBeNull();
  expect(q("div-option-empty").getAttribute("data-kn-chosen")).toBeNull();
  await act(async () => { r.root.unmount(); });
  document.body.innerHTML = "";
});

test("nilai tersimpan yang tak ada di daftar tampil berlabel (combobox & Radix); daftar belum termuat = perilaku lama", async () => {
  let r = await mount(<KNSelect value="internal" onValueChange={() => {}} options={MONTHS} data-testid="jenis" />);
  expect(q("jenis-value").textContent).toBe("internal (tidak ada di daftar)");
  expect(q("jenis").getAttribute("data-kn-unknown")).toBe("true");
  await act(async () => { r.root.unmount(); });
  document.body.innerHTML = "";
  r = await mount(<KNSelect value="internal" onValueChange={() => {}} options={MONTHS.slice(0, 3)}
    unknownLabel={(v) => `${v} (lama)`} data-testid="jenis2" />);
  expect(q("jenis2").getAttribute("data-kn-unknown")).toBe("true");
  expect(q("jenis2").textContent).toContain("internal (lama)");
  await act(async () => { r.root.unmount(); });
  document.body.innerHTML = "";
  r = await mount(<KNSelect value="internal" onValueChange={() => {}} options={[]} searchable data-testid="jenis3" />);
  expect(q("jenis3").getAttribute("data-kn-unknown")).toBeNull();
  await act(async () => { r.root.unmount(); });
  document.body.innerHTML = "";
});

test("Radix: placeholder tampil di pemicu, nilai normal tidak berlabel peringatan", async () => {
  const r = await mount(<KNSelect value="" onValueChange={() => {}} options={MONTHS.slice(0, 3)} placeholder="Pilih bulan" data-testid="pendek" />);
  expect(q("pendek").textContent).toContain("Pilih bulan");
  expect(q("pendek").getAttribute("data-kn-empty")).toBe("true");
  expect(q("pendek").getAttribute("data-kn-unknown")).toBeNull();
  await act(async () => { r.root.unmount(); });
  document.body.innerHTML = "";
});

test("daftar tanpa opsi nyata menampilkan emptyText", async () => {
  const r = await mount(<KNSelect value="" onValueChange={() => {}} options={[]} searchable data-testid="kosong" />);
  await openCombo("kosong");
  expect(q("kosong-empty-state").textContent).toBe("Belum ada pilihan");
  await act(async () => { r.root.unmount(); });
  document.body.innerHTML = "";
});
