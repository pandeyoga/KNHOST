import { ClipboardList, Users, Tags, Boxes, ExternalLink } from "lucide-react";
import { hubTabsForRole } from "../../../config/navigationConfig";

// Hub desktop yang di HP hanya punya layar ringkas → semua halaman turunannya dibuka tampilan penuh.
const HUBS = [
  { id: "sales-orders", label: "Pesanan", icon: ClipboardList },
  { id: "customers-crm", label: "Pelanggan", icon: Users },
  { id: "products-pricing", label: "Produk & Harga", icon: Tags },
  { id: "stock-atp", label: "Stok & ATP", icon: Boxes },
];

/**
 * Fase 3 · P7 (D-26) — `exclude(view)` membuang layar yang sudah punya layar HP di menu "Lainnya" (mis. Koreksi &
 * Amandemen, Permintaan Internal); hub yang tak tersisa satu pun layar tidak ditampilkan.
 */
const hubsFor = (role, exclude) => HUBS
  .map((h) => ({ ...h, tabs: hubTabsForRole(h.id, role).filter((t) => !exclude?.(t.view)) }))
  .filter((h) => h.tabs.length);

/** Jumlah layar hub yang tampil (untuk hitungan seksi "Layar lengkap"). `keep(view)` = true bila layar ditampilkan. */
export const hubViewCount = (role, keep) => hubsFor(role, keep ? (v) => !keep(v) : null).reduce((n, h) => n + h.tabs.length, 0);

export default function MobileHubMenu({ role, onOpenFull, exclude = null }) {
  const hubs = hubsFor(role, exclude);
  if (!hubs.length) return null;
  return (
    <div className="pb-1" data-testid="mobile-more-hubs">
      {hubs.map((h) => {
        const Icon = h.icon;
        return (
          <div key={h.id} className="py-2" data-testid={`mobile-hub-group-${h.id}`}>
            <p className="flex items-center gap-2 text-[13px] font-bold"><Icon size={15} className="text-[#0058CC]" /> {h.label}</p>
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
