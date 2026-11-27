// F1 — kwitansi otomatis dari mutasi bank · Tugas 6 (layar). Rancangan `docs/superpowers/specs/2026-11-27-kwitansi-
// otomatis-mutasi-design.md` §5.4–§5.6, §5.8; ketetapan R8 (tombol batal = sumber kwitansi, bukan match_type) dan R9
// (nominal kwitansi dari mutasi = nominal mutasi).
//  · Meja Keuangan: antrean `mutasi_berkode` di kelompok "Uang masuk perlu dicatat" (cash.create + ar_receipt.create),
//    pop-up `BankLineQueuePanel` (alasan, pratinjau pesanan, Terima/Tolak laporan bayar bersama mutasi), "Catat kwitansi"
//    → form Terima pembayaran terisi dari mutasi, disimpan lewat SATU permintaan `POST /lines/{id}/receipt`.
//  · Rekonsiliasi: alasan kartu, lencana "Kwitansi otomatis", "Batalkan kwitansi" (ar_receipt.void) → alasan → void.
//  · Pesan impor & "Cocokkan otomatis" menyebut jumlah kwitansi otomatis & yang perlu dicek.
//  · Pratinjau kwitansi bersumber mutasi; label & tujuan notifikasi baru.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { AppNavProvider } from "../../context/AppNavContext";
import FinanceDesk, { PERLU_TINDAKAN, susunKelompok } from "../finance/FinanceDesk";
import { DESK_DOC_OF, DESK_PANELS, docOfRow, panelFor } from "../desks/deskPanels";
import BankLineQueuePanel from "../desks/BankLineQueuePanel";
import ReceivePaymentModal from "../finance/payments/ReceivePaymentModal";
import BankReconciliationView from "../finance/BankReconciliationView";
import ReconImportPanel from "../finance/bank/ReconImportPanel";
import ArReceiptPreview from "../documents/preview/bodies/ArReceiptPreview";
import { receiptFromLine, voidLineReceipt } from "../finance/bank/bankLineReceiptApi";
import { TYPE_LABEL } from "../../components/NotificationCenter";
import { notifDocTarget } from "../notifications/notifDocTarget";
import { askConfirm, askReason } from "../../services/confirmService";
import { badgeLabel } from "../sales_admin/workDeskApi";
import { invalidatePaymentMethods } from "../../config/paymentMethods";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockToast = jest.fn();
const mockModalProps = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    put: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } } },
  API: "/api",
  setActiveEntity: () => {}, setAuthToken: () => {}, setLocationScope: () => {},
}));
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: (...a) => mockToast(...a) }));
jest.mock("../../services/confirmService", () => ({
  __esModule: true, askConfirm: jest.fn(), askReason: jest.fn(), askText: jest.fn(async () => null), askChoice: jest.fn(async () => null), default: {},
}));
jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid, disabled }) => (
    <select data-testid={tid} value={value ?? ""} disabled={disabled} onChange={(e) => onValueChange(e.target.value)}>
      <option value="" />
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: M, KNSelect: M };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: ({ value, onChange, "data-testid": tid }) => <input data-testid={tid} value={value || ""} onChange={(e) => onChange?.(e.target.value)} />,
  formatDateId: (v) => String(v || ""),
}));
jest.mock("@/components/KNDatePicker", () => ({
  __esModule: true,
  default: ({ value, onChange, "data-testid": tid }) => <input data-testid={tid} value={value || ""} onChange={(e) => onChange?.(e.target.value)} />,
}));
jest.mock("../../components/AskKnButton", () => ({ __esModule: true, AskKnButton: () => null, PENDING_KEY: "x" }));
jest.mock("../finance/payments/paymentApi", () => ({
  assessVariance: () => Promise.resolve({ direction: "none" }),
  directionMeta: () => ({ label: "", bg: "", fg: "" }), varianceMeta: () => Promise.resolve({ reasons: [] }),
  varianceKindMeta: () => ({ label: "", bg: "", fg: "" }),
}));
jest.mock("../sales_admin/SoTrackerCard", () => () => <div data-testid="so-tracker-stub" />);
jest.mock("../finance/TaxIssueDialog", () => () => null);
// Form asli dirender (uji isian & jumlah permintaan); pembungkus hanya mencatat props yang diterima dari meja.
jest.mock("../finance/payments/ReceivePaymentModal", () => {
  const ReactAsli = jest.requireActual("react");
  const asli = jest.requireActual("../finance/payments/ReceivePaymentModal");
  const Bungkus = (props) => { mockModalProps(props); return ReactAsli.createElement(asli.default, props); };
  return { __esModule: true, ...asli, default: Bungkus };
});

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const teks = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");
let roots = [];
const ENT = [{ id: "ent_ksc", short_name: "Sukacita", legal_name: "PT Kain Suka Cita" }];
async function mount(el, { nav = null } = {}) {
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host); roots.push(root);
  const isi = <EntityScopeProvider selectedEntity="ent_ksc" entities={ENT} canSwitch>{el}</EntityScopeProvider>;
  await act(async () => { root.render(nav ? <AppNavProvider role="admin" onNavigateTo={nav}>{isi}</AppNavProvider> : isi); });
  await tunggu();
  return host;
}
const klik = async (id) => {
  const el = typeof id === "string" ? q(id) : id;
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await tunggu();
};
async function ketik(id, value) {
  const el = q(id);
  const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await tunggu();
}
async function tunggu() { for (let i = 0; i < 6; i += 1) await act(async () => { await new Promise((r) => setTimeout(r, 0)); }); }
afterEach(async () => {
  for (const r of roots) await act(async () => r.unmount());
  roots = []; document.body.innerHTML = "";
  [mockGet, mockPost, mockToast, mockModalProps].forEach((m) => m.mockReset());
  askConfirm.mockReset(); askReason.mockReset();
  invalidatePaymentMethods();
  sessionStorage.clear();
});

