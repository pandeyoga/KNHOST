// Lapor Bayar CBD & DP · Tugas 8 — Meja Keuangan (lapor_bayar: bukti + pratinjau pesanan + Terima/Tolak di tempat), keterangan
// Admin Sales, HP (panel bayar di rincian pesanan, pemandu MobileArReceipt), label & tautan notifikasi, dan ketetapan R15
// (galat Terima menyebut nomor laporan, Terima mati tanpa bukti, kwitansi tunai bagi non-pemutus, toast galat unggah).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import FinanceDesk from "../finance/FinanceDesk";
import DeskRowDetail from "../desks/DeskRowDetail";
import { DESK_DOC_OF, DESK_PANELS, docOfRow, panelFor } from "../desks/deskPanels";
import PayReportList from "../orders/payReport/PayReportList";
import LaporBayarDialog from "../orders/payReport/LaporBayarDialog";
import DispatchPaymentGatePanel from "../orders/DispatchPaymentGatePanel";
import MobileOrders from "../sales/mobile/MobileOrders";
import MobileArReceipt from "../sales/mobile/MobileArReceipt";
import { TYPE_LABEL, typeLabel } from "../../components/NotificationCenter";
import { notifDocTarget } from "../notifications/notifDocTarget";
import { askConfirm, askReason } from "../../services/confirmService";
import { badgeLabel } from "../sales_admin/workDeskApi";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockToast = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } } },
  API: "/api",
  setActiveEntity: () => {}, setAuthToken: () => {},
}));
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: (...a) => mockToast(...a) }));
jest.mock("../../services/confirmService", () => ({
  __esModule: true, askConfirm: jest.fn(), askReason: jest.fn(), askText: jest.fn(async () => null), askChoice: jest.fn(async () => null), default: {},
}));
jest.mock("../../hooks/useBlobUrl", () => ({
  ...jest.requireActual("../../hooks/useBlobUrl"),
  useBlobUrl: () => ({ src: "blob:bukti", type: "image/png", status: "ok" }),
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
  default: ({ value, onChange, "data-testid": tid }) => <input data-testid={tid} value={value || ""} onChange={(e) => onChange(e.target.value)} />,
}));
jest.mock("../sales_admin/SoTrackerCard", () => () => <div data-testid="so-tracker-stub" />);
jest.mock("../finance/TaxIssueDialog", () => () => null);
jest.mock("../finance/payments/ReceivePaymentModal", () => ({ cashOnly, preselectOrderId }) => (
  <div data-testid="ar-receipt-modal" data-cash-only={String(Boolean(cashOnly))} data-order={preselectOrderId || ""} />));
jest.mock("../sales/mobile/MobilePendingQueue", () => () => null);
jest.mock("../sales/mobile/MobileAmendSheet", () => () => null);
jest.mock("../sales/mobile/MobileOrderJourney", () => () => null);
jest.mock("../orders/SoApprovalsPanel", () => () => null);
jest.mock("../sales_admin/VerifyOrderDialog", () => () => null);
jest.mock("../sales_admin/ReleaseToWarehouseDialog", () => () => null);
jest.mock("../sales_admin/FulfillmentDecisionDialog", () => () => null);

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const semua = (id) => document.body.querySelectorAll(`[data-testid="${id}"]`);
const teks = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");
let roots = [];
async function mount(el) {
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host); roots.push(root);
  await act(async () => { root.render(el); }); await act(async () => {}); await act(async () => {});
  return host;
}
const klik = async (id) => act(async () => { q(id).dispatchEvent(new MouseEvent("click", { bubbles: true })); });
const tunggu = async () => { for (let i = 0; i < 4; i += 1) await act(async () => { await new Promise((r) => setTimeout(r, 0)); }); };   // eslint-disable-line no-await-in-loop
afterEach(async () => {
  for (const r of roots) await act(async () => r.unmount());
  roots = []; document.body.innerHTML = "";
  mockGet.mockReset(); mockPost.mockReset(); mockToast.mockReset(); askConfirm.mockReset(); askReason.mockReset();
  sessionStorage.clear();
});

