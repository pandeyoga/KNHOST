import { Users, RotateCcw, FileStack, Tags, Monitor, LogOut, ChevronRight, ArrowLeft, UserCircle, Target, Sparkles } from "lucide-react";
import { Scissors, FlaskConical, Truck, Briefcase, Wallet, Car, Megaphone, FileText, UserCheck, ExternalLink, FileEdit } from "lucide-react";
import { roleLabel } from "../../../config/roles";
import TanyaKnView from "../../tanya/TanyaKnView";
import MobileAmendments from "./MobileAmendments";
import MoreSection from "./MoreSection";
import MobileCustomers from "./MobileCustomers";
import MobileHubMenu from "./MobileHubMenu";
import MobileLeads from "./MobileLeads";
import { MobileReturns, MobileSpecialOrders, MobilePricelist } from "./MobileSalesNative";
import MobilePendingQueue from "./MobilePendingQueue";
import { BadgePercent, MapPin, Boxes, ArrowLeftRight, BadgeCheck, ShieldQuestion, Warehouse, ClipboardList, Building2, ScrollText, Route } from "lucide-react";
import { MobileSpecialPrice, MobileVisits, MobileStock } from "./MobileFieldViews";
import MobileInternalRequests from "./MobileInternalRequests";
import { MobileInstallCard, MobilePushCard, dropPushSubscription } from "./MobilePwa";
import { MobilePriceStatus, MobileSampleOrders, MobileApprovalWatch } from "./MobileExtraViews";
import { entityShortById } from "../../../utils/entityLabel";

const MENU = [
  { id: "tanya", label: "Tanya KN", desc: "Laporan instan & tanya data penjualan Anda", icon: Sparkles },
  { id: "special-price", label: "Minta Harga Khusus", desc: "Ajukan harga nego pelanggan + bukti chat", icon: BadgePercent },
  { id: "visits", label: "Kunjungan Sales", desc: "Check-in / check-out di lokasi pelanggan", icon: MapPin, roles: ["sales"] },
  { id: "internal", label: "Permintaan Internal (PIN)", desc: "Minta barang dari PT lain saat stok kurang", icon: ArrowLeftRight },
  { id: "price-status", label: "Status Harga Khusus", desc: "Pantau pengajuan harga khusus Anda", icon: BadgeCheck },
  { id: "sample-orders", label: "Pesanan Sampel", desc: "Sampel kain gratis / berbayar & statusnya", icon: Scissors },
  { id: "approvals", label: "Pantau Persetujuan", desc: "Dokumen menunggu keputusan manajer (hanya-lihat)", icon: ShieldQuestion, roles: ["sales_admin"] },
  { id: "stock", label: "Status Stok", desc: "Tersedia vs dipesan per gudang (hanya-lihat)", icon: Boxes },
  { id: "leads", label: "Prospek (Lead)", desc: "Catat calon pelanggan, geser tahap, jadikan pelanggan", icon: Target },
  { id: "crm", label: "Pelanggan (CRM)", desc: "Kelola pelanggan & insentif", icon: Users },
  { id: "returns", label: "Retur Penjualan", desc: "Pengajuan & status retur", icon: RotateCcw },
  { id: "special", label: "Pesanan Khusus (OD)", desc: "Pesanan khusus / dibuat sesuai pesanan", icon: FileStack },
  { id: "pricelist", label: "Daftar Harga", desc: "Lihat harga per entitas", icon: Tags },
  { id: "amendments", label: "Koreksi & Amandemen", desc: "Koreksi jumlah / harga pesanan dalam dua ketukan", icon: FileEdit },
];

const GROUPS = [
  { id: "assist", label: "Asisten & laporan", items: ["tanya"], open: true },
  { id: "admin", label: "Admin Sales", items: ["approvals", "internal"], open: true, roles: ["sales_admin"] },
  { id: "orders", label: "Pesanan & harga", items: ["amendments", "special", "sample-orders", "returns", "special-price", "price-status", "pricelist"], open: true },
  { id: "customers", label: "Pelanggan & lapangan", items: ["crm", "leads", "visits"] },
  { id: "stock", label: "Stok & pemenuhan", items: ["stock", "internal"] },
];
const allowed = (item, role) => !item.roles || item.roles.includes(role);

