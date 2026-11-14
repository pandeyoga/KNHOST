// PK-26 (IV-01, K-05) — sisi layar rincian voucher biaya masuk tanpa peramban (U14 uji jalan tetap di lingkungan A):
//  · kolom "Perlakuan" (Persediaan · Di makloon · Sudah keluar) dari `treatment`; voucher lama tanpa `treatment` → "—";
//  · sesudah disetujui: baris ringkas dari `capitalization` (nilai 0 disembunyikan; label beban ikut `expensed_to`);
//  · sebelum disetujui: kalimat roll keluar hanya bila pratinjau memuat roll ber-`treatment` `keluar`.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { AppNavProvider } from "../../context/AppNavContext";
import { setAccessContext } from "../../config/roles";

jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: () => Promise.resolve({ data: [] }), post: () => Promise.resolve({ data: {} }),
    patch: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
// Pemilih bawaan (cmdk/radix) diganti <select> polos.
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});

// eslint-disable-next-line import/first
import LandedCostDetailPanel, { capitalizationRows, KALIMAT_KELUAR, PERLAKUAN } from "../purchasing/LandedCostDetailPanel";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function mount(voucher, props = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(<AppNavProvider role="admin"><LandedCostDetailPanel voucher={voucher} canApprove {...props} /></AppNavProvider>);
  });
  for (let i = 0; i < 3; i += 1) await act(async () => {});
  return host;
}

// U2: tiga roll, 300.000 → 100.000 per roll; persediaan · di makloon · sudah keluar.
const ALOKASI = [
  { roll_id: "r1", roll_no: "R-STOK", product_name: "Kain Uji", length: 100, alloc_amount: 100000, per_unit: 1000,
    new_unit_cost: 11000, treatment: "persediaan", capitalized_amount: 100000 },
  { roll_id: "r2", roll_no: "R-MITRA", product_name: "Kain Uji", length: 100, alloc_amount: 100000, per_unit: 1000,
    new_unit_cost: 11000, treatment: "wip", capitalized_amount: 100000 },
  { roll_id: "r3", roll_no: "R-JUAL", product_name: "Kain Uji", length: 100, alloc_amount: 100000, per_unit: 1000,
    new_unit_cost: 11000, treatment: "keluar", capitalized_amount: 0 },
];
const DISETUJUI = {
  id: "lcv_1", voucher_number: "LCV-00001", status: "applied", entity_id: "ent_ksc", basis: "value", total_cost: 300000,
  cost_lines: [{ category: "freight", description: "angkut", amount: 300000 }], allocations: ALOKASI,
  allocation_preview: ALOKASI, target_roll_count: 3, gl_status: "posted",
  capitalization: { inventory_amount: 100000, wip_amount: 100000, expensed_amount: 100000, expensed_to: "hpp" },
};

beforeEach(() => setAccessContext({ role: "admin" }));
afterEach(() => { document.body.innerHTML = ""; });

test("U14 — kolom Perlakuan tiga nilai + tiga baris ringkas Rp 100.000", async () => {
  const host = await mount(DISETUJUI);
  expect([0, 1, 2].map((i) => q(host, `lc-detail-alloc-${i}-treatment`).textContent))
    .toEqual(["Persediaan", "Di makloon", "Sudah keluar"]);
  expect(host.textContent).toContain("Perlakuan");
  const baris = ["inventory", "wip", "expensed"].map((k) => q(host, `lc-cap-${k}`).textContent);
  expect(baris[0]).toMatch(/^Menambah nilai persediaan.*100\.000$/);
  expect(baris[1]).toMatch(/^Menambah nilai barang di makloon.*100\.000$/);
  expect(baris[2]).toMatch(/^Dibebankan ke HPP.*100\.000$/);
  expect(q(host, "lc-keluar-note")).toBeNull();          // sudah disetujui → kalimat sebelum-setujui tidak tampil
  // ikon + teks (bukan warna saja)
  expect(q(host, "lc-detail-alloc-0-treatment").querySelector("svg")).not.toBeNull();
});

test("U14 — baris 0 disembunyikan; varians memakai label biaya masuk pembelian", async () => {
  const host = await mount({ ...DISETUJUI, capitalization: {
    inventory_amount: 1500000, wip_amount: 0, expensed_amount: 1500000, expensed_to: "varians" } });
  expect(q(host, "lc-cap-wip")).toBeNull();
  expect(q(host, "lc-cap-expensed").textContent).toMatch(/^Dicatat sebagai biaya masuk pembelian.*1\.500\.000$/);
  expect(capitalizationRows(null)).toEqual([]);
  expect(capitalizationRows({ inventory_amount: 0, wip_amount: 0, expensed_amount: 0 })).toEqual([]);
});

test("sebelum disetujui: kalimat roll keluar hanya bila pratinjau memuat roll keluar", async () => {
  const menunggu = { ...DISETUJUI, status: "pending_approval", allocations: [], capitalization: undefined };
  let host = await mount(menunggu);
  expect(q(host, "lc-keluar-note").textContent).toBe(KALIMAT_KELUAR);
  expect(q(host, "lc-capitalization")).toBeNull();
  // kalimat berada di atas tombol Setujui (bilah sendiri, sebelum baris tombol)
  const note = q(host, "lc-keluar-note");
  const tombol = q(host, "lc-action-approve");
  expect(note.compareDocumentPosition(tombol) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  document.body.innerHTML = "";
  host = await mount({ ...menunggu, allocation_preview: ALOKASI.slice(0, 2) });
  expect(q(host, "lc-keluar-note")).toBeNull();
});

test("voucher lama tanpa treatment/capitalization: kolom Perlakuan '—', tanpa ringkasan", async () => {
  const lama = { ...DISETUJUI, allocations: ALOKASI.map(({ treatment, capitalized_amount, ...a }) => a),
    capitalization: undefined };
  const host = await mount(lama);
  expect(q(host, "lc-detail-alloc-0-treatment").textContent).toBe("—");
  expect(q(host, "lc-capitalization")).toBeNull();
  expect(Object.keys(PERLAKUAN)).toEqual(["persediaan", "wip", "keluar"]);
});
