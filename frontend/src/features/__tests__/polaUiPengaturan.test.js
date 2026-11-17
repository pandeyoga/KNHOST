// Pola UI gelombang Pengaturan (docs/blueprint/04_POLA_UI.md §2.D; masukan pemilik 16 Nov M43 "Semua menu Pengaturan
// masih berantakan, boros, tidak konsisten … bertele-tele", foto 36–40).
//  · Hak akses per peran (foto 36): matriks baris = modul, kolom = tingkat; ringkasan satu baris; peringatan satu baris.
//  · Peran & Hak Akses (foto 37): satu bilah daftar (cari · ? · muat ulang · + Buat Peran Baru), tanpa bilah penjelasan.
//  · Aturan Persetujuan (foto 38): satu baris per jenis + penguji "Coba nilai" bersama (uji komponen di kpt4).
//  · Kontrol dua orang (foto 40): baris padat, isian Rp hanya bila berlaku, tanpa gema "Rp 0".
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";

const mockGet = jest.fn();
const mockPut = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), put: (...a) => mockPut(...a),
    post: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled} aria-label={p["aria-label"]}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      <option value="">{p.placeholder || ""}</option>
      {(p.options || []).filter((o) => o.value !== "").map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../settings/entities/entityApi", () => ({
  createAccessRole: jest.fn(), patchAccessRole: jest.fn(), deleteAccessRole: jest.fn(), resetAccessRole: jest.fn(),
  followBaseAccessRole: jest.fn(), previewAccessRole: jest.fn(), accessModules: jest.fn(), accessRolesFull: jest.fn(),
  accessRoleHistory: jest.fn(), errText: (e, d) => d,
}));
jest.mock("../settings/entities/RoleMenuPreview", () => () => null);
jest.mock("../settings/entities/RoleAccountsList", () => () => null);
jest.mock("../settings/entities/RoleNotifPreview", () => () => null);
jest.mock("../settings/entities/RoleTraitsPanel", () => ({ __esModule: true, default: () => null,
  traitChangeLines: () => [], traitPayload: () => ({}) }));
jest.mock("../settings/entities/RoleNavTree", () => ({ __esModule: true, default: () => null, titleOf: (x) => x }));

