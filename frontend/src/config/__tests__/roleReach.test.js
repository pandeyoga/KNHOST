// Fase 3 · P1 — UJI JANGKAUAN PERAN berbaseline (rencana fase 3 §0 & §1.1).
//
// Penggabungan layar duplikat (P2–P8) TIDAK boleh membuat peran bawaan kehilangan layar, dan TIDAK boleh diam-diam
// membuka layar baru. Baseline `fixtures/role_reach_baseline.json` dibuat dari konfigurasi SEBELUM fase 3 (HEAD
// b2c092e): untuk tiap peran, setiap id alamat (`?view=<id>`: view tab, id menu/hub, beranda, nama lama) → layar
// tempat ia mendarat. JANGAN membuat ulang baseline dari konfigurasi baru — itu menghapus bukti.
//
// Aturan:
//  1. Setiap id yang dulu sampai MASIH sampai, ke layar yang sama atau ke layar utama alias-nya (registri alias).
//  2. Tidak ada layar tujuan BARU untuk sebuah peran, kecuali tercatat di ROLE_REACH_ADDITIONS (tabel §6 rencana
//     fase 3 — diisi P8/P2 saat aktivasi, satu baris per keputusan).
import baseline from "./fixtures/role_reach_baseline.json";
import { HUB_TABS, NAV_STRUCTURE, ROLE_HOME_REGISTRY, resolveDeepLinkTarget } from "../navigationConfig";
import { ROLE_IDS } from "../roles";
import { aliasTarget, listAliases } from "../viewAliases";

