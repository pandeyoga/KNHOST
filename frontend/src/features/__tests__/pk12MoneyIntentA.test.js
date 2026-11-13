// PK-12 (kelompok A) — kunci idempotensi form uang di layar.
// U11: Catat Transaksi kas — klik ganda saat menunggu jawaban tidak mengirim dua kali; tombol mati; header terisi.
// U12: Jurnal manual — koneksi putus lalu simpan lagi tanpa mengubah isi → Idempotency-Key SAMA.
// U13: Jurnal manual — server menolak (400), isi diperbaiki, simpan lagi → Idempotency-Key BERBEDA.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CashManagementView from "../purchasing/CashManagementView";
import JournalEntryModal from "../finance/JournalEntryModal";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a),
    patch: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: jest.fn(async () => true),
  askReason: jest.fn(async () => null),
  askText: jest.fn(async () => null),
  askChoice: jest.fn(async () => null),
  default: {},
}));
// Pemilih bawaan (cmdk/radix) & kalender (radix popover) diganti isian polos — yang diuji logika kirim, bukan pemilihnya.
jest.mock("../../components/KNSelect", () => (p) => (
  <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
    <option value="">-</option>
    {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
  </select>
));
jest.mock("../../components/KNDatePicker", () => (p) => (
  <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange && p.onChange(e.target.value)} />
));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function flush() { await act(async () => {}); await act(async () => {}); }
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await flush();
  return { host, root };
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
}
async function type(el, value) {
  const proto = el.tagName === "SELECT" ? HTMLSelectElement.prototype
    : el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
  await act(async () => {
    setter.call(el, value);
    el.dispatchEvent(new Event(el.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
  });
}
const keyOf = (call) => call?.[2]?.headers?.["Idempotency-Key"];

afterEach(() => { mockGet.mockReset(); mockPost.mockReset(); document.body.innerHTML = ""; });

describe("U11 — CashManagementView: Catat Transaksi", () => {
  test("klik ganda saat menunggu jawaban → post 1 kali, tombol mati, Idempotency-Key terisi", async () => {
    mockGet.mockImplementation((url) => {
      if (url.endsWith("/cash-transactions/summary")) return Promise.resolve({ data: { kas_kecil: {}, kas_besar: {}, kas_kecil_per_entity: {} } });
      if (url.endsWith("/entities")) return Promise.resolve({ data: [{ id: "ent_ksc", short_name: "Sukacita" }] });
      return Promise.resolve({ data: [] });
    });
    let resolvePost;
    mockPost.mockImplementation(() => new Promise((res) => { resolvePost = res; }));
    const user = { role: "admin", permissions: { cash: ["*"] } };
    const { host } = await mount(<CashManagementView currentUser={user} selectedEntity="ent_ksc" />);

    await click(q(host, "create-cash-button"));
    await flush();
    await type(q(host, "cash-amount-input"), "75000");
    await type(q(host, "cash-description-input"), "Beli ATK");

    const btn = q(host, "submit-cash-button");
    expect(btn.disabled).toBe(false);
    await click(btn);                                   // klik pertama — jawaban server ditunda
    await click(q(host, "submit-cash-button"));         // klik kedua saat masih menunggu
    await flush();
    expect(mockPost).toHaveBeenCalledTimes(1);
    // Selama jawaban belum datang: tombol kirim dan tombol batal mati.
    expect(q(host, "submit-cash-button").disabled).toBe(true);
    expect(q(host, "cancel-cash-button").disabled).toBe(true);
    const [url, body] = mockPost.mock.calls[0];
    expect(url).toBe("/api/cash-transactions");
    expect(body).toEqual(expect.objectContaining({ amount: 75000, direction: "out", description: "Beli ATK" }));
    expect(keyOf(mockPost.mock.calls[0])).toMatch(/^kas-/);

    await act(async () => { resolvePost({ data: { number: "KSC/CASH-0001", direction: "out" } }); });
    await flush();
    expect(q(host, "cash-notice").textContent).toContain("KSC/CASH-0001");
    expect(mockPost).toHaveBeenCalledTimes(1);
  });
});

const ACCOUNTS = [
  { code: "1-1100", name: "Kas", is_postable: true },
  { code: "6-1000", name: "Beban Sewa", is_postable: true },
];
async function fillJournal(host) {
  await type(q(host, "je-description"), "Penyesuaian sewa");
  await type(q(host, "je-line-account-0"), "6-1000");
  await type(q(host, "je-line-debit-0"), "250000");
  await type(q(host, "je-line-account-1"), "1-1100");
  await type(q(host, "je-line-credit-1"), "250000");
}

describe("U12/U13 — JournalEntryModal: kunci per niat", () => {
  beforeEach(() => { mockGet.mockResolvedValue({ data: { closed: false } }); });

  test("U12 — koneksi putus lalu simpan ulang isi yang sama → Idempotency-Key sama", async () => {
    mockPost
      .mockRejectedValueOnce(Object.assign(new Error("Network Error"), { code: "ERR_NETWORK" }))
      .mockResolvedValueOnce({ data: { id: "je_1", number: "JE-0001" } });
    const onSaved = jest.fn(async () => {});
    const { host } = await mount(<JournalEntryModal accounts={ACCOUNTS} onClose={() => {}} onSaved={onSaved} />);
    await fillJournal(host);

    await click(q(host, "je-submit"));
    await flush();
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(onSaved).not.toHaveBeenCalled();
    expect(q(host, "je-error")).not.toBeNull();

    await click(q(host, "je-submit"));
    await flush();
    expect(mockPost).toHaveBeenCalledTimes(2);
    expect(onSaved).toHaveBeenCalledTimes(1);
    const [k1, k2] = mockPost.mock.calls.map(keyOf);
    expect(mockPost.mock.calls[0][0]).toBe("/api/gl/journal");
    expect(k1).toMatch(/^je-/);
    expect(k2).toBe(k1);
  });

  test("U13 — server menjawab 400, isi diperbaiki, simpan lagi → Idempotency-Key berbeda", async () => {
    mockPost
      .mockRejectedValueOnce({ response: { status: 400, data: { detail: "Akun 6-1000 tidak aktif untuk PT ini." } } })
      .mockResolvedValueOnce({ data: { id: "je_2", number: "JE-0002" } });
    const onSaved = jest.fn(async () => {});
    const { host } = await mount(<JournalEntryModal accounts={ACCOUNTS} onClose={() => {}} onSaved={onSaved} />);
    await fillJournal(host);

    await click(q(host, "je-submit"));
    await flush();
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(q(host, "je-error").textContent).toContain("tidak aktif");

    await type(q(host, "je-description"), "Penyesuaian sewa (akun diperbaiki)");
    await click(q(host, "je-submit"));
    await flush();
    expect(mockPost).toHaveBeenCalledTimes(2);
    const [k1, k2] = mockPost.mock.calls.map(keyOf);
    expect(k1).toMatch(/^je-/);
    expect(k2).toMatch(/^je-/);
    expect(k2).not.toBe(k1);
    expect(mockPost.mock.calls[1][1].description).toBe("Penyesuaian sewa (akun diperbaiki)");
  });
});