import DualControlView, { batasBerlaku, bantuanAksi } from "../settings/kontrol/DualControlView";
import RoleAccessPanel from "../settings/entities/RoleAccessPanel";
import RoleEditorDrawer from "../settings/entities/RoleEditorDrawer";
import RoleModuleRow from "../settings/entities/RoleModuleRow";
import { SOURCE_BADGE, issueCount, ruleSummary } from "../settings/approvalPolicyHelpers";
const api = require("../settings/entities/entityApi");

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(<>{el}<ConfirmHost /></>); });
  await flush();
  return host;
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
async function choose(el, value) {
  await act(async () => {
    el.value = value;
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}
afterEach(async () => {
  const openCancel = document.body.querySelector(".modal-overlay [data-testid$='-cancel']");
  if (openCancel) await click(openCancel);
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockReset(); mockPut.mockReset();
  jest.clearAllMocks();
  document.body.innerHTML = "";
});

// ── Kontrol dua orang (foto 40) ──────────────────────────────────────────────────────────────────────────────────
const BAGIAN = ["Pembelian & hutang", "Penjualan & piutang", "Gudang & produksi", "SDM", "Buku besar"];
const row = (aksi, label, bagian, min, nominal, sumber = "default", batas = 0) => ({
  aksi, label, bagian, kelompok: "B", punya_nominal: nominal, min_orang: min, batas_nominal: nominal ? batas : null,
  sumber, kunci_min_orang: `kontrol.${aksi}.min_orang`, kunci_batas: nominal ? `kontrol.${aksi}.batas_nominal` : null,
});
const DUAL = (over = {}) => ({
  rows: [row("setujui_po", "Persetujuan PO", BAGIAN[0], "2", true),
    row("tagihan_pemasok", "Tagihan pemasok", BAGIAN[0], "1", true, "entity", 5000000),
    row("transfer_gudang", "Transfer gudang / antar-PT", BAGIAN[2], "1", false, "global")],
  bagian: BAGIAN, entity_id: "ent_ksc", admin_boleh_sendiri: true, admin_tetap_dua_orang: ["setujui_po"],
  can_edit: true, ...over,
});
const ENTS = [{ id: "ent_ksc", legal_name: "PT Kain Suka Cita", short_name: "Sukacita" }];

describe("Kontrol dua orang — baris padat", () => {
  test("isian Rp hanya bila berlaku (bernominal & cukup satu orang), tanpa gema 'Rp 0'; sumber = lencana", async () => {
    mockGet.mockResolvedValue({ data: DUAL() });
    await mount(<DualControlView selectedEntity="ent_ksc" entities={ENTS} />);
    // Harus dua orang → batas tidak dipakai: "—", bukan isian.
    expect(q("dual-limit-setujui_po").tagName).toBe("SPAN");
    expect(q("dual-limit-setujui_po").textContent).toBe("—");
    // Cukup satu orang + bernominal → isian, tanpa baris pratinjau di bawahnya; nilai terformat di tooltip.
    const input = q("dual-limit-tagihan_pemasok");
    expect(input.tagName).toBe("INPUT");
    expect(input.value).toBe("5000000");
    expect(input.getAttribute("title")).toMatch(/^Rp\s5\.000\.000$/);   // formatCurrency memakai spasi tak-putus
    expect(q("dual-limit-tagihan_pemasok-preview")).toBeNull();
    expect(document.body.textContent).not.toMatch(/Rp\s?0\b/);
    // Tanpa nominal → "—".
    expect(q("dual-limit-transfer_gudang").textContent).toBe("—");
    // Sumber berwarna lapisan (bawaan abu · grup biru · PT ungu).
    expect(q("dual-source-setujui_po").className).toBe("badge-muted");
    expect(q("dual-source-tagihan_pemasok").className).toBe("badge-purple");
    expect(q("dual-source-transfer_gudang").className).toBe("badge-blue");
    // Paragraf pengantar pindah ke ikon ?; tiap baris punya ? sendiri.
    expect(document.body.textContent).not.toContain("Atur aksi mana yang");
    expect(q("dual-help")).not.toBeNull();
    expect(q("dual-help-tagihan_pemasok")).not.toBeNull();
  });

  test("ganti ke 'Harus dua orang' menyembunyikan isian batas; kembali ke satu orang memunculkannya; hitung perubahan", async () => {
    mockGet.mockResolvedValue({ data: DUAL() });
    await mount(<DualControlView selectedEntity="ent_ksc" entities={ENTS} />);
    expect(q("dual-dirty-count")).toBeNull();
    await choose(q("dual-min-tagihan_pemasok"), "2");
    expect(q("dual-limit-tagihan_pemasok").textContent).toBe("—");
    expect(q("dual-dirty-count").textContent).toBe("1 perubahan belum disimpan");
    await choose(q("dual-min-setujui_po"), "1");
    expect(q("dual-limit-setujui_po").tagName).toBe("INPUT");
  });

  test("daftar 'Tetap dua orang walau Admin' tertutup sampai dibuka; jumlahnya tampil di baris", async () => {
    mockGet.mockResolvedValue({ data: DUAL() });
    await mount(<DualControlView selectedEntity="ent_ksc" entities={ENTS} />);
    expect(q("dual-admin-keep-count").textContent).toBe("1 aksi");
    expect(q("dual-admin-keep-setujui_po")).toBeNull();
    await click(q("dual-admin-keep-open"));
    expect(q("dual-admin-keep-setujui_po").checked).toBe(true);
    await click(q("dual-admin-keep-tagihan_pemasok"));
    expect(q("dual-admin-keep-count").textContent).toBe("2 aksi");
    await click(q("dual-admin-self"));
    expect(q("dual-admin-keep-count").textContent).toContain("tidak berlaku");
  });

  test("hanya-baca: batas tampil sebagai teks, satu baris keterangan (bukan bilah)", async () => {
    mockGet.mockResolvedValue({ data: DUAL({ can_edit: false }) });
    await mount(<DualControlView selectedEntity="ent_ksc" entities={ENTS} />);
    expect(q("dual-limit-tagihan_pemasok").textContent).toMatch(/^dua orang di atas Rp\s5\.000\.000$/);
    expect(q("dual-readonly").tagName).toBe("P");
    expect(q("dual-savebar")).toBeNull();
  });

  test("pembantu: batasBerlaku & bantuanAksi", () => {
    expect(batasBerlaku({ punya_nominal: true }, "1")).toBe(true);
    expect(batasBerlaku({ punya_nominal: true }, "2")).toBe(false);
    expect(batasBerlaku({ punya_nominal: false }, "1")).toBe(false);
    expect(bantuanAksi({ label: "Kontrabon", punya_nominal: true })).toContain("di atas batas nominal");
    expect(bantuanAksi({ label: "ACC desain", punya_nominal: false })).not.toContain("batas nominal");
  });
});

// ── Aturan Persetujuan (foto 38) — pembantu ringkasan satu baris ─────────────────────────────────────────────────
describe("Aturan Persetujuan — ringkasan satu baris & lencana pendek", () => {
  const tier = (o) => ({ min_amount: 0, max_amount: null, roles: [], role_labels: [], any_holder: false,
    no_permission_labels: [], ...o });
  test("ruleSummary", () => {
    expect(ruleSummary({ has_amount: true, levels: [{ level: 1, label: "Persetujuan", tiers: [tier({})] }] }))
      .toBe("Tanpa persetujuan");
    expect(ruleSummary({ has_amount: false, levels: [{ level: 1, label: "P", tiers: [tier({ roles: ["admin", "manager"],
      role_labels: ["Admin", "Manajer"] })] }] })).toBe("Admin, Manajer");
    expect(ruleSummary({ has_amount: true, levels: [{ level: 1, label: "P", tiers: [
      tier({ min_amount: 0, max_amount: 1000 }), tier({ min_amount: 1000, roles: ["admin"], role_labels: ["Admin"] })] }] }))
      .toBe("mulai Rp 1.000 · Admin");                                // rentang tanpa peran tidak dihitung
    expect(ruleSummary({ has_amount: true, levels: [
      { level: 1, label: "Atasan", tiers: [tier({ roles: ["a"], role_labels: ["A"] })] },
      { level: 2, label: "", tiers: [tier({ any_holder: true })] }] })).toBe("2 jenjang: Atasan → Jenjang 2");
  });
  test("issueCount & SOURCE_BADGE", () => {
    expect(issueCount({ warnings: [{ code: "x" }], levels: [{ tiers: [tier({ no_permission_labels: ["Finance"] })] }] })).toBe(2);
    expect(issueCount({ warnings: [], levels: [] })).toBe(0);
    expect(SOURCE_BADGE.bawaan.label).toBe("Bawaan sistem");
    expect(SOURCE_BADGE.bawaan.label).not.toMatch(/belum disimpan/);
    expect(SOURCE_BADGE.bawaan.title).toMatch(/belum pernah disimpan/);
  });
});

// ── Peran & Hak Akses (foto 37) ──────────────────────────────────────────────────────────────────────────────────
const MOD_SO = {
  id: "penjualan", group: "Penjualan", label: "Pesanan Penjualan", description: "Pesanan (SO), koreksi, retur.",
  resources: ["order"], nav: [], actions: { order: ["view", "create", "update"] },
  levels_available: ["none", "view", "manage"], view_excludes: [], sensitive_actions: {},
};
const MOD_VIS = {
  id: "field_visibility", group: "Gudang", label: "Melihat grade & lot", description: "Sakelar.",
  resources: ["field_visibility"], nav: [], actions: { field_visibility: ["grade", "lot"] },
  levels_available: ["none", "manage"], view_excludes: [], sensitive_actions: {},
};
const MODULES = [MOD_SO, MOD_VIS];
const SALES = { id: "sales", label: "Sales", description: "Tim penjualan lapangan", custom: false, locked: false, users: 3,
  hidden_views: [], cross_entity: false, cross_entity_default: false, version: "v1", turn_alerts: [],
  permissions: { order: ["view"] }, levels: { penjualan: { level: "view", partial: false } } };
const KUSTOM = { ...SALES, id: "cr_tagih", label: "Staf Penagihan", description: "Piutang & pelanggan", custom: true,
  base_role: "finance", base_role_label: "Finance" };

describe("Peran & Hak Akses — satu bilah daftar, daftar padat", () => {
  test("bilah: cari · ? · muat ulang · + Buat Peran Baru; tanpa bilah penjelasan; muat ulang memuat ulang peran", async () => {
    api.accessModules.mockResolvedValue({ modules: MODULES, resource_labels: {}, action_labels: {} });
    api.accessRolesFull.mockResolvedValue({ canEditAssignable: false, roles: [SALES, KUSTOM] });
    await mount(<RoleAccessPanel canManage />);
    const bar = q("role-toolbar");
    ["role-search", "role-access-help", "role-access-refresh", "role-create-button"]
      .forEach((id) => expect(bar.querySelector(`[data-testid="${id}"]`)).not.toBeNull());
    expect(q("role-toolbar-count").textContent).toBe("2 peran");
    expect(document.body.textContent).not.toContain("Peran menentukan modul mana");   // dulu bilah biru panjang
    await click(q("role-access-help"));
    expect(q("role-access-help-text").textContent).toContain("Peran menentukan modul mana");
    expect(api.accessRolesFull).toHaveBeenCalledTimes(1);
    await click(q("role-access-refresh"));
    expect(api.accessRolesFull).toHaveBeenCalledTimes(2);
  });

  test("satu baris per peran; keterangan peran di ?; cari menyaring kustom & bawaan", async () => {
    api.accessModules.mockResolvedValue({ modules: MODULES, resource_labels: {}, action_labels: {} });
    api.accessRolesFull.mockResolvedValue({ canEditAssignable: false, roles: [SALES, KUSTOM] });
    await mount(<RoleAccessPanel canManage={false} />);
    expect(q("role-card-cr_tagih").className).toContain("cfg-row");
    expect(q("role-card-kind-cr_tagih").textContent).toBe("Kustom");
    expect(q("role-card-sales").textContent).not.toContain("Tim penjualan lapangan");
    expect(q("role-card-help-sales")).not.toBeNull();
    const search = q("role-search");
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(search, "tagih");
      search.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await flush();
    expect(q("role-card-cr_tagih")).not.toBeNull();
    expect(q("role-card-sales")).toBeNull();
    expect(q("role-toolbar-count").textContent).toBe("1 peran");
  });
});

// ── Hak akses per peran (foto 36) ────────────────────────────────────────────────────────────────────────────────
describe("Editor hak akses — matriks tanpa gulir mendatar", () => {
  test("baris modul berkolom tetap: tiga tingkat + Rinci; keterangan modul di ?; sakelar tanpa kolom Lihat saja", async () => {
    const host = await mount(<RoleModuleRow module={MOD_SO} value="view" onChange={() => {}} onToggleAdvanced={() => {}} />);
    expect(host.querySelector(".cfg-mx-row")).not.toBeNull();
    expect(host.textContent).not.toContain("Pesanan (SO), koreksi");
    await click(q("role-module-help-penjualan"));
    expect(q("role-module-help-penjualan-text").textContent).toContain("Pesanan (SO), koreksi");
    expect(q("role-level-penjualan-view").getAttribute("aria-pressed")).toBe("true");
    expect(q("role-level-penjualan-view").className).toContain("link-button");
    expect(q("role-module-advanced-penjualan")).not.toBeNull();
    for (const r of roots) await act(async () => { r.unmount(); });
    roots = []; document.body.innerHTML = "";
    await mount(<RoleModuleRow module={MOD_VIS} value="manage" partial held={1} total={2} onChange={() => {}} />);
    expect(q("role-level-field_visibility-view")).toBeNull();
    expect(q("role-level-field_visibility-manage").getAttribute("aria-pressed")).toBe("false");   // sebagian
    expect(q("role-level-field_visibility-manage").getAttribute("title")).toContain("Sebagian (1 dari 2 aksi)");
  });

  test("editor: kepala kolom + baris 'Semua modul'; ringkasan satu baris, rincian & peringatan terpisah; tanpa kotak info", async () => {
    jest.useFakeTimers();
    api.previewAccessRole.mockResolvedValue({ nav_added: [], turn_alerts: [], summary: {
      home: { label: "Meja Sales" }, data_scope: { label: "Milik sendiri" }, kategori: { label: "Sales" },
      cross_entity: false, approvals: [], risky: ["membatalkan kwitansi"], follows_base: [],
      modules: [{ id: "penjualan", label: "Pesanan Penjualan", pages: [{ label: "SO", can: ["Lihat"], cannot: ["Buat"] }] }],
    } });
    await mount(<RoleEditorDrawer role={SALES} roles={[SALES]} modules={MODULES} labels={{}} onClose={() => {}} onSaved={() => {}} />);
    await act(async () => { jest.advanceTimersByTime(600); });
    await flush();
    jest.useRealTimers();
    const matrix = q("role-editor-matrix");
    const head = matrix.querySelector(".cfg-mx-head").textContent;
    ["Modul", "Tidak ada", "Lihat saja", "Semua aksi", "Rinci"].forEach((h) => expect(head).toContain(h));
    expect(q("role-editor-all").className).toContain("cfg-mx-row");
    expect(q("role-editor-all-manage").getAttribute("aria-label")).toBe("Jadikan semua modul: Semua aksi");
    expect(q("role-editor-group-Penjualan").querySelector(".cfg-mx-group").textContent).toBe("Penjualan");
    // ringkasan: satu baris (jumlah per tingkat + halaman awal + data + PT); rincian per modul di <details>.
    expect(q("role-editor-count-view").textContent).toBe("1 lihat");
    expect(q("role-summary-scope").textContent).toBe("Data yang terlihat: Milik sendiri");
    expect(q("role-summary-details").tagName).toBe("DETAILS");
    expect(q("role-summary-details").open).toBe(false);
    expect(q("role-summary-details").contains(q("role-summary-module-penjualan"))).toBe(true);
    expect(q("role-summary-risky").textContent).toBe("Perhatian — peran ini bisa: membatalkan kwitansi.");
    // kotak info "berlaku otomatis" & keterangan judul pindah ke ? judul.
    expect(document.body.textContent).not.toContain("Perubahan berlaku otomatis");
    await click(q("role-editor-help"));
    expect(q("role-editor-help-text").textContent).toContain("Perubahan berlaku otomatis");
    expect(q("role-editor-help-text").textContent).toContain("Tim penjualan lapangan.");
    // tanpa gulir mendatar: kolom kiri boleh menyusut (minmax 0), wadah gulir menyembunyikan luapan mendatar.
    const scroll = q("role-editor-drawer").querySelector(".cfg-mx-scroll");
    expect(scroll.className).toContain("lg:grid-cols-[minmax(0,1fr)_280px]");
  });
});
