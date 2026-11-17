// Masukan pemilik 16 Nov 2026 (docs/blueprint/masukan-pemilik/2026-11-16_UI_MEJA_DAN_MENU.md) — perbaikan fungsi.
// M34 — "Buat Nota Denda" diklik tidak terjadi apa-apa: pesan hasil kini di DALAM pop-up rincian; tombol nonaktif +
// alasan tertulis bila tidak ada estimasi denda yang belum jadi nota.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import ARAgingDetail from "../finance/ARAgingDetail";
import ARAgingView from "../finance/ARAgingView";
import { SlipRow } from "../hr/PayrollRunsView";
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
jest.mock("../../services/confirmService", () => ({
  __esModule: true, askConfirm: jest.fn(async () => true), askReason: jest.fn(async () => "alasan uji"),
  askText: jest.fn(async () => null), askChoice: jest.fn(async () => null), default: {},
}));
// M3 — modul Tanya KN memakai pustaka markdown berformat ESM; di jsdom cukup diganti tiruan ringan.
jest.mock("../tanya/TanyaMarkdown", () => ({ __esModule: true, default: () => null, TanyaMarkdown: () => null }));
jest.mock("../tanya/TanyaAnswer", () => ({ TanyaAnswer: () => null }));
jest.mock("../tanya/TanyaThread", () => ({ TanyaThread: () => null }));
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
if (!window.matchMedia) {
  window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });
}

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
let mounted = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  mounted.push(root);
  await act(async () => { root.render(el); });
  await act(async () => {});
  await act(async () => {});
  return host;
}
afterEach(async () => {
  for (const r of mounted) await act(async () => { r.unmount(); });
  mounted = [];
  mockGet.mockReset(); mockPost.mockReset();
  document.body.innerHTML = "";
});

const FIN = { name: "Fin", role: "finance", permissions: { penalty: ["issue"], ar_receipt: ["create"] } };

describe("M34 — Buat Nota Denda", () => {
  test("tidak ada denda baru → tombol nonaktif + alasan tertulis", async () => {
    const host = await mount(<ARAgingDetail customerId="c1" loading={false} onClose={() => {}} onAccrue={() => {}}
      currentUser={FIN} detail={{ customer_name: "Toko A", totals: { total: 100, denda_undocumented: 0 }, items: [] }} />);
    expect(q(host, "ar-aging-accrue").disabled).toBe(true);
    expect(q(host, "ar-aging-accrue-reason").textContent).toContain("Tidak ada denda baru");
  });

  test("ada estimasi denda → tombol aktif, tanpa alasan", async () => {
    const host = await mount(<ARAgingDetail customerId="c1" loading={false} onClose={() => {}} onAccrue={() => {}}
      currentUser={FIN} detail={{ customer_name: "Toko A", totals: { total: 100, denda_undocumented: 5000 }, items: [] }} />);
    expect(q(host, "ar-aging-accrue").disabled).toBe(false);
    expect(q(host, "ar-aging-accrue-reason")).toBeNull();
  });

  test("hasil klik tampil di DALAM pop-up rincian (bukan di halaman di belakangnya)", async () => {
    const detail = { customer_name: "Toko A", totals: { total: 100, denda_undocumented: 5000 }, items: [] };
    mockGet.mockImplementation((url) => Promise.resolve({ data: url.includes("/ar/aging/c1") ? detail
      : { customers: [{ customer_id: "c1", customer_name: "Toko A", outstanding: 100, denda: 5000 }], totals: {} } }));
    mockPost.mockResolvedValue({ data: { count: 0, detail } });
    const host = await mount(<AppNavProvider><ViewPresetProvider>
      <ARAgingView currentUser={FIN} selectedEntity="ent_ksc" />
    </ViewPresetProvider></AppNavProvider>);
    const accrueRow = q(document.body, "ar-denda-accrue-c1");
    expect(accrueRow).not.toBeNull();
    await act(async () => { accrueRow.click(); });
    await act(async () => {});
    const modal = q(document.body, "ar-aging-detail-modal");
    expect(modal).not.toBeNull();
    const note = q(document.body, "ar-aging-accrue-notice");
    expect(note.textContent).toContain("Tidak ada denda yang layak");
    expect(modal.contains(note)).toBe(true);
    expect(q(host, "ar-aging-flash")).toBeNull();
  });
});

