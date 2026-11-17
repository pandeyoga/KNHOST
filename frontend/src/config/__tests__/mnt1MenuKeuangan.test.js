// MN-T1 — menu keuangan & SDM: pindah dan kelompokkan tanpa mengubah isi layar (docs/blueprint/unit/MN-T1.md).
// Uji komponen U1, U2, U3, U6–U10 (+ label U15). Izin peran bawaan dari `access_builtin_fixture.json` (generator backend
// `backend/tests/fe03_access_fixture.py`), sama dengan respons login; tabel bantu `fixtures/view_main_permission.json`
// = view → pasangan izin layar (salah satu cukup) + endpoint GET utamanya (dipakai juga uji backend U4).
import builtin from "./fixtures/access_builtin_fixture.json";
import tabel from "./fixtures/view_main_permission.json";
import { HUB_TABS, NAV_STRUCTURE, buildNavGroups, hubTabsForRole, resolveDeepLinkTarget } from "../navigationConfig";
import { ROLE_HOME_REGISTRY } from "../navMeta";
import { ROLE_IDS, can, setAccessContext } from "../roles";

const BUILTIN = ROLE_IDS.filter((r) => !String(r).startsWith("cr_") && r !== "__preview");
const login = (role, perms = builtin.permissions[role] || {}) => setAccessContext({
  role, permissions: perms, view_resources: builtin.view_resources, hidden_views: [],
  view_actions: builtin.view_actions,
});
afterEach(() => setAccessContext(null));

/** Menu peran: { grup/standalone: { id menu: [view tab tampak] } } — sama dengan Sidebar. */
const menu = (role, perms) => {
  login(role, perms);
  const out = {};
  for (const g of buildNavGroups(role, { showComingSoon: false })) {
    const items = g.type === "group" ? g.items : [g];
    out[g.groupId || g.id] = Object.fromEntries(items.map((it) => [it.id, it.hub ? hubTabsForRole(it.hub, role).map((t) => t.view) : []]));
  }
  return out;
};
const labels = (hub) => HUB_TABS[hub].filter((t) => !t.hidden).map((t) => t.label);

describe("U1 — Keuangan 5 entri + Akuntansi & Pajak 5 entri (admin); grup Kas & Aset hilang", () => {
  test("admin: 5 + 5 = 10 entri, urutan & label rancangan", () => {
    const m = menu("admin");
    expect(Object.keys(m.keuangan)).toEqual(["finance-tower", "ar-aging", "accounts-payable", "cash-bank", "interco-transactions"]);
    expect(Object.keys(m.akuntansi)).toEqual(["ledger", "closing", "fin-reports", "tax-hub", "fixed-assets"]);
    expect(Object.keys(m.keuangan).length + Object.keys(m.akuntansi).length).toBe(10);
    expect(m["kas-aset"]).toBeUndefined();
    expect(NAV_STRUCTURE.some((e) => e.groupId === "kas-aset")).toBe(false);
    const lbl = (gid) => NAV_STRUCTURE.find((e) => e.groupId === gid).items.map((i) => i.label);
    expect(lbl("keuangan")).toEqual(["Beranda Keuangan", "Piutang", "Hutang", "Kas & Bank", "Antar-PT"]);
    expect(lbl("akuntansi")).toEqual(["Buku Besar", "Tutup Buku", "Laporan", "Pajak", "Aset Tetap"]);
  });
  test("Hutang tidak lagi di Pembelian; Kendaraan di Gudang & Logistik; Meja Finance bukan menu lepas", () => {
    const m = menu("admin");
    expect(m.pembelian["accounts-payable"]).toBeUndefined();
    expect(m.gudang["vehicle-logs"]).toEqual([]);
    expect(m["finance-desk"]).toBeUndefined();
    expect((m["meja-peran"] || {})["finance-desk"]).toBeUndefined();
  });
});