const REPORT = { id: "lb1", number: "LB-1", order_id: "so1", order_number: "KSC/SO-1", amount: 600000, transfer_date: "2026-11-25",
  method: "transfer", account_id: "acc1", account_name: "BCA Utama", status: "menunggu", created_by_name: "Sari", note: "",
  attachments: [{ id: "att1", original_filename: "bukti.png", content_type: "image/png" }], attachment_count: 1 };
const SO1 = { id: "so1", number: "KSC/SO-1", customer_id: "c1", customer_name: "Toko A", entity_id: "ent_ksc", status: "approved",
  created_at: "2026-11-20T03:00:00Z", items: [{ product_name: "Katun A", sku: "KA-01", quantity: 10, unit: "meter", price: 25000, subtotal: 250000 }],
  total_amount: 250000, grand_total: 277500, ppn_amount: 27500, paid_total: 0 };
const ROW = { ref_type: "payment_report", ref_id: "lb1", number: "LB-1", title: "Toko A", subtitle: "KSC/SO-1 · transfer 2026-11-25 · BCA Utama",
  value: 600000, age_days: 1, badge: "menunggu dicek", action: "Putuskan", action_kind: "decide_payment_report", entity_id: "ent_ksc",
  order_id: "so1", order_number: "KSC/SO-1", amount: 600000, transfer_date: "2026-11-25", account_label: "BCA Utama", attachments_count: 1,
  reported_by_name: "Sari", row_key: "lb1" };
const TERIMA_LAIN = { ref_type: "customer", ref_id: "c9", number: "KSC/SO-9", title: "Toko Z", value: 5000, entity_id: "ent_ksc",
  action: "Catat kwitansi", action_kind: "receipt", order_id: "so9", age_days: 2, badge: "tertahan bayar", row_key: "so9" };
const DESK = { queues: [
  { id: "uang_masuk", label: "Uang masuk", count: 0, rows: [] },
  { id: "bayar_sebelum_kirim", label: "Bayar sebelum kirim", count: 1, rows: [TERIMA_LAIN] },
  { id: "lapor_bayar", label: "Lapor bayar menunggu dicek", count: 1, rows: [ROW] },
], not_my_desk: [] };
const PERMS_FIN = { payment_variance: ["decide"], payment_report: ["create", "decide"], ar_receipt: ["create"], order: ["view"] };
const PERMS_TANPA = { payment_variance: ["decide"], ar_receipt: ["create"], order: ["view"] };

function routeGet({ reports = [REPORT], bisaPutuskan = true, mode = "kas_langsung" } = {}) {
  mockGet.mockImplementation(async (u) => {
    if (u.includes("/finance/desk")) return { data: DESK };
    if (u === "/api/sales-orders/so1/payment-reports") return { data: { items: reports, bisa_lapor: true, bisa_putuskan: bisaPutuskan } };
    if (u === "/api/sales-orders/so1") return { data: SO1 };
    if (u === "/api/cash-holdings/me/summary") return { data: { mode } };
    if (u === "/api/sales-orders/so1/dispatch-payment-gate") return { data: GATE };
    return { data: [] };
  });
}
const GATE = { applies: true, blocked: true, term_code: "CBD", term_name: "CBD", dp_percent: 100, grand_total: 1000000,
  required: 1000000, paid: 400000, shortfall: 600000, released: null, mode: "block" };
const jumlahMuatMeja = () => mockGet.mock.calls.filter(([u]) => String(u).includes("/finance/desk")).length;

// ─── 1. Registri panel ────────────────────────────────────────────────────────────────────────────────────
test("R21 — lencana baris lapor_bayar berbahasa Finance, bukan 'Menunggu manajer'", () => {
  expect(badgeLabel("menunggu dicek")).toBe("Menunggu dicek");
  expect(badgeLabel("sedang diproses")).toBe("Sedang diproses");
  expect(badgeLabel("macet — ulangi")).toBe("Macet — ulangi");
  expect(badgeLabel(ROW.badge)).not.toMatch(/manajer/i);
});

