// PK-21 (SL-10) — rekonsiliasi bank satu mekanisme, sisi layar (uji U14 tanpa peramban):
// Rekening & Saldo menampilkan lencana BACA-SAJA (Terekonsiliasi / Sebagian {rupiah} / Belum) tanpa tombol pada kolom
// itu; pemegang `cash.create` mendapat tautan "Cocokkan di Rekonsiliasi Bank" yang membuka tab rekonsiliasi dengan
// rekening ini terpilih. Rekonsiliasi Bank: preset rekening diterapkan; lepas-cocok dijawab 409 → pesan tampil sebagai
// galat biasa dan daftar dimuat ulang.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import BankAccountsView from "../finance/BankAccountsView";
import BankReconciliationView from "../finance/BankReconciliationView";
import { AppNavProvider } from "../../context/AppNavContext";
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
// Pemilih bawaan (cmdk/radix) diganti <select> polos — yang diuji alur layar, bukan komponen pilihannya.
jest.mock("../../components/KNSelect", () => {
  const Pilih = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange(e.target.value)}>
      <option value="">-</option>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: Pilih, KNSelect: Pilih };
});
jest.mock("@/components/KNDatePicker", () => () => null);
const mockAskConfirm = jest.fn(async () => false);
jest.mock("../../services/confirmService", () => ({
  __esModule: true, askConfirm: (...a) => mockAskConfirm(...a), askReason: jest.fn(async () => "alasan uji"),
  askText: jest.fn(async () => null), askChoice: jest.fn(async () => null), default: {},
}));
jest.mock("@/components/MoneyInput", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function settle() { await act(async () => {}); await act(async () => {}); await act(async () => {}); }
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await settle();
  return { host, root };
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
}
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.endsWith(k));
    const v = hit ? map[hit] : [];
    return Promise.resolve({ data: typeof v === "function" ? v() : v });
  });
}

afterEach(() => { mockGet.mockReset(); mockPost.mockReset(); document.body.innerHTML = ""; });

// Lanjutan U4: K1 1.000.000 belum dicocokkan (0); K2 600.000 baru 400.000 (M2) → "Sebagian Rp 400.000";
// H5 750.000 kas titipan → penuh.
const R1 = { id: "ba_r1", name: "BCA PK21", account_type: "bank", bank_name: "BCA", balance: 2_350_000, inflow: 2_350_000,
  outflow: 0, txn_count: 3, unreconciled_count: 2, reconciled_balance: 750_000, is_active: true, entity_id: "ent_ksc" };
const LEDGER = { ...R1, transactions: [
  { id: "k1", number: "CASH-K1", amount: 1_000_000, direction: "in", reconciled: false, reconciled_amount: 0, running_balance: 1_000_000 },
  { id: "k2", number: "CASH-K2", amount: 600_000, direction: "in", reconciled: false, reconciled_amount: 400_000, running_balance: 1_600_000 },
  { id: "h5", number: "CASH-H5", amount: 750_000, direction: "in", reconciled: true, reconciled_amount: 750_000, running_balance: 2_350_000 },
] };

async function bukaBuku(perms, onNavigateTo = jest.fn()) {
  routeGet({ "/bank-accounts": [R1], "/bank-accounts/position": { gl_total: 2_350_000, unlinked: { count: 0, net: 0 } },
    "/bank-accounts/ba_r1/ledger": LEDGER });
  const { host } = await mount(
    <AppNavProvider role="admin" onNavigateTo={onNavigateTo}>
      <BankAccountsView selectedEntity="ent_ksc" currentUser={{ role: "admin", permissions: perms }} />
    </AppNavProvider>);
  await click(q(host, "bank-card-ba_r1"));
  return { host, onNavigateTo };
}

test("U14: lencana baca-saja Belum / Sebagian / Terekonsiliasi; kolom tanpa tombol; tanpa kiriman tanda manual", async () => {
  const { host } = await bukaBuku({ cash: ["view", "create"] });
  const k1 = q(host, "bank-recon-status-k1");
  const k2 = q(host, "bank-recon-status-k2");
  const h5 = q(host, "bank-recon-status-h5");
  expect(k1.textContent).toBe("Belum");
  expect(k2.textContent.replace(/\s+/g, " ")).toBe("Sebagian Rp 400.000");
  expect(h5.textContent).toContain("Terekonsiliasi");
  for (const id of ["k1", "k2", "h5"]) {
    const sel = q(host, `bank-ledger-row-${id}`).lastElementChild;
    expect(sel.querySelector("button")).toBeNull();
  }
  expect(host.querySelector('[data-testid^="bank-reconcile-"]')).toBeNull();
  await click(k1);
  expect(mockPost).not.toHaveBeenCalled();
});

test("U14: tautan Cocokkan di Rekonsiliasi Bank membuka tab rekonsiliasi untuk rekening ini", async () => {
  const { host, onNavigateTo } = await bukaBuku({ cash: ["view", "create"] });
  const link = q(host, "bank-ledger-match-link");
  expect(link.textContent).toContain("Cocokkan di Rekonsiliasi Bank");
  await click(link);
  expect(onNavigateTo).toHaveBeenCalledWith("bank-reconciliation",
    expect.objectContaining({ preset: { bank_account_id: "ba_r1" } }));
});

