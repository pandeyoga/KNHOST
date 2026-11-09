/**
 * PREP-H — polling ramah server untuk layar gate (monitor, kios, panel U300, antrean periksa):
 *  - BERHENTI saat tab/layar tersembunyi (document.visibilityState = "hidden"); begitu terlihat lagi langsung
 *    memuat ulang (kios tidak menampilkan status basi — status "tidak terhubung" tetap dihitung dari umur data);
 *  - MUNDUR BERTAHAP saat galat: jeda ×2 setiap gagal berturut-turut, maksimal `maxMs`; kembali ke `intervalMs`
 *    begitu berhasil. `fn` WAJIB melempar galat bila gagal (agar mundur bekerja);
 *  - tidak pernah menumpuk permintaan: panggilan berikut dijadwalkan sesudah panggilan sebelumnya selesai.
 * Push (SSE/WebSocket) belum dipakai — butuh MongoDB replica set (change stream); lihat laporan PREP-H.
 */
import { useEffect, useRef } from "react";

export function nextDelay(current, base, maxMs, ok) {
  return ok ? base : Math.min(maxMs, Math.max(base, current) * 2);
}

function isHidden() {
  return typeof document !== "undefined" && document.visibilityState === "hidden";
}

export default function usePolling(fn, { intervalMs, enabled = true, maxMs = 60000, immediate = true }, deps = []) {
  const fnRef = useRef(fn);
  fnRef.current = fn;
  useEffect(() => {
    if (!enabled || !intervalMs) return undefined;
    let timer = null;
    let delay = intervalMs;
    let stopped = false;
    let running = false;
    async function tick() {
      if (stopped || running || isHidden()) return;
      running = true;
      let ok = true;
      try { await fnRef.current(); } catch { ok = false; }
      running = false;
      delay = nextDelay(delay, intervalMs, maxMs, ok);
      schedule(delay);
    }
    function schedule(ms) {
      clearTimeout(timer);
      if (!stopped && !isHidden()) timer = setTimeout(tick, ms);
    }
    function onVisible() {
      clearTimeout(timer);
      if (!isHidden()) tick();
    }
    document.addEventListener("visibilitychange", onVisible);
    if (immediate) tick(); else schedule(intervalMs);
    return () => {
      stopped = true;
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [enabled, intervalMs, maxMs, immediate, ...deps]); // eslint-disable-line react-hooks/exhaustive-deps
}