/** Penambahan jangkauan yang SAH: { peran: ["view", …] } + alasan di komentar (rujuk D-xx / §6). */
// Fase 3 · P2 (P16-K1) — layar Pengaturan per domain = Pusat Pengaturan yang DIKUNCI ke kelompok registrinya (fungsi
// yang sudah dimiliki admin/manajer lewat `settings-config`, kini juga di menu domainnya) + Koreksi Harga (dulu tab
// Pusat Pengaturan; manajer: pratinjau dampak saja, server product.view).
const P2_SETTINGS_VIEWS = [
  "settings-cfg-approval", "settings-cfg-sales", "settings-cfg-warehouse", "settings-cfg-purchasing",
  "settings-cfg-finance", "settings-cfg-hr", "settings-cfg-rnd", "settings-cfg-documents", "settings-cfg-notify",
  "settings-cfg-system", "price-corrections",
];
// Fase 3 · P8 (D-23) — tab tersembunyi Master Pembelian › "Harga Internal Antar-PT" (`supplier-internal-prices`, peran =
// peran Kontrak; layar = InternalPricesView). Id layar BARU untuk fungsi yang dulu ada di Kontrak (tab Harga Internal +
// "Isi massal"). Gudang tidak mendapatkannya: menu Master Pembelian memang tertutup untuk gudang (tanpa saudara tab).
const P8_SUPPLIER_INTERNAL = ["supplier-internal-prices"];
// KF-T6 — tab Pengaturan › Persetujuan › Kontrol dua orang (baca `settings.view`; ubah `settings.manage`).
const KFT6_DUAL_CONTROL = ["settings-dual-control"];
// MN-T1 — id layar BARU untuk layar yang SUDAH ADA: empat sub-tab CRM & Pelanggan kini tab hub sendiri (komponen sama;
// dulu terjangkau sebagai isi `customers-crm`): Penagihan & Penerimaan, Kredit & Plafon (Keuangan › Piutang), Kinerja
// Sales, Skema (Arsip) (SDM › Kinerja & Insentif). Peran mendapatkannya sesuai kolom "Peran bawaan" tabel MN-T1.
// KP-T5 — tab Pengaturan › Dokumen & Notifikasi › Penomoran Dokumen (baca `settings.view`; ubah `settings.manage`).
const KPT5_DOC_NUMBERING = ["settings-doc-numbering"];
const MNT1_CRM_TABS = ["collection-worklist", "credit-overrides", "sales-performance", "incentive-schemes"];
// PK-28 (IV-03) — layar BARU Keuangan › Hutang › GR/IR (Diterima Belum Ditagih): admin, manajer, Finance (vendor_bill.view).
const PK28_GRIR = ["gr-ir"];
// PK-22 (FY-07) — layar BARU SDM › Penggajian › Setoran Kewajiban (tab ketiga hub Penggajian): admin, manajer.
const PK22_SETORAN = ["hr-payroll-remittances"];
// KM-T1 — layar BARU SDM › Kinerja & Insentif › Target & Aturan (Meja Insentif; `incentive.view`): admin, manajer, Finance.
const KMT1_TARGET_ATURAN = ["incentive-setup"];
// KM-T2 — layar BARU SDM › Kinerja & Insentif › Capaian (Meja Insentif; `incentive.view`): admin, manajer, Finance.
const KMT2_CAPAIAN = ["incentive-capaian"];
// KM-T3 — layar BARU SDM › Kinerja & Insentif › Lembar Insentif (penyiap `incentive.prepare`: admin, manajer, Finance,
// Admin Sales; pemutus `incentive.approve`: admin, manajer).
const KMT3_LEMBAR = ["incentive-sheets"];
// PY-T1 (K-37) — layar BARU SDM › Penggajian › Komponen & Masukan (tab hub Penggajian): admin, manajer.
const PYT1_KOMPONEN = ["hr-pay-components"];
// PM-T4 (K-36) — layar BARU Keuangan › Kas & Bank › Titipan Sales (setoran titipan tunai; `cash_holding.approve`): admin,
// manajer, Finance.
const PMT4_TITIPAN = ["cash-holdings"];
// PY-T4 (K-41) — Finance mendapat SDM › Penggajian › Setoran & Pajak (`payroll.pay`: bayar gaji, setor BPJS/PPh 21);
// tab lain hub Penggajian tetap admin & manajer.
const PYT4_SETORAN_FINANCE = ["hr-payroll-remittances"];
// PY-T3 — layar BARU Pengaturan › SDM › Kalender Libur (tab hub SDM; lihat `hr.view`, ubah `hr.manage_attendance`): admin, manajer.
const PYT3_LIBUR = ["hr-holidays"];
// KP-T9 — id layar BARU untuk bagian layar yang SUDAH ADA: layar wadah Badan Usaha & Akses, Perangkat, dan Penjadwal &
// Notifikasi dibuka satu bagian per tab hub (komponen sama, prop `only`). `settings-pt-profile` = tujuan alias
// `entities-access` (sudah di baseline). Manajer: Peran & Hak Akses / Cek Peran hanya tampil menurut rancangan menu — izin
// server (tanpa `permission`) menyembunyikannya (serverAccessReach.test.js); Perangkat RFID tetap khusus admin.
const KPT9_PART_TABS = ["settings-pt-readiness", "settings-accounts", "settings-role-check", "settings-attendance-devices",
  "settings-whatsapp"];
