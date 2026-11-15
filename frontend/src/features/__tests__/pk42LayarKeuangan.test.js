// PK-42 — layar keuangan per berkas (docs/blueprint/unit/PK-42.md), uji komponen:
// U1–U3 tombol buat mati di "Semua PT" (alasan tertulis di samping, bukan hanya tooltip) · U4–U5 galat di dalam pop-up ·
// U6 (tidak berlaku sejak PK-21: tombol tanda rekonsiliasi sudah dihapus) · U7 pita periode tertutup jujur · U8 isian
// rupiah · U12 riwayat kwitansi berhalaman · daftar kas berhalaman + lencana tab dari server · tanggal WIB seragam.
import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";
import EntityGatedButton, { EntityGateNote } from "../../components/EntityGatedButton";
import GeneralLedger from "../finance/GeneralLedger";
import CashManagementView from "../purchasing/CashManagementView";
import VendorBillPayments from "../purchasing/VendorBillPayments";
import { WorklistFollowup } from "../crm/CollectionWorklist";
import ARReceiptsHistory from "../crm/ARReceiptsHistory";
import BankAccountsView from "../finance/BankAccountsView";
import JournalEntryModal from "../finance/JournalEntryModal";
import { AppNavProvider } from "../../context/AppNavContext";
import { formatDate, formatDateTime } from "../../utils/formatters";
import { fmtDate as crmFmtDate } from "../crm/crmUtils";
import { fmtDate as cbFmtDate, fmtDateTime as cbFmtDateTime } from "../purchasing/contrabon/contraBonApi";
import { fmtDate as icFmtDate } from "../finance/interco/intercoApi";
import { fmtDate as pcFmtDate } from "../pettycash/pettyCashShared";
import { fmtDate as faFmtDate } from "../finance/FixedAssetsParts";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a),
    patch: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
const mockAskReason = jest.fn();
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: jest.fn(async () => true),
  askReason: (...a) => mockAskReason(...a),
  askText: jest.fn(async () => null),
  askChoice: jest.fn(async () => null),
  default: {},
}));
jest.mock("@/services/confirmService", () => ({
  __esModule: true,
  askConfirm: jest.fn(async () => true),
  askReason: (...a) => mockAskReason(...a),
  askText: jest.fn(async () => null),
  askChoice: jest.fn(async () => null),
  default: {},
}));
// Pemilih bawaan (cmdk/radix) & kalender (radix popover) diganti isian polos — yang diuji alur layar, bukan pemilihnya.
jest.mock("../../components/KNSelect", () => {
  const Pilih = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      <option value="">-</option>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: Pilih, KNSelect: Pilih };
});
jest.mock("../../components/KNDatePicker", () => (p) => (
  <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange && p.onChange(e.target.value)} />
));
jest.mock("@/components/KNDatePicker", () => (p) => (
  <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange && p.onChange(e.target.value)} />
));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const norm = (s) => String(s || "").replace(/\s+/g, " ").trim();
async function flush() { for (let i = 0; i < 4; i += 1) { await act(async () => {}); } }   // eslint-disable-line no-await-in-loop
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await flush();
  return { host, root };
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
async function type(el, value) {
  const proto = el.tagName === "SELECT" ? HTMLSelectElement.prototype
    : el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
  await act(async () => {
    setter.call(el, value);
    el.dispatchEvent(new Event(el.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
  });
  await flush();
}
function routeGet(map) {
  mockGet.mockImplementation((url, cfg) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.endsWith(k));
    const v = hit ? map[hit] : [];
    return Promise.resolve({ data: typeof v === "function" ? v(cfg) : v });
  });
}
afterEach(() => { mockGet.mockReset(); mockPost.mockReset(); mockAskReason.mockClear(); document.body.innerHTML = ""; });

const ADMIN = { role: "admin", permissions: { cash: ["*"], accounting: ["*"], ar_receipt: ["*"], vendor_bill: ["*"],
  audit: ["view"] } };