test("tautan hanya untuk pemegang cash.create", async () => {
  const { host } = await bukaBuku({ cash: ["view"] });
  expect(q(host, "bank-recon-status-k2")).not.toBeNull();
  expect(q(host, "bank-ledger-match-link")).toBeNull();
});

const SUMMARY = { statement: { net: 0, lines: 1 }, book: { net: 0 }, matched: 1, unmatched_lines: 0, suggested: 0,
  holding: { balance: 0, count: 0 }, difference: 0, unmatched_book_txns: 0 };

test("Rekonsiliasi Bank: preset rekening dipakai; lepas-cocok 409 → galat tampil dan daftar dimuat ulang", async () => {
  const ACC = [{ id: "ba_r0", name: "Rekening Lain" }, { id: "ba_r1", name: "BCA PK21" }];
  const LINE = { id: "m1", status: "matched", amount: 1_000_000, direction: "in", stmt_date: "2026-11-05",
    description: "TRF M1", matched_txns: [{ id: "k1", number: "CASH-K1", allocated: 1_000_000 }] };
  routeGet({ "/bank-accounts": ACC, "/bank-reconciliation/lines": [LINE], "/bank-reconciliation/summary": SUMMARY,
    "/bank-reconciliation/holding": { items: [], balance: 0, count: 0 }, "/bank-reconciliation/rules": [],
    "/bank-reconciliation/formats": [] });
  mockPost.mockRejectedValue({ response: { status: 409, data: {
    detail: "Mutasi bank ini baru saja dilepas atau diubah proses lain. Muat ulang." } } });
  const { host } = await mount(
    <ViewPresetProvider preset={{ view: "bank-reconciliation", nonce: 1, bank_account_id: "ba_r1" }}>
      <BankReconciliationView />
    </ViewPresetProvider>);
  const linesCalls = () => mockGet.mock.calls.filter(([u]) => u.endsWith("/bank-reconciliation/lines"));
  expect(linesCalls().length).toBeGreaterThan(0);
  expect(linesCalls().every(([, cfg]) => cfg.params.bank_account_id === "ba_r1")).toBe(true);
  const before = linesCalls().length;
  await click(q(host, "recon-unmatch-m1"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  expect(mockPost.mock.calls[0][0]).toBe("/api/bank-reconciliation/lines/m1/unmatch");
  expect(linesCalls().length).toBe(before + 1);
  expect(q(host, "recon-error").textContent).toContain("baru saja dilepas");
});

test("Rekonsiliasi Bank: galat 400 tidak memuat ulang (kendali)", async () => {
  routeGet({ "/bank-accounts": [{ id: "ba_r1", name: "BCA PK21" }],
    "/bank-reconciliation/lines": [{ id: "m1", status: "matched", amount: 10, direction: "in", stmt_date: "2026-11-05",
      description: "TRF", matched_txns: [] }],
    "/bank-reconciliation/summary": SUMMARY, "/bank-reconciliation/holding": { items: [], balance: 0, count: 0 },
    "/bank-reconciliation/rules": [], "/bank-reconciliation/formats": [] });
  mockPost.mockRejectedValue({ response: { status: 400, data: { detail: "Hanya baris berstatus TERCOCOK yang bisa dilepas." } } });
  const { host } = await mount(<BankReconciliationView />);
  const n = () => mockGet.mock.calls.filter(([u]) => u.endsWith("/bank-reconciliation/lines")).length;
  const before = n();
  await click(q(host, "recon-unmatch-m1"));
  expect(n()).toBe(before);
  expect(q(host, "recon-error").textContent).toContain("TERCOCOK");
});

test("M38 — mutasi data contoh (bukan unggahan): asal tertulis & Cocokkan otomatis minta konfirmasi dulu", async () => {
  const ACC = [{ id: "ba_r1", name: "BCA PK21" }];
  const S38 = { ...SUMMARY, matched: 0, unmatched_lines: 1,
    statement: { net: 1000, lines: 1, user_lines: 0, ever_user_import: false,
      sources: { berkas: 0, tempel: 0, contoh: 1, tidak_tercatat: 0 }, last_import: null } };
  routeGet({ "/bank-accounts": ACC, "/bank-reconciliation/lines": [], "/bank-reconciliation/summary": S38,
    "/bank-reconciliation/holding": { items: [], balance: 0, count: 0 }, "/bank-reconciliation/rules": [],
    "/bank-reconciliation/formats": [] });
  const { host } = await mount(
    <ViewPresetProvider preset={{ view: "bank-reconciliation", nonce: 1, bank_account_id: "ba_r1" }}>
      <BankReconciliationView />
    </ViewPresetProvider>);
  expect(q(host, "recon-statement-source-other").textContent).toContain("data contoh");
  await click(q(host, "recon-auto-match"));
  expect(mockAskConfirm).toHaveBeenCalledTimes(1);
  expect(mockPost).not.toHaveBeenCalled();   // dibatalkan → tidak mencocokkan diam-diam
});