test("registri: baris lapor_bayar (kelompok uang_masuk) → PayReportQueuePanel; dokumen = pesanan dari order_id", () => {
  const row = { ...ROW, _queue: "lapor_bayar" };
  expect(DESK_DOC_OF["queue:lapor_bayar"]).toBeTruthy();
  expect(panelFor(row, { id: "uang_masuk" })).toBe(DESK_PANELS["queue:lapor_bayar"]);
  expect(panelFor(row, { id: "uang_masuk" })).not.toBe(DESK_PANELS["queue:uang_masuk"]);
  expect(docOfRow(row, { id: "uang_masuk" })).toEqual({ docType: "sales_order", docId: "so1" });
  // baris uang masuk biasa tidak ikut berubah
  expect(panelFor({ ...TERIMA_LAIN, _queue: "uang_masuk" }, { id: "uang_masuk" })).toBe(DESK_PANELS["queue:uang_masuk"]);
});

// ─── 2. Meja Keuangan ─────────────────────────────────────────────────────────────────────────────────────
describe("Meja Keuangan — lapor_bayar", () => {
  const buka = async (perms = PERMS_FIN) => {
    routeGet();
    await mount(<FinanceDesk currentUser={{ permissions: perms }} selectedEntity="ent_ksc" />);
    await tunggu();
  };

  test("tanpa izin payment_report.decide baris laporan tidak tampil (walau server mengirimnya)", async () => {
    await buka(PERMS_TANPA);
    expect(q("fin-desk-bayar_sebelum_kirim-action-so9") || q("fin-desk-uang_masuk-action-so9")).not.toBeNull();
    expect(q("fin-desk-uang_masuk-action-lb1")).toBeNull();
    expect(document.body.textContent).not.toContain("LB-1");
  });

  test("pemegang decide: baris tampil di kartu uang masuk; Putuskan membuka SATU pop-up berisi bukti + pratinjau pesanan", async () => {
    await buka();
    expect(q("fin-desk-uang_masuk-action-lb1")).not.toBeNull();
    await klik("fin-desk-uang_masuk-action-lb1"); await tunggu();
    expect(semua("fin-desk-detail")).toHaveLength(1);
    expect(q("pay-report-lb1-proof-att1")).not.toBeNull();             // bukti lewat blob
    expect(teks(q("pay-report-lb1"))).toContain("BCA Utama");
    expect(teks(q("doc-preview-lines"))).toContain("Katun A");           // pratinjau pesanan di pop-up yang sama
    expect(mockGet).toHaveBeenCalledWith("/api/sales-orders/so1/payment-reports");
    expect(q("pay-report-lb1-terima")).not.toBeNull();
    expect(q("pay-report-lb1-tolak")).not.toBeNull();
    expect(q("fin-desk-detail-action")).toBeNull();                      // keputusan di panel, bukan tombol kaki yang pindah layar
  });

  test("Terima di tempat: konfirmasi → POST terima (kunci idempotensi) → toast, pop-up menutup, kartu dimuat ulang", async () => {
    await buka();
    askConfirm.mockResolvedValue(true);
    mockPost.mockResolvedValue({ data: { report: {}, receipt_number: "KW-9", released: true, waiting_bank: false } });
    await klik("fin-desk-uang_masuk-action-lb1"); await tunggu();
    const awal = jumlahMuatMeja();
    await klik("pay-report-lb1-terima"); await tunggu();
    const [url, , cfg] = mockPost.mock.calls[0];
    expect(url).toBe("/api/payment-reports/lb1/terima");
    expect(cfg.headers["Idempotency-Key"]).toBeTruthy();
    expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: expect.stringContaining("KW-9") }));
    expect(q("fin-desk-detail")).toBeNull();
    expect(jumlahMuatMeja()).toBeGreaterThan(awal);
  });

  test("galat 409 saat Terima: tampil DI DALAM pop-up dengan nomor laporan; pop-up tetap terbuka", async () => {
    await buka();
    askConfirm.mockResolvedValue(true);
    mockPost.mockRejectedValue({ response: { status: 409, data: { detail: "Laporan sudah diputus orang lain." } } });
    await klik("fin-desk-uang_masuk-action-lb1"); await tunggu();
    await klik("pay-report-lb1-terima"); await tunggu();
    expect(q("fin-desk-detail")).not.toBeNull();
    expect(teks(q("pay-report-error"))).toMatch(/LB-1/);
    expect(teks(q("pay-report-error"))).toMatch(/Laporan sudah diputus orang lain/);
  });

  test("R18-b: laporan macet di 'memproses' → pop-up menawarkan ulangi Terima / Tolak di tempat", async () => {
    routeGet({ reports: [{ ...REPORT, status: "memproses", claim_stale: true, claim_at: "2026-11-25T03:05:00+00:00" }] });
    await mount(<FinanceDesk currentUser={{ permissions: PERMS_FIN }} selectedEntity="ent_ksc" />);
    await tunggu();
    askReason.mockResolvedValue("Bukti tidak cocok");
    mockPost.mockResolvedValue({ data: { ...REPORT, status: "ditolak" } });
    await klik("fin-desk-uang_masuk-action-lb1"); await tunggu();
    expect(teks(q("pay-report-lb1-stale"))).toMatch(/Macet sejak .* — ulangi Terima \/ Tolak/);
    expect(q("pay-report-lb1-terima")).not.toBeNull();
    await klik("pay-report-lb1-tolak"); await tunggu();
    const [url, body] = mockPost.mock.calls[0];
    expect(url).toBe("/api/payment-reports/lb1/tolak");
    expect(body).toEqual({ reason: "Bukti tidak cocok" });
    expect(q("fin-desk-detail")).toBeNull();
  });

  test("Tolak di tempat: alasan → POST tolak {reason}; pop-up menutup", async () => {
    await buka();
    askReason.mockResolvedValue("Nominal tidak cocok");
    mockPost.mockResolvedValue({ data: { ...REPORT, status: "ditolak" } });
    await klik("fin-desk-uang_masuk-action-lb1"); await tunggu();
    await klik("pay-report-lb1-tolak"); await tunggu();
    const [url, body] = mockPost.mock.calls[0];
    expect(url).toBe("/api/payment-reports/lb1/tolak");
    expect(body).toEqual({ reason: "Nominal tidak cocok" });
    expect(q("fin-desk-detail")).toBeNull();
  });
});

