// Cek UI UAT v3 (2026-10-22) — Gudang punya izin makloon_order.issue & tab "Order Makloon", tetapi induk
// "Pesanan Pembelian" tertutup untuk gudang → pengeluaran bahan makloon tidak bisa dibuka dari menu.
import { buildNavGroups, hubTabsForRole } from "../../config/navigationConfig";

const item = (role, id) => buildNavGroups(role).flatMap((g) => (g.type === "group" ? g.items : [g])).find((i) => i.id === id);

test.each(["warehouse", "warehouse_admin"])("%s melihat Pembelian › Pesanan Pembelian › Order Makloon", (role) => {
  const po = item(role, "purchase-orders");
  expect(po).toBeTruthy();                                                   // dulu: tidak ada
  const tabs = hubTabsForRole("purchase-orders", role).map((t) => t.view);
  expect(tabs).toEqual(expect.arrayContaining(["makloon-orders", "makloon-claims"]));
  expect(tabs).not.toContain("purchasing");                                 // tab PO tetap tertutup untuk gudang
});

// Fase 3 · P8 (D-22) — gudang dulu melihat skor mitra di Klaim Selisih Makloon; kini satu layar "Kinerja Mitra Makloon"
// (rekap + skor) di hub yang sama. Admin Gudang mewarisi menu gudang.
test.each(["warehouse", "warehouse_admin"])("%s melihat tab Kinerja Mitra Makloon", (role) => {
  const recap = hubTabsForRole("purchase-orders", role).find((t) => t.view === "makloon-claim-recap");
  expect(recap).toMatchObject({ label: "Kinerja Mitra Makloon" });
});

test("finance & sales tidak berubah", () => {
  expect(item("finance", "purchase-orders")).toBeTruthy();
  expect(item("sales", "purchase-orders")).toBeFalsy();
});
