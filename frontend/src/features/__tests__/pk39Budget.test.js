// PK-39 (FY-10/11/12, K-12) — layar Anggaran: mode gabungan (kolom PT + pita), Riwayat Pagu, ubah/hapus beralasan,
// panel Kebijakan hanya-baca + tautan Pusat Pengaturan bagi pemegang `budget.configure`, pratinjau & peringatan
// anggaran di form kas / LPJ. Uji komponen; uji jalan U17 (login Manajer, "Semua PT") dikerjakan integrator.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import BudgetView from "../finance/BudgetView";
import { historyChange } from "../finance/BudgetDialogs";
import { BudgetCheckNotice, BudgetPreview } from "../../components/BudgetCheckNotice";
import { CONFIG_EVENT } from "../settings/config/configDeepLink";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockPatch = jest.fn();
const mockDelete = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), delete: (...a) => mockDelete(...a),
    patch: (...a) => mockPatch(...a), put: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => <select data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />;
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("recharts", () => {
  const Box = () => <div />;
  return new Proxy({}, { get: () => Box });
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const ENTS = [
  { id: "ent_ksc", legal_name: "PT Kain Suka Cita", short_name: "Sukacita" },
  { id: "ent_kanda", legal_name: "CV Kanda Suka", short_name: "Kanda" },
];
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el, { selectedEntity = "all" } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(<EntityScopeProvider selectedEntity={selectedEntity} entities={ENTS}>{el}<ConfirmHost /></EntityScopeProvider>);
  });
  await flush();
  return host;
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
async function type(el, value) {
  const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new Event("input", { bubbles: true })); });
}
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.endsWith(k));
    return Promise.resolve({ data: hit ? map[hit] : [] });
  });
}

const ROW = (eid, name, actual) => ({
  id: `b_${eid}`, entity_id: eid, entity_name: name, dimension: "account", key: "6-2000", label: "Beban Sewa",
  month: 0, budget: 100, committed: 0, actual, spent: actual, remaining: 100 - actual, status: "ok",
  spent_pct: actual, used_pct: actual, commitment_docs: [],
  actual_docs: [{ ref: `JU-${eid}`, source_type: "manual", amount: actual, month: 3 }],
});
const RULES = { entity_id: "ent_ksc", mode: "block", mode_value: "blokir", mode_label: "Tolak bila melampaui",
  mode_source: "Khusus PT", warn_threshold_pct: 85, unbudgeted_action: "allow" };
const REPORT = {
  totals: { budget: 200, actual: 90 }, by_dimension: {}, alerts: [], unbudgeted_commitments: [],
  rows: [ROW("ent_ksc", "Sukacita", 80), ROW("ent_kanda", "Kanda", 10)],
  is_combined: true, combined_note: "Penjumlahan pagu dan realisasi tiap PT; transaksi antar-PT belum dieliminasi.",
};
const MANAJER = { role: "manager", permissions: { budget: ["view", "create", "update", "delete"] } };
const ADMIN = { role: "admin", permissions: { budget: ["*"] } };

beforeEach(() => {
  mockPost.mockResolvedValue({ data: {} });
  mockPatch.mockResolvedValue({ data: {} });
  mockDelete.mockResolvedValue({ data: {} });
});
afterEach(async () => {
  const openCancel = document.body.querySelector(".modal-overlay [data-testid$='-cancel']");
  if (openCancel) await click(openCancel);
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockReset(); mockPost.mockReset(); mockPatch.mockReset(); mockDelete.mockReset();
  document.body.innerHTML = "";
});

