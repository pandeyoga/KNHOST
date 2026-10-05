import { useCallback, useEffect, useState } from "react";
import axios, { API } from "../services/apiClient";

const EVT = "kn:receiving-mode-changed";
let cache = null;
let inflight = null;

const load = (force = false) => {
  if (cache && !force) return Promise.resolve(cache);
  if (!inflight || force) {
    inflight = axios.get(`${API}/goods-receipts/mode`)
      .then((r) => { cache = r.data; return cache; })
      .catch(() => ({ entities: [], modes: {} }))
      .finally(() => { inflight = null; });
  }
  return inflight;
};

export const notifyReceivingModeChanged = () => { cache = null; window.dispatchEvent(new Event(EVT)); };

/** GRN Fase 7 — mode penerimaan per badan usaha (`legacy` | `grn`). Layar lama menyembunyikan tombol terima bila `grn`. */
export default function useReceivingMode() {
  const [data, setData] = useState(cache);
  const reload = useCallback(() => load(true).then(setData), []);
  useEffect(() => {
    let alive = true;
    load().then((d) => alive && setData(d));
    const on = () => load(true).then((d) => alive && setData(d));
    window.addEventListener(EVT, on);
    return () => { alive = false; window.removeEventListener(EVT, on); };
  }, []);
  const modeOf = useCallback((eid) => (data?.modes || {})[eid] || "legacy", [data]);
  const entityOf = useCallback((eid) => (data?.entities || []).find((e) => e.entity_id === eid), [data]);
  return { data, modeOf, entityOf, reload, isGrn: (eid) => modeOf(eid) === "grn" };
}
