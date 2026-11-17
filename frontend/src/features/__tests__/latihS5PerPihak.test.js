// Pelatihan keuangan 18 Nov 2026 — situasi S5 "Hutang & Piutang per Pihak" (uji jalan docs/pelatihan/2026-11-18_keuangan/
// uji/situasi/S5_per_pihak.js). Permintaan pemilik: hutang/piutang dikelompokkan per pemasok/pelanggan, diklik muncul
// semua hutang/piutangnya, dan bisa dibayar dari situ.
//  · Fitur baru (uji perilaku): Hutang per Pemasok — saring/urut/jumlah daftar, rincian pemasok (tagihan di kontrabon tidak
//    bisa dicentang/dibayar langsung), "Bayar beberapa tagihan": satu konfirmasi N5 (total, pemasok, rekening, PT) lalu
//    satu POST per tagihan ke pintu yang ada dengan kunci idempoten SENDIRI per tagihan; kirim ulang memakai kunci sama.
//  · Piutang per Pelanggan: tombol Rekening koran (izin baca rekening koran) dan Janji bayar (izin `order.update`).
//  · Perbaikan (gagal di kode lama): kartu pemasok — kontrabon "Dijadwalkan bayar" tidak punya tombol Bayar (status
//    ditulis "scheduled", padahal "scheduled_payment"); rekening koran › Cetak PDF — nama berkas ber-"·" (nama pelanggan)
//    ditolak peramban, berkas tersimpan sebagai "download" tanpa ".pdf".
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { AppNavProvider } from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";

const mockGet = jest.fn();
const mockPost = jest.fn();
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
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: jest.fn(), askReason: jest.fn(), askText: jest.fn(), askChoice: jest.fn(), default: {},
}));
jest.mock("../../components/AskKnButton", () => ({ __esModule: true, AskKnButton: () => null, PENDING_KEY: "x" }));
jest.mock("../../components/StoreCreditBadge", () => () => null);
jest.mock("../finance/payments/PenaltyPanel", () => () => <div data-testid="stub-penalty-panel" />);
jest.mock("../documents/RecordDetailModal", () => () => null);
jest.mock("../../components/KNSelect", () => {
  // eslint-disable-next-line global-require
  const React = require("react");
  const M = ({ value, onValueChange, options = [], "data-testid": tid }) => React.createElement("select",
    { "data-testid": tid, value: value || "", onChange: (e) => onValueChange && onValueChange(e.target.value) },
    [React.createElement("option", { key: "", value: "" }, "-"),
      ...options.map((o) => React.createElement("option", { key: o.value, value: o.value }, o.label))]);
  return { __esModule: true, default: M, KNSelect: M };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange?.(e.target.value)} />,
  formatDateId: (v) => String(v || ""),
}));

/* eslint-disable import/first */
import { askConfirm } from "../../services/confirmService";
import {
  bayarBanyakConfirmText, bayarBerurutan, cekBayarBanyak, filterSupplierRows, makeBatchKeys, sumSupplierRows,
} from "../finance/ap/apPartyApi";
import APSupplierDetail from "../finance/ap/APSupplierDetail";
import PayManyBillsModal from "../finance/ap/PayManyBillsModal";
import Supplier360Panel from "../purchasing/Supplier360Panel";
import ARAgingDetail from "../finance/ARAgingDetail";
import APBySupplierView from "../finance/ap/APBySupplierView";
import CustomerStatementTab from "../crm/CustomerStatementTab";
/* eslint-enable import/first */

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const nbsp = (s) => String(s || "").replace(/\u00a0/g, " ");
async function flush(n = 8) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
const ENT = [{ id: "ent_ksc", short_name: "Sukacita", legal_name: "PT Kain Suka Cita" }];
async function mount(el, selectedEntity = "ent_ksc") {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(<AppNavProvider role="finance"><EntityScopeProvider selectedEntity={selectedEntity} entities={ENT} canSwitch>{el}</EntityScopeProvider></AppNavProvider>);
  });
  await flush();
  return host;
}
async function click(el) { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await flush(); }
async function pick(el, value) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(el, value);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = []; document.body.innerHTML = "";
});

const FIN = { vendor_bill: ["view", "pay"], contra_bon: ["view", "pay"], supplier: ["view"], ar_receipt: ["view", "create"],
  credit_profile: ["view"], document: ["view", "print"], order: ["view"], penalty: ["view", "issue"] };
