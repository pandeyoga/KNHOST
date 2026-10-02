/**
 * MobileMdApp — aplikasi HP untuk MD / Merchandiser (dulu jatuh ke inbox generik MobileOpsApp).
 * Tab: Meja · Desain · Sample · Produk · Lainnya. Pola kerangka sama dengan MobileSalesApp
 * (appbar gradient, lonceng interaktif + push, tab bawah); fitur tanpa layar HP khusus dibuka
 * "tampilan penuh" + tombol kembali ke aplikasi HP.
 */
import { useEffect, useState } from "react";
import { Bell, ClipboardList, Palette, FlaskConical, Package, Menu, Layers, ChevronRight, LogOut, Monitor, FileStack, ShoppingBag, Tags, BadgeCheck, Boxes,
  ScrollText, Droplet, Hand, Stamp, BarChart3, Images, LayoutTemplate, FolderTree, Ruler, FileSearch, Truck, SearchCheck, Route, UserCheck, ArrowLeft } from "lucide-react";
import { entityShortById } from "../../../utils/entityLabel";
import { NotifSheet } from "./MobileSalesApp";
import { MobileInstallCard, MobilePushCard, dropPushSubscription, syncPushSubscription } from "./MobilePwa";
import { MobileDesignRequests, MobileMdDesk, MobileMdProducts, MobilePoWatch, MobilePurchaseRequisitions, MobileRndSamples, mdRowTarget } from "./MobileMdViews";
import { MobilePricelist } from "./MobileSalesNative";
import { MobilePriceStatus } from "./MobileExtraViews";
import { MobileStock } from "./MobileFieldViews";

const TABS = [
  { id: "desk", label: "Meja", icon: ClipboardList },
  { id: "design", label: "Desain", icon: Palette },
  { id: "sample", label: "Sample", icon: FlaskConical },
  { id: "products", label: "Produk", icon: Package },
  { id: "more", label: "Lainnya", icon: Menu },
];
const SUBS = [
  { id: "pr", label: "Permintaan Pembelian (PR)", desc: "Ajukan bahan untuk sample & produksi", icon: FileStack },
  { id: "po", label: "Pantau PO Bahan", desc: "Status PO dari PR Anda (hanya-lihat)", icon: ShoppingBag },
  { id: "pricelist", label: "Daftar Harga", desc: "Harga efektif per pelanggan", icon: Tags },
  { id: "price-status", label: "Pengajuan Harga Khusus", desc: "Status harga khusus yang diajukan", icon: BadgeCheck },
  { id: "stock", label: "Status Stok", desc: "Ketersediaan per gudang", icon: Boxes },
];
const FULL = [
  { nav: "rnd-hub", view: "rnd-specs", label: "Spesifikasi Produk", icon: ScrollText },
  { nav: "rnd-hub", view: "rnd-labdip", label: "Riwayat Labdip", icon: Droplet },
  { nav: "rnd-hub", view: "rnd-handfeel", label: "Handfeel", icon: Hand },
  { nav: "rnd-hub", view: "rnd-proofing", label: "Proofing", icon: Stamp },
  { nav: "rnd-hub", view: "rnd-reports", label: "Laporan R&D", icon: BarChart3 },
  { nav: "designer-hub", view: "rnd-designs", label: "Galeri & Studio Desain", icon: Images },
  { nav: "products-pricing", view: "product-templates", label: "Template Produk", icon: LayoutTemplate },
  { nav: "products-pricing", view: "md-categories", label: "Kategori", icon: FolderTree },
  { nav: "products-pricing", view: "color-library", label: "Pustaka Warna", icon: Palette },
  { nav: "products-pricing", view: "md-uoms", label: "Satuan (UoM)", icon: Ruler },
  { nav: "sourcing", view: "rfq", label: "RFQ Supplier", icon: FileSearch },
  { nav: "master-pembelian", view: "suppliers", label: "Supplier", icon: Truck },
  { nav: "gudang", view: "inspections", label: "Inspeksi (acuan sample)", icon: SearchCheck },
  { nav: "document-center", view: "doc-trace", label: "Jejak Dokumen", icon: Route },
  { nav: "hr-my-profile", view: "hr-my-profile", label: "Profil & Kehadiran Saya", icon: UserCheck },
];
const SUB_TITLE = Object.fromEntries(SUBS.map((s) => [s.id, s.label]));

