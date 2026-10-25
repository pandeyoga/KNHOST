/**
 * useViewPreset (fase 3 · P1) — baca preset navigasi untuk SATU layar.
 *
 *   // nilai awal state dari preset (mis. dibuka lewat alias `my-approvals` → { tab: "matrix" })
 *   const preset = useViewPreset("approval-inbox");
 *   const [tab, setTab] = useState(preset?.tab || "inbox");
 *
 *   // atau terapkan setiap kali navigasi ber-preset datang (termasuk saat layar sudah terbuka):
 *   useViewPreset("rnd-samples", (p) => { if (p.mode) setMode(p.mode); if (p.type) setType(p.type); });
 *
 * Mengembalikan `null` bila navigasi terakhir tidak membawa preset untuk `view` ini. Callback `apply`
 * dipanggil sekali per `nonce` (navigasi), juga saat layar dipasang ulang (mis. ganti badan usaha) —
 * jadi pengguna tetap di tab yang dituju tautan. Perubahan tab manual tidak ditimpa selama tidak ada
 * navigasi ber-preset baru.
 */
import { useEffect, useRef } from "react";
import { useRawViewPreset } from "../context/ViewPresetContext";

export default function useViewPreset(view, apply) {
  const raw = useRawViewPreset();
  const preset = raw && raw.view === view ? raw : null;
  const applyRef = useRef(apply);
  applyRef.current = apply;
  const nonce = preset?.nonce ?? null;
  useEffect(() => {
    if (nonce === null || typeof applyRef.current !== "function") return;
    applyRef.current(preset);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce]);
  return preset;
}

export { useViewPreset };