describe("U2 — jumlah tab tampak per hub (admin)", () => {
  test.each([
    // PK-28 — Hutang mendapat tab ketiga GR/IR (Diterima Belum Ditagih). S5 (pelatihan 18 Nov) — + Hutang per Pemasok.
    ["finance-tower", 3], ["ar-aging", 6], ["accounts-payable", 4], ["cash-bank", 5], ["closing", 3], ["ledger", 2],
    // KM-T1 — + Target & Aturan (Meja Insentif); KM-T2 — + Capaian; KM-T5 — − Kinerja Sales, − Komisi Otomatis.
    ["hr-kpi-hub", 4], ["purchase-orders", 7],
  ])("%s = %i tab", (hub, n) => {
    expect(hubTabsForRole(hub, "admin")).toHaveLength(n);
  });
  test("label tab persis tabel lama → baru", () => {
    expect(labels("finance-tower")).toEqual(["Perlu Tindakan", "Posisi", "Analisis"]);
    expect(labels("ar-aging")).toEqual(["Saldo & Umur", "Penagihan & Penerimaan", "Rencana & Denda",
      "Titipan & Saldo Kredit", "Kredit & Plafon", "Kasus"]);
    expect(labels("accounts-payable")).toEqual(["Tagihan", "Kontrabon", "GR/IR (Diterima Belum Ditagih)",   // PK-28
      "Hutang per Pemasok"]);   // S5 (pelatihan 18 Nov)
    // PM-T4 — + Titipan Sales (setoran titipan tunai sales).
    expect(labels("cash-bank")).toEqual(["Rekening & Saldo", "Transaksi Kas", "Rekonsiliasi", "Kas Kecil", "Titipan Sales"]);
    expect(labels("closing")).toEqual(["Daftar Periksa & Tutup", "Buka Periode", "Posting Gagal"]);
    expect(labels("ledger")).toEqual(["Jurnal", "Bagan Akun"]);
    expect(labels("fin-reports")).toEqual(["Laba-Rugi, Neraca & Arus Kas", "Profitabilitas", "Proyeksi Kas", "Anggaran", "Konsolidasi"]);
    expect(labels("tax-hub")).toEqual(["Faktur Keluaran", "Faktur Masukan", "PPN & PPh"]);
    // PK-22 (Setoran Kewajiban) · PY-T1 (Komponen & Masukan; tab Slip Gaji dihapus — panel "Cari slip" di Proses Gaji).
    // PY-T4 — tab setoran berlabel "Setoran & Pajak" (bayar gaji + setoran BPJS/PPh 21).
    expect(labels("hr-payroll-hub")).toEqual(["Proses Gaji", "Setoran & Pajak", "Komponen & Masukan"]);
    // KM-T1 — tab Meja Insentif "Target & Aturan" (`incentive-setup`); tab lama `incentive-rates` berlabel "Komisi Otomatis".
    // KM-T2 — tab "Capaian" (`incentive-capaian`) di urutan pertama.
    // KM-T3 — tab "Lembar Insentif" (`incentive-sheets`) sesudah Capaian; "Skema (Arsip)" tersembunyi (batas enam tab L3,
    // layarnya tetap terbuka lewat tautan di Lembar Insentif).
    // KM-T5 — "Kinerja Sales", "Komisi Otomatis", dan "Skema (Arsip)" dicabut (alias ke Capaian / Target & Aturan).
    expect(labels("hr-kpi-hub")).toEqual(["Capaian", "Lembar Insentif", "Target & Aturan", "KPI Karyawan"]);
    expect(HUB_TABS["purchase-orders"].map((t) => t.view)).toContain("landed-cost");
    expect(HUB_TABS["settings-sales"].map((t) => t.view)).not.toContain("incentive-rates");
    expect(HUB_TABS["petty-cash"]).toBeUndefined();
  });
  test("U15 — label 'Payroll Run' dan 'Chart of Accounts' tidak lagi tampil di menu", () => {
    const all = [...Object.values(HUB_TABS).flat().map((t) => t.label),
      ...NAV_STRUCTURE.flatMap((e) => [e.label, ...(e.items || []).map((i) => i.label)])].join(" | ");
    expect(all).not.toMatch(/Payroll Run|Chart of Accounts/);
  });
});