export const ROLE_REACH_ADDITIONS = {
  admin: [...P2_SETTINGS_VIEWS, ...P8_SUPPLIER_INTERNAL, ...KFT6_DUAL_CONTROL, ...KPT5_DOC_NUMBERING, ...MNT1_CRM_TABS,
    ...KPT9_PART_TABS, ...PK28_GRIR, ...PK22_SETORAN, ...KMT1_TARGET_ATURAN, ...KMT2_CAPAIAN, ...PYT1_KOMPONEN, ...PMT4_TITIPAN, ...PYT3_LIBUR,
    ...KMT3_LEMBAR],
  manager: [...P2_SETTINGS_VIEWS, ...P8_SUPPLIER_INTERNAL, ...KFT6_DUAL_CONTROL, ...KPT5_DOC_NUMBERING, ...MNT1_CRM_TABS,
    ...KPT9_PART_TABS, ...PK28_GRIR, ...PK22_SETORAN, ...KMT1_TARGET_ATURAN, ...KMT2_CAPAIAN, ...PYT1_KOMPONEN, ...PMT4_TITIPAN, ...PYT3_LIBUR,
    ...KMT3_LEMBAR,
    "finance-desk",       // MN-T1 — Beranda Keuangan › Perlu Tindakan (Meja Finance; manajer memegang payment_variance.decide)
    "approval-rules",     // D-04 — manajer membaca aturan (dulu lewat Master per Badan Usaha), tulis tetap settings.manage
    "pdf-templates",      // D-01 — tab "Kop & tata letak dasar" (dulu Master per BU kind document-templates); Desainer PDF tetap admin
    "settings-devices",   // D-29 — tab Mesin absen (dulu Shift & Geofence › Perangkat); KP-T9: kini settings-attendance-devices
    // FIX-1 (K-B1-07, keputusan 9 Nov — audit B1 UI-20/B1b UI-57) — manajer mendapat menu RFID (baca) termasuk
    // Monitor Gerbang (operasional gate U300). Sapu RFID di Stock Opname tetap tertutup (D-15).
    "cs-rfid-lokasi", "cs-rfid-tags", "cs-rfid-gate",
  ],
  // Fase 3 · P8 (D-22) — Kinerja Mitra Makloon: gudang dulu melihat skor mitra di Klaim Selisih Makloon. Admin Gudang
  // mewarisi menu gudang (ROLE_NAV inherit "warehouse"), jadi ikut — bukan keputusan terpisah.
  // FIX-4 (K-B4-07 · K-B3b-04, 9 Nov) — petugas gudang boleh mengunduh daftar gudang; unduhan > 50.000 baris
  // menjadi job yang diambil di Pusat Export (dataset dibatasi daftar putih gudang di server).
  warehouse: ["makloon-claim-recap", "export-center"],
  warehouse_admin: ["makloon-claim-recap"],
  // MN-T1 (IA-06) — "Kasus Keuangan" mencantumkan sales (izin finance_case.view/create) tetapi grup induknya hanya admin &
  // manajer → sales tidak pernah melihatnya; kini grup Keuangan memuat sales. + Penagihan & Penerimaan dan Kinerja Sales
  // (dulu sub-tab CRM; Admin Sales mewarisi menu sales).
  sales: ["finance-cases", "collection-worklist", "sales-performance"],
  sales_admin: ["finance-cases", "collection-worklist", "sales-performance", ...KMT3_LEMBAR],
  // MN-T1 — menu Finance mengikuti izin bawaannya (UX-17): Rekening & Saldo dan Rekonsiliasi (K-09: ya; izin `cash`),
  // Kas Kecil (izin `cash_advance` sudah dipegang), Buku Besar lihat saja (K-09; `accounting.view`), Hutang lihat &
  // bayar (K-17), Analisis/BI Keuangan (`accounting.view`), Pemetaan Akun (IA-06; `gl_mapping.view/update`), dan dua tab
  // Piutang yang dulu sub-tab CRM (Penagihan & Penerimaan; Kredit & Plafon tanpa hak memutus).
  finance: ["bank-accounts", "bank-reconciliation", "petty-cash", "general-ledger", "chart-of-accounts",
    "vendor-bills", "contra-bons", "bi-finance", "gl-account-mappings", "collection-worklist", "credit-overrides",
    ...PK28_GRIR, ...KMT1_TARGET_ATURAN, ...KMT2_CAPAIAN, ...PMT4_TITIPAN, ...PYT4_SETORAN_FINANCE, ...KMT3_LEMBAR],
};
/** Id MENU/HUB yang kini mendarat di tab pertama LAIN di hub yang sama (urutan/isi tab baru), sementara layar lamanya tetap
 *  terjangkau (diperiksa): { peran: { id: "view baru" } } + alasan.
 *  · MN-T1 — SDM › Kinerja & Insentif: tab pertama kini Kinerja Sales (urutan tabel MN-T1); KPI Karyawan tetap tab hub.
 *  · MN-T1 — Kas & Bank untuk Finance: kini memuat Rekening & Saldo (K-09) sebagai tab pertama; Transaksi Kas tetap.
 *  · KM-T2 — SDM › Kinerja & Insentif: tab pertama kini Capaian (spesifikasi KM-T2 "Layar"); Kinerja Sales tetap tab hub. */
