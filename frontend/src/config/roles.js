/**
 * roles.js — FASE E-8 (E8.1) · **REGISTRY PERAN sisi layar** (cermin
 * `backend/role_registry.py`).
 */
import { ROLE_HOME_REGISTRY } from "./navMeta";

/*
 * KENAPA ADA: label peran, beranda peran, dan "siapa boleh melihat menu apa" dulu
 * tersebar sebagai literal `"manager"`/`"sales"` di ~81 tempat. Menambah dua peran
 * baru (`sales_admin`, `finance`) dengan cara lama berarti menyunting puluhan berkas
 * dan berharap tidak ada yang terlewat.
 *
 * SATU aturan penting soal MENU: `navStructure.js`/`hubTabs.js` TIDAK disentuh untuk
 * peran baru. Alasannya bukan kemalasan — daftar `roles:` di sana adalah niat desain
 * yang sudah diaudit; menambah dua nama ke ~40 baris membuat riwayat perubahan sulit
 * dibaca dan mudah salah. Sebagai gantinya peran baru dinyatakan EKSPLISIT di satu
 * tempat (di bawah): mewarisi menu peran lain, ditambah/dikurangi daftar yang jelas.
 * Dengan begitu "Admin Sales boleh lihat apa" bisa dibaca sekali pandang.
 */

export const ROLE_REGISTRY = {
  admin: {
    label: "Admin",
    longLabel: "Admin sistem",
    rank: 4,
    crossEntity: true,
    scopeHint: "lintas badan usaha",
    order: 1,
  },
  manager: {
    label: "Manajer",
    longLabel: "Manajer",
    rank: 3,
    crossEntity: true,
    scopeHint: "lintas badan usaha",
    order: 2,
  },
  sales_admin: {
    label: "Admin Sales",
    longLabel: "Admin Sales (alur pesanan)",
    rank: 2,
    crossEntity: false,
    scopeHint: "1 badan usaha (bisa ditugaskan ke beberapa)",
    order: 3,
    newIn: "E-8",
  },
  // K-FIN-01 (pemilik 17 Nov 2026 malam: "untuk sekarang finance juga memiliki akses yang sama dengan manager dan jangan
  // dipisah") — lintas badan usaha seperti Manajer; peringkat tetap 2 (setara lewat `ROLE_SETARA`, bukan peringkat).
  finance: {
    label: "Finance",
    longLabel: "Kasir / Finance",
    rank: 2,
    crossEntity: true,
    scopeHint: "lintas badan usaha",
    order: 4,
    newIn: "E-8",
  },
  sales: {
    label: "Sales",
    longLabel: "Sales (lapangan)",
    rank: 1,
    crossEntity: false,
    scopeHint: "1 badan usaha",
    order: 5,
  },
  warehouse: {
    label: "Gudang",
    longLabel: "Gudang (WMS)",
    rank: 1,
    crossEntity: false,
    scopeHint: "1 badan usaha",
    order: 6,
  },
  // FASE D — peran ke-7 (keputusan pemilik): desainer ber-AKUN supaya ia sendiri
  // yang mengunggah artwork & menyerahkannya, dan rapor desainer terisi dari
  // pekerjaan nyata. Cermin `backend/role_registry.py`.
  designer: {
    label: "Desainer",
    longLabel: "Desainer (MD Desain)",
    rank: 1,
    crossEntity: false,
    scopeHint: "1 badan usaha",
    order: 7,
    newIn: "D",
  },
  // FB-02 — peran ke-8: sopir/kurir armada sendiri (modul Logistik). Cermin `backend/role_registry.py`.
  driver: {
    label: "Sopir",
    longLabel: "Sopir / Kurir (Logistik)",
    rank: 1,
    crossEntity: false,
    scopeHint: "1 badan usaha",
    order: 8,
    newIn: "FB-2",
  },
  // Sesi #087 — dua peran pelaksana baru dengan MEJA KERJA sendiri. Cermin `backend/role_registry.py`.
  md: {
    label: "MD",
    longLabel: "MD / Merchandiser (produk, sample & desain)",
    rank: 2,
    crossEntity: false,
    scopeHint: "1 badan usaha (bisa ditugaskan ke beberapa)",
    order: 9,
    newIn: "R-9",
  },
  warehouse_admin: {
    label: "Admin Gudang",
    longLabel: "Admin Gudang (kepala operasi gudang & logistik)",
    rank: 2,
    crossEntity: false,
    scopeHint: "1 badan usaha (bisa ditugaskan ke beberapa)",
    order: 10,
    newIn: "R-9",
  },
  // REVISI SAMPEL — peran ke-11: Admin Sample (pesanan sample SOS-). Cermin `backend/role_registry.py`.
  sample_admin: {
    label: "Admin Sample",
    longLabel: "Admin Sample (alur pesanan sample)",
    rank: 2,
    crossEntity: false,
    scopeHint: "1 badan usaha (bisa ditugaskan ke beberapa)",
    order: 11,
    newIn: "SMP",
  },
  // P05 IMP-16 (DEC-06) — dua peran mutu. Cermin `backend/role_registry.py`.
  md_quality: {
    label: "MD Quality",
    longLabel: "MD Quality (warna & handfeel vs sample ACC)",
    rank: 2,
    crossEntity: false,
    scopeHint: "1 badan usaha (bisa ditugaskan ke beberapa)",
    order: 12,
    newIn: "P05",
  },
  qc: {
    label: "QC",
    longLabel: "QC (cacat 4-point, grade & random check)",
    rank: 1,
    crossEntity: false,
    scopeHint: "1 badan usaha (bisa ditugaskan ke beberapa)",
    order: 13,
    newIn: "P05",
  },
};

