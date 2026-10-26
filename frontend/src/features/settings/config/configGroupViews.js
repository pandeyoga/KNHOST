/**
 * configGroupViews.js — fase 3 · P2 (keputusan pemilik P16-K1): kelompok registri Pusat Pengaturan → layar domain.
 *
 * KENAPA ADA: Pengaturan dulu satu menu ber-±20 tab + Pusat Pengaturan dengan 23 kelompok di kolom kiri; pemilik
 * harus tahu sendiri bahwa "toleransi penerimaan" ada di Pusat Pengaturan sedangkan "Penerimaan & OCR" di tab lain.
 * Susunan baru menaruh tiap kelompok registri di kelompok menu DOMAIN-nya (Penjualan, Gudang & Mutu, …) sebagai
 * layar `settings-cfg-*` = Pusat Pengaturan yang dikunci ke kelompok itu. "Semua pengaturan" (`settings-config`)
 * tetap memuat semuanya (cari lintas kelompok, kesehatan, riwayat).
 *
 * Aturan (dijaga `features/__tests__/phase3Settings.test.js` + `backend/tests/test_phase3_p2_settings_groups.py`):
 *  · setiap kelompok registri (`backend/config_registry.py` GROUPS) dipetakan ke TEPAT SATU layar di bawah —
 *    kelompok baru tanpa rumah = merah (tidak boleh ada kelompok yatim);
 *  · kunci `commission.*` hanya diubah di Komisi & Insentif (D-03) — layar lain menyembunyikannya + tautan.
 *
 * Modul tanpa dependensi React (dipakai router, deep link, dan uji).
 */
import { groupForKey } from "./configDeepLink";

/** Kunci bawaan komisi (D-03) — rumahnya `incentive-rates`, bukan kelompok "Harga, Diskon & Komisi". */
export const COMMISSION_PREFIX = "commission.";
export const COMMISSION_HOME = { view: "incentive-rates", nav: "settings-sales" };

/** `view` layar domain → { nav (menu Pengaturan), groups (id kelompok registri), excludeKeys } */
export const CONFIG_GROUP_VIEWS = {
  "settings-cfg-approval":   { nav: "settings-approval", groups: ["persetujuan"] },
  "settings-cfg-sales":      { nav: "settings-sales", groups: ["harga-diskon", "retur", "amandemen"],
    excludeKeys: [COMMISSION_PREFIX] },
  "settings-cfg-warehouse":  { nav: "settings-warehouse", groups: ["penerimaan", "stok-satuan", "kualitas", "lot"] },
  "settings-cfg-purchasing": { nav: "settings-purchasing", groups: ["pembelian", "makloon", "kontrabon"] },
  "settings-cfg-finance":    { nav: "settings-finance",
    groups: ["uang-masuk", "pajak", "keuangan-dasar", "bank", "kasus", "antar-entitas"] },
  "settings-cfg-hr":         { nav: "settings-hr", groups: ["sdm"] },
  "settings-cfg-rnd":        { nav: "settings-rnd", groups: ["rnd"] },
  "settings-cfg-documents":  { nav: "settings-documents", groups: ["dokumen"] },
  "settings-cfg-notify":     { nav: "settings-notify", groups: ["notifikasi"] },
  "settings-cfg-system":     { nav: "settings-system", groups: ["tampilan", "asisten-analitik"] },
};

export const CONFIG_GROUP_VIEW_IDS = Object.keys(CONFIG_GROUP_VIEWS);

/** Layar domain yang memuat kelompok registri `group` ("" bila tak dikenal). */
export function configViewForGroup(group) {
  if (!group) return "";
  return CONFIG_GROUP_VIEW_IDS.find((v) => CONFIG_GROUP_VIEWS[v].groups.includes(group)) || "";
}

/**
 * Tujuan deep link `openConfig({ key, group })` → `{ view, nav }`.
 * Kunci komisi → Komisi & Insentif; kelompok dikenal → layar domainnya; selain itu "Semua pengaturan".
 */
export function configTargetFor({ key = "", group = "" } = {}) {
  if (String(key || "").startsWith(COMMISSION_PREFIX)) return { ...COMMISSION_HOME };
  const view = configViewForGroup(group || groupForKey(key));
  return view ? { view, nav: CONFIG_GROUP_VIEWS[view].nav } : { view: "settings-config", nav: "settings-system" };
}