const USER = { id: "u9", role: "finance", permissions: FIN };
// Hitung tangan (angka peserta peraga 91): VB-18 sisa 1.864.800 + VB-19 sisa 1.287.600 = 3.152.400.
const B1 = { bill_id: "vb18", bill_number: "VB-00018", supplier_invoice_no: "INV-1", po_number: "PO-18", entity_id: "ent_ksc",
  due_date: "2026-12-17", days_past_due: -30, aging_bucket: "not_due", grand_total: 1864800, amount_paid: 0,
  outstanding: 1864800, contra_bon: null, payment_tolerance: 5000 };
const B2 = { ...B1, bill_id: "vb19", bill_number: "VB-00019", outstanding: 1287600, grand_total: 1287600, po_number: "PO-19" };
const B3 = { ...B1, bill_id: "vb20", bill_number: "VB-00020", outstanding: 500000, grand_total: 500000,
  contra_bon: { id: "cb1", number: "KB-0001", status: "approved", status_label: "Disetujui" } };

test("Daftar per pemasok: saringan, urutan, cari, dan jumlah kaki tabel", () => {
  const rows = [
    { supplier_name: "B Grey", entity_label: "Sukacita", outstanding: 300, overdue: 0, bill_count: 1, aging: { not_due: 300 }, held_count: 0, nearest_due: "2026-12-01" },
    { supplier_name: "A Celup", entity_label: "Sukacita", outstanding: 200, overdue: 200, bill_count: 2, aging: { "61-90": 200 }, held_count: 1, advance: 50, nearest_due: "2026-09-01" },
    { supplier_name: "C Benang", entity_label: "Kanda", outstanding: 900, overdue: 100, bill_count: 3, aging: { not_due: 800, "1-30": 100 }, held_count: 0, debit_notes: 10, nearest_due: "2026-11-20" },
  ];
  expect(filterSupplierRows(rows).map((r) => r.supplier_name)).toEqual(["A Celup", "C Benang", "B Grey"]);   // telat dulu
  expect(filterSupplierRows(rows, { urut: "sisa" }).map((r) => r.supplier_name)).toEqual(["C Benang", "B Grey", "A Celup"]);
  expect(filterSupplierRows(rows, { urut: "jatuh_tempo" })[0].supplier_name).toBe("A Celup");
  expect(filterSupplierRows(rows, { saring: "lewat" })).toHaveLength(2);
  expect(filterSupplierRows(rows, { saring: "lewat60" }).map((r) => r.supplier_name)).toEqual(["A Celup"]);
  expect(filterSupplierRows(rows, { saring: "kontrabon" }).map((r) => r.supplier_name)).toEqual(["A Celup"]);
  expect(filterSupplierRows(rows, { saring: "potongan" })).toHaveLength(2);
  expect(filterSupplierRows(rows, { q: "kanda" }).map((r) => r.supplier_name)).toEqual(["C Benang"]);
  const t = sumSupplierRows(rows);
  expect(t.outstanding).toBe(1400);
  expect(t.aging.not_due).toBe(1100);
  expect(t.potongan).toBe(60);
  expect(t.bill_count).toBe(6);
});

test("Cek form bayar banyak: nominal > sisa, tanpa rekening, Semua PT → tombol mati dengan alasan", () => {
  expect(cekBayarBanyak([B1, B2], { vb18: 1864800, vb19: 1287600 }, { accountId: "rek" })).toMatchObject({ blok: "", total: 3152400 });
  expect(cekBayarBanyak([B1], { vb18: 2000000 }, { accountId: "rek" }).blok).toMatch(/VB-00018: .*melebihi sisa hutang/);
  expect(cekBayarBanyak([B1], { vb18: 1864800 }, {}).blok).toMatch(/Pilih rekening/);
  expect(cekBayarBanyak([B1], { vb18: 1864800 }, { accountId: "rek", allPt: true }).blok).toMatch(/Pilih satu PT/);
  expect(cekBayarBanyak([], {}, { accountId: "rek" }).blok).toMatch(/Centang minimal satu/);
  // Kurang bayar dalam toleransi selisih → diberi tahu sebelum simpan (ditutup otomatis oleh pintu bayar).
  expect(cekBayarBanyak([B1], { vb18: 1862800 }, { accountId: "rek" }).items[0].info).toMatch(/ditutup|DITUTUP/i);
  const teks = nbsp(bayarBanyakConfirmText({ count: 2, total: 3152400, supplier: "Pemasok 91", account: "BCA Operasional KSC", pt: "Sukacita" }));
  expect(teks).toMatch(/Bayar 2 tagihan senilai Rp 3\.152\.400 ke Pemasok 91 dari BCA Operasional KSC untuk Sukacita\?/);
});

