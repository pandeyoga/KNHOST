/**
 * MobileMdApp — aplikasi HP untuk MD / Merchandiser (dulu jatuh ke inbox generik MobileOpsApp).
 * Tab: Meja · Desain · Sample · Produk · Lainnya. Fitur tanpa layar HP khusus dibuka "tampilan penuh" + tombol
 * kembali ke aplikasi HP.
 *
 * Fase 3 · P7 (L-09) — kerangka bersama `MobileShell` v2 (dulu app bar/tab bar sendiri, judul "· MD"): app bar,
 * lonceng, tab bar & tab "Lainnya" identik dengan aplikasi HP lain; bagian akun = `MobileAccountMenu` (SATU
 * "Tampilan desktop" — D-26; baris desktop kedua MD dicabut). Testid lama `m-md-tab-*`, `m-md-notif-btn`,
 * `m-md-tabbar`, `m-md-view-*` dipertahankan lewat `ids`.
 * D-28 HP — "Status Stok" kini `MobileStockAtp` (Stok & ATP, definisi "Tersedia" K-04), bukan `/inventory/balances`.
 */
import { can } from "../../../config/roles";
import { useState } from "react";
import { ClipboardList, Palette, FlaskConical, Package, Layers, ChevronRight, FileStack, ShoppingBag, Tags, BadgeCheck, Boxes,
  ScrollText, BarChart3, Images, LayoutTemplate, FolderTree, Ruler, FileSearch, Truck, SearchCheck, Route, UserCheck, ArrowLeft } from "lucide-react";
import MobileShell from "../../mobile/MobileShell";
import MobileAccountMenu from "../../mobile/MobileAccountMenu";
import { notifLink } from "../../mobile/notifText";
import { MobileDesignRequests, MobileMdDesk, MobileMdProducts, MobilePoWatch, MobilePurchaseRequisitions, MobileRndSamples, mdRowTarget } from "./MobileMdViews";
import { MobilePricelist } from "./MobileSalesNative";
import { MobilePriceStatus } from "./MobileExtraViews";
import MobileStockAtp from "./MobileStockAtp";

const TABS = [
  { id: "desk", label: "Meja", icon: ClipboardList },
  { id: "design", label: "Desain", icon: Palette },
  { id: "sample", label: "Sample", icon: FlaskConical },
  { id: "products", label: "Produk", icon: Package },
];
const SUBS = [
  { id: "pr", label: "Permintaan Pembelian (PR)", desc: "Ajukan bahan untuk sample & produksi", icon: FileStack },
  { id: "po", label: "Pantau PO Bahan", desc: "Status PO dari PR Anda (hanya-lihat)", icon: ShoppingBag },
  { id: "pricelist", label: "Daftar Harga", desc: "Harga efektif per pelanggan", icon: Tags },
  { id: "price-status", label: "Pengajuan Harga Khusus", desc: "Status harga khusus yang diajukan", icon: BadgeCheck },
  // D-28 — satu layar stok HP (sama dengan Sales): judul mengikuti layar utama "Stok & ATP".
  { id: "stock", label: "Stok & ATP", desc: "Siap janji, akan datang, peluang antar-PT per gudang", icon: Boxes },
];
const FULL = [
  { nav: "rnd-hub", view: "rnd-specs", label: "Spesifikasi Produk", icon: ScrollText },
  // Fase 4 · R1 (D-24b HP) — tiga baris Labdip / Handfeel / Proofing (kini alias yang mendarat di layar yang sama) diringkas
  // jadi SATU baris ke layar utamanya: label = tab menu desktop (`hubTabs` rnd-hub › "R&D Produk Baru"), mode Galeri
  // dengan chip jenis "Semua" & tujuan "Semua" (preset alias `rnd-labdip` dkk. tanpa jenis). Istilah lama tetap terbaca di
  // keterangan baris (K-13).
  { nav: "rnd-hub", view: "rnd-samples", label: "R&D Produk Baru", desc: "Galeri sample: labdip · handfeel · proofing", icon: FlaskConical,
    preset: { mode: "gallery", type: "", purpose: "all" } },
  { nav: "rnd-hub", view: "rnd-reports", label: "Laporan R&D", icon: BarChart3 },
  { nav: "designer-hub", view: "rnd-designs", label: "Desain & Pattern", icon: Images },
  { nav: "products-pricing", view: "product-templates", label: "Template Produk", icon: LayoutTemplate },
  { nav: "products-pricing", view: "md-categories", label: "Kategori", icon: FolderTree },
  { nav: "products-pricing", view: "color-library", label: "Pustaka Warna", icon: Palette },
  { nav: "products-pricing", view: "md-uoms", label: "Satuan", icon: Ruler },
  { nav: "sourcing", view: "rfq", label: "RFQ Supplier", icon: FileSearch },
  { nav: "master-pembelian", view: "suppliers", label: "Supplier", icon: Truck },
  { nav: "quality-hub", view: "inspections", label: "SPK Inspeksi", icon: SearchCheck },
  { nav: "purchase-orders", view: "makloon-orders", label: "Order Makloon", icon: Layers, perm: ["makloon_order", "view"] },
  { nav: "document-center", view: "doc-trace", label: "Jejak Dokumen", icon: Route },
  { nav: "hr-my-profile", view: "hr-my-profile", label: "Profil & Kehadiran Saya", icon: UserCheck },
];
const SUB_TITLE = Object.fromEntries(SUBS.map((s) => [s.id, s.label]));

