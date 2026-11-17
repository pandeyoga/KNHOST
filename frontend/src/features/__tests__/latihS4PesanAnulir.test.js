// Pelatihan Keuangan 18 Nov (putaran akhir S4) — Transaksi Kas: Manajer menekan [Anulir] pada kas yang sudah dicocokkan
// dengan mutasi bank → server menolak "sudah dicocokkan — lepaskan dulu". Dulu pemuatan ringkasan yang selesai SESUDAH
// penolakan memanggil setError("") sehingga pesan penolakan hilang sebelum terbaca. Kini galat muat dan galat aksi terpisah.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CashManagementView from "../purchasing/CashManagementView";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a),
    patch: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: jest.fn(async () => true),
  askReason: jest.fn(async () => "Salah kategori: ongkos kirim bukan pembelian"),
  askText: jest.fn(async () => null),
  askChoice: jest.fn(async () => null),
  default: {},
}));
jest.mock("../../components/KNSelect", () => () => null);
jest.mock("../../components/KNDatePicker", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function flush() { for (let i = 0; i < 6; i += 1) await act(async () => {}); }   // eslint-disable-line no-await-in-loop
const KAS = { id: "cash_1", number: "KSC/CASH-00057", direction: "out", amount: 417600, status: "posted", ref_type: "manual",
  cash_type: "kas_besar", entity_id: "ent_ksc", category: "pembelian", description: "Ongkos ekspedisi", date: "2026-11-17" };

afterEach(() => { mockGet.mockReset(); mockPost.mockReset(); document.body.innerHTML = ""; });

test("penolakan anulir tetap tampil walau ringkasan selesai dimuat sesudahnya", async () => {
  const ringkasan = [];
  mockGet.mockImplementation((url) => {
    if (url.endsWith("/cash-transactions/summary")) {
      return new Promise((res) => { ringkasan.push(() => res({ data: { kas_kecil: {}, kas_besar: {}, kas_kecil_per_entity: {} } })); });
    }
    if (url.endsWith("/cash-transactions")) return Promise.resolve({ data: { items: [KAS], total: 1 } });
    if (url.endsWith("/entities")) return Promise.resolve({ data: [{ id: "ent_ksc", short_name: "Sukacita" }] });
    return Promise.resolve({ data: [] });
  });
  mockPost.mockImplementation(() => Promise.reject({ response: { status: 409,
    data: { detail: "Transaksi sudah dicocokkan dengan mutasi bank — lepaskan dulu." } } }));
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => {
    createRoot(host).render(<CashManagementView currentUser={{ role: "manager", permissions: { cash: ["*"] } }} selectedEntity="ent_ksc" />);
  });
  await flush();
  const tombol = q(host, "void-cash-cash_1");
  expect(tombol).not.toBeNull();
  await act(async () => { tombol.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
  expect(q(host, "cash-error").textContent).toMatch(/sudah dicocokkan/);
  // ringkasan yang tertunda baru selesai sekarang
  await act(async () => { ringkasan.splice(0).forEach((r) => r()); });
  await flush();
  expect(q(host, "cash-error")?.textContent || "").toMatch(/sudah dicocokkan/);
});