// ─── 3. Admin Sales ───────────────────────────────────────────────────────────────────────────────────────
test("Admin Sales: keterangan 'menunggu bayar (dicek Finance)' dari server tampil di rincian baris", async () => {
  const row = { ref_type: "sales_order", ref_id: "so1", number: "KSC/SO-1", title: "Toko A", value: 1000, entity_id: "ent_ksc",
    subtitle: "Bandung · Sari · menunggu bayar (dicek Finance)", action: "Periksa & lepas", action_kind: "verify" };
  mockGet.mockResolvedValue({ data: SO1 });
  await mount(<DeskRowDetail row={row} queue={{ id: "perlu_verifikasi", label: "Perlu diperiksa" }} testPrefix="desk"
    currentUser={{ permissions: { order: ["view"] } }} onClose={() => {}} onAction={() => {}} />);
  expect(teks(q("desk-detail-field-subtitle"))).toContain("menunggu bayar (dicek Finance)");
});

// ─── 4. R15 — komponen bersama ────────────────────────────────────────────────────────────────────────────
describe("R15 — daftar laporan & dialog", () => {
  test("M1: galat 409 Terima menyebut nomor laporan", async () => {
    askConfirm.mockResolvedValue(true);
    mockPost.mockRejectedValue({ response: { status: 409, data: { detail: "Lampirkan bukti bayar dulu" } } });
    await mount(<PayReportList reports={[REPORT]} canDecide onChanged={() => {}} />);
    await klik("pay-report-lb1-terima"); await tunggu();
    expect(teks(q("pay-report-error"))).toMatch(/^.*LB-1.*Lampirkan bukti bayar dulu/);
  });

  test("M2: tanpa bukti Terima mati dengan alasan singkat; Tolak tetap hidup", async () => {
    const tanpa = { ...REPORT, attachments: [], attachment_count: 0 };
    await mount(<PayReportList reports={[tanpa]} canDecide onChanged={() => {}} />);
    expect(q("pay-report-lb1-terima").disabled).toBe(true);
    expect(teks(q("pay-report-lb1-terima-reason"))).toMatch(/bukti/i);
    expect(q("pay-report-lb1-tolak").disabled).toBe(false);
    await klik("pay-report-lb1-terima");
    expect(askConfirm).not.toHaveBeenCalled();
  });

  test("M4: unggah bukti gagal sesudah laporan terbentuk → toast GALAT (destructive), bukan kabar sukses", async () => {
    mockGet.mockImplementation(async (u) => {
      if (u === "/api/payment-methods") return { data: [{ code: "transfer", name: "Transfer Bank", needs_account: "bank", needs_reference: false }] };
      if (u === "/api/bank-accounts/receiving") return { data: [{ id: "acc1", name: "BCA Utama", bank_name: "BCA", account_number: "1", holder_name: "PT" }] };
      return { data: {} };
    });
    mockPost.mockImplementation(async (url) => {
      if (url.endsWith("/payment-reports")) return { data: { ...REPORT, attachments: [] } };
      throw { response: { status: 502, data: { detail: "Gagal mengunggah file" } } };
    });
    const onDone = jest.fn();
    await mount(<LaporBayarDialog order={{ id: "so1", number: "KSC/SO-1", entity_id: "ent_ksc", receiving_account_id: "acc1" }}
      shortfall={600000} onClose={() => {}} onDone={onDone} />);
    await tunggu();
    const sel = q("lapor-bayar-method");
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(sel, "transfer");
      sel.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await tunggu();
    const input = q("lapor-bayar-file");
    await act(async () => {
      Object.defineProperty(input, "files", { value: [new File(["x"], "b.png", { type: "image/png" })], configurable: true });
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await act(async () => { q("lapor-bayar-submit").click(); }); await tunggu();
    expect(onDone).toHaveBeenCalled();
    expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ variant: "destructive",
      description: expect.stringMatching(/Bukti belum terunggah/) }));
    expect(mockToast).not.toHaveBeenCalledWith(expect.objectContaining({ title: "Laporan bayar dibuat", variant: undefined }));
  });

  test("kamera HP: prop camera → input berkas accept image/*,pdf + capture=environment; tanpa prop tidak", async () => {
    mockGet.mockResolvedValue({ data: [] });
    const order = { id: "so1", number: "KSC/SO-1", entity_id: "ent_ksc" };
    await mount(<LaporBayarDialog order={order} shortfall={1} camera onClose={() => {}} onDone={() => {}} />);
    const f = q("lapor-bayar-file");
    expect(f.getAttribute("accept")).toBe("image/*,application/pdf");
    expect(f.getAttribute("capture")).toBe("environment");
  });
});

