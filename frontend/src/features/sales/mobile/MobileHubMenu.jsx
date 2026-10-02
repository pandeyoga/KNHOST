import { ClipboardList, Users, Tags, Boxes, ExternalLink } from "lucide-react";
import { hubTabsForRole } from "../../../config/navigationConfig";

// Hub desktop yang di HP hanya punya layar ringkas → semua halaman turunannya dibuka tampilan penuh.
const HUBS = [
  { id: "sales-orders", label: "Pesanan", icon: ClipboardList },
  { id: "customers-crm", label: "Pelanggan", icon: Users },
  { id: "products-pricing", label: "Produk & Harga", icon: Tags },
  { id: "stock-atp", label: "Stok & ATP", icon: Boxes },
];

export default function MobileHubMenu({ role, onOpenFull }) {
  const hubs = HUBS.map((h) => ({ ...h, tabs: hubTabsForRole(h.id, role) })).filter((h) => h.tabs.length);
  if (!hubs.length) return null;
  return (
    <div className="pb-1" data-testid="mobile-more-hubs">
      {hubs.map((h) => {
        const Icon = h.icon;
        return (
          <div key={h.id} className="py-2" data-testid={`mobile-hub-group-${h.id}`}>
            <p className="flex items-center gap-2 text-[13px] font-bold"><Icon size={15} className="text-[#6B219A]" /> {h.label}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {h.tabs.map((t) => (
                <button key={t.view} type="button" onClick={() => onOpenFull(h.id, t.view)} data-testid={`mobile-hub-${t.view}`}
                  className="m-press inline-flex min-h-[36px] scroll-mb-28 items-center gap-1.5 rounded-full border border-[#E5E5EA] bg-white px-3 text-[12px] font-semibold">
                  {t.label} <ExternalLink size={12} className="text-[#C7C7CC]" />
                </button>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
