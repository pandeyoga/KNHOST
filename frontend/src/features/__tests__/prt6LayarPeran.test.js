// PR-T6 — layar Peran & Hak Akses dan Akun & Akses (uji komponen; uji jalan peramban U18/U19 terpisah):
// "Peran dasar" dan "Salin hak akses dari…" dua kontrol terpisah; ganti peran dasar lewat konfirmasi berisi
// `follows_base`; panel Ringkasan peran dari pratinjau server; mode baca + tab Riwayat; "Menu lain" tanpa id grup;
// menu peran bawaan bertambah dari `nav.add` server; tab Badan Usaha & Akses mengikuti izin; formulir akun tanpa peran
// awal dan kalimat lintas PT dari server; galat lewat penerjemah pusat; label jejak audit.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("../settings/entities/entityApi", () => ({
  createAccessRole: jest.fn(), patchAccessRole: jest.fn(), deleteAccessRole: jest.fn(), resetAccessRole: jest.fn(),
  followBaseAccessRole: jest.fn(), previewAccessRole: jest.fn(), accessRoleHistory: jest.fn(),
  accessRoleSummary: jest.fn(), accessRolesFull: jest.fn(), accessModules: jest.fn(), publicRoles: jest.fn(),
  manageableRoles: jest.fn(), availableEmployees: jest.fn(), createUser: jest.fn(), patchUser: jest.fn(),
  listEntities: jest.fn(), ROLE_OPTIONS: [],
  errText: jest.requireActual("../settings/entities/entityApi").errText,
}));
// Pemilih bawaan (cmdk/radix) diganti <select> polos.
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      <option value="">{p.placeholder || ""}</option>
      {(p.options || []).map((o) => <option key={o.value} value={o.value} disabled={o.disabled}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../settings/entities/RoleMenuPreview", () => () => null);
jest.mock("../settings/entities/RoleAccountsList", () => () => <div data-testid="role-editor-accounts-mock" />);
jest.mock("../settings/entities/RoleAdvancedPanel", () => () => null);
jest.mock("../settings/entities/AccountLocationScope", () => ({ AccountLocationScope: () => null }));
jest.mock("../../hooks/useDomainEnums", () => () => ({ options: () => [] }));
const mockAsk = jest.fn();
jest.mock("../../services/confirmService", () => ({ askConfirm: (...a) => mockAsk(...a) }));
jest.mock("../../services/apiClient", () => ({
  __esModule: true, API: "/api",
  default: { get: () => Promise.resolve({ data: {} }), post: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } } },
}));
const mockToast = jest.fn();
jest.mock("../../hooks/use-toast", () => ({ toast: (...a) => mockToast(...a) }));
// Badan Usaha & Akses: isi tab diganti penanda (yang diuji hanya tab mana yang tampil).
jest.mock("../settings/entities/EntityList", () => () => <div data-testid="tab-isi-entities" />);
jest.mock("../settings/entities/AccountList", () => () => <div data-testid="tab-isi-accounts" />);
jest.mock("../settings/entities/RoleAccessPanel", () => () => <div data-testid="tab-isi-roles" />);
jest.mock("../settings/entities/RoleRealityPanel", () => () => <div data-testid="tab-isi-role-reality" />);
jest.mock("../settings/entities/EntityReadinessPanel", () => () => <div data-testid="tab-isi-readiness" />);
jest.mock("../settings/entities/EntityWizard", () => () => null);
jest.mock("../settings/entities/EntityDetailDrawer", () => () => null);
jest.mock("../../components/DesktopOnlyNotice", () => () => null);

/* eslint-disable import/first */
import RoleEditorDrawer from "../settings/entities/RoleEditorDrawer";
import { navTree } from "../settings/entities/RoleNavTree";
import { approvalLines, pageLine } from "../settings/entities/RoleSummaryPanel";
import AccountFormDrawer from "../settings/entities/AccountFormDrawer";
import { roleCanSee, registerDynamicRoles } from "../../config/roles";
import { auditActionInfo } from "../../config/auditLabels";
import EntitiesAccessView from "../settings/entities/EntitiesAccessView";
import useSessionSync from "../../hooks/useSessionSync";
/* eslint-enable import/first */
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
  await act(async () => { root.render(el); });
  await flush();
  return host;
}
async function pick(el, value) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(el, value);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}
async function click(el) { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await flush(); }
async function waitPreview() { await act(async () => { jest.advanceTimersByTime(600); }); await flush(); }