// ── U1–U2 — komponen EntityGatedButton ─────────────────────────────────────────────────────────────────────────────
describe("U1–U2 — EntityGatedButton", () => {
  test("U1: Semua PT → mati, alasan di title DAN tertulis di samping tombol; klik tidak memanggil onClick", async () => {
    const onClick = jest.fn();
    const { host } = await mount(
      <EntityGatedButton selectedEntity="all" what="membuat jurnal" data-testid="b" className="primary-button" onClick={onClick}>
        Jurnal Baru
      </EntityGatedButton>);
    const b = q(host, "b");
    expect(b.disabled).toBe(true);
    expect(b.getAttribute("aria-disabled")).toBe("true");
    expect(b.getAttribute("title")).toBe("Pilih satu PT dulu (kanan atas) untuk membuat jurnal.");
    expect(b.textContent).toBe("Jurnal Baru");                               // label tombol tidak berubah
    expect(q(host, "b-scope-hint").textContent).toBe("Pilih satu PT dulu");  // KN_37: bukan hanya tooltip
    expect(b.getAttribute("aria-describedby")).toBe("b-scope-hint");
    await click(b);
    expect(onClick).not.toHaveBeenCalled();
  });

  test("U2: satu PT → aktif, onClick sekali, tanpa petunjuk", async () => {
    const onClick = jest.fn();
    const { host } = await mount(
      <EntityGatedButton selectedEntity="ent_ksc" what="membuat jurnal" data-testid="b" onClick={onClick}>Jurnal Baru</EntityGatedButton>);
    const b = q(host, "b");
    expect(b.disabled).toBe(false);
    expect(b.getAttribute("title")).toBeNull();
    expect(q(host, "b-scope-hint")).toBeNull();
    await click(b);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  test("kepala kartu padat: hint={false} + EntityGateNote = alasan di bilah sendiri (hanya di Semua PT)", async () => {
    const { host } = await mount(<div>
      <EntityGateNote selectedEntity="all" what="membuat jurnal" testId="n" />
      <EntityGatedButton selectedEntity="all" what="membuat jurnal" hint={false} aria-describedby="n" data-testid="b">X</EntityGatedButton>
    </div>);
    expect(q(host, "b").disabled).toBe(true);
    expect(q(host, "b-scope-hint")).toBeNull();
    expect(q(host, "b").getAttribute("aria-describedby")).toBe("n");
    expect(q(host, "n").textContent).toBe("Pilih satu PT dulu (kanan atas) untuk membuat jurnal.");
    const satu = await mount(<EntityGateNote selectedEntity="ent_ksc" what="membuat jurnal" testId="n2" />);
    expect(q(satu.host, "n2")).toBeNull();
  });
});

// ── U3 — layar uang di mode Semua PT ───────────────────────────────────────────────────────────────────────────────
describe("U3 — tombol buat di layar uang", () => {
  test.each([["all", true], ["ent_ksc", false]])("Jurnal & Buku Besar + Transaksi Kas, PT %s → mati %s", async (ent, mati) => {
    routeGet({ "/cash-transactions/summary": { kas_kecil: {}, kas_besar: {}, kas_kecil_per_entity: {} } });
    const gl = await mount(<GeneralLedger selectedEntity={ent} entities={[]} />);
    expect(q(gl.host, "gl-new-journal").disabled).toBe(mati);
    // Kepala kartu Jurnal padat (5 tab + 3 tombol) → alasan di bilah sendiri, bukan di samping tombol.
    expect(!!q(gl.host, "gl-new-journal-scope-note")).toBe(mati);
    if (mati) expect(q(gl.host, "gl-new-journal-scope-note").textContent).toBe("Pilih satu PT dulu (kanan atas) untuk membuat jurnal.");
    expect(q(gl.host, "gl-new-journal-scope-hint")).toBeNull();
    const cash = await mount(<CashManagementView currentUser={ADMIN} selectedEntity={ent} />);
    expect(q(cash.host, "create-cash-button").disabled).toBe(mati);
    if (mati) expect(q(cash.host, "create-cash-button").getAttribute("title")).toBe("Pilih satu PT dulu (kanan atas) untuk mencatat transaksi kas.");
  });

  // Tabel UX-05 (dikurangi baris antar-PT yang rutenya memang tingkat grup — lihat laporan): tiap tombol lewat
  // EntityGatedButton dengan `what` dari spesifikasi.
  const SRC = path.resolve(__dirname, "..");
  test.each([
    ["finance/GeneralLedger.jsx", "gl-new-journal", "membuat jurnal"],
    ["purchasing/CashManagementView.jsx", "create-cash-button", "mencatat transaksi kas"],
    ["purchasing/VendorBillsView.jsx", "create-vendor-bill-button", "membuat tagihan pemasok"],
    ["purchasing/contrabon/ContraBonsView.jsx", "cb-new", "membuat kontrabon"],
    ["purchasing/LandedCostView.jsx", "create-landed-cost-button", "mencatat biaya masuk"],
    ["purchasing/InputTaxView.jsx", "it-create-button", "mencatat faktur pajak masukan"],
    ["finance/FixedAssetsView.jsx", "add-asset-btn", "menambah aset tetap"],
    ["finance/BudgetView.jsx", "budget-add-toggle", "menambah anggaran"],
    ["finance/BankAccountsView.jsx", "bank-add-toggle", "menambah rekening"],
    // MN-T2 — Kas Kecil satu daftar (PettyCashView): "Ajukan dana" tetap bergerbang PT; LPJ dibuat dari panel PD
    // dicairkan (PT = PT pengajuan dananya), jadi tombol "LPJ Baru" di daftar LPJ lama tidak ada lagi.
    ["pettycash/PettyCashView.jsx", "pc-create-btn", "mengajukan dana"],
  ])("%s · %s lewat EntityGatedButton", (file, testId, what) => {
    const src = fs.readFileSync(path.join(SRC, file), "utf8");
    const tag = new RegExp(`<EntityGatedButton\\s[^>]*selectedEntity=\\{selectedEntity\\}[^>]*what="${what}"[^>]*data-testid="${testId}"`, "s");
    expect(src).toMatch(tag);
    expect(src).not.toMatch(new RegExp(`<button[^>]*data-testid="${testId}"`));
  });
});

// ── U4 — galat batal-bayar di dalam rincian tagihan ────────────────────────────────────────────────────────────────
test("U4: VendorBillPayments — galat batal-bayar tampil di vb-payments-error (dan onError tetap dipanggil)", async () => {
  mockAskReason.mockResolvedValue("salah input nominal");   // CRA: resetMocks → isi tiruan dipasang per uji
  mockPost.mockRejectedValue({ response: { status: 409, data: { detail: "Periode sudah ditutup" } } });
  const onError = jest.fn();
  const bill = { id: "vb1", payments: [{ id: "p1", amount: 500000, method: "transfer", cash_txn_number: "KSC/CASH-0001" }] };
  const { host } = await mount(<VendorBillPayments bill={bill} canVoid onAction={jest.fn()} onError={onError} />);
  await click(q(host, "vb-payment-void-p1"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  expect(mockPost.mock.calls[0][0]).toBe("/api/vendor-bills/vb1/payments/p1/void");
  expect(q(host, "vb-payments-error").textContent).toContain("Periode sudah ditutup");
  expect(q(host, "vb-payments").contains(q(host, "vb-payments-error"))).toBe(true);
  expect(onError).toHaveBeenCalledWith("Periode sudah ditutup");
  expect(mockAskReason.mock.calls[0][0].message).not.toMatch(/di-void/);
});

// ── U5 — tindak lanjut penagihan: pop-up baku, galat di dalamnya ───────────────────────────────────────────────────
describe("U5 — WorklistFollowup", () => {
  const ROW = { customer_id: "c1", customer_name: "Toko Melati", order_id: "so1", order_number: "KSC/SO-0001",
    outstanding: 1250000, overdue: true, days_late: 3 };
  test("simpan tanpa catatan → 'Catatan wajib diisi.' di DALAM worklist-followup-modal; tidak ada kiriman", async () => {
    const { host } = await mount(<WorklistFollowup row={ROW} onClose={jest.fn()} onDone={jest.fn()} />);
    const modal = q(host, "worklist-followup-modal");
    expect(modal.getAttribute("role")).toBe("dialog");
    expect(q(host, "worklist-followup-modal-title").textContent).toBe("Tindak Lanjut Penagihan — Toko Melati");
    expect(q(host, "worklist-followup-submit").textContent).toContain("Simpan");
    await click(q(host, "worklist-followup-submit"));
    expect(modal.textContent).toContain("Catatan wajib diisi.");
    expect(mockPost).not.toHaveBeenCalled();
  });
  test("server menolak → pesan server di dalam pop-up; cadangan 'Gagal menyimpan tindak lanjut.'", async () => {
    mockPost.mockRejectedValueOnce({ response: { status: 400, data: { detail: "Pelanggan diarsipkan" } } });
    mockPost.mockRejectedValueOnce({});                       // galat tanpa kalimat apa pun → teks cadangan
    const onDone = jest.fn();
    const { host } = await mount(<WorklistFollowup row={ROW} onClose={jest.fn()} onDone={onDone} />);
    await type(q(host, "worklist-followup-note"), "Janji transfer Jumat");
    await click(q(host, "worklist-followup-submit"));
    expect(q(host, "worklist-followup-modal").textContent).toContain("Pelanggan diarsipkan");
    await click(q(host, "worklist-followup-submit"));
    expect(q(host, "worklist-followup-modal").textContent).toContain("Gagal menyimpan tindak lanjut.");
    expect(onDone).not.toHaveBeenCalled();
  });
});

// ── U6 — tidak berlaku: tombol tanda rekonsiliasi optimistis sudah dicabut PK-21 ───────────────────────────────────
test("U6 (tidak berlaku sejak PK-21): mutasi rekening hanya lencana baca-saja, tidak ada tombol/kiriman tanda", async () => {
  const R1 = { id: "ba1", name: "BCA", account_type: "bank", balance: 0, inflow: 0, outflow: 0, txn_count: 1, entity_id: "ent_ksc" };
  routeGet({ "/bank-accounts": [R1], "/bank-accounts/position": null, "/bank-accounts/ba1/ledger": { ...R1,
    transactions: [{ id: "k1", number: "CASH-K1", amount: 1000, direction: "in", reconciled: false, reconciled_amount: 0 }] } });
  const { host } = await mount(<BankAccountsView selectedEntity="ent_ksc" currentUser={ADMIN} />);
  await click(q(host, "bank-card-ba1"));
  expect(q(host, "bank-recon-status-k1").textContent).toBe("Belum");
  expect(host.querySelector('[data-testid^="bank-reconcile-"]')).toBeNull();
  expect(mockPost).not.toHaveBeenCalled();
});

// ── U7–U8 — jurnal manual ──────────────────────────────────────────────────────────────────────────────────────────
const ACCOUNTS = [
  { code: "1-1100", name: "Kas", is_postable: true, is_active: true },
  { code: "6-1000", name: "Beban Sewa", is_postable: true, is_active: true },
];
describe("U7 — pita periode tertutup", () => {
  test("mengatakan yang sebenarnya (akan ditolak) + tautan Ajukan Buka Periode", async () => {
    routeGet({ "/finance/closing/status": { closed: true, period_label: "Oktober 2026" } });
    const onNavigateTo = jest.fn();
    const { host } = await mount(
      <AppNavProvider role="admin" onNavigateTo={onNavigateTo}>
        <JournalEntryModal accounts={ACCOUNTS} onClose={jest.fn()} onSaved={jest.fn()} />
      </AppNavProvider>);
    const w = q(host, "je-period-warning");
    expect(w).not.toBeNull();
    expect(norm(w.textContent)).toContain("Periode Oktober 2026 sudah ditutup.");
    expect(w.textContent).toContain("Jurnal bertanggal ini akan ditolak");
    expect(w.textContent).not.toMatch(/tetap dapat diposting/);
    expect(w.textContent).not.toMatch(/reopen/i);
    expect(w.className).toContain("bg-kn-danger-soft");                       // merah, bukan kuning
    const link = q(host, "je-period-unlock-link");
    expect(link.textContent).toContain("Ajukan Buka Periode");
    await click(link);
    expect(onNavigateTo).toHaveBeenCalledWith("period-unlock", expect.anything());
  });
  test("tautan disembunyikan bila layar Buka Periode tidak boleh dibuka", async () => {
    routeGet({ "/finance/closing/status": { closed: true, period_label: "Oktober 2026" } });
    const { host } = await mount(<JournalEntryModal accounts={ACCOUNTS} onClose={jest.fn()} onSaved={jest.fn()} />);
    expect(q(host, "je-period-warning")).not.toBeNull();
    expect(q(host, "je-period-unlock-link")).toBeNull();
  });
});

test("U8: Debit 1250000 → pratinjau 'Rp 1.250.000'; nilai terkirim angka 1250000", async () => {
  routeGet({ "/finance/closing/status": { closed: false } });
  mockPost.mockResolvedValue({ data: { id: "je1", number: "KSC/JE-0001" } });
  const { host } = await mount(<JournalEntryModal accounts={ACCOUNTS} onClose={jest.fn()} onSaved={jest.fn()} />);
  const debit = q(host, "je-line-debit-0");
  expect(debit.getAttribute("type")).toBe("text");           // dulu type="number" polos
  await type(debit, "1250000");
  expect(norm(q(host, "je-line-debit-0-preview").textContent)).toBe("Rp 1.250.000");
  await type(q(host, "je-line-account-0"), "6-1000");
  await type(q(host, "je-line-account-1"), "1-1100");
  await type(q(host, "je-line-credit-1"), "1250000");
  expect(norm(q(host, "je-total-debit").textContent)).toBe("Rp 1.250.000");
  await click(q(host, "je-submit"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  const [url, body] = mockPost.mock.calls[0];
  expect(url).toBe("/api/gl/journal");
  expect(body.lines[0]).toEqual(expect.objectContaining({ account_code: "6-1000", debit: 1250000, credit: 0 }));
  expect(body.lines[1]).toEqual(expect.objectContaining({ account_code: "1-1100", debit: 0, credit: 1250000 }));
});

// ── U12 — riwayat kwitansi berhalaman ──────────────────────────────────────────────────────────────────────────────
test("U12: ARReceiptsHistory — 'Menampilkan 1–25 dari 30 penerimaan', tombol berikut aktif, PT ikut kueri", async () => {
  const items = Array.from({ length: 25 }, (_, i) => ({ id: `r${i}`, number: `KSC/AR-${String(30 - i).padStart(4, "0")}`,
    customer_name: "Toko Uji", amount: 100000, method: "transfer", status: "posted", allocations: [],
    receipt_date: "2026-10-22T18:47:00Z", entity_id: "ent_ksc" }));
  routeGet({ "/ar-receipts": { items, total: 30, page: 1, page_size: 25, has_more: true } });
  const { host } = await mount(<ARReceiptsHistory refreshKey={0} selectedEntity="ent_ksc" currentUser={ADMIN} />);
  expect(norm(q(host, "ar-history-pager-info").textContent)).toBe("Menampilkan 1–25 dari 30 penerimaan");
  expect(q(host, "ar-history-pager-next").disabled).toBe(false);
  expect(host.querySelectorAll('[data-testid^="ar-history-row-"]').length).toBe(25);
  const call = mockGet.mock.calls.find(([u]) => u === "/api/ar-receipts");
  expect(call[1].params).toEqual(expect.objectContaining({ page: 1, page_size: 25, entity_id: "ent_ksc" }));
  // Status = ikon + teks + warna, bahasa Indonesia (dulu "Posted"/"Void" tanpa ikon).
  const st = q(host, "ar-history-status-r0");
  expect(st.textContent).toBe("Tercatat");
  expect(st.querySelector("svg")).not.toBeNull();
  expect(q(host, "ar-history-table").className).toContain("data-table");
});

// ── UX-12 kas: daftar berhalaman + lencana tab dari server; tanggal WIB ────────────────────────────────────────────
test("Transaksi Kas: 50 per halaman di server, lencana tab dari summary.counts, saringan tab ikut kueri, tanggal WIB", async () => {
  const items = [{ id: "t1", number: "KSC/CASH-0501", cash_type: "kas_kecil", direction: "out", amount: 75000,
    category: "operasional", description: "Beli ATK", entity_id: "ent_ksc", txn_date: "2026-10-22T18:47:00Z" }];
  routeGet({
    "/cash-transactions/summary": { kas_kecil: {}, kas_besar: {}, kas_kecil_per_entity: {},
      counts: { all: 501, kas_kecil: 300, kas_besar: 201 } },
    "/cash-transactions": { items, total: 501, page: 1, page_size: 50, has_more: true },
  });
  const { host } = await mount(<CashManagementView currentUser={ADMIN} selectedEntity="ent_ksc" />);
  expect(q(host, "cash-filter-count-all").textContent).toBe("501");
  expect(q(host, "cash-filter-count-kas_kecil").textContent).toBe("300");
  expect(q(host, "cash-filter-count-kas_besar").textContent).toBe("201");
  expect(norm(q(host, "cash-pager-info").textContent)).toBe("Menampilkan 1–50 dari 501 transaksi");
  expect(q(host, "cash-row-date-t1").textContent).toBe("23 Okt 2026");   // 22 Okt 18.47 UTC = 23 Okt 01.47 WIB
  const first = mockGet.mock.calls.filter(([u]) => u === "/api/cash-transactions");
  expect(first[0][1].params).toEqual(expect.objectContaining({ page: 1, page_size: 50, entity_id: "ent_ksc" }));
  await click(q(host, "cash-filter-kas_besar"));
  const last = mockGet.mock.calls.filter(([u]) => u === "/api/cash-transactions").pop();
  expect(last[1].params).toEqual(expect.objectContaining({ cash_type: "kas_besar", page: 1 }));
});

// ── UX-18 — satu pemformat tanggal WIB ─────────────────────────────────────────────────────────────────────────────
test("UX-18: pemformat tanggal lokal = formatDate/formatDateTime WIB (tahun empat angka)", () => {
  const T = "2026-10-22T18:47:00Z";
  expect(formatDate(T)).toBe("23 Okt 2026");
  for (const f of [crmFmtDate, cbFmtDate, icFmtDate, pcFmtDate, faFmtDate]) expect(f(T)).toBe("23 Okt 2026");
  expect(cbFmtDateTime(T)).toBe(formatDateTime(T));
  expect(formatDateTime(T)).toMatch(/^23 Okt 2026.*01\.47 WIB$/);
});
