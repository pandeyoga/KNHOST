/**
 * viewAliases.js — REGISTRI ALIAS LAYAR (fase 3 · P1, pola "gabung" §1.1 rencana fase 3).
 *
 * KENAPA ADA: keputusan pemilik 26 Okt — layar duplikat TIDAK dihapus, melainkan menjadi
 * TAUTAN ke layar utama. Alamat lama (`?view=<lama>`, notifikasi, giliran, papan antrean,
 * bookmark) harus tetap mendarat di tempat yang benar. Satu registri ini dibaca oleh SEMUA
 * jalan masuk navigasi: sidebar/palet Ctrl+K/deep link (`navigationConfig.resolveDeepLinkTarget`),
 * `App.js` (`handleNavSelect` → preset), notifikasi (`utils/viewAlias.resolveView`).
 *
 * Bentuk entri:
 *   "<id lama>": {
 *     to: "<view utama>",        // WAJIB — view yang dirender AppViewRouter
 *     nav: "<navId utama>",      // opsional — menu yang disorot (bawaan: turunan dari `to`)
 *     preset: { tab: "…" },      // opsional — dibaca layar utama lewat `useViewPreset(to)`
 *     label: "Nama lama",        // opsional — palet Ctrl+K menampilkan "Nama lama → kini di <utama>"
 *     since: "D-06",             // asal keputusan (dokumentasi + guardrail)
 *     legacy: true,              // nama lama TANPA layar sendiri (tidak butuh rute cadangan)
 *   }
 *
 * Aturan (dijaga `scripts/guardrails/verify_view_aliases.py` + `config/__tests__/viewAliases.test.js`):
 *  · `to` bukan alias lagi (tanpa rantai) dan ada di menu;
 *  · alias non-`legacy` tetap punya rute cadangan `activeView === "<lama>"` di AppViewRouter;
 *  · peran yang dulu bisa membuka id lama ⊆ peran yang bisa membuka `to` (uji jangkauan peran).
 *
 * ISI: alias lama (S14, `utils/viewAlias.js`) · alias P2 (Pengaturan & master data, diaktifkan bersama menunya) ·
 * alias P8 (tabel §6 rencana fase 3: D-06, D-09, D-11, D-16, D-24b) yang diaktifkan bersama pencabutan tab lama.
 */
