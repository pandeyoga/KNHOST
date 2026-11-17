// Pelatihan keuangan 18 Nov 2026 (Bagian B · Kas & Bank, F09 Transaksi Kas):
// pratinjau anggaran kas keluar hanya diminta bila akun memegang `budget.view`. Tanpa izin itu (Finance) permintaan
// POST /finance/budget-check dulu selalu dijawab 403 (galat merah di konsol) setiap nominal diketik.
// F10 Rekonsiliasi (`02_STANDAR` N5): "Catat biaya bank" / "Catat bunga bank" / "Titipkan" melahirkan kas + jurnal →
// bertanya dulu (nominal & PT); batal = tidak ada aksi.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CashManagementView from "../purchasing/CashManagementView";
import ReconLinesTable from "../finance/bank/ReconLinesTable";
import { sourceLabel } from "../finance/glSourceLabels";

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
jest.mock("../../components/KNSelect", () => (p) => (
  <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
    <option value="">-</option>
    {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
  </select>
));
const mockAsk = jest.fn();
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: (...a) => mockAsk(...a),
  askReason: jest.fn(async () => null),
  askText: jest.fn(async () => null),
  askChoice: jest.fn(async () => null),
  REASON_MIN_LENGTH: 5,
  default: {},
}));
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
  return host;
}
async function click(el) { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); }
async function type(el, value) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new Event("input", { bubbles: true })); });
}

beforeEach(() => {
  mockGet.mockImplementation((url) => {
    if (url.endsWith("/cash-transactions/summary")) return Promise.resolve({ data: { kas_kecil: {}, kas_besar: {}, kas_kecil_per_entity: {} } });
    if (url.endsWith("/entities")) return Promise.resolve({ data: [{ id: "ent_ksc", short_name: "Sukacita" }] });
    if (url.endsWith("/bank-accounts")) {
      return Promise.resolve({ data: [{ id: "rek_k", name: "Kas Toko", entity_id: "ent_ksc", account_type: "cash", cash_type: "kas_kecil" }] });
    }
    return Promise.resolve({ data: [] });
  });
  mockPost.mockResolvedValue({ data: { applies: false } });
});
afterEach(() => { jest.useRealTimers(); mockGet.mockReset(); mockPost.mockReset(); document.body.innerHTML = ""; });

async function ketikNominal(perms) {
  jest.useFakeTimers();
  const host = await mount(<CashManagementView currentUser={{ role: "finance", permissions: perms }} selectedEntity="ent_ksc" />);
  await click(q(host, "create-cash-button"));
  await flush();
  await type(q(host, "cash-amount-input"), "330000");
  await act(async () => { jest.advanceTimersByTime(1000); });
  await flush();
  return mockPost.mock.calls.filter(([url]) => String(url).endsWith("/finance/budget-check"));
}

test("Finance tanpa izin lihat anggaran: kas keluar tidak meminta pratinjau anggaran (tidak ada 403)", async () => {
  expect(await ketikNominal({ cash: ["view", "create"] })).toHaveLength(0);
});

test("Pemegang budget.view: pratinjau anggaran kas keluar tetap diminta", async () => {
  const calls = await ketikNominal({ cash: ["view", "create"], budget: ["view"] });
  expect(calls).toHaveLength(1);
  expect(calls[0][1]).toMatchObject({ source: "cash_out", amount: 330000, entity_id: "ent_ksc" });
});

describe("F10 — ReconLinesTable: aksi baris yang menerbitkan jurnal berkonfirmasi", () => {
  const baris = [
    { id: "L1", status: "unmatched", direction: "out", amount: 15000, description: "BIAYA ADM LATIHAN 03",
      entity_id: "ent_ksc", stmt_date: "2026-11-18" },
    { id: "L2", status: "unmatched", direction: "in", amount: 2500000, description: "TRSF E-BANKING CR TANPA NAMA",
      entity_id: "ent_ksc", stmt_date: "2026-11-18" },
  ];
  async function pasang(jawab) {
    mockAsk.mockReset();
    mockAsk.mockResolvedValue(jawab);
    const onAction = jest.fn(async () => true);
    const host = await mount(<ReconLinesTable lines={baris} busy="" onAction={onAction} onOpenMatch={() => {}}
      onReload={() => {}} onError={() => {}} onNotify={() => {}} perms={{}} />);
    return { host, onAction };
  }

  test("Catat biaya bank: konfirmasi menyebut nominal; Ya → book-charge kind=charge", async () => {
    const { host, onAction } = await pasang(true);
    await click(q(host, "recon-charge-L1"));
    await flush();
    expect(mockAsk).toHaveBeenCalledTimes(1);
    const o = mockAsk.mock.calls[0][0];
    expect(o).toMatchObject({ title: "Catat biaya bank?", confirmLabel: "Catat biaya bank", testId: "recon-charge-confirm" });
    expect(JSON.stringify(o.message.props.children)).toContain("Rp 15.000");
    expect(onAction).toHaveBeenCalledWith("L1", "book-charge", { kind: "charge" }, expect.stringContaining("Biaya bank dibukukan"));
  });

  test("Batal → tidak ada aksi (biaya, bunga, titipkan)", async () => {
    const { host, onAction } = await pasang(false);
    for (const id of ["recon-charge-L1", "recon-interest-L2", "recon-holding-L2"]) await click(q(host, id));
    await flush();
    expect(mockAsk).toHaveBeenCalledTimes(3);
    expect(mockAsk.mock.calls.map((c) => c[0].testId)).toEqual(
      ["recon-charge-confirm", "recon-interest-confirm", "recon-holding-confirm"]);
    expect(onAction).not.toHaveBeenCalled();
  });

  test("Titipkan: Ya → aksi holding", async () => {
    const { host, onAction } = await pasang(true);
    await click(q(host, "recon-holding-L2"));
    await flush();
    expect(onAction).toHaveBeenCalledWith("L2", "holding", { note: "" }, expect.stringContaining("Dana dititipkan"));
  });
});

test("F08 — sumber jurnal titipan tunai sales berlabel Indonesia di Buku Besar (bukan 'Cash holding')", () => {
  expect(sourceLabel("cash_holding")).toBe("Titipan Tunai Sales");
  expect(sourceLabel("cash_holding_reversal")).toBe("Pembalik Titipan Tunai");
});