export const ROLE_IDS = Object.keys(ROLE_REGISTRY)
  .sort((a, b) => ROLE_REGISTRY[a].order - ROLE_REGISTRY[b].order);

export const CROSS_ENTITY_ROLES = ROLE_IDS.filter((r) => ROLE_REGISTRY[r].crossEntity);

export function roleLabel(role, long = false) {
  const e = ROLE_REGISTRY[role];
  if (!e) return role || "—";
  return long ? e.longLabel : e.label;
}

/** K-FIN-01 — cermin `backend/role_registry.SETARA_PERAN`: peran → peran yang gerbang namanya ikut ia lewati (satu
 *  arah: Finance lolos gerbang Manajer, Manajer tidak lolos gerbang khusus Finance). Peran kustom ikut peran acuannya. */
export const ROLE_SETARA = { finance: ["manager"] };

/** Peran itu, peran acuannya (peran kustom), dan peran setara keduanya. */
function selfAndPeers(role) {
  const out = [role];
  const base = ROLE_REGISTRY[role]?.baseRole;
  if (base) out.push(base);
  [...out].forEach((r) => (ROLE_SETARA[r] || []).forEach((p) => { if (!out.includes(p)) out.push(p); }));
  return out;
}

/** Peran (atau peran ACUAN untuk peran kustom, atau peran SETARA — K-FIN-01) termasuk daftar? Pengganti
 *  `[..].includes(role)`. */
export function roleIs(role, list) {
  return selfAndPeers(role).some((r) => !!r && list.includes(r));
}

export function roleRank(role) {
  return ROLE_REGISTRY[role]?.rank || 0;
}

/** Apakah peran aktor memenuhi tuntutan peran sebuah aturan persetujuan? (K-FIN-01: Finance memenuhi tuntutan Manajer.) */
export function roleSatisfies(actorRole, requiredRole) {
  if (!requiredRole) return true;
  const need = ROLE_REGISTRY[requiredRole]?.rank ?? ROLE_REGISTRY.manager.rank;
  return selfAndPeers(actorRole).some((r) => roleRank(r) >= need);
}

/** Pilihan peran untuk formulir akun (layar "Badan Usaha & Akses"). */
export const ROLE_OPTIONS = ROLE_IDS.map((id) => ({
  value: id,
  label: ROLE_REGISTRY[id].longLabel,
  scope: ROLE_REGISTRY[id].scopeHint,
  isNew: !!ROLE_REGISTRY[id].newIn,
}));

