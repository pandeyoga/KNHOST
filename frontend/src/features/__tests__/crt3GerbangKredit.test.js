// CR-T3 — layar gerbang kredit (docs/blueprint/unit/CR-T3.md, bagian Layar; U18 diwakili uji komponen, uji jalan peramban
// = integrator): (a) checkout menampilkan empat baris eksposur, Plafon, Sisa plafon, pesan alasan, dan tombol "Ajukan izin
// kredit" saat tertahan; (b) pop-up izin mengirim lingkup, nominal, alasan dari master; (c) panel izin kredit menampilkan
// Lingkup, Sisa, Berlaku sampai, Alasan, konfirmasi menyebut pelanggan + PT + nominal (N5); (d) detail pesanan: lencana
// Tahan kredit + alasan + Periksa ulang kredit; (e) sub-status "Tahan kredit".
import React, { act } from "react";
import { createRoot } from "react-dom/client";

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
      <option value="">—</option>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/MoneyInput", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p.testId} value={p.value || ""} onChange={(e) => p.onChange?.(e.target.value)} />,
}));

import CreditGateBox from "../pos/CreditGateBox";
import CreditOverrideModal from "../crm/CreditOverrideModal";
import CreditOverridesPanel from "../crm/CreditOverridesPanel";
import OrderCreditHold from "../orders/OrderCreditHold";
import { deriveStageSub, subStatusLabel } from "../../utils/soStatus";
import { setAccessContext } from "../../config/roles";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  for (let i = 0; i < 5; i += 1) await act(async () => {});
  roots.push(root);
  return host;
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = []; document.body.innerHTML = ""; setAccessContext(null); mockGet.mockReset(); mockPost.mockReset();
});
const q = (host, tid) => host.querySelector(`[data-testid="${tid}"]`);
const setVal = async (el, v) => {
  const proto = el.tagName === "SELECT" ? window.HTMLSelectElement.prototype
    : el.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, "value").set.call(el, v);
  await act(async () => { el.dispatchEvent(new Event(el.tagName === "SELECT" ? "change" : "input", { bubbles: true })); });
};

// U2 (G1): 6.000.000 + 2.000.000 − 500.000 + 3.000.000 = 10.500.000 > 10.000.000 → tertahan
const GATE_TAHAN = {
  result: "tahan", raw_result: "tahan", checked: true, override: null, pay_before_ship: false,
  exposure: { ar_delivered: 6000000, open_orders: 2000000, giro_outstanding: 0, deposit: 500000, this_order: 3000000, total: 10500000 },
  counted: { open_orders: true, giro: true, deposit: true }, limit: { credit_limit: 10000000, available: 0 },
  reasons: [{ code: "LEWAT_PLAFON", result: "tahan", message: "Eksposur Rp 10.500.000 melewati plafon Rp 10.000.000." }],
};

test("U18a checkout: empat baris eksposur, plafon, sisa, alasan, dan Ajukan izin kredit saat tertahan", async () => {
  setAccessContext({ role: "sales", permissions: { credit_override: ["view", "create"] } });
  const host = await mount(<CreditGateBox credit={{ gate: GATE_TAHAN }} customer={{ id: "cus1", name: "Toko P" }} amount={3000000} entityId="ent_kanda" />);
  const rows = q(host, "credit-gate-box-rows").textContent;
  for (const t of ["Piutang barang terkirim", "Pesanan belum dikirim", "Giro belum cair", "Titipan pelanggan", "Eksposur", "Plafon", "Sisa plafon"]) {
    expect(rows).toContain(t);
  }
  expect(q(host, "credit-gate-box-ar").textContent).toContain("6.000.000");
  expect(q(host, "credit-gate-box-deposit").textContent).toContain("500.000");
  expect(q(host, "credit-gate-box-total").textContent).toContain("10.500.000");
  expect(q(host, "credit-gate-box-result").textContent).toContain("Kredit tertahan");
  expect(q(host, "credit-gate-box-reasons").textContent).toContain("Eksposur Rp 10.500.000 melewati plafon Rp 10.000.000.");
  expect(q(host, "credit-override-open")).not.toBeNull();
});

test("U18a' komponen tidak dihitung tertulis; tanpa izin mengajukan = kalimat, bukan tombol mati", async () => {
  setAccessContext({ role: "finance", permissions: { credit_override: ["view"] } });
  const gate = { ...GATE_TAHAN, counted: { open_orders: true, giro: true, deposit: false } };
  const host = await mount(<CreditGateBox credit={{ gate }} customer={{ id: "cus1", name: "Toko P" }} amount={3000000} />);
  expect(q(host, "credit-gate-box-deposit").textContent).toContain("tidak dihitung");
  expect(q(host, "credit-override-open")).toBeNull();
  expect(q(host, "credit-override-request-none").textContent).toContain("pemegang akses mengajukan izin kredit");
});