const ALASAN = "Nominal mutasi Rp 1.500.000 ≠ tagihan Rp 1.318.125 (lebih Rp 181.875)";
const BARIS = { ref_type: "bank_statement_line", ref_id: "bl1", number: "KSC/SO-1", title: "Toko A",
  subtitle: `2026-11-26 · BCA Utama · KN-7F3K2 · ${ALASAN}`, value: 1500000, age_days: 1, badge: "nominal_beda",
  action: "Catat kwitansi", action_kind: "receipt_from_line", entity_id: "ent_ksc", line_id: "bl1", order_id: "so1",
  order_number: "KSC/SO-1", customer_id: "c1", bank_account_id: "acc1", stmt_date: "2026-11-26", ref: "TRX-77",
  codes: ["KN-7F3K2"], alasan: ALASAN, alasan_kode: "nominal_beda", report_id: "", row_key: "bl1" };
const SO1 = { id: "so1", number: "KSC/SO-1", customer_id: "c1", customer_name: "Toko A", entity_id: "ent_ksc", status: "approved",
  created_at: "2026-11-20T03:00:00Z", items: [{ product_name: "Katun A", sku: "KA-01", quantity: 10, unit: "meter", price: 150000, subtotal: 1500000 }],
  total_amount: 1500000, grand_total: 1500000, paid_total: 0 };
const REK = { id: "acc1", name: "BCA Utama", bank_name: "BCA", account_number: "123-456", holder_name: "PT Kain Suka Cita", is_default: true };
const REK2 = { id: "acc2", name: "Mandiri KSC", bank_name: "Mandiri", account_number: "140-00", holder_name: "PT Kain Suka Cita", is_default: false };
const LAPORAN = { id: "lb1", number: "LB-1", order_id: "so1", order_number: "KSC/SO-1", customer_id: "c1", amount: 1500000,
  transfer_date: "2026-11-26", method: "transfer", account_id: "acc1", account_name: "BCA Utama", status: "menunggu",
  created_by_name: "Sari", attachments: [{ id: "att1" }], attachment_count: 1 };
const deskDari = (baris = [BARIS]) => ({ queues: [
  { id: "uang_masuk", label: "Uang masuk", count: 0, rows: [] },
  { id: "mutasi_berkode", label: "Mutasi berkode perlu dicek", count: baris.length, rows: baris },
], not_my_desk: [] });
const PERMS_F1 = { payment_variance: ["decide"], ar_receipt: ["create"], cash: ["create"], order: ["view"], payment_report: ["decide"] };
const PERMS_TANPA_KAS = { payment_variance: ["decide"], ar_receipt: ["create"], order: ["view"], payment_report: ["decide"] };

function routeGet({ desk = deskDari(), reports = [LAPORAN] } = {}) {
  mockGet.mockImplementation(async (u, cfg) => {
    if (u.includes("/finance/desk")) return { data: desk };
    if (u === "/api/sales-orders/so1/payment-reports") return { data: { items: reports, bisa_lapor: true, bisa_putuskan: true } };
    if (u === "/api/sales-orders/so1") return { data: SO1 };
    if (u.includes("/ar-receipts/open-orders")) return { data: [{ order_id: "so1", number: "KSC/SO-1", outstanding: 1500000, receiving_account_id: "acc1" }] };
    if (u.includes("/ar-receipts/deposit")) return { data: {} };
    if (u.includes("/payment-methods")) return { data: [{ code: "transfer", name: "Transfer bank", needs_account: "bank", needs_reference: true }] };
    if (u.includes("/bank-accounts/receiving")) return { data: cfg?.params?.method === "transfer" ? [REK, REK2] : [] };
    if (u.includes("/settings/effective")) return { data: { payment: { wajib_nomor_referensi: false } } };
    if (u.includes("/cash-holdings/me/summary")) return { data: { mode: "kas_langsung" } };
    return { data: [] };
  });
}
const jumlahMuatMeja = () => mockGet.mock.calls.filter(([u]) => String(u).includes("/finance/desk")).length;
const postKe = (pola) => mockPost.mock.calls.filter(([u]) => pola.test(String(u)));

