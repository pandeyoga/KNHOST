// PR-T5 — editor peran: tingkat sebagian berlencana jumlah aksi, tombol tingkat yang tidak berlaku tidak ditawarkan,
// konfirmasi menyebut aksi yang ditambah/dicabut + kalimat aksi berisiko; kartu peran empat keadaan; satu kamus label
// server untuk pesan penolakan & jejak audit; menu meja peran butuh aksi tertentu (`view_actions`).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import RoleModuleRow from "../settings/entities/RoleModuleRow";
import RoleEditorDrawer from "../settings/entities/RoleEditorDrawer";
import RoleAdvancedPanel from "../settings/entities/RoleAdvancedPanel";
import RoleAccessPanel from "../settings/entities/RoleAccessPanel";
import { permissionDeniedText } from "../../utils/apiError";
import { actionLabel, moduleLabel, setServerLabels } from "../../config/auditLabels";
import { navExplicitlyHidden, setAccessContext } from "../../config/roles";

jest.mock("../settings/entities/entityApi", () => ({
  createAccessRole: jest.fn(), patchAccessRole: jest.fn(), deleteAccessRole: jest.fn(), resetAccessRole: jest.fn(),
  followBaseAccessRole: jest.fn(), accessModules: jest.fn(), accessRolesFull: jest.fn(),
  errText: (e, d) => d,
}));
jest.mock("../../components/KNSelect", () => () => null);
jest.mock("../settings/entities/RoleMenuPreview", () => () => null);
jest.mock("../settings/entities/RoleAccountsList", () => () => null);
jest.mock("../settings/entities/RoleDangerDialog", () => () => null);
jest.mock("../settings/entities/RoleNotifPreview", () => () => null);
jest.mock("../settings/entities/RoleTraitsPanel", () => ({ __esModule: true, default: () => null,
  traitChangeLines: () => [], traitPayload: () => ({}) }));
jest.mock("../settings/entities/RoleNavTree", () => ({ __esModule: true, default: () => null, titleOf: (x) => x }));
const api = require("../settings/entities/entityApi");

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);

// Potongan katalog `GET /api/access/modules` (bentuk server sesudah PR-T5).
const PENJUALAN = {
  id: "penjualan", group: "Penjualan", label: "Pesanan Penjualan", description: "Pesanan (SO).",
  resources: ["order", "od_pricing"], nav: [],
  actions: { order: ["view", "create", "update", "release_unpaid"], od_pricing: ["view_cost", "set_price"] },
  levels_available: ["none", "view", "manage"], view_excludes: ["Harga Pesanan Khusus (kunci, harga PIC, biaya kontrak)"],
  sensitive_actions: { order: { release_unpaid: "mengirim barang sebelum lunas dan mengubah pesanan terkunci" },
    od_pricing: { view_cost: "melihat HPP dan margin" } },
};
const VISIBILITAS = {
  id: "field_visibility", group: "Gudang", label: "Melihat grade, nomor lot & asal barang", description: "Sakelar.",
  resources: ["field_visibility"], nav: [], actions: { field_visibility: ["grade", "lot", "origin"] },
  levels_available: ["none", "manage"], view_excludes: [], sensitive_actions: {},
};
const PERSETUJUAN = {
  id: "approval", group: "Alat", label: "Pusat Persetujuan", description: "Antrean.", resources: ["approval"], nav: [],
  actions: { approval: ["view"] }, levels_available: ["none", "view"], view_excludes: [], sensitive_actions: {},
};
const MODULES = [PENJUALAN, VISIBILITAS, PERSETUJUAN];
const LABELS = { resource_labels: { order: "Pesanan Penjualan (SO)", od_pricing: "Harga Pesanan Khusus" },
  action_labels: { view: "Lihat", create: "Buat", update: "Ubah", release_unpaid: "Kirim tanpa lunas", view_cost: "Lihat biaya",
    set_price: "Isi harga" } };
const SALES = { id: "sales", label: "Sales", custom: false, locked: false, users: 3, hidden_views: [], cross_entity: false,
  cross_entity_default: false, version: "v1", turn_alerts: [],
  permissions: { order: ["view", "create"], field_visibility: ["grade"] } };

async function render(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  return { host, root };
}

