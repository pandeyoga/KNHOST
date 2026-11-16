// Cek layar 16 Nov (pemilik: "kenapa ada 2 kembali?") — sesudah melompat dari layar lain ke rincian dokumen, bilah
// layar asal (PK-44) dan tombol kembali rincian dulu bertumpuk. Kini SATU baris: "← Kembali ke {asal}" (utama) +
// tautan kecil "{Daftar …}"; bilah asal di atas layar tidak dirender selama rincian itu tampil. Tanpa layar asal:
// tombol rincian seperti dulu.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { AppNavProvider } from "../../context/AppNavContext";
import BackToOriginBar from "../../components/BackToOriginBar";
import { DetailBack, DetailHeader, listLabelOf } from "../../components/DetailParts";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelectorAll(`[data-testid="${id}"]`);
const ASAL = { view: "gr-ir", label: "GR/IR", at: "makloon-orders" };

async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  return { host, root };
}
afterEach(() => { document.body.innerHTML = ""; });

test("tanpa layar asal: satu tombol rincian seperti dulu", async () => {
  const onBack = jest.fn();
  const { host } = await mount(
    <AppNavProvider role="admin"><DetailHeader onBack={onBack} backLabel="Kembali ke Daftar Order Makloon"
      backTestId="mko-detail-back" title="KSC/MKO-1" /></AppNavProvider>);
  expect(q(host, "mko-detail-back")).toHaveLength(1);
  expect(q(host, "mko-detail-back")[0].textContent).toContain("Kembali ke Daftar Order Makloon");
  expect(q(host, "back-to-origin")).toHaveLength(0);
  await act(async () => { q(host, "mko-detail-back")[0].click(); });
  expect(onBack).toHaveBeenCalled();
});

test("dengan layar asal: satu baris — Kembali ke asal (utama) + Daftar (tautan), bilah asal tidak tampil", async () => {
  const onBack = jest.fn();
  const onGoBack = jest.fn();
  const { host, root } = await mount(
    <AppNavProvider role="admin" origin={ASAL} onGoBack={onGoBack}>
      <BackToOriginBar origin={ASAL} onBack={onGoBack} />
      <DetailHeader onBack={onBack} backLabel="Kembali ke Daftar Order Makloon" backTestId="mko-detail-back" title="X" />
    </AppNavProvider>);
  expect(q(host, "back-to-origin-bar")).toHaveLength(0);
  expect(q(host, "back-to-origin")).toHaveLength(1);
  expect(q(host, "back-to-origin")[0].textContent).toContain("Kembali ke GR/IR");
  const daftar = q(host, "mko-detail-back");
  expect(daftar).toHaveLength(1);
  expect(daftar[0].textContent).toBe("Daftar Order Makloon");
  expect(host.textContent.match(/Kembali/g)).toHaveLength(1);
  await act(async () => { q(host, "back-to-origin")[0].click(); });
  expect(onGoBack).toHaveBeenCalledWith(ASAL);
  await act(async () => { daftar[0].click(); });
  expect(onBack).toHaveBeenCalled();
  // Rincian ditutup (daftar tampil) → bilah asal kembali tampil sendiri.
  await act(async () => {
    root.render(<AppNavProvider role="admin" origin={ASAL} onGoBack={onGoBack}>
      <BackToOriginBar origin={ASAL} onBack={onGoBack} /></AppNavProvider>);
  });
  expect(q(host, "back-to-origin-bar")).toHaveLength(1);
});

test("DetailBack lepas (panel 360) memakai label daftar dari teks tombol", async () => {
  const { host } = await mount(
    <AppNavProvider role="admin" origin={ASAL} onGoBack={() => {}}>
      <DetailBack onBack={() => {}} label="Kembali ke daftar" testId="supplier-360-back" className="secondary-button" />
    </AppNavProvider>);
  expect(q(host, "supplier-360-back")[0].textContent).toBe("Daftar");
  expect(listLabelOf("Kembali ke daftar Kedatangan")).toBe("Daftar Kedatangan");
  expect(listLabelOf("Kembali")).toBe("Daftar");
});
