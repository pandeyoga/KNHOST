// Uji situasi S1 (Pelatihan Keuangan 18 Nov — amandemen & koreksi penjualan) — dua kebingungan layar yang ditemukan saat
// situasi dijalankan sebagai pengguna:
//  (a) Ajukan Amandemen: kartu dampak menulis "Butuh persetujuan manager", kartu hasil "MENUNGGU persetujuan manager" dan
//      dokumen hasil "KSC/DN-… · debit_note" (kode peran & kode dokumen mentah) → kini "Manajer" dan "Nota Debit";
//  (b) Rincian pesanan: selama daftar faktur pajak dimuat tampil "Belum ada Faktur Pajak" dan tombol [Terbitkan Faktur
//      Pajak] (Finance bisa menekan tombol untuk pesanan yang sudah berfaktur) → kini "Memuat faktur pajak…" tanpa tombol.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), patch: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid }) => (
    <select data-testid={tid} value={value ?? ""} onChange={(e) => onValueChange(e.target.value)}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: M, KNSelect: M };
});
jest.mock("../documents/ProcessTimeline", () => () => null);
jest.mock("../documents/DocumentActionsBar", () => () => null);
jest.mock("../documents/RelatedDocsPanel", () => () => null);
jest.mock("../documents/trace/DocRefsPanel", () => () => null);
jest.mock("../finance/payments/SoPaymentPanel", () => () => null);
jest.mock("../orders/DispatchPaymentGatePanel", () => () => null);
jest.mock("../orders/PodProgressNote", () => () => null);
jest.mock("../orders/SoApprovalsPanel", () => () => null);
jest.mock("../orders/OrderFulfillmentBadges", () => () => null);
jest.mock("../orders/OrderIntercoSupplyPanel", () => () => null);
jest.mock("../orders/OrderTransferLinks", () => () => null);
jest.mock("../orders/RestockPanel", () => () => null);
jest.mock("../finance/amendments/AmendmentTrailPanel", () => () => null);
jest.mock("../orders/OrderFeedbackPanel", () => () => null);

import AmendmentImpactCard from "../finance/amendments/AmendmentImpactCard";
import { AmendmentResult } from "../finance/amendments/AmendmentProposeModal";
import { OrderDetailPanel } from "../orders/OrderDetailPanel";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);

let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(el); });
  await act(async () => {});
  return host;
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = []; document.body.innerHTML = "";
});

test("S1 (a): kartu dampak & kartu hasil amandemen menyebut peran penyetuju dan jenis dokumen dengan label", async () => {
  const pv = { before: { grand_total: 5875563 }, after: { grand_total: 5747802 }, impact: { delta: -127761, delta_pct: 2.17 },
    method: "re_derive", requires_approval: true, required_role: "manager", explain: [] };
  const host = await mount(<AmendmentImpactCard data={pv} testId="amd-preview-impact" />);
  const badge = q(host, "amd-preview-impact-approval").textContent;
  expect(badge).toContain("Butuh persetujuan Manajer");
  expect(badge).not.toMatch(/manager/);

  const menunggu = await mount(<AmendmentResult testId="amd-propose-modal" onClose={() => {}} result={{
    number: "KSC/AMD-00006", doc_number: "KSC/SO-00077", reason_label: "Negosiasi pelanggan", status: "pending_approval",
    required_role: "manager", impact: { delta: -127761 }, result_refs: [] }} />);
  const pesan = q(menunggu, "amd-result-message").textContent;
  expect(pesan).toContain("menunggu persetujuan Manajer");
  expect(pesan).not.toMatch(/manager|MENUNGGU/);

  const debit = await mount(<AmendmentResult testId="amd-propose-modal-2" onClose={() => {}} result={{
    number: "KSC/AMD-00010", doc_number: "KSC/SO-00076", reason_label: "Koreksi harga", status: "auto_applied",
    method_label: "Terbit Nota Debit (nilai naik) — dokumen asal tidak diubah", impact: { delta: 138395 },
    result_refs: [{ rel: "issued", doc_type: "debit_note", doc_number: "KSC/DN-00002", note: "Rp 138.395" }] }} />);
  const refs = q(debit, "amd-result-refs").textContent;
  expect(refs).toContain("KSC/DN-00002 · Nota Debit");
  expect(refs).not.toContain("debit_note");
});