export const ROLE_REACH_RELANDED = {
  admin: { "hr-kpi-hub": "incentive-capaian" },
  manager: { "hr-kpi-hub": "incentive-capaian" },
  finance: { "cash-bank": "bank-accounts" },
};
/** Pencabutan jangkauan yang SAH (layar yang server-nya menolak peran itu): { peran: ["id", …] } + alasan. */
// FIX-1 (audit B1b UI-48) — "Meja Saya" untuk Admin Gudang & Admin Sales: server `/desks/me` menolak kedua peran
// ("memakai meja khususnya sendiri"); mejanya = Meja Gudang / Meja Admin Sales. Menu yang hanya berujung galat dicabut.
export const ROLE_REACH_REMOVALS = {
  warehouse_admin: ["my-desk"],
  sales_admin: ["my-desk"],
};

function universe() {
  const ids = new Set(baseline.universe);
  Object.values(HUB_TABS).flat().forEach((t) => ids.add(t.view));
  NAV_STRUCTURE.forEach((e) => {
    if (e.type === "standalone") { ids.add(e.id); if (e.view) ids.add(e.view); if (e.hub) ids.add(e.hub); }
    else {
      ids.add(e.groupId);
      (e.items || []).forEach((i) => { if (i.type === "heading") return; ids.add(i.id); if (i.view) ids.add(i.view); if (i.hub) ids.add(i.hub); });
    }
  });
  Object.values(ROLE_HOME_REGISTRY).forEach((h) => { ids.add(h.view); ids.add(h.navId); });
  listAliases().forEach((a) => ids.add(a.from));
  return [...ids].filter(Boolean).sort();
}

const BUILTIN = ROLE_IDS.filter((r) => !String(r).startsWith("cr_") && r !== "__preview");

test("baseline mencakup semua peran bawaan (peran bawaan baru = baseline baru yang disengaja)", () => {
  expect(BUILTIN.filter((r) => !baseline.roles[r])).toEqual([]);
});

test("bukti-merah: mencabut peran dari sebuah tab TERDETEKSI sebagai jangkauan hilang", () => {
  const tab = HUB_TABS["sales-orders"].find((t) => t.view === "keep-pending");
  const roles = tab.roles;
  tab.roles = ["admin"];
  try {
    expect(baseline.roles.sales["keep-pending"]).toBe("keep-pending");
    expect(resolveDeepLinkTarget("keep-pending", "sales")).toBeNull();
  } finally { tab.roles = roles; }
  expect(resolveDeepLinkTarget("keep-pending", "sales")).toMatchObject({ view: "keep-pending" });
});

describe.each(BUILTIN)("peran %s", (role) => {
  test("setiap alamat yang dulu sampai, masih sampai ke layar yang sama / layar utama aliasnya", () => {
    const lost = [];
    const removed = new Set(ROLE_REACH_REMOVALS[role] || []);
    const relanded = ROLE_REACH_RELANDED[role] || {};
    for (const [id, view] of Object.entries(baseline.roles[role] || {})) {
      if (removed.has(id)) continue;
      const t = resolveDeepLinkTarget(id, role);
      if (relanded[id]) {   // MN-T1 — mendarat di tab baru yang tercatat, DAN layar lamanya tetap terjangkau
        if (t?.view !== relanded[id] || resolveDeepLinkTarget(view, role)?.view !== view) lost.push(`${id} → ${t?.view} (tercatat ${relanded[id]}; ${view} tetap?)`);
        continue;
      }
      const ok = new Set([view, aliasTarget(view), aliasTarget(id)]);
      if (!t) lost.push(`${id} → (tidak sampai; dulu ${view})`);
      else if (!ok.has(t.view)) lost.push(`${id} → ${t.view} (dulu ${view})`);
    }
    expect(lost).toEqual([]);
  });

  test("tidak ada layar tujuan BARU selain penambahan tercatat", () => {
    const before = new Set(Object.values(baseline.roles[role] || {}).map(aliasTarget));
    const allowed = new Set(ROLE_REACH_ADDITIONS[role] || []);
    const extra = [];
    for (const id of universe()) {
      const t = resolveDeepLinkTarget(id, role);
      if (t && !before.has(t.view) && !allowed.has(t.view)) extra.push(`${id} → ${t.view}`);
    }
    expect(extra).toEqual([]);
  });
});
