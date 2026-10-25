/**
 * MobileAppSwitch — pemilih aplikasi HP per peran (dulu blok percabangan di `App.js`).
 *
 * Fase 3 · P1 — DIEKSTRAK apa adanya dari App.js (batas 500 baris) supaya paket P7 (satu kerangka
 * aplikasi HP, L-09) mengubah berkas di wilayahnya sendiri (`features/mobile/**`) alih-alih App.js.
 * Dirender App.js hanya bila `wantMobile && !responsiveWorkspace`; perilakunya sama persis:
 *  · MD / Merchandiser → MobileMdApp (Meja MD, desain, sample, produk, PR);
 *  · bukan peran sales → gudang (warehouse, warehouse_admin, driver) MobileWarehouseApp, selain itu MobileOpsApp;
 *  · sales & Admin Sales (mewarisi wilayah sales) → MobileSalesApp.
 */
import MobileSalesApp from "../sales/mobile/MobileSalesApp";
import MobileMdApp from "../sales/mobile/MobileMdApp";
import MobileWarehouseApp from "./MobileWarehouseApp";
import MobileOpsApp from "./MobileOpsApp";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { roleIs } from "../../config/roles";

export default function MobileAppSwitch({
  user, token, entities, selectedEntity, onSelectEntity,
  notifications, unreadCount, notifProps, onMarkAllRead, onMarkRead, onPollNotifications,
  onOpenFull, onLogout, onForceDesktop, onNavigate, wantsTanya,
  // MobileSalesApp
  actions, settings, data, loading, cart, setCart, selectedCustomer, setSelectedCustomer,
  selectedAddress, setSelectedAddress, notice, paymentTerms,
}) {
  // Admin Sales mewarisi wilayah kerja sales (ROLE_NAV) → aplikasi HP sales + Meja Admin Sales.
  const salesMobileRole = roleIs(user.role, ["sales", "sales_admin"]);   // Sisir lanjutan gerbang peran (2026-10-21) — tata letak, peran acuan dikenali
  // MD / Merchandiser → aplikasi HP khusus (Meja MD, desain, sample, produk, PR).
  if (roleIs(user.role, ["md"])) {
    return (
      <MobileMdApp user={user} entities={entities} selectedEntity={selectedEntity}
        notifications={notifications} unreadCount={unreadCount} onMarkAllRead={onMarkAllRead}
        onMarkRead={onMarkRead} onPollNotifications={onPollNotifications} notifProps={notifProps}
        onOpenFull={onOpenFull} onLogout={onLogout} onForceDesktop={onForceDesktop} onSelectEntity={onSelectEntity} />
    );
  }
  if (!salesMobileRole) {
    const MobileApp = roleIs(user.role, ["warehouse", "warehouse_admin", "driver"]) ? MobileWarehouseApp : MobileOpsApp;
    return <MobileApp user={user} onLogout={onLogout} entities={entities} selectedEntity={selectedEntity}
      unreadCount={unreadCount} onForceDesktop={onForceDesktop} onNavigate={onNavigate} onOpenFull={onOpenFull}
      initialTab={wantsTanya && MobileApp === MobileOpsApp ? "tanya" : undefined} />;
  }
  return (
    <EntityScopeProvider selectedEntity={selectedEntity} entities={entities} canSwitch pickEntity={onSelectEntity}>
    <MobileSalesApp
      initialSub={wantsTanya ? "tanya" : null}
      onOpenFull={onOpenFull}
      onRefresh={actions.loadAll}
      user={user}
      token={token}
      onLogout={onLogout}
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
      selectedEntity={selectedEntity}
      entities={entities}
      notifications={notifications}
      unreadCount={unreadCount}
      onMarkAllRead={onMarkAllRead}
      onMarkRead={onMarkRead}
      onPollNotifications={onPollNotifications}
      notifProps={notifProps}
      onSelectEntity={onSelectEntity}
      onForceDesktop={onForceDesktop}
    />
    </EntityScopeProvider>
  );
}