// ─── 1. Kamus lencana, label notifikasi, tujuan notifikasi ────────────────────────────────────────────────
test("lencana alasan kartu berbahasa Indonesia (kamus BADGE_LABEL)", () => {
  const harap = {
    nominal_beda: "Nominal beda", kode_ganda: "Dua kode", rekening_beda: "Rekening beda",
    rekening_tolak_cara: "Rekening tak menerima cara bayar", pesanan_mati: "Pesanan batal", sudah_lunas: "Sudah lunas",
    laporan_beda: "Laporan bayar beda", laporan_diproses: "Laporan sedang diproses",
    laporan_dan_kwitansi: "Kwitansi & laporan menunggu", periode_tutup: "Periode ditutup", pt_tidak_jelas: "PT tak jelas",
    selisih_perlu_putusan: "Perlu putusan selisih", otomatis_mati: "Otomatis mati", galat: "Gagal otomatis",
  };
  Object.entries(harap).forEach(([k, v]) => expect([k, badgeLabel(k)]).toEqual([k, v]));
});

test("notifikasi: label dua jenis baru; bayar_masuk_mutasi → pesanan, ringkasan_mutasi_otomatis → Meja Keuangan", () => {
  expect(TYPE_LABEL.bayar_masuk_mutasi).toBe("Pembayaran masuk (mutasi bank)");
  expect(TYPE_LABEL.ringkasan_mutasi_otomatis).toBe("Kwitansi otomatis dari mutasi");
  expect(notifDocTarget({ type: "bayar_masuk_mutasi", link: "/?view=orders&id=so1" }))
    .toEqual({ link: expect.objectContaining({ view: "orders", focus_type: "sales_order", focus_id: "so1" }) });
  expect(notifDocTarget({ type: "ringkasan_mutasi_otomatis", link: "/?view=finance-desk" }))
    .toEqual({ link: expect.objectContaining({ view: "finance-desk" }) });
  expect(notifDocTarget({ type: "x", link: "/?view=finance-desk" })).toBeNull();   // jenis lain tidak berubah
});

// ─── 2. Registri & izin kelompok ──────────────────────────────────────────────────────────────────────────
test("registri: baris mutasi_berkode (kelompok uang_masuk) → BankLineQueuePanel; dokumen = pesanan dari order_id", () => {
  const row = { ...BARIS, _queue: "mutasi_berkode" };
  expect(panelFor(row, { id: "uang_masuk" })).toBe(BankLineQueuePanel);
  expect(DESK_PANELS["queue:mutasi_berkode"]).toBe(BankLineQueuePanel);
  expect(DESK_DOC_OF["queue:mutasi_berkode"]).toBeTruthy();
  expect(docOfRow(row, { id: "uang_masuk" })).toEqual({ docType: "sales_order", docId: "so1" });
});

test("kelompok uang_masuk memuat antrean mutasi_berkode hanya bagi pemegang cash.create DAN ar_receipt.create", () => {
  const g = PERLU_TINDAKAN.find((x) => x.key === "uang_masuk");
  expect(g.queues).toContain("mutasi_berkode");
  const desk = deskDari();
  const ada = (perms) => (susunKelompok(perms, { desk }).find((x) => x.id === "uang_masuk")?.rows || [])
    .some((r) => r._queue === "mutasi_berkode");
  expect(ada(PERMS_F1)).toBe(true);
  expect(ada(PERMS_TANPA_KAS)).toBe(false);
  expect(ada({ ...PERMS_F1, ar_receipt: [] })).toBe(false);
});

