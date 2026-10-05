import { useEffect, useState } from "react";
import { Home, Store, ShoppingCart, ClipboardList, Menu, Bell, Layers, X, CheckCheck, ClipboardCheck } from "lucide-react";
import MobileSalesAdminDesk from "./MobileSalesAdminDesk";
import { syncPushSubscription } from "./MobilePwa";
import MobileSalesHome from "./MobileSalesHome";
import MobileCatalog from "./MobileCatalog";
import MobileCart from "./MobileCart";
import OfflineBanner from "../../mobile/OfflineBanner";
import MobileOrders from "./MobileOrders";
import MobileMore from "./MobileMore";
import { entityShortById } from "../../../utils/entityLabel";

// Admin Sales mewarisi menu sales (ROLE_NAV) — beda satu: beranda = Meja Admin Sales.
const ChevronRightIcon = () => <span className="self-center text-[#C7C7CC]">›</span>;
// link notifikasi (id view desktop) → layar HP.
const NOTIF_SUB = { "internal-requests": "internal", "special-orders": "special", "price-approvals": "price-status", "sales-returns": "returns",
  returns: "returns", amendments: "amendments", "customers-crm": "crm", crm: "crm", "sample-orders": "sample-orders", leads: "leads", "crm-leads": "leads" };
const NOTIF_ORDERS = ["orders", "pending-so", "sales-orders", "sales"];
const DESK_TAB = { id: "home", label: "Meja", icon: ClipboardCheck };
const TABS = [
  { id: "home", label: "Beranda", icon: Home },
  { id: "catalog", label: "Katalog", icon: Store },
  { id: "cart", label: "Keranjang", icon: ShoppingCart },
  { id: "orders", label: "Pesanan", icon: ClipboardList },
  { id: "more", label: "Lainnya", icon: Menu },
];

const fmtAgo = (s) => {
  if (!s) return "";
  const m = Math.max(0, Math.round((Date.now() - new Date(s).getTime()) / 60000));
  if (m < 1) return "baru saja";
  if (m < 60) return `${m} mnt lalu`;
  if (m < 1440) return `${Math.round(m / 60)} jam lalu`;
  return new Date(s).toLocaleDateString("id-ID", { day: "2-digit", month: "short" });
};

