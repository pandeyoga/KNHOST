// Uji peran kustom 18 Nov 2026 (agen A, perburuan cacat) — peran kustom "lihat saja" semua modul keuangan.
//
// Langkah ulang di layar: peran kustom TANPA peran dasar, modul Uang Masuk/Piutang, Hutang, Kas-Bank-Kasus, Akuntansi,
// Kas Kecil = "Lihat saja" → tombol berikut tampil lalu ditolak 403 di server:
//  · Tutup Buku › [Tutup Buku] (POST /finance/closing/close = `accounting.manage`);
//  · Kas & Bank › Rekonsiliasi › [Impor mutasi bank], [Cocokkan otomatis], [Lepas], [Cocokkan], [Abaikan], [Titipkan],
//    biaya/bunga bank (= `cash.create`);
//  · Piutang › Kasus › [Pindai temuan], [Kasus baru] (= `finance_case.create`); tambahan: `/customers` 403 (tanpa modul
//    Pelanggan) mengosongkan playbook, alasan, dan kebijakan sekaligus (bilah merah).
// Server sudah benar (403); layar kini mengikuti izin. Tanpa data izin (uji lama) layar tetap seperti dulu.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ClosingView from "../finance/ClosingView";
import BankReconciliationView from "../finance/BankReconciliationView";
import FinanceCasesView from "../finance/cases/FinanceCasesView";
import { ViewPresetProvider } from "../../context/ViewPresetContext";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../components/KNSelect", () => {
  const Pilih = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange?.(e.target.value)}>
      <option value="">-</option>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: Pilih, KNSelect: Pilih };
});
jest.mock("@/components/KNDatePicker", () => () => null);
jest.mock("@/components/MoneyInput", () => () => null);
jest.mock("../../components/PeriodUnlockCard", () => () => null);
jest.mock("../../components/OpeningCostBanner", () => () => null);
jest.mock("../../components/AskKnButton", () => ({ __esModule: true, AskKnButton: () => null, default: () => null, PENDING_KEY: "x" }));
jest.mock("../../services/confirmService", () => ({
  __esModule: true, askConfirm: jest.fn(async () => false), askReason: jest.fn(async () => null),
  askText: jest.fn(async () => null), askChoice: jest.fn(async () => null), default: {},
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function settle() { for (let i = 0; i < 6; i += 1) await act(async () => {}); }
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await settle();
  return { host, root };
}
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.endsWith(k));
    return Promise.resolve({ data: hit ? map[hit] : [] });
  });
}
beforeEach(() => { mockPost.mockImplementation(() => Promise.resolve({ data: {} })); });
afterEach(() => { mockGet.mockReset(); mockPost.mockReset(); document.body.innerHTML = ""; });

const ENTS = [{ id: "ent_ksc", short_name: "Sukacita" }];
const LIHAT = { role: "cr_uji_lihat", permissions: { accounting: ["view"], cash: ["view"], finance_case: ["view"] } };

describe("Tutup Buku", () => {
  test("lihat saja (accounting.view): tombol Tutup Buku tidak tampil, keterangan akses tampil", async () => {
    routeGet({ "/finance/closing": [] });
    const { host } = await mount(<ClosingView selectedEntity="ent_ksc" entities={ENTS} currentUser={LIHAT} />);
    expect(q(host, "closing-close-btn")).toBeNull();
    expect(q(host, "closing-close-noaccess")).not.toBeNull();
    expect(q(host, "closing-preview-btn")).not.toBeNull();   // pratinjau = baca (accounting.view)
  });
  test("pemegang accounting.manage: tombol Tutup Buku tampil", async () => {
    routeGet({ "/finance/closing": [] });
    const kelola = { role: "cr_uji_kelola", permissions: { accounting: ["view", "manage"] } };
    const { host } = await mount(<ClosingView selectedEntity="ent_ksc" entities={ENTS} currentUser={kelola} />);
    expect(q(host, "closing-close-btn")).not.toBeNull();
    expect(q(host, "closing-close-noaccess")).toBeNull();
  });
});