const SUMMARY_FIN = {
  home: { view: "finance-desk", label: "Meja Finance" }, data_scope: { value: "semua", label: "Semua di PT yang boleh dibuka" },
  kategori: { value: "", label: "Tidak ada" }, cross_entity: false, approvals: { follows_rank_of: "Finance" },
  modules: [{ id: "ar", label: "Uang Masuk", level: "manage", partial: true, held: 1, total: 2,
    pages: [{ label: "Kwitansi", can: ["Lihat"], cannot: ["Batalkan (void)"] }] }],
  risky: [], follows_base: ["Halaman awal mengikuti Finance", "Data yang terlihat mengikuti Finance"],
};
const SUMMARY_SALES = { ...SUMMARY_FIN, data_scope: { value: "milik_sendiri", label: "Milik sendiri" },
  follows_base: ["Data yang terlihat mengikuti Sales"] };
const MODULES = [{ id: "ar", label: "Uang Masuk", group: "Keuangan", resources: ["ar_receipt"],
  actions: { ar_receipt: ["view", "void"] }, levels_available: ["none", "view", "manage"], nav: [] }];
const FIN = { id: "finance", label: "Finance", custom: false, locked: false, cross_entity: false, permissions: { ar_receipt: ["view"] } };
const SALES = { id: "sales", label: "Sales", custom: false, locked: false, cross_entity: false, permissions: { ar_receipt: ["view", "void"] } };
const ADMIN = { id: "admin", label: "Admin", custom: false, locked: true, permissions: {} };
const K = { id: "cr_k", label: "K Uji", custom: true, base_role: "finance", base_role_label: "Finance", users: 2, users_inactive: 1,
  deletable: false, locked: false, can_manage: true, version: "v1", permissions: { ar_receipt: ["view"] }, hidden_views: [],
  cross_entity: false, cross_entity_default: false, turn_alerts: [], traits_overridden: [] };
const ROLES = [ADMIN, FIN, SALES, K];

beforeEach(() => {
  jest.useFakeTimers();
  api.previewAccessRole.mockImplementation((body) => Promise.resolve({
    summary: body.base_role === "sales" ? SUMMARY_SALES : SUMMARY_FIN, nav_added: [], turn_alerts: [] }));
  api.accessRoleHistory.mockResolvedValue([]);
});
afterEach(() => {
  roots.forEach((r) => act(() => r.unmount()));
  roots = [];
  document.body.innerHTML = "";
  jest.useRealTimers();
  jest.clearAllMocks();
});

test("U18 — peran baru: Peran dasar dan Salin hak akses dari… dua kontrol; menyalin tidak mengganti peran dasar", async () => {
  api.createAccessRole.mockResolvedValue({ id: "cr_baru", label: "Baru" });
  await mount(<RoleEditorDrawer role={null} roles={ROLES} modules={MODULES} labels={{}} onClose={() => {}} onSaved={() => {}} />);
  expect(q("role-editor-base-select")).not.toBeNull();
  expect(q("role-editor-copy-from")).not.toBeNull();
  await pick(q("role-editor-base-select"), "sales");
  await pick(q("role-editor-copy-from"), "finance");
  expect(q("role-editor-base-select").value).toBe("sales");
  await waitPreview();
  expect(api.previewAccessRole).toHaveBeenLastCalledWith(expect.objectContaining({ base_role: "sales", permissions: { ar_receipt: ["view"] } }));
  expect(q("role-summary-scope").textContent).toBe("Data yang terlihat: Milik sendiri");
  expect(q("role-summary-module-ar").textContent).toContain("Kwitansi: bisa Lihat; tidak bisa Batalkan (void).");
  expect(q("role-summary-follows").textContent).toBe("Mengikuti peran dasar: Data yang terlihat mengikuti Sales.");
  expect(q("role-summary-approvals").textContent).toContain("Mengikuti tingkat Finance; diatur di Aturan Persetujuan.");
});

test("ganti peran dasar peran kustom: konfirmasi berisi sebelum & sesudah; simpan mengirim base_role", async () => {
  api.patchAccessRole.mockResolvedValue({ ...K, users: 2 });
  const onSaved = jest.fn();
  await mount(<RoleEditorDrawer role={K} roles={ROLES} modules={MODULES} labels={{}} onClose={() => {}} onSaved={onSaved} />);
  await waitPreview();
  await pick(q("role-editor-base-select"), "sales");
  expect(q("role-editor-base-confirm")).not.toBeNull();
  expect(document.body.textContent).toContain("Ganti peran dasar ke Sales?");
  expect(q("role-editor-base-confirm-before").textContent).toContain("Halaman awal mengikuti Finance");
  expect(q("role-editor-base-confirm-after").textContent).toContain("Data yang terlihat mengikuti Sales");
  await click(q("role-editor-base-confirm-confirm"));
  expect(q("role-editor-base-select").value).toBe("sales");
  await click(q("role-editor-save"));
  expect(q("role-editor-confirm-base").textContent).toContain("Finance → Sales");
  await click(q("role-editor-confirm-save"));
  expect(api.patchAccessRole).toHaveBeenCalledWith("cr_k", expect.objectContaining({ base_role: "sales", permissions: { ar_receipt: ["view"] } }));
  expect(onSaved).toHaveBeenCalled();
});

