/**
 * deskQueueOrder — URUTAN TAMPIL antrean meja kerja (penyajian saja).
 *
 * Perapian Meja Finance (14 Nov 2026): dari belasan kartu antrean, biasanya hanya satu-dua yang berisi.
 * Kartu bernilai 0 yang tampil sebesar kartu berisi membuat antrean yang benar-benar perlu ditindak
 * tenggelam (KN_08 — progressive disclosure). Modul ini memisahkan keduanya:
 *   · `filled` — antrean ber-isi, diurutkan **umur tertua dulu**, lalu **nilai rupiah terbesar**, lalu
 *     **jumlah dokumen terbanyak**; seri terakhir mengikuti urutan server (stabil).
 *   · `empty`  — antrean kosong, urutan server.
 * Meja gelombang 1 (spek 2026-11-25 §5.1–§5.2): kartu ukuran tetap digambar berurutan `orderDeskQueues` (berisi
 * terurut, lalu kosong); antrean PANTAU (bukan pekerjaan meja ini, hanya dipantau) dipisah ke tab Pantau
 * (`splitPantau`). Meja Keuangan tetap tidak menggambar kelompok kosong (MN-T2) dan memakai pembandingnya sendiri.
 *
 * Yang TIDAK dilakukan di sini: menghitung ulang apa pun. `count`, `total_value`, `oldest_age_days`
 * dibaca apa adanya dari server (`work_desk_service._queue`) — modul ini hanya memilih URUTAN.
 */

const num = (v) => Number(v) || 0;
const isMoney = (q) => !q?.value_kind || q.value_kind === "money";

/** Pembanding antrean ber-isi: umur tertua → nilai rupiah (hanya antar-antrean rupiah) → jumlah. */
export function compareFilledQueues(a, b) {
  const age = num(b?.oldest_age_days) - num(a?.oldest_age_days);
  if (age) return age;
  // yard/kg/jumlah dokumen tidak sebanding dengan rupiah — nilai hanya membandingkan sesama rupiah.
  if (isMoney(a) && isMoney(b)) {
    const val = num(b?.total_value) - num(a?.total_value);
    if (val) return val;
  }
  return num(b?.count) - num(a?.count);
}

/** Pisahkan antrean menjadi { filled (terurut), empty (urutan server) }. Masukan tidak diubah. */
export function splitDeskQueues(queues) {
  const list = Array.isArray(queues) ? queues : [];
  const filled = [];
  const empty = [];
  list.forEach((q, i) => (num(q?.count) > 0 ? filled : empty).push({ q, i }));
  filled.sort((x, y) => compareFilledQueues(x.q, y.q) || x.i - y.i);
  return { filled: filled.map((x) => x.q), empty: empty.map((x) => x.q) };
}

/** Urutan tampil kartu meja: antrean berisi (terurut `compareFilledQueues`), lalu antrean kosong (urutan server). */
export function orderDeskQueues(queues) {
  const { filled, empty } = splitDeskQueues(queues);
  return [...filled, ...empty];
}

/** Antrean yang hanya DIPANTAU meja itu (pekerjaannya milik orang lain) — tampil di tab Pantau, bukan Antrean. */
export const PANTAU_QUEUE_IDS = {
  sales_admin: ["menunggu_manajer"],
  sample_admin: ["di_gudang", "kirim_ambil", "selesai"],
};

/** Pisahkan antrean meja `deskKey` menjadi { antrean, pantau }; keduanya urutan server, masukan tidak diubah. */
export function splitPantau(queues, deskKey) {
  const ids = PANTAU_QUEUE_IDS[deskKey] || [];
  const list = Array.isArray(queues) ? queues : [];
  return {
    antrean: list.filter((q) => !ids.includes(q?.id)),
    pantau: list.filter((q) => ids.includes(q?.id)),
  };
}
