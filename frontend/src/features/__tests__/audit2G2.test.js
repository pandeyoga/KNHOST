// UAT 24 Okt (audit UI tahap 2) — G2: helper teks penjualan (harga khusus, status SO, lencana Meja Saya, label CRM)
// + perilaku layar: pop-up Pelanggan Baru (G2-01/G2-22) dan kartu SO batal di HP (G2-20).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CreateCustomerModal from "../pos/CreateCustomerModal";
import MobileOrders from "../sales/mobile/MobileOrders";
import { discountInfo, requesterName, deciderName, customerOptionLabel } from "../sales/priceApprovals/priceApprovalText";
import { visibleSubs, isClosedSo, lotModeLabel, allocationExplain } from "../orders/soStatusView";
import { badgeLabel } from "../sales_admin/workDeskApi";
import { paymentMethodLabel, payStatusLabel, lotPolicyLabel } from "../crm/crmUtils";

jest.mock("../../services/apiClient", () => ({ __esModule: true, default: { get: () => Promise.resolve({ data: [] }), post: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } } }, API: "/api" }));
jest.mock("../sales/mobile/MobileOrderJourney", () => () => null);
jest.mock("../sales/mobile/MobilePendingQueue", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  return { host, root };
}

test("G2-02: harga di atas normal tidak lagi '−-3064%'", () => {
  expect(discountInfo(-3064.1)).toEqual({ above: true, short: "+3.064%", long: "+3.064% di atas harga normal" });
  expect(discountInfo(12.5)).toEqual({ above: false, short: "−12,5%", long: "−12,5%" });
  expect(discountInfo(0)).toBeNull();
});

test("G2-02/G2-14: nama pengaju & pemutus", () => {
  // pengajuan dari SO/checkout menyimpan nama di `requested_by` (+ requested_by_id)
  expect(requesterName({ requested_by: "Ayu Marketing", requested_by_id: "user_sales_01" })).toBe("Ayu Marketing");
  expect(requesterName({ requested_by: "user_admin_01", requested_by_name: "Budi Santoso" })).toBe("Budi Santoso");
  expect(requesterName({ requested_by: "user_admin_01" })).toBe("—");
  expect(deciderName({ approved_by_name: "sistem (KLR-05)", source: "return_replacement" })).toBe("Sistem (harga asal retur)");
  expect(deciderName({ approved_by_name: "Dewi Manager" })).toBe("Dewi Manager");
  expect(deciderName({ approved_by_name: "sistem (KLR-05)" })).not.toMatch(/KLR/);
  expect(customerOptionLabel({ name: "Toko A", code: "CUST-0012", city: "Bandung" })).toBe("Toko A · CUST-0012 · Bandung");
});

test("G2-06/G2-20: sub-status yang sama dengan tahap tidak diulang", () => {
  expect(visibleSubs({ status: "cancelled" })).toEqual([]);
  expect(visibleSubs({ status: "waiting_stock" })).toEqual(["menunggu_stok"]);
  expect(isClosedSo({ status: "expired" })).toBe(true);
  expect(isClosedSo({ status: "reserved" })).toBe(false);
  expect(lotModeLabel("prefer_single")).toBe("Utamakan satu lot");
  expect(allocationExplain("1.09 dari Lot KSC/LOT-2610-0201 (FEFO)", "meter")).toBe("1,09 meter dari Lot KSC/LOT-2610-0201 (FEFO)");
});

test("G2-13: lencana keparahan Meja Saya berbahasa Indonesia", () => {
  expect(badgeLabel("warning")).toBe("Perlu perhatian");
  expect(badgeLabel("info")).toBe("Info");
  expect(badgeLabel("critical")).toBe("Mendesak");
  expect(badgeLabel("created")).toBe("Siap diambil");
});

test("G2-08/G2-09: label metode bayar, status bayar & kebijakan lot", () => {
  expect(paymentMethodLabel("tempo")).toBe("Tempo (kredit)");
  expect(paymentMethodLabel("tunai")).toBe("Tunai");
  expect(payStatusLabel("pending")).toBe("Belum bayar");
  expect(payStatusLabel("paid")).toBe("Lunas");
  expect(lotPolicyLabel("")).toBe("Bawaan (utamakan satu lot)");
});

test("G2-01/G2-22: pop-up Pelanggan Baru — isi bergulir di dalam kartu, label & 'Buat Pelanggan', kekurangan tampil", async () => {
  const { host, root } = await mount(<CreateCustomerModal open onClose={() => {}} onCreateCustomer={() => Promise.resolve()} user={{ role: "sales", name: "Ayu" }} />);
  expect(q(host, "create-customer-body").className).toMatch(/overflow-y-auto/);
  expect(host.textContent).toMatch(/No\. HP \/ WhatsApp PIC/);
  expect(host.textContent).not.toMatch(/Customer/);
  const btn = q(host, "create-customer-button");
  expect(btn.textContent).toMatch(/Buat Pelanggan/);
  await act(async () => { btn.click(); });
  expect(q(host, "create-customer-missing").textContent).toMatch(/nama toko/);
  await act(async () => { root.unmount(); });
});

test("G2-20: kartu SO batal di HP — status sekali, tanpa status bayar", async () => {
  const order = { id: "so9", number: "KSC/SO-00420", status: "cancelled", customer_name: "Toko", payment_status: "unpaid",
    items: [{ product_id: "p1", product_name: "Ceruty", quantity: 24.78, unit: "yard", price: 1000 }] };
  const { host, root } = await mount(<MobileOrders orders={[order]} role="sales" />);
  expect(host.querySelector('[data-testid^="mobile-order-sub-so9-"]')).toBeNull();     // dulu chip "Dibatalkan" kedua
  expect(q(host, "mobile-order-meta-so9").textContent).not.toMatch(/bayar/);
  await act(async () => { root.unmount(); });
});
