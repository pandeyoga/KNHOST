// Fase 3 · P4 (L-03/L-07) — pop-up buatan sendiri → FormModal/DetailModal baku; daftar tetap tampil di belakang.
// Aset Tetap, Bagan Akun (Tambah Akun dulu inline), Pengajuan Dana & LPJ (dulu halaman penuh), Anggaran (dulu inline).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import FixedAssetsView from "../finance/FixedAssetsView";
import ChartOfAccounts from "../finance/ChartOfAccounts";
import BudgetView from "../finance/BudgetView";
import CashAdvancesView from "../pettycash/CashAdvancesView";
import SettlementsView from "../pettycash/SettlementsView";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), patch: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  await act(async () => {});
  return { host, root };
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await act(async () => {});
  await act(async () => {});
}
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.endsWith(k));
    return Promise.resolve({ data: hit ? map[hit] : [] });
  });
}
afterEach(() => { mockGet.mockReset(); document.body.innerHTML = ""; });

const ADMIN = { role: "admin", permissions: {
  cash_advance: ["*"], cash_settlement: ["*"], accounting: ["*"], budget: ["*"], audit: ["view"],
} };

test("Aset Tetap: Tambah Aset = FormModal (Simpan mati sampai wajib terisi), banner desktop di HP", async () => {
  routeGet({ "/fixed-assets": [], "/fixed-assets/summary": {}, "/fixed-assets/meta": { categories: ["Peralatan & Mesin"] } });
  const { host } = await mount(<FixedAssetsView selectedEntity="ent_ksc" entities={[]} />);
  expect(q(host, "fa-desktop-notice")).not.toBeNull();
  await click(q(host, "add-asset-btn"));
  const dlg = q(host, "add-asset-dialog");
  expect(dlg.getAttribute("role")).toBe("dialog");
  expect(q(host, "add-asset-dialog-overlay")).not.toBeNull();
  expect(q(host, "add-asset-submit-btn").disabled).toBe(true);
  expect(q(host, "asset-name-input")).not.toBeNull();
  expect(q(host, "fixed-assets-view")).not.toBeNull();          // daftar tetap di belakang
  await click(q(host, "add-asset-cancel-btn"));
  expect(q(host, "add-asset-dialog")).toBeNull();
});

test("Bagan Akun: Tambah Akun membuka pop-up (dulu form inline), isian lengkap, banner desktop", async () => {
  routeGet({ "/gl/accounts": [{ code: "1-1000", name: "Kas", type: "asset", is_postable: true, normal_balance: "debit" }] });
  const { host } = await mount(<ChartOfAccounts entities={[]} currentUser={ADMIN} />);
  expect(q(host, "coa-desktop-notice")).not.toBeNull();
  expect(q(host, "coa-add-form")).toBeNull();
  await click(q(host, "coa-add-toggle"));
  expect(q(host, "coa-add-form").getAttribute("role")).toBe("dialog");
  ["coa-form-code", "coa-form-name", "coa-form-type", "coa-form-parent", "coa-form-postable-true", "coa-form-postable-false"]
    .forEach((id) => expect(q(host, id)).not.toBeNull());
  expect(q(host, "coa-form-submit").disabled).toBe(true);       // kode & nama wajib
  await click(q(host, "coa-detail-1-1000"));
  expect(q(host, "coa-detail-modal").getAttribute("role")).toBe("dialog");
  expect(q(host, "coa-detail-tab-history")).not.toBeNull();     // izin audit.view
});

test("Anggaran: Tambah Anggaran = FormModal (dulu inline), banner desktop", async () => {
  routeGet({ "/finance/budget-vs-actual": { totals: {}, rows: [] }, "/finance/budget-rules": null,
    "/finance/budget-keys": { accounts: [{ code: "6-1000", name: "Beban" }], categories: [] } });
  const { host } = await mount(<BudgetView selectedEntity="ent_ksc" currentUser={ADMIN} />);
  expect(q(host, "budget-desktop-notice")).not.toBeNull();
  await click(q(host, "budget-add-toggle"));
  expect(q(host, "budget-form").getAttribute("role")).toBe("dialog");
  ["budget-form-key", "budget-form-month", "budget-form-amount", "budget-form-note"].forEach((id) => expect(q(host, id)).not.toBeNull());
  expect(q(host, "budget-form-submit").disabled).toBe(true);
  await click(q(host, "budget-form-cancel"));
  expect(q(host, "budget-form")).toBeNull();
});

const CA = { id: "ca1", number: "PD-0001", status: "draft", entity_id: "ent_ksc", lines: [], approvals: [],
  total_amount: 150000, kegiatan: "Pameran", divisi: "Marketing" };

test("Pengajuan Dana: form & rincian = pop-up, daftar tetap tampil (dulu halaman penuh)", async () => {
  routeGet({ "/cash-advances": [CA], "/cash-advances/ca1": CA });
  const { host } = await mount(<CashAdvancesView currentUser={ADMIN} selectedEntity="ent_ksc" entities={[{ id: "ent_ksc", short_name: "Sukacita" }]} />);
  await click(q(host, "ca-create-btn"));
  expect(q(host, "ca-form").getAttribute("role")).toBe("dialog");
  expect(q(host, "ca-form-title").textContent).toContain("Buat Pengajuan Dana");
  expect(q(host, "cash-advances-view")).not.toBeNull();
  expect(q(host, "ca-submit")).not.toBeNull();
  await click(q(host, "ca-form-close"));
  expect(q(host, "ca-form")).toBeNull();
  await click(q(host, "ca-open-ca1"));
  expect(q(host, "ca-detail-modal").getAttribute("role")).toBe("dialog");
  expect(q(host, "ca-detail-number").textContent).toBe("PD-0001");
  expect(q(host, "cash-advances-view")).not.toBeNull();
});

test("LPJ: daftar = tabel baku (ResponsiveTable), rincian & form = pop-up", async () => {
  const STL = { id: "s1", number: "LPJ-0001", status: "draft", entity_id: "ent_ksc", cash_advance_number: "PD-0001",
    total_pengeluaran: 90000, total_pettycash: 150000, sisa_kurang_dana: 60000,
    expense_lines: [{ date: "2026-10-20", description: "Parkir", category: "transport", amount: 90000 }] };
  routeGet({ "/cash-advance-settlements": [STL], "/cash-advance-settlements/s1": STL, "/expense-categories": [], "/cash-advances": [] });
  const { host } = await mount(<SettlementsView currentUser={ADMIN} selectedEntity="ent_ksc" entities={[]} />);
  expect(q(host, "stl-table")).not.toBeNull();
  expect(q(host, "stl-table").querySelector("table.data-table")).not.toBeNull();
  expect(q(host, "stl-row-s1")).not.toBeNull();
  await click(q(host, "stl-open-s1"));
  expect(q(host, "stl-detail-modal").getAttribute("role")).toBe("dialog");
  expect(q(host, "stl-detail-lines").className).toContain("data-table");
  expect(q(host, "stl-detail-sisa").textContent).toContain("60.000");
  await click(q(host, "stl-detail-modal-close-x"));
  await click(q(host, "stl-create-btn"));
  expect(q(host, "stl-form").getAttribute("role")).toBe("dialog");
  expect(q(host, "settlements-view")).not.toBeNull();
});