test("U15 — modul sebagian: lencana 'Sebagian (n dari m aksi)' dan tidak ada tombol tingkat yang menyala", async () => {
  const { host, root } = await render(<RoleModuleRow module={PENJUALAN} value="manage" partial held={2} total={6}
                                                     original="manage" onChange={() => {}} />);
  expect(q(host, "role-module-partial-penjualan").textContent).toBe("Sebagian (2 dari 6 aksi)");
  expect(host.querySelectorAll('[aria-pressed="true"]').length).toBe(0);
  expect(host.textContent).not.toMatch(/Kelola penuh/);
  expect(q(host, "role-level-penjualan-manage").textContent).toMatch("Semua aksi");
  await act(async () => { root.unmount(); });
});

test("U15 — modul sakelar hanya Mati/Nyala; modul hanya-lihat tanpa 'Semua aksi'", async () => {
  const a = await render(<RoleModuleRow module={VISIBILITAS} value="none" onChange={() => {}} />);
  expect(q(a.host, "role-level-field_visibility-view")).toBeNull();
  expect(q(a.host, "role-level-field_visibility-none").textContent).toMatch("Mati");
  expect(q(a.host, "role-level-field_visibility-manage").textContent).toMatch("Nyala");
  await act(async () => { a.root.unmount(); });
  const b = await render(<RoleModuleRow module={PERSETUJUAN} value="view" onChange={() => {}} />);
  expect(q(b.host, "role-level-approval-manage")).toBeNull();
  expect(q(b.host, "role-level-approval-view").getAttribute("aria-pressed")).toBe("true");
  await act(async () => { b.root.unmount(); });
});

test("'Lihat saja' menyebut halaman yang tidak termasuk", async () => {
  const { host, root } = await render(<RoleModuleRow module={PENJUALAN} value="view" onChange={() => {}} />);
  expect(q(host, "role-module-view-excludes-penjualan").textContent)
    .toBe("Tidak termasuk pada Lihat saja: Harga Pesanan Khusus (kunci, harga PIC, biaya kontrak).");
  await act(async () => { root.unmount(); });
});

test("U15 — 'Semua aksi' lalu simpan: daftar +aksi per halaman dan kalimat 'Perhatian — peran ini akan bisa: …'", async () => {
  api.patchAccessRole.mockResolvedValue({ ...SALES, label: "Sales", users: 3 });
  const { host, root } = await render(<RoleEditorDrawer role={SALES} roles={[SALES]} modules={MODULES} labels={LABELS}
                                                        onClose={() => {}} onSaved={() => {}} />);
  expect(q(host, "role-module-partial-penjualan").textContent).toBe("Sebagian (2 dari 6 aksi)");
  expect(q(host, "role-module-partial-field_visibility").textContent).toBe("Sebagian (1 dari 3 aksi)");
  expect(q(host, "role-editor-count-partial").textContent).toMatch(/^2 sebagian/);
  await act(async () => { q(host, "role-level-penjualan-manage").click(); });
  // tingkat tetap "manage" tetapi aksinya berubah → baris tetap bertanda diubah, menyebut keadaan sebelumnya
  expect(q(host, "role-module-changed-penjualan").textContent).toBe("diubah · sebelumnya Sebagian (2 dari 6 aksi)");
  await act(async () => { q(host, "role-editor-save").click(); });
  const diff = [...host.querySelectorAll('[data-testid="role-editor-confirm-diff-penjualan"]')].map((n) => n.textContent);
  expect(diff).toEqual(["Pesanan Penjualan (SO): +Ubah, +Kirim tanpa lunas", "Harga Pesanan Khusus: +Lihat biaya, +Isi harga"]);
  expect(q(host, "role-editor-confirm-penjualan").textContent).toMatch("Sebagian (2 dari 6 aksi) → Semua aksi");
  expect(q(host, "role-editor-confirm-sensitive").textContent).toBe(
    "Perhatian — peran ini akan bisa: mengirim barang sebelum lunas dan mengubah pesanan terkunci; melihat HPP dan margin.");
  await act(async () => { q(host, "role-editor-confirm-save").click(); });
  expect(api.patchAccessRole).toHaveBeenCalledWith("sales", expect.objectContaining({
    permissions: expect.objectContaining({ order: ["view", "create", "update", "release_unpaid"],
      od_pricing: ["view_cost", "set_price"] }) }));
  await act(async () => { root.unmount(); });
});

