// Pelatihan 18 Nov — klik ganda tidak menutup dialog konfirmasi; pratinjau nominal menampilkan sen.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { overlayDismiss } from "../../utils/overlayDismiss";
import MoneyInput from "../../components/MoneyInput";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

function klik(h, detail) {
  const el = { dataset: {} };
  h.onPointerDown({ target: el, currentTarget: el });
  h.onClick({ target: el, currentTarget: el, detail });
}

test("klik backdrop biasa menutup; klik ke-2 dari klik ganda tidak", () => {
  const tutup = jest.fn();
  const h = overlayDismiss(tutup);
  klik(h, 2);
  expect(tutup).not.toHaveBeenCalled();
  klik(h, 1);
  expect(tutup).toHaveBeenCalledTimes(1);
});

test("pratinjau MoneyInput: bulat tanpa sen, bersen dua angka di belakang koma", async () => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<MoneyInput testId="uji-nominal" value={40864.5} onChange={() => {}} showPreview />); });
  const pv = () => (host.querySelector('[data-testid="uji-nominal-preview"]') || {}).textContent || "";
  expect(pv().replace(/\s/g, " ")).toContain("40.864,50");
  await act(async () => { root.render(<MoneyInput testId="uji-nominal" value={500000} onChange={() => {}} showPreview />); });
  expect(pv().replace(/\s/g, " ")).toContain("500.000");
  expect(pv()).not.toContain(",00");
  await act(async () => { root.unmount(); });
});
