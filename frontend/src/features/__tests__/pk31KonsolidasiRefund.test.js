// PK-31 U16 (komponen) — Konsolidasi Grup: Bagian non-pengendali/pemilik induk (K-10), eliminasi otomatis per bulan
// dengan lencana Beku, peringatan bulan beku yang berbeda dari hitung ulang; Saldo Antar-PT: kolom Utang refund, tombol
// Catat Refund (izin `interco.settle`), dialog refund yang menyebut nominal dan kedua PT lalu mengirim Idempotency-Key.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { AutoEliminationsByMonth, OwnershipShare, PeriodStaleNotice } from "../finance/ConsolidationPeriodParts";
import { BalancesPanel } from "../finance/interco/IntercoPanels";
import IntercoRefundModal, { refundLeft } from "../finance/interco/IntercoRefundModal";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockConfirm = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: (...a) => mockConfirm(...a),
  default: { askConfirm: (...a) => mockConfirm(...a) },
}));
jest.mock("../../config/paymentMethods", () => ({
  __esModule: true,
  usePaymentMethods: () => ({ methods: [{ code: "transfer", name: "Transfer bank", needs_account: "bank" }] }),
}));
jest.mock("../../components/KNSelect", () => {
  const Sel = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={!!p.disabled}
      onChange={(e) => p.onValueChange?.(e.target.value)}>
      <option value="">—</option>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: Sel, KNSelect: Sel };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange(e.target.value)} />,
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  await act(async () => {});
  return { host, root };
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await act(async () => {});
  await act(async () => {});
}
afterEach(() => { mockGet.mockReset(); mockPost.mockReset(); mockConfirm.mockReset(); document.body.innerHTML = ""; });

const RINGKASAN = {
  entities: [{ entity_id: "A", short_name: "PT A", ownership_pct: 100 }, { entity_id: "B", short_name: "PT B", ownership_pct: 80 }],
  consolidated: { nci_net_income: 2000000, nci_equity: 10000000, net_income_parent: 38000000, equity_parent: 240000000 },
};

test("U16 (komponen) — Bagian non-pengendali tampil bila ada PT < 100 %, tersembunyi bila semua 100 %", async () => {
  let r = await mount(<OwnershipShare data={RINGKASAN} year="2027" asOf="2027-12-31" />);
  expect(q(r.host, "cons-share-nci").textContent).toContain("Bagian non-pengendali");
  expect(q(r.host, "cons-share-nci-ni").textContent).toMatch(/2\.000\.000/);
  expect(q(r.host, "cons-share-nci-eq").textContent).toMatch(/10\.000\.000/);
  expect(q(r.host, "cons-share-parent-ni").textContent).toMatch(/38\.000\.000/);
  await act(async () => { r.root.unmount(); });
  r = await mount(<OwnershipShare data={{ ...RINGKASAN, entities: [{ entity_id: "A", ownership_pct: 100 }] }} year="2027" asOf="2027-12-31" />);
  expect(q(r.host, "cons-ownership-share")).toBeNull();
});

test("U16 (komponen) — eliminasi otomatis per bulan: lencana Beku (ikon + teks) & peringatan hitung ulang", async () => {
  const entries = [
    { source_g6_pair_id: "p1", period_key: "2026-12", period_label: "Desember 2026", seller_number: "AAA/IC-P1",
      effective_date: "2026-12-31", frozen: true, total_debit: 200000000,
      lines: [{ account_code: "4-1000", account_name: "Pendapatan", debit: 100000000, credit: 0 }] },
    { source_g6_pair_id: "p1", period_key: "2027-01", period_label: "Januari 2027", seller_number: "AAA/IC-P1",
      effective_date: "2027-01-31", frozen: false, total_debit: 100000000, lines: [] },
  ];
  const r = await mount(<AutoEliminationsByMonth entries={entries} />);
  const des = q(r.host, "cons-month-2026-12");
  expect(des.textContent).toContain("Desember 2026");
  const beku = des.querySelector('[data-testid="cons-month-frozen"]');
  expect(beku.textContent).toContain("Beku");
  expect(beku.querySelector("svg")).not.toBeNull();
  expect(q(r.host, "cons-month-2027-01").querySelector('[data-testid="cons-month-frozen"]')).toBeNull();
  await click(q(r.host, "cons-month-toggle-2026-12"));
  expect(q(r.host, "cons-auto-elim-p1-2026-12").textContent).toContain("4-1000");
  const s = await mount(<PeriodStaleNotice stale={[{ pair_id: "p5", number: "IC/P5", period_key: "2026-12", period_label: "Desember 2026" }]} />);
  expect(q(s.host, "cons-period-stale").textContent).toContain(
    "Eliminasi bulan Desember 2026 berbeda dari hitung ulang karena ada jurnal mundur. Periksa sebelum memakai laporan ini.");
});