export const VIEW_ALIASES = {
  // Cek UI UAT v3 (S14) — tautan giliran/notifikasi backend (TURN_MAP) memakai nama lama tanpa layar.
  approvals: { to: "approval-inbox", legacy: true, since: "S14" },
  finance: { to: "finance-desk", legacy: true, since: "S14" },
  "purchase-orders": { to: "purchasing", nav: "purchase-orders", legacy: true, since: "S14" },

  // ── Fase 3 · P2 (tabel §6 rencana: baris bertanda P2) ─────────────────────────────────────────────────────
  // P16-K1 — "Pengaturan" kini GRUP sidebar (groupId sama), bukan menu ber-hub. Nama lama `settings-hub` tak punya
  // layar sendiri; tujuannya satu-satunya layar Pengaturan yang dulu terjangkau SEMUA peran pemegang menu itu
  // (admin, manager, Admin Gudang, Admin Sales) — Master Grade Mutu. Admin/manajer memilih kelompok dari sidebar.
  "settings-hub": { to: "grade-master", nav: "settings-warehouse", legacy: true, since: "P16-K1" },
  // D-01 — Template Dokumen Dasar (AdminView tab templates) = tab "Kop & tata letak dasar" di Template Dokumen.
  "doc-templates-basic": {
    to: "pdf-templates", nav: "settings-documents", preset: { tab: "dasar" },
    label: "Template Dokumen Dasar", since: "D-01",
  },
  // D-21 — satu tabel "Satuan & faktor" di Produk & Harga › Satuan & Konversi.
  "uom-conversions": { to: "md-uoms", nav: "products-pricing", since: "D-21" },
  // D-29 — Perangkat RFID = tab "RFID" di layar Perangkat; sejak KP-T9 tab sendiri Pengaturan › Sistem › Perangkat RFID.
  "cs-rfid-devices": {
    to: "settings-devices", nav: "settings-system", preset: { tab: "rfid" },
    label: "Perangkat RFID", since: "D-29",
  },

  // ── Fase 3 · P8 (tabel §6 rencana) — diaktifkan BERSAMAAN dengan pencabutan tab lamanya di hubTabs.js. Rute cadangan
  // `activeView === "<lama>"` tetap (pembungkus tipis yang merender layar utama): notifikasi/papan backend masih
  // menunjuk id lama. Gerbang per bagian di layar utama memakai id lama (`canOpen`/`roleCanSee`) supaya
  // `hidden_views` peran kustom tetap dipatuhi (§1.1 butir 6, risiko 6).
  // D-06 — Persetujuan Saya = tab "Matriks divisi" di Pusat Persetujuan (manager/admin; `inboxTabs.canSeeMatrix`).
  "my-approvals": {
    to: "approval-inbox", nav: "approval-inbox", preset: { tab: "matrix" },
    label: "Persetujuan Saya", since: "D-06",
  },
  // D-09 — Galeri Desain (Showcase) = mode Galeri (desain ACC) di Desain & Pattern.
  "cs-design-gallery": {
    to: "rnd-designs", nav: "designer-hub", preset: { mode: "gallery", status: "acc" },
    label: "Galeri Desain (Showcase)", since: "D-09",
  },
  // D-11 — Analitik › Margin & HPP = tab "Margin katalog (HPP/WAC)" di Profitabilitas & Margin.
  costing: {
    to: "profitability", nav: "fin-reports", preset: { tab: "katalog" },
    label: "Margin & HPP", since: "D-11",
  },
  // D-16 — Transfer Antar-Entitas = daftar Transfer (Operasi Gudang) dengan saringan Jenis "Antar PT".
  "interco-transfers": {
    to: "operations", nav: "wms-operations", preset: { tab: "transfer", kind: "inter_entity" },
    label: "Transfer Antar-Entitas", since: "D-16",
  },
  // D-24b — Labdip/Handfeel/Proofing = Sample R&D mode Galeri dengan chip jenis (tujuan "Semua").
  "rnd-labdip": {
    to: "rnd-samples", nav: "rnd-hub", preset: { mode: "gallery", type: "labdip", purpose: "all" },
    label: "Labdip", since: "D-24",
  },
  "rnd-handfeel": {
    to: "rnd-samples", nav: "rnd-hub", preset: { mode: "gallery", type: "handfeel", purpose: "all" },
    label: "Handfeel", since: "D-24",
  },
  "rnd-proofing": {
    to: "rnd-samples", nav: "rnd-hub", preset: { mode: "gallery", type: "proofing", purpose: "all" },
    label: "Proofing", since: "D-24",
  },
  // KF-T4 — dua kelompok registri (Dokumen, Notifikasi) pindah ke sub-judul kelompok Persetujuan; layarnya menjadi alias.
  // Rute cadangan `activeView === "<id lama>"` tetap (SettingsGroupView `CFG_VIEW_ALIASES`); id tetap di access_modules.
  "settings-cfg-documents": {
    to: "settings-cfg-approval", nav: "settings-approval", preset: { section: "rujukan-dokumen" },
    label: "Aturan Dokumen", since: "KF-T4",
  },
  "settings-cfg-notify": {
    to: "settings-cfg-approval", nav: "settings-approval", preset: { section: "pemberitahuan" },
    label: "Penerima Notifikasi", since: "KF-T4",
  },

  // ── MN-T1 — menu keuangan & SDM dipindah dan dikelompokkan (docs/blueprint/unit/MN-T1.md). Layar lama dirender UTUH
  // di dalam pembungkus ber-chip (`preset.bagian`); rute cadangan `activeView === "<lama>"` tetap; id lama tetap di
  // access_modules (hidden_views peran kustom menyembunyikan chipnya).
  "advance-report": {
    to: "customer-credit", nav: "ar-aging", preset: { bagian: "titipan" },
    label: "Uang Muka Pelanggan", since: "MN-T1",
  },
  "store-credit": {
    to: "customer-credit", nav: "ar-aging", preset: { bagian: "saldo" },
    label: "Saldo Kredit", since: "MN-T1",
  },
  "cash-advances": {
    to: "petty-cash", nav: "cash-bank", preset: { bagian: "pengajuan" },
    label: "Pengajuan Dana (PD)", since: "MN-T1",
  },
  settlements: {
    to: "petty-cash", nav: "cash-bank", preset: { bagian: "pertanggungjawaban" },
    label: "Pertanggungjawaban (LPJ)", since: "MN-T1",
  },
  "reimburse-payables": {
    to: "petty-cash", nav: "cash-bank", preset: { bagian: "reimburse" },
    label: "Hutang Reimburse", since: "MN-T1",
  },
  // Id grup lama "Kas & Aset" (bookmark/`?view=kas-aset`) tanpa layar sendiri → Kas & Bank › Kas Kecil.
  "kas-aset": { to: "petty-cash", nav: "cash-bank", label: "Kas & Aset", legacy: true, since: "MN-T1" },

  // ── PY-T1 (PY-14) — tab Slip Gaji menampilkan tabel yang sama dengan rincian proses; kini panel "Cari slip" di Proses
  // Gaji (dibuka lewat preset). Rute cadangan `activeView === "hr-payslips"` merender Proses Gaji dengan panel terbuka;
  // id lama tetap di access_modules (hidden_views peran kustom menyembunyikan panelnya — `canOpen("hr-payslips")`).
  "hr-payslips": {
    to: "hr-payroll-runs", nav: "hr-payroll-hub", preset: { cari: true }, label: "Slip Gaji", since: "PY-T1",
  },

  // ── KP-T9 — menu Pengaturan sembilan hub (docs/blueprint/unit/KP-T9.md). Layar Badan Usaha & Akses dipecah menjadi
  // lima tab (Profil PT, Kesiapan PT, Akun, Peran & Hak Akses, Cek Peran); id lamanya mendarat di Profil PT dan rute
  // cadangan `activeView === "entities-access"` tetap. Empat id hub yang hilang (tanpa layar sendiri) → tab barunya.
  "entities-access": {
    to: "settings-pt-profile", nav: "settings-company", label: "Badan Usaha & Akses", since: "KP-T9",
  },
  "settings-purchasing": {
    to: "settings-cfg-purchasing", nav: "settings-warehouse", label: "Pembelian & Produksi", legacy: true, since: "KP-T9",
  },
  "settings-rnd": { to: "settings-cfg-rnd", nav: "settings-warehouse", legacy: true, since: "KP-T9" },
  "settings-masters": {
    to: "entity-masters", nav: "settings-company", label: "Master Data", legacy: true, since: "KP-T9",
  },
  "settings-notify": {
    to: "scheduler", nav: "settings-documents", label: "Notifikasi & Penjadwal", legacy: true, since: "KP-T9",
  },

  // ── KM-T5 — layar insentif lama dicabut dari SDM › Kinerja & Insentif (docs/blueprint/unit/KM-T5.md). Kinerja Sales
  // (KPI + papan peringkat) → tab Capaian; Komisi Otomatis (tarif + bawaan komisi) & Skema (Arsip) (jenjang) → Target &
  // Aturan bagian "Komisi otomatis (cara lama)". Rute cadangan `activeView === "<lama>"` merender layar tujuannya; sales
  // (dulu memegang Kinerja Sales) tidak mendapat pintu ke Capaian — angkanya di kartu "Capaian & Insentif Saya".
  "sales-performance": { to: "incentive-capaian", nav: "hr-kpi-hub", label: "Kinerja Sales", since: "KM-T5" },
  "incentive-rates": { to: "incentive-setup", nav: "hr-kpi-hub", label: "Komisi Otomatis", since: "KM-T5" },
  "incentive-schemes": { to: "incentive-setup", nav: "hr-kpi-hub", label: "Skema Insentif (Arsip)", since: "KM-T5" },
};

/** Alias untuk `view` → `{ from, to, nav, preset, label, since, legacy }`, atau null bila bukan alias. */
export function resolveAlias(view) {
  if (typeof view !== "string" || !view) return null;
  const a = Object.prototype.hasOwnProperty.call(VIEW_ALIASES, view) ? VIEW_ALIASES[view] : null;
  if (!a || !a.to || a.to === view) return null;
  return {
    from: view,
    to: a.to,
    nav: a.nav || null,
    preset: a.preset || null,
    label: a.label || "",
    since: a.since || "",
    legacy: !!a.legacy,
  };
}

/** View utama untuk `view` (alias → tujuannya; selain itu view itu sendiri). */
export function aliasTarget(view) {
  return resolveAlias(view)?.to || view;
}

/** Semua alias yang menunjuk `view` (mis. untuk palet/breadcrumb). */
export function aliasesOf(view) {
  return Object.keys(VIEW_ALIASES).filter((k) => VIEW_ALIASES[k]?.to === view).map(resolveAlias).filter(Boolean);
}

/** Daftar semua alias (untuk uji & palet). */
export function listAliases() {
  return Object.keys(VIEW_ALIASES).map(resolveAlias).filter(Boolean);
}