describe("U3 — tiap menu/tab yang tampak dipegang izinnya (13 peran bawaan)", () => {
  test("fixture memuat 13 peran bawaan", () => {
    expect(BUILTIN.filter((r) => builtin.permissions[r])).toHaveLength(13);
  });
  const tampakTanpaIzin = (role, perms) => {
    const m = menu(role, perms);
    const tanpa = [];
    for (const [gid, items] of Object.entries(m)) {
      for (const [id, tabs] of Object.entries(items)) {
        for (const v of (tabs.length ? tabs : [id])) {
          const t = tabel.views[v];
          if (t && !t.izin.some(([r, a]) => can(perms, r, a))) tanpa.push(`${gid} › ${id} › ${v}`);
        }
      }
    }
    return tanpa;
  };
  test.each(BUILTIN)("%s: nol entri tampak tanpa izin", (role) => {
    expect(tampakTanpaIzin(role, builtin.permissions[role] || {})).toEqual([]);
  });
  test("bukti-merah: Finance tanpa izin Tagihan (vendor_bill) → tab Hutang › Tagihan terdeteksi tampak tanpa izin", () => {
    const tanpaTagihan = { ...builtin.permissions.finance };
    delete tanpaTagihan.vendor_bill;
    expect(tampakTanpaIzin("finance", tanpaTagihan)).toEqual(["keuangan › accounts-payable › vendor-bills"]);
  });
  test("tabel bantu mencakup semua tab hub keuangan & SDM yang dipindah", () => {
    const hubs = ["finance-tower", "ar-aging", "accounts-payable", "cash-bank", "closing", "ledger", "fin-reports", "tax-hub",
      "hr-payroll-hub", "hr-kpi-hub"];
    const kurang = hubs.flatMap((h) => HUB_TABS[h].filter((t) => !t.hidden).map((t) => t.view)).filter((v) => !tabel.views[v]);
    expect(kurang).toEqual([]);
  });
});

describe("U6 — alamat lama tetap mendarat (admin)", () => {
  test.each([
    ["advance-report", "customer-credit", "ar-aging", { bagian: "titipan" }],
    ["store-credit", "customer-credit", "ar-aging", { bagian: "saldo" }],
    ["cash-advances", "petty-cash", "cash-bank", { bagian: "pengajuan" }],
    ["settlements", "petty-cash", "cash-bank", { bagian: "pertanggungjawaban" }],
    ["reimburse-payables", "petty-cash", "cash-bank", { bagian: "reimburse" }],
  ])("%s → %s (%s) + preset", (old, view, navId, preset) => {
    expect(resolveDeepLinkTarget(old, "admin")).toMatchObject({ view, navId, preset, alias: old });
  });
  test.each([
    ["period-unlock", "closing"], ["posting-failures", "closing"], ["payment-plans", "ar-aging"],
    ["landed-cost", "purchase-orders"], ["vehicle-logs", "vehicle-logs"], ["fixed-assets", "fixed-assets"],
    ["finance-desk", "finance-tower"], ["petty-cash", "cash-bank"], ["kas-aset", "cash-bank"],
  ])("%s → menu %s", (id, navId) => {
    const t = resolveDeepLinkTarget(id, "admin");
    expect(t).not.toBeNull();
    expect(t.navId).toBe(navId);
  });
  test("kas-aset (id grup lama) → Kas & Bank › Kas Kecil", () => {
    expect(resolveDeepLinkTarget("kas-aset", "admin")).toMatchObject({ view: "petty-cash", navId: "cash-bank" });
  });
  test("beranda Finance tetap Meja Finance, menu yang disorot Beranda Keuangan", () => {
    expect(ROLE_HOME_REGISTRY.finance).toEqual({ view: "finance-desk", navId: "finance-tower" });
  });
});

