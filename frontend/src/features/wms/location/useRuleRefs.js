// PREP-C (K-GDG-08) — rujukan aturan zona: PT pemilik & artikel (template produk). Dimuat SEKALI per sesi layar
// (banyak editor node memakainya bersamaan) — kegagalan memuat = daftar kosong (aturan lama tetap tampil apa adanya).
import { useEffect, useState } from "react";
import axios, { API } from "../../../services/apiClient";

let cache = null;
let pending = null;

function load() {
  if (cache) return Promise.resolve(cache);
  if (!pending) {
    pending = Promise.all([
      axios.get(`${API}/entities`).then((r) => (Array.isArray(r.data) ? r.data : r.data?.items || [])).catch(() => []),
      axios.get(`${API}/product-templates`).then((r) => (Array.isArray(r.data) ? r.data : r.data?.items || [])).catch(() => []),
    ]).then(([ents, tpls]) => {
      cache = {
        owners: ents.map((e) => ({ value: e.id, label: e.short_name || e.name || e.id })),
        templates: tpls.map((t) => ({ value: t.id, label: t.name || t.code || t.id })),
      };
      return cache;
    }).finally(() => { pending = null; });
  }
  return pending;
}

export function resetRuleRefs() { cache = null; }

export default function useRuleRefs(enabled = true) {
  const [refs, setRefs] = useState(cache || { owners: [], templates: [] });
  useEffect(() => {
    if (!enabled) return undefined;
    let alive = true;
    load().then((v) => { if (alive) setRefs(v); });
    return () => { alive = false; };
  }, [enabled]);
  return refs;
}
