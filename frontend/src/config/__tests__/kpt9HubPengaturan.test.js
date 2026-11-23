// KP-T9 — menu Pengaturan menjadi sembilan hub dengan satu istilah "PT" (docs/blueprint/unit/KP-T9.md, K-46).
// Uji komponen U3 (susunan), U4 (alamat lama), U5 (jangkauan peran bawaan vs potret awal), U10 (tab pecahan ikut
// tersembunyi bersama wadah lamanya). Lapis B (katalog modul, hidden_views) di backend/tests_mem/test_KPT9_hub_pengaturan.py.
import builtin from "./fixtures/access_builtin_fixture.json";
import { HUB_TABS, NAV_STRUCTURE, buildNavGroups, hubTabsForRole, isNavHeading, resolveDeepLinkTarget } from "../navigationConfig";
import { ROLE_IDS, registerDynamicRoles, setAccessContext } from "../roles";
import { resolveAlias } from "../viewAliases";

/** Tabel "Layar" unit (sembilan hub) — id hub · label · [id tab, label tab]. Hub 4 tanpa Komisi & Insentif (pindah ke
 *  SDM › Kinerja & Insentif oleh MN-T1); hub 3 + Kontrol dua orang (KF-T6); hub 8 + Penomoran Dokumen (KP-T5). */
const SEMBILAN = [
  ["settings-company", "Perusahaan (PT)", [["settings-pt-profile", "Profil PT"], ["settings-pt-readiness", "Kesiapan PT"],
    ["entity-masters", "Master per PT"]]],
  ["settings-access", "Pengguna & Hak Akses", [["settings-accounts", "Akun"], ["permission-matrix", "Peran & Hak Akses"],
    ["settings-role-check", "Cek Peran"]]],
  ["settings-approval", "Persetujuan", [["approval-rules", "Aturan Persetujuan"], ["rnd-divisions", "Persetujuan R&D"],
    ["settings-cfg-approval", "Ketegasan, Pengingat & Dokumen"], ["settings-dual-control", "Kontrol dua orang"]]],
  ["settings-sales", "Penjualan", [["settings-cfg-sales", "Aturan Penjualan"], ["return-policies", "Kebijakan Retur"],
    ["amendment-reasons", "Alasan Koreksi"]]],
  ["settings-warehouse", "Gudang, Pembelian & Produksi", [["settings-cfg-warehouse", "Aturan Gudang & Mutu"],
    ["settings-receiving-ocr", "Penerimaan Barang"], ["grade-master", "Grade Mutu"],
    ["settings-cfg-purchasing", "Aturan Pembelian & Makloon"], ["settings-cfg-rnd", "R&D & Desain"]]],
  ["settings-finance", "Keuangan & Pajak", [["settings-cfg-finance", "Aturan Keuangan & Pajak"],
    ["gl-account-mappings", "Pemetaan Akun"], ["expense-categories", "Kategori Beban"], ["bank-recon-rules", "Bank"]]],
  // PY-T3 — + tab Kalender Libur (hari libur PT; jenis hari lembur, hari kerja untuk prorata & potongan).
  ["settings-hr", "SDM", [["settings-cfg-hr", "Aturan SDM & Penggajian"], ["hr-attendance-setup", "Shift & Lokasi Absen"],
    ["settings-attendance-devices", "Mesin Absen"], ["hr-holidays", "Kalender Libur"]]],
  ["settings-documents", "Dokumen & Notifikasi", [["pdf-templates", "Template Dokumen"], ["scheduler", "Pengingat Otomatis"],
    ["settings-whatsapp", "WhatsApp"], ["settings-doc-numbering", "Penomoran Dokumen"]]],
  ["settings-system", "Sistem", [["admin", "Integrasi & Audit"], ["settings-devices", "Perangkat RFID"],
    ["domain-registry", "Kamus Aturan Kain"], ["client-dataset-import", "Impor Data Awal"],
    ["settings-cfg-system", "AI & Tampilan"], ["settings-config", "Cari Semua Pengaturan"]]],
];
const tampak = (hub) => (HUB_TABS[hub] || []).filter((t) => !t.hidden);