function Row({ icon: Icon, label, desc, onClick, testId }) {
  return (
    <button type="button" className="m-list-row m-press w-full text-left" onClick={onClick} data-testid={testId}>
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-[#EAF2FF]"><Icon size={16} className="text-[#0058CC]" /></span>
      <span className="min-w-0 flex-1"><span className="block text-[13px] font-semibold">{label}</span>{desc && <span className="block truncate text-[11px] m-muted">{desc}</span>}</span>
      <ChevronRight size={16} className="text-[#C7C7CC]" />
    </button>
  );
}

function MdMore({ user, entities, selectedEntity, onSelectEntity, sub, setSub, subParam, onOpenFull, onLogout, onForceDesktop }) {
  if (sub) {
    return (
      <div className="space-y-2" data-testid={`m-md-sub-${sub}`}>
        <div className="flex items-center gap-2"><button type="button" className="m-subpage-back" onClick={() => setSub(null)} data-testid="m-md-sub-back"><ArrowLeft size={17} /> Kembali</button><span className="m-subpage-title">{SUB_TITLE[sub]}</span></div>
        {sub === "pr" && <MobilePurchaseRequisitions focusId={subParam?.id} selectedEntity={selectedEntity} />}
        {sub === "po" && <MobilePoWatch />}
        {sub === "pricelist" && <MobilePricelist selectedEntity={selectedEntity} />}
        {sub === "price-status" && <MobilePriceStatus />}
        {sub === "stock" && <MobileStockAtp user={user} selectedEntity={selectedEntity} />}
      </div>
    );
  }
  return (
    <div data-testid="m-md-more">
      <MobileAccountMenu user={user} entities={entities} selectedEntity={selectedEntity} onSelectEntity={onSelectEntity}
        onForceDesktop={onForceDesktop} onLogout={onLogout}
        entityNote={'Mode "Semua" hanya untuk melihat — pilih satu badan usaha untuk mengajukan PR / desain.'}>
        <div className="m-card px-3" data-testid="m-md-menu">
          <p className="pt-3 text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Pembelian, harga & stok</p>
          {SUBS.map((s) => <Row key={s.id} icon={s.icon} label={s.label} desc={s.desc} onClick={() => setSub(s.id)} testId={`m-md-menu-${s.id}`} />)}
        </div>
        <div className="m-card px-3" data-testid="m-md-full-menu">
          <p className="pt-3 text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Layar lengkap</p>
          {FULL.filter((f) => !f.perm || can(user?.permissions, ...f.perm)).map((f) => <Row key={f.view} icon={f.icon} label={f.label} desc={f.desc}
            onClick={() => (f.preset ? onOpenFull?.(f.nav, f.view, { preset: f.preset }) : onOpenFull?.(f.nav, f.view))} testId={`m-md-full-${f.view}`} />)}
        </div>
      </MobileAccountMenu>
    </div>
  );
}

const NOTIF_TAB = { "design-requests": "design", "rnd-samples": "sample", "rnd-hub": "sample", "md-products": "products", "products-pricing": "products", "md-desk": "desk" };
const MD_IDS = { tab: "m-md-tab-", tabbar: "m-md-tabbar", view: "m-md-view-", notif: "m-md-notif-btn", count: "m-md-notif-count" };

export default function MobileMdApp(props) {
  const { user, entities, selectedEntity, onOpenFull, onLogout, onForceDesktop, onSelectEntity } = props;
  const [tab, setTab] = useState("desk");
  const [focus, setFocus] = useState({});
  const [sub, setSub] = useState(null);
  const [subParam, setSubParam] = useState(null);
  const canEditProduct = (user?.permissions?.product || []).includes("update");

  const go = (t) => {
    if (t.full) return onOpenFull?.(t.full.nav_id, t.full.view);
    if (t.sub) { setSub(t.sub); setSubParam({ id: t.id }); setTab("more"); return undefined; }
    setFocus({ [t.tab]: t.id }); setTab(t.tab);
    return undefined;
  };
  const openNotif = (n) => {
    const link = notifLink(n);
    if (!link) return false;
    if (link === "purchase-requisitions") go({ sub: "pr", id: n.action_id });
    else if (NOTIF_TAB[link]) go({ tab: NOTIF_TAB[link], id: n.action_id || null });
    else onOpenFull?.(link, link);
    return true;
  };
  const tabs = TABS.map((t) => ({ ...t, render: () => ({
    desk: <MobileMdDesk selectedEntity={selectedEntity} onOpenRow={(r, q) => go(mdRowTarget(r, q))} />,
    design: <MobileDesignRequests focusId={focus.design} />,
    sample: <MobileRndSamples focusId={focus.sample} />,
    products: <MobileMdProducts canEdit={canEditProduct} />,
  }[t.id]) }));
  const moreTab = { render: () => (
    <MdMore user={user} entities={entities} selectedEntity={selectedEntity} onSelectEntity={onSelectEntity} sub={sub} setSub={(s) => { setSubParam(null); setSub(s); }}
      subParam={subParam} onOpenFull={onOpenFull} onLogout={onLogout} onForceDesktop={onForceDesktop} />) };

  return (
    <MobileShell {...props} tabs={tabs} moreTab={moreTab} tab={tab} testId="mobile-md-app" ids={MD_IDS}
      onTabChange={(id) => { setFocus({}); if (id === "more") setSub(null); setTab(id); }} onOpenNotif={openNotif} />
  );
}