// ─── 3. Meja Keuangan ─────────────────────────────────────────────────────────────────────────────────────
describe("Meja Keuangan — mutasi berkode perlu dicek", () => {
  const buka = async (perms = PERMS_F1, opts = {}) => {
    routeGet(opts);
    return mount(<FinanceDesk currentUser={{ permissions: perms }} selectedEntity="ent_ksc" />, { nav: opts.nav });
  };

  test("baris tampil di kartu Uang masuk dengan lencana alasan; tanpa cash.create tidak tampil", async () => {
    await buka();
    expect(teks(q("fin-desk-uang_masuk-action-bl1"))).toBe("Catat kwitansi");
    expect(teks(q("fin-desk-uang_masuk-badge-bl1"))).toBe("Nominal beda");
    for (const r of roots) await act(async () => r.unmount());
    roots = []; document.body.innerHTML = "";
    await buka(PERMS_TANPA_KAS);
    expect(q("fin-desk-uang_masuk-action-bl1")).toBeNull();
    expect(document.body.textContent).not.toContain(ALASAN);
  });

  test("pop-up: alasan + pratinjau pesanan; Catat kwitansi → SATU pop-up form terisi dari mutasi", async () => {
    await buka();
    await klik("fin-desk-uang_masuk-number-bl1");
    expect(q("fin-desk-bankline-panel")).not.toBeNull();
    expect(teks(q("fin-desk-bankline-reason"))).toContain(ALASAN);
    expect(teks(q("fin-desk-bankline-ref"))).toContain("TRX-77");
    expect(teks(q("doc-preview-lines"))).toContain("Katun A");          // pratinjau pesanan dari order_id
    expect(q("fin-desk-bankline-accept-report")).toBeNull();              // tanpa laporan menunggu
    expect(teks(q("fin-desk-detail-action"))).toBe("Catat kwitansi");
    await klik("fin-desk-detail-action");
    expect(q("fin-desk-detail")).toBeNull();                               // satu pop-up: rincian menutup dulu
    expect(q("ar-receipt-modal")).not.toBeNull();
    const props = mockModalProps.mock.calls[mockModalProps.mock.calls.length - 1][0];
    expect(props).toMatchObject({ bankLineId: "bl1", customerId: "c1", preselectOrderId: "so1", amountHint: 1500000 });
    expect(props.preset).toMatchObject({ accountId: "acc1", date: "2026-11-26", reference: "TRX-77" });
    expect(teks(q("ar-receipt-amount-line"))).toMatch(/Rp\s?1\.500\.000/);
    expect(teks(q("ar-receipt-date-line"))).toMatch(/26/);
    expect(q("ar-receipt-account").value).toBe("acc1");
    expect(q("ar-receipt-account").disabled).toBe(true);                   // rekening = rekening mutasi
    expect(q("ar-receipt-reference").value).toBe("TRX-77");
    expect(teks(q("ar-receipt-line-note"))).toContain(ALASAN);
  });

  test("simpan form dari meja: tepat SATU POST ke /lines/{id}/receipt (tanpa /ar-receipts & /match); toast + kartu dimuat ulang", async () => {
    await buka();
    askConfirm.mockResolvedValue(true);
    mockPost.mockResolvedValue({ data: { receipt: { id: "arc1", number: "KSC/KW-1", amount: 1500000, applied_total: 1500000 },
      line: { id: "bl1", status: "matched" }, released_order_ids: ["so1"] } });
    await klik("fin-desk-uang_masuk-action-bl1");                          // aksi di tempat: langsung form
    expect(q("ar-receipt-modal")).not.toBeNull();
    const awal = jumlahMuatMeja();
    await klik("ar-receipt-submit");
    expect(mockPost).toHaveBeenCalledTimes(1);
    const [url, body, cfg] = mockPost.mock.calls[0];
    expect(url).toBe("/api/bank-reconciliation/lines/bl1/receipt");
    expect(body).toMatchObject({ customer_id: "c1", amount: 1500000, method: "transfer", reference_no: "TRX-77" });
    expect(body.payment_report_id).toBeUndefined();
    expect(cfg.headers["Idempotency-Key"]).toBeTruthy();
    expect(postKe(/\/ar-receipts$/)).toHaveLength(0);
    expect(postKe(/\/match$/)).toHaveLength(0);
    expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: expect.stringContaining("KSC/KW-1") }));
    expect(q("ar-receipt-modal")).toBeNull();
    expect(jumlahMuatMeja()).toBeGreaterThan(awal);
  });

  test("laporan menunggu: 'Terima laporan ini dengan mutasi ini' → receiptFromLine dengan payment_report_id", async () => {
    await buka(PERMS_F1, { desk: deskDari([{ ...BARIS, badge: "otomatis_mati", alasan_kode: "otomatis_mati", report_id: "lb1" }]) });
    askConfirm.mockResolvedValue(true);
    mockPost.mockResolvedValue({ data: { receipt: { id: "arc2", number: "KSC/KW-2", amount: 1500000 }, line: {}, released_order_ids: [] } });
    await klik("fin-desk-uang_masuk-number-bl1");
    expect(teks(q("fin-desk-bankline-report"))).toContain("LB-1");
    expect(mockGet).toHaveBeenCalledWith("/api/sales-orders/so1/payment-reports");
    const awal = jumlahMuatMeja();
    await klik("fin-desk-bankline-accept-report");
    expect(askConfirm).toHaveBeenCalledWith(expect.objectContaining({ testId: "fin-desk-bankline-accept-confirm" }));
    expect(mockPost).toHaveBeenCalledTimes(1);
    const [url, body, cfg] = mockPost.mock.calls[0];
    expect(url).toBe("/api/bank-reconciliation/lines/bl1/receipt");
    expect(body).toMatchObject({ payment_report_id: "lb1", customer_id: "c1", amount: 1500000 });
    expect(cfg.headers["Idempotency-Key"]).toBeTruthy();
    expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: expect.stringContaining("KSC/KW-2") }));
    expect(q("fin-desk-detail")).toBeNull();
    expect(jumlahMuatMeja()).toBeGreaterThan(awal);
  });

  test("laporan menunggu: Tolak memakai aturan Lapor Bayar (alasan) — pop-up tetap terbuka untuk Catat kwitansi", async () => {
    await buka(PERMS_F1, { desk: deskDari([{ ...BARIS, report_id: "lb1", alasan_kode: "laporan_beda", badge: "laporan_beda" }]) });
    askReason.mockResolvedValue("Bukan transfer ini");
    mockPost.mockResolvedValue({ data: { ...LAPORAN, status: "ditolak" } });
    await klik("fin-desk-uang_masuk-number-bl1");
    await klik("fin-desk-bankline-reject-report");
    expect(askReason).toHaveBeenCalledWith(expect.objectContaining({ reasonMinLength: 5 }));
    const [url, body] = mockPost.mock.calls[0];
    expect(url).toBe("/api/payment-reports/lb1/tolak");
    expect(body).toEqual({ reason: "Bukan transfer ini" });
    expect(q("fin-desk-detail")).not.toBeNull();
  });

  test("galat Terima laporan tampil DI DALAM pop-up; pop-up tetap terbuka", async () => {
    await buka(PERMS_F1, { desk: deskDari([{ ...BARIS, report_id: "lb1" }]) });
    askConfirm.mockResolvedValue(true);
    mockPost.mockRejectedValue({ response: { status: 409, data: { detail: "Nominal laporan LB-1 berbeda dari mutasi." } } });
    await klik("fin-desk-uang_masuk-number-bl1");
    await klik("fin-desk-bankline-accept-report");
    expect(q("fin-desk-detail")).not.toBeNull();
    expect(teks(q("fin-desk-bankline-error"))).toContain("Nominal laporan LB-1 berbeda dari mutasi.");
  });

  test("tanpa payment_report.decide: laporan hanya dibaca, tanpa Terima/Tolak", async () => {
    await buka({ ...PERMS_F1, payment_report: [] }, { desk: deskDari([{ ...BARIS, report_id: "lb1" }]) });
    await klik("fin-desk-uang_masuk-number-bl1");
    expect(q("fin-desk-bankline-accept-report")).toBeNull();
    expect(q("fin-desk-bankline-reject-report")).toBeNull();
    expect(q("fin-desk-bankline-report-note")).not.toBeNull();
  });

  test("Buka Rekonsiliasi → layar Rekonsiliasi Bank dengan rekening mutasi terpilih", async () => {
    const nav = jest.fn();
    await buka(PERMS_F1, { nav });
    await klik("fin-desk-uang_masuk-number-bl1");
    await klik("fin-desk-bankline-open-recon");
    expect(nav).toHaveBeenCalledWith("bank-reconciliation",
      expect.objectContaining({ preset: expect.objectContaining({ bank_account_id: "acc1" }) }));
  });
});