// ─── VISIBILITAS MENU UNTUK PERAN BARU ───────────────────────────────────────
// `inherit` : mulai dari menu peran ini (biar tidak menulis ulang puluhan id).
// `add`     : id menu / id grup / `view` tab hub yang DITAMBAHKAN.
// `remove`  : yang DICABUT walau ikut terwarisi (pemisahan tugas E8.2).
export const ROLE_NAV = {
  sales_admin: {
    // Admin Sales bekerja di wilayah yang sama dengan sales, plus wewenang
    // pemenuhan: mengajukan pembelian (PR) & mengurus transaksi antar-PT.
    inherit: "sales",
    add: [
      "sales-admin-desk",          // Meja Admin Sales (gelombang 2)
      // E8.3 — sales DICABUT dari "Operasi Gudang" (layar mati: `/api/wms/tasks` 403),
      // tetapi Admin Sales PUNYA izin `wms.view` untuk memantau progres tanpa aksi.
      // Tanpa baris ini ia ikut kehilangan menu itu karena mewarisi menu sales.
      "wms-operations",
      "pembelian", "sourcing", "purchase-requisitions",
      // MN-T1 — Antar-PT kini di grup Keuangan (warisan `sales`); induk lama `akuntansi` dicabut dari daftar ini.
      "interco-transactions",
      "return-policies",           // perlu membaca kebijakan retur saat memproses retur
      // Fase 3 · P2 (P16-K1) — Pengaturan kini GRUP (groupId tetap `settings-hub`): Admin Sales melihat
      // Penjualan › Kebijakan Retur dan Gudang, Pembelian & Produksi › Grade Mutu (KP-T9; tab yang sama seperti sebelumnya).
      "settings-hub", "settings-sales", "settings-warehouse",
      "document-center", "doc-trace",
      // AUDIT SALES vs ADMIN SALES (sesi 2026-08-15) — keputusan pemilik E8.1b memberi
      // peran ini `approval: ["view"]` ("melihat antrean, tanpa menyetujui"). Izin itu
      // dulu TANPA PINTU: tabnya hanya untuk admin/manager, jadi Admin Sales tak punya
      // cara melihat persetujuan yang nyangkut padahal mengejarnya adalah tugasnya.
      // Layar ini read-only (keputusan tetap di layar kaya konteks milik manajer).
      "approval-inbox",
    ],
    remove: [
      // "Hutang Supplier" (accounts-payable) DICABUT. Menunya dulu ada di sini,
      // tetapi `GET /vendor-bills` menuntut `vendor_bill.view` yang SENGAJA tidak
      // dimiliki peran ini (plan.md E8.1b: "sisi HUTANG tetap manager/admin —
      // jangan diperluas sendiri"). Hasilnya layar mati. Obat yang benar =
      // mencabut menunya, BUKAN melebarkan izinnya.
      "accounts-payable",
      // "Kunjungan Sales" DICABUT. `VisitsView` bercabang: peran `sales` melihat
      // kunjungan MILIKNYA (`/hr/visits/mine`), peran lain masuk ke Log Kunjungan
      // yang memanggil `/hr/visits` + `/hr/employees` (izin HR — bukan milik peran
      // ini). Karena menunya terwarisi dari `sales`, Admin Sales mendarat di layar
      // yang selalu 403. Kunjungan lapangan memang bukan wilayahnya.
      "hr-visits",
      // FIX-1 (audit B1b UI-48) — "Meja Saya" terwarisi dari `sales` tetapi `/desks/me` menolak peran ini (meja
      // khususnya = Meja Admin Sales) → galat berkunci peran mentah di atas kartu "0 antrean".
      "my-desk",
    ],
  },
  designer: {
    // Desainer TIDAK mewarisi siapa pun: wilayahnya sengaja sempit — papan
    // pekerjaannya sendiri + tempat karyanya. Menu lain (pesanan, stok, uang,
    // master) bukan urusannya, dan menampilkannya hanya melahirkan layar mati.
    inherit: null,
    add: [
      "design-requests",   // papan pekerjaan (beranda perannya)
      "designer-hub",      // hub tempat papan & galeri hidup
      "rnd-designs", "cs-design-gallery",
      "hr-my-profile",     // Profil Saya (ESS) — termasuk KPI desainer miliknya
    ],
    remove: [
      // Tab hub Desainer yang menilai ORANG (KPI lintas desainer) & matriks divisi
      // bukan wewenang yang dinilai — pola privasi yang sama dengan PS-18.
      "designer-kpi", "rnd-divisions",
    ],
  },
  // FB-02 — sopir hanya melihat modul Logistik + Profil Saya.
  driver: {
    inherit: null,
    add: ["logistics", "hr-my-profile"],
    remove: [],
  },
  finance: {
    // K-FIN-01 (pemilik 17 Nov 2026 malam: "untuk sekarang finance juga memiliki akses yang sama dengan manager dan
    // jangan dipisah") — Finance MEWARISI seluruh menu & tab Manajer (izin bawaannya kini = izin Manajer + miliknya
    // sendiri, `backend/permissions_config.py` blok K-FIN-01), ditambah menu khas Finance di bawah. Dulu `inherit: null`
    // (wilayah sempit "kasir"). Untuk memisah lagi: kembalikan `inherit: null`.
    inherit: "manager",
    add: [
      "finance-desk",              // Meja Finance (gelombang 2) — beranda perannya
      "home", "hr-my-profile", "documents",
      "document-center", "doc-trace",
      // Penjualan: hanya MELIHAT pesanan & retur (untuk menagih & mencocokkan)
      "penjualan", "sales-orders", "orders", "returns",
      // REVISI SAMPEL — menyetujui pembayaran sample berbayar dari daftar Pesanan Sample
      "sample-orders",
      "customers-crm",
      // Keuangan: uang masuk, piutang, denda, kas, pajak keluaran
      "keuangan", "finance-tower", "ar-aging", "advance-report", "payment-plans", "finance-cases",
      "cash-bank", "cash-management",
      "akuntansi", "tax-hub", "tax-invoices",
      "store-credit",
      // 2026-09 — hutang jatuh tempo (Meja Finance) → PO hanya-lihat
      "pembelian", "purchase-orders", "purchasing",
      // 2026-10 — penetap harga internal antar-PT (keputusan pemilik: MD, Finance, Admin)
      "products-pricing", "internal-prices",
      // LN-140 — retur antar-PT masuk & saldo pasangan PT (hanya-lihat)
      "interco-transactions",
      // MN-T1 (UX-17, K-09, K-17, IA-06) — menu mengikuti izin bawaan Finance: Rekening & Saldo, Rekonsiliasi (K-09),
      // Kas Kecil (cash_advance), Buku Besar lihat saja (K-09), Hutang lihat & bayar (K-17), tab Piutang yang dulu
      // sub-tab CRM, Analisis (BI Keuangan), Pengaturan › Keuangan & Pajak › Pemetaan Akun (izin gl_mapping, IA-06).
      "bank-accounts", "bank-reconciliation", "petty-cash",
      // PM-T4 — Kas & Bank › Titipan Sales: menerima setoran titipan tunai sales (`cash_holding.approve`).
      "cash-holdings",
      "ledger", "general-ledger", "chart-of-accounts",
      "accounts-payable", "vendor-bills", "contra-bons", "gr-ir",
      "collection-worklist", "customer-credit", "credit-overrides", "bi-finance",
      "settings-hub", "settings-finance", "gl-account-mappings",
      // K-SDM-01 (pemilik 17 Nov 2026: "SDM/HR itu dipegang finance juga") — SDM › Karyawan, Kehadiran (Presensi, Cuti &
      // Izin, Lembur), Penggajian (Proses Gaji, Komponen & Masukan; Setoran & Pajak sudah PY-T4) + Pengaturan › SDM
      // (Aturan SDM & Penggajian, Shift & Lokasi Absen, Kalender Libur). Izin bawaan `hr.view/create/update/view_pii/
      // manage_attendance/manage_payroll` + `payroll.create/post` (`permissions_config.KSDM01_DEFAULT_PAIRS`). Struktur
      // organisasi, lacak lapangan, mesin absen, dan KPI karyawan tetap Admin/Manajer.
      "hr-people", "hr-employees",
      "hr-attendance-hub", "hr-attendance", "hr-leave", "hr-overtime",
      "hr-payroll-runs", "hr-pay-components",
      "settings-hr", "settings-cfg-hr", "hr-attendance-setup", "hr-holidays",
    ],
    remove: [],
  },
  // Sesi #087 — MD/Merchandiser: pengembangan produk. Tidak mewarisi siapa pun.
  md: {
    inherit: null,
    add: [
      "md-desk", "home", "hr-my-profile",
      // R&D & desain
      "rnd-hub", "rnd-specs", "rnd-samples", "rnd-revalidation", "rnd-labdip", "rnd-handfeel", "rnd-proofing", "rnd-reports",
      "designer-hub", "design-requests", "rnd-designs", "cs-design-gallery",
      // produk & harga
      "penjualan", "products-pricing", "md-products", "product-templates", "md-categories", "color-library", "md-uoms",
      "cs-price-list", "products-pricing", "sales-orders", "orders", "internal-prices",
      // UAT 24 Okt (P7) — Perbaikan roll (repair / celup ulang) — satu-satunya tab Operasi Gudang untuk MD
      "wms-operations", "repair-orders",
      // pembelian bahan (PR/RFQ hanya-lihat PO)
      "pembelian", "sourcing", "purchase-requisitions", "rfq", "purchase-orders", "purchasing", "master-pembelian", "suppliers",
      // pantau inspeksi (acuan sample) — menu Kualitas (23 Okt)
      "quality-hub", "inspections",
      // UAT 23 Okt — cutloss retur: catat qty cacat & pecah roll di detail retur (izin server sudah ada, layar belum)
      "returns",
      // Persetujuan MD (desain/sample) diputus di Meja MD — Pusat Persetujuan lintas modul bukan haknya.
      "document-center", "doc-trace",
    ],
    remove: ["designer-kpi", "rnd-divisions", "operations", "qc-inspection", "interco-transfers"],
  },
  // Sesi #087 — Admin Gudang: semua menu gudang + logistik + persetujuan gudang.
  warehouse_admin: {
    inherit: "warehouse",
    add: [
      "warehouse-admin-desk", "home", "hr-my-profile",
      "logistics",
      // Persetujuan gudang (opname/transfer) diputus di Meja Admin Gudang — bukan Pusat Persetujuan lintas modul.
      "document-center", "doc-trace",
      "cs-stock-analytics",
    ],
    // FIX-1 (audit B1b UI-48) — "Meja Saya" terwarisi dari `warehouse`, padahal server menolak peran ini
    // (`/desks/me` 404 "memakai meja khususnya sendiri") → galat berkunci peran + kartu "0 antrean". Mejanya = Meja Gudang.
    remove: ["my-desk"],
  },
  // REVISI SAMPEL — Admin Sample: meja sample + daftar pesanan sample + pantau gudang/logistik. Tidak mewarisi siapa pun.
  sample_admin: {
    inherit: null,
    add: [
      "sample-admin-desk", "home", "hr-my-profile",
      "penjualan", "sales-orders", "sample-orders", "customers-crm",
      "gudang", "wms-operations", "logistics",
      "document-center", "doc-trace",
    ],
    remove: ["orders", "amendments", "returns", "return-policies", "special-orders", "internal-requests", "keep-pending"],
  },
  // P05 IMP-16 — MD Quality & QC: layar SPK Inspeksi (QC juga antrean karantina kedatangan).
  // 23 Okt — keduanya bekerja di menu Kualitas (dulu lewat Gudang › Operasi Gudang).
  md_quality: {
    inherit: null,
    // UAT 23 Okt — + Retur Pelanggan: panel Cutloss & diskon (catat qty cacat, pecah roll, SJ potongan baik).
    add: ["home", "hr-my-profile", "quality-hub", "inspections", "returns", "document-center", "doc-trace"],
    remove: [],
  },
  qc: {
    inherit: null,
    add: ["home", "hr-my-profile", "quality-hub", "qc-inspection", "inspections", "document-center", "doc-trace"],
    remove: [],
  },
};

