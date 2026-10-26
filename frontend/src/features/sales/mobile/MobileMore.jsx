import { Users, RotateCcw, FileStack, Tags, ChevronRight, ArrowLeft, Target, Sparkles, BarChart3 } from "lucide-react";
import { Scissors, FlaskConical, Truck, Briefcase, Wallet, Car, Megaphone, FileText, UserCheck, ExternalLink, FileEdit } from "lucide-react";
import { roleIs } from "../../../config/roles";
import TanyaKnView from "../../tanya/TanyaKnView";
import MobileAmendments from "./MobileAmendments";
import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { SubpageBackContext } from "./subpageBack";
import MoreSection from "./MoreSection";
import { buildNavigation, hubTabsForRole } from "../../../config/navigationConfig";
import { HUB_TABS } from "../../../config/hubTabs";

// Posisi scroll daftar Lainnya diingat selama aplikasi terbuka (kembali dari sub-halaman / pindah tab).
const MORE_SCROLL = { y: 0 };
const scroller = () => document.querySelector(".m-main");
import MobileCustomers from "./MobileCustomers";
import MobileHubMenu, { hubViewCount } from "./MobileHubMenu";
import MobileLeads from "./MobileLeads";
import { MobileReturns, MobileSpecialOrders, MobilePricelist } from "./MobileSalesNative";
import MobilePendingQueue from "./MobilePendingQueue";
import { BadgePercent, MapPin, Boxes, ArrowLeftRight, BadgeCheck, ShieldQuestion, Warehouse, ClipboardList, Building2, ScrollText, Route } from "lucide-react";
import { MobileSpecialPrice, MobileVisits } from "./MobileFieldViews";
import MobileStockAtp from "./MobileStockAtp";
import MobileCollectionTargets from "./MobileCollectionTargets";
import MobileOrderDashboard from "./MobileOrderDashboard";
import MobileInternalRequests from "./MobileInternalRequests";
import MobileAccountMenu from "../../mobile/MobileAccountMenu";
import { MobileSampleOrders, MobileApprovalWatch } from "./MobileExtraViews";
import PriceApprovals from "../PriceApprovals";

const MENU = [
  { id: "tanya", label: "Tanya KN", desc: "Laporan instan & tanya data penjualan Anda", icon: Sparkles },
  { id: "special-price", label: "Minta Harga Khusus", desc: "Ajukan harga nego pelanggan + bukti chat", icon: BadgePercent },
  { id: "visits", label: "Kunjungan Sales", desc: "Check-in / check-out di lokasi pelanggan", icon: MapPin, roles: ["sales"] },
  { id: "internal", label: "Permintaan Internal (PIN)", desc: "Minta barang dari PT lain saat stok kurang", icon: ArrowLeftRight },
  { id: "price-status", label: "Harga Khusus Saya", desc: "Semua status (draf, menunggu, digantikan, diakhiri…) · ubah, kirim, lampiran", icon: BadgeCheck },
  { id: "sample-orders", label: "Pesanan Sample", desc: "Sample kain gratis / berbayar & statusnya", icon: Scissors },
  { id: "approvals", label: "Pantau Persetujuan", desc: "Dokumen menunggu keputusan manajer (hanya-lihat)", icon: ShieldQuestion, roles: ["sales_admin"] },
  { id: "stock", label: "Stok & ATP", desc: "Siap janji, akan datang, peluang antar-PT per gudang", icon: Boxes },
  { id: "order-dashboard", label: "Dasbor Pesanan", desc: "Omzet, status, tren 8 minggu, pelanggan teratas & butuh tindakan", icon: BarChart3 },
  { id: "collection", label: "Penagihan & Target", desc: "Pengingat tagih, follow-up, target, komisi & peringkat", icon: Wallet },
  { id: "leads", label: "Prospek (Lead)", desc: "Catat calon pelanggan, geser tahap, jadikan pelanggan", icon: Target },
  { id: "crm", label: "Pelanggan (CRM)", desc: "Kelola pelanggan & insentif", icon: Users },
  { id: "returns", label: "Retur Penjualan", desc: "Pengajuan & status retur", icon: RotateCcw },
  { id: "special", label: "Pesanan Khusus (OD)", desc: "Pesanan khusus / dibuat sesuai pesanan", icon: FileStack },
  // UAT 24 Okt (audit UI tahap 2) — G2-30: deskripsi sesuai isi layar (pilih pelanggan → harga efektif).
  { id: "pricelist", label: "Daftar Harga", desc: "Harga efektif per pelanggan", icon: Tags },
  { id: "amendments", label: "Koreksi & Amandemen", desc: "Koreksi jumlah / harga pesanan dalam dua ketukan", icon: FileEdit },
];

