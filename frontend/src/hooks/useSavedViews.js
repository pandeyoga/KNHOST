/**
 * useSavedViews — FIX-8 (K-B4-12 · B4 §3.4 [6–8]): tampilan tersimpan sebuah daftar (saringan + urut + kolom + mode)
 * di SERVER (`/api/saved-views`, koleksi `saved_views`).
 *
 *   const sv = useSavedViews("wms.transfers", { state, apply, base });
 *   <SavedViewsMenu sv={sv} … />
 *
 *  · `state`  = keadaan layar sekarang {filters, sort, columns, mode} (columns = kunci kolom yang DISEMBUNYIKAN).
 *  · `apply`  = fungsi layar untuk memasang sebuah state (dipanggil saat memilih tampilan / memulihkan bawaan).
 *  · `base`   = state "Tampilan standar" (tanpa saringan) — dipakai tombol Reset & penanda berubah.
 * Saat daftar dibuka: bawaan pribadi → bawaan bersama (peran/PT) dipasang SEKALI. Cakupan PT/lokasi tidak pernah
 * ikut (server menolaknya) — pilihan bilah "Lokasi: … ▾" & PT aktif tetap milik pengguna (FIX-1).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios, { API } from "../services/apiClient";
import { apiErrorText } from "../utils/apiError";

const EMPTY = { filters: {}, sort: null, columns: [], mode: "" };

/** Bentuk baku (kunci urut, nilai kosong dibuang) supaya perbandingan "berubah" stabil. */
export function normalizeViewState(s) {
  const st = { ...EMPTY, ...(s || {}) };
  const filters = Object.fromEntries(Object.entries(st.filters || {})
    .filter(([, v]) => !(v === "" || v === null || v === undefined || v === false || v === "all"
      || (Array.isArray(v) && !v.length)))
    .sort(([a], [b]) => a.localeCompare(b)));
  return {
    filters,
    sort: st.sort && st.sort.key ? { key: st.sort.key, dir: st.sort.dir === "desc" ? "desc" : "asc" } : null,
    columns: [...new Set(st.columns || [])].sort(),
    mode: st.mode || "",
  };
}
export const sameViewState = (a, b) => JSON.stringify(normalizeViewState(a)) === JSON.stringify(normalizeViewState(b));

export default function useSavedViews(listKey, { state, apply, base = EMPTY, enabled = true } = {}) {
  const [views, setViews] = useState([]);
  const [activeId, setActiveId] = useState("");
  const [defaultId, setDefaultId] = useState("");
  const [canShare, setCanShare] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const restored = useRef(false);
  const applyRef = useRef(apply);
  applyRef.current = apply;

  const load = useCallback(async ({ restore = false } = {}) => {
    if (!enabled || !listKey) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/saved-views`, { params: { list_key: listKey } });
      const items = Array.isArray(data?.items) ? data.items : [];
      setViews(items);
      setDefaultId(data?.default_id || "");
      setCanShare(Boolean(data?.can_share));
      setError("");
      if (restore && !restored.current) {
        restored.current = true;
        const def = items.find((v) => v.id === data?.default_id);
        if (def) { setActiveId(def.id); applyRef.current?.(normalizeViewState(def.state)); }
      }
    } catch (e) {
      setError(apiErrorText(e, "Tampilan tersimpan tidak bisa dimuat."));
    } finally {
      setLoading(false);
    }
  }, [listKey, enabled]);

  useEffect(() => { load({ restore: true }); }, [load]);

  const active = useMemo(() => views.find((v) => v.id === activeId) || null, [views, activeId]);
  const dirty = active ? !sameViewState(active.state, state) : !sameViewState(base, state);

  const select = useCallback((id) => {
    const v = views.find((x) => x.id === id);
    if (!v) return;
    setActiveId(id);
    applyRef.current?.(normalizeViewState(v.state));
  }, [views]);

  const reset = useCallback(() => {
    setActiveId("");
    applyRef.current?.(normalizeViewState(base));
  }, [base]);

  const run = async (fn, fallback) => {
    setBusy(true);
    try {
      const out = await fn();
      setError("");
      return out;
    } catch (e) {
      setError(apiErrorText(e, fallback));
      return null;
    } finally {
      setBusy(false);
    }
  };

  const saveAs = (name, { isDefault = false, share = null } = {}) => run(async () => {
    const { data } = await axios.post(`${API}/saved-views`, {
      list_key: listKey, name, state: normalizeViewState(state), is_default: isDefault,
      ...(share ? { share } : {}),
    });
    await load();
    setActiveId(data.id);
    return data;
  }, "Tampilan gagal disimpan.");

  const saveActive = () => active && run(async () => {
    await axios.put(`${API}/saved-views/${active.id}`, { state: normalizeViewState(state) });
    await load();
    return true;
  }, "Perubahan tampilan gagal disimpan.");

  const setDefault = (id, on = true) => run(async () => {
    await axios.put(`${API}/saved-views/${id}`, { is_default: on });
    await load();
    return true;
  }, "Bawaan tampilan gagal diubah.");

  const remove = (id) => run(async () => {
    await axios.delete(`${API}/saved-views/${id}`);
    if (id === activeId) setActiveId("");
    await load();
    return true;
  }, "Tampilan gagal dihapus.");

  return {
    listKey, views, active, activeId, defaultId, canShare, loading, error, busy, dirty,
    select, reset, saveAs, saveActive, setDefault, remove, reload: load, clearError: () => setError(""),
  };
}

export { useSavedViews };
