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
 *   openConfig({ group: "makloon" })      → buka kelompoknya saja (id lama → kelompok + sub-judul barunya)
 *
 * App.js yang mendengarkan event ini, lalu berpindah view ke `settings-config`
 * dan meneruskan fokus ke <SettingsHub focusKey focusGroup focusNonce />.
 * Fase 3 · P2 (P16-K1) — tujuannya kini layar DOMAIN yang memuat kelompok itu (`settings-cfg-*`, lihat
 * `configGroupViews.js` + `hooks/useDeepLinks.js`); "Semua pengaturan" hanya bila peran tak boleh membukanya.
 */

/** Nama event global. Satu konstanta supaya tidak ada salah ketik di 2 tempat. */
export const CONFIG_EVENT = "kn-open-config";

/**
 * KF-T4 — kelompok sebuah kunci DIBACA dari indeks yang dibangkitkan registry (`configKeyIndex.json`, ditulis
 * `scripts/gen_config_key_index.py`; uji `backend/tests_mem/test_KFT4_registry.py` menegaskan berkasnya sama dengan
 * keluaran skrip). Dulu kelompok DITEBAK dari awalan kunci lewat peta salinan tangan (`LEGACY_DEEPLINK`,
 * `CONFIG_GROUP_IDS`) yang basi tiap kali kelompok bertambah.
 */
import KEY_INDEX from "./configKeyIndex.json";

/** Kelompok registri urut tampil: [{ id, label, sections: [{ id, label, advanced }] }]. */
export const CONFIG_GROUPS = KEY_INDEX.groups;
/** Salinan `config_registry.GROUP_ALIASES`: id kelompok lama → [id baru, sub-judul tujuan]. */
export const GROUP_ALIASES = KEY_INDEX.aliases;
const GROUP_IDS = new Set(CONFIG_GROUPS.map((g) => g.id));

/** `{ group, section }` untuk id kelompok baru atau lama (`{group: ""}` bila tak dikenal). */
export function resolveGroupId(group) {
  const g = String(group || "");
  if (GROUP_IDS.has(g)) return { group: g, section: "" };
  const a = GROUP_ALIASES[g];
  return a ? { group: a[0], section: a[1] || "" } : { group: "", section: "" };
}

/** Kelompok mana yang memuat sebuah kunci. Mengembalikan "" bila tak dikenal. */
export function groupForKey(key) {
  if (!key) return "";
  return (KEY_INDEX.keys[String(key)] || [""])[0];
}

/** Sub-judul sebuah kunci ("" bila tak dikenal). */
export function sectionForKey(key) {
  if (!key) return "";
  return (KEY_INDEX.keys[String(key)] || ["", ""])[1];
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
  // KF-T4 — id kelompok lama (pemanggil lama tidak diubah) diterjemahkan lewat salinan GROUP_ALIASES.
  // Kunci yang dikenal indeks → kelompok & sub-judul kunci itu sendiri (lebih tepat daripada alias kelompok lama).
  const tujuan = key && groupForKey(key) ? { group: groupForKey(key), section: sectionForKey(key) }
    : (t.group ? resolveGroupId(t.group) : { group: groupForKey(key), section: sectionForKey(key) });
  const group = tujuan.group || t.group || "";
  const section = t.section || tujuan.section || "";
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(CONFIG_EVENT, { detail: { key, group, section } }));
}