const GROUPS = [
  { id: "assist", label: "Asisten & laporan", items: ["tanya"], open: true },
  { id: "admin", label: "Admin Sales", items: ["approvals", "internal"], open: true, roles: ["sales_admin"] },
  { id: "orders", label: "Pesanan & harga", items: ["amendments", "special", "sample-orders", "returns", "special-price", "price-status", "pricelist"], open: true },
  { id: "customers", label: "Pelanggan & lapangan", items: ["order-dashboard", "crm", "collection", "leads", "visits"], open: true },
  { id: "stock", label: "Stok & pemenuhan", items: ["stock", "internal"], open: true },
];
// Hanya menu yang memang ada di sidebar desktop peran ini (roles + peran custom + menu tersembunyi).
const navIdsFor = (role) => new Set(buildNavigation(role).filter((e) => !e.comingSoon).map((e) => e.id));
// Menu & grup layar HP sales (MENU/GROUPS) tidak punya `nav` — cukup cek peran. Dulu ikut disaring `allowed`
// (yang mewajibkan `nav` di sidebar) sehingga SEMUA menu HP sales hilang (Retur, Pesanan Sample, Pesanan Khusus,
// Minta Harga Khusus, …) — cek UI UAT v3 (2026-10-22).
const roleOk = (item, role) => !item.roles || item.roles.includes(role);
// Fitur tampilan penuh (FULL_VIEWS) — hanya yang memang ada di sidebar desktop peran ini.
const allowed = (item, role) => {
  if (!roleOk(item, role)) return false;
  if (!navIdsFor(role).has(item.nav)) return false;
  const tabs = hubTabsForRole(item.nav, role);   // view tab hub (mis. Kebijakan Retur) juga harus terlihat untuk peran ini
  return !tabs.length || item.view === item.nav || tabs.some((t) => t.view === item.view) || !HUB_VIEWS.has(item.view);
};
const HUB_VIEWS = new Set(Object.values(HUB_TABS).flat().map((t) => t.view));

// Fitur desktop yang belum punya layar HP khusus → dibuka dalam tampilan penuh (responsif) + tombol kembali.
const FULL_VIEWS = [
  { nav: "rnd-hub", view: "rnd-samples", label: "Permintaan Sample R&D", desc: "Ajukan & pantau sample R&D", icon: FlaskConical },
  { nav: "logistics", view: "logistics", label: "Pengiriman", desc: "Lacak surat jalan & status kirim", icon: Truck },
  { nav: "finance-cases", view: "finance-cases", label: "Kasus Keuangan", desc: "Selisih bayar, klaim, sengketa", icon: Briefcase },
  { nav: "petty-cash", view: "cash-advances", label: "Kas Kecil", desc: "Pengajuan dana & pertanggungjawaban", icon: Wallet },
  { nav: "vehicle-logs", view: "vehicle-logs", label: "Kendaraan", desc: "Log pemakaian kendaraan", icon: Car },
  { nav: "marketing-hub", view: "mkt-calendar", label: "Marketing & Sosmed", desc: "Kalender konten & kampanye", icon: Megaphone },
  { nav: "document-center", view: "document-center", label: "Pusat Dokumen", desc: "Cari & unduh dokumen", icon: FileText },
  { nav: "hr-my-profile", view: "hr-my-profile", label: "Profil & Kehadiran Saya", desc: "Absensi, cuti, slip gaji", icon: UserCheck },
  { nav: "document-center", view: "doc-trace", label: "Jejak Dokumen", desc: "Rantai SO → surat jalan → invoice → retur", icon: Route },
  // Admin Sales (ROLE_NAV.add) — memantau gudang, mengajukan PR, antar-PT, kebijakan retur.
  { nav: "sales-admin-desk", view: "sales-admin-desk", label: "Meja Admin Sales (desktop)", desc: "Tampilan meja lengkap", icon: ClipboardList, roles: ["sales_admin"] },
  { nav: "wms-operations", view: "operations", label: "Operasi Gudang (pantau)", desc: "Progres ambil/kemas/kirim tanpa aksi", icon: Warehouse, roles: ["sales_admin"] },
  { nav: "sourcing", view: "purchase-requisitions", label: "Permintaan Pembelian (PR)", desc: "Ajukan reorder ke supplier", icon: FileStack, roles: ["sales_admin"] },
  // Fase 3 · P7 — nav lama `accounts-payable` DICABUT untuk Admin Sales (ROLE_NAV.remove) sehingga butir ini tak pernah
  // tampil; menu yang benar = `interco-transactions` (ROLE_NAV.add sales_admin).
  { nav: "interco-transactions", view: "interco-transactions", label: "Transaksi Antar-PT", desc: "Jual-beli antar badan usaha grup", icon: Building2, roles: ["sales_admin"] },
  // Fase 3 · P2 (P16-K1) — Kebijakan Retur pindah ke Pengaturan › Penjualan (`settings-sales`); view sama.
  { nav: "settings-sales", view: "return-policies", label: "Kebijakan Retur", desc: "Aturan retur per jenis keluhan", icon: ScrollText, roles: ["sales_admin"] },
];