test("'Semua modul: Lihat saja' melewati modul sakelar (tidak dimatikan diam-diam)", async () => {
  const { host, root } = await render(<RoleEditorDrawer role={SALES} roles={[SALES]} modules={MODULES} labels={LABELS}
                                                        onClose={() => {}} onSaved={() => {}} />);
  await act(async () => { q(host, "role-editor-all-view").click(); });
  expect(q(host, "role-module-partial-field_visibility").textContent).toBe("Sebagian (1 dari 3 aksi)");
  expect(q(host, "role-level-penjualan-view").getAttribute("aria-pressed")).toBe("true");
  await act(async () => { root.unmount(); });
});

test("'Atur rinci': aksi berisiko diberi ikon & petunjuk kalimatnya", async () => {
  const { host, root } = await render(<RoleAdvancedPanel module={PENJUALAN} perms={{}} original={{}} labels={LABELS}
                                                         onToggle={() => {}} onSetResource={() => {}} />);
  expect(q(host, "role-action-sensitive-order-release_unpaid")).not.toBeNull();
  expect(q(host, "role-action-order-release_unpaid").getAttribute("title"))
    .toBe("Peran ini bisa mengirim barang sebelum lunas dan mengubah pesanan terkunci.");
  expect(q(host, "role-action-sensitive-order-create")).toBeNull();
  await act(async () => { root.unmount(); });
});

test("kartu peran: semua aksi · sebagian · lihat · tidak ada", async () => {
  api.accessModules.mockResolvedValue({ modules: MODULES, resource_labels: {}, action_labels: {} });
  api.accessRolesFull.mockResolvedValue({ canEditAssignable: false, roles: [{ ...SALES, levels: {
    penjualan: { level: "manage", partial: true, held: 2, total: 6 }, field_visibility: { level: "manage", partial: false },
    approval: { level: "view", partial: false }, accounts: { level: "none", partial: false } } }] });
  const { host, root } = await render(<RoleAccessPanel canManage={false} />);
  await act(async () => { await Promise.resolve(); });
  expect(q(host, "role-card-count-manage-sales").textContent).toBe("1 semua aksi");
  expect(q(host, "role-card-count-partial-sales").textContent).toBe("1 sebagian");
  expect(q(host, "role-card-count-view-sales").textContent).toBe("1 lihat");
  expect(q(host, "role-card-count-none-sales").textContent).toBe("1 tidak ada");
  await act(async () => { root.unmount(); });
});

test("satu kamus label: pesan penolakan & jejak audit memakai nama dari server", () => {
  setServerLabels({ resources: { order: "Pesanan Penjualan (SO)", permission: "Peran & Hak Akses" },
    actions: { view: "Lihat", release_unpaid: "Kirim tanpa lunas (pengecualian termin CBD/DP)",
      "cash.configure": "Kelola rekening kas & bank", configure: "Konfigurasi" },
    modules: { order: "Pesanan Penjualan" } });
  expect(permissionDeniedText("Permission ditolak: order.release_unpaid"))
    .toBe("Anda tidak punya izin “Kirim tanpa lunas (pengecualian termin CBD/DP)” di Pesanan Penjualan (SO).");
  expect(moduleLabel("permission")).toBe("Peran & Hak Akses");
  expect(actionLabel("configure", "cash")).toBe("Kelola rekening kas & bank");
  expect(actionLabel("configure")).toBe("Konfigurasi");
  expect(moduleLabel("sales_admin")).toBe("Meja Admin Sales");   // bukan sumber daya izin → peta setempat
  setServerLabels(null);
  expect(permissionDeniedText("Permission ditolak: order.view")).toBe("Anda tidak punya akses ke modul ini.");
});

test("U13 (layar) — menu meja peran butuh aksinya, bukan sekadar akses modul", () => {
  const user = (perms) => ({ role: "cr_lihat_pesanan", permissions: perms, hidden_views: [],
    view_resources: { "sales-admin-desk": ["order", "sales_return"], "sales-orders": ["order"] },
    view_actions: { "sales-admin-desk": [["order", "confirm"]] } });
  setAccessContext(user({ order: ["view"] }));
  expect(navExplicitlyHidden("cr_lihat_pesanan", "sales-admin-desk")).toBe(true);
  expect(navExplicitlyHidden("cr_lihat_pesanan", "sales-orders")).toBe(false);
  setAccessContext(user({ order: ["view", "confirm"] }));
  expect(navExplicitlyHidden("cr_lihat_pesanan", "sales-admin-desk")).toBe(false);
  setAccessContext(null);
});