/**
 * SATU definisi "boleh lihat menu ini?" — dipakai `navigationConfig.js`
 * (sidebar, tab hub, command palette, deep-link) supaya keempatnya tidak
 * pernah berbeda pendapat.
 *
 * @param {string[]|undefined} roles daftar peran pada entri menu/tab
 * @param {string} role peran pengguna
 * @param {string} id id menu / groupId / view tab
 */
// L01 LN-015 — konteks akses akun aktif (+ pratinjau editor). Menu/tab yang dibuka modul tanpa
// satu pun izin efektif disembunyikan, begitu pula tab yang dimatikan di editor peran.
// PR-T5 — `view_actions` (server `access_modules.VIEW_ACTION_REQUIREMENTS`): menu yang butuh AKSI tertentu (meja peran),
// bukan sekadar "ada aksi apa pun pada sumber daya modulnya". Peta global (sama untuk semua peran), ikut pratinjau editor.
const ACCESS = { current: null, preview: null, role: "", perms: null, viewAct: {} };
export function setAccessContext(user) {
  ACCESS.viewAct = user?.view_actions || {};
  ACCESS.current = user?.role && user.role !== "admin" && user.view_resources
    ? { role: user.role, perms: user.permissions || {}, hidden: new Set(user.hidden_views || []), viewRes: user.view_resources,
        viewAct: ACCESS.viewAct }
    : null;
  // PR-T7 — izin efektif dicatat walau `view_resources` (penyaring menu) belum ada, untuk `canCurrent`.
  ACCESS.role = user?.role || "";
  ACCESS.perms = user?.role && user.role !== "admin" && user.permissions ? user.permissions : null;
}
export function setPreviewAccess(perms, hidden, viewRes) {
  ACCESS.preview = perms ? { role: "__preview", perms, hidden: new Set(hidden || []), viewRes: viewRes || {},
    viewAct: ACCESS.viewAct } : null;
}
function accessBlocks(role, id) {
  const a = role === "__preview" ? ACCESS.preview : (ACCESS.current?.role === role ? ACCESS.current : null);
  if (!a || !id) return false;
  if (a.hidden.has(id)) return true;
  const res = a.viewRes[id];
  if (Array.isArray(res) && res.length > 0 && !res.some((r) => (a.perms[r] || []).length > 0)) return true;
  const need = (a.viewAct || {})[id];   // PR-T5 — syarat per aksi
  return Array.isArray(need) && need.length > 0 && !need.some(([r, act]) => can(a.perms, r, act));
}

