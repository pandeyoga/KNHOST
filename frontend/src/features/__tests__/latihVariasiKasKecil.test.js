// Uji variasi isian pelatihan keuangan 18 Nov — form LPJ Kas Kecil (SettlementForm) dengan MoneyInput:
//  · "185.000,50" / "47.000" / "Rp 1.250" dibaca benar → isi POST = nominal persis, total di layar sama dengan yang dikirim;
//  · baris bernominal minus atau beruraian tanpa nominal → ditolak dengan pesan (dulu dibuang diam-diam saat simpan,
//    padahal Total Pengeluaran di layar ikut menghitung minusnya);
//  · baris kosong total (belum diisi) tetap diabaikan seperti dulu.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import SettlementForm from "../pettycash/SettlementForm";

const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: () => Promise.resolve({ data: [] }), post: (...a) => mockPost(...a), patch: (...a) => mockPost(...a),
    defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => <select data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />;
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />,
  formatDateId: (v) => String(v || ""),
}));
jest.mock("../../components/KNMonthPicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange(e.target.value)} />,
  formatPeriodId: (v) => String(v || ""),
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let root;
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(el); });
  await flush();
}
async function click(el) { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await flush(); }
async function ketik(el, value) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new Event("input", { bubbles: true })); });
  await flush();
}
async function ketikHuruf(el, teks) { for (let i = 1; i <= teks.length; i++) await ketik(el, teks.slice(0, i)); }

const PD = { id: "ca1", number: "PD-0001", total_amount: 500000, status: "disbursed" };
beforeEach(() => { mockPost.mockReset(); mockPost.mockResolvedValue({ data: { id: "stl1" } }); });
afterEach(async () => { await act(async () => { root.unmount(); }); document.body.innerHTML = ""; });

async function formDuaBaris(a0, a1, d1 = "Fotokopi") {
  await mount(<SettlementForm categories={[]} preselectPd={PD} selectedEntity="ent_ksc" onCancel={() => {}} onSaved={() => {}} />);
  await ketik(q("stl-line-desc-0"), "Bensin");
  await ketikHuruf(q("stl-line-amount-0"), a0);
  await click(q("stl-add-line"));
  await ketik(q("stl-line-desc-1"), d1);
  if (a1) await ketikHuruf(q("stl-line-amount-1"), a1);
}

test("nominal bergaya Indonesia dibaca persis; total layar = yang dikirim", async () => {
  await formDuaBaris("185.000,50", "47.000");
  expect(q("stl-total-pengeluaran").textContent.replace(/\s/g, " ")).toBe("Rp 232.001");
  await click(q("stl-submit"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  expect(mockPost.mock.calls[0][1].expense_lines.map((l) => l.amount)).toEqual([185000.5, 47000]);
});

test("baris bernominal minus ditolak dengan pesan, tidak dikirim", async () => {
  await formDuaBaris("185.000", "-5.000");
  await click(q("stl-submit"));
  expect(mockPost).not.toHaveBeenCalled();
  expect(q("stl-form-error").textContent).toContain("baris 2: nominal tidak boleh minus");
});

test("baris beruraian tanpa nominal ditolak (dulu dibuang diam-diam)", async () => {
  await formDuaBaris("185.000", "", "Parkir");
  await click(q("stl-submit"));
  expect(mockPost).not.toHaveBeenCalled();
  expect(q("stl-form-error").textContent).toContain("baris 2: isi nominalnya atau hapus barisnya");
});

test("baris kosong total tetap diabaikan", async () => {
  await formDuaBaris("Rp 1.250", "", "");
  await click(q("stl-submit"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  expect(mockPost.mock.calls[0][1].expense_lines).toEqual([expect.objectContaining({ description: "Bensin", amount: 1250 })]);
});

// Daftar Kas Kecil: LPJ yang DIAJUKAN melebihi PD → baris berlabel "Perkiraan hutang reimburse" dan tetap bertombol
// "Buka" (dulu "Bayar" yang ditolak server, sehingga manajer tidak bisa membuka PD untuk menyetujui LPJ dari barisnya).
import { sisaText, bolehBayarBaris } from "../pettycash/PettyCashView";

test("LPJ diajukan > PD: perkiraan, tanpa Bayar; LPJ dijurnal: hutang reimburse + Bayar", () => {
  const diajukan = { status: "submitted", refund_due: 0, reimburse_due: 50000 };
  expect(sisaText(diajukan).replace(/\s/g, " ")).toBe("Perkiraan hutang reimburse Rp 50.000");
  expect(bolehBayarBaris({ settlement: diajukan })).toBe(false);
  const dijurnal = { status: "posted_to_gl", refund_due: 0, reimburse_due: 50000 };
  expect(sisaText(dijurnal).replace(/\s/g, " ")).toBe("Hutang reimburse Rp 50.000");
  expect(bolehBayarBaris({ settlement: dijurnal })).toBe(true);
  expect(sisaText({ status: "draft", refund_due: 268000, reimburse_due: 0 }).replace(/\s/g, " "))
    .toBe("Perkiraan sisa kembali Rp 268.000");
});