describe("Rekonsiliasi bank", () => {
  const SUMMARY = { statement: { net: 0, lines: 3, user_lines: 3, ever_user_import: true, sources: { berkas: 3 } },
    book: { net: 0 }, matched: 1, unmatched_lines: 2, suggested: 1, holding: { balance: 0, count: 0 }, difference: 0,
    unmatched_book_txns: 0 };
  const LINES = [
    { id: "m1", status: "matched", amount: 10, direction: "in", stmt_date: "2026-11-05", description: "A", matched_txns: [] },
    { id: "u1", status: "unmatched", amount: 20, direction: "in", stmt_date: "2026-11-05", description: "B",
      suggestions: [{ id: "k9", number: "CASH-9", amount: 20, score: 90 }] },
    { id: "u2", status: "unmatched", amount: 30, direction: "out", stmt_date: "2026-11-05", description: "C" },
  ];
  const buka = async (user) => {
    routeGet({ "/bank-accounts": [{ id: "ba_r1", name: "BCA Uji" }], "/bank-reconciliation/lines": LINES,
      "/bank-reconciliation/summary": SUMMARY, "/bank-reconciliation/holding": { items: [], balance: 0, count: 0 },
      "/bank-reconciliation/rules": [], "/bank-reconciliation/formats": [] });
    return mount(
      <ViewPresetProvider preset={{ view: "bank-reconciliation", nonce: 1, bank_account_id: "ba_r1" }}>
        <BankReconciliationView user={user} />
      </ViewPresetProvider>);
  };
  const AKSI = ["recon-import-toggle", "recon-auto-match", "recon-unmatch-m1", "recon-matchbtn-u1", "recon-holding-u1",
    "recon-ignore-u1", "recon-interest-u1", "recon-charge-u2", "recon-pick-u1", "recon-accept-u1-k9"];

  test("lihat saja (cash.view): tidak ada tombol yang menulis (semuanya cash.create di server)", async () => {
    const { host } = await buka(LIHAT);
    expect(q(host, "recon-line-u1")).not.toBeNull();   // daftar tetap terbaca
    expect(AKSI.filter((id) => q(host, id))).toEqual([]);
  });
  test("pemegang cash.create: semua tombol tetap ada", async () => {
    const { host } = await buka({ role: "cr_uji_kas", permissions: { cash: ["view", "create"] } });
    expect(AKSI.filter((id) => !q(host, id))).toEqual([]);
  });
});

describe("Kasus Keuangan", () => {
  const STATS = { open: 0, total: 0, by_status: {}, by_type: [] };
  const route = () => routeGet({ "/finance-cases": [], "/finance-cases/stats": STATS,
    "/finance-cases/playbooks": [{ code: "double_payment", label: "Bayar ganda" }], "/finance-cases/reasons": [],
    "/finance-cases/policy": { approval_above: 0 } });

  test("lihat saja (finance_case.view, tanpa Pelanggan/Kas/Pemasok): tanpa Kasus baru & Pindai, tanpa panggilan 403", async () => {
    route();
    const { host } = await mount(<FinanceCasesView currentUser={LIHAT} selectedEntity="ent_ksc" entities={ENTS} />);
    expect(q(host, "case-new")).toBeNull();
    expect(q(host, "case-scan")).toBeNull();
    const urls = mockGet.mock.calls.map(([u]) => u);
    expect(urls.filter((u) => /\/(customers|suppliers)$/.test(u))).toEqual([]);
    expect(urls.some((u) => u.endsWith("/finance-cases/playbooks"))).toBe(true);
  });
  test("/customers ditolak 403 tidak lagi mengosongkan playbook/kebijakan (tanpa bilah merah)", async () => {
    route();
    const base = mockGet.getMockImplementation();
    mockGet.mockImplementation((url) => (url.endsWith("/customers")
      ? Promise.reject({ response: { status: 403, data: { detail: "Anda belum punya akses untuk melihat Pelanggan." } } })
      : base(url)));
    const pemegang = { role: "cr_uji_kasus", permissions: { finance_case: ["view", "create"], customer: ["view"] } };
    const { host } = await mount(<FinanceCasesView currentUser={pemegang} selectedEntity="ent_ksc" entities={ENTS} />);
    expect(host.textContent).not.toContain("belum punya akses untuk melihat Pelanggan");
    expect(q(host, "case-new")).not.toBeNull();
    expect(q(host, "case-scan")).not.toBeNull();
  });
});