describe("U3 — grup Pengaturan: sembilan hub berurutan, tanpa sub-judul", () => {
  test("butir grup settings-hub = sembilan hub dengan label baru; tanpa sub-judul", () => {
    const g = NAV_STRUCTURE.find((e) => e.groupId === "settings-hub");
    expect(g.items.filter(isNavHeading)).toEqual([]);
    expect(g.items.map((i) => [i.id, i.label, i.hub])).toEqual(SEMBILAN.map(([id, label]) => [id, label, id]));
    expect(g.items.find((i) => i.id === "settings-access").roles).toEqual(["admin", "manager"]);
  });

  test("tab tiap hub persis tabel unit; 3–6 tab tampak per hub; 36 tab (PY-T3 + Kalender Libur)", () => {
    for (const [hub, , tabs] of SEMBILAN) {
      expect([hub, tampak(hub).map((t) => [t.view, t.label])]).toEqual([hub, tabs]);
      expect(tampak(hub).length).toBeGreaterThanOrEqual(3);
      expect(tampak(hub).length).toBeLessThanOrEqual(6);
    }
    expect(SEMBILAN.reduce((n, [hub]) => n + tampak(hub).length, 0)).toBe(36);
    // hub lama hilang dari HUB_TABS (kini alias legacy)
    ["settings-purchasing", "settings-rnd", "settings-masters", "settings-notify"].forEach((h) => {
      expect(HUB_TABS[h]).toBeUndefined();
      expect(resolveAlias(h)).toMatchObject({ legacy: true, since: "KP-T9" });
    });
  });

  test("tab pecahan wadah lama membawa inheritsHiddenFrom", () => {
    const by = Object.fromEntries(Object.values(HUB_TABS).flat().map((t) => [t.view, t]));
    ["settings-pt-profile", "settings-pt-readiness", "settings-accounts", "permission-matrix", "settings-role-check"]
      .forEach((v) => expect([v, by[v].inheritsHiddenFrom]).toEqual([v, "entities-access"]));
    expect(by["settings-attendance-devices"].inheritsHiddenFrom).toEqual(["settings-devices", "hr-attendance-setup"]);
    expect(by["settings-whatsapp"].inheritsHiddenFrom).toBe("scheduler");
    expect(by["settings-devices"].inheritsHiddenFrom).toBe("cs-rfid-devices");
  });
});

