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
import { groupForKey, resolveGroupId } from "./configDeepLink";

/** Kunci bawaan komisi (D-03) — rumahnya Target & Aturan › "Komisi otomatis (cara lama)" (KM-T5; dulu tab
 *  `incentive-rates`), bukan kelompok "Harga, Diskon & Komisi". */
export const COMMISSION_PREFIX = "commission.";
// MN-T1 — Komisi & Insentif kini SDM › Kinerja & Insentif › Target & Aturan (view sama, menu `hr-kpi-hub`).
// KM-T5 — tab "Komisi Otomatis" dicabut; bawaan komisi kini di Target & Aturan › "Komisi otomatis (cara lama)".
export const COMMISSION_HOME = { view: "incentive-setup", nav: "hr-kpi-hub" };

/** KF-T6 — kunci `kontrol.*` (kontrol dua orang) hanya diubah di tab Persetujuan › Kontrol dua orang. */
export const DUAL_CONTROL_PREFIX = "kontrol.";
export const DUAL_CONTROL_HOME = { view: "settings-dual-control", nav: "settings-approval" };
export const DUAL_CONTROL_LINK = {
  testId: "cfg-dual-control-link", what: "Kontrol dua orang (pengaju ≠ pemutus)", view: "settings-dual-control",
  where: "Pengaturan › Persetujuan › Kontrol dua orang",
};

/**
 * `view` layar domain → { nav (menu Pengaturan), groups (id kelompok registri), excludeKeys }.
 * KF-T4 — 13 kelompok bersub-judul (`backend/config_registry.py` GROUPS); delapan layar. Dua layar lama kehilangan
 * kelompoknya dan menjadi alias (`config/viewAliases.js`): `settings-cfg-documents` → sub-judul "Rujukan antar dokumen",
 * `settings-cfg-notify` → sub-judul "Pemberitahuan", keduanya di `settings-cfg-approval`.
 */
export const CONFIG_GROUP_VIEWS = {
  "settings-cfg-approval":   { nav: "settings-approval", groups: ["persetujuan"],
    excludeKeys: [DUAL_CONTROL_PREFIX], excludeLink: DUAL_CONTROL_LINK },   // KF-T6
  "settings-cfg-sales":      { nav: "settings-sales", groups: ["penjualan", "retur-koreksi"],
    excludeKeys: [COMMISSION_PREFIX] },
  "settings-cfg-warehouse":  { nav: "settings-warehouse", groups: ["penerimaan", "kualitas", "stok"] },
  "settings-cfg-purchasing": { nav: "settings-warehouse", groups: ["pembelian"] },   // KP-T9 — dulu hub Pembelian & Produksi
  "settings-cfg-finance":    { nav: "settings-finance",
    groups: ["pembayaran-pelanggan", "pajak-pembukuan", "bank-kasus"] },
  "settings-cfg-hr":         { nav: "settings-hr", groups: ["sdm"] },
  "settings-cfg-rnd":        { nav: "settings-warehouse", groups: ["rnd"] },          // KP-T9 — dulu hub R&D
  "settings-cfg-system":     { nav: "settings-system", groups: ["sistem", "keamanan"] },   // KF-T7 — + Keamanan akun & sesi
};

export const CONFIG_GROUP_VIEW_IDS = Object.keys(CONFIG_GROUP_VIEWS);

/**
 * KP-T9 (KP-29) — pengaturan yang tinggal di layar lain di luar grup Pengaturan: kartu tautan (`LinkCard`
 * `hideWhenDenied`) di bawah daftar kartu layar ini. `where` = nama menu tujuannya (dijaga uji
 * `features/__tests__/kpt9BagianLayar.test.js` terhadap breadcrumb menu). Tab WhatsApp dirender rute
 * (`AppViewRouter`) di bawah layar Penjadwal.
 */
export const SETTINGS_LINKS = {
  "settings-cfg-finance": [
    { what: "Jadwal bayar antar-PT", view: "interco-transactions", where: "Keuangan › Antar-PT" },
    { what: "Rekening bank dan kas tiap PT", view: "bank-accounts", where: "Keuangan › Kas & Bank › Rekening & Saldo" },
    { what: "Syarat pembayaran", view: "entity-masters", where: "Pengaturan › Perusahaan (PT) › Master per PT" },
  ],
  "settings-cfg-warehouse": [
    { what: "Daftar gudang dan lokasi", view: "md-warehouses", where: "Gudang & Logistik › Data Gudang" },
  ],
  "settings-whatsapp": [
    { what: "WhatsApp untuk mengirim dokumen dan aturan kirim otomatis", view: "document-center",
      where: "Pusat Dokumen › Daftar Dokumen" },
  ],
};

/** Layar domain yang memuat kelompok registri `group` ("" bila tak dikenal). KF-T4 — id kelompok lama diterjemahkan. */
export function configViewForGroup(group) {
  const g = resolveGroupId(group).group;
  if (!g) return "";
  return CONFIG_GROUP_VIEW_IDS.find((v) => CONFIG_GROUP_VIEWS[v].groups.includes(g)) || "";
}

/**
 * Tujuan deep link `openConfig({ key, group })` → `{ view, nav }`.
 * Kunci komisi → Komisi & Insentif; kelompok dikenal → layar domainnya; selain itu "Semua pengaturan".
 */
export function configTargetFor({ key = "", group = "" } = {}) {
  if (String(key || "").startsWith(COMMISSION_PREFIX)) return { ...COMMISSION_HOME };
  if (String(key || "").startsWith(DUAL_CONTROL_PREFIX)) return { ...DUAL_CONTROL_HOME };   // KF-T6
  const view = configViewForGroup(group || groupForKey(key));
  return view ? { view, nav: CONFIG_GROUP_VIEWS[view].nav } : { view: "settings-config", nav: "settings-system" };
}
