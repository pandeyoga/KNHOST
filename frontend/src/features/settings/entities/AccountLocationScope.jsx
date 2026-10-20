import { useEffect, useState } from "react";
import { MapPin } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { roleIs } from "../../../config/roles";

const chip = (on) => `rounded-md border px-2 py-1 text-[11px] font-semibold ${on
  ? "border-[#0058CC] bg-[#EAF2FF] text-[#0058CC]" : "border-[#E5E5EA] bg-white text-[#6B6B73]"}`;

const toggle = (list, id) => (list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);

/** P01 IMP-20 — penugasan lokasi kerja: site (semua gudangnya) lalu opsional dipersempit per gudang. */
export function AccountLocationScope({ role, siteIds, warehouseIds, onChange }) {
  const [sites, setSites] = useState([]);
  const [whs, setWhs] = useState([]);
  useEffect(() => {
    axios.get(`${API}/warehouse-sites`).then((r) => setSites(Array.isArray(r.data) ? r.data : r.data?.sites || r.data?.items || [])).catch(() => setSites([]));
    axios.get(`${API}/warehouses`).then((r) => setWhs(Array.isArray(r.data) ? r.data : r.data?.items || [])).catch(() => setWhs([]));
  }, []);
  const inSite = whs.filter((w) => siteIds.includes(w.site_id));
  return (
    <div className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2.5" data-testid="account-form-locations">
      <p className="kicker mb-1 flex items-center gap-1"><MapPin size={12} />Lokasi kerja gudang</p>
      <div className="flex flex-wrap gap-1.5">
        {sites.map((s) => (
          <button key={s.id} type="button" data-testid={`account-form-site-${s.id}`} className={chip(siteIds.includes(s.id))}
                  onClick={() => { const next = toggle(siteIds, s.id); onChange({ location_site_ids: next,
                    location_warehouse_ids: warehouseIds.filter((w) => next.includes(whs.find((x) => x.id === w)?.site_id)) }); }}>
            {s.name}
          </button>
        ))}
      </div>
      {inSite.length > 0 && (
        <div className="mt-2" data-testid="account-form-warehouses">
          <p className="text-[10.5px] text-[#6B6B73]">Persempit ke gudang (kosong = semua gudang di site terpilih):</p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {inSite.map((w) => (
              <button key={w.id} type="button" data-testid={`account-form-wh-${w.code || w.id}`} className={chip(warehouseIds.includes(w.id))}
                      onClick={() => onChange({ location_warehouse_ids: toggle(warehouseIds, w.id) })}>
                {w.code || w.name}
              </button>
            ))}
          </div>
        </div>
      )}
      <p className="mt-1 text-[10px] text-[#8E8E93]" data-testid="account-form-locations-help">
        {roleIs(role, ["warehouse"])
          ? "Saat pembatasan lokasi aktif, petugas ini hanya melihat dan mengerjakan tugas, stok, putaway, dan transfer di lokasi terpilih. Tanpa lokasi = tidak melihat pekerjaan gudang mana pun."
          : "Peran ini tidak dibatasi lokasi (supervisor gudang, manajer, dan admin melihat semua lokasi). Penugasan tetap disimpan sebagai lokasi asal."}
      </p>
    </div>
  );
}
