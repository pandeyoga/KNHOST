// TX-T2 — layar Faktur Keluaran: status Draf/Diganti + sakelar jenis dokumen, kolom Sumber (bisa dibuka), Terbitkan
// draf (pop-up tanggal/kode/NSFP, konfirmasi menyebut PT & PPN, kunci idempotensi), Buang draf (alasan wajib), lencana
// data pajak membuka kartu pelanggan, panel Pencocokan PPN keluaran (satu PT; "Semua PT" hanya petunjuk), dan tautan
// "Lihat draf faktur" di detail pesanan. Uji komponen (uji jalan peramban: integrator, U18).
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockGet = jest.fn();
const mockPost = jest.fn(() => Promise.resolve({ data: {} }));
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    put: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../documents/DocumentActionsBar", () => () => null);
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange?.(e.target.value)} />,
}));
jest.mock("../../components/KNMonthPicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange?.(e.target.value)} />,
  formatPeriodId: (v) => v,
}));

// eslint-disable-next-line import/first
import TaxInvoices from "../finance/TaxInvoices";
// eslint-disable-next-line import/first
import TaxOutputRecon from "../finance/TaxOutputRecon";
// eslint-disable-next-line import/first
import { EntityScopeProvider } from "../../context/EntityScopeContext";
// eslint-disable-next-line import/first
import { AppNavProvider } from "../../context/AppNavContext";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(el); });
  await flush();
  return host;
}
async function click(el) { await act(async () => { el.click(); }); await flush(); }
// Pola UI 16 Nov — saringan chip kini dropdown (FilterSelect); pilih nilai seperti pengguna memilih opsi.
async function pilih(el, v) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(el, v);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}