describe("PK-39 — layar Anggaran", () => {
  test("U17 — Semua PT: kolom PT + pita gabungan; Riwayat membuka pop-up; mode hanya-baca tanpa tautan", async () => {
    routeGet({
      "/finance/budget-vs-actual": REPORT, "/finance/budget-rules": RULES,
      "/finance/budget-keys": { accounts: [], categories: [], default_po_account: "1-1300" },
      "/finance/budgets/b_ent_kanda/history": [
        { id: "h2", action: "updated", before: { amount: 100, month: 0, year: 2026, note: "" },
          after: { amount: 150, month: 0, year: 2026, note: "" }, reason: "revisi triwulan", by: "Budi", at: "2026-11-14T03:00:00Z" },
        { id: "h1", action: "created", before: {}, after: { amount: 100, month: 0, year: 2026, note: "" }, reason: "",
          by: "Budi", at: "2026-11-13T03:00:00Z" }],
    });
    await mount(<BudgetView selectedEntity="all" currentUser={MANAJER} />);
    expect(q("budget-col-entity")?.textContent).toBe("PT");
    expect(q("budget-entity-ent_kanda-6-2000")?.textContent).toBe("Kanda");
    expect(q("budget-actual-ent_kanda-6-2000")?.textContent).toContain("10");
    expect(q("budget-combined-note")?.textContent).toContain("belum dieliminasi");
    expect(q("budget-col-committed").getAttribute("title")).toBe("Sisa PO yang belum diterima + LPJ yang belum disetujui");
    expect(q("budget-committed-hint")?.textContent).toContain("sisa PO yang belum diterima");
    expect(q("budget-adocs-ent_ksc-6-2000")?.textContent).toContain("JU-ent_ksc");
    // status = ikon + teks + warna
    const st = q("budget-status-ent_ksc-6-2000");
    expect(st.className).toContain("status-pill");
    expect(st.querySelector("svg")).not.toBeNull();
    // panel kebijakan: hanya-baca; Manajer tanpa budget.configure → tanpa tautan & tanpa tombol sakelar
    expect(q("budget-rules-mode").textContent).toContain("Tolak bila melampaui");
    expect(q("budget-rules-mode-source").textContent).toContain("Khusus PT");
    expect(q("budget-rules-open-config")).toBeNull();
    expect(q("budget-rules-mode-select")).toBeNull();
    // Riwayat
    await click(q("budget-history-ent_kanda-6-2000"));
    expect(q("budget-history")).not.toBeNull();
    const rows = document.body.querySelectorAll("[data-testid^='budget-history-row-']");
    expect(rows.length).toBe(2);
    expect(rows[0].textContent).toContain("revisi triwulan");
    expect(q("budget-history-row-updated").textContent).toMatch(/Nominal Rp\s?100 → Rp\s?150/);
    await click(q("budget-history-close"));
    expect(q("budget-history")).toBeNull();
    // puluhan baris (2× PT) → kotak cari menyaring kunci / nama / PT
    await type(q("budget-search"), "kanda");
    await flush();
    expect(q("budget-row-ent_kanda-6-2000")).not.toBeNull();
    expect(q("budget-row-ent_ksc-6-2000")).toBeNull();
    await type(q("budget-search"), "tidak-ada");
    await flush();
    expect(q("budget-search-empty")?.textContent).toContain("Tidak ada pagu yang cocok");
    expect(q("budget-table")).toBeNull();
  });

  test("Riwayat kosong → 'Belum ada perubahan.'", async () => {
    routeGet({ "/finance/budget-vs-actual": { ...REPORT, is_combined: false, rows: [ROW("ent_ksc", "Sukacita", 80)] },
      "/finance/budget-rules": RULES, "/finance/budget-keys": { accounts: [], categories: [] },
      "/finance/budgets/b_ent_ksc/history": [] });
    await mount(<BudgetView selectedEntity="ent_ksc" currentUser={MANAJER} />, { selectedEntity: "ent_ksc" });
    expect(q("budget-col-entity")).toBeNull();
    expect(q("budget-combined-note")).toBeNull();
    await click(q("budget-history-6-2000"));
    expect(q("budget-history-empty")?.textContent).toContain("Belum ada perubahan.");
  });

  test("Ubah pagu lewat pop-up dengan alasan; hapus mengirim alasan; pemegang configure melihat tautan", async () => {
    routeGet({ "/finance/budget-vs-actual": { ...REPORT, is_combined: false, rows: [ROW("ent_ksc", "Sukacita", 80)] },
      "/finance/budget-rules": RULES, "/finance/budget-keys": { accounts: [], categories: [] } });
    const heard = jest.fn();
    window.addEventListener(CONFIG_EVENT, heard);
    await mount(<BudgetView selectedEntity="ent_ksc" currentUser={ADMIN} />, { selectedEntity: "ent_ksc" });
    await click(q("budget-rules-open-config"));
    expect(heard).toHaveBeenCalledTimes(1);
    expect(heard.mock.calls[0][0].detail.key).toBe("budget.mode");
    window.removeEventListener(CONFIG_EVENT, heard);
    // ubah
    await click(q("budget-edit-6-2000"));
    expect(q("budget-edit-form")).not.toBeNull();
    await type(q("budget-edit-reason"), "revisi triwulan");
    await click(q("budget-edit-submit"));
    expect(mockPatch).toHaveBeenCalledTimes(1);
    expect(mockPatch.mock.calls[0][0]).toBe("/api/finance/budgets/b_ent_ksc");
    expect(mockPatch.mock.calls[0][1]).toEqual({ amount: 100, reason: "revisi triwulan" });
    // hapus: dialog beralasan (opsional)
    await click(q("budget-delete-6-2000"));
    expect(q("budget-delete-confirm")).not.toBeNull();
    const ta = q("budget-delete-confirm").querySelector("textarea");
    expect(ta).not.toBeNull();
    await type(ta, "salah akun");
    await click(q("budget-delete-confirm-confirm"));
    expect(mockDelete).toHaveBeenCalledTimes(1);
    expect(mockDelete.mock.calls[0][1]).toEqual({ params: { reason: "salah akun" } });
  });

  test("Simpan sakelar tidak mengirim mode", async () => {
    const mockPut = jest.fn().mockResolvedValue({ data: RULES });
    const api = require("../../services/apiClient").default;
    api.put = mockPut;
    routeGet({ "/finance/budget-vs-actual": { ...REPORT, is_combined: false, rows: [] },
      "/finance/budget-rules": RULES, "/finance/budget-keys": { accounts: [], categories: [] } });
    await mount(<BudgetView selectedEntity="ent_ksc" currentUser={ADMIN} />, { selectedEntity: "ent_ksc" });
    await click(q("budget-rules-toggle"));
    await click(q("budget-rules-save"));
    expect(mockPut).toHaveBeenCalledTimes(1);
    expect(mockPut.mock.calls[0][1]).not.toHaveProperty("mode");
  });
});