// ─── 5. R15 M3 — kwitansi tunai bagi non-pemutus pada pesanan tertahan ────────────────────────────────────
describe("M3 — Terima pembayaran (tunai) bagi non-pemutus", () => {
  const SALES = { permissions: { order: ["view"], ar_receipt: ["create"], payment_report: ["create"] } };
  const ORDER = { id: "so1", number: "KSC/SO-1", entity_id: "ent_ksc", status: "approved", customer_id: "c1",
    pay_hold: { since: "2026-11-25T03:00:00Z", due_at: new Date(Date.now() + 2.5 * 86400000).toISOString(), required: 1000000 } };
  const panel = async (user, mode) => {
    routeGet({ mode });
    await mount(<DispatchPaymentGatePanel orderId="so1" initial={GATE} currentUser={user} order={ORDER} customerId="c1" customerName="Toko" />);
    await tunggu();
  };

  test("sales boleh menerima tunai → tombol tampil dan membuka kwitansi KHUSUS TUNAI", async () => {
    await panel(SALES, "kas_langsung");
    expect(q("so-gate-receipt-open")).not.toBeNull();
    await klik("so-gate-receipt-open");
    expect(q("ar-receipt-modal").getAttribute("data-cash-only")).toBe("true");
  });

  test("tunai dilarang untuk sales (pembayaran.sales_terima_tunai = dilarang) → tombol tetap tersembunyi", async () => {
    await panel(SALES, "dilarang");
    expect(q("so-gate-receipt-open")).toBeNull();
  });

  test("pemutus (Finance) → tombol kwitansi penuh, bukan khusus tunai", async () => {
    await panel({ permissions: { ...SALES.permissions, payment_report: ["create", "decide"] } }, "dilarang");
    await klik("so-gate-receipt-open");
    expect(q("ar-receipt-modal").getAttribute("data-cash-only")).toBe("false");
  });
});

