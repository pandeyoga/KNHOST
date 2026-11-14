// PK-13 (UX-03, FY-17) — konfirmasi untuk aksi uang sekali klik.
// Tiap tombol (A1–A10) kini bertanya dulu lewat dialog baku (`ConfirmHost` asli, TIDAK ditiru) dengan menyebut nominal
// dan nama lengkap PT. Pola per uji (spesifikasi `docs/blueprint/unit/PK-13.md`, Uji penerimaan):
//   (i)   klik tombol → belum ada panggilan tulis (`axios.post`/`axios.delete`) dan dialog tampil;
//   (ii)  isi `{testId}-message` memuat nominal ("Rp 12.500.000", spasi biasa) dan nama PT, id PT tidak tampil;
//   (iii) Batal → tetap 0 panggilan;
//   (iv)  lanjut → tepat 1 panggilan ke jalur yang benar (tolak/batal: alasan dikirim di `notes`).
// U13 memuat `utils/moneyConfirm` lewat `require` di dalam uji supaya uji lain tetap bisa berjalan pada berkas lama
// (bukti merah: modul itu belum ada sebelum PK-13).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { useAppActions } from "../../hooks/useAppActions";
import VendorBillsView from "../purchasing/VendorBillsView";
import VendorBillDetailPanel from "../purchasing/VendorBillDetailPanel";
import SettlementDetail from "../pettycash/SettlementDetail";
import FixedAssetsView from "../finance/FixedAssetsView";
import BudgetView from "../finance/BudgetView";
import TaxCenterView from "../finance/TaxCenterView";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockDelete = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), delete: (...a) => mockDelete(...a),
    patch: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
// Pemilih bawaan (cmdk/radix) & kalender (radix popover) diganti isian polos — yang diuji dialog konfirmasinya.
jest.mock("../../components/KNSelect", () => {
  const S = (p) => <select data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />;
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />,
  formatDateId: (v) => String(v || ""),
}));
jest.mock("../../components/KNMonthPicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />,
  formatPeriodId: (v) => String(v || ""),
}));
// Komponen berat yang tidak diuji di sini.
jest.mock("../../components/AskKnButton", () => ({ __esModule: true, AskKnButton: () => null }));
jest.mock("../documents/DocumentActionsBar", () => () => null);
jest.mock("../documents/trace/DocRefsPanel", () => () => null);
jest.mock("../purchasing/GrnDocVariance", () => () => null);
jest.mock("../purchasing/VendorBillCreateModal", () => () => null);
// recharts butuh ukuran DOM nyata — di jsdom cukup diganti kotak kosong.
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
/** Pasang layar + `ConfirmHost` di bawah konteks PT (`ent_ksc` terpilih). */
async function mount(el, { selectedEntity = "ent_ksc", entities = ENTS } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(
      <EntityScopeProvider selectedEntity={selectedEntity} entities={entities}>
        {el}
        <ConfirmHost />
      </EntityScopeProvider>);
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
  await act(async () => {
    setter.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
}
/** (ii) — isi pesan: teks penuh + dua bagian tebal [nominal, nama PT]. */
function message(testId) {
  const el = q(`${testId}-message`);
  expect(el).not.toBeNull();
  return { text: el.textContent, strong: [...el.querySelectorAll("strong")].map((s) => s.textContent) };
}
const dialogTitle = (testId) => q(testId)?.querySelector("[role=dialog]")?.getAttribute("aria-label");
const keyOf = (call) => call?.[call.length - 1]?.headers?.["Idempotency-Key"];
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.endsWith(k));
    return Promise.resolve({ data: hit ? map[hit] : [] });
  });
}

beforeEach(() => {
  mockPost.mockResolvedValue({ data: {} });
  mockDelete.mockResolvedValue({ data: {} });
});
afterEach(async () => {
  // Dialog yang masih terbuka (uji gagal di tengah) ditutup supaya antrean confirmService tidak macet untuk uji berikutnya.
  const openCancel = document.body.querySelector(".modal-overlay [data-testid$='-cancel']");
  if (openCancel) await click(openCancel);
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockReset(); mockPost.mockReset(); mockDelete.mockReset();
  document.body.innerHTML = "";
});

