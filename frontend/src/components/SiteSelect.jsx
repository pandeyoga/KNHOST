import { useEffect, useState } from "react";
import { MapPin } from "lucide-react";
import axios, { API } from "../services/apiClient";
import KNSelect from "./KNSelect";

let _sitesCache = null;
/** Daftar lokasi (site) — satu kali muat per sesi halaman. */
export function useSites() {
  const [sites, setSites] = useState(_sitesCache || []);
  useEffect(() => {
    if (_sitesCache) return undefined;
    let live = true;
    axios.get(`${API}/warehouse-sites`).then((r) => {
      _sitesCache = r.data?.sites || [];
      if (live) setSites(_sitesCache);
    }).catch(() => {});
    return () => { live = false; };
  }, []);
  return sites;
}

/**
 * UAT 24 Okt (P9) — pemilih "Lokasi kirim" (site), pengganti pemilih gudang bebas di dokumen beli/terima.
 * Barang dikirim ke LOKASI; gudang penerimaannya diturunkan server (peran Transit / Penerimaan Pusat) dan
 * ditampilkan sebagai info — pengguna tidak lagi bisa memilih gudang simpan / gudang nonaktif.
 */
export default function SiteSelect({ value, onChange, entityId = "", label = "Lokasi kirim", required = true,
  testId = "site-select", disabled = false, showReceiving = true }) {
  const sites = useSites();
  const [recv, setRecv] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!value || !showReceiving) { setRecv(null); setErr(""); return undefined; }
    let live = true;
    axios.get(`${API}/warehouse-sites/${value}/receiving`, { params: entityId ? { entity_id: entityId } : {} })
      .then((r) => { if (live) { setRecv(r.data?.warehouse || null); setErr(""); } })
      .catch((e) => { if (live) { setRecv(null); setErr(e?.response?.data?.detail || "Lokasi belum punya gudang penerimaan."); } });
    return () => { live = false; };
  }, [value, entityId, showReceiving]);
  return (
    <label className="block" data-testid={`${testId}-wrap`}>
      <span className="field-label">{label}{required ? " *" : ""}</span>
      <KNSelect data-testid={testId} className="field" value={value || ""} disabled={disabled}
        placeholder="Pilih lokasi" onValueChange={(v) => onChange?.(v)}
        options={sites.map((s) => ({ value: s.id, label: `${s.name}${s.city && s.city !== s.name ? ` · ${s.city}` : ""}` }))} />
      {showReceiving && value && (
        <span data-testid={`${testId}-receiving`} className={`mt-1 flex items-center gap-1 text-[11px] ${err ? "text-[#A8221A]" : "text-[#4A4A52]"}`}>
          <MapPin size={11} /> {err || (recv ? `Diterima di ${recv.name || recv.code} (gudang penerimaan lokasi)` : "Memuat gudang penerimaan…")}
        </span>
      )}
    </label>
  );
}
