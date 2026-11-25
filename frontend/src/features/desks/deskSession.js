// Status tampilan meja yang bertahan selama sesi tab (sessionStorage):
//   kartu antrean  `kn.meja.kartu.<deskKey>:<queueId>` → { q, st, sort, page }
//   halaman meja   `kn.meja.<deskKey>`                  → { tab, scrollY, returnPending }
// Setiap baca/tulis dibungkus try/catch: mode privat, kuota penuh, atau penyimpanan diblokir tidak boleh
// mematahkan meja — paling buruk statusnya tidak diingat.

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