// ─── 4. Form Terima pembayaran dengan bankLineId ──────────────────────────────────────────────────────────
test("ReceivePaymentModal bankLineId + paymentReportId: satu POST atomik, payment_report_id diteruskan, pesan sukses", async () => {
  routeGet();
  askConfirm.mockResolvedValue(true);
  mockPost.mockResolvedValue({ data: { receipt: { id: "arc3", number: "KSC/KW-3", amount: 1500000, applied_total: 1500000 },
    line: { id: "bl9" }, released_order_ids: ["so1"] } });
  const onDone = jest.fn();
  await mount(<ReceivePaymentModal customerId="c1" customerName="Toko A" preselectOrderId="so1" bankLineId="bl9"
    paymentReportId="lb1" amountHint={1500000} preset={{ accountId: "acc1", date: "2026-11-26", reference: "TRX-9" }}
    onClose={() => {}} onDone={onDone} />);
  await klik("ar-receipt-submit");
  expect(mockPost).toHaveBeenCalledTimes(1);
  const [url, body] = mockPost.mock.calls[0];
  expect(url).toBe("/api/bank-reconciliation/lines/bl9/receipt");
  expect(body).toMatchObject({ payment_report_id: "lb1", amount: 1500000 });
  expect(onDone).toHaveBeenCalledWith(expect.stringMatching(/KSC\/KW-3.*mutasi bank/), expect.objectContaining({ number: "KSC/KW-3" }));
});