// Fitur desktop yang belum punya layar HP khusus → dibuka dalam tampilan penuh (responsif) + tombol kembali.
const FULL_VIEWS = [
  { nav: "rnd-hub", view: "rnd-samples", label: "Permintaan Sample R&D", desc: "Ajukan & pantau sampel R&D", icon: FlaskConical },
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
  { nav: "accounts-payable", view: "interco-transactions", label: "Transaksi Antar-PT", desc: "Jual-beli antar badan usaha grup", icon: Building2, roles: ["sales_admin"] },
  { nav: "sales-orders", view: "return-policies", label: "Kebijakan Retur", desc: "Aturan retur per jenis keluhan", icon: ScrollText, roles: ["sales_admin"] },
];

const TITLES = { tanya: "Tanya KN", amendments: "Koreksi & Amandemen", leads: "Prospek (Lead)", crm: "Pelanggan (CRM)", returns: "Retur Penjualan", special: "Special Order", pricelist: "Daftar Harga",
  "special-price": "Minta Harga Khusus", visits: "Kunjungan Sales", stock: "Status Stok", internal: "Permintaan Internal", "price-status": "Status Harga Khusus",
  "sample-orders": "Pesanan Sampel", approvals: "Pantau Persetujuan" };

function FullViewMenu({ onOpenFull, role }) {
  return (
    <div data-testid="mobile-more-full-views">
      {FULL_VIEWS.filter((m) => allowed(m, role)).map((m) => {
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

export default function MobileMore({ user, token, selectedEntity, entities, onLogout, onForceDesktop, sub, setSub, onOpenFull, orders, onRefresh, subParam, onSelectEntity, onStartOrder }) {
  const role = user?.role;
  const switchable = (entities || []).filter((e) => (user?.allowed_entity_ids || []).includes(e.id));
  const shownIds = new Set();
  if (sub) {
    return (
      <div data-testid={`mobile-sub-${sub}`} className="-mx-3.5 -mt-3.5">
        <div className="m-subpage-head">
          <button className="m-subpage-back" data-testid="mobile-sub-back" onClick={() => setSub(null)}><ArrowLeft size={17} /> Kembali</button>
          <span className="m-subpage-title">{TITLES[sub]}</span>
        </div>
        <div className="m-subpage-body">
          {sub === "tanya" && <TanyaKnView selectedEntity={selectedEntity} entities={entities} />}
          {sub === "amendments" && <MobileAmendments orders={orders} onRefresh={onRefresh} />}
          {sub === "special-price" && <MobileSpecialPrice selectedEntity={selectedEntity} />}
          {sub === "visits" && <MobileVisits />}
          {sub === "stock" && <MobileStock />}
          {sub === "leads" && <MobileLeads />}
          {sub === "crm" && <MobileCustomers selectedEntity={selectedEntity} user={user} onRefresh={onRefresh} onStartOrder={onStartOrder} />}
          {sub === "returns" && <MobileReturns user={user} initialOrder={subParam?.order || null} focusId={subParam?.id || null} />}
          {sub === "internal" && <MobileInternalRequests user={user} focusId={subParam?.id || null} />}
          {sub === "price-status" && <MobilePriceStatus onNew={() => setSub("special-price")} />}
          {sub === "sample-orders" && <MobileSampleOrders canCancel={(user?.permissions?.sample_order || []).includes("cancel")} />}
          {sub === "approvals" && <MobileApprovalWatch />}
          {sub === "special" && <MobileSpecialOrders focusId={subParam?.id || null} />}
          {sub === "pricelist" && <MobilePricelist selectedEntity={selectedEntity} />}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="mobile-more">
      <MobilePendingQueue />
      {/* Profile card */}
      <div className="m-card flex items-center gap-3 p-4">
        <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-[#0058CC] text-[16px] font-bold text-white">
          {(user?.name || "S").slice(0, 1).toUpperCase()}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[14px] font-bold">{user?.name || "Sales"}</p>
          <p className="truncate text-[11.5px] m-muted">{user?.email}</p>
          {/* FASE E-8 — label peran dari registry (id mentah `sales_admin` tampil buruk). */}
          <p className="text-[10.5px] font-semibold uppercase tracking-wide text-[#0058CC]">{user?.role_label || roleLabel(user?.role)}</p>
        </div>
        <UserCircle size={22} className="text-[#C7C7CC]" />
      </div>

      {/* Menu — dikelompokkan & bisa dibuka/tutup (menu akan terus bertambah) */}
      <MobilePushCard />
      <MobileInstallCard />

      {onSelectEntity && switchable.length > 1 && (
        <div className="m-card p-3" data-testid="mobile-entity-switch">
          <p className="mb-2 text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Badan usaha aktif</p>
          {selectedEntity === "all" && <p className="mb-2 text-[11px] text-[#8A5300]" data-testid="mobile-entity-all-note">Mode "Semua Entitas" hanya untuk melihat — pilih satu badan usaha untuk membuat pesanan, retur, atau permintaan.</p>}
          <div className="flex flex-wrap gap-2">
            <button onClick={() => onSelectEntity("all")} data-testid="mobile-entity-all"
              className={`h-9 rounded-full border px-3 text-[12px] font-semibold ${selectedEntity === "all" ? "border-[#0058CC] bg-[#0058CC] text-white" : "border-[#E5E5EA] bg-white text-[#3A3A3C]"}`}>Semua</button>
            {switchable.map((e) => (
              <button key={e.id} onClick={() => onSelectEntity(e.id)} data-testid={`mobile-entity-${e.id}`}
                className={`h-9 rounded-full border px-3 text-[12px] font-semibold ${selectedEntity === e.id ? "border-[#0058CC] bg-[#0058CC] text-white" : "border-[#E5E5EA] bg-white text-[#3A3A3C]"}`}>
                {entityShortById(entities, e.id)}
              </button>
            ))}
          </div>
        </div>
      )}

      {GROUPS.filter((g) => allowed(g, role)).map((g) => {
        // Satu menu hanya tampil sekali (grup pertama yang memuatnya) — testid tetap unik.
        const items = g.items.map((id) => MENU.find((m) => m.id === id)).filter((m) => m && allowed(m, role) && !shownIds.has(m.id));
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

      {onOpenFull && <MoreSection id="hubs" title="Hub lengkap · setara desktop"><MobileHubMenu role={user?.role} onOpenFull={onOpenFull} /></MoreSection>}
      {onOpenFull && <MoreSection id="full" title="Fitur lainnya · tampilan penuh" count={FULL_VIEWS.filter((m) => allowed(m, role)).length}><FullViewMenu onOpenFull={onOpenFull} role={role} /></MoreSection>}

      {/* Settings */}
      <div className="m-card px-4">
        <button data-testid="mobile-force-desktop" onClick={onForceDesktop} className="m-list-row m-press w-full text-left">
          <span className="inline-flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-[#F2F3F5]"><Monitor size={17} className="text-[#3C3C43]" /></span>
          <div className="min-w-0 flex-1">
            <p className="text-[13px] font-semibold">Tampilan Desktop</p>
            <p className="truncate text-[11px] m-muted">Beralih ke antarmuka penuh</p>
          </div>
          <ChevronRight size={16} className="text-[#C7C7CC]" />
        </button>
        <button data-testid="mobile-logout" onClick={async () => { await dropPushSubscription(); onLogout?.(); }} className="m-list-row m-press w-full text-left">
          <span className="inline-flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-[#FFECEB]"><LogOut size={17} className="text-[#C0392B]" /></span>
          <div className="min-w-0 flex-1"><p className="text-[13px] font-semibold text-[#C0392B]">Keluar</p></div>
        </button>
      </div>

      <p className="pt-1 text-center text-[10.5px] m-muted">Kain Nusantara — Mobile {role === "sales_admin" ? "Admin Sales" : "Sales"}</p>
    </div>
  );
}