/** FE-03 — peran yang menunya DITURUNKAN dari katalog modul (peran kustom & pratinjau editor
 *  peran). Peran bawaan memakai rancangan menu tertulis (`roles` grup + overlay ROLE_NAV). */
export function isModuleNavRole(role) {
  return role === "__preview" || !!ROLE_REGISTRY[role]?.custom;
}

/** FE-03 — disembunyikan EKSPLISIT (menu disembunyikan di pengaturan peran, modul bertingkat
 *  "tidak ada", atau izin baca sumbernya tidak ada) — bukan sekadar "tidak tercantum". */
export function navExplicitlyHidden(role, id) {
  if (!id) return false;
  if (accessBlocks(role, id)) return true;
  const rule = ROLE_NAV[role];
  return !!(rule && rule.remove.includes(id));
}

/** KP-T9 — id disembunyikan oleh PILIHAN pengaturan peran: `hidden_views` (peran kustom, pratinjau editor) atau
 *  `ROLE_NAV.remove` peran bawaan. `remove` peran kustom/pratinjau tidak dihitung: isinya turunan tingkat modul (menu
 *  modul "Tidak ada"), bukan pilihan sembunyi — tab baru sudah mengikuti modulnya sendiri di katalog. Dipakai tab hub
 *  ber-`inheritsHiddenFrom` (navigationConfig.hubTabsForRole). */