// M39 — rincian gaji sejajar kolom; PPh 21 nol → "—", ada pajak → "TER {kategori} {tarif}".
describe("M39 — baris slip gaji", () => {
  const slip = (over) => ({ id: "s1", employee_name: "Budi", gross: 5000000, bpjs_emp_total: 100000, other_deductions: 0,
    pph21: 0, pph21_rate: 0, net: 4900000, base_salary: 5000000, bpjs_emp: {}, bpjs_er_total: 0, ...over });
  const tabel = (s, open) => (<table><tbody><SlipRow s={s} open={open} onToggle={() => {}} /></tbody></table>);

  test("PPh 21 nol → '—' tanpa '0,00%'", async () => {
    const host = await mount(tabel(slip(), false));
    const cell = q(host, "payslip-pph-s1");
    expect(cell.textContent.trim()).toBe("—");
    expect(cell.textContent).not.toContain("%");
  });

  test("PPh 21 ada → nominal + 'TER A 1,50%'", async () => {
    const host = await mount(tabel(slip({ pph21: 75000, pph21_rate: 0.015, ter_category: "A" }), false));
    const cell = q(host, "payslip-pph-s1");
    expect(cell.textContent).toContain("75.000");
    expect(cell.textContent).toMatch(/TER A 1,5/);
  });

  test("rincian dibuka = tiga sel sejajar kolom (2 + 2 + 1)", async () => {
    const host = await mount(tabel(slip(), true));
    const cells = q(host, "payslip-detail-s1").querySelectorAll(":scope > td");
    expect(Array.from(cells).map((c) => c.colSpan)).toEqual([2, 2, 1]);
  });
});

// M21 — riwayat harga yang benar-benar dibeli pelanggan; M42 — Jejak Dokumen tanpa kata cari = dokumen terbaru.
describe("M21 + M42", () => {
  const CustomerPriceHistoryModal = jest.requireActual("../sales/customerPricelist/CustomerPriceHistoryModal").default;
  const TraceSearch = jest.requireActual("../documents/trace/TraceSearch").default;

  test("M21 — 'Pernah dibeli': pesanan, qty, harga, asal harga", async () => {
    mockGet.mockImplementation((url) => Promise.resolve({ data: url.includes("purchase-history")
      ? { items: [{ so_id: "s1", so_number: "SO-9", date: "2026-11-01", qty: 10, unit: "yard", price: 90000,
        normal_price: 100000, price_source_label: "Harga khusus" }] } : [] }));
    const host = await mount(<CustomerPriceHistoryModal row={{ product_id: "p1", product_name: "Rayon", sku: "R1",
      global_price: 100000, base_unit: "yard" }} customer={{ id: "c1", name: "Toko A" }} entityId="ent_ksc"
      canManage={false} onClose={() => {}} onChanged={() => {}} />);
    const row = q(host, "cpl-bought-row-0");
    expect(row.textContent).toContain("SO-9");
    expect(row.textContent).toContain("Harga khusus");
    expect(row.textContent).toContain("90.000");
  });

  test("M42 — tanpa kata cari tampil 'Dokumen terbaru'", async () => {
    jest.useFakeTimers();
    mockGet.mockResolvedValue({ data: [{ key: "k1", doc_id: "d1", number: "SO-1", label: "SO", title: "Toko A",
      date: "2026-11-16", ref_count: 2 }] });
    const host = await mount(<TraceSearch entityId="ent_ksc" onPick={() => {}} onError={() => {}} />);
    await act(async () => { jest.advanceTimersByTime(400); });
    await act(async () => {});
    jest.useRealTimers();
    expect(mockGet.mock.calls[0][1].params.q).toBe("");
    expect(q(host, "trace-recent-label")).not.toBeNull();
    expect(q(host, "trace-result-d1")).not.toBeNull();
  });
});

// M3 — Tanya KN layar penuh: panel laporan & riwayat bisa disembunyikan dan pilihan diingat.
describe("M3 — Tanya KN", () => {
  test("tombol sembunyikan panel menutup panel samping & mengingatnya", async () => {
    const TanyaKnView = jest.requireActual("../tanya/TanyaKnView").default;
    mockGet.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/ai/status")
      ? { chat_enabled: false, narrative_ai: false, budget: {} }
      : url.endsWith("/ai/templates") ? { groups: [], templates: [], period_presets: [] } : [] }));
    try { localStorage.removeItem("kn_tanya_side"); } catch { /* jsdom */ }
    const host = await mount(<TanyaKnView selectedEntity="ent_ksc" entities={[]} />);
    await act(async () => {});
    expect(q(host, "tanya-side")).not.toBeNull();
    await act(async () => { q(host, "tanya-side-toggle").click(); });
    expect(q(host, "tanya-side")).toBeNull();
    expect(localStorage.getItem("kn_tanya_side")).toBe("0");
  });
});
