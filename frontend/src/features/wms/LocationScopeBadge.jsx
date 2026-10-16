import { useEffect, useState } from "react";
import { MapPin } from "lucide-react";
import axios, { API } from "../../services/apiClient";

export function useLocationScope() {
  const [scope, setScope] = useState(null);
  useEffect(() => { axios.get(`${API}/wms/my-location-scope`).then((r) => setScope(r.data)).catch(() => setScope({})); }, []);
  return scope;
}

/** P01 IMP-20 — indikator cakupan lokasi kerja aktif. */
export function LocationScopeBadge({ scope }) {
  if (!scope || !scope.role) return null;
  const text = !scope.enforced ? "Pembatasan lokasi nonaktif"
    : !scope.restricted ? (scope.supervisor ? "Supervisor · semua lokasi" : "Semua lokasi")
    : scope.no_assignment ? "Belum ada lokasi tugas — hubungi admin"
    : `Lokasi tugas: ${[...scope.sites, ...(scope.sites.length ? [] : scope.warehouses)].join(", ") || scope.warehouses.join(", ")}`;
  const warn = scope.restricted && scope.no_assignment;
  return (
    <span data-testid="location-scope-badge" title={scope.restricted ? `Gudang: ${scope.warehouses.join(", ") || "—"}` : undefined}
          className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${warn
            ? "border-[#F0C88A] bg-[#FEF7EC] text-[#8C4A00]" : "border-[#CFE3FF] bg-[#F0F6FF] text-[#0058CC]"}`}>
      <MapPin size={11} />{text}
    </span>
  );
}
