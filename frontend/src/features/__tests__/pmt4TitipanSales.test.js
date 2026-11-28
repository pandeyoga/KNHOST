// PM-T4 — tunai yang diterima sales dicatat sebagai titipan sampai disetor. Uji komponen (bagian layar U17; uji jalan
// peramban terpisah): form kwitansi (teks bantu titipan tanpa isian rekening; "Dilarang" → tunai tidak ditawarkan),
// kartu HP "Titipan Saya" (Setor → setoran diajukan, kunci idempotensi), tab Kas & Bank › Titipan Sales (setoran
// menunggu diterima: Terima → pop-up rekening + konfirmasi nominal · PT · rekening · penyetor; setoran sendiri dan
// "Semua PT" → tombol mati dengan alasan tertulis; titipan per orang).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";
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
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      <option value="" />
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange?.(e.target.value)} />,
  formatDateId: (v) => String(v || ""),
}));
jest.mock("../../components/AskKnButton", () => ({ __esModule: true, AskKnButton: () => null, PENDING_KEY: "x" }));
jest.mock("../finance/payments/paymentApi", () => ({
  assessVariance: () => Promise.resolve({ direction: "none" }),
  directionMeta: () => ({ label: "", bg: "", fg: "" }), varianceMeta: () => Promise.resolve({ reasons: [] }),
  varianceKindMeta: () => ({ label: "", bg: "", fg: "" }),
}));

/* eslint-disable import/first */
import ARReceiptModal from "../finance/payments/ReceivePaymentModal";   // MN-T3 — dulu crm/ARReceiptModal
import MobileCashHoldingCard, { alasanTidakBisaSetor, showCashHoldingCard } from "../sales/mobile/MobileCashHoldingCard";
import CashHoldingsView from "../finance/cashholding/CashHoldingsView";
import { TEKS_TITIPAN, cashHoldingStatus } from "../finance/cashholding/cashHoldingShared";
import { invalidatePaymentMethods } from "../../config/paymentMethods";
import { setAccessContext } from "../../config/roles";
/* eslint-enable import/first */

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const M = (code, name, need = "bank") => ({ code, name, needs_account: need, needs_reference: need === "bank",
  needs_due_date: false });
const MASUK = [M("transfer", "Transfer bank"), M("cash", "Tunai", "kas")];
const ENT = [{ id: "ent_kanda", short_name: "Kanda", legal_name: "CV Kanda" }];
const K = { id: "rek_k", name: "Kas Kecil Kanda", account_type: "cash", cash_type: "kas_kecil", entity_id: "ent_kanda",
  is_active: true };
const KASIR = { id: "rek_ks", name: "Kas Kasir Toko KSC", account_type: "cash", cash_type: "kas_kasir", entity_id: "ent_kanda",
  is_active: true, is_default: true };
const S1 = { order_id: "so1", number: "KANDA/SO-0001", outstanding: 1000000, receiving_account_id: "", receiving_account: {} };

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 10) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el, entity = "ent_kanda") {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(<EntityScopeProvider selectedEntity={entity} entities={ENT} canSwitch>{el}<ConfirmHost /></EntityScopeProvider>);
  });
  await flush();
  return host;
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
async function pick(el, value) {
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set;
    setter.call(el, value);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}
function routeGet(map) {
  mockGet.mockImplementation((url, cfg) => {
    const key = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.includes(k));
    const v = key ? map[key] : [];
    return Promise.resolve({ data: typeof v === "function" ? v(cfg) : v });
  });
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  [mockGet, mockPost].forEach((m) => m.mockReset());
  invalidatePaymentMethods();
  setAccessContext(null);
  document.body.innerHTML = "";
});

const formDasar = (mode) => ({
  "/payment-methods": MASUK, "/ar-receipts/open-orders": [S1], "/ar-receipts/deposit": {},
  "/bank-accounts/receiving": (cfg) => (cfg?.params?.method === "cash" ? [K] : []),
  "/settings/effective": { payment: { wajib_nomor_referensi: false } },
  "/cash-holdings/me/summary": { entity_id: "ent_kanda", mode } });