// ─── 6. HP ────────────────────────────────────────────────────────────────────────────────────────────────
describe("HP sales", () => {
  const USER = { permissions: { order: ["view"], ar_receipt: ["create"], payment_report: ["create"] } };
  const ORDER = { id: "so1", number: "KSC/SO-1", entity_id: "ent_ksc", status: "approved", customer_id: "c1", customer_name: "Toko A",
    grand_total: 1000000, payment_status: "unpaid", items: [{ product_name: "Katun", quantity: 1, unit: "m", price: 1000000 }],
    receiving_account_id: "acc1", pay_hold: { since: "2026-11-25T03:00:00Z", due_at: new Date(Date.now() + 86400000).toISOString(), required: 1000000 } };

  test("rincian pesanan HP: panel 'Bayar sebelum gudang' + Lapor bayar; dialog memakai kamera", async () => {
    routeGet();
    await mount(<MobileOrders orders={[ORDER]} role="sales" user={USER} focusId="so1" />);
    await tunggu();
    expect(teks(q("m-gate-so1-title"))).toBe("Bayar sebelum gudang");
    await klik("m-gate-so1-lapor-open"); await tunggu();
    expect(q("lapor-bayar-file").getAttribute("capture")).toBe("environment");
    expect(q("lapor-bayar-file").getAttribute("accept")).toBe("image/*,application/pdf");
  });

  test("MobileArReceipt: pesanan tertahan, bukan pemutus, tunai dilarang → pesan pemandu, tanpa formulir kwitansi", async () => {
    routeGet({ mode: "dilarang" });
    await mount(<MobileArReceipt customer={{ id: "c1", name: "Toko A", focus_order_id: "so1" }} order={ORDER} user={USER}
      onClose={() => {}} onDone={() => {}} />);
    await tunggu();
    expect(teks(q("m-ar-receipt-held"))).toContain("Pesanan ini menunggu lapor bayar — pakai Lapor bayar di rincian pesanan");
    expect(q("ar-receipt-modal")).toBeNull();
  });

  test("MobileArReceipt: tertahan tetapi tunai diizinkan → formulir kwitansi khusus tunai", async () => {
    routeGet({ mode: "titipan" });
    await mount(<MobileArReceipt customer={{ id: "c1", name: "Toko A", focus_order_id: "so1" }} order={ORDER} user={USER}
      onClose={() => {}} onDone={() => {}} />);
    await tunggu();
    expect(q("m-ar-receipt-held")).toBeNull();
    expect(q("ar-receipt-modal").getAttribute("data-cash-only")).toBe("true");
  });

  test("MobileArReceipt: pesanan tidak tertahan / pemutus → formulir biasa", async () => {
    routeGet({ mode: "dilarang" });
    await mount(<MobileArReceipt customer={{ id: "c1", name: "Toko A", focus_order_id: "so1" }}
      order={{ ...ORDER, pay_hold: null, status: "confirmed" }} user={USER} onClose={() => {}} onDone={() => {}} />);
    await tunggu();
    expect(q("ar-receipt-modal").getAttribute("data-cash-only")).toBe("false");
    document.body.innerHTML = "";
    await mount(<MobileArReceipt customer={{ id: "c1", name: "Toko A", focus_order_id: "so1" }} order={ORDER}
      user={{ permissions: { payment_report: ["decide"] } }} onClose={() => {}} onDone={() => {}} />);
    await tunggu();
    expect(q("ar-receipt-modal").getAttribute("data-cash-only")).toBe("false");
  });
});