test("hapus mati dengan petunjuk akun aktif & nonaktif; judul duplikat menyebut peran dasar", async () => {
  await mount(<RoleEditorDrawer role={K} roles={ROLES} modules={MODULES} labels={{}} onClose={() => {}} onSaved={() => {}} />);
  expect(q("role-editor-delete").disabled).toBe(true);
  expect(q("role-editor-delete-hint").textContent).toBe("Masih dipakai 3 akun (1 nonaktif) — pindahkan akunnya dulu.");
  roots.forEach((r) => act(() => r.unmount())); roots = []; document.body.innerHTML = "";
  await mount(<RoleEditorDrawer role={null} template={K} roles={ROLES} modules={MODULES} labels={{}} onClose={() => {}} onSaved={() => {}} />);
  expect(q("role-editor-title").textContent).toBe("Duplikat Peran · K Uji (peran dasar: Finance)");
});

test("U19 — mode baca (tanpa permission.update): judul 'Lihat Hak Akses', isian mati, tanpa simpan/hapus/pindah; tab Riwayat", async () => {
  api.accessRoleHistory.mockResolvedValue([{ at: "2026-11-13T03:00:00+00:00", actor: "Budi", action: "role_access_updated",
    action_label: "Hak akses diubah", added: [], removed: ["Kwitansi: Batalkan (void)"], other: [], users: 2 }]);
  await mount(<RoleEditorDrawer role={K} roles={ROLES} modules={MODULES} labels={{}} canManage={false} onClose={() => {}} onSaved={() => {}} />);
  expect(q("role-editor-title").textContent).toBe("Lihat Hak Akses · K Uji");
  expect(q("role-editor-save")).toBeNull();
  expect(q("role-editor-delete")).toBeNull();
  expect(q("role-editor-label").disabled).toBe(true);
  expect(q("role-editor-base-select").disabled).toBe(true);
  expect(q("role-editor-copy-from")).toBeNull();
  expect(q("role-level-ar-manage").disabled).toBe(true);
  expect(q("role-editor-cancel").textContent).toBe("Tutup");
  await click(q("role-editor-tabs-riwayat"));
  expect(api.accessRoleHistory).toHaveBeenCalledWith("cr_k");
  expect(q("role-history-row").textContent).toContain("− Kwitansi: Batalkan (void)");
  expect(q("role-history-row").textContent).toContain("WIB");
});

test("riwayat kosong; ringkasan galat → 'Coba lagi'", async () => {
  api.previewAccessRole.mockRejectedValue(new Error("x"));
  await mount(<RoleEditorDrawer role={K} roles={ROLES} modules={MODULES} labels={{}} onClose={() => {}} onSaved={() => {}} />);
  expect(q("role-summary-loading")).not.toBeNull();
  await waitPreview();
  expect(q("role-summary-error").textContent).toContain("Ringkasan tidak bisa dimuat.");
  api.previewAccessRole.mockResolvedValue({ summary: { ...SUMMARY_FIN, modules: [] }, nav_added: [], turn_alerts: [] });
  await click(q("role-summary-retry"));
  await waitPreview();
  expect(q("role-summary-empty").textContent).toBe("Belum ada modul yang dinyalakan.");
  await click(q("role-editor-tabs-riwayat"));
  expect(q("role-history-empty").textContent).toBe("Belum ada perubahan tercatat.");
});

