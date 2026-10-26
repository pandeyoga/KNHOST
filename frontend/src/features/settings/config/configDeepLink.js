/**
 * configDeepLink.js — FASE G-0 · jembatan "buka pengaturan ini" dari mana pun.
 *
 * KENAPA MODUL TERPISAH (bukan di SettingsHub.jsx):
 *   SettingsHub di-`lazy()`. Kalau helper deep-link tinggal di dalamnya, setiap
 *   layar yang cuma ingin MENAUTKAN ke sebuah setting jadi ikut menarik seluruh
 *   bundel Pusat Pengaturan. Modul ini sengaja **tanpa dependensi** (tidak impor
 *   React, tidak impor axios) supaya murah dipakai di layar mana pun.
 *
 * POLA EVENT GLOBAL:
 *   Repo ini sudah punya `kn-open-palette` (lihat components/CommandPalette.jsx)
 *   untuk membuka Command Palette dari komponen sedalam apa pun tanpa prop
 *   drilling. Deep-link konfigurasi memakai pola yang sama: `kn-open-config`.
 *
 *   openConfig({ key: "tax.ppn_rate" })   → buka kartu setting itu (scroll + sorot)
 *   openConfig({ group: "makloon" })      → buka kelompoknya saja
 *
 * App.js yang mendengarkan event ini, lalu berpindah view ke `settings-config`
 * dan meneruskan fokus ke <SettingsHub focusKey focusGroup focusNonce />.
 * Fase 3 · P2 (P16-K1) — tujuannya kini layar DOMAIN yang memuat kelompok itu (`settings-cfg-*`, lihat
 * `configGroupViews.js` + `hooks/useDeepLinks.js`); "Semua pengaturan" hanya bila peran tak boleh membukanya.
 */

/** Nama event global. Satu konstanta supaya tidak ada salah ketik di 2 tempat. */
export const CONFIG_EVENT = "kn-open-config";

/**
 * Peta prefiks kunci → id kelompok di Pusat Pengaturan.
 *
 * Dipakai supaya pemanggil cukup menyebut `key` (mis. `hr.bpjs.kes_rate_employee`)
 * tanpa perlu tahu kelompok mana yang memuatnya. Id kelompok = `groups[].id`
 * dari `GET /api/config/registry` (sumber kebenaran ada di backend
 * `config_registry.py`; peta ini hanya jalan pintas navigasi, bukan data).
 */
export const LEGACY_DEEPLINK = {
  tax: "pajak",
  ar: "uang-masuk",
  amendment: "amandemen",
  pricing: "harga-diskon",
  commission: "harga-diskon",
  approval: "persetujuan",
  purchasing: "pembelian",
  receiving: "penerimaan",
  inventory: "stok-satuan",
  uom: "stok-satuan",
  allocation: "stok-satuan",
  qc: "kualitas",
  lot: "lot",
  makloon: "makloon",
  hr: "sdm",
  ui: "tampilan",
  role_home: "tampilan",
  finance: "keuangan-dasar",
  sales: "harga-diskon",
  // Fase 3 · P2 — prefiks registri yang dulu tak terpetakan (deep link berbasis kunci jatuh ke kelompok pertama).
  // Prefiks yang dipakai >1 kelompok (finance, inventory, purchasing, sales) tetap ke kelompok mayoritasnya;
  // pemanggil yang tahu kelompoknya mengirim `group` sendiri.
  ai: "asisten-analitik",
  antar_entitas: "antar-entitas",
  bank: "bank",
  case: "kasus",
  catalog: "stok-satuan",
  contra_bon: "kontrabon",
  cutting: "stok-satuan",
  docref: "dokumen",
  notif: "notifikasi",
  payment: "uang-masuk",
  periode: "keuangan-dasar",
  pos: "tampilan",
  pricelist: "harga-diskon",
  returns: "retur",
  rnd: "rnd",
  saga: "keuangan-dasar",
  sales_admin: "persetujuan",
  wms: "stok-satuan",
};

/** Semua id kelompok yang valid (dipakai untuk membedakan key vs group). Cermin `backend/config_registry.py`. */
export const CONFIG_GROUP_IDS = [
  "uang-masuk", "harga-diskon", "persetujuan", "pajak", "keuangan-dasar",
  "pembelian", "penerimaan", "stok-satuan", "kualitas", "lot", "makloon",
  "sdm", "tampilan", "amandemen",
  // Fase 3 · P2 — kelompok yang lahir sesudah daftar ini ditulis (G-1..L08).
  "dokumen", "rnd", "bank", "kasus", "kontrabon", "antar-entitas", "notifikasi", "asisten-analitik", "retur",
];

/** Kelompok mana yang memuat sebuah kunci. Mengembalikan "" bila tak dikenal. */
export function groupForKey(key) {
  if (!key) return "";
  const prefix = String(key).split(".")[0];
  return LEGACY_DEEPLINK[prefix] || "";
}

/**
 * Buka Pusat Pengaturan pada kunci / kelompok tertentu.
 *
 * @param {{key?: string, group?: string}|string} target
 *   String dianggap `key`. Objek boleh berisi `key`, `group`, atau keduanya.
 */
export function openConfig(target) {
  const t = typeof target === "string" ? { key: target } : (target || {});
  const key = t.key || "";
  const group = t.group || groupForKey(key);
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(CONFIG_EVENT, { detail: { key, group } }));
}