test("ReceivePaymentModal bankLineId: nominal = nominal mutasi walau alokasi 'Atur sendiri' lebih kecil (R9)", async () => {
  routeGet();
  mockGet.mockImplementation(async (u, cfg) => {
    if (u.includes("/ar-receipts/open-orders")) return { data: [{ order_id: "so1", number: "KSC/SO-1", outstanding: 1318125 }] };
    if (u.includes("/payment-methods")) return { data: [{ code: "transfer", name: "Transfer bank", needs_account: "bank", needs_reference: true }] };
    if (u.includes("/bank-accounts/receiving")) return { data: cfg?.params?.method === "transfer" ? [REK] : [] };
    if (u.includes("/cash-holdings/me/summary")) return { data: { mode: "kas_langsung" } };
    return { data: {} };
  });
  askConfirm.mockResolvedValue(true);
  mockPost.mockResolvedValue({ data: { receipt: { id: "arc4", number: "KSC/KW-4", amount: 1500000 }, line: {}, released_order_ids: [] } });
  await mount(<ReceivePaymentModal customerId="c1" customerName="Toko A" preselectOrderId="so1" bankLineId="bl1"
    amountHint={1500000} preset={{ accountId: "acc1", date: "2026-11-26", reference: "TRX-77" }} onClose={() => {}} onDone={() => {}} />);
  expect(teks(q("ar-receipt-total"))).toMatch(/Rp\s?1\.500\.000/);
  await klik("ar-receipt-submit");
  const [, body] = mockPost.mock.calls[0];
  expect(body.amount).toBe(1500000);
  expect(body.allocations).toEqual([{ order_id: "so1", amount: 1318125 }]);
});

// ─── 5. Rekonsiliasi Bank ─────────────────────────────────────────────────────────────────────────────────
const HIT = { code: "KN-7F3K2", order_id: "so1", order_number: "KSC/SO-1", customer_id: "c1", customer_name: "Toko A", has_open_receipt: false };
const LINES = [
  { id: "k1", status: "unmatched", direction: "in", amount: 1500000, stmt_date: "2026-11-26", description: "TRSF KN-7F3K2",
    pay_code_hits: [HIT], f1: { status: "kartu", alasan_kode: "nominal_beda", alasan: ALASAN } },
  { id: "o1", status: "matched", direction: "in", amount: 1318125, stmt_date: "2026-11-26", description: "TRSF KN-9QW2X",
    match_type: "auto_receipt", match_kind: "1:1", matched_txns: [{ id: "t1", number: "CASH-1", allocated: 1318125 }],
    f1: { status: "otomatis", jalur: "C", receipt_id: "arc9", order_id: "so2", pernah_otomatis: true } },
  { id: "a1", status: "matched", direction: "in", amount: 500000, stmt_date: "2026-11-26", description: "TRSF KN-A",
    match_type: "auto", match_kind: "1:1", matched_txns: [{ id: "t2", number: "CASH-2", allocated: 500000 }],
    f1: { status: "otomatis", jalur: "A", receipt_id: "arc5", pernah_otomatis: true } },
  { id: "m1", status: "matched", direction: "in", amount: 700000, stmt_date: "2026-11-26", description: "TRSF KN-M",
    match_type: "manual", match_kind: "1:1", matched_txns: [{ id: "t3", number: "CASH-3", allocated: 700000 }],
    f1: { status: "manual", jalur: "manual", receipt_id: "arc7" } },
  { id: "d1", status: "unmatched", direction: "in", amount: 900000, stmt_date: "2026-11-26", description: "TRSF KN-D",
    f1: { status: "dibatalkan", alasan: "Kwitansi KSC/KW-8 dibatalkan Budi: salah pesanan", pernah_otomatis: true } },
];
const SUMMARY = { statement: { net: 0, lines: 5, user_lines: 5, ever_user_import: true }, book: { net: 0 }, matched: 3,
  unmatched_lines: 2, suggested: 0, holding: { balance: 0, count: 0 }, difference: 0, unmatched_book_txns: 0 };
function routeRecon() {
  mockGet.mockImplementation(async (u) => {
    if (u.endsWith("/bank-accounts")) return { data: [REK] };
    if (u.endsWith("/bank-reconciliation/lines")) return { data: LINES };
    if (u.endsWith("/bank-reconciliation/summary")) return { data: SUMMARY };
    if (u.endsWith("/bank-reconciliation/holding")) return { data: { items: [], balance: 0, count: 0 } };
    return { data: [] };
  });
}
const RECON_VOID = { permissions: { cash: ["view", "create"], ar_receipt: ["create", "void"] } };

