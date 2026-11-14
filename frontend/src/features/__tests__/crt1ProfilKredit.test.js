// CR-T1 (K-27–K-29) — layar profil kredit (spesifikasi docs/blueprint/unit/CR-T1.md, bagian Layar; U17 diwakili di
// sini dengan izin dari server `currentUser.permissions`; uji jalan peramban = integrator).
//   (a) Sales membuka kartu P1 › Kredit: plafon Rp 50.000.000 bertanda "khusus", tombol "Ajukan perubahan", TANPA
//       Setujui/Tolak; baris lain "ikut PT"; riwayat; termin bertanda "belum dipakai";
//   (b) pengajuan terbuka: "Ajukan perubahan" mati + alasan tertulis; Sales pengaju melihat "Batalkan pengajuan" saja;
//   (c) plafon kedaluwarsa → kalimat "Plafon khusus berakhir … — sekarang memakai bawaan PT";
//   (d) pop-up: hanya isian yang BERUBAH dikirim (+ alasan); "Ajukan & setujui" hanya untuk pemutus bila aturan satu orang;
//   (e) Manajer membuka Kredit & Plafon: antrean pengajuan + tombol putus; pengaju sendiri saat dua orang → mati + alasan;
//   (f) memuat / galat dibedakan.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CustomerCreditTab from "../crm/CustomerCreditTab";
import CreditProfileRequestsPanel from "../crm/CreditProfileRequestsPanel";

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
const mockConfirm = jest.fn(async () => true);
jest.mock("../../services/confirmService", () => ({
  __esModule: true, askConfirm: (...a) => mockConfirm(...a), askReason: jest.fn(async () => "alasan uji"), REASON_MIN_LENGTH: 5,
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
// CRA `resetMocks: true` mengosongkan implementasi tiruan sebelum tiap uji → dipasang ulang di sini.
beforeEach(() => { mockConfirm.mockImplementation(async () => true); });
afterEach(async () => {
  for (const { root, host } of roots) { await act(async () => { root.unmount(); }); host.remove(); }
  roots = [];
  [mockGet, mockPost, mockConfirm].forEach((m) => m.mockReset());
});

const SLS = { id: "u_sls", name: "Ayu", role: "sales", permissions: { customer: ["view"], credit_profile: ["view", "update"] } };
const MGR = { id: "u_mgr", name: "Mira", role: "manager", permissions: { customer: ["view"], credit_profile: ["view", "update", "approve"] } };
const P1 = { id: "cus_p1", name: "Toko Kredit Satu", entity_id: "ent_ksc" };
const ENT = { id: "ent_ksc", short_name: "KSC", legal_name: "PT Kain Suka Cita" };

// Profil sesudah U4: plafon khusus 50 jt, hari blokir ikut PT 14 hari, satu riwayat disetujui.
function profil({ pending = null, eff = {}, dual = { dua_orang: false, batas_nominal: 0 } } = {}) {
  return {
    customer: { id: P1.id, name: P1.name, entity_id: "ent_ksc" }, entity: ENT, entity_options: [ENT],
    profile: { version: 1 },
    effective: { credit_limit: 50000000, limit_source: "khusus", limit_mode: "khusus", khusus_credit_limit: 50000000,
      limit_valid_until: "", default_credit_limit: 0, overdue_block_days: 14, block_days_source: "bawaan_pt",
      default_overdue_block_days: 14, warning_ratio: 0.8, allowed_term_codes: [], default_term_code: "",
      credit_status: "normal", status_source: "bawaan_pt", block_reason: "", ...eff },
    pending_request: pending,
    history: [{ id: "cpr_1", number: "KSC/PKR-00001", status: "disetujui", requested_by: "Ayu", decided_by: "Mira",
      decided_at: "2026-11-14T03:00:00Z", reason: "Naik kelas grosir", decision_note: "",
      changes: [{ field: "credit_limit", from: null, to: 50000000 }] }],
    term_options: [{ code: "NET30", name: "Tempo 30 hari" }, { code: "CBD", name: "Bayar di muka" }],
    dual_control: dual,
  };
}
const PENDING = { id: "cpr_2", number: "KSC/PKR-00002", status: "diajukan", requested_by: "Ayu", requested_by_id: "u_sls",
  created_at: "2026-11-14T04:00:00Z", reason: "Plafon naik", customer_name: P1.name, entity_id: "ent_ksc",
  changes: [{ field: "credit_limit", from: 50000000, to: 60000000 }], blocked_reason: "" };

test("CR-T1 U17 (sales): plafon 50 jt 'khusus', Ajukan perubahan, tanpa Setujui; riwayat; termin belum dipakai", async () => {
  mockGet.mockResolvedValue({ data: profil() });
  await mount(<CustomerCreditTab customer={P1} currentUser={SLS} selectedEntity="ent_ksc" />);
  expect(mockGet).toHaveBeenCalledWith("/api/customers/cus_p1/credit-profile", { params: { entity_id: "ent_ksc" } });
  expect(q("customer-credit-scope").textContent).toContain("PT Kain Suka Cita");
  expect(q("customer-credit-value-limit").textContent).toMatch(/Rp\s50\.000\.000/);
  expect(q("customer-credit-source-limit").textContent).toBe("khusus");
  expect(q("customer-credit-source-block-days").textContent).toBe("ikut PT");
  expect(q("customer-credit-value-block-days").textContent).toBe("14 hari");
  expect(q("customer-credit-row-terms").textContent).toContain("belum dipakai saat pesanan dibuat");
  expect(q("customer-credit-request")).not.toBeNull();
  expect(q("customer-credit-request").disabled).toBe(false);
  expect(q("customer-credit-approve")).toBeNull();
  expect(q("customer-credit-reject")).toBeNull();
  expect(q("customer-credit-history").textContent).toMatch(/Rp\s50\.000\.000/);
  expect(q("customer-credit-history").textContent).toContain("Disetujui");
  expect(document.body.textContent).not.toMatch(/ent_ksc|credit_limit|limit_mode/);   // L1 — tanpa id/isian teknis
});

test("CR-T1 (pengajuan terbuka): tombol ajukan mati + alasan; pengaju Sales hanya bisa membatalkan", async () => {
  mockGet.mockResolvedValue({ data: profil({ pending: PENDING }) });
  await mount(<CustomerCreditTab customer={P1} currentUser={SLS} selectedEntity="ent_ksc" />);
  expect(q("customer-credit-request").disabled).toBe(true);
  expect(q("customer-credit-request-why").textContent).toContain("Masih ada pengajuan yang menunggu keputusan");
  expect(q("customer-credit-pending-changes").textContent).toMatch(/Plafon kredit: Rp\s50\.000\.000 → Rp\s60\.000\.000/);
  expect(q("customer-credit-pending-status").textContent).toBe("Menunggu keputusan");
  expect(q("customer-credit-approve")).toBeNull();
  expect(q("customer-credit-cancel")).not.toBeNull();
});

test("CR-T1 (manajer, dua orang): pengaju sendiri → Setujui/Tolak mati + alasan tertulis; orang lain → konfirmasi + putus", async () => {
  mockGet.mockResolvedValue({ data: profil({ pending: { ...PENDING, requested_by_id: "u_mgr", blocked_reason: "harus orang lain" } }) });
  await mount(<CustomerCreditTab customer={P1} currentUser={MGR} selectedEntity="ent_ksc" />);
  expect(q("customer-credit-approve").disabled).toBe(true);
  expect(q("customer-credit-blocked").textContent).toContain("rekan lain yang memutus");
  for (const { root, host } of roots) { await act(async () => { root.unmount(); }); host.remove(); }
  roots = [];
  mockGet.mockResolvedValue({ data: profil({ pending: PENDING }) });
  mockPost.mockResolvedValue({ data: { request: { ...PENDING, status: "disetujui" } } });
  await mount(<CustomerCreditTab customer={P1} currentUser={MGR} selectedEntity="ent_ksc" />);
  await click(q("customer-credit-approve"));
  expect(mockConfirm).toHaveBeenCalledTimes(1);
  const msg = mockConfirm.mock.calls[0][0].message;
  const host = document.createElement("div");
  const r = createRoot(host);
  await act(async () => { r.render(<div>{msg}</div>); });
  expect(host.textContent).toContain("Toko Kredit Satu");
  expect(host.textContent).toContain("KSC");
  expect(host.textContent).toMatch(/Plafon baru: Rp\s60\.000\.000/);
  await act(async () => { r.unmount(); });
  const [url, body, cfg] = mockPost.mock.calls[0];
  expect(url).toBe("/api/credit-profile-requests/cpr_2/decision");
  expect(body).toEqual({ decision: "approve", note: "" });
  expect(cfg.headers["Idempotency-Key"]).toBeTruthy();
  expect(q("customer-credit-notice").textContent).toContain("disetujui");
});

test("CR-T1 (kedaluwarsa): kalimat plafon khusus berakhir", async () => {
  mockGet.mockResolvedValue({ data: profil({ eff: { credit_limit: 0, limit_source: "kedaluwarsa", limit_valid_until: "2026-11-13" } }) });
  await mount(<CustomerCreditTab customer={P1} currentUser={SLS} selectedEntity="ent_ksc" />);
  expect(q("customer-credit-expired").textContent).toMatch(/Plafon khusus berakhir .* — sekarang memakai bawaan PT\./);
  expect(q("customer-credit-source-limit").textContent).toBe("ikut PT");
});

test("CR-T1 (pop-up): hanya isian berubah + alasan dikirim; Ajukan & setujui hanya untuk pemutus bila satu orang", async () => {
  mockGet.mockResolvedValue({ data: profil() });
  mockPost.mockResolvedValue({ data: { id: "cpr_9" } });
  await mount(<CustomerCreditTab customer={P1} currentUser={SLS} selectedEntity="ent_ksc" />);
  await click(q("customer-credit-request"));
  expect(q("credit-request-modal")).not.toBeNull();
  expect(q("credit-request-submit-approve")).toBeNull();          // Sales tidak memutus (K-28)
  await type(q("credit-request-limit"), "60000000");
  await click(q("credit-request-submit"));
  expect(q("credit-request-missing").textContent).toContain("alasan pengajuan");
  expect(mockPost).not.toHaveBeenCalled();
  await type(q("credit-request-reason"), "Naik kelas grosir");
  await click(q("credit-request-submit"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  const [url, body] = mockPost.mock.calls[0];
  expect(url).toBe("/api/customers/cus_p1/credit-profile-requests");
  expect(body).toEqual({ entity_id: "ent_ksc", changes: { credit_limit: 60000000 }, reason: "Naik kelas grosir", attachment_url: "" });

  for (const { root, host } of roots) { await act(async () => { root.unmount(); }); host.remove(); }
  roots = [];
  mockPost.mockReset();
  mockGet.mockResolvedValue({ data: profil() });
  mockPost.mockResolvedValueOnce({ data: { id: "cpr_10" } }).mockResolvedValueOnce({ data: { request: {} } });
  await mount(<CustomerCreditTab customer={P1} currentUser={MGR} selectedEntity="ent_ksc" />);
  await click(q("customer-credit-request"));
  await click(q("credit-request-block-follow").querySelector("input"));   // lepas "Ikut PT" → isi 30 hari
  await type(q("credit-request-block-days"), "30");
  await type(q("credit-request-reason"), "Pelanggan lama terpercaya");
  await click(q("credit-request-submit-approve"));
  expect(mockConfirm).toHaveBeenCalledTimes(1);
  expect(mockPost.mock.calls[0][1].changes).toEqual({ overdue_block_days: 30 });
  expect(mockPost.mock.calls[1][0]).toBe("/api/credit-profile-requests/cpr_10/decision");

  for (const { root, host } of roots) { await act(async () => { root.unmount(); }); host.remove(); }
  roots = [];
  mockGet.mockResolvedValue({ data: profil({ dual: { dua_orang: true, batas_nominal: 0 } }) });
  await mount(<CustomerCreditTab customer={P1} currentUser={MGR} selectedEntity="ent_ksc" />);
  await click(q("customer-credit-request"));
  expect(q("credit-request-submit-approve")).toBeNull();          // aturan PT dua orang → tidak ada tombol kedua
});

test("CR-T1 U17 (manajer): Kredit & Plafon menampilkan antrean pengajuan dan tombol putus", async () => {
  mockGet.mockResolvedValue({ data: { items: [{ ...PENDING, entity: ENT, can_cancel: false },
    { ...PENDING, id: "cpr_3", requested_by_id: "u_mgr", blocked_reason: "harus orang lain", entity: ENT, can_cancel: true }],
  total: 2, page: 1, page_size: 50 } });
  await mount(<CreditProfileRequestsPanel currentUser={MGR} />);
  expect(mockGet).toHaveBeenCalledWith("/api/credit-profile-requests", { params: { status: "diajukan", page: 1, page_size: 50 } });
  expect(q("credit-requests-count").textContent).toBe("2 menunggu");
  expect(q("credit-request-approve-cpr_2").disabled).toBe(false);
  expect(q("credit-request-reject-cpr_2")).not.toBeNull();
  expect(q("credit-request-approve-cpr_3").disabled).toBe(true);
  expect(q("credit-request-blocked-cpr_3").textContent).toContain("rekan lain yang memutus");
  expect(q("credit-requests-table").querySelector("th.col-sticky-end").textContent).toBe("Keputusan");
  expect(q("credit-requests-search")).not.toBeNull();
});

test("CR-T1 (memuat / galat / tanpa izin)", async () => {
  let resolve;
  mockGet.mockImplementation(() => new Promise((r) => { resolve = r; }));
  await mount(<CustomerCreditTab customer={P1} currentUser={SLS} selectedEntity="ent_ksc" />);
  expect(q("customer-credit-loading").textContent).toBe("Memuat profil kredit…");
  const err = new Error("500");
  err.response = { status: 500, data: { detail: "Galat server" } };
  await act(async () => { resolve(Promise.reject(err)); });
  await flush();
  expect(q("customer-credit-error")).not.toBeNull();
  for (const { root, host } of roots) { await act(async () => { root.unmount(); }); host.remove(); }
  roots = [];
  await mount(<CreditProfileRequestsPanel currentUser={{ id: "x", permissions: { customer: ["view"] } }} />);
  expect(q("credit-requests-panel")).toBeNull();
});