// ── Tagihan pemasok (U1–U5) ────────────────────────────────────────────────────────────────────────────────────────
const MGR = { role: "manager", permissions: { vendor_bill: ["view", "approve", "pay"] } };
const billOf = (over = {}) => ({
  id: "vb1", bill_number: "VB-2026-0001", status: "pending_approval", match_status: "matched",
  supplier_name: "CV Benang Jaya", entity_id: "ent_ksc", po_number: "PO-0001", items: [], timeline: [], payments: [],
  grand_total: 12500000, financials: { grand_total: 12500000, outstanding: 12500000, amount_paid: 0 },
  ...over,
});
const mountPanel = (bill, onAction = jest.fn()) => mount(
  <VendorBillDetailPanel bill={bill} canApprove currentUser={MGR} onClose={() => {}} onAction={onAction}
    onError={() => {}} />);

describe("U1 — Tagihan Pemasok, daftar: Setujui (A1)", () => {
  test("bertanya dulu dengan nominal & PT; Batal = 0 POST; lanjut = 1 POST …/approve", async () => {
    const bill = billOf();
    // KP-T4 — tombol Setujui muncul bila server menjawab boleh memutus (Aturan Persetujuan), bukan dari peringkat peran.
    routeGet({ "/vendor-bills": { items: [bill], total: 1, has_more: false }, "/vendor-bills/status-counts": {},
      "/vendor-bills/payables/summary": null, "/purchase-orders": [],
      "/approval-policies/can-decide/me": { allowed: true, code: "", message: "" } });
    mockPost.mockResolvedValue({ data: { ...bill, status: "posted" } });
    await mount(<VendorBillsView currentUser={MGR} selectedEntity="ent_ksc" />);

    await click(q("vb-quick-approve-vb1"));
    expect(mockPost).not.toHaveBeenCalled();                                    // (i)
    expect(q("vb-approve-confirm")).not.toBeNull();
    expect(dialogTitle("vb-approve-confirm")).toBe("Setujui tagihan VB-2026-0001?");
    const m = message("vb-approve-confirm");                                    // (ii)
    expect(m.strong).toEqual(["Rp 12.500.000", "PT Kain Suka Cita"]);
    expect(m.text).toContain("Hutang kepada CV Benang Jaya akan dijurnal");
    expect(m.text).not.toContain("ent_ksc");
    expect(q("vb-approve-confirm-confirm").textContent).toBe("Setujui & Posting");

    await click(q("vb-approve-confirm-cancel"));                                // (iii)
    expect(q("vb-approve-confirm")).toBeNull();
    expect(mockPost).not.toHaveBeenCalled();

    await click(q("vb-quick-approve-vb1"));                                     // (iv)
    await click(q("vb-approve-confirm-confirm"));
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe("/api/vendor-bills/vb1/approve");
    expect(typeof keyOf(mockPost.mock.calls[0])).toBe("string");               // PK-12 tetap utuh
    expect(q("vb-approve-confirm")).toBeNull();
  });

  test("Kirim (submit) tetap langsung tanpa dialog", async () => {
    const bill = billOf({ status: "draft" });
    routeGet({ "/vendor-bills": { items: [bill], total: 1, has_more: false } });
    mockPost.mockResolvedValue({ data: { ...bill, status: "pending_approval" } });
    await mount(<VendorBillsView currentUser={MGR} selectedEntity="ent_ksc" />);
    await click(q("vb-quick-submit-vb1"));
    expect(document.body.querySelector(".modal-overlay")).toBeNull();
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe("/api/vendor-bills/vb1/submit");
  });
});

describe("U2 — Tagihan Pemasok, detail: Setujui & Posting (A2)", () => {
  test("(i)–(iv): pesan memuat Rp 12.500.000 & PT; lanjut = 1 POST …/approve", async () => {
    mockGet.mockResolvedValue({ data: [] });
    mockPost.mockResolvedValue({ data: { ...billOf(), status: "posted" } });
    const onAction = jest.fn();
    await mountPanel(billOf(), onAction);

    await click(q("vb-action-approve"));
    expect(mockPost).not.toHaveBeenCalled();
    expect(q("vb-approve-confirm")).not.toBeNull();
    const m = message("vb-approve-confirm");
    expect(m.strong).toEqual(["Rp 12.500.000", "PT Kain Suka Cita"]);
    expect(m.text).toContain("hanya bisa dibatalkan dengan jurnal pembalik");

    await click(q("vb-approve-confirm-cancel"));
    expect(mockPost).not.toHaveBeenCalled();
    expect(onAction).not.toHaveBeenCalled();

    await click(q("vb-action-approve"));
    await click(q("vb-approve-confirm-confirm"));
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe("/api/vendor-bills/vb1/approve");
    expect(onAction).toHaveBeenCalledWith("approve", expect.objectContaining({ id: "vb1" }));
  });
});