export function hiddenByRoleSetting(role, id) {
  if (!role || !id) return false;
  const a = role === "__preview" ? ACCESS.preview : (ACCESS.current?.role === role ? ACCESS.current : null);
  if (a && a.hidden.has(id)) return true;
  if (isModuleNavRole(role)) return false;
  const rule = ROLE_NAV[role];
  return !!(rule && rule.remove.includes(id));
}

// PR-T6 — menu tambahan PERAN BAWAAN dari server (`GET /api/roles` → `nav.add`): menu yang dibuka izin sekarang di luar
// izin bawaan peran itu. Hanya untuk peran itu sendiri (tidak diwariskan ke peran kustom berdasarnya — peran kustom
// memakai menunya sendiri dari tingkat modul).
const NAV_EXTRA = {};

export function roleCanSee(roles, role, id, depth = 0) {
  if (depth === 0 && accessBlocks(role, id)) return false;
  const rule = ROLE_NAV[role];
  if (rule && id && rule.remove.includes(id)) return false;
  if (!Array.isArray(roles)) return true;      // tab tanpa `roles` = semua peran
  if (roles.includes(role)) return true;
  if (id && depth === 0 && (NAV_EXTRA[role] || []).includes(id)) return true;   // PR-T6
  if (!rule) return false;
  if (id && rule.add.includes(id)) return true;
  // Peran kustom mewarisi peran acuannya (yang mungkin punya overlay sendiri).
  if (rule.inherit && depth < 3) return roleCanSee(roles, rule.inherit, id, depth + 1);
  return false;
}