describe("Rekonsiliasi Bank — F1", () => {
  test("kartu: alasan tampil; lencana Kwitansi otomatis untuk auto_receipt; tanda dibatalkan", async () => {
    routeRecon();
    await mount(<BankReconciliationView user={RECON_VOID} />);
    expect(teks(q("recon-f1-reason-k1"))).toContain(ALASAN);
    expect(teks(q("recon-f1-auto-o1"))).toBe("Kwitansi otomatis");
    expect(q("recon-f1-auto-a1")).toBeNull();                                // jalur A: kwitansi lama, bukan lahir dari mutasi
    expect(q("recon-f1-reason-o1")).toBeNull();
    expect(teks(q("recon-f1-voided-d1"))).toContain("dibatalkan");
  });

  test("Batalkan kwitansi hanya untuk kwitansi yang lahir dari mutasi (R8) dan pemegang ar_receipt.void", async () => {
    routeRecon();
    await mount(<BankReconciliationView user={RECON_VOID} />);
    expect(q("recon-f1-void-o1")).not.toBeNull();
    expect(q("recon-f1-void-m1")).not.toBeNull();                            // dicatat dari mutasi (match_type manual)
    expect(q("recon-f1-void-a1")).toBeNull();
    expect(q("recon-f1-void-k1")).toBeNull();
    for (const r of roots) await act(async () => r.unmount());
    roots = []; document.body.innerHTML = "";
    routeRecon();
    await mount(<BankReconciliationView user={{ permissions: { cash: ["view", "create"], ar_receipt: ["create"] } }} />);
    expect(q("recon-f1-void-o1")).toBeNull();
    expect(q("recon-f1-void-m1")).toBeNull();
  });

  test("batal: alasan wajib → voidLineReceipt (kunci idempotensi) → peringatan respons tampil, daftar dimuat ulang", async () => {
    routeRecon();
    askReason.mockResolvedValue("Salah pesanan");
    const PERINGATAN = "Pesanan KSC/SO-2 sudah dilepas ke gudang (Dikirim); membatalkan kwitansi tidak menahan barang — tahan pesanan atau hubungi Gudang bila perlu.";
    mockPost.mockResolvedValue({ data: { order_released: true, peringatan: PERINGATAN, receipt: { number: "KSC/KW-9" } } });
    await mount(<BankReconciliationView user={RECON_VOID} />);
    const n = () => mockGet.mock.calls.filter(([u]) => u.endsWith("/bank-reconciliation/lines")).length;
    const awal = n();
    await klik("recon-f1-void-o1");
    expect(askReason).toHaveBeenCalledWith(expect.objectContaining({ reasonMinLength: 5, testId: "recon-f1-void-reason" }));
    expect(mockPost).toHaveBeenCalledTimes(1);
    const [url, body, cfg] = mockPost.mock.calls[0];
    expect(url).toBe("/api/bank-reconciliation/lines/o1/void-receipt");
    expect(body).toEqual({ reason: "Salah pesanan" });
    expect(cfg.headers["Idempotency-Key"]).toBeTruthy();
    expect(teks(q("recon-f1-warning"))).toContain(PERINGATAN);
    expect(teks(q("recon-notice"))).toContain("KSC/KW-9");
    expect(n()).toBeGreaterThan(awal);
  });

  test("batal dibatalkan di dialog alasan → tidak ada permintaan", async () => {
    routeRecon();
    askReason.mockResolvedValue(null);
    await mount(<BankReconciliationView user={RECON_VOID} />);
    await klik("recon-f1-void-o1");
    expect(mockPost).not.toHaveBeenCalled();
  });

  test("Catat sebagai kwitansi di Rekonsiliasi: form dengan bankLineId → satu POST atomik", async () => {
    routeRecon();
    const lama = mockGet.getMockImplementation();
    mockGet.mockImplementation(async (u, cfg) => {
      if (u.includes("/ar-receipts/open-orders")) return { data: [{ order_id: "so1", number: "KSC/SO-1", outstanding: 1500000, receiving_account_id: "acc1" }] };
      if (u.includes("/payment-methods")) return { data: [{ code: "transfer", name: "Transfer bank", needs_account: "bank", needs_reference: true }] };
      if (u.includes("/bank-accounts/receiving")) return { data: [REK] };
      if (u.includes("/cash-holdings/me/summary")) return { data: { mode: "kas_langsung" } };
      if (u.includes("/settings/effective") || u.includes("/ar-receipts/deposit")) return { data: {} };
      return lama(u, cfg);
    });
    askConfirm.mockResolvedValue(true);
    mockPost.mockResolvedValue({ data: { receipt: { id: "arc6", number: "KSC/KW-6", amount: 1500000 }, line: {}, released_order_ids: [] } });
    await mount(<BankReconciliationView user={RECON_VOID} />);
    await klik("recon-record-receipt-k1");
    expect(teks(q("ar-receipt-line-note"))).toContain(ALASAN);
    await klik("ar-receipt-submit");
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe("/api/bank-reconciliation/lines/k1/receipt");
    expect(teks(q("recon-notice"))).toContain("KSC/KW-6");
  });

  test("Cocokkan otomatis: pesan memuat jumlah kwitansi otomatis dan yang perlu dicek", async () => {
    routeRecon();
    mockPost.mockResolvedValue({ data: { matched: 1, auto_min: 80, suggested: 0, suggest_min: 60, unmatched_lines: 2,
      kwitansi_otomatis: 3, kartu: 2, nilai_otomatis: 4500000 } });
    await mount(<BankReconciliationView user={RECON_VOID} />);
    await klik("recon-auto-match");
    expect(mockPost.mock.calls[0][0]).toBe("/api/bank-reconciliation/auto-match");
    expect(teks(q("recon-notice"))).toContain("3 kwitansi otomatis");
    expect(teks(q("recon-notice"))).toContain("2 perlu dicek");
  });

  test("Cocokkan otomatis tanpa hasil F1: pesan lama tanpa kalimat kwitansi otomatis", async () => {
    routeRecon();
    mockPost.mockResolvedValue({ data: { matched: 1, auto_min: 80, suggested: 0, suggest_min: 60, unmatched_lines: 2,
      kwitansi_otomatis: 0, kartu: 0, nilai_otomatis: 0 } });
    await mount(<BankReconciliationView user={RECON_VOID} />);
    await klik("recon-auto-match");
    expect(teks(q("recon-notice"))).not.toContain("kwitansi otomatis");
    expect(teks(q("recon-notice"))).not.toContain("perlu dicek");
  });
});