// ── U4 — alamat lama mendarat di layar & hub tabel lama → baru (peran admin) ───────────────────────────────────────
const ALAMAT = {
  // 31 id tab lama (30 tab hub Pengaturan di HEAD awal unit + Komisi & Insentif yang dipindah MN-T1)
  "entities-access": ["settings-pt-profile", "settings-company"],
  "permission-matrix": ["permission-matrix", "settings-access"],
  "approval-rules": ["approval-rules", "settings-approval"],
  "rnd-divisions": ["rnd-divisions", "settings-approval"],
  "settings-cfg-approval": ["settings-cfg-approval", "settings-approval"],
  "settings-dual-control": ["settings-dual-control", "settings-approval"],
  "settings-cfg-sales": ["settings-cfg-sales", "settings-sales"],
  "incentive-rates": ["incentive-scheme", "hr-kpi-hub"],   // KM-T5 — alias ke Target & Aturan; KA-9 — ke Skema & Tarif
  "return-policies": ["return-policies", "settings-sales"],
  "amendment-reasons": ["amendment-reasons", "settings-sales"],
  "settings-cfg-warehouse": ["settings-cfg-warehouse", "settings-warehouse"],
  "settings-receiving-ocr": ["settings-receiving-ocr", "settings-warehouse"],
  "grade-master": ["grade-master", "settings-warehouse"],
  "settings-cfg-purchasing": ["settings-cfg-purchasing", "settings-warehouse"],
  "settings-cfg-rnd": ["settings-cfg-rnd", "settings-warehouse"],
  "settings-cfg-finance": ["settings-cfg-finance", "settings-finance"],
  "gl-account-mappings": ["gl-account-mappings", "settings-finance"],
  "expense-categories": ["expense-categories", "settings-finance"],
  "bank-recon-rules": ["bank-recon-rules", "settings-finance"],
  "settings-cfg-hr": ["settings-cfg-hr", "settings-hr"],
  "hr-attendance-setup": ["hr-attendance-setup", "settings-hr"],
  "settings-devices": ["settings-devices", "settings-system"],
  "entity-masters": ["entity-masters", "settings-company"],
  "domain-registry": ["domain-registry", "settings-system"],
  "client-dataset-import": ["client-dataset-import", "settings-system"],
  "pdf-templates": ["pdf-templates", "settings-documents"],
  "settings-doc-numbering": ["settings-doc-numbering", "settings-documents"],
  scheduler: ["scheduler", "settings-documents"],
  "settings-config": ["settings-config", "settings-system"],
  "settings-cfg-system": ["settings-cfg-system", "settings-system"],
  admin: ["admin", "settings-system"],
  // empat id hub yang hilang
  "settings-purchasing": ["settings-cfg-purchasing", "settings-warehouse"],
  "settings-rnd": ["settings-cfg-rnd", "settings-warehouse"],
  "settings-masters": ["entity-masters", "settings-company"],
  "settings-notify": ["scheduler", "settings-documents"],
  // alias lama yang tetap
  "settings-hub": ["grade-master", "settings-warehouse"],
  "doc-templates-basic": ["pdf-templates", "settings-documents"],
  "cs-rfid-devices": ["settings-devices", "settings-system"],
  "settings-cfg-documents": ["settings-cfg-approval", "settings-approval"],
  "settings-cfg-notify": ["settings-cfg-approval", "settings-approval"],
  // id hub yang bertahan / baru → tab pertama
  "settings-company": ["settings-pt-profile", "settings-company"],
  "settings-access": ["settings-accounts", "settings-access"],
  "settings-documents": ["pdf-templates", "settings-documents"],
  "settings-system": ["admin", "settings-system"],
};

test("U4 — 44 alamat (31 tab lama, 4 hub hilang, 5 alias, 4 hub) mendarat di layar & hub tabel lama → baru", () => {
  expect(Object.keys(ALAMAT)).toHaveLength(44);
  const salah = Object.entries(ALAMAT).map(([id, [view, navId]]) => {
    const t = resolveDeepLinkTarget(id, "admin");
    return t && t.view === view && t.navId === navId ? null : `${id} → ${t ? `${t.view} @ ${t.navId}` : "null"}`;
  }).filter(Boolean);
  expect(salah).toEqual([]);
  expect(resolveDeepLinkTarget("doc-templates-basic", "admin").preset).toEqual({ tab: "dasar" });
  expect(resolveDeepLinkTarget("cs-rfid-devices", "admin").preset).toEqual({ tab: "rfid" });
  expect(resolveDeepLinkTarget("settings-cfg-notify", "admin").preset).toEqual({ section: "pemberitahuan" });
});