export function NotifSheet({ notifications, onClose, onMarkAll, onOpen }) {
  return (
    <div className="m-sheet-wrap" data-testid="mobile-notif-sheet">
      <div className="m-sheet-backdrop" onClick={onClose} />
      <div className="m-sheet">
        <div className="m-sheet-grip" />
        <div className="flex items-center justify-between px-4 py-2 border-b border-[#EFF0F2]">
          <h3 className="m-section-title">Notifikasi</h3>
          <div className="flex items-center gap-2">
            {onMarkAll && notifications.length > 0 && (
              <button data-testid="mobile-notif-markall" onClick={onMarkAll} className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#0058CC]"><CheckCheck size={14} /> Tandai dibaca</button>
            )}
            <button onClick={onClose} aria-label="Tutup" className="text-[#6B6B73]" data-testid="mobile-notif-close"><X size={18} /></button>
          </div>
        </div>
        <div className="overflow-y-auto px-4 py-2" style={{ maxHeight: "60vh" }}>
          {notifications.length === 0 ? (
            <div className="py-12 text-center text-[13px] m-muted">Belum ada notifikasi.</div>
          ) : notifications.map((n) => (
            <button key={n.id} type="button" className="m-list-row m-press w-full text-left" onClick={() => onOpen?.(n)} data-testid={`mobile-notif-${n.id}`}>
              <span className={`mt-1 h-2 w-2 flex-shrink-0 rounded-full ${n.read ? "bg-[#D6D7DC]" : n.severity === "critical" ? "bg-[#FF3B30]" : "bg-[#0058CC]"}`} />
              <div className="min-w-0 flex-1">
                <p className={`text-[12.5px] leading-tight ${n.read ? "font-medium text-[#3C3C43]" : "font-semibold"}`}>{n.title || n.type}</p>
                {n.body && <p className="text-[11.5px] m-muted leading-snug mt-0.5">{n.body}</p>}
                <p className="mt-0.5 text-[10px] text-[#AEAEB2]">{fmtAgo(n.created_at)}</p>
              </div>
              {n.link && <ChevronRightIcon />}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function MobileSalesApp(props) {
  const {
    user, token, onLogout, data, loading, cart, setCart,
    onInspect, onAdd, selectedCustomer, setSelectedCustomer,
    selectedAddress, setSelectedAddress, onSubmitOrder, paymentTerms,
    selectedEntity, entities, notifications = [], unreadCount = 0,
    onMarkAllRead, onForceDesktop, allowRollPick = true, initialSub = null, onOpenFull, onRefresh, onSelectEntity,
    onPollNotifications, onMarkRead,
  } = props;
  const isAdmin = user?.role === "sales_admin";
  const tabs = isAdmin ? [DESK_TAB, ...TABS.slice(1)] : TABS;
  const [orderFocus, setOrderFocus] = useState(null);
  const [subParam, setSubParam] = useState(null);
  const openOrder = (id) => { setOrderFocus(id); setTab("orders"); };
  const openSubWith = (s, param) => { setSubParam(param || null); setMoreSub(s); setTab("more"); };

  // Pintasan PWA (?m=orders|catalog|cart|more) & klik notifikasi push (?notif=…).
  const urlParams = new URLSearchParams(window.location.search);
  const urlTab = ["orders", "catalog", "cart", "more"].includes(urlParams.get("m")) ? urlParams.get("m") : null;
  const [tab, setTab] = useState(initialSub ? "more" : urlTab || "home");
  const [moreSub, setMoreSub] = useState(initialSub);
  const [notifOpen, setNotifOpen] = useState(!!urlParams.get("notif"));

  // Lonceng HP: muat ulang tiap 60 dtk saat layar terlihat, saat kembali ke aplikasi,
  // dan seketika saat push masuk (pesan dari service worker).
  useEffect(() => {
    if (!onPollNotifications) return undefined;
    const tick = () => { if (document.visibilityState === "visible") onPollNotifications(); };
    tick();
    const id = setInterval(tick, 60000);
    document.addEventListener("visibilitychange", tick);
    const onMsg = (e) => {
      if (e.data?.type === "kn-push") onPollNotifications();
      if (e.data?.type === "kn-push-open") { onPollNotifications(); setNotifOpen(true); }
    };
    navigator.serviceWorker?.addEventListener?.("message", onMsg);
    return () => { clearInterval(id); document.removeEventListener("visibilitychange", tick); navigator.serviceWorker?.removeEventListener?.("message", onMsg); };
  }, [onPollNotifications]);
  useEffect(() => { syncPushSubscription(); }, [user?.id]);

  const openNotif = (n) => {
    if (!n.read) onMarkRead?.(n.id);
    const link = String(n.link || "").replace(/^\/?(\?view=)?/, "");
    if (!link) return;
    setNotifOpen(false);
    if (n.type === "turn" && isAdmin) { setTab("home"); return; }
    if (NOTIF_ORDERS.includes(link)) { if (String(n.action_id || "").startsWith("so_")) openOrder(n.action_id); else setTab("orders"); return; }
    if (NOTIF_SUB[link]) { openSubWith(NOTIF_SUB[link], n.action_id ? { id: n.action_id } : null); return; }
    onOpenFull?.(link, link);
  };
  const openSub = (s) => { setSubParam(null); setMoreSub(s); setTab("more"); };
  useEffect(() => { if (initialSub) openSub(initialSub); }, [initialSub]);

  const cartCount = (cart || []).reduce((s, it) => s + Number(it.quantity || 0), 0);
  // `/api/entities` tak punya field `name` — pakai resolver bersama supaya
  // header POS mobile tidak pernah menampilkan id teknis (`ent_ksc`).
  const entityName = entityShortById(entities, selectedEntity);

  const goCatalog = () => setTab("catalog");

  return (
    <div className="m-shell" data-testid="mobile-sales-app">
      <header className="m-appbar">
        <div className="m-brand-mark"><Layers size={16} /></div>
        <div className="m-title">
          <span className="t1">Halo, {(user?.name || "Sales").split(" ")[0]}{isAdmin ? " · Admin Sales" : ""}</span>
          <span className="t2">{entityName}</span>
        </div>
        <button className="m-act" data-testid="mobile-notif-btn" onClick={() => setNotifOpen(true)} aria-label="Notifikasi">
          <Bell size={18} />
          {unreadCount > 0 && <span className="m-badge">{unreadCount > 9 ? "9+" : unreadCount}</span>}
        </button>
      </header>

      {notifOpen && <NotifSheet notifications={notifications} onClose={() => setNotifOpen(false)} onMarkAll={onMarkAllRead} onOpen={openNotif} />}

      <main className={`m-main ${tab === "catalog" ? "m-flush" : ""}`} data-testid={`mobile-view-${tab}`}>
        <OfflineBanner />
        {tab === "home" && !isAdmin && <MobileSalesHome token={token} user={user} onNewOrder={goCatalog} onOpenTab={setTab} onAskKn={() => openSub("tanya")} onOpenSub={openSub} onOpenFull={onOpenFull} />}
        {tab === "home" && isAdmin && (
          <MobileSalesAdminDesk selectedEntity={selectedEntity} onOpenOrder={openOrder}
            onOpenSub={(s, id) => openSubWith(s, { id })} onOpenFull={onOpenFull} />
        )}
        {tab === "catalog" && (
          <MobileCatalog data={data} loading={loading} onAdd={onAdd} onInspect={onInspect}
            entityId={selectedEntity} cart={cart} onOpenCart={() => setTab("cart")}
            allowRollPick={allowRollPick}
            selectedCustomer={selectedCustomer} />
        )}
        {tab === "cart" && (
          <MobileCart cart={cart} setCart={setCart} data={data}
            selectedCustomer={selectedCustomer} setSelectedCustomer={setSelectedCustomer}
            selectedAddress={selectedAddress} setSelectedAddress={setSelectedAddress}
            paymentTerms={paymentTerms} onSubmitOrder={onSubmitOrder} onAdd={onAdd} user={user} onRefresh={onRefresh}
            entityId={selectedEntity} onBrowse={goCatalog} onDone={() => setTab("orders")} />
        )}
        {tab === "orders" && <MobileOrders orders={data?.orders || []} loading={loading} onBrowse={goCatalog} onRefresh={onRefresh}
          role={user?.role} focusId={orderFocus} onReturn={(o) => openSubWith("returns", { order: o })} />}
        {tab === "more" && (
          <MobileMore user={user} token={token} selectedEntity={selectedEntity} entities={entities} orders={data?.orders || []} onRefresh={onRefresh}
            onLogout={onLogout} onForceDesktop={onForceDesktop} sub={moreSub} setSub={(s) => { setSubParam(null); setMoreSub(s); }} onOpenFull={onOpenFull}
            subParam={subParam} onSelectEntity={onSelectEntity}
            onStartOrder={(c) => { setSelectedCustomer?.(c); setSelectedAddress?.(c?.addresses?.[0]?.id || ""); setTab("catalog"); }} />
        )}
      </main>

      <nav className="m-tabbar" data-testid="mobile-tabbar">
        {tabs.map((t) => {
          const Icon = t.icon;
          const active = tab === t.id;
          return (
            <button key={t.id} data-testid={`mobile-tab-btn-${t.id}`} className={`m-tab ${active ? "active" : ""}`} onClick={() => { if (t.id !== "orders") setOrderFocus(null); setTab(t.id); }} aria-current={active}>
              <span className="m-tab-ico">
                <Icon size={21} strokeWidth={active ? 2.4 : 2} />
                {t.id === "cart" && cartCount > 0 && (
                  <span className="m-tab-badge" data-testid="mobile-tab-cart-count">{cartCount > 99 ? "99+" : cartCount}</span>
                )}
              </span>
              {t.label}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