test("Bayar berurutan: satu kunci per tagihan; gagal satu tidak menghentikan yang lain; kirim ulang memakai kunci sama", async () => {
  const keys = makeBatchKeys("vbpay");
  const sent = [];
  let gagalSekali = true;
  const post = async (url, body, key) => {
    sent.push({ url, body, key });
    if (url.includes("vb19") && gagalSekali) { gagalSekali = false; throw new Error("jaringan putus"); }   // tanpa jawaban server
    return { data: { status: "paid", financials: { outstanding: 0 } } };
  };
  const items = cekBayarBanyak([B1, B2], { vb18: 1864800, vb19: 1287600 }, { accountId: "rek" }).items;
  const base = { method: "transfer", paidAt: "2026-11-17", accountId: "rek", notes: "" };
  const r1 = await bayarBerurutan({ items, base, keys, post, api: "/api" });
  expect(r1.map((r) => r.ok)).toEqual([true, false]);
  expect(sent.map((s) => s.url)).toEqual(["/api/vendor-bills/vb18/pay", "/api/vendor-bills/vb19/pay"]);
  expect(sent[0].key).not.toEqual(sent[1].key);
  expect(sent[0].body).toMatchObject({ amount: 1864800, method: "transfer", paid_at: "2026-11-17", bank_account_id: "rek" });
  // Ulangi yang gagal (isi sama) → kunci SAMA dengan percobaan pertama (server memutar ulang, tidak menggandakan kas).
  const r2 = await bayarBerurutan({ items: [items[1]], base, keys, post, api: "/api" });
  expect(r2[0].ok).toBe(true);
  expect(sent[2].key).toEqual(sent[1].key);
});

test("Rincian pemasok: tagihan di kontrabon tidak bisa dicentang/dibayar langsung; Bayar terpilih menyebut jumlah & total", async () => {
  let dipilih = null;
  const detail = { supplier: { id: "s91", name: "Pemasok 91", code: "SUP-1" }, entities: [{ entity_id: "ent_ksc", label: "Sukacita" }],
    bills: [B1, B2, B3], contra_bons: [{ id: "cb2", number: "KB-0002", status: "scheduled_payment", status_label: "Dijadwalkan bayar",
      bill_count: 1, net_payable: 700000, outstanding: 700000, payable: true },
    { id: "cb3", number: "KB-0003", status: "submitted", status_label: "Diajukan", bill_count: 1, net_payable: 1, outstanding: 1, payable: false }],
    credits: [], totals: { outstanding: 3652400, overdue: 0, payable_direct: 3152400, held: 500000, bill_count: 3 } };
  await mount(<APSupplierDetail detail={detail} currentUser={USER} allPt={false} ptName="Sukacita" onPayMany={(b) => { dipilih = b; }} onPayOne={() => {}} />);
  expect(q("ap-detail-check-vb20")).toBeNull();
  expect(q("ap-detail-pay-vb20")).toBeNull();
  expect(q("ap-detail-held-vb20").textContent).toMatch(/Bayar lewat kontrabon KB-0001/);
  expect(q("ap-detail-pay-many").disabled).toBe(true);
  expect(q("ap-detail-cb-pay-cb2")).not.toBeNull();
  expect(q("ap-detail-cb-pay-cb3")).toBeNull();
  await click(q("ap-detail-check-all"));
  expect(nbsp(q("ap-detail-pay-many").textContent)).toMatch(/Bayar terpilih \(2\) · Rp 3\.152\.400/);
  await click(q("ap-detail-pay-many"));
  expect(dipilih.map((b) => b.bill_id)).toEqual(["vb18", "vb19"]);
});

test("Rincian pemasok di Semua PT: tombol bayar mati + alasan tertulis", async () => {
  const detail = { supplier: { id: "s91", name: "Pemasok 91" }, entities: [], bills: [B1], contra_bons: [], credits: [],
    totals: { outstanding: 1864800 } };
  await mount(<APSupplierDetail detail={detail} currentUser={USER} allPt ptName="" onPayMany={() => {}} onPayOne={() => {}} />, "all");
  expect(q("ap-detail-pay-vb18").disabled).toBe(true);
  expect(q("ap-detail-pay-scope-note").textContent).toMatch(/Pilih satu PT/);
});