const AKUN = [
  { id: "ica_A_B_ar", role: "receivable", from_entity_id: "A", from_entity_name: "PT A", to_entity_id: "B",
    to_entity_name: "PT B", seller_entity_name: "PT A", buyer_entity_name: "PT B", outstanding: 0, refund_outstanding: 4000000 },
  { id: "ica_B_A_ap", role: "payable", from_entity_id: "B", from_entity_name: "PT B", to_entity_id: "A",
    to_entity_name: "PT A", seller_entity_name: "PT A", buyer_entity_name: "PT B", outstanding: 0, refund_outstanding: 4000000 },
];

test("U16 (komponen) — Saldo Antar-PT: kolom Utang refund dua sisi; Catat Refund hanya untuk pemegang izin", async () => {
  const onRefund = jest.fn();
  let r = await mount(<BalancesPanel accounts={AKUN} canWrite={false} canRefund onRefund={onRefund} />);
  expect(q(r.host, "interco-refund-ica_A_B_ar").textContent).toMatch(/4\.000\.000.*Harus dikembalikan ke PT B/);
  expect(q(r.host, "interco-refund-ica_B_A_ap").textContent).toMatch(/4\.000\.000.*Akan diterima dari PT A/);
  expect(q(r.host, "interco-refund-btn-ica_B_A_ap")).toBeNull();      // tombol di sisi penjual saja
  await click(q(r.host, "interco-refund-btn-ica_A_B_ar"));
  expect(onRefund).toHaveBeenCalledWith(AKUN[0]);
  await act(async () => { r.root.unmount(); });
  r = await mount(<BalancesPanel accounts={AKUN} canWrite={false} canRefund={false} onRefund={onRefund} />);
  expect(q(r.host, "interco-refund-btn-ica_A_B_ar")).toBeNull();
});

test("U16 (komponen) — dialog Catat Refund: konfirmasi menyebut nominal & kedua PT, kirim ber-Idempotency-Key", async () => {
  const doc = { id: "rf_s", role: "seller", number: "RFS/IC-RF", seller_entity_id: "A", buyer_entity_id: "B",
    doc_date: "2026-11-02", grand_total: 10000000, settled_amount: 10000000, returned_amount: 4000000,
    refund_due: 4000000, refund_paid: 0 };
  expect(refundLeft(doc)).toBe(4000000);
  expect(refundLeft({ grand_total: 10, settled_amount: 10, returned_amount: 4 })).toBe(4);   // dokumen lama tanpa refund_due
  mockGet.mockImplementation((url) => Promise.resolve({
    data: url.includes("/bank-accounts") ? [{ id: "rek_a", name: "Bank A", entity_id: "A", is_active: true }] : [doc] }));
  mockConfirm.mockResolvedValue(true);
  mockPost.mockResolvedValue({ data: { id: "ics_1", number: "ICS-1", total_applied: 4000000 } });
  const onCreated = jest.fn();
  const ents = [{ id: "A", short_name: "PT A" }, { id: "B", short_name: "PT B" }];
  const r = await mount(<IntercoRefundModal entities={ents} presetPayerEntityId="A" presetPayeeEntityId="B"
    onClose={() => {}} onCreated={onCreated} />);
  expect(mockGet.mock.calls[0][1].params).toEqual({ entity_id: "A", role: "seller", refund_open: true });
  expect(q(r.host, "interco-refund-submit").disabled).toBe(true);
  expect(q(r.host, "interco-refund-reason").textContent).toContain("Centang minimal satu transaksi");
  await click(q(r.host, "interco-refund-check-rf_s"));
  expect(q(r.host, "interco-refund-total").textContent).toMatch(/4\.000\.000/);
  await click(q(r.host, "interco-refund-submit"));
  expect(mockConfirm.mock.calls[0][0].message).toMatch(/Pengembalian dana Rp\s?4\.000\.000 dari PT A kepada PT B akan dicatat dan dijurnal di kedua PT\./);
  const [url, body, cfg] = mockPost.mock.calls[0];
  expect(url).toBe("/api/interco/refunds");
  expect(body).toMatchObject({ payer_entity_id: "A", payee_entity_id: "B", bank_account_id: "rek_a", method: "transfer",
    transactions: [{ interco_id: "rf_s", applied_amount: 4000000 }] });
  expect(cfg.headers["Idempotency-Key"]).toMatch(/^ic-refund-/);
  expect(onCreated).toHaveBeenCalled();
});