// ─── PERAN KUSTOM (dibuat admin di "Peran & Hak Akses") ─────────────────────
// Server (`GET /api/roles`) adalah sumbernya; di sini registry, overlay menu, dan
// beranda peran diisi SAAT RUNTIME supaya seluruh navigasi memakai satu jawaban.
const CUSTOM_IDS = new Set();
// PR-T4 — halaman awal SEMUA peran (bawaan & kustom) dari `home_view`/`home_nav_id` jawaban `GET /api/roles`
// (bisa diatur per peran di Peran & Hak Akses › Sifat peran). Nilai tertulis `ROLE_HOME_REGISTRY` = cadangan sebelum
// jawaban datang. Bila view sama dengan cadangan, id menu tertulis dipertahankan (sorotan sidebar tidak bergeser).
const WRITTEN_HOME = Object.fromEntries(Object.entries(ROLE_HOME_REGISTRY).map(([k, v]) => [k, { ...v }]));
const PROFILE_HOME = { view: "hr-my-profile", navId: "hr-my-profile" };

function homeFromServer(r, fallback) {
  if (!r?.home_view) return fallback || PROFILE_HOME;
  if (fallback && fallback.view === r.home_view) return { ...fallback };
  return { view: r.home_view, navId: r.home_nav_id || r.home_view };
}

// PR-T4 — kategori kerja per peran dari `kategori_kerja` jawaban `GET /api/roles` (Sifat peran). Nilai tertulis =
// cadangan sebelum jawaban datang (= bawaan sistem `backend/role_registry.PRT4_BUILTIN_TRAITS`).
const WRITTEN_CATEGORY = { sales: "sales", driver: "sopir", designer: "desainer", warehouse: "gudang",
  admin: "pengawas", manager: "pengawas", finance: "pengawas" };   // K-FIN-01 — Finance setara Manajer
const ROLE_CATEGORY = { ...WRITTEN_CATEGORY };

/** Kategori kerja peran: "" · "sales" · "sopir" · "desainer" · "gudang" · "pengawas" (bukan nama peran). */
export function categoryOf(role) {
  if (!role) return "";
  if (Object.prototype.hasOwnProperty.call(ROLE_CATEGORY, role)) return ROLE_CATEGORY[role];
  const base = ROLE_REGISTRY[role]?.baseRole;
  return base ? (ROLE_CATEGORY[base] || "") : "";
}

/** Halaman awal peran ini berbeda dari nilai tertulis (diatur Admin)? */
export function homeChangedByServer(role) {
  const w = WRITTEN_HOME[role];
  return Boolean(w && ROLE_HOME_REGISTRY[role] && ROLE_HOME_REGISTRY[role].view !== w.view);
}

function rebuildDerived() {
  const ids = Object.keys(ROLE_REGISTRY).sort((a, b) => ROLE_REGISTRY[a].order - ROLE_REGISTRY[b].order);
  ROLE_IDS.splice(0, ROLE_IDS.length, ...ids);
  ROLE_OPTIONS.splice(0, ROLE_OPTIONS.length, ...ids.map((id) => ({
    value: id,
    label: ROLE_REGISTRY[id].longLabel,
    scope: ROLE_REGISTRY[id].scopeHint,
    isNew: !!ROLE_REGISTRY[id].newIn,
    custom: !!ROLE_REGISTRY[id].custom,
  })));
}