test("U18b pop-up izin kredit: lingkup, nominal, alasan dari master, catatan", async () => {
  mockGet.mockResolvedValue({ data: [{ code: "cr_riwayat_baik", label: "Riwayat bayar baik" }, { code: "cr_lain", label: "Lainnya (jelaskan di catatan)" }] });
  mockPost.mockResolvedValue({ data: { id: "cro1" } });
  const saved = jest.fn();
  const host = await mount(<CreditOverrideModal open customer={{ id: "cus1", name: "Toko P" }} entityId="ent_kanda"
    amount={3000000} onClose={() => {}} onSaved={saved} />);
  expect(mockGet).toHaveBeenCalledWith("/api/credit-override-reasons");
  expect([...q(host, "credit-override-scope").options].map((o) => o.textContent)).toContain("Pelanggan ini");
  await act(async () => { q(host, "credit-override-submit").click(); });
  expect(q(host, "credit-override-missing").textContent).toContain("alasan");
  expect(mockPost).not.toHaveBeenCalled();
  await setVal(q(host, "credit-override-reason-code"), "cr_riwayat_baik");
  await act(async () => { q(host, "credit-override-submit").click(); });
  for (let i = 0; i < 3; i += 1) await act(async () => {});
  const [url, body, cfg] = mockPost.mock.calls[0];
  expect(url).toBe("/api/customers/cus1/credit-override");
  expect(body).toMatchObject({ amount: 3000000, scope: "pelanggan", reason_code: "cr_riwayat_baik", entity_id: "ent_kanda" });
  expect(cfg.headers["Idempotency-Key"]).toBeTruthy();
  expect(saved).toHaveBeenCalled();
});

test("U18c panel izin kredit: Lingkup, Sisa, Berlaku sampai, Alasan; konfirmasi menyebut pelanggan, PT, nominal", async () => {
  mockGet.mockResolvedValue({ data: [
    { id: "co1", customer_name: "Toko P", entity_name: "CV Kanda", scope: "pelanggan", amount: 3000000, remaining_amount: 3000000,
      status: "pending", reason_code: "cr_riwayat_baik", reason_label: "Riwayat bayar baik", requested_by: "Ayu", created_at: "2026-11-14T02:00:00Z" },
    { id: "co2", customer_name: "Toko Q", entity_name: "CV Kanda", scope: "pesanan", order_number: "KANDA/SO-00012", amount: 2000000,
      remaining_amount: 500000, valid_until: "2026-11-17T02:00:00+00:00", status: "approved", reason_label: "Ada jaminan atau giro mundur",
      requested_by: "Ayu", decided_by: "Dewi", created_at: "2026-11-13T02:00:00Z" },
  ] });
  const host = await mount(<CreditOverridesPanel currentUser={{ role: "manager", permissions: { credit_override: ["view", "approve"] } }} />);
  const head = q(host, "overrides-table").querySelector("thead").textContent;
  for (const t of ["Lingkup", "Sisa", "Berlaku sampai", "Alasan"]) expect(head).toContain(t);
  expect(q(host, "override-scope-co2").textContent).toContain("Pesanan ini");
  expect(q(host, "override-remaining-co2").textContent).toContain("500.000");
  expect(q(host, "override-valid-co2").textContent).not.toBe("—");
  expect(q(host, "override-status-co1").textContent).toContain("Menunggu");
  expect(q(host, "override-status-co2").textContent).toContain("Disetujui");
  await act(async () => { q(host, "override-approve-co1").click(); });
  const msg = q(host, "override-decision-confirm").textContent;
  expect(msg).toContain("Toko P");
  expect(msg).toContain("CV Kanda");
  expect(msg).toContain("3.000.000");
});

test("U18d detail pesanan: Tahan kredit + alasan + Periksa ulang kredit (order.update)", async () => {
  mockPost.mockResolvedValue({ data: { released: false, message: "Eksposur Rp 10.500.000 melewati plafon Rp 10.000.000." } });
  const order = { id: "so1", number: "KANDA/SO-00007", customer_id: "cus1", customer_name: "Toko P", entity_id: "ent_kanda",
    grand_total: 5000000, credit_hold: true,
    credit_hold_info: { since: "2026-11-15T03:00:00Z", checkpoint: "pesanan_diubah",
      reasons: [{ code: "LEWAT_PLAFON", result: "tahan", message: "Eksposur Rp 10.500.000 melewati plafon Rp 10.000.000." }] } };
  const host = await mount(<OrderCreditHold order={order} user={{ permissions: { order: ["update"] } }} onRefresh={() => {}} />);
  expect(q(host, "order-credit-hold-badge").textContent).toContain("Tahan kredit");
  expect(q(host, "order-credit-hold-reasons").textContent).toContain("melewati plafon");
  await act(async () => { q(host, "order-credit-recheck").click(); });
  for (let i = 0; i < 3; i += 1) await act(async () => {});
  expect(mockPost.mock.calls[0][0]).toBe("/api/sales-orders/so1/credit-recheck");
  expect(q(host, "order-credit-msg").textContent).toContain("Masih ditahan");
  const host2 = await mount(<OrderCreditHold order={order} user={{ permissions: {} }} />);
  expect(q(host2, "order-credit-recheck")).toBeNull();
  expect(q(host2, "order-credit-recheck-none")).not.toBeNull();
  const host3 = await mount(<OrderCreditHold order={{ ...order, credit_hold: false, pay_before_ship: true }} user={{ permissions: {} }} />);
  expect(q(host3, "order-pay-before-ship").textContent.trim()).toBe("Bayar penuh sebelum kirim (pelanggan sedang ditahan)");
});

test("U18e sub-status Tahan kredit mendahului alasan lain (mirror server)", () => {
  expect(deriveStageSub({ status: "confirmed", credit_hold: true })[1]).toEqual(["tahan_kredit", "siap_pick"]);
  expect(deriveStageSub({ status: "shipped", credit_hold: true })[1]).toEqual([]);
  expect(subStatusLabel("tahan_kredit")).toBe("Tahan kredit");
});
