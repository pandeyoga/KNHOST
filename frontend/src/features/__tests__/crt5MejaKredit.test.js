// CR-T5 — layar daftar kerja "Kredit & Plafon" dan kartu pelanggan (docs/blueprint/unit/CR-T5.md, bagian Layar; U16 =
// uji jalan integrator di peramban). Izin dari `currentUser.permissions` (server), bukan nama peran.
//   (a) enam chip berlabel persis + jumlah dari ringkasan; Finance (credit_profile.view tanpa approve) tanpa "Setujui";
//       Manajer pemutus melihat Setujui/Tolak; pengaju sendiri saat dua orang → tombol mati + alasan tertulis;
//   (b) kosong "Tidak ada pekerjaan di antrean ini."; galat di tempat daftar + "Coba lagi"; "Semua PT" = catatan
//       gabungan hanya-baca dan tombol mati;
//   (c) "Buka kartu pelanggan" membuka kartu pelanggan yang sama (Customer360Panel) di tempat;
//   (d) kartu pelanggan: tab Pesanan · Dokumen · Harga Khusus · Sample · Penagihan · Kredit · Tagihan · Rekening Koran
//       (tanpa "Override Kredit"); "Dijanjikan bayar" memunculkan "Tanggal janji" + "Nominal janji" wajib;
//   (e) kotak Eksposur: baris berlabel persis, "tidak dihitung", denda terpisah; (f) Rekening Koran: kolom, saldo awal &
//       akhir, nomor dokumen membuka Jejak Dokumen.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CreditDeskView from "../finance/CreditDeskView";
import Customer360Panel from "../crm/Customer360Panel";
import CustomerExposureBox from "../crm/CustomerExposureBox";
import CustomerStatementTab from "../crm/CustomerStatementTab";
import { EntityScopeProvider } from "../../context/EntityScopeContext";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange?.(e.target.value)}>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange?.(e.target.value)} />,
}));
jest.mock("../../components/EntityScopeBanner", () => () => <div data-testid="credit-desk-scope" />);
jest.mock("../../components/PaginationBar", () => (p) => <div data-testid={p.testId}>{p.total}</div>);
jest.mock("../crm/CreditOverridesPanel", () => () => <div data-testid="mock-overrides-panel" />);
jest.mock("../crm/CreditProfileRequestsPanel", () => () => <div data-testid="mock-requests-panel" />);
jest.mock("../crm/CustomerCreditTab", () => () => <div data-testid="mock-credit-tab" />);
jest.mock("../crm/CustomerBillingTab", () => ({
  __esModule: true, default: () => <div data-testid="mock-billing-tab" />, CustomerOverrideSection: () => <div data-testid="mock-override-section" />,
}));
jest.mock("../../components/AskKnButton", () => ({ AskKnButton: () => null }));
jest.mock("../../components/AuditHistoryPanel", () => () => null);
jest.mock("../settings/config/ScopedRulesSection", () => () => null);
jest.mock("../crm/CustomerColorsSection", () => () => null);
jest.mock("../crm/CustomerMergeSection", () => () => null);
jest.mock("../crm/CustomerFormModal", () => () => null);
const mockTrace = jest.fn();
jest.mock("../documents/trace/traceDeepLink", () => ({ openTrace: (...a) => mockTrace(...a) }));
const mockConfirm = jest.fn(async () => true);
jest.mock("../../services/confirmService", () => ({
  __esModule: true, askConfirm: (...a) => mockConfirm(...a), askReason: jest.fn(async () => "alasan uji"), REASON_MIN_LENGTH: 5,
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const text = () => document.body.textContent;
const flush = async (n = 8) => { for (let i = 0; i < n; i += 1) await act(async () => {}); };
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push({ root, host });
  await act(async () => { root.render(el); });
  await flush();
}
async function click(el) { await act(async () => { el.click(); }); await flush(); }
async function choose(el, value) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(el, value);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}
beforeEach(() => { mockConfirm.mockImplementation(async () => true); });
afterEach(async () => {
  for (const { root, host } of roots) { await act(async () => { root.unmount(); }); host.remove(); }
  roots = [];
  [mockGet, mockPost, mockConfirm, mockTrace].forEach((m) => m.mockReset());
});

const ENT = [{ id: "ent_kanda", short_name: "Kanda", legal_name: "CV Kanda Suka" }, { id: "ent_ksc", short_name: "KSC" }];
const FIN = { id: "u_fin", role: "finance", permissions: { credit_profile: ["view", "update"], penalty: ["view"], order: ["view"] } };
const MGR = { id: "u_mgr", role: "manager",
  permissions: { credit_profile: ["view", "update", "approve"], credit_override: ["approve"], penalty: ["view", "issue", "waive"],
    order: ["view", "update"], customer: ["view"] } };
const SUMMARY = { menunggu_keputusan: 2, ditahan: 1, jatuh_tempo: 3, janji_bayar: 0, kaji_ulang: 4, denda: 5, combined: false };
const MENUNGGU = { items: [
  { kind: "izin_kredit", id: "cro_1", customer_id: "cus_a", customer_name: "Toko A", entity_id: "ent_kanda",
    amount: 2000000, requested_by: "Ayu", age_days: 10, summary: "PO besar", blocked_reason: "" },
  { kind: "ubah_profil", id: "cpr_1", customer_id: "cus_b", customer_name: "Toko B", entity_id: "ent_kanda",
    amount: 20000000, requested_by: "Mira", age_days: 5, summary: "Plafon kredit: Rp 20.000.000",
    blocked_reason: "Pengaju tidak boleh memutus pengajuannya sendiri." },
], total: 2, page: 1, page_size: 25, combined: false };

function route(map) {
  mockGet.mockImplementation(async (url, cfg) => {
    const key = url.replace("/api", "");
    const hit = map[`${key}?${cfg?.params?.queue || ""}`] ?? map[key];
    if (hit instanceof Error) throw hit;
    return { data: typeof hit === "function" ? hit(cfg) : hit };
  });
}
const desk = (user, entity = "ent_kanda") => (
  <EntityScopeProvider selectedEntity={entity} entities={ENT} canSwitch>
    <CreditDeskView currentUser={user} selectedEntity={entity} />
  </EntityScopeProvider>
);

describe("Kredit & Plafon — enam antrean", () => {
  test("(a) enam chip berlabel persis + jumlah; Finance tanpa Setujui", async () => {
    route({ "/credit-desk/summary": SUMMARY, "/credit-desk?menunggu_keputusan": MENUNGGU });
    await mount(desk(FIN));
    const labels = [...document.querySelectorAll('[data-testid^="credit-desk-chip-"]')].map((b) => b.textContent);
    expect(labels).toEqual(["Menunggu keputusan2", "Ditahan1", "Jatuh tempo3", "Janji bayar0", "Kaji ulang4", "Denda5"]);
    expect(q("credit-desk-row-cro_1")).toBeTruthy();
    expect(q("credit-desk-approve-cro_1")).toBeNull();
    expect(text()).not.toContain("Setujui");
    // tanpa izin memutus: kolom Aksi tidak ditampilkan (bukan tombol mati tanpa alasan)
    expect(q("credit-desk-table-menunggu_keputusan").textContent).not.toContain("Aksi");
  });

  test("(a) Manajer pemutus: Setujui/Tolak; pengaju sendiri → mati + alasan tertulis; keputusan terkirim", async () => {
    route({ "/credit-desk/summary": SUMMARY, "/credit-desk?menunggu_keputusan": MENUNGGU });
    mockPost.mockResolvedValue({ data: {} });
    await mount(desk(MGR));
    expect(q("credit-desk-approve-cro_1").disabled).toBe(false);
    expect(q("credit-desk-approve-cpr_1").disabled).toBe(true);
    expect(q("credit-desk-blocked-cpr_1").textContent).toBe("Pengaju tidak boleh memutus pengajuannya sendiri.");
    await click(q("credit-desk-approve-cro_1"));
    expect(text()).toContain("Toko A · Kanda · Rp");   // konfirmasi menyebut pelanggan, PT, nominal (N5)
  });

  test("(b) kosong, galat + Coba lagi, dan Semua PT hanya-baca", async () => {
    route({ "/credit-desk/summary": { ...SUMMARY, ditahan: 0 }, "/credit-desk?menunggu_keputusan": MENUNGGU,
      "/credit-desk?ditahan": { items: [], total: 0, page: 1, page_size: 25 } });
    await mount(desk(MGR));
    await click(q("credit-desk-chip-ditahan"));
    expect(q("credit-desk-empty").textContent).toBe("Tidak ada pekerjaan di antrean ini.");
    route({ "/credit-desk/summary": SUMMARY, "/credit-desk?jatuh_tempo": new Error("jaringan") });
    await click(q("credit-desk-chip-jatuh_tempo"));
    expect(q("credit-desk-error")).toBeTruthy();
    expect(text()).toContain("Coba lagi");
  });

  test("(b) Semua PT: catatan gabungan belum dieliminasi, tombol putus mati", async () => {
    route({ "/credit-desk/summary": { ...SUMMARY, combined: true },
      "/credit-desk?menunggu_keputusan": { ...MENUNGGU, combined: true } });
    await mount(desk(MGR, "all"));
    expect(q("credit-desk-combined-note").textContent).toContain("gabungan, belum dieliminasi");
    expect(q("credit-desk-approve-cro_1").disabled).toBe(true);
  });

  test("pembaca izin kredit saja (tanpa credit_profile.view): daftar izin kredit, tanpa antrean & tanpa panggilan", async () => {
    route({});
    await mount(desk({ id: "u_x", role: "cr_x", permissions: { credit_override: ["view"] } }));
    expect(q("mock-overrides-panel")).toBeTruthy();
    expect(q("credit-desk-chips")).toBeNull();
    expect(mockGet.mock.calls.filter(([u]) => String(u).includes("/credit-desk"))).toEqual([]);
  });

  test("(c) Buka kartu pelanggan membuka Customer360Panel di tempat", async () => {
    route({ "/credit-desk/summary": SUMMARY, "/credit-desk?menunggu_keputusan": MENUNGGU,
      "/customers/cus_a/360": { id: "cus_a", name: "Toko A", credit: {}, order_history: [], document_history: [],
        special_price_history: [], sample_history: [], collection_followups: [], credit_overrides: [], stats: {} },
      "/customers/cus_a/exposure": { rows: [], penalty: null } });
    await mount(desk(MGR));
    await click(q("credit-desk-open-cro_1"));
    expect(q("customer-360-panel")).toBeTruthy();
    expect(q("customer-360-name").textContent).toBe("Toko A");
  });

  test("Jatuh tempo: Salin pengingat menyalin naskah server; Denda menandai jadwal void", async () => {
    const tulis = jest.fn(async () => {});
    Object.assign(navigator, { clipboard: { writeText: tulis } });
    route({ "/credit-desk/summary": SUMMARY, "/credit-desk?menunggu_keputusan": MENUNGGU,
      "/credit-desk?jatuh_tempo": { items: [{ id: "cus_c:ent_kanda", customer_id: "cus_c", customer_name: "Toko C",
        entity_id: "ent_kanda", line_count: 2, total_outstanding: 400000, max_days_late: 10, next_due_date: "2026-11-22",
        oldest_due_date: "2026-11-10", lines: [] }], total: 1, page: 1, page_size: 25 },
      "/customers/cus_c/reminder-text": { text: "Yth. Toko C,\n…", note: "" },
      "/credit-desk?denda": { items: [{ id: "pnl_1", number: "DN-1", customer_id: "cus_d", customer_name: "Toko D",
        entity_id: "ent_kanda", amount: 25000, status: "draft", plan_void: true }], total: 1, page: 1, page_size: 25 } });
    await mount(desk(MGR));
    await click(q("credit-desk-chip-jatuh_tempo"));
    expect(text()).toContain("Telat 10 hari");
    await click(q("credit-desk-copy-cus_c:ent_kanda"));
    expect(tulis).toHaveBeenCalledWith("Yth. Toko C,\n…");
    expect(q("credit-desk-notice").textContent).toContain("Naskah pengingat Toko C disalin");
    await click(q("credit-desk-chip-denda"));
    expect(q("credit-desk-planvoid-pnl_1")).toBeTruthy();
    expect(q("credit-desk-issue-pnl_1")).toBeTruthy();
    expect(q("credit-desk-waive-pnl_1")).toBeTruthy();
  });
});

const C360 = { id: "cus_p", name: "Toko P", code: "C-01", entity_id: "ent_kanda", credit: { credit_limit: 0 },
  order_history: [], document_history: [], special_price_history: [], sample_history: [], credit_overrides: [],
  collection_followups: [{ id: "cfu_1", note: "janji transfer", outcome: "promised", promise_date: "2026-11-10",
    promise_amount: 500000, promise_status: "ingkar", created_by: "Ayu", created_at: "2026-11-06T03:00:00Z" }],
  stats: {} };

describe("Kartu pelanggan", () => {
  test("(d) tab baru, tanpa Override Kredit; janji bayar berlencana; isian janji wajib", async () => {
    // MN-T3 — kartu pelanggan: bagian dari `sections_allowed` server (enam bagian kartu) + "Kredit" (halaman CRM);
    // tab lama Pesanan · Dokumen · Harga Khusus · Sample menjadi chip di "Riwayat Lain", "Penagihan" = "Tindak Lanjut".
    const SEC = ["ringkasan", "tagihan", "pembayaran", "denda_kasus", "tindak_lanjut", "rekening_koran", "riwayat"];
    route({ "/customers/cus_p/360": { ...C360, sections_allowed: SEC }, "/customers/cus_p/exposure": { rows: [], penalty: null } });
    const user = { ...MGR, permissions: { ...MGR.permissions, payment_plan: ["view"], ar_receipt: ["view"] } };
    await mount(<Customer360Panel customerId="cus_p" currentUser={user} selectedEntity="ent_kanda" />);
    const tabs = [...document.querySelectorAll('[data-testid^="customer-360-tab-"]')].map((b) => b.textContent.replace(/\d+$/, ""));
    expect(tabs).toEqual(["Tagihan & Jadwal", "Pembayaran", "Denda & Kasus", "Tindak Lanjut", "Rekening Koran", "Riwayat Lain",
      "Kredit"]);
    expect(text()).not.toContain("Override Kredit");
    await click(q("customer-360-tab-tindak_lanjut"));
    expect(q("customer-360-promise-status-cfu_1").textContent).toBe("Ingkar");
    expect(q("customer-360-promise-cfu_1").textContent).toContain("Rp");
    await click(q("customer-360-followup"));
    expect(q("followup-promise-fields")).toBeNull();
    await choose(q("followup-outcome"), "promised");
    expect(q("followup-promise-fields").textContent).toContain("Tanggal janji");
    expect(q("followup-promise-fields").textContent).toContain("Nominal janji");
  });

  test("(e) kotak Eksposur: label persis, 'tidak dihitung', denda terpisah", async () => {
    route({ "/customers/cus_p/exposure": {
      entity: { id: "ent_kanda", short_name: "Kanda" }, note: "Pesanan bertermin tunai tidak dihitung dalam eksposur.",
      rows: [
        { key: "terkirim", label: "Piutang barang terkirim", amount: 6000000, counted: true, sign: "+", note: "" },
        { key: "belum_kirim", label: "Pesanan belum dikirim", amount: 2000000, counted: true, sign: "+", note: "" },
        { key: "giro", label: "Giro belum cair", amount: 300000, counted: false, sign: "+", note: "tidak dihitung" },
        { key: "titipan", label: "Titipan & saldo kredit", amount: 500000, counted: false, sign: "-", note: "tidak dihitung" },
        { key: "eksposur", label: "Eksposur", amount: 8000000, counted: true, sign: "=", note: "" },
        { key: "plafon", label: "Plafon", amount: 7000000, counted: true, sign: "", note: "" },
        { key: "sisa", label: "Sisa plafon", amount: -1000000, counted: true, sign: "", note: "" },
      ],
      penalty: { label: "Denda belum dibayar (tidak mengurangi plafon)", amount: 25000 } } });
    await mount(<CustomerExposureBox customerId="cus_p" selectedEntity="ent_kanda" />);
    const labels = [...document.querySelectorAll('[data-testid="customer-exposure-rows"] dt')].map((d) => d.textContent);
    expect(labels).toEqual(["Piutang barang terkirim", "Pesanan belum dikirim", "Giro belum cair", "Titipan & saldo kredit",
      "Eksposur", "Plafon", "Sisa plafon"]);
    expect(q("customer-exposure-giro-note").textContent).toBe("tidak dihitung");
    expect(q("customer-exposure-penalty").textContent).toContain("Denda belum dibayar (tidak mengurangi plafon)");
    expect(q("customer-exposure-sisa").querySelector(".whitespace-nowrap").textContent).toMatch(/^-/);
  });

  test("(f) Rekening Koran: kolom, saldo awal/akhir, nomor dokumen & jurnal membuka Jejak Dokumen", async () => {
    route({ "/customers/cus_p/statement": { customer: { id: "cus_p" }, entity: { id: "ent_kanda", legal_name: "CV Kanda Suka" },
      from: "2026-10-01", to: "2026-10-31", opening_balance: 0, closing_balance: 500000, note: "Titipan dan uang muka ada di kotak Eksposur.",
      rows: [{ date: "2026-10-01", doc_type: "surat_jalan", doc_label: "Surat jalan", doc_number: "SJ-1", doc_id: "shp_1",
        trace_type: "shipment", description: "Pengakuan penjualan", debit: 400000, credit: 0, balance: 400000,
        je_id: "je_1", je_number: "JE-1" }],
      penalties: { opening_balance: 0, rows: [], closing_balance: 0 } } });
    await mount(<CustomerStatementTab customer={{ id: "cus_p", name: "Toko P", entity_id: "ent_kanda" }} currentUser={MGR}
      selectedEntity="ent_kanda" />);
    const heads = [...document.querySelectorAll('[data-testid="customer-statement-table"] th')].map((t) => t.textContent);
    expect(heads).toEqual(["Tanggal", "Dokumen", "Keterangan", "Tagihan", "Pembayaran / Kredit", "Saldo"]);
    expect(q("customer-statement-table-opening").textContent).toContain("Saldo awal");
    expect(q("customer-statement-table-closing").textContent).toContain("Saldo akhir");
    expect(q("customer-statement-show").textContent).toBe("Tampilkan");
    expect(q("customer-statement-copy").textContent).toBe("Salin pengingat");
    await click(q("customer-statement-table-doc-je_1"));
    expect(mockTrace).toHaveBeenCalledWith({ docType: "shipment", docId: "shp_1", number: "SJ-1" });
    await click(q("customer-statement-table-je-je_1"));
    expect(mockTrace).toHaveBeenLastCalledWith({ docType: "journal_entry", docId: "je_1", number: "JE-1" });
    expect(q("customer-statement-penalty-empty").textContent).toBe("Tidak ada denda pada periode ini.");
  });
});