test("form kwitansi: mode titipan → teks bantu titipan, tanpa rekening, konfirmasi menyebut titipan", async () => {
  routeGet(formDasar("titipan"));
  mockPost.mockResolvedValue({ data: { id: "arc_1", number: "AR-1", amount: 300000, applied_total: 300000 } });
  await mount(<ARReceiptModal customerId="c1" customerName="Toko Kanda" preselectOrderId="so1" onClose={() => {}} onDone={() => {}} />);
  await pick(q("ar-receipt-method"), "cash");
  expect(q("ar-receipt-cash-hint").textContent).toBe(TEKS_TITIPAN);
  expect(q("ar-receipt-cash-hint").querySelector("svg")).not.toBeNull();
  expect(q("ar-receipt-account-field")).toBeNull();                 // belum ada kas → tidak memilih rekening
  expect(q("ar-receipt-submit").disabled).toBe(false);
  await click(q("ar-receipt-submit"));
  expect(q("ar-receipt-confirm-message").textContent).toContain("titipan tunai di tangan Anda (belum masuk kas)");
  await click(q("ar-receipt-confirm-confirm"));
  const [url, body] = mockPost.mock.calls[0];
  expect(url).toBe("/api/ar-receipts");
  expect(body).toMatchObject({ method: "cash", amount: 1000000 });
  expect(body.account_id).toBeUndefined();
  // Transfer tetap memakai rekening seperti biasa (teks bantu lama).
  await pick(q("ar-receipt-method"), "transfer");
  expect(q("ar-receipt-cash-hint").textContent).toContain("Kas Besar");
});

test("form kwitansi: mode dilarang → pilihan Tunai tidak ditawarkan; kas langsung → teks lama", async () => {
  routeGet(formDasar("dilarang"));
  await mount(<ARReceiptModal customerId="c1" customerName="Toko Kanda" preselectOrderId="so1" onClose={() => {}} onDone={() => {}} />);
  const opsi = [...q("ar-receipt-method").querySelectorAll("option")].map((o) => o.value).filter(Boolean);
  expect(opsi).toEqual(["transfer"]);
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  document.body.innerHTML = "";
  routeGet(formDasar("kas_langsung"));
  await mount(<ARReceiptModal customerId="c1" customerName="Toko Kanda" preselectOrderId="so1" onClose={() => {}} onDone={() => {}} />);
  await pick(q("ar-receipt-method"), "cash");
  expect(q("ar-receipt-cash-hint").textContent).toContain("Kas Kecil");
  expect(q("ar-receipt-account-field")).not.toBeNull();
});