describe("U7–U10 — menu per peran", () => {
  // K-FIN-01 (pemilik 17 Nov 2026 malam: "untuk sekarang finance juga memiliki akses yang sama dengan manager dan jangan
  // dipisah") — menu Keuangan, Akuntansi & Pajak, dan Pengaturan › Keuangan & Pajak Finance = Manajer (dulu: Beranda 3,
  // Piutang 6, Hutang 3, Kas & Bank 5, Antar-PT; Buku Besar 2 + Faktur Keluaran; Pemetaan Akun saja).
  test("U7 Finance (K-FIN-01 = Manajer): Keuangan, Akuntansi & Pajak, Pengaturan › Keuangan & Pajak", () => {
    const mgr = menu("manager");
    const m = menu("finance");
    expect(m.keuangan).toEqual(mgr.keuangan);
    expect(m.akuntansi).toEqual(mgr.akuntansi);
    expect(m["settings-hub"]["settings-finance"]).toEqual(mgr["settings-hub"]["settings-finance"]);
    expect(m.keuangan["cash-bank"]).toEqual(expect.arrayContaining(["bank-accounts", "cash-holdings"]));
    expect(m.akuntansi.closing).toEqual(["closing", "period-unlock", "posting-failures"]);
    expect(m["settings-hub"]["settings-finance"]).toContain("gl-account-mappings");   // IA-06
  });
  test("U8 Sales: Keuangan hanya Piutang (Penagihan, Kasus) + Kas & Bank (Kas Kecil); SDM tidak tampil (KM-T5)", () => {
    const m = menu("sales");
    expect(m.keuangan).toEqual({ "ar-aging": ["collection-worklist", "finance-cases"], "cash-bank": ["petty-cash"] });
    // KM-T5 — tab Kinerja Sales dicabut: sales melihat capaian & insentifnya di kartu "Capaian & Insentif Saya".
    expect(m.hrd).toBeUndefined();
    expect(m.akuntansi).toBeUndefined();
  });
  test("U9 Gudang: Keuangan hanya Hutang › Kontrabon dan Antar-PT; Akuntansi & Pajak tidak tampil", () => {
    const m = menu("warehouse");
    expect(m.keuangan).toEqual({ "accounts-payable": ["contra-bons"], "interco-transactions": [] });
    expect(m.akuntansi).toBeUndefined();
    expect(m.gudang["vehicle-logs"]).toEqual([]);
  });
  test("U10 Admin Sales: tanpa Hutang; memuat Antar-PT", () => {
    const m = menu("sales_admin");
    expect(m.keuangan["accounts-payable"]).toBeUndefined();
    expect(m.keuangan["interco-transactions"]).toEqual([]);
    expect(m.akuntansi).toBeUndefined();
  });
  test("Admin Gudang mewarisi Gudang: Kontrabon & Antar-PT", () => {
    expect(menu("warehouse_admin").keuangan).toEqual({ "accounts-payable": ["contra-bons"], "interco-transactions": [] });
  });
  test("Manajer: Perlu Tindakan (Meja Finance) dan semua tab Kinerja & Insentif", () => {
    const m = menu("manager");
    expect(m.keuangan["finance-tower"]).toEqual(["finance-desk", "finance-tower", "bi-finance"]);
    // KM-T1, KM-T2; KM-T3 — + Lembar Insentif; KM-T5 — Kinerja Sales, Komisi Otomatis, Skema (Arsip) dicabut.
    expect(m.hrd["hr-kpi-hub"]).toEqual(["incentive-capaian", "incentive-sheets", "incentive-setup", "cs-kpi"]);
    expect(m.akuntansi.closing).toEqual(["closing", "period-unlock", "posting-failures"]);
  });
});
