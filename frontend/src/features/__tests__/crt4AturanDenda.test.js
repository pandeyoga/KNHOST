// CR-T4 (K-30) — layar aturan denda berlapis PT → pelanggan → rencana (docs/blueprint/unit/CR-T4.md, bagian Layar; U17
// diwakili di sini, uji jalan peramban = integrator):
//   (a) kartu P › Kredit: bagian "Aturan denda" menulis tarif 1 % per bulan "khusus pelanggan", unsur lain "ikut PT";
//   (b) pelanggan bebas denda → lencana "Bebas denda s.d. {tanggal}" + alasan; tanpa izin denda → kalimat penjelas;
//   (c) pop-up "Ajukan perubahan": Ikut PT · Khusus · Bebas denda; bebas tanpa alasan/tanggal → "Lengkapi: …"; khusus
//       mengirim `penalty_rule` baku (tarif 1,5 → 1.5, kosong = null);
//   (d) form rencana bayar: bagian lipat "Aturan denda khusus rencana ini" (keterangan "Kosong = mengikuti aturan
//       pelanggan atau PT."), tarif 0,5 ikut dikirim sebagai `penalty`;
//   (e) panel denda: "Aturan dari: PT · pelanggan" per nota; nota dua pelanggan dikelompokkan per pelanggan.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CustomerCreditTab from "../crm/CustomerCreditTab";
import PaymentPlanBuilder from "../finance/payments/PaymentPlanBuilder";
import PenaltyPanel from "../finance/payments/PenaltyPanel";

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
jest.mock("@/components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange?.(e.target.value)} />,
}), { virtual: true });
const mockConfirm = jest.fn(async () => true);
jest.mock("../../services/confirmService", () => ({
  __esModule: true, askConfirm: (...a) => mockConfirm(...a), askReason: jest.fn(async () => "alasan uji"), REASON_MIN_LENGTH: 5,
}));
const mockPreview = jest.fn();
const mockCreate = jest.fn();
jest.mock("../finance/payments/paymentApi", () => ({
  __esModule: true,
  previewPlan: (...a) => mockPreview(...a), createPlan: (...a) => mockCreate(...a), updatePlan: jest.fn(),
  errText: (e, f) => f, money: (n) => `Rp ${Number(n || 0).toLocaleString("id-ID")}`,
  fetchMeta: jest.fn(async () => ({ reasons: [] })), penaltyAccounts: jest.fn(async () => []),
  penaltyMeta: () => ({ label: "Usulan", bg: "transparent", fg: "inherit" }),
  issuePenalty: jest.fn(), waivePenalty: jest.fn(), adjustPenalty: jest.fn(), payPenalty: jest.fn(),
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const flush = async (n = 6) => { for (let i = 0; i < n; i += 1) await act(async () => {}); };
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push({ root, host });
  await act(async () => { root.render(el); });
  await flush();
}
async function type(el, value) {
  const proto = el.tagName === "SELECT" ? HTMLSelectElement.prototype
    : el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
    el.dispatchEvent(new Event(el.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
  });
  await flush();
}
async function click(el) { await act(async () => { el.click(); }); await flush(); }
beforeEach(() => { mockConfirm.mockImplementation(async () => true); });
afterEach(async () => {
  for (const { root, host } of roots) { await act(async () => { root.unmount(); }); host.remove(); }
  roots = [];
  [mockGet, mockPost, mockConfirm, mockPreview, mockCreate].forEach((m) => m.mockReset());
});

const SLS = { id: "u_sls", name: "Ayu", role: "sales",
  permissions: { customer: ["view"], credit_profile: ["view", "update"], penalty: ["view"] } };
const P = { id: "cus_p", name: "Toko Denda P", entity_id: "ent_kanda" };
const ENT = { id: "ent_kanda", short_name: "KANDA", legal_name: "PT Kanda" };
const SRC_GLOBAL = { mode: "global", base: "global", rate_pct_per_month: "global", cap_pct: "global", grace_days: "global",
  min_amount: "global" };

function profil(rule = { mode: "khusus", rate_pct_per_month: 1, cap_pct: null, grace_days: null, base: "", reason: "",
  valid_until: "" }) {
  return {
    customer: { id: P.id, name: P.name, entity_id: "ent_kanda" }, entity: ENT, entity_options: [ENT], profile: { version: 1 },
    effective: { credit_limit: 0, limit_source: "bawaan_pt", limit_mode: "ikut_pt", khusus_credit_limit: null,
      limit_valid_until: "", default_credit_limit: 0, overdue_block_days: 14, block_days_source: "bawaan_pt",
      default_overdue_block_days: 14, warning_ratio: 0.8, allowed_term_codes: [], default_term_code: "",
      credit_status: "normal", status_source: "bawaan_pt", block_reason: "", penalty_rule: rule },
    pending_request: null, history: [], term_options: [], dual_control: { dua_orang: false, batas_nominal: 0 },
  };
}
function kebijakan({ waiver = null, rate = 1, src = { ...SRC_GLOBAL, rate_pct_per_month: "pelanggan" }, mode = "draft" } = {}) {
  return { customer: { id: P.id, name: P.name }, entity_id: "ent_kanda",
    effective: { mode, rate_pct_per_month: rate, base: "installment", cap_pct: 0, grace_days: 0, min_amount: 10000 },
    sources: src, waiver, expired_waiver: null, customer_rule_mode: waiver ? "bebas" : "khusus", rule: null };
}
function rute(prof, pol) {
  mockGet.mockImplementation(async (url) => ({ data: url.endsWith("/penalty-policy") ? pol : prof }));
}

test("CR-T4 U17 (a): Kredit › Aturan denda menulis tarif 1 % 'khusus pelanggan', unsur lain 'ikut PT'", async () => {
  rute(profil(), kebijakan());
  await mount(<CustomerCreditTab customer={P} currentUser={SLS} selectedEntity="ent_kanda" />);
  expect(mockGet).toHaveBeenCalledWith("/api/customers/cus_p/penalty-policy", { params: { entity_id: "ent_kanda" } });
  expect(q("customer-penalty-value-rate").textContent).toBe("1 % per bulan");
  expect(q("customer-penalty-source-rate").textContent).toBe("khusus pelanggan");
  expect(q("customer-penalty-source-grace").textContent).toBe("ikut PT");
  expect(q("customer-penalty-value-base").textContent).toBe("Sisa tagihan yang telat");
  expect(q("customer-penalty-value-min").textContent).toMatch(/Rp\s10\.000/);
  expect(q("customer-penalty-waiver")).toBeNull();
  expect(document.body.textContent).not.toMatch(/installment|pelanggan"|ent_kanda|rate_pct/);   // L1
});

test("CR-T4 (b): bebas denda → lencana 'Bebas denda s.d. …' + alasan; tanpa izin denda → kalimat penjelas", async () => {
  rute(profil({ mode: "bebas", reason: "Kesepakatan direksi", valid_until: "2026-12-31" }),
    kebijakan({ waiver: { reason: "Kesepakatan direksi", valid_until: "2026-12-31" }, mode: "off",
      src: { ...SRC_GLOBAL, mode: "pelanggan" } }));
  await mount(<CustomerCreditTab customer={P} currentUser={SLS} selectedEntity="ent_kanda" />);
  expect(q("customer-penalty-waiver-badge").textContent).toMatch(/^Bebas denda s\.d\. 31 Des 2026$/);
  expect(q("customer-penalty-waiver").textContent).toContain("Kesepakatan direksi");
  expect(q("customer-penalty-waiver-badge").querySelector("svg")).not.toBeNull();   // ikon + teks + warna
  expect(q("customer-penalty-value-mode").textContent).toBe("Tidak ada denda");
  for (const { root, host } of roots) { await act(async () => { root.unmount(); }); host.remove(); }
  roots = [];
  mockGet.mockReset();
  rute(profil(), kebijakan());
  const tanpaDenda = { ...SLS, permissions: { customer: ["view"], credit_profile: ["view"] } };
  await mount(<CustomerCreditTab customer={P} currentUser={tanpaDenda} selectedEntity="ent_kanda" />);
  expect(q("customer-penalty-noaccess").textContent).toContain("pemegang akses melihat denda");
  expect(mockGet.mock.calls.some(([u]) => u.endsWith("/penalty-policy"))).toBe(false);
});

test("CR-T4 (c): pop-up — bebas wajib alasan & tanggal; khusus mengirim penalty_rule baku", async () => {
  rute(profil(null), kebijakan({ rate: 2, src: SRC_GLOBAL }));
  mockPost.mockResolvedValue({ data: { id: "cpr_9" } });
  await mount(<CustomerCreditTab customer={P} currentUser={SLS} selectedEntity="ent_kanda" />);
  await click(q("customer-credit-request"));
  expect(q("credit-request-section-penalty")).not.toBeNull();
  expect([...q("credit-request-penalty-mode").options].map((o) => o.textContent)).toEqual(["Ikut PT", "Khusus", "Bebas denda"]);
  await type(q("credit-request-penalty-mode"), "bebas");
  await type(q("credit-request-reason"), "Kesepakatan dengan pelanggan");
  await click(q("credit-request-submit"));
  expect(q("credit-request-missing").textContent).toContain("alasan bebas denda");
  expect(q("credit-request-missing").textContent).toContain("tanggal berakhir bebas denda");
  expect(mockPost).not.toHaveBeenCalled();
  await type(q("credit-request-penalty-reason"), "Kesepakatan direksi");
  await type(q("credit-request-penalty-until"), "2026-12-31");
  await click(q("credit-request-submit"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  expect(mockPost.mock.calls[0][1].changes).toEqual({
    penalty_rule: { mode: "bebas", reason: "Kesepakatan direksi", valid_until: "2026-12-31" } });

  for (const { root, host } of roots) { await act(async () => { root.unmount(); }); host.remove(); }
  roots = [];
  mockPost.mockReset();
  mockPost.mockResolvedValue({ data: { id: "cpr_10" } });
  rute(profil(null), kebijakan({ rate: 2, src: SRC_GLOBAL }));
  await mount(<CustomerCreditTab customer={P} currentUser={SLS} selectedEntity="ent_kanda" />);
  await click(q("customer-credit-request"));
  await type(q("credit-request-penalty-mode"), "khusus");
  expect(q("credit-request-penalty-hint").textContent).toBe("Kosong = ikut aturan PT.");
  await type(q("credit-request-penalty-rate_pct_per_month"), "101");
  await type(q("credit-request-reason"), "Pelanggan grosir lama");
  await click(q("credit-request-submit"));
  expect(q("credit-request-missing").textContent).toContain("tarif denda");
  await type(q("credit-request-penalty-rate_pct_per_month"), "1,5");
  await type(q("credit-request-penalty-grace_days"), "10");
  await click(q("credit-request-submit"));
  expect(mockPost.mock.calls[0][1].changes).toEqual({
    penalty_rule: { mode: "khusus", rate_pct_per_month: 1.5, cap_pct: null, grace_days: 10, base: "" } });
});

test("CR-T4 (d): form rencana bayar — bagian lipat aturan denda; tarif 0,5 dikirim sebagai penalty", async () => {
  mockPreview.mockResolvedValue({ lines: [{ seq: 1, kind: "installment", label: "Pelunasan", amount: 5000000,
    due_rule: "fixed_date", due_date: "2026-10-01", status: "open", paid_amount: 0 }] });
  mockCreate.mockResolvedValue({ id: "pyp_1" });
  await mount(<PaymentPlanBuilder docId="so_1" total={5000000} />);
  expect(q("ppb-penalty-toggle").textContent).toContain("Aturan denda khusus rencana ini");
  expect(q("ppb-penalty").open).toBe(false);
  expect(q("ppb-penalty-hint").textContent).toBe("Kosong = mengikuti aturan pelanggan atau PT.");
  await type(q("ppb-penalty-rate_pct_per_month"), "0,5");
  await click(q("ppb-save"));
  expect(mockCreate).toHaveBeenCalledTimes(1);
  expect(mockCreate.mock.calls[0][0].penalty).toEqual(
    { mode: "", rate_pct_per_month: 0.5, cap_pct: null, grace_days: null, base: "" });
  for (const { root, host } of roots) { await act(async () => { root.unmount(); }); host.remove(); }
  roots = [];
  await mount(<PaymentPlanBuilder docId="so_1" total={5000000} plan={{ id: "pyp_1", mode: "custom", lines: [],
    penalty: { mode: "", rate_pct_per_month: 0.5, cap_pct: null, grace_days: null, base: "" } }} />);
  expect(q("ppb-penalty").open).toBe(true);                       // rencana beraturan denda sendiri → terbuka
  expect(q("ppb-penalty-rate_pct_per_month").value).toBe("0,5");
});

test("CR-T4 (e): panel denda — 'Aturan dari' per nota; dua pelanggan dikelompokkan", async () => {
  const nota = (id, cid, nama, src, amount) => ({ id, number: `KANDA/DN-DENDA-${id}`, status: "draft", amount, paid_amount: 0,
    customer_id: cid, customer_name: nama, line_label: "Surat jalan SJ-1", due_date: "2026-10-01", days_late: 30,
    billable_days: 30, explain: [], entity_id: "ent_kanda", policy_snapshot: { sources: src } });
  const rows = [
    nota("1", "cus_b", "Toko B", { ...SRC_GLOBAL, rate_pct_per_month: "pelanggan" }, 50000),
    nota("2", "cus_a", "Toko A", { ...SRC_GLOBAL, rate_pct_per_month: "rencana" }, 25000),
    nota("3", "cus_b", "Toko B", SRC_GLOBAL, 100000),
  ];
  await mount(<PenaltyPanel rows={rows} currentUser={{ role: "x", permissions: { penalty: ["view"] } }} />);
  expect(q("penalty-source-1").textContent).toBe("Aturan dari: PT · pelanggan");
  expect(q("penalty-source-2").textContent).toBe("Aturan dari: PT · rencana");
  expect(q("penalty-source-3").textContent).toBe("Aturan dari: PT");
  expect(q("penalty-group-head-0").textContent).toContain("Toko A");
  expect(q("penalty-group-head-1").textContent).toMatch(/Toko B.*2 nota/);
  expect(q("penalty-group-1").querySelectorAll('[data-testid^="penalty-row-"]').length).toBe(2);
  for (const { root, host } of roots) { await act(async () => { root.unmount(); }); host.remove(); }
  roots = [];
  await mount(<PenaltyPanel rows={[rows[0]]} currentUser={{ role: "x", permissions: { penalty: ["view"] } }} />);
  expect(q("penalty-group-head-0")).toBeNull();                   // satu pelanggan → tanpa judul kelompok
});