describe("U3 — Tagihan Pemasok, detail: Tolak (A3)", () => {
  test("alasan wajib ≥ 5 huruf; 'abc' = tombol lanjut mati; alasan dikirim di notes", async () => {
    mockGet.mockResolvedValue({ data: [] });
    mockPost.mockResolvedValue({ data: { ...billOf(), status: "cancelled" } });
    await mountPanel(billOf());

    await click(q("vb-action-reject"));
    expect(mockPost).not.toHaveBeenCalled();                                    // (i)
    expect(q("vb-reject-confirm")).not.toBeNull();
    expect(dialogTitle("vb-reject-confirm")).toBe("Tolak tagihan VB-2026-0001?");
    const m = message("vb-reject-confirm");                                     // (ii)
    expect(m.strong).toEqual(["Rp 12.500.000", "PT Kain Suka Cita"]);
    expect(m.text).toContain("Tagihan dari CV Benang Jaya ditolak dan tidak dijurnal.");
    expect(q("vb-reject-confirm-confirm").textContent).toBe("Tolak Tagihan");
    expect(q("vb-reject-confirm-confirm").className).toContain("btn-danger");
    await click(q("vb-reject-confirm-cancel"));                                 // (iii)
    expect(mockPost).not.toHaveBeenCalled();

    await click(q("vb-action-reject"));
    await type(q("vb-reject-confirm-reason"), "abc");
    expect(q("vb-reject-confirm-confirm").disabled).toBe(true);                 // kurang dari 5 huruf
    await click(q("vb-reject-confirm-confirm"));
    expect(mockPost).not.toHaveBeenCalled();
    expect(q("vb-reject-confirm")).not.toBeNull();

    await type(q("vb-reject-confirm-reason"), "harga tidak sesuai PO");
    expect(q("vb-reject-confirm-confirm").disabled).toBe(false);
    await click(q("vb-reject-confirm-confirm"));                                // (iv)
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe("/api/vendor-bills/vb1/reject");
    expect(mockPost.mock.calls[0][1]).toEqual({ notes: "harga tidak sesuai PO" });
  });
});

describe("U4/U5 — Tagihan Pemasok, detail: Batalkan (A4)", () => {
  test("U4 draf 3.000.000: alasan → notes; pesan tidak menyebut jurnal", async () => {
    mockGet.mockResolvedValue({ data: [] });
    const bill = billOf({ status: "draft", grand_total: 3000000,
      financials: { grand_total: 3000000, outstanding: 3000000, amount_paid: 0 } });
    mockPost.mockResolvedValue({ data: { ...bill, status: "cancelled" } });
    await mountPanel(bill);

    await click(q("vb-action-cancel"));
    expect(mockPost).not.toHaveBeenCalled();
    expect(q("vb-cancel-confirm")).not.toBeNull();
    const m = message("vb-cancel-confirm");
    expect(m.strong).toEqual(["Rp 3.000.000", "PT Kain Suka Cita"]);
    expect(m.text).toContain("Tagihan dari CV Benang Jaya dibatalkan.");
    expect(m.text.toLowerCase()).not.toContain("jurnal");
    expect(q("vb-cancel-confirm-confirm").disabled).toBe(true);                 // alasan kosong → mati
    await click(q("vb-cancel-confirm-cancel"));
    expect(mockPost).not.toHaveBeenCalled();

    await click(q("vb-action-cancel"));
    await type(q("vb-cancel-confirm-reason"), "salah input pemasok");
    await click(q("vb-cancel-confirm-confirm"));
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe("/api/vendor-bills/vb1/cancel");
    expect(mockPost.mock.calls[0][1]).toEqual({ notes: "salah input pemasok" });
  });

  test("U5 terposting 3.000.000 (bukan makloon): pesan 'jurnal hutangnya dibalik', alasan wajib", async () => {
    mockGet.mockResolvedValue({ data: [] });
    const bill = billOf({ status: "posted", bill_type: "goods", grand_total: 3000000,
      financials: { grand_total: 3000000, outstanding: 3000000, amount_paid: 0 } });
    mockPost.mockResolvedValue({ data: { ...bill, status: "cancelled" } });
    await mountPanel(bill);

    await click(q("vb-action-cancel-posted"));
    expect(mockPost).not.toHaveBeenCalled();
    const m = message("vb-cancel-confirm");
    expect(m.text).toContain("jurnal hutangnya dibalik");
    expect(m.strong).toEqual(["Rp 3.000.000", "PT Kain Suka Cita"]);
    expect(q("vb-cancel-confirm-reason")).not.toBeNull();
    expect(q("vb-cancel-confirm-confirm").disabled).toBe(true);
    await click(q("vb-cancel-confirm-confirm"));
    expect(mockPost).not.toHaveBeenCalled();
    await click(q("vb-cancel-confirm-cancel"));
    expect(mockPost).not.toHaveBeenCalled();

    await click(q("vb-action-cancel-posted"));
    await type(q("vb-cancel-confirm-reason"), "tagihan ganda dari pemasok");
    await click(q("vb-cancel-confirm-confirm"));
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe("/api/vendor-bills/vb1/cancel");
    expect(mockPost.mock.calls[0][1]).toEqual({ notes: "tagihan ganda dari pemasok" });
  });
});

