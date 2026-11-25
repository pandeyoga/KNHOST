// Status tampilan meja yang bertahan selama sesi tab (sessionStorage):
//   kartu antrean  `kn.meja.kartu.<deskKey>:<queueId>` → { q, st, sort, page }
//   halaman meja   `kn.meja.<deskKey>`                  → { tab, scrollY, returnPending }
// Setiap baca/tulis dibungkus try/catch: mode privat, kuota penuh, atau penyimpanan diblokir tidak boleh
// mematahkan meja — paling buruk statusnya tidak diingat.
import { useEffect, useRef } from "react";

const KARTU = "kn.meja.kartu.";
const MEJA = "kn.meja.";

export const cardStateKey = (stateKey) => `${KARTU}${stateKey}`;
export const pageStateKey = (deskKey) => `${MEJA}${deskKey}`;

/** Objek tersimpan di `key`; `{}` bila tidak ada, rusak, bukan objek, atau penyimpanan tidak bisa dibaca. */
export function readDeskState(key) {
  try {
    const raw = window.sessionStorage.getItem(key);
    if (!raw) return {};
    const v = JSON.parse(raw);
    return v && typeof v === "object" && !Array.isArray(v) ? v : {};
  } catch {
    return {};
  }
}

/** Gabungkan `patch` ke objek tersimpan di `key`; kegagalan penyimpanan diabaikan. */
export function writeDeskState(key, patch) {
  try {
    window.sessionStorage.setItem(key, JSON.stringify({ ...readDeskState(key), ...patch }));
  } catch {
    /* penyimpanan penuh/diblokir — status tidak diingat, meja tetap jalan */
  }
}

/**
 * Tandai bahwa pengguna meninggalkan meja ke layar lain (aksi pindah layar, "Buka layar penuh", tautan Pelacak):
 * posisi gulir disimpan dan meja akan menggulir kembali ke sana saat dibuka lagi (`useDeskScrollRestore`).
 */
export function markDeskReturn(deskKey) {
  let scrollY = 0;
  try { scrollY = window.scrollY || 0; } catch { scrollY = 0; }
  writeDeskState(pageStateKey(deskKey), { scrollY, returnPending: true });
}

/**
 * Saat `ready` pertama kali benar (antrean sudah tergambar) dan ada tanda kembali, gulir ke posisi tersimpan lalu hapus
 * tandanya — membuka meja biasa (tanpa tanda) tidak menggulir apa pun.
 */
export function useDeskScrollRestore(deskKey, ready) {
  const done = useRef(false);
  useEffect(() => {
    if (!ready || done.current) return;
    done.current = true;
    const key = pageStateKey(deskKey);
    const s = readDeskState(key);
    if (!s.returnPending) return;
    try { window.scrollTo(0, Number(s.scrollY) || 0); } catch { /* lingkungan tanpa gulir — abaikan */ }
    writeDeskState(key, { returnPending: false });
  }, [deskKey, ready]);
}
