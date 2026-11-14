// KP-T4 — boleh-tidaknya PENGGUNA INI memutus satu dokumen, ditanyakan ke server (Aturan Persetujuan + izin), supaya
// tombol Setujui/Tolak mati dengan petunjuk yang sama dengan penolakan server (`GET /api/approval-policies/can-decide/me`).
// Layar tidak lagi menebak dari peringkat peran.
import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../services/apiClient";

export const DECIDE_UNKNOWN = { allowed: false, message: "", loading: true };

export async function fetchCanDecide({ docKind, entityId, amount = 0, level = 1, action = "approve" }) {
  const r = await axios.get(`${API}/approval-policies/can-decide/me`,
    { params: { doc_kind: docKind, entity_id: entityId || undefined, amount: Number(amount) || 0, level, action } });
  return { allowed: !!r.data?.allowed, message: r.data?.message || "", loading: false };
}

/**
 * Peta `id dokumen → {allowed, message, loading}` untuk daftar dokumen yang menunggu keputusan.
 * `toParams(doc)` → `{docKind, entityId, amount, level}` atau `null` (dokumen tidak menunggu → dilewati).
 */
export function useCanDecideMap(docs, toParams) {
  const [map, setMap] = useState({});
  const wanted = useMemo(() => (docs || []).map((d) => [d?.id, d ? toParams(d) : null])
    .filter(([id, p]) => id && p), [docs, toParams]);
  const sig = JSON.stringify(wanted);
  useEffect(() => {
    let alive = true;
    (async () => {
      const out = {};
      for (const [id, p] of wanted) {
        try {
          out[id] = await fetchCanDecide(p);
        } catch (e) {
          out[id] = { allowed: false, loading: false,
            message: e?.response?.data?.detail && typeof e.response.data.detail === "string"
              ? e.response.data.detail : "Tidak dapat memeriksa wewenang persetujuan. Muat ulang." };
        }
      }
      if (alive) setMap(out);
    })();
    return () => { alive = false; };
  }, [sig]); // eslint-disable-line react-hooks/exhaustive-deps
  return map;
}