// ── Kartu notifikasi (U6–U7): `approveFromNotification` lewat komponen pembungkus kecil ─────────────────────────────
function actionState(setNotice) {
  const f = () => jest.fn();
  return {
    user: null, token: "t", auditFilters: {}, selectedCustomer: null, selectedAddress: "", cart: [], data: {},
    selectedEntity: "ent_ksc", entities: ENTS,
    setUser: f(), setToken: f(), setActiveView: f(), setNotice, setOnboarding: f(), setShowOnboarding: f(),
    setData: f(), setTemplates: f(), setUoms: f(), setMovements: f(), setTasks: f(), setUsers: f(), setPermissions: f(),
    setAuditLogs: f(), setSelectedCustomer: f(), setSelectedAddress: f(), setSelectedProduct: f(), setBreakdown: f(),
    setCart: f(), setLastDocument: f(), setLastLabel: f(), setPreviewHtml: f(), setActiveDetail: f(), setLoading: f(),
    setEntities: f(), setNotifications: f(), setUnreadCount: f(), setNotifMeta: f(), setSettings: f(),
    setPaymentTerms: f(), setEntityContext: f(), setSelectedEntity: f(), setActiveNavId: f(), setLocationChoice: f(),
  };
}
function Harness({ state, onActions }) { onActions(useAppActions(state)); return null; }
const NOTIF = { id: "n1", action_type: "vendor_bill_approve", action_id: "vb9" };
const approvePosts = () => mockPost.mock.calls.filter((c) => /\/vendor-bills\/vb9\/approve$/.test(c[0]));

describe("U6/U7 — Kartu notifikasi: Setujui tagihan kampanye (A5)", () => {
  test("U6: GET tagihan dulu lalu tanya; Batal = 0 POST; lanjut = 1 POST …/approve; pesan Rp 8.000.000", async () => {
    routeGet({ "/vendor-bills/vb9": billOf({ id: "vb9", bill_number: "VB-2026-0009", supplier_name: "CV Iklan Kita",
      grand_total: 8000000, financials: { grand_total: 8000000, outstanding: 8000000 } }) });
    mockPost.mockResolvedValue({ data: { id: "vb9", bill_number: "VB-2026-0009", status: "posted" } });
    const setNotice = jest.fn();
    let actions;
    await mount(<Harness state={actionState(setNotice)} onActions={(a) => { actions = a; }} />);

    let p1;
    await act(async () => { p1 = actions.approveFromNotification(NOTIF); });
    await flush();
    expect(mockGet).toHaveBeenCalledWith("/api/vendor-bills/vb9");
    expect(approvePosts()).toHaveLength(0);                                     // (i)
    expect(q("vb-approve-confirm")).not.toBeNull();
    const m = message("vb-approve-confirm");                                    // (ii)
    expect(m.strong).toEqual(["Rp 8.000.000", "PT Kain Suka Cita"]);
    expect(m.text).toContain("CV Iklan Kita");
    await click(q("vb-approve-confirm-cancel"));                                // (iii)
    await expect(p1).resolves.toBeNull();
    expect(approvePosts()).toHaveLength(0);

    let p2;
    await act(async () => { p2 = actions.approveFromNotification(NOTIF); });
    await flush();
    await click(q("vb-approve-confirm-confirm"));                               // (iv)
    await expect(p2).resolves.toEqual(expect.objectContaining({ id: "vb9" }));
    expect(approvePosts()).toHaveLength(1);
    expect(setNotice).toHaveBeenCalledWith(expect.stringContaining("VB-2026-0009 disetujui"));
  });

  test("U7: GET gagal 500 → 0 POST, pesan galat, dialog tidak muncul", async () => {
    mockGet.mockImplementation((url) => (url.endsWith("/vendor-bills/vb9")
      ? Promise.reject({ response: { status: 500, data: "Internal Server Error" } })
      : Promise.resolve({ data: [] })));
    const setNotice = jest.fn();
    let actions;
    await mount(<Harness state={actionState(setNotice)} onActions={(a) => { actions = a; }} />);

    let p;
    await act(async () => { p = actions.approveFromNotification(NOTIF); });
    await flush();
    await expect(p).resolves.toBeNull();
    expect(approvePosts()).toHaveLength(0);
    expect(mockPost).not.toHaveBeenCalled();
    expect(q("vb-approve-confirm")).toBeNull();
    expect(document.body.querySelector(".modal-overlay")).toBeNull();
    expect(setNotice).toHaveBeenCalledWith("Gagal memuat tagihan — tagihan belum disetujui.");
  });
});

