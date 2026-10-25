// Fase 3 · P1 (L-04/L-07) — ResponsiveTable: satu definisi kolom → `.data-table` di layar lebar, kartu di HP.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ResponsiveTable from "../ResponsiveTable";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let host; let root;
async function mount(el) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(el); });
}
afterEach(async () => { await act(async () => { root.unmount(); }); host.remove(); delete window.matchMedia; });
const q = (id) => host.querySelector(`[data-testid="${id}"]`);
const click = (el) => act(async () => { el.click(); });

/** Emulasi viewport: `(max-width: Npx)` cocok bila lebar ≤ N. */
function viewport(width) {
  window.matchMedia = (query) => {
    const m = /max-width:\s*(\d+)px/.exec(query);
    return { matches: m ? width <= Number(m[1]) : false, media: query,
      addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} };
  };
}

const ROWS = [
  { id: "r1", number: "RFQ-001", status: "Draf", supplier: "PT Benang", total: 1500000, created: "1 Okt", note: "", extra: "x" },
  { id: "r2", number: "RFQ-002", status: "Terkirim", supplier: "CV Kain", total: 0, created: "2 Okt", note: null, extra: "y" },
];
const COLS = [
  { key: "number", header: "Nomor", render: (r) => <b>{r.number}</b> },
  { key: "status", header: "Status", mobile: "badge" },
  { key: "supplier", header: "Pemasok", mobile: "subtitle" },
  { key: "total", header: "Total", align: "right", priority: 1, render: (r) => `Rp ${r.total}` },
  { key: "created", header: "Dibuat", priority: 3 },
  { key: "note", header: "Catatan", priority: 2 },
  { key: "extra", header: "Lain", priority: 4 },
  { key: "secret", header: "Internal", mobile: "hidden", value: () => "rahasia" },
];

test("layar lebar: tabel .data-table, testid baris, klik baris membuka; klik aksi TIDAK ikut membuka", async () => {
  viewport(1440);
  const opened = []; const acted = [];
  await mount(<ResponsiveTable testId="rfq" columns={COLS} rows={ROWS} onRowClick={(r) => opened.push(r.id)}
    actions={(r) => <button type="button" data-testid={`act-${r.id}`} onClick={() => acted.push(r.id)}>Ubah</button>}
    footer={<div data-testid="pager">pager</div>} />);
  expect(q("rfq").className).toMatch(/rt-mode-table/);
  const table = host.querySelector("table.data-table");
  expect(table).not.toBeNull();
  expect([...table.querySelectorAll("thead th")].map((th) => th.textContent)).toEqual(
    ["Nomor", "Status", "Pemasok", "Total", "Dibuat", "Catatan", "Lain", "Internal", "Aksi"]);
  expect(q("rfq-row-r1").querySelectorAll("td")[3].className).toMatch(/text-right/);
  expect(q("rfq-row-r1").querySelectorAll("td")[5].textContent).toBe("—");   // "" → tanda kosong
  expect(q("rfq-row-r2").querySelectorAll("td")[5].textContent).toBe("—");   // null → tanda kosong
  expect(q("rfq-row-r2").querySelectorAll("td")[7].textContent).toBe("rahasia");
  await click(q("rfq-row-r2"));
  await click(q("act-r1"));
  expect(opened).toEqual(["r2"]);
  expect(acted).toEqual(["r1"]);
  // Pager di LUAR wadah gulir (P-05).
  expect(host.querySelector(".table-container").contains(q("pager"))).toBe(false);
});

test("HP (≤640 px): kartu — judul, lencana, sub-judul, isian prioritas, '+N lainnya', aksi di kaki kartu", async () => {
  viewport(390);
  const opened = []; const acted = [];
  await mount(<ResponsiveTable testId="rfq" columns={COLS} rows={ROWS} cardFields={2} onRowClick={(r) => opened.push(r.id)}
    actions={(r) => <button type="button" data-testid={`act-${r.id}`} onClick={() => acted.push(r.id)}>Ubah</button>} />);
  expect(q("rfq").className).toMatch(/rt-mode-cards/);
  expect(host.querySelector("table")).toBeNull();
  const card = q("rfq-row-r1");
  expect(card.className).toMatch(/rt-card/);
  expect(card.querySelector(".rt-card-title").textContent).toBe("RFQ-001");
  expect(card.querySelector(".rt-card-badges").textContent).toBe("Draf");
  expect(card.querySelector(".rt-card-sub").textContent).toBe("PT Benang");
  const labels = () => [...card.querySelectorAll(".rt-card-field dt")].map((d) => d.textContent);
  expect(labels()).toEqual(["Total", "Catatan"]);             // prioritas 1, 2 lebih dulu; kolom tersembunyi tidak ada
  expect(q("rfq-row-r1-more").textContent).toBe("+2 lainnya");
  await click(q("rfq-row-r1-more"));
  expect(labels()).toEqual(["Total", "Catatan", "Dibuat", "Lain"]);   // tidak ada kolom yang hilang
  expect(opened).toEqual([]);                                  // tombol "lainnya" tidak membuka rincian
  expect(card.querySelector(".rt-card-actions").contains(q("act-r1"))).toBe(true);
  await click(q("act-r1"));
  expect(opened).toEqual([]);
  await click(card);
  expect(opened).toEqual(["r1"]);
  expect(acted).toEqual(["r1"]);
  expect(card.textContent).not.toMatch(/rahasia/);
});

test("kosong & memuat: pesan di luar tabel; mode paksa mengabaikan lebar layar", async () => {
  viewport(1440);
  await mount(<ResponsiveTable testId="t" columns={COLS} rows={[]} empty="Belum ada RFQ." mode="cards" />);
  expect(q("t-empty").textContent).toBe("Belum ada RFQ.");
  expect(host.querySelector("table")).toBeNull();
  await act(async () => { root.render(<ResponsiveTable testId="t" columns={COLS} rows={[]} loading />); });
  expect(q("t-loading")).not.toBeNull();
  await act(async () => { root.render(<ResponsiveTable testId="t" columns={COLS} rows={ROWS} mode="cards" />); });
  expect(host.querySelectorAll(".rt-card").length).toBe(2);
  expect(host.querySelector(".rt-card[role='button']")).toBeNull();   // tanpa onRowClick: bukan tombol
});