describe("PK-39 — peringatan anggaran di form", () => {
  test("BudgetCheckNotice: hanya tampil bila ada peringatan; ikon + teks", async () => {
    await mount(<>
      <BudgetCheckNotice check={{ mode: "warn", mode_label: "Peringatkan", warnings: ["Melampaui anggaran Beban Sewa"] }} testId="a" />
      <BudgetCheckNotice check={{ mode: "off", skipped: true, warnings: [] }} testId="b" />
    </>);
    expect(q("a").textContent).toContain("Melampaui anggaran Beban Sewa");
    expect(q("a").querySelector("svg")).not.toBeNull();
    expect(q("b")).toBeNull();
  });

  test("BudgetPreview kas keluar: meminta pratinjau ke server dan menulis sisa sesudah transaksi", async () => {
    jest.useFakeTimers();
    mockPost.mockResolvedValue({ data: { applies: true, mode: "block", blocked: true, over: true, has_budget: true,
      label: "Beban Sewa", key: "6-2000", budget: 1000000, actual: 900000, committed: 0, available: 100000,
      available_after: -100000, warning: "Melampaui" } });
    await mount(<BudgetPreview entityId="ent_ksc" source="cash_out" category="sewa" amount={200000} testId="pv" />);
    await act(async () => { jest.advanceTimersByTime(500); });
    jest.useRealTimers();
    await flush();
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe("/api/finance/budget-check");
    expect(mockPost.mock.calls[0][1]).toMatchObject({ entity_id: "ent_ksc", source: "cash_out", category: "sewa", amount: 200000 });
    expect(q("pv-title").textContent).toBe("Akan ditolak: melampaui anggaran");
    expect(q("pv").className).toContain("danger");
  });

  test("historyChange: kalimat buat / ubah / hapus", () => {
    expect(historyChange({ action: "created", after: { amount: 100, month: 8, year: 2026 } })).toMatch(/^Dibuat · Rp\s?100 · Agustus 2026$/);
    expect(historyChange({ action: "deleted", before: { amount: 150, month: 0, year: 2026 } })).toMatch(/^Dihapus · Rp\s?150 · Tahunan 2026$/);
    expect(historyChange({ action: "updated", before: { amount: 1, month: 1, year: 2026, note: "" },
      after: { amount: 1, month: 2, year: 2026, note: "x" } })).toBe("Periode Januari 2026 → Februari 2026 · Catatan diubah");
  });
});
