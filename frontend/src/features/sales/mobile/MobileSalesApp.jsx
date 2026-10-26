import { useEffect, useState } from "react";
import { Home, Store, ShoppingCart, ClipboardList, ClipboardCheck } from "lucide-react";
import MobileSalesAdminDesk from "./MobileSalesAdminDesk";
import MobileSalesHome from "./MobileSalesHome";
import MobileCatalog from "./MobileCatalog";
import MobileCart from "./MobileCart";
import MobileOrders from "./MobileOrders";
import MobileMore from "./MobileMore";
import MobileShell from "../../mobile/MobileShell";
import { notifLink } from "../../mobile/notifText";
import { roleIs } from "../../../config/roles";
import PosStartGate, { loadPosCtx, savePosCtx } from "../../pos/PosStartGate";
import CreateCustomerModal from "../../pos/CreateCustomerModal";
import { useSites } from "../../../components/SiteSelect";

/**
 * Aplikasi HP Sales & Admin Sales. Fase 3 · P7 (L-09) — memakai kerangka bersama `MobileShell` v2 (app bar, lonceng
 * `NotifSheet`, tab bar + lencana keranjang, tab "Lainnya", sinkron push & muat ulang lonceng di SATU tempat).
 * Dulu menggambar app bar/tab bar sendiri dan memanggil `syncPushSubscription` sendiri.
 */

// Admin Sales mewarisi menu sales (ROLE_NAV) — beda satu: beranda = Meja Admin Sales.
// link notifikasi (id view desktop) → layar HP.
const NOTIF_SUB = { "internal-requests": "internal", "special-orders": "special", "price-approvals": "price-status", "sales-returns": "returns",
  returns: "returns", amendments: "amendments", "customers-crm": "crm", crm: "crm", "sample-orders": "sample-orders", leads: "leads", "crm-leads": "leads" };
const NOTIF_ORDERS = ["orders", "pending-so", "sales-orders", "sales"];