function Row({ icon: Icon, label, desc, onClick, testId }) {
  return (
    <button className="m-list-row m-press w-full text-left" onClick={onClick} data-testid={testId}>
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-[#EAF2FF]"><Icon size={16} className="text-[#0058CC]" /></span>
      <span className="min-w-0 flex-1"><span className="block text-[13px] font-semibold">{label}</span>{desc && <span className="block truncate text-[11px] m-muted">{desc}</span>}</span>
      <ChevronRight size={16} className="text-[#C7C7CC]" />
    </button>
  );
}

function MdMore({ user, entities, selectedEntity, onSelectEntity, sub, setSub, subParam, onOpenFull, onLogout, onForceDesktop }) {
  const switchable = (entities || []).filter((e) => (user?.allowed_entity_ids || []).includes(e.id));
  if (sub) {
    return (
      <div className="space-y-2" data-testid={`m-md-sub-${sub}`}>
        <div className="flex items-center gap-2"><button className="m-subpage-back" onClick={() => setSub(null)} data-testid="m-md-sub-back"><ArrowLeft size={17} /> Kembali</button><span className="m-subpage-title">{SUB_TITLE[sub]}</span></div>
        {sub === "pr" && <MobilePurchaseRequisitions focusId={subParam?.id} />}
        {sub === "po" && <MobilePoWatch />}
        {sub === "pricelist" && <MobilePricelist selectedEntity={selectedEntity} />}
        {sub === "price-status" && <MobilePriceStatus />}
        {sub === "stock" && <MobileStock />}
      </div>
    );
  }
  return (
    <div className="space-y-3" data-testid="m-md-more">
      <div className="m-card flex items-center gap-3 p-4">
        <span className="grid h-12 w-12 place-items-center rounded-full bg-[#0058CC] text-[18px] font-bold text-white">{(user?.name || "M")[0]}</span>
        <div className="min-w-0 flex-1"><p className="truncate text-[15px] font-bold">{user?.name}</p><p className="truncate text-[11.5px] m-muted">{user?.email}</p><p className="text-[10.5px] font-bold uppercase text-[#0058CC]">MD / Merchandiser</p></div>
      </div>
      <MobilePushCard />
      <MobileInstallCard />
      {switchable.length > 1 && onSelectEntity && (
        <div className="m-card p-3" data-testid="m-md-entity-switch">
          <p className="mb-2 text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Badan usaha aktif</p>
          {selectedEntity === "all" && <p className="mb-2 text-[11px] text-[#8A5300]">Mode "Semua" hanya untuk melihat — pilih satu badan usaha untuk mengajukan PR / desain.</p>}
          <div className="flex flex-wrap gap-2">
            {[{ id: "all" }, ...switchable].map((e) => (
              <button key={e.id} onClick={() => onSelectEntity(e.id)} data-testid={`m-md-entity-${e.id}`}
                className={`h-9 rounded-full border px-3 text-[12px] font-semibold ${selectedEntity === e.id ? "border-[#0058CC] bg-[#0058CC] text-white" : "border-[#E5E5EA] bg-white"}`}>{e.id === "all" ? "Semua" : entityShortById(entities, e.id)}</button>
            ))}
          </div>
        </div>
      )}
      <div className="m-card px-3" data-testid="m-md-menu">
        <p className="pt-3 text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Pembelian, harga & stok</p>
        {SUBS.map((s) => <Row key={s.id} icon={s.icon} label={s.label} desc={s.desc} onClick={() => setSub(s.id)} testId={`m-md-menu-${s.id}`} />)}
      </div>
      <div className="m-card px-3" data-testid="m-md-full-menu">
        <p className="pt-3 text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Tampilan lengkap</p>
        {FULL.map((f) => <Row key={f.view} icon={f.icon} label={f.label} onClick={() => onOpenFull?.(f.nav, f.view)} testId={`m-md-full-${f.view}`} />)}
      </div>
      <div className="m-card px-3">
        {onForceDesktop && <Row icon={Monitor} label="Tampilan desktop" onClick={onForceDesktop} testId="m-md-desktop" />}
        <button className="m-list-row m-press w-full text-left text-[#C0392B]" onClick={async () => { await dropPushSubscription(); onLogout?.(); }} data-testid="m-md-logout"><LogOut size={16} /> <span className="text-[13px] font-semibold">Keluar</span></button>
      </div>
    </div>
  );
}

const NOTIF_TAB = { "design-requests": "design", "rnd-samples": "sample", "rnd-hub": "sample", "md-products": "products", "products-pricing": "products", "md-desk": "desk" };

export default function MobileMdApp({ user, entities, selectedEntity, notifications = [], unreadCount = 0, onMarkAllRead, onMarkRead, onPollNotifications,
  onOpenFull, onLogout, onForceDesktop, onSelectEntity }) {
  const [tab, setTab] = useState("desk");
  const [focus, setFocus] = useState({});
  const [sub, setSub] = useState(null);
  const [subParam, setSubParam] = useState(null);
  const [notifOpen, setNotifOpen] = useState(false);
  const canEditProduct = (user?.permissions?.product || []).includes("update");

  useEffect(() => {
    if (!onPollNotifications) return undefined;
    const tick = () => { if (document.visibilityState === "visible") onPollNotifications(); };
    tick();
    const id = setInterval(tick, 60000);
    document.addEventListener("visibilitychange", tick);
    const onMsg = (e) => { if (e.data?.type?.startsWith("kn-push")) { onPollNotifications(); if (e.data.type === "kn-push-open") setNotifOpen(true); } };
    navigator.serviceWorker?.addEventListener?.("message", onMsg);
    return () => { clearInterval(id); document.removeEventListener("visibilitychange", tick); navigator.serviceWorker?.removeEventListener?.("message", onMsg); };
  }, [onPollNotifications]);
  useEffect(() => { syncPushSubscription(); }, [user?.id]);

  const go = (t) => {
    if (t.full) return onOpenFull?.(t.full.nav_id, t.full.view);
    if (t.sub) { setSub(t.sub); setSubParam({ id: t.id }); setTab("more"); return; }
    setFocus({ [t.tab]: t.id }); setTab(t.tab);
  };
  const openNotif = (n) => {
    if (!n.read) onMarkRead?.(n.id);
    const link = String(n.link || "");
    if (!link) return;
    setNotifOpen(false);
    if (link === "purchase-requisitions") return go({ sub: "pr", id: n.action_id });
    if (NOTIF_TAB[link]) return go({ tab: NOTIF_TAB[link], id: n.action_id || null });
    onOpenFull?.(link, link);
  };

  return (
    <div className="m-shell" data-testid="mobile-md-app">
      <header className="m-appbar">
        <div className="m-brand-mark"><Layers size={16} /></div>
        <div className="m-title"><span className="t1">Halo, {(user?.name || "MD").split(" ")[0]} · MD</span><span className="t2">{entityShortById(entities, selectedEntity) || "Semua Entitas"}</span></div>
        <button className="m-act" data-testid="m-md-notif-btn" onClick={() => setNotifOpen(true)} aria-label="Notifikasi">
          <Bell size={18} />{unreadCount > 0 && <span className="m-badge" data-testid="m-md-notif-count">{unreadCount > 99 ? "99+" : unreadCount}</span>}
        </button>
      </header>
      {notifOpen && <NotifSheet notifications={notifications} onClose={() => setNotifOpen(false)} onMarkAll={onMarkAllRead} onOpen={openNotif} />}
      <main className="m-main" data-testid={`m-md-view-${tab}`}>
        {tab === "desk" && <MobileMdDesk selectedEntity={selectedEntity} onOpenRow={(r, q) => go(mdRowTarget(r, q))} />}
        {tab === "design" && <MobileDesignRequests focusId={focus.design} />}
        {tab === "sample" && <MobileRndSamples focusId={focus.sample} />}
        {tab === "products" && <MobileMdProducts canEdit={canEditProduct} />}
        {tab === "more" && <MdMore user={user} entities={entities} selectedEntity={selectedEntity} onSelectEntity={onSelectEntity} sub={sub} setSub={(s) => { setSubParam(null); setSub(s); }}
          subParam={subParam} onOpenFull={onOpenFull} onLogout={onLogout} onForceDesktop={onForceDesktop} />}
      </main>
      <nav className="m-tabbar" data-testid="m-md-tabbar">
        {TABS.map((t) => {
          const Icon = t.icon; const active = tab === t.id;
          return (
            <button key={t.id} className={`m-tab ${active ? "active" : ""}`} data-testid={`m-md-tab-${t.id}`} aria-current={active}
              onClick={() => { setFocus({}); if (t.id === "more") setSub(null); setTab(t.id); }}>
              <span className="m-tab-ico"><Icon size={21} strokeWidth={active ? 2.4 : 2} /></span>{t.label}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