test("Form bayar beberapa tagihan: satu konfirmasi N5 lalu satu POST ber-kunci per tagihan; hasil per tagihan tampil", async () => {
  mockGet.mockImplementation((url) => {
    if (url.endsWith("/ap-payments/accounts")) return Promise.resolve({ data: [{ id: "rek1", name: "BCA Operasional KSC", bank_name: "BCA" }] });
    if (url.endsWith("/ap-payments/pending")) return Promise.resolve({ data: null });
    if (url.includes("payment-methods")) return Promise.resolve({ data: [] });
    return Promise.resolve({ data: {} });
  });
  mockPost.mockImplementation((url) => Promise.resolve({ data: { status: "paid", financials: { outstanding: 0 }, bill_number: url } }));
  askConfirm.mockImplementation(async () => true);
  const done = jest.fn();
  await mount(<PayManyBillsModal supplierName="Pemasok 91" entityId="ent_ksc" ptName="Sukacita" bills={[B1, B2]} onClose={() => {}} onDone={done} />);
  expect(q("pay-many-submit").disabled).toBe(true);
  expect(q("pay-many-reason").textContent).toMatch(/Pilih rekening/);
  await pick(q("pay-many-account"), "rek1");
  expect(nbsp(q("pay-many-total").textContent)).toBe("Rp 3.152.400");
  await click(q("pay-many-submit"));
  expect(askConfirm).toHaveBeenCalledTimes(1);
  expect(nbsp(askConfirm.mock.calls[0][0].message)).toMatch(/Bayar 2 tagihan senilai Rp 3\.152\.400 ke Pemasok 91 dari BCA Operasional KSC · BCA untuk Sukacita\?/);
  expect(mockPost).toHaveBeenCalledTimes(2);
  const [c1, c2] = mockPost.mock.calls;
  expect(c1[0]).toBe("/api/vendor-bills/vb18/pay");
  expect(c2[0]).toBe("/api/vendor-bills/vb19/pay");
  expect(c1[1]).toMatchObject({ amount: 1864800, bank_account_id: "rek1", method: "transfer" });
  expect(c2[1]).toMatchObject({ amount: 1287600, bank_account_id: "rek1" });
  expect(c1[2].headers["Idempotency-Key"]).toBeTruthy();
  expect(c1[2].headers["Idempotency-Key"]).not.toEqual(c2[2].headers["Idempotency-Key"]);
  expect(q("pay-many-result-vb18").textContent).toMatch(/Lunas/);
  expect(nbsp(q("pay-many-summary").textContent)).toMatch(/2 tagihan dibayar, total Rp 3\.152\.400/);
  expect(done).toHaveBeenCalledTimes(1);
  expect(q("pay-many-submit")).toBeNull();   // semua lunas → tinggal tombol Tutup
});

test("Kartu pemasok: kontrabon 'Dijadwalkan bayar' punya tombol Bayar (dulu status ditulis 'scheduled')", async () => {
  const sup = { id: "s1", name: "Pemasok S", entity_id: "ent_ksc", status: "active", sections_allowed: ["kontrabon"],
    bills: [], payments: [], documents: [], price_history: [], payables: null,
    contra_bons: [{ id: "cbx", number: "KB-9", status: "scheduled_payment", status_label: "Dijadwalkan bayar", bills: [],
      totals: { outstanding: 100, net_payable: 100 } }] };
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/suppliers/s1/360") ? sup : [] }));
  await mount(<Supplier360Panel variant="card" supplierId="s1" currentUser={USER} selectedEntity="ent_ksc" />);
  expect(q("supplier-360-pay-cbx")).not.toBeNull();
});

test("Piutang per pelanggan: Rekening koran (izin baca) dan Janji bayar (izin order.update) dari rincian", async () => {
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.includes("/statement")
    ? { from: "2026-11-01", to: "2026-11-17", rows: [], opening_balance: 0, closing_balance: 0, note: "", penalties: null,
      entity: { short_name: "Sukacita" } } : {} }));
  const detail = { customer_name: "Toko 91", totals: { total: 6907252.5 }, penalties: [], items: [
    { order_id: "so52", order_number: "KSC/SO-00052", outstanding: 3438502.5, grand_total: 3438502.5, paid_total: 0, lines: [], penalties: [] }] };
  const props = { detail, customerId: "c91", loading: false, selectedEntity: "ent_ksc", onPay: () => {}, onClose: () => {}, onRefresh: () => {} };
  await mount(<ARAgingDetail {...props} currentUser={USER} />);
  expect(q("ar-aging-promise-so52")).toBeNull();   // Finance hari ini tanpa order.update
  await click(q("ar-aging-statement"));
  expect(q("customer-statement-tab")).not.toBeNull();
  expect(mockGet.mock.calls.some(([u, c]) => u === "/api/customers/c91/statement" && c.params.entity_id === "ent_ksc")).toBe(true);
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = []; document.body.innerHTML = "";
  await mount(<ARAgingDetail {...props} currentUser={{ ...USER, permissions: { ...FIN, order: ["view", "update"] } }} />);
  await click(q("ar-aging-promise-so52"));
  expect(q("worklist-followup-modal")).not.toBeNull();
  const tanpa = { ar_receipt: ["create"], penalty: ["issue"] };
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = []; document.body.innerHTML = "";
  await mount(<ARAgingDetail {...props} currentUser={{ ...USER, permissions: tanpa }} />);
  expect(q("ar-aging-statement")).toBeNull();
});