/** Daftarkan peran kustom dari server. Mengembalikan true bila ada yang berubah. */
export function registerDynamicRoles(list) {
  const incoming = (list || []).filter((r) => r && r.custom && r.id);
  const homes = () => JSON.stringify(Object.keys(ROLE_HOME_REGISTRY).sort().map((id) => [id, ROLE_HOME_REGISTRY[id]]));
  const homesBefore = homes();
  (list || []).filter((r) => r && r.id && !r.custom && WRITTEN_HOME[r.id]).forEach((r) => {
    ROLE_HOME_REGISTRY[r.id] = homeFromServer(r, WRITTEN_HOME[r.id]);
  });
  (list || []).filter((r) => r && r.id && typeof r.kategori_kerja === "string").forEach((r) => {
    ROLE_CATEGORY[r.id] = r.kategori_kerja;
  });
  // PR-T6 — menu tambahan peran bawaan (selisih izin sekarang terhadap izin bawaannya).
  const extraBefore = JSON.stringify(NAV_EXTRA);
  (list || []).filter((r) => r && r.id && !r.custom && WRITTEN_HOME[r.id]).forEach((r) => {
    const add = Array.isArray(r.nav?.add) ? r.nav.add.filter(Boolean) : [];
    if (add.length) NAV_EXTRA[r.id] = add; else delete NAV_EXTRA[r.id];
  });
  const extraChanged = extraBefore !== JSON.stringify(NAV_EXTRA);
  const before = JSON.stringify([...CUSTOM_IDS].sort().map((id) => [id, ROLE_NAV[id], ROLE_REGISTRY[id]?.label]));
  for (const id of [...CUSTOM_IDS]) {
    delete ROLE_REGISTRY[id]; delete ROLE_NAV[id]; delete ROLE_HOME_REGISTRY[id];
    if (!incoming.some((r) => r.id === id)) delete ROLE_CATEGORY[id];
  }
  CUSTOM_IDS.clear();
  incoming.forEach((r, i) => {
    CUSTOM_IDS.add(r.id);
    ROLE_REGISTRY[r.id] = {
      label: r.label, longLabel: r.long_label || r.label, rank: r.rank || 1,
      crossEntity: false, scopeHint: r.scope_hint || "1 badan usaha", order: 100 + i,
      custom: true, baseRole: r.base_role || "",
    };
    ROLE_NAV[r.id] = { inherit: r.base_role || null, add: r.nav?.add || [], remove: r.nav?.remove || [] };
    ROLE_HOME_REGISTRY[r.id] = homeFromServer(r, ROLE_HOME_REGISTRY[r.base_role]);
  });
  rebuildDerived();
  const after = JSON.stringify([...CUSTOM_IDS].sort().map((id) => [id, ROLE_NAV[id], ROLE_REGISTRY[id]?.label]));
  return before !== after || homesBefore !== homes() || extraChanged;
}

/** Overlay sementara untuk PRATINJAU menu di editor peran (id `__preview`). */
export function setPreviewRoleNav(rule) {
  if (rule) ROLE_NAV.__preview = rule; else delete ROLE_NAV.__preview;
}

/** Izin efektif pengguna (dikirim server saat login) → `can(perms, "interco", "create")`. */
export function can(perms, module, action) {
  const actions = (perms || {})[module] || [];
  return actions.includes(action) || actions.includes("*");
}

/** Izin akun aktif tanpa prop drilling. Server tetap menegakkan.
 *  PR-T7 (PR-UX-41) — konteks izin BELUM dimuat = TIDAK (dulu "boleh": kerangka aplikasi memanggil endpoint yang pasti
 *  403 sebelum `/auth/me` dijawab). Admin tetap boleh. Konteks kini sudah lengkap sejak jawaban login. */
export function canCurrent(module, action) {
  if (ACCESS.role === "admin") return true;
  const perms = ACCESS.current?.perms || ACCESS.perms;
  return !!perms && can(perms, module, action);
}

/** Hak lihat grade dari Manajemen Peran (field_visibility). Data grade juga disamarkan server bila tidak berhak. */
export function canSeeGrade(user) {
  const fv = user?.permissions?.field_visibility || [];
  return fv.includes("*") || fv.includes("grade");
}