test("S1 (a2): rincian amandemen di Pusat Amandemen menyebut penyetuju dengan label peran", async () => {
  mockGet.mockImplementation((url) => (String(url).startsWith("/api/amendments/") ? Promise.resolve({ data: {
    id: "amd1", number: "KSC/AMD-00011", status: "pending_approval", doc_number: "KSC/SO-00101", reason_label: "Negosiasi pelanggan",
    method: "re_derive", required_role: "manager", proposed_by: "Ayu Marketing", proposed_by_id: "u_sales",
    before: { grand_total: 5831829 }, after: { grand_total: 5701804 }, impact: { delta: -130025, delta_pct: 2.2 },
    changes: [], explain: [], refs: [], notes: [],
    policy_snapshot: { approval_threshold_amount: 5000000, approval_threshold_pct: 5, approver_role: "manager",
      admin_approval_above: 50000000, require_note_above: 10000000, dual_control: true, issued_doc_policy: "note_only" },
  } }) : Promise.resolve({ data: [] })));
  const { default: AmendmentDetailPanel } = await import("../finance/amendments/AmendmentDetailPanel");
  const user = { id: "u_mgr", role: "manager", permissions: { finance_amendment: ["propose", "approve"] } };
  const host = await mount(<AmendmentDetailPanel amdId="amd1" currentUser={user} />);
  await act(async () => {});
  const panel = q(host, "amd-detail-panel").textContent;
  expect(q(host, "amd-detail-policy").textContent).toContain("Penyetuju standarManajer");
  expect(q(host, "amd-decision-box").textContent).toContain("Keputusan diperlukan (Manajer)");
  expect(panel).not.toMatch(/MANAGER|manager/);
});

test("S1 (b): rincian pesanan tidak menawarkan [Terbitkan Faktur Pajak] selama daftar faktur masih dimuat", async () => {
  let lepasFaktur;
  mockGet.mockImplementation((url) => {
    if (url === "/api/tax-invoices") return new Promise((res) => { lepasFaktur = res; });
    if (url === "/api/settings/effective") return Promise.resolve({ data: { tax: { pemicu_faktur: "pesanan" } } });
    return Promise.resolve({ data: [] });
  });
  const SO = { id: "so_s1", number: "KSC/SO-S1", customer_name: "Toko Uji S1", status: "done", entity_id: "ent_ksc",
    is_pkp: true, payment_status: "unpaid", items: [{ product_id: "p1", product_name: "Kain A", sku: "A", quantity: 10,
      unit: "yard", price: 25000 }], total_amount: 250000, net_subtotal: 250000, ppn_amount: 27500, grand_total: 277500,
    created_at: "2026-11-17T03:00:00Z" };
  const user = { role: "finance", permissions: { tax_invoice: ["view", "create"], order: ["view"] } };
  const host = await mount(<OrderDetailPanel order={SO} user={user} embedded onIssueTaxInvoice={() => Promise.resolve()} />);
  expect(q(host, "order-tax-invoice-section")).not.toBeNull();
  expect(q(host, "order-tax-invoice-empty").textContent).toContain("Memuat faktur pajak");
  expect(q(host, "issue-tax-invoice-btn")).toBeNull();

  // Pesanan sudah berfaktur: sesudah daftar tiba, baris faktur tampil dan tombol terbit tetap tidak ada.
  await act(async () => { lepasFaktur({ data: [{ id: "fkt1", number: "KSC/FKT-00003", status: "normal", ppn_amount: 27500 }] }); });
  expect(q(host, "tax-invoice-row-fkt1")).not.toBeNull();
  expect(q(host, "issue-tax-invoice-btn")).toBeNull();
});