export default function MobileSalesApp(props) {
  const {
    user, token, onLogout, data, loading, cart, setCart,
    onInspect, onAdd, selectedCustomer, setSelectedCustomer,
    selectedAddress, setSelectedAddress, onSubmitOrder, paymentTerms,
    selectedEntity, entities, onForceDesktop, allowRollPick = true, initialSub = null, onOpenFull, onRefresh, onSelectEntity,
    settings, onCreateCustomer, notice = "",
  } = props;
  const isAdmin = roleIs(user?.role, ["sales_admin"]);   // Sisir gerbang peran (2026-10-20) — tata letak meja Admin Sales (peran acuan dikenali)
  const [orderFocus, setOrderFocus] = useState(null);
  const [subParam, setSubParam] = useState(null);

  // Pintasan PWA (?m=orders|catalog|cart|more) & klik notifikasi push (?notif=…) — tetap berlaku di kerangka v2.
  const urlParams = new URLSearchParams(window.location.search);
  const urlTab = ["orders", "catalog", "cart", "more"].includes(urlParams.get("m")) ? urlParams.get("m") : null;
  const [tab, setTab] = useState(initialSub ? "more" : urlTab || "home");
  const [moreSub, setMoreSub] = useState(initialSub);
  const openOrder = (id) => { setOrderFocus(id); setTab("orders"); };
  const openSubWith = (s, param) => { setSubParam(param || null); setMoreSub(s); setTab("more"); };
  // UAT 24 Okt (P8) — konteks jualan (lokasi + pelanggan) bersama dengan POS desktop (sessionStorage).
  const [siteId, setSiteId] = useState(() => loadPosCtx().site_id || "");
  const [gateForce, setGateForce] = useState(false);
  const [newCustOpen, setNewCustOpen] = useState(false);
  const sites = useSites();
  const siteName = (sites.find((x) => x.id === siteId) || {}).name || "";

  // Lonceng (kerangka v2): tautan notifikasi → layar HP bila ada, selain itu tampilan penuh. false = lembar tetap.
  const openNotif = (n) => {
    const link = notifLink(n);
    if (!link) return false;
    if (n.type === "turn" && isAdmin) { setTab("home"); return true; }
    if (NOTIF_ORDERS.includes(link)) { if (String(n.action_id || "").startsWith("so_")) openOrder(n.action_id); else setTab("orders"); return true; }
    if (NOTIF_SUB[link]) { openSubWith(NOTIF_SUB[link], n.action_id ? { id: n.action_id } : null); return true; }
    onOpenFull?.(link, link);
    return true;
  };
  const openSub = (s) => { setSubParam(null); setMoreSub(s); setTab("more"); };
  useEffect(() => { if (initialSub) openSub(initialSub); }, [initialSub]);   // eslint-disable-line react-hooks/exhaustive-deps

  const cartCount = (cart || []).length;   // L01 — jumlah BARIS, bukan qty
  const goCatalog = () => setTab("catalog");
  const gated = gateForce || !siteId || !selectedCustomer;

  const home = isAdmin
    ? { id: "home", label: "Meja", icon: ClipboardCheck, render: () => (
      <MobileSalesAdminDesk selectedEntity={selectedEntity} onOpenOrder={openOrder}
        onOpenSub={(s, id) => openSubWith(s, { id })} onOpenFull={onOpenFull} />) }
    : { id: "home", label: "Beranda", icon: Home, render: () => (
      <MobileSalesHome token={token} user={user} onNewOrder={goCatalog} onOpenTab={setTab} onAskKn={() => openSub("tanya")}
        onOpenSub={openSub} onOpenSubWith={openSubWith} onOpenFull={onOpenFull} onOpenDocument={props.onOpenDocument} onOpenOrder={openOrder} selectedEntity={selectedEntity} />) };
  const catalog = { id: "catalog", label: "Katalog", icon: Store, flush: true, render: () => (gated ? (
    <div className="p-3">
      {/* UAT 24 Okt (P8) — "Mulai jualan": lokasi + pelanggan dulu, baru katalog. */}
      <PosStartGate user={user} customers={data?.customers || []} initialSiteId={siteId}
        initialCustomerId={selectedCustomer?.id || loadPosCtx().customer_id || ""} testPrefix="m-pos-gate"
        onCreateCustomer={onCreateCustomer ? () => setNewCustOpen(true) : null}
        onStart={({ siteId: sid, customer }) => {
          setSiteId(sid); setSelectedCustomer?.(customer); setSelectedAddress?.(customer?.addresses?.[0]?.id || "");
          savePosCtx({ site_id: sid, customer_id: customer.id }); setGateForce(false);
        }} />
      {/* D-05 — form pelanggan LENGKAP (CustomerFormModal lewat CreateCustomerModal), layar penuh di HP. */}
      <CreateCustomerModal open={newCustOpen} onClose={() => setNewCustOpen(false)} user={user} selectedEntity={selectedEntity}
        onCreateCustomer={async (c) => { await onCreateCustomer(c); setNewCustOpen(false); }} />
    </div>
  ) : (
    <MobileCatalog data={data} loading={loading} onAdd={onAdd} onInspect={onInspect}
      entityId={selectedEntity} cart={cart} onOpenCart={() => setTab("cart")}
      allowRollPick={allowRollPick}
      selectedCustomer={selectedCustomer} siteId={siteId} siteName={siteName} onChangeContext={() => setGateForce(true)}
      onSelectCustomer={(c) => { setSelectedCustomer?.(c); setSelectedAddress?.(c?.addresses?.[0]?.id || ""); savePosCtx({ site_id: siteId, customer_id: c?.id || "" }); }} />
  )) };
  const tabs = [
    home,
    catalog,
    { id: "cart", label: "Keranjang", icon: ShoppingCart, badge: cartCount, badgeTestId: "mobile-tab-cart-count", render: () => (
      <MobileCart cart={cart} setCart={setCart} data={data}
        selectedCustomer={selectedCustomer} setSelectedCustomer={setSelectedCustomer}
        selectedAddress={selectedAddress} setSelectedAddress={setSelectedAddress}
        paymentTerms={paymentTerms} onSubmitOrder={(extra = {}) => onSubmitOrder({ ...extra, fulfillment_site_id: siteId })} onAdd={onAdd} user={user} onRefresh={onRefresh}
        settings={settings} onCreateCustomer={onCreateCustomer}
        entityId={selectedEntity} onBrowse={goCatalog} onDone={() => setTab("orders")} />) },
    { id: "orders", label: "Pesanan", icon: ClipboardList, render: () => (
      <MobileOrders orders={data?.orders || []} loading={loading} onBrowse={goCatalog} onRefresh={onRefresh}
        role={user?.role} user={user} focusId={orderFocus} onReturn={(o) => openSubWith("returns", { order: o })} onDashboard={() => openSub("order-dashboard")} />) },
  ];
  // Tab terakhir baku "Lainnya" = menu HP Sales + MobileAccountMenu (profil, PT, push, satu "Tampilan desktop", Keluar).
  const moreTab = { render: () => (
    <MobileMore onOpenOrder={openOrder} user={user} token={token} selectedEntity={selectedEntity} entities={entities} orders={data?.orders || []} onRefresh={onRefresh}
      onLogout={onLogout} onForceDesktop={onForceDesktop} sub={moreSub} setSub={(s) => { setSubParam(null); setMoreSub(s); }} onOpenFull={onOpenFull}
      subParam={subParam} onSelectEntity={onSelectEntity}
      onStartOrder={(c) => { setSelectedCustomer?.(c); setSelectedAddress?.(c?.addresses?.[0]?.id || ""); setTab("catalog"); }} />) };
  const topSlot = notice && !/^(Sistem siap|Login berhasil)/.test(notice)
    ? <div data-testid="mobile-sales-notice" className="mb-2 rounded-lg border border-[#CBDFFF] bg-[#F2F7FF] px-3 py-2 text-[11.5px] text-[#31465F]">{notice}</div> : null;

  return (
    <MobileShell {...props} tabs={tabs} moreTab={moreTab} tab={tab} testId="mobile-sales-app" topSlot={topSlot}
      onTabChange={(id) => { if (id !== "orders") setOrderFocus(null); setTab(id); }}
      onOpenNotif={openNotif} initialNotifOpen={!!urlParams.get("notif")} />
  );
}