// ── U5 — jangkauan tab Pengaturan per peran bawaan = potret awal (id baru dipetakan ke wadah lamanya) ───────────────
// Potret dibuat pada HEAD a742da9 sebelum unit ini (bukti/KP-T9/potret_jangkauan_awal.json); sama dengan & tanpa izin
// server. Finance melihat Pemetaan Akun sejak MN-T1 (IA-06). PY-T3 — + `hr-holidays` (tab BARU Kalender Libur: admin, manajer).
// K-SDM-01 (pemilik 17 Nov 2026) — Finance + Pengaturan › SDM: Aturan SDM & Penggajian, Shift & Lokasi Absen, Kalender Libur.
const POTRET = {
  admin: ["admin", "amendment-reasons", "approval-rules", "bank-recon-rules", "client-dataset-import", "domain-registry",
    "entities-access", "entity-masters", "expense-categories", "gl-account-mappings", "grade-master", "hr-attendance-setup",
    "hr-holidays", "pdf-templates", "return-policies", "rnd-divisions", "scheduler", "settings-cfg-approval", "settings-cfg-finance",
    "settings-cfg-hr", "settings-cfg-purchasing", "settings-cfg-rnd", "settings-cfg-sales", "settings-cfg-system",
    "settings-cfg-warehouse", "settings-config", "settings-devices", "settings-doc-numbering", "settings-dual-control",
    "settings-receiving-ocr"],
  manager: ["amendment-reasons", "approval-rules", "bank-recon-rules", "domain-registry", "entities-access", "entity-masters",
    "expense-categories", "gl-account-mappings", "grade-master", "hr-attendance-setup", "hr-holidays", "pdf-templates",
    "return-policies",
    "rnd-divisions", "scheduler", "settings-cfg-approval", "settings-cfg-finance", "settings-cfg-hr",
    "settings-cfg-purchasing", "settings-cfg-rnd", "settings-cfg-sales", "settings-cfg-system", "settings-cfg-warehouse",
    "settings-config", "settings-devices", "settings-doc-numbering", "settings-dual-control", "settings-receiving-ocr"],
  sales_admin: ["grade-master", "return-policies"],
  // K-FIN-01 (pemilik 17 Nov 2026 malam: "finance juga memiliki akses yang sama dengan manager") — = Manajer (di bawah).
  finance: null,
  warehouse_admin: ["grade-master", "settings-receiving-ocr"],
};
POTRET.finance = [...POTRET.manager];   // dulu: Pemetaan Akun, Aturan SDM & Penggajian, Shift & Lokasi Absen, Kalender Libur
/** id tab baru → id wadah lama (layar yang dulu memuatnya). */
const WADAH = {
  "settings-pt-profile": "entities-access", "settings-pt-readiness": "entities-access", "settings-accounts": "entities-access",
  "permission-matrix": "entities-access", "settings-role-check": "entities-access",
  "settings-attendance-devices": "settings-devices", "settings-whatsapp": "scheduler",
};
const BAWAAN = ROLE_IDS.filter((r) => !String(r).startsWith("cr_") && r !== "__preview");
const jangkauan = (role) => {
  const g = buildNavGroups(role, { showComingSoon: false }).find((x) => x.groupId === "settings-hub");
  const tabs = g ? g.items.flatMap((it) => hubTabsForRole(it.hub, role).map((t) => WADAH[t.view] || t.view)) : [];
  return [...new Set(tabs)].sort();
};

describe.each(BAWAAN)("U5 — jangkauan Pengaturan peran %s", (role) => {
  afterEach(() => setAccessContext(null));
  test("tanpa izin server (rancangan menu) = potret", () => {
    expect(jangkauan(role)).toEqual(POTRET[role] || []);
  });
  test("dengan izin server (view_resources) = potret", () => {
    setAccessContext({ role, permissions: builtin.permissions[role] || {}, view_resources: builtin.view_resources,
      hidden_views: [], view_actions: builtin.view_actions });
    expect(jangkauan(role)).toEqual(POTRET[role] || []);
  });
});

test("U5 — manajer dengan izin server: tab Peran & Hak Akses / Cek Peran tersembunyi (tanpa izin permission)", () => {
  setAccessContext({ role: "manager", permissions: builtin.permissions.manager, view_resources: builtin.view_resources,
    hidden_views: [], view_actions: builtin.view_actions });
  try {
    expect(hubTabsForRole("settings-access", "manager").map((t) => t.view)).toEqual(["settings-accounts"]);
    expect(hubTabsForRole("settings-hr", "manager").map((t) => t.view))
      .toEqual(["settings-cfg-hr", "hr-attendance-setup", "settings-attendance-devices", "hr-holidays"]);
    expect(hubTabsForRole("settings-system", "manager").map((t) => t.view))
      .toEqual(["domain-registry", "settings-cfg-system", "settings-config"]);
  } finally { setAccessContext(null); }
});

