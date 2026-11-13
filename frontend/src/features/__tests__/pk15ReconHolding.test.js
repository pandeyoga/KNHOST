// PK-15 — alokasi titipan: jawaban 409 tetap tampil di pop-up DAN daftar titipan dimuat ulang; baris dengan alokasi
// yang jurnalnya belum terbit diberi lencana "Jurnal belum terbit".
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ReconHoldingPanel from "../finance/bank/ReconHoldingPanel";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
// Pemilih bawaan (cmdk/radix) diganti <select> polos — yang diuji alur pop-up, bukan komponen pilihannya.
jest.mock("../../components/KNSelect", () => {
  const Pilih = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange(e.target.value)}>
      <option value="">-</option>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: Pilih, KNSelect: Pilih };
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  return { host, root };
}
async function flush() { await act(async () => {}); await act(async () => {}); }
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
async function change(el, value) {
  const proto = el.tagName === "SELECT" ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
    el.dispatchEvent(new Event(el.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
  });
  await flush();
}

const HOLDING = {
  account_code: "2-1950", balance: 10000000, count: 1, max_age_days: 7,
  items: [{ id: "L1", stmt_date: "2026-11-05", amount: 10000000, remaining: 10000000, allocated: 0, age_days: 1,
    needs_action: false, description: "transfer masuk", entity_id: "ent_ksc", gl_failed: [] }],
};

afterEach(() => { mockGet.mockReset(); mockPost.mockReset(); document.body.innerHTML = ""; });

test("alokasi dijawab 409: pesan di pop-up dan daftar titipan dimuat ulang", async () => {
  mockGet.mockImplementation((url) => {
    if (url.includes("/customers")) return Promise.resolve({ data: [{ id: "cus_x", name: "Toko X", entity_id: "ent_ksc" }] });
    if (url.includes("/open-orders")) return Promise.resolve({ data: [{ id: "so_x", number: "SO-X", outstanding: 8000000 }] });
    return Promise.resolve({ data: [] });
  });
  mockPost.mockRejectedValue({ response: { status: 409, data: { detail:
    "Alokasi sebelumnya untuk titipan ini belum tuntas dan baru saja dilanjutkan. Muat ulang, periksa sisa titipan, lalu alokasikan lagi bila perlu." } } });
  const onReload = jest.fn(async () => {});
  const { host } = await mount(<ReconHoldingPanel holding={HOLDING} onReload={onReload} onNotify={() => {}}
    onAction={() => {}} onError={() => {}} />);
  await click(q(host, "recon-allocate-L1"));
  await change(q(document.body, "recon-allocate-customer"), "cus_x");
  await change(q(document.body, "recon-allocate-amount-so_x"), "1000000");
  await click(q(document.body, "recon-allocate-submit"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  expect(onReload).toHaveBeenCalledTimes(1);
  expect(document.body.textContent).toContain("baru saja dilanjutkan");
  expect(q(document.body, "recon-allocate-submit")).not.toBeNull();   // pop-up tetap terbuka
});

test("alokasi dijawab 400: daftar tidak dimuat ulang", async () => {
  mockGet.mockImplementation((url) => {
    if (url.includes("/customers")) return Promise.resolve({ data: [{ id: "cus_x", name: "Toko X", entity_id: "ent_ksc" }] });
    if (url.includes("/open-orders")) return Promise.resolve({ data: [{ id: "so_x", number: "SO-X", outstanding: 8000000 }] });
    return Promise.resolve({ data: [] });
  });
  mockPost.mockRejectedValue({ response: { status: 400, data: { detail: "Σ alokasi melebihi sisa titipan" } } });
  const onReload = jest.fn(async () => {});
  const { host } = await mount(<ReconHoldingPanel holding={HOLDING} onReload={onReload} onNotify={() => {}}
    onAction={() => {}} onError={() => {}} />);
  await click(q(host, "recon-allocate-L1"));
  await change(q(document.body, "recon-allocate-customer"), "cus_x");
  await change(q(document.body, "recon-allocate-amount-so_x"), "1000000");
  await click(q(document.body, "recon-allocate-submit"));
  expect(onReload).not.toHaveBeenCalled();
});

test("lencana Jurnal belum terbit untuk alokasi yang jurnalnya gagal", async () => {
  const h = { ...HOLDING, items: [{ ...HOLDING.items[0], gl_failed: [{ order_number: "SO-Y", amount: 4000000,
    gl_error: "akun tidak aktif" }] }] };
  const { host } = await mount(<ReconHoldingPanel holding={h} onReload={() => {}} onNotify={() => {}}
    onAction={() => {}} onError={() => {}} />);
  const b = q(host, "recon-holding-gl-failed-L1");
  expect(b.textContent).toContain("Jurnal belum terbit");
  expect(b.getAttribute("title")).toContain("SO-Y: akun tidak aktif");
});
