import { useEffect, useState } from "react";
import { MapPin, Store, UserPlus, Users } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import SiteSelect, { useSites } from "../../components/SiteSelect";

const KEY = "kn_pos_ctx";
/** Konteks jualan (lokasi + pelanggan) per sesi tab — bertahan saat muat ulang, hilang saat tab ditutup. */
export const loadPosCtx = () => {
  try { return JSON.parse(sessionStorage.getItem(KEY) || "{}") || {}; } catch { return {}; }
};
export const savePosCtx = (ctx) => {
  try { sessionStorage.setItem(KEY, JSON.stringify(ctx || {})); } catch { /* penyimpanan sesi tidak tersedia */ }
};

/**
 * UAT 24 Okt (P8, keputusan pemilik) — "Mulai jualan": pilih LOKASI gudang + PELANGGAN dulu, baru katalog.
 * Dulu pelanggan opsional di atas katalog dan lokasi tidak ada sama sekali (stok = total global semua lokasi).
 * Lokasi bawaan = lokasi akun (`location_site_ids[0]`); pelanggan = milik sales (+ walk-in PT) atau pelanggan baru.
 */
export default function PosStartGate({ user, customers = [], initialSiteId = "", initialCustomerId = "", onStart, onCreateCustomer, testPrefix = "pos-gate" }) {
  const [siteId, setSiteId] = useState(initialSiteId || (user?.location_site_ids || [])[0] || "");
  const [custId, setCustId] = useState(initialCustomerId || "");
  const sites = useSites();
  useEffect(() => {
    if (!siteId && sites.length === 1) setSiteId(sites[0].id);
  }, [sites, siteId]);
  useEffect(() => { if (initialCustomerId) setCustId(initialCustomerId); }, [initialCustomerId]);
  const customer = customers.find((c) => c.id === custId) || null;
  const walkIn = customers.find((c) => c.shared_walk_in);
  return (
    <section className="section-card mb-3" data-testid={`${testPrefix}`}>
      <div className="section-head">
        <div className="flex items-center gap-2"><Store size={15} className="text-[#0058CC]" /><h2>Mulai jualan</h2></div>
        <span className="text-[11px] text-[#6B6B73]">Pilih lokasi gudang & pelanggan — harga, kredit, dan stok mengikuti pilihan ini.</span>
      </div>
      <div className="grid gap-3 p-4 sm:grid-cols-2">
        <div>
          <SiteSelect value={siteId} onChange={setSiteId} label="Lokasi gudang" showReceiving={false} testId={`${testPrefix}-site`} />
          <p className="mt-1 flex items-center gap-1 text-[11px] text-[#6B6B73]"><MapPin size={11} /> Stok di lokasi ini ditonjolkan; lokasi lain tetap terlihat sebagai "perlu transfer".</p>
        </div>
        <div>
          <span className="field-label">Pelanggan *</span>
          <KNSelect data-testid={`${testPrefix}-customer`} className="field" value={custId} onValueChange={setCustId} searchable
            placeholder={customers.length ? "Pilih pelanggan Anda" : "Belum ada pelanggan — buat pelanggan baru"}
            options={customers.map((c) => ({ value: c.id, label: `${c.name}${c.code ? ` · ${c.code}` : ""}${c.shared_walk_in ? " (umum)" : ""}` }))} />
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            {onCreateCustomer && (
              <button type="button" className="secondary-button !py-1 text-[12px]" data-testid={`${testPrefix}-new-customer`} onClick={onCreateCustomer}>
                <UserPlus size={13} /> Pelanggan baru
              </button>
            )}
            {walkIn && custId !== walkIn.id && (
              <button type="button" className="link-button text-[12px]" data-testid={`${testPrefix}-walkin`} onClick={() => setCustId(walkIn.id)}>
                <Users size={12} /> Pakai pelanggan umum (walk-in)
              </button>
            )}
          </div>
        </div>
      </div>
      <div className="flex items-center justify-end gap-2 border-t border-[#EFF0F2] px-4 py-3">
        <button type="button" className="primary-button" data-testid={`${testPrefix}-start`} disabled={!siteId || !customer}
          onClick={() => onStart?.({ siteId, customer })}>
          Buka katalog
        </button>
      </div>
    </section>
  );
}