async function ketik(el, v) {
  await act(async () => {
    const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
    set.call(el, v);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await flush();
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  document.body.innerHTML = "";
  mockGet.mockReset();
  mockPost.mockClear();
});

const ENTITIES = [{ id: "ent_ksc", name: "PT Kain Suka Cita", legal_name: "PT Kain Suka Cita" }];
const DRAF = {
  id: "d1", number: "FKT-9", status: "draf", doc_kind: "faktur", trigger: "surat_jalan", order_id: "so1",
  order_number: "SO-1", shipment_no: "SJ-1", entity_id: "ent_ksc", kode_transaksi: "04", customer_id: "cus1",
  customer_name: "Toko Uji", ppn_rate: 12, ppn_amount: 440_000, grand_total: 4_440_000, dpp: 3_666_666.67,
  net_subtotal: 4_000_000, dpp_nilai_lain: true, faktur_date: "2026-11-14", data_incomplete: ["identitas_pajak"],
  customer_tax: { id_type: "", id_number: "" },
};
const DIGANTI = { ...DRAF, id: "f0", number: "FKT-8", status: "diganti", replaced_by_id: "f2", data_incomplete: [] };
const RETUR = { ...DRAF, id: "r1", number: "FKT-10", status: "draf", doc_kind: "retur", trigger: "retur", shipment_no: "SJ-1",
  credit_note_number: "CN-1", ref_tax_invoice_number: "FKT-7", ppn_amount: 110_000, data_incomplete: [] };
const RECON = {
  entity_id: "ent_ksc", period: "2026-11", faktur_ppn: 440_000, retur_ppn: 0, gl_ppn: 1_150_000, difference: 710_000,
  unexplained: 50_000, accounts: ["2-1200"],
  causes: { surat_jalan_tanpa_faktur: [{ jenis: "surat_jalan", order_id: "so1", order_number: "SO-1", shipment_no: "SJ-2",
    gl_ppn: 660_000, doc_ppn: 0, amount: 660_000, effect: 660_000 }], faktur_tanpa_jurnal: [], retur_tanpa_dokumen: [] },
  unexplained_journals: [{ id: "je9", number: "JE-9", amount: 50_000, description: "PPN manual" }],
};
function routeGet(map) {
  mockGet.mockImplementation((url, cfg) => {
    const key = Object.keys(map).find((k) => url.endsWith(k));
    const v = key ? map[key] : [];
    return Promise.resolve({ data: typeof v === "function" ? v(cfg) : v });
  });
}
const PERMS = { tax_invoice: ["view", "create", "update", "replace", "cancel"] };
function wrap(el, { selectedEntity = "ent_ksc", onOpen = () => {} } = {}) {
  return (
    <AppNavProvider role="admin" onOpenDocument={onOpen}>
      <EntityScopeProvider selectedEntity={selectedEntity} entities={ENTITIES} canSwitch>{el}</EntityScopeProvider>
    </AppNavProvider>
  );
}

test("Draf: status ikon+teks, kolom Sumber, saringan Draf/Diganti, sakelar jenis, aksi draf saja", async () => {
  routeGet({ "/tax-invoices": [DRAF, DIGANTI, RETUR], "/tax/output-reconciliation": RECON,
    "/settings/effective": { tax: { kode_transaksi_diizinkan: ["01", "04"] } } });
  const buka = jest.fn();
  await mount(wrap(<TaxInvoices currentUser={{ role: "admin", permissions: PERMS }} />, { onOpen: buka }));
  // Cek layar integrator (1024 px): 8 kolom = 1069 px > kartu ±730 px → 5 kolom; NSFP di bawah nomor, DPP · PPN · total
  // satu kolom berlabel.
  expect([...q("fkt-table").querySelectorAll("thead th")].map((t) => t.textContent)).toEqual([
    "No. Faktur · Status · NSFP", "Sumber", "Pembeli", "DPP · PPN · Total", "Aksi"]);
  expect(q("fkt-nsfp-text-d1").textContent).toMatch(/NSFP\s*belum diisi/);
  expect(q("fkt-ppn-d1").textContent).toMatch(/^PPN\s/);
  expect(q("fkt-total-d1").textContent).toMatch(/^Total\s/);
  expect(q("fkt-row-d1").querySelector(".status-pill").textContent).toBe("Draf");
  expect(q("fkt-row-d1").querySelector(".status-pill svg")).not.toBeNull();
  expect(q("fkt-row-f0").querySelector(".status-pill").textContent).toBe("Diganti");
  expect(q("fkt-row-r1")).toBeNull();                                  // sakelar jenis: bawaan Faktur
  expect(q("fkt-row-d1").textContent).toMatch(/Surat jalan SJ-1/);
  expect(q("fkt-issue-d1")).not.toBeNull();
  expect(q("fkt-discard-d1")).not.toBeNull();
  expect(q("fkt-nsfp-d1")).toBeNull();                                 // draf: NSFP diisi saat terbit
  expect(q("fkt-cancel-d1")).toBeNull();
  expect(q("fkt-replace-f0")).toBeNull();                              // diganti: tidak bisa diganti lagi
  await click(q("fkt-source-d1"));
  expect(buka).toHaveBeenCalledWith(expect.objectContaining({ focus_type: "sales_order", focus_id: "so1" }));
  await click(q("fkt-incomplete-d1"));
  expect(buka).toHaveBeenCalledWith(expect.objectContaining({ focus_type: "customer", focus_id: "cus1" }));
  await pilih(q("fkt-kind"), "retur");
  expect(q("fkt-row-r1").textContent).toMatch(/Nota CN-1/);
  expect(q("fkt-row-r1").textContent).toMatch(/atas FKT-7/);
  expect(q("fkt-replace-r1")).toBeNull();
  await pilih(q("fkt-kind"), "faktur");
  await pilih(q("fkt-filter"), "diganti");
  expect(q("fkt-row-d1")).toBeNull();
  expect(q("fkt-row-f0")).not.toBeNull();
  await pilih(q("fkt-filter"), "draf");
  expect(q("fkt-row-d1")).not.toBeNull();
});

test("Terbitkan draf: pop-up tanggal/kode/NSFP, konfirmasi menyebut PT & PPN, kunci idempotensi", async () => {
  routeGet({ "/tax-invoices": [DRAF], "/settings/effective": { tax: { kode_transaksi_diizinkan: ["01", "04"] } } });
  await mount(wrap(<TaxInvoices currentUser={{ role: "admin", permissions: PERMS }} />));
  await click(q("fkt-issue-d1"));
  expect(q("fkt-issue-date").value).toBe("2026-11-14");
  expect([...q("fkt-kode-select").querySelectorAll("option")].map((o) => o.value)).toEqual(["01", "04"]);
  expect(q("fkt-issue-confirm").textContent).toMatch(/PT Kain Suka Cita/);
  expect(q("fkt-issue-confirm").textContent).toMatch(/Rp 440\.000/);
  expect(q("fkt-modal-submit").textContent).toBe("Terbitkan");
  await ketik(q("fkt-issue-nsfp"), "0100002612345678");
  await click(q("fkt-modal-submit"));
  const [url, body, cfg] = mockPost.mock.calls.find(([u]) => u.endsWith("/issue"));
  expect(url).toBe("/api/tax-invoices/d1/issue");
  expect(body).toEqual({ faktur_date: "2026-11-14", kode_transaksi: "04", nsfp: "0100002612345678" });
  expect(cfg.headers["Idempotency-Key"]).toBeTruthy();
});

test("Buang draf: alasan wajib (tanpa alasan tidak dikirim)", async () => {
  routeGet({ "/tax-invoices": [DRAF] });
  await mount(wrap(<TaxInvoices currentUser={{ role: "admin", permissions: PERMS }} />));
  await click(q("fkt-discard-d1"));
  await click(q("fkt-modal-submit"));
  expect(q("fkt-modal-error").textContent).toMatch(/Alasan membuang draf wajib diisi/);
  expect(mockPost.mock.calls.some(([u]) => u.endsWith("/discard"))).toBe(false);
  await ketik(q("fkt-reason-input"), "pelanggan minta digabung");
  await click(q("fkt-modal-submit"));
  const [url, body] = mockPost.mock.calls.find(([u]) => u.endsWith("/discard"));
  expect([url, body]).toEqual(["/api/tax-invoices/d1/discard", { reason: "pelanggan minta digabung" }]);
});

test("Tanpa izin terbit/batal: tombol draf tidak tampil; daftar draf kosong punya kalimat sendiri", async () => {
  routeGet({ "/tax-invoices": [DIGANTI] });
  await mount(wrap(<TaxInvoices currentUser={{ role: "viewer", permissions: { tax_invoice: ["view"] } }} />));
  expect(q("fkt-issue-f0")).toBeNull();
  await pilih(q("fkt-filter"), "draf");
  expect(q("fkt-table").textContent).toMatch(/Tidak ada draf faktur\./);
});

test("Pencocokan PPN keluaran: empat angka, sebab, belum terjelaskan berwarna peringatan; Semua PT = petunjuk", async () => {
  routeGet({ "/tax/output-reconciliation": RECON });
  await mount(wrap(<TaxOutputRecon canRebuild />));
  const angka = q("fkt-recon-angka").textContent;
  ["PPN di faktur", "PPN di dokumen retur", "PPN di buku besar", "Selisih"].forEach((l) => expect(angka).toMatch(l));
  expect(q("fkt-recon-surat_jalan_tanpa_faktur").textContent).toMatch(/SO-1 · SJ-2/);
  expect(q("fkt-recon-belum").className).toMatch(/bg-kn-warning-soft/);
  expect(q("fkt-recon-belum").textContent).toMatch(/JE-9/);
  const call = mockGet.mock.calls.find(([u]) => u.endsWith("/tax/output-reconciliation"));
  expect(call[1].params.entity_id).toBe("ent_ksc");
  await click(q("fkt-recon-rebuild"));
  expect(mockPost.mock.calls.some(([u]) => u.endsWith("/tax-invoices/drafts/rebuild"))).toBe(true);
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockClear();
  await mount(wrap(<TaxOutputRecon canRebuild />, { selectedEntity: "all" }));
  expect(q("fkt-recon-pilih-pt")).not.toBeNull();
  expect(q("fkt-recon-rebuild")).toBeNull();
  expect(mockGet.mock.calls.some(([u]) => u.endsWith("/tax/output-reconciliation"))).toBe(false);
});

test("Pencocokan cocok: belum terjelaskan 0 netral, kalimat cocok", async () => {
  routeGet({ "/tax/output-reconciliation": { ...RECON, gl_ppn: 440_000, difference: 0, unexplained: 0,
    unexplained_journals: [], causes: { surat_jalan_tanpa_faktur: [], faktur_tanpa_jurnal: [], retur_tanpa_dokumen: [] } } });
  await mount(wrap(<TaxOutputRecon />));
  expect(q("fkt-recon-cocok")).not.toBeNull();
  expect(q("fkt-recon-belum").className).toMatch(/bg-kn-neutral-soft/);
  expect(q("fkt-recon-rebuild")).toBeNull();
});

test("Pencocokan: kotak cari menyaring baris sebab", async () => {
  const banyak = { ...RECON, causes: { ...RECON.causes, surat_jalan_tanpa_faktur: [
    ...RECON.causes.surat_jalan_tanpa_faktur,
    { jenis: "pesanan", order_id: "so2", order_number: "SO-77", gl_ppn: 10, doc_ppn: 0, amount: 10, effect: 10 }] } };
  routeGet({ "/tax/output-reconciliation": banyak });
  await mount(wrap(<TaxOutputRecon />));
  expect(q("fkt-recon-surat_jalan_tanpa_faktur").textContent).toMatch(/\(2\)/);
  await ketik(q("fkt-recon-search"), "SO-77");
  const teks = q("fkt-recon-surat_jalan_tanpa_faktur").textContent;
  expect(teks).toMatch(/1 dari 2/);
  expect(teks).toMatch(/SO-77/);
  expect(teks).not.toMatch(/SJ-2/);
});
