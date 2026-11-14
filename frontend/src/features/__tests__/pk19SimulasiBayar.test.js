// PK-19 (SL-05, IA-07) — "Simulasi Pembayaran" dimatikan: rincian pesanan tidak lagi menampilkan tombol simulasi
// walau pesanan terkonfirmasi, belum lunas, dan pengguna berizin menerima uang (`ar_receipt.create`). Pembayaran
// pesanan dicatat lewat kwitansi. Tombol lain di bilah aksi (Faktur, Surat Jalan) tetap.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { OrderDetailPanel } from "../orders/OrderDetailPanel";

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
// Panel anak detail SO yang memuat data sendiri — di luar cakupan uji ini.
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
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  return host;
}

afterEach(() => { document.body.innerHTML = ""; });

const SO = {
  id: "so_pk19", number: "KSC/SO-PK19", customer_name: "Toko Uji PK19", status: "confirmed", entity_id: "ent_ksc",
  payment_status: "unpaid", items: [{ product_id: "p1", product_name: "Kain A", sku: "A", quantity: 10, unit: "yard",
    price: 10000 }], total_amount: 100000, net_subtotal: 100000, grand_total: 100000, ppn_amount: 0, is_pkp: false,
  created_at: "2026-11-14T03:00:00Z",
};

test("PK-19 U17 (layar): tombol Simulasi Pembayaran tidak ada untuk pesanan terkonfirmasi yang belum lunas", async () => {
  mockGet.mockImplementation(() => Promise.resolve({ data: [] }));   // CRA `resetMocks` — pasang di dalam uji
  const user = { role: "admin", permissions: { ar_receipt: ["create", "view"], order: ["view"] } };
  const host = await mount(<OrderDetailPanel order={SO} user={user} embedded onGenerateDocument={() => {}} />);
  expect(host.querySelector(`[data-testid="simulate-payment-button-${SO.id}"]`)).toBeNull();
  expect(host.textContent).not.toContain("Simulasi Pembayaran");
  expect(host.querySelector(`[data-testid="generate-invoice-button-${SO.id}"]`)).not.toBeNull();
});