const TITLES = { tanya: "Tanya KN", amendments: "Koreksi & Amandemen", leads: "Prospek (Lead)", crm: "Pelanggan (CRM)", returns: "Retur Penjualan", special: "Pesanan Khusus (OD)", pricelist: "Daftar Harga",
  "special-price": "Minta Harga Khusus", visits: "Kunjungan Sales", stock: "Stok & ATP", collection: "Penagihan & Target", "order-dashboard": "Dasbor Pesanan", internal: "Permintaan Internal", "price-status": "Harga Khusus Saya",
  "sample-orders": "Pesanan Sample", approvals: "Pantau Persetujuan" };

// Fase 3 · P7 (D-26) — layar hub yang SUDAH punya layar HP di menu ini tidak diulang di "Layar lengkap".
// view hub → id layar HP (MENU) atau "tab" (tab bawah aplikasi HP); hanya dibuang bila layar HP itu tampil untuk peran.
const HP_EQUIV = { orders: "tab", amendments: "amendments", "internal-requests": "internal", "customers-crm": "crm",
  "hr-visits": "visits", "cs-price-list": "pricelist", "inventory-board": "stock" };
export const hasHpScreen = (view, role) => {
  const id = HP_EQUIV[view];
  if (!id) return false;
  if (id === "tab") return true;
  const m = MENU.find((x) => x.id === id);
  return !!m && roleOk(m, role);
};
export const fullViewsFor = (role) => FULL_VIEWS.filter((m) => allowed(m, role) && !hasHpScreen(m.view, role));

function FullViewMenu({ onOpenFull, items }) {
  return (
    <div data-testid="mobile-more-full-views">
      {items.map((m) => {
        const Icon = m.icon;
        return (
          <button key={m.view} data-testid={`mobile-full-${m.view}`} onClick={() => onOpenFull(m.nav, m.view)} className="m-list-row m-press w-full text-left">
            <span className="inline-flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-[#F2F3F5]"><Icon size={17} className="text-[#3C3C43]" /></span>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-semibold">{m.label}</p>
              <p className="truncate text-[11px] m-muted">{m.desc}</p>
            </div>
            <ExternalLink size={15} className="text-[#C7C7CC]" />
          </button>
        );
      })}
    </div>
  );
}