// ── Kas Kecil › LPJ (U8–U9) ─────────────────────────────────────────────────────────────────────────────────────────
const stlOf = (over = {}) => ({
  id: "stl1", number: "LPJ-2026-0001", status: "submitted", entity_id: "ent_ksc", dibuat_oleh: "Sari",
  total_pengeluaran: 1750000, total_pettycash: 2000000, sisa_kurang_dana: 250000, expense_lines: [], ...over,
});
const mountStl = (stl, user, onChanged = jest.fn()) => mount(
  <SettlementDetail stl={stl} currentUser={user} entities={ENTS} catLabels={{}} onChanged={onChanged}
    flash={() => {}} />);

describe("U8/U9 — LPJ: Setujui & Posting GL (A6) dan Bayar Reimburse (A7)", () => {
  test("U8: pesan Rp 1.750.000 & PT; lanjut = 1 POST /cash-advance-settlements/{id}/approve", async () => {
    mockPost.mockResolvedValue({ data: { ...stlOf(), status: "approved" } });
    const onChanged = jest.fn();
    await mountStl(stlOf(), { role: "manager", permissions: { cash_settlement: ["approve"] } }, onChanged);

    await click(q("stl-approve-btn"));
    expect(mockPost).not.toHaveBeenCalled();
    expect(q("stl-approve-confirm")).not.toBeNull();
    expect(dialogTitle("stl-approve-confirm")).toBe("Setujui dan posting LPJ-2026-0001?");
    const m = message("stl-approve-confirm");
    expect(m.strong).toEqual(["Rp 1.750.000", "PT Kain Suka Cita"]);
    expect(m.text).toContain("Pengeluaran dijurnal ke beban");
    await click(q("stl-approve-confirm-cancel"));
    expect(mockPost).not.toHaveBeenCalled();

    await click(q("stl-approve-btn"));
    await click(q("stl-approve-confirm-confirm"));
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe("/api/cash-advance-settlements/stl1/approve");
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  test("U9: pesan Rp 250.000; lanjut = 1 POST …/pay-reimburse berisi cash_type kas_besar", async () => {
    const stl = stlOf({ status: "approved", sisa_kurang_dana: -250000, hutang_reimburse: { status: "open", amount: 250000 } });
    mockPost.mockResolvedValue({ data: { ...stl, hutang_reimburse: { status: "paid", amount: 250000 } } });
    await mountStl(stl, { role: "finance", permissions: { accounting: ["create"] } });

    await click(q("stl-pay-reimburse-btn"));
    expect(mockPost).not.toHaveBeenCalled();
    expect(q("stl-reimburse-confirm")).not.toBeNull();
    const m = message("stl-reimburse-confirm");
    expect(m.strong).toEqual(["Rp 250.000", "PT Kain Suka Cita"]);
    expect(m.text).toContain("Kas keluar untuk melunasi kelebihan pengeluaran Sari");
    await click(q("stl-reimburse-confirm-cancel"));
    expect(mockPost).not.toHaveBeenCalled();

    await click(q("stl-pay-reimburse-btn"));
    await click(q("stl-reimburse-confirm-confirm"));
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe("/api/cash-advance-settlements/stl1/pay-reimburse");
    expect(mockPost.mock.calls[0][1]).toEqual({ cash_type: "kas_besar" });
  });
});

// ── Aset Tetap (U10) ─────────────────────────────────────────────────────────────────────────────────────────────────
describe("U10 — Aset Tetap: Catat pembayaran pindah aset (A8)", () => {
  test("pesan Rp 40.000.000 & PT penerima (ent_kanda); lanjut = 1 POST /fixed-assets/{id}/transfer/settle", async () => {
    const asset = { id: "fa1", number: "AST-0001", name: "Mesin Tenun", category: "Mesin", status: "transferred",
      entity_id: "ent_ksc", acquisition_date: "2025-01-10", useful_life_months: 60, acquisition_cost: 50000000,
      accumulated_depreciation: 10000000, book_value: 40000000,
      transfer: { price: 40000000, to_entity_id: "ent_kanda", from_entity_id: "ent_ksc", settled: false,
        new_asset_number: "AST-K-0001", transfer_date: "2026-11-01" } };
    routeGet({ "/fixed-assets": [asset], "/fixed-assets/summary": { count: 1, transferred: 1 }, "/fixed-assets/meta": {} });
    mockPost.mockResolvedValue({ data: { paid: 40000000, cash: [] } });
    await mount(<FixedAssetsView selectedEntity="ent_ksc" entities={ENTS} />);

    await click(q("settle-transfer-fa1"));
    expect(mockPost).not.toHaveBeenCalled();
    expect(q("asset-settle-confirm")).not.toBeNull();
    expect(dialogTitle("asset-settle-confirm")).toBe("Catat pembayaran pindah aset AST-0001?");
    const m = message("asset-settle-confirm");
    expect(m.strong).toEqual(["Rp 40.000.000", "CV Kanda Suka"]);
    expect(m.text).toContain("Kas keluar dari CV Kanda Suka dan masuk ke PT Kain Suka Cita");
    expect(m.text).not.toMatch(/ent_(kanda|ksc)/);
    await click(q("asset-settle-confirm-cancel"));
    expect(mockPost).not.toHaveBeenCalled();

    await click(q("settle-transfer-fa1"));
    await click(q("asset-settle-confirm-confirm"));
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe("/api/fixed-assets/fa1/transfer/settle");
  });
});

// ── Anggaran (U11) ───────────────────────────────────────────────────────────────────────────────────────────────────
describe("U11 — Anggaran: hapus baris (A9)", () => {
  test("pesan Rp 5.000.000 & PT terpilih; lanjut = 1 DELETE /finance/budgets/{id}", async () => {
    const row = { id: "bud1", dimension: "account", key: "6-1000", label: "Beban Sewa", budget: 5000000, committed: 0,
      actual: 0, remaining: 5000000, status: "ok", used_pct: 0 };
    routeGet({ "/finance/budget-vs-actual": { totals: {}, rows: [row] }, "/finance/budget-rules": null,
      "/finance/budget-keys": { accounts: [], categories: [] } });
    await mount(<BudgetView selectedEntity="ent_ksc" currentUser={{ role: "admin", permissions: { budget: ["*"] } }} />);

    await click(q("budget-delete-6-1000"));
    expect(mockDelete).not.toHaveBeenCalled();
    expect(q("budget-delete-confirm")).not.toBeNull();
    expect(dialogTitle("budget-delete-confirm")).toBe("Hapus anggaran Beban Sewa?");
    const m = message("budget-delete-confirm");
    expect(m.strong).toEqual(["Rp 5.000.000", "PT Kain Suka Cita"]);
    expect(q("budget-delete-confirm-confirm").className).toContain("btn-danger");
    await click(q("budget-delete-confirm-cancel"));
    expect(mockDelete).not.toHaveBeenCalled();

    await click(q("budget-delete-6-1000"));
    await click(q("budget-delete-confirm-confirm"));
    expect(mockDelete).toHaveBeenCalledTimes(1);
    expect(mockDelete.mock.calls[0][0]).toBe("/api/finance/budgets/bud1");
  });
});

// ── Pusat Pajak (U12) ────────────────────────────────────────────────────────────────────────────────────────────────
const PPH_REC = { id: "rec1", name: "PPh 23 Jasa", dpp: 10000000, rate: 2, amount: 200000, note: "" };
async function mountTaxPph() {
  routeGet({
    "/tax/summary": { period: "2026-10", periods: ["2026-10"], config: { is_pkp: true }, entity: {},
      ppn: { keluaran: {}, masukan: {}, masukan_by_supplier: [] }, pph: { items: [], total: 0 } },
    "/tax/pph-records": [PPH_REC],
  });
  await mount(<TaxCenterView currentUser={{ role: "manager", permissions: { accounting: ["view", "manage"] } }}
    selectedEntity="ent_ksc" />);
  await click(q("tax-tab-pph"));
  expect(q("tax-pph-rec-rec1")).not.toBeNull();
}

describe("U12 — Pusat Pajak: hapus rekaman PPh (A10)", () => {
  test("pesan Rp 200.000 (= 10.000.000 × 2 %) & PT; lanjut = 1 DELETE /tax/pph-records/{id}", async () => {
    await mountTaxPph();
    await click(q("tax-pph-rec-del-rec1"));
    expect(mockDelete).not.toHaveBeenCalled();
    expect(q("pph-delete-confirm")).not.toBeNull();
    expect(dialogTitle("pph-delete-confirm")).toBe("Hapus rekaman PPh 23 Jasa?");
    const m = message("pph-delete-confirm");
    expect(m.strong).toEqual(["Rp 200.000", "PT Kain Suka Cita"]);
    expect(m.text).toContain("Rekaman DPP masa Okt 2026 dihapus dari rekap pajak.");
    await click(q("pph-delete-confirm-cancel"));
    expect(mockDelete).not.toHaveBeenCalled();

    await click(q("tax-pph-rec-del-rec1"));
    await click(q("pph-delete-confirm-confirm"));
    expect(mockDelete).toHaveBeenCalledTimes(1);
    expect(mockDelete.mock.calls[0][0]).toBe("/api/tax/pph-records/rec1");
    expect(typeof keyOf(mockDelete.mock.calls[0])).toBe("string");             // PK-12 tetap utuh
  });

  test("DELETE gagal 403 → tax-pph-rec-error tampil, baris tetap", async () => {
    await mountTaxPph();
    mockDelete.mockRejectedValue({ response: { status: 403, data: { detail: "Anda tidak berizin menghapus rekaman PPh." } } });
    await click(q("tax-pph-rec-del-rec1"));
    expect(mockDelete).not.toHaveBeenCalled();
    await click(q("pph-delete-confirm-confirm"));
    expect(mockDelete).toHaveBeenCalledTimes(1);
    expect(q("tax-pph-rec-error")).not.toBeNull();
    expect(q("tax-pph-rec-error").textContent).toContain("Anda tidak berizin menghapus rekaman PPh.");
    expect(q("tax-pph-rec-rec1")).not.toBeNull();
  });
});

// ── moneyConfirm (U13) ───────────────────────────────────────────────────────────────────────────────────────────────
describe("U13 — confirmMoney tanpa daftar PT", () => {
  test("entities kosong → pesan memuat 'Entitas aktif', tidak memuat 'ent_ksc'; Batal = false, lanjut = true", async () => {
    const { confirmMoney, rupiahText } = require("../../utils/moneyConfirm");
    expect(rupiahText(12500000)).toBe("Rp 12.500.000");
    expect(rupiahText(-250000)).toBe("-Rp 250.000");
    await mount(<div />, { entities: [] });
    const ask = () => confirmMoney({ title: "Uji?", effect: "Efek uji.", amount: 12500000, entityId: "ent_ksc",
      entities: [], confirmLabel: "Lanjut", testId: "u13-confirm" });

    let p;
    await act(async () => { p = ask(); });
    await flush();
    const m = message("u13-confirm");
    expect(m.text).toContain("Entitas aktif");
    expect(m.text).not.toContain("ent_ksc");
    expect(m.strong).toEqual(["Rp 12.500.000", "Entitas aktif"]);
    await click(q("u13-confirm-cancel"));
    await expect(p).resolves.toBe(false);

    await act(async () => { p = ask(); });
    await flush();
    await click(q("u13-confirm-confirm"));
    await expect(p).resolves.toBe(true);
  });
});