test("impor mutasi: pesan sukses memuat jumlah kwitansi otomatis & yang perlu dicek", async () => {
  mockPost.mockResolvedValue({ data: { format_name: "BCA", imported: 5, skipped: 0, kwitansi_otomatis: 2, kartu: 1, nilai_otomatis: 3000000 } });
  const onDone = jest.fn();
  await mount(<ReconImportPanel accountId="acc1" formats={[]} onClose={() => {}} onDone={onDone} />);
  await ketik("recon-raw", "26/11 TRSF KN-7F3K2 1.500.000");
  await klik("recon-import-submit");
  expect(mockPost.mock.calls[0][0]).toBe("/api/bank-reconciliation/import-file");
  const pesan = onDone.mock.calls[0][0];
  expect(pesan).toContain("2 kwitansi otomatis");
  expect(pesan).toContain("1 perlu dicek");
});

// ─── 6. Pratinjau kwitansi ────────────────────────────────────────────────────────────────────────────────
test("pratinjau kwitansi bersumber mutasi_bank menulis 'Lahir dari mutasi bank …'; kwitansi biasa tidak", async () => {
  const doc = { id: "arc1", number: "KSC/KW-1", customer_name: "Toko A", amount: 1500000, status: "posted", entity_id: "ent_ksc",
    receipt_date: "2026-11-26T00:00:00+07:00", reference_no: "TRX-77", source: "mutasi_bank", bank_line_id: "bl1",
    account_snapshot: { name: "BCA Utama", bank_name: "BCA", account_number: "123-456" }, allocations: [] };
  await mount(<ArReceiptPreview doc={doc} push={() => {}} canPush={() => false} currentUser={{ permissions: {} }} />);
  const asal = teks(q("doc-preview-ar-receipt-source"));
  expect(asal).toContain("Lahir dari mutasi bank");
  expect(asal).toContain("BCA Utama");
  expect(asal).toContain("TRX-77");
  for (const r of roots) await act(async () => r.unmount());
  roots = []; document.body.innerHTML = "";
  await mount(<ArReceiptPreview doc={{ ...doc, source: undefined, bank_line_id: undefined }} push={() => {}} canPush={() => false}
    currentUser={{ permissions: {} }} />);
  expect(q("doc-preview-ar-receipt-source")).toBeNull();
});

// ─── 7. Pemanggil API ─────────────────────────────────────────────────────────────────────────────────────
test("receiptFromLine & voidLineReceipt: POST ber-Idempotency-Key, mengembalikan data", async () => {
  mockPost.mockResolvedValueOnce({ data: { receipt: { id: "r" }, line: {}, released_order_ids: [] } });
  await expect(receiptFromLine("bl1", { amount: 1 }, "k-1")).resolves.toEqual({ receipt: { id: "r" }, line: {}, released_order_ids: [] });
  expect(mockPost).toHaveBeenLastCalledWith("/api/bank-reconciliation/lines/bl1/receipt", { amount: 1 },
    expect.objectContaining({ headers: expect.objectContaining({ "Idempotency-Key": "k-1" }) }));
  mockPost.mockResolvedValueOnce({ data: { order_released: false, peringatan: "" } });
  await expect(voidLineReceipt("bl1", "alasan uji", "k-2")).resolves.toEqual({ order_released: false, peringatan: "" });
  expect(mockPost).toHaveBeenLastCalledWith("/api/bank-reconciliation/lines/bl1/void-receipt", { reason: "alasan uji" },
    expect.objectContaining({ headers: expect.objectContaining({ "Idempotency-Key": "k-2" }) }));
});