export default function MobileMore({ onOpenOrder, user, token, selectedEntity, entities, onLogout, onForceDesktop, sub, setSub, onOpenFull, orders, onRefresh, subParam, onSelectEntity, onStartOrder }) {
  useLayoutEffect(() => {
    const el = scroller();
    if (!el) return undefined;
    if (sub) { el.scrollTo(0, 0); return undefined; }
    el.scrollTo(0, MORE_SCROLL.y);
    const raf = requestAnimationFrame(() => el.scrollTo(0, MORE_SCROLL.y));   // sesudah grup terbuka ter-render
    return () => cancelAnimationFrame(raf);
  }, [sub]);
  useEffect(() => {
    if (sub) return undefined;
    const el = scroller();
    const save = () => { MORE_SCROLL.y = el?.scrollTop || 0; };
    el?.addEventListener("scroll", save, { passive: true });
    return () => el?.removeEventListener("scroll", save);
  }, [sub]);
  // Rincian di dalam subhalaman mendaftarkan aksi kembalinya (lihat subpageBack.js) — satu tombol "Kembali".
  const backStack = useRef([]);
  const backCtx = useMemo(() => ({
    push: (fn) => { backStack.current = [...backStack.current, fn]; },
    pop: (fn) => { backStack.current = backStack.current.filter((x) => x !== fn); },
  }), []);
  const goBack = () => { const top = backStack.current[backStack.current.length - 1]; if (top) top(); else setSub(null); };
  const role = user?.role;
  const shownIds = new Set();
  if (sub) {
    return (
      <div data-testid={`mobile-sub-${sub}`} className="-mx-3.5 -mt-3.5">
        <div className="m-subpage-head">
          <button className="m-subpage-back" data-testid="mobile-sub-back" onClick={goBack}><ArrowLeft size={17} /> Kembali</button>
          <span className="m-subpage-title">{TITLES[sub]}</span>
        </div>
        <SubpageBackContext.Provider value={backCtx}>
        <div className="m-subpage-body">
          {sub === "tanya" && <TanyaKnView selectedEntity={selectedEntity} entities={entities} />}
          {sub === "amendments" && <MobileAmendments orders={orders} onRefresh={onRefresh} />}
          {sub === "special-price" && <MobileSpecialPrice selectedEntity={selectedEntity} />}
          {sub === "visits" && <MobileVisits />}
          {sub === "collection" && <MobileCollectionTargets selectedEntity={selectedEntity} />}
          {sub === "order-dashboard" && <MobileOrderDashboard selectedEntity={selectedEntity} onOpenOrder={onOpenOrder} />}
          {sub === "stock" && <MobileStockAtp user={user} selectedEntity={selectedEntity} />}
          {sub === "leads" && <MobileLeads />}
          {sub === "crm" && <MobileCustomers selectedEntity={selectedEntity} user={user} onRefresh={onRefresh} onStartOrder={onStartOrder} />}
          {sub === "returns" && <MobileReturns user={user} initialOrder={subParam?.order || null} focusId={subParam?.id || null} />}
          {sub === "internal" && <MobileInternalRequests user={user} focusId={subParam?.id || null} />}
          {sub === "price-status" && <div className="m-price-approvals"><PriceApprovals currentUser={user} /></div>}
          {sub === "sample-orders" && <MobileSampleOrders canCancel={(user?.permissions?.sample_order || []).includes("cancel")} />}
          {sub === "approvals" && <MobileApprovalWatch />}
          {sub === "special" && <MobileSpecialOrders focusId={subParam?.id || null} />}
          {sub === "pricelist" && <MobilePricelist selectedEntity={selectedEntity} />}
        </div>
        </SubpageBackContext.Provider>
      </div>
    );
  }

  const full = fullViewsFor(role);
  return (
    <div data-testid="mobile-more">
      {/* L-09 — profil, PT, push/pasang, SATU "Tampilan desktop" (D-26) & Keluar = MobileAccountMenu (sama di semua aplikasi HP). */}
      <MobileAccountMenu user={user} entities={entities} selectedEntity={selectedEntity} onSelectEntity={onSelectEntity}
        onForceDesktop={onForceDesktop} onLogout={onLogout} header={<MobilePendingQueue />}
        entityNote={'Mode "Semua Entitas" hanya untuk melihat — pilih satu badan usaha untuk membuat pesanan, retur, atau permintaan.'}
        footer={`Kain Nusantara — Mobile ${roleIs(role, ["sales_admin"]) ? "Admin Sales" : "Sales"}`}>
        {GROUPS.filter((g) => roleOk(g, role)).map((g) => {
          // Satu menu hanya tampil sekali (grup pertama yang memuatnya) — testid tetap unik.
          const items = g.items.map((id) => MENU.find((m) => m.id === id)).filter((m) => m && roleOk(m, role) && !shownIds.has(m.id));
          items.forEach((m) => shownIds.add(m.id));
          if (!items.length) return null;
          return (
            <MoreSection key={g.id} id={g.id} title={g.label} count={items.length} defaultOpen={g.open}>
              {items.map((m) => {
                const Icon = m.icon;
                return (
                  <button key={m.id} data-testid={`mobile-more-${m.id}`} onClick={() => setSub(m.id)} className="m-list-row m-press w-full text-left last:border-0">
                    <span className="inline-flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-[#F2F3F5]"><Icon size={17} className="text-[#0058CC]" /></span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-semibold">{m.label}</p>
                      <p className="truncate text-[11px] m-muted">{m.desc}</p>
                    </div>
                    <ChevronRight size={16} className="text-[#C7C7CC]" />
                  </button>
                );
              })}
            </MoreSection>
          );
        })}

        {/* D-26 — dulu dua seksi ("Hub lengkap · setara desktop" & "Fitur lainnya · tampilan penuh") yang mengulang
            layar yang sudah ada di menu HP; kini SATU seksi "Layar lengkap" tanpa butir yang punya layar HP. */}
        {onOpenFull && (
          <MoreSection id="full" title="Layar lengkap" count={full.length + hubViewCount(role, (v) => !hasHpScreen(v, role))}>
            <MobileHubMenu role={role} onOpenFull={onOpenFull} exclude={(v) => hasHpScreen(v, role)} />
            <FullViewMenu onOpenFull={onOpenFull} items={full} />
          </MoreSection>
        )}
      </MobileAccountMenu>
    </div>
  );
}