// ─── 7. Notifikasi ────────────────────────────────────────────────────────────────────────────────────────
describe("Notifikasi lapor bayar", () => {
  test("label jenis", () => {
    expect(TYPE_LABEL.lapor_bayar_masuk).toBe("Lapor bayar masuk");
    expect(TYPE_LABEL.lapor_bayar_diterima).toBe("Lapor bayar diterima");
    expect(TYPE_LABEL.lapor_bayar_ditolak).toBe("Lapor bayar ditolak");
    expect(TYPE_LABEL.lapor_bayar_lewat_batas).toBe("Lapor bayar menunggu melewati batas");
    expect(TYPE_LABEL.pay_due_soon).toBe("Batas bayar pesanan segera habis");
    expect(typeLabel("pay_due_soon")).toBe("Batas bayar pesanan segera habis");
  });

  test("tautan `/?view=orders&id=<id>` membuka rincian pesanan (dokumen), bukan layar polos", () => {
    const t = notifDocTarget({ type: "lapor_bayar_masuk", link: "/?view=orders&id=so1" });
    expect(t).toEqual({ link: expect.objectContaining({ view: "orders", nav_id: "sales-orders", focus_type: "sales_order", focus_id: "so1" }) });
    expect(notifDocTarget({ type: "turn", link: "operations" })).toBeNull();
    expect(notifDocTarget({ type: "x", link: "/?view=orders" })).toBeNull();
  });
});

// ─── 8. R16 — satu predikat "tertahan bayar" ───────────────────────────────────────────────────────────────
describe("isHeldForPayment", () => {
  const { isHeldForPayment } = require("../orders/payReport/payReportApi");
  const g = (o = {}) => ({ applies: true, released: null, ...o });
  test("gerbang berlaku + status sebelum gudang + belum dilepas → tertahan (walau penanda belum ada)", () => {
    expect(isHeldForPayment({ status: "approved" }, g())).toBe(true);
    expect(isHeldForPayment({ status: "reserved" }, g())).toBe(true);
    expect(isHeldForPayment({ status: "waiting_stock" }, g())).toBe(true);
  });
  test("pengecualian berizin, gerbang tidak berlaku, sample, atau status sesudah gudang → tidak", () => {
    expect(isHeldForPayment({ status: "approved" }, g({ released: { by: "x" } }))).toBe(false);
    expect(isHeldForPayment({ status: "approved", dispatch_payment_release: { by: "x" } }, g())).toBe(false);
    expect(isHeldForPayment({ status: "approved" }, g({ applies: false }))).toBe(false);
    expect(isHeldForPayment({ status: "approved", order_type: "sample" }, g())).toBe(false);
    expect(isHeldForPayment({ status: "confirmed", pay_hold: {} }, g())).toBe(false);
    expect(isHeldForPayment(null, g())).toBe(false);
  });
  test("tanpa jawaban gerbang: jatuh ke penanda pay_hold / release.waiting=bayar", () => {
    expect(isHeldForPayment({ status: "approved", pay_hold: { since: "x" } })).toBe(true);
    expect(isHeldForPayment({ status: "approved", release: { waiting: "bayar" } }, null)).toBe(true);
    expect(isHeldForPayment({ status: "approved" })).toBe(false);
  });
});

test("MobileArReceipt R16: pesanan approved TANPA penanda tetapi gerbang berlaku → dibatasi (pemandu bila tunai dilarang)", async () => {
  routeGet({ mode: "dilarang" });
  await mount(<MobileArReceipt customer={{ id: "c1", name: "Toko A", focus_order_id: "so1" }}
    order={{ id: "so1", status: "approved", customer_id: "c1" }} user={{ permissions: { payment_report: ["create"] } }}
    onClose={() => {}} onDone={() => {}} />);
  await tunggu();
  expect(q("m-ar-receipt-held")).not.toBeNull();
});