test("kartu HP Titipan Saya: total, batas, Setor → setoran diajukan dengan kunci idempotensi", async () => {
  setAccessContext({ role: "sales", permissions: { cash_holding: ["view", "create"] } });
  let summary = { entity_id: "ent_kanda", mode: "titipan", held_total: 450000, count: 2, limit: 0, oldest_due_at: "",
    pending_total: 0, available: 450000, overdue_count: 1 };
  routeGet({ "/cash-holdings/me/summary": () => summary });
  mockPost.mockImplementation(() => {
    summary = { ...summary, pending_total: 450000, available: 0 };
    return Promise.resolve({ data: { id: "cdp_1", number: "KANDA/STT-00001", status: "diajukan" } });
  });
  await mount(<MobileCashHoldingCard selectedEntity="ent_kanda" />);
  expect(q("m-cth-held").textContent).toMatch(/Rp\s?450\.000/);
  expect(q("m-cth-count").textContent).toBe("2");
  expect(q("m-cth-limit").textContent).toBe("Tanpa batas");
  expect(q("m-cth-due").textContent).toBe("Tanpa tenggat");
  expect(q("m-cth-overdue").querySelector("svg")).not.toBeNull();
  await click(q("m-cth-deposit"));
  expect(q("m-cth-form-amount").value).toMatch(/450/);
  await act(async () => { q("m-cth-form").querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
  await flush();
  const [url, body, cfg] = mockPost.mock.calls[0];
  expect(url).toBe("/api/cash-deposits");
  expect(body).toEqual({ amount: 450000, note: "" });
  expect(cfg.headers["Idempotency-Key"]).toBeTruthy();
  expect(q("m-cth-msg").textContent).toBe("Setoran diajukan. Serahkan uangnya ke kasir.");
  expect(q("m-cth-pending").textContent).toMatch(/Rp\s?450\.000/);
  expect(q("m-cth-deposit").disabled).toBe(true);
  expect(q("m-cth-deposit-why").textContent).toBe("Semua titipan sudah diajukan — tunggu kasir menerimanya.");
});

test("kartu HP: tidak tampil saat kas langsung tanpa titipan; alasan tombol mati tertulis", () => {
  expect(showCashHoldingCard({ mode: "kas_langsung", held_total: 0, pending_total: 0 })).toBe(false);
  expect(showCashHoldingCard({ mode: "kas_langsung", held_total: 1, pending_total: 0 })).toBe(true);
  expect(showCashHoldingCard({ mode: "titipan", held_total: 0, pending_total: 0 })).toBe(true);
  expect(alasanTidakBisaSetor({ entity_id: "" }, true)).toBe("Pilih satu PT dulu");
  expect(alasanTidakBisaSetor({ entity_id: "e", available: 5 }, false)).toMatch(/butuh akses/);
  expect(alasanTidakBisaSetor({ entity_id: "e", available: 0, pending_total: 0 }, true)).toBe("Tidak ada titipan yang bisa disetor.");
  expect(alasanTidakBisaSetor({ entity_id: "e", available: 5 }, true)).toBe("");
  for (const s of ["dipegang", "sebagian_disetor", "disetor", "batal", "diajukan", "diterima", "ditolak", "dibatalkan"]) {
    const st = cashHoldingStatus(s);
    expect(st.label).not.toMatch(/_/);
    expect(st.icon).toBeTruthy();
  }
});

const DEP_OTHER = { id: "cdp_a", number: "KANDA/STT-00001", holder_user_id: "u_sls", holder_name: "Sales Satu", amount: 300000,
  note: "uang kunjungan", created_at: new Date(Date.now() - 2 * 86400000).toISOString(), status: "diajukan" };
const DEP_OWN = { ...DEP_OTHER, id: "cdp_b", number: "KANDA/STT-00002", holder_user_id: "u_fin", holder_name: "Fina" };
const HOLDERS = { items: [{ id: "cth_1", number: "KANDA/TTP-00001", receipt_number: "KANDA/AR-00001", customer_name: "Toko",
  received_at: "2026-11-10T03:00:00+00:00", amount: 300000, outstanding: 300000, status: "dipegang", overdue: true,
  holder_user_id: "u_sls" }], total: 1,
  holders: [{ holder_user_id: "u_sls", holder_name: "Sales Satu", held_total: 300000, count: 1,
    oldest_received_at: "2026-11-10T03:00:00+00:00", overdue_count: 1 }] };

test("tab Titipan Sales: terima setoran → pop-up rekening + konfirmasi nominal · PT · rekening · penyetor", async () => {
  setAccessContext({ role: "finance", permissions: { cash_holding: ["view", "approve"], cash: ["view"] } });
  routeGet({ "/cash-deposits": { items: [DEP_OTHER, DEP_OWN], total: 2, amount_total: 600000 },
    "/cash-holdings": HOLDERS, "/bank-accounts": [K] });
  mockPost.mockResolvedValue({ data: { ...DEP_OTHER, status: "diterima", gl_status: "posted" } });
  await mount(<CashHoldingsView currentUser={{ id: "u_fin" }} />);
  expect(q("cth-deposits-count").textContent).toMatch(/2 setoran/);
  expect(q("cth-receive-cdp_b").disabled).toBe(true);                       // setoran sendiri
  expect(q("cth-deposit-own-cdp_b").textContent).toBe("Setoran Anda sendiri — diterima orang lain.");
  expect(q("cth-receive-why")).toBeNull();
  expect(q("cth-holder-row-u_sls").textContent).toContain("Sales Satu");
  expect(q("cth-holder-overdue-u_sls").querySelector("svg")).not.toBeNull();
  await click(q("cth-receive-cdp_a"));
  expect(q("cth-receive-holder").textContent).toBe("Sales Satu");
  expect(q("cth-receive-account-select").value).toBe("rek_k");              // satu-satunya rekening PT
  await act(async () => { q("cth-receive-form").querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
  await flush();
  expect(mockPost).not.toHaveBeenCalled();
  const pesan = q("cth-receive-confirm-message").textContent;
  expect(q("cth-receive-confirm").textContent).toMatch(/Rp\s?300\.000/);
  expect(pesan).toContain("Kanda");
  expect(pesan).toContain("Kas Kecil Kanda");
  expect(pesan).toContain("Sales Satu");
  await click(q("cth-receive-confirm-confirm"));
  const [url, body, cfg] = mockPost.mock.calls[0];
  expect(url).toBe("/api/cash-deposits/cdp_a/receive");
  expect(body).toEqual({ account_id: "rek_k" });
  expect(cfg.headers["Idempotency-Key"]).toBeTruthy();
  expect(q("cth-msg").textContent).toContain("diterima ke Kas Kecil Kanda");
  // rincian per orang
  await click(q("cth-holder-open-u_sls"));
  expect(q("cth-holding-status-cth_1").textContent).toBe("Dipegang");
  expect(q("cth-holding-overdue-cth_1").textContent).toBe("Lewat tenggat");
});

test("tab Titipan Sales: Semua PT → tombol mati beralasan; kosong → satu kalimat", async () => {
  setAccessContext({ role: "finance", permissions: { cash_holding: ["view", "approve"] } });
  routeGet({ "/cash-deposits": { items: [DEP_OTHER], total: 1, amount_total: 300000 },
    "/cash-holdings": { items: [], total: 0, holders: [] } });
  await mount(<CashHoldingsView currentUser={{ id: "u_fin" }} />, "all");
  expect(q("cth-receive-why").textContent).toBe("Pilih satu PT dulu");
  expect(q("cth-receive-cdp_a").disabled).toBe(true);
  expect(q("cth-reject-cdp_a").disabled).toBe(true);
  expect(q("cth-holdings-empty").textContent).toBe("Tidak ada titipan tunai.");
});

test("tab Titipan Sales: tanpa izin menerima → alasan tertulis", async () => {
  setAccessContext({ role: "sales", permissions: { cash_holding: ["view", "create"] } });
  routeGet({ "/cash-deposits": { items: [DEP_OTHER], total: 1, amount_total: 300000 },
    "/cash-holdings": { items: [], total: 0, holders: [] } });
  await mount(<CashHoldingsView currentUser={{ id: "u_x" }} />);
  expect(q("cth-receive-why").textContent).toBe("Menerima setoran butuh akses menerima setoran titipan.");
  expect(q("cth-receive-cdp_a").disabled).toBe(true);
});

test("kalimat cara bayar tunai mengikuti rekening penerima: kasir, kas kecil, belum terpilih", async () => {
  const ARR = (rows) => ({ ...formDasar("kas_langsung"), "/bank-accounts/receiving": (cfg) => (cfg?.params?.method === "cash" ? rows : []) });
  const buka = async () => {
    await mount(<ARReceiptModal customerId="c1" customerName="Toko Kanda" preselectOrderId="so1" onClose={() => {}} onDone={() => {}} />);
    await pick(q("ar-receipt-method"), "cash");
  };
  routeGet(ARR([KASIR]));
  await buka();
  expect(q("ar-receipt-cash-hint").textContent).toBe("Tunai → masuk Kas Kasir Toko KSC (Kas Kasir).");
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = []; document.body.innerHTML = "";
  routeGet(ARR([K]));
  await buka();
  expect(q("ar-receipt-cash-hint").textContent).toBe("Tunai → masuk Kas Kecil Kanda (Kas Kecil).");
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = []; document.body.innerHTML = "";
  routeGet(ARR([K, { ...K, id: "rek_k2", name: "Kas Kecil Dua" }]));   // dua rekening, tanpa bawaan → belum terpilih
  await buka();
  expect(q("ar-receipt-cash-hint").textContent).toBe("Tunai → masuk rekening tunai PT yang dipilih.");
  expect(q("ar-receipt-cash-hint").textContent).not.toMatch(/Kas (Kecil|Kasir)/);
});