test("lintas PT dimatikan → dialog Tinjau penugasan PT berisi akun dan tombol Buka Akun & Akses", async () => {
  const onOpen = jest.fn();
  const onSaved = jest.fn();
  api.patchAccessRole.mockResolvedValue({ ...K, users: 2, accounts_to_review: [{ id: "u1", name: "Rina", allowed_entities: ["KSC", "Kanda"] }] });
  await mount(<RoleEditorDrawer role={{ ...K, cross_entity: true }} roles={ROLES} modules={MODULES} labels={{}}
                                onClose={() => {}} onSaved={onSaved} onOpenAccounts={onOpen} />);
  await click(q("role-editor-cross-entity-toggle"));
  await click(q("role-editor-save"));
  await click(q("role-editor-confirm-save"));
  expect(q("role-editor-review").textContent).toContain("Rina — KSC, Kanda");
  expect(q("role-editor-review-confirm").textContent).toBe("Buka Akun & Akses");
  await click(q("role-editor-review-confirm"));
  expect(onSaved).toHaveBeenCalled();
  expect(onOpen).toHaveBeenCalled();
});

test("ringkasan: batas persetujuan dan kalimat halaman", () => {
  expect(approvalLines([{ label: "Pesanan Pembelian", level: "Persetujuan 1", max_amount: 5000000 },
    { label: "Tagihan", level: "Pimpinan", max_amount: null }]))
    .toEqual(["Pesanan Pembelian — Persetujuan 1, sampai Rp 5.000.000", "Tagihan — Pimpinan, tanpa batas"]);
  expect(approvalLines({ follows_rank_of: "Manajer" })).toEqual(["Mengikuti tingkat Manajer; diatur di Aturan Persetujuan."]);
  expect(pageLine({ label: "SO", can: ["Lihat", "Buat"], cannot: [] })).toBe("SO: bisa Lihat, Buat.");
});

test("'Menu & tab yang tampil': id grup sidebar/hub tidak tampil sebagai centang", () => {
  const menus = navTree({ id: "x", nav: ["settings-hub", "penjualan", "gudang", "price-corrections"] });
  const ids = menus.flatMap((m) => m.tabs.map((t) => t.id));
  expect(ids).not.toContain("settings-hub");
  expect(ids).not.toContain("penjualan");
  expect(ids).not.toContain("gudang");
  expect(ids).toContain("price-corrections");
});

test("menu peran bawaan bertambah dari nav.add server (tidak diwariskan ke peran kustom)", () => {
  expect(roleCanSee(["admin", "manager"], "finance", "hr-people")).toBe(false);
  registerDynamicRoles([{ id: "finance", label: "Finance", custom: false, home_view: "finance-desk", nav: { add: ["hrd", "hr-people"], remove: [] } },
    { id: "cr_fin", label: "Fin", custom: true, base_role: "finance", nav: { add: [], remove: [] } }]);
  expect(roleCanSee(["admin", "manager"], "finance", "hr-people")).toBe(true);
  expect(roleCanSee(["admin", "manager"], "cr_fin", "hr-people")).toBe(false);
  registerDynamicRoles([{ id: "finance", label: "Finance", custom: false, home_view: "finance-desk", nav: { add: [], remove: [] } }]);
  expect(roleCanSee(["admin", "manager"], "finance", "hr-people")).toBe(false);
});

test("formulir akun: tanpa peran awal ('Pilih peran…', wajib); kalimat lintas PT dari server; label peran dasar", async () => {
  api.publicRoles.mockResolvedValue([{ id: "manager", label: "Manajer", custom: false, cross_entity: false },
    { id: "sales", label: "Sales", custom: false, cross_entity: false },
    { id: "cr_kasir", label: "Kasir", custom: true, base_role: "finance", cross_entity: true },
    { id: "finance", label: "Finance", custom: false, cross_entity: false }]);
  api.manageableRoles.mockResolvedValue({ all: true });
  api.availableEmployees.mockResolvedValue([]);
  api.accessRoleSummary.mockResolvedValue({ ...SUMMARY_FIN, cross_entity: true });
  await mount(<AccountFormDrawer user={null} entities={[{ id: "ent_ksc", legal_name: "KSC", short_name: "KSC" }]} selectedEntity="ent_ksc" onClose={() => {}} onSaved={() => {}} />);
  const sel = q("account-form-role");
  expect(sel.value).toBe("");
  expect(sel.options[0].textContent).toBe("Pilih peran…");
  expect([...sel.options].map((o) => o.textContent)).toContain("Kasir · peran dasar Finance");
  expect(q("account-form-cross")).toBeNull();
  await click(q("account-form-submit"));
  expect(q("account-form-errors").textContent).toContain("Peran wajib dipilih.");
  await pick(sel, "manager");   // Manajer yang lintas PT-nya dimatikan → kalimat mengikuti server, bukan daftar tertulis
  expect(q("account-form-cross").textContent).toBe("Peran ini hanya membuka PT yang dicentang di bawah.");
  expect(q("account-form-allowed")).not.toBeNull();
  await pick(sel, "cr_kasir");
  expect(q("account-form-cross").textContent).toBe("Peran ini membuka semua PT aktif.");
  expect(api.accessRoleSummary).toHaveBeenLastCalledWith("cr_kasir");
  expect(q("account-role-summary-body").textContent).toContain("PT: semua PT aktif");
  expect(q("account-role-summary-open")).toBeNull();   // tanpa permission.view: tanpa tautan "Lihat hak peran ini"
});