test("Layar Hutang per Pemasok: satu baris per pemasok; kartu angka menyaring; klik baris membuka rincian pemasok itu", async () => {
  const LIST = { combined: false, aging_labels: [], totals: { outstanding: 3652400, overdue: 500000, aging: { "61-90": 0, ">90": 0 },
    supplier_count: 2, bill_count: 3, advance: 0, debit_notes: 0 },
  rows: [
    { supplier_id: "s91", supplier_name: "Pemasok 91", entity_id: "ent_ksc", entity_label: "Sukacita", bill_count: 2,
      outstanding: 3152400, overdue: 0, aging: { not_due: 3152400 }, nearest_due: "2026-12-17", held_count: 0 },
    { supplier_id: "s92", supplier_name: "Pemasok 92", entity_id: "ent_ksc", entity_label: "Sukacita", bill_count: 1,
      outstanding: 500000, overdue: 500000, aging: { "1-30": 500000 }, nearest_due: "2026-11-01", max_days_past_due: 16, held_count: 0 },
  ] };
  const DET = { supplier: { id: "s91", name: "Pemasok 91" }, entities: [], bills: [B1, B2], contra_bons: [], credits: [],
    totals: { outstanding: 3152400, payable_direct: 3152400, bill_count: 2 } };
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/by-supplier") ? LIST : url.endsWith("/by-supplier/s91") ? DET : {} }));
  await mount(<APBySupplierView currentUser={USER} selectedEntity="ent_ksc" />);
  expect(mockGet.mock.calls.some(([u, c]) => u === "/api/vendor-bills/payables/by-supplier" && c.params.entity_id === "ent_ksc")).toBe(true);
  expect(q("ap-party-row-s92")).not.toBeNull();
  expect(nbsp(q("ap-party-foot-total").textContent)).toBe("Rp 3.652.400");
  await click(q("ap-party-kpi-overdue"));                       // kartu "Lewat jatuh tempo" = saringan cepat
  expect(q("ap-party-row-s91")).toBeNull();
  expect(nbsp(q("ap-party-foot-total").textContent)).toBe("Rp 500.000");
  await click(q("ap-party-kpi-overdue"));
  await click(q("ap-party-row-s91"));
  expect(mockGet.mock.calls.some(([u]) => u === "/api/vendor-bills/payables/by-supplier/s91")).toBe(true);
  expect(q("ap-detail-bill-vb18")).not.toBeNull();
});

test("Rekening koran › Cetak PDF: nama berkas tanpa tanda '·' (dulu peramban menyimpannya sebagai 'download' tanpa .pdf)", async () => {
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/statement.pdf") ? new Blob(["%PDF-1.4"])
    : { from: "2026-11-01", to: "2026-11-18", rows: [], opening_balance: 0, closing_balance: 0, note: "", penalties: null } }));
  const asal = { create: URL.createObjectURL, revoke: URL.revokeObjectURL, click: HTMLAnchorElement.prototype.click };
  const nama = [];
  URL.createObjectURL = () => "blob:uji";
  URL.revokeObjectURL = () => {};
  HTMLAnchorElement.prototype.click = function klik() { nama.push(this.download); };
  try {
    await mount(<CustomerStatementTab customer={{ id: "c91", name: "Latihan 91 · Toko Kain Peserta 91" }} currentUser={USER}
      selectedEntity="ent_ksc" />);
    await click(q("customer-statement-pdf"));
  } finally {
    URL.createObjectURL = asal.create; URL.revokeObjectURL = asal.revoke; HTMLAnchorElement.prototype.click = asal.click;
  }
  expect(nama).toHaveLength(1);
  expect(nama[0]).toMatch(/^rekening-koran-latihan-91-toko-kain-peserta-91-\d{4}-\d{2}-\d{2}-\d{4}-\d{2}-\d{2}\.pdf$/);
});
