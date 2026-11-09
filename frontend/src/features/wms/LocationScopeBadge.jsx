import { useEffect, useState } from "react";
import { MapPin } from "lucide-react";
import axios, { API } from "../../services/apiClient";

export function useLocationScope() {
  const [scope, setScope] = useState(null);
  useEffect(() => { axios.get(`${API}/wms/my-location-scope`).then((r) => setScope(r.data)).catch(() => setScope({})); }, []);
  return scope;
}

/** P01 IMP-20 — indikator cakupan lokasi kerja aktif.
 *  FIX-1 (K-B1-01) — teks mengikuti cakupan TAMPILAN yang sama dengan bilah cakupan app bar (`scope.view`):
 *  lokasi kerja bawaan / pilihan eksplisit / semua lokasi / belum diatur. */
export function LocationScopeBadge({ scope }) {
  if (!scope || !scope.role) return null;
  const v = scope.view || {};
  const text = scope.restricted && scope.no_assignment ? "Belum ada lokasi tugas — hubungi admin"
    : v.mode === "restricted" ? `Lokasi tugas: ${v.label || scope.warehouses.join(", ")}`
    : v.mode === "unset" ? "Lokasi kerja belum diatur · semua lokasi"
    : v.mode === "all" ? (scope.supervisor ? "Supervisor · semua lokasi" : "Semua lokasi")
    : v.label ? `Lokasi: ${v.label}`
    : !scope.enforced ? "Pembatasan lokasi nonaktif" : "Semua lokasi";
  const warn = (scope.restricted && scope.no_assignment) || v.mode === "unset";
  return (
    <span data-testid="location-scope-badge" title={scope.restricted ? `Gudang: ${scope.warehouses.join(", ") || "—"}` : undefined}
          className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${warn
            ? "border-[#F0C88A] bg-[#FEF7EC] text-[#8C4A00]" : "border-[#CFE3FF] bg-[#F0F6FF] text-[#0058CC]"}`}>
      <MapPin size={11} />{text}
    </span>
  );
}
