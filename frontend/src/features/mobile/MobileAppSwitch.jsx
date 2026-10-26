/**
 * MobileAppSwitch — pemilih aplikasi HP per peran (dulu blok percabangan di `App.js`).
 *
 * Fase 3 · P1 — DIEKSTRAK apa adanya dari App.js (batas 500 baris) supaya paket P7 (satu kerangka
 * aplikasi HP, L-09) mengubah berkas di wilayahnya sendiri (`features/mobile/**`) alih-alih App.js.
 * Dirender App.js hanya bila `wantMobile && !responsiveWorkspace`:
 *  · MD / Merchandiser → MobileMdApp (Meja MD, desain, sample, produk, PR);
 *  · bukan peran sales → gudang (warehouse, warehouse_admin, driver) MobileWarehouseApp, selain itu MobileOpsApp;
 *  · sales & Admin Sales (mewarisi wilayah sales) → MobileSalesApp.
 *
 * Fase 3 · P7 (L-09) — keempat aplikasi memakai `MobileShell` v2, jadi SEMUA menerima set props kerangka yang sama:
 * lonceng (notifikasi, tandai dibaca, muat ulang), pengalih PT (`onSelectEntity`), "Tampilan desktop", Keluar, dan
 * tampilan penuh (`onOpenFull(navId, view, { preset, tab })`). Dulu Ops/Gudang tidak menerima notifikasi & PT.
 * Semua aplikasi dibungkus `EntityScopeProvider` + `AppNavProvider` supaya komponen desktop yang dipakai ulang di HP
 * (form pelanggan, Permintaan Internal, kartu tautan) memakai PT header & membuka layar tujuan sebagai tampilan penuh.
 */
import MobileSalesApp from "../sales/mobile/MobileSalesApp";
import MobileMdApp from "../sales/mobile/MobileMdApp";
import MobileWarehouseApp from "./MobileWarehouseApp";
import MobileOpsApp from "./MobileOpsApp";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { AppNavProvider } from "../../context/AppNavContext";
import { roleIs } from "../../config/roles";

export default function MobileAppSwitch({
  user, token, entities, selectedEntity, onSelectEntity,
  notifications, unreadCount, notifProps, onMarkAllRead, onMarkRead, onPollNotifications,
  onOpenFull, onOpenDocument, onNavigateTo, onLogout, onForceDesktop, onNavigate, wantsTanya,
  // MobileSalesApp
  actions, settings, data, loading, cart, setCart, selectedCustomer, setSelectedCustomer,
  selectedAddress, setSelectedAddress, notice, paymentTerms,
}) {
  // Props kerangka HP — identik untuk keempat aplikasi.
  const shell = {
    user, entities, selectedEntity, onSelectEntity,
    notifications, unreadCount, notifProps, onMarkAllRead, onMarkRead, onPollNotifications,
    onOpenFull, onOpenDocument, onLogout, onForceDesktop,
  };
  const wrap = (app) => (
    <EntityScopeProvider selectedEntity={selectedEntity} entities={entities} canSwitch pickEntity={onSelectEntity}>
      <AppNavProvider role={user?.role} onNavigateTo={onNavigateTo} onOpenDocument={onOpenDocument}>{app}</AppNavProvider>
    </EntityScopeProvider>
  );
  // Admin Sales mewarisi wilayah kerja sales (ROLE_NAV) → aplikasi HP sales + Meja Admin Sales.
  const salesMobileRole = roleIs(user.role, ["sales", "sales_admin"]);   // Sisir lanjutan gerbang peran (2026-10-21) — tata letak, peran acuan dikenali
  // MD / Merchandiser → aplikasi HP khusus (Meja MD, desain, sample, produk, PR).
  if (roleIs(user.role, ["md"])) return wrap(<MobileMdApp {...shell} />);
  if (!salesMobileRole) {
    const MobileApp = roleIs(user.role, ["warehouse", "warehouse_admin", "driver"]) ? MobileWarehouseApp : MobileOpsApp;
    return wrap(<MobileApp {...shell} onNavigate={onNavigate}
      initialTab={wantsTanya && MobileApp === MobileOpsApp ? "tanya" : undefined} />);
  }
  return wrap(
    <MobileSalesApp
      {...shell}
      initialSub={wantsTanya ? "tanya" : null}
      onRefresh={actions.loadAll}
      token={token}
      allowRollPick={settings?.allocation?.roll_pick_sales !== false}
      data={data}
      loading={loading}
      cart={cart}
      setCart={setCart}
      onInspect={actions.inspectProduct}
      onAdd={actions.addToCart}
      selectedCustomer={selectedCustomer}
      setSelectedCustomer={setSelectedCustomer}
      selectedAddress={selectedAddress}
      setSelectedAddress={setSelectedAddress}
      onSubmitOrder={actions.submitOrder}
      onCreateCustomer={actions.createCustomer}
      settings={settings}
      notice={notice}
      paymentTerms={paymentTerms}
    />,
  );
}