// ── U10 — hidden_views wadah lama menyembunyikan tab pecahannya ─────────────────────────────────────────────────────
describe("U10 — tab pecahan ikut tersembunyi bersama wadah lamanya", () => {
  const ADD = ["settings-hub", "settings-company", "settings-access", "settings-hr", "settings-documents", "settings-system",
    "entities-access", "settings-pt-profile", "settings-pt-readiness", "entity-masters", "settings-accounts",
    "permission-matrix", "settings-role-check", "settings-cfg-hr", "hr-attendance-setup", "settings-attendance-devices",
    "scheduler", "settings-whatsapp", "settings-devices", "cs-rfid-devices"];
  const PERMS = { entity: ["view"], user: ["view"], permission: ["view"], hr: ["view"], scheduler: ["view"],
    settings: ["view"], wms: ["view"], rfid_device: ["configure"] };
  const masuk = (hidden, remove = []) => {
    registerDynamicRoles([{ id: "cr_kpt9", label: "Uji KP-T9", custom: true, base_role: "", nav: { add: ADD, remove } }]);
    setAccessContext({ role: "cr_kpt9", permissions: PERMS, view_resources: builtin.view_resources, hidden_views: hidden,
      view_actions: builtin.view_actions });
  };
  const tabs = (hub) => hubTabsForRole(hub, "cr_kpt9").map((t) => t.view);
  afterEach(() => { setAccessContext(null); registerDynamicRoles([]); });

  test("hidden_views [entities-access] → lima tab pecahan tidak tampil; Master per PT tetap", () => {
    masuk([]);
    expect(tabs("settings-company")).toEqual(["settings-pt-profile", "settings-pt-readiness", "entity-masters"]);
    expect(tabs("settings-access")).toEqual(["settings-accounts", "permission-matrix", "settings-role-check"]);
    masuk(["entities-access"]);
    expect(tabs("settings-company")).toEqual(["entity-masters"]);
    expect(tabs("settings-access")).toEqual([]);
    // alias tidak menjadi pintu belakang: alamat lama yang disembunyikan tetap tertutup
    expect(resolveDeepLinkTarget("entities-access", "cr_kpt9")).toBeNull();
    expect(resolveDeepLinkTarget("settings-pt-profile", "cr_kpt9")).toBeNull();
  });

  test("hidden_views [settings-devices] → Mesin Absen ikut; [scheduler] → WhatsApp ikut; [cs-rfid-devices] → Perangkat RFID", () => {
    masuk(["settings-devices"]);
    expect(tabs("settings-hr")).toEqual(["settings-cfg-hr", "hr-attendance-setup"]);
    masuk(["scheduler"]);
    expect(tabs("settings-documents")).toEqual([]);
    masuk(["cs-rfid-devices"]);
    expect(tabs("settings-system")).toEqual([]);
    expect(tabs("settings-hr")).toEqual(["settings-cfg-hr", "hr-attendance-setup", "settings-attendance-devices"]);
  });

  test("peran kustom: `remove` hasil tingkat modul (bukan pilihan sembunyi) tidak menyembunyikan tab pecahan", () => {
    masuk([], ["settings-devices", "scheduler"]);   // mis. modul SDM saja: id wadah lama ikut `remove` modul lain
    expect(tabs("settings-hr")).toEqual(["settings-cfg-hr", "hr-attendance-setup", "settings-attendance-devices"]);
    expect(tabs("settings-documents")).toEqual(["settings-whatsapp"]);
  });
});
