/**
 * useRolePreview — PR-T6: SATU pratinjau server untuk editor peran (`POST /api/access/roles/preview`), diperbarui
 * ±500 ms setelah perubahan terakhir. Hasilnya dipakai panel Ringkasan peran (`summary`), pratinjau menu peran bawaan
 * (`nav_added`), dan notifikasi giliran (`turn_alerts`). Galat tidak menghalangi editor (panel menampilkan "Coba lagi").
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { previewAccessRole } from "./entityApi";

export const PREVIEW_DELAY_MS = 500;

/** Isi permintaan pratinjau dari keadaan editor (tanpa `base_role` untuk peran bawaan). */
export function previewBody({ roleId, custom, baseRole, perms, traits, cross }) {
  return {
    role_id: roleId || "", permissions: perms || {}, cross_entity: Boolean(cross),
    ...(custom ? { base_role: baseRole || "" } : {}),
    ...(traits && Object.keys(traits).length ? { traits } : {}),
  };
}

export default function useRolePreview(input, { enabled = true } = {}) {
  const body = JSON.stringify(previewBody(input));
  const [state, setState] = useState({ data: null, loading: enabled, error: false });
  const [nonce, setNonce] = useState(0);
  const seq = useRef(0);

  useEffect(() => {
    if (!enabled) return undefined;
    const mine = ++seq.current;
    setState((s) => ({ ...s, loading: true }));
    const t = setTimeout(() => {
      // `Promise.resolve().then(...)` — galat sinkron (mis. API tidak tersedia) ikut menjadi keadaan "galat".
      Promise.resolve().then(() => previewAccessRole(JSON.parse(body)))
        .then((data) => { if (mine === seq.current) setState({ data: data || null, loading: false, error: false }); })
        .catch(() => { if (mine === seq.current) setState((s) => ({ ...s, loading: false, error: true })); });
    }, PREVIEW_DELAY_MS);
    return () => clearTimeout(t);
  }, [body, enabled, nonce]);

  const retry = useCallback(() => setNonce((n) => n + 1), []);
  return { ...state, retry };
}