test("formulir akun: melepas tautan karyawan meminta konfirmasi 'Lepas tautan ke {nama}?'", async () => {
  api.publicRoles.mockResolvedValue([{ id: "sales", label: "Sales", custom: false, cross_entity: false }]);
  api.manageableRoles.mockResolvedValue({ all: true });
  api.availableEmployees.mockResolvedValue([]);
  api.accessRoleSummary.mockResolvedValue(SUMMARY_SALES);
  mockAsk.mockResolvedValue(false);
  const user = { id: "u1", name: "Rina", email: "r@x.id", role: "sales", employee_id: "e1",
    employee: { id: "e1", name: "Rina Karyawan", code: "K1", entity_id: "ent_ksc" }, home_entity_id: "ent_ksc", allowed_entity_ids: ["ent_ksc"] };
  await mount(<AccountFormDrawer user={user} entities={[{ id: "ent_ksc", legal_name: "KSC" }]} canViewRoles onClose={() => {}} onSaved={() => {}} />);
  await click(q("account-form-hr-none"));
  expect(mockAsk).toHaveBeenCalledWith(expect.objectContaining({ title: "Lepas tautan ke Rina Karyawan?" }));
  expect(q("account-form-home-locked")).not.toBeNull();   // dibatalkan → tautan tetap
  expect(q("account-role-summary-open")).not.toBeNull();
});

test("galat layar peran & akun lewat penerjemah pusat; label jejak audit peran", () => {
  const e = { response: { status: 403, data: { detail: "Permission ditolak: permission.view" } } };
  expect(api.errText(e, "x")).not.toMatch(/permission\.view|Permission/);
  const blk = { response: { status: 409, data: { detail: { message: "Tidak bisa diarsip", blockers: ["Ada stok"] } } } };
  expect(api.errText(blk, "x")).toBe("Tidak bisa diarsip · Ada stok");
  expect(auditActionInfo("custom_role_created").label).toBe("Peran dibuat");
  expect(auditActionInfo("custom_role_deleted").label).toBe("Peran dihapus");
  expect(auditActionInfo("role_users_moved").label).toBe("Akun dipindahkan ke peran lain");
});

test("tab Peran & Hak Akses dan Cek Peran hanya bagi pemegang permission.view; Akun & Akses bagi user.view", async () => {
  api.listEntities.mockResolvedValue([]);
  const tabs = () => [...document.body.querySelectorAll('[data-testid^="entities-access-tab-"]')].map((n) => n.getAttribute("data-testid").replace("entities-access-tab-", ""));
  await mount(<EntitiesAccessView currentUser={{ role: "cr_x", permissions: { entity: ["view"] } }} initialTab="roles" />);
  expect(tabs()).toEqual(["entities", "readiness"]);
  expect(q("tab-isi-roles")).toBeNull();
  expect(q("tab-isi-entities")).not.toBeNull();   // tab awal yang tidak boleh dibuka → tab pertama yang boleh
  roots.forEach((r) => act(() => r.unmount())); roots = []; document.body.innerHTML = "";
  await mount(<EntitiesAccessView currentUser={{ role: "cr_y", permissions: { user: ["view"], permission: ["view"] } }} />);
  expect(tabs()).toEqual(["entities", "accounts", "roles", "role-reality", "readiness"]);
});

function SessionProbe({ user, onView }) {
  useSessionSync({ token: "", user, setUser: () => {}, setEntityContext: () => {}, setEntities: () => {},
    setActiveView: onView, setActiveNavId: () => {} });
  return null;
}

test("peran berubah di tengah sesi → ke halaman awal peran baru + pemberitahuan", async () => {
  const onView = jest.fn();
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(<SessionProbe user={{ id: "u1", role: "sales" }} onView={onView} />); });
  expect(onView).not.toHaveBeenCalled();
  await act(async () => { root.render(<SessionProbe user={{ id: "u1", role: "warehouse", role_label: "Gudang" }} onView={onView} />); });
  expect(onView).toHaveBeenCalledWith("operations");
  expect(mockToast).toHaveBeenCalledWith({ title: "Peran Anda berubah menjadi Gudang." });
});
