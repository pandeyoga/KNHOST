// KP-T4 — Aturan Persetujuan satu tabel (docs/blueprint/unit/KP-T4.md, Layar + U16 bagian komponen).
// Data jawaban server = bentuk `GET /api/approval-policies` (`approval_policy_service.policy_view`) untuk PT Kanda:
// Uang Muka tiga jenjang (Atasan Langsung · Pimpinan · Bagian Keuangan) dan Pesanan Pembelian dengan satu peran
// tercantum yang belum memegang izin Pembelian.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import ApprovalPoliciesView from "../settings/ApprovalPoliciesView";
import ApprovalRulesSettings from "../settings/ApprovalRulesSettings";
import { approverText, groupKinds, passingText, tableRows } from "../settings/approvalPolicyHelpers";

const mockGet = jest.fn();
const mockPut = jest.fn();
const mockDelete = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), put: (...a) => mockPut(...a), post: () => Promise.resolve({ data: {} }),
    delete: (...a) => mockDelete(...a), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange?.(e.target.value)}>
      <option value="">{p.placeholder || ""}</option>
      {(p.options || []).filter((o) => o.value !== "").map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const ENTS = [{ id: "ent_ksc", name: "PT Kain Suka Cita", code: "KSC" }, { id: "ent_kanda", name: "CV Kanda Suka", code: "KND" }];
const JT = 1000000;
const tier = (o) => ({ id: "", min_amount: 0, max_amount: null, roles: [], role_labels: [], any_holder: false,
  passing_labels: [], no_permission_labels: [], source: "migrasi", ...o });
const CA_KANDA = {
  doc_kind: "cash_advance", label: "Uang muka (panjar)", group: "Keuangan", has_amount: true,
  permission_label: "Kas Kecil (PD / LPJ)", source: "grup", version: 1, note: "", unused_group_rows: [], warnings: [],
  levels: [
    { level: 1, label: "Atasan Langsung", tiers: [tier({ id: "c1", roles: ["admin", "manager"], role_labels: ["Admin", "Manajer"], passing_labels: ["Admin", "Manajer"] })] },
    { level: 2, label: "Pimpinan", tiers: [tier({ id: "c2", roles: ["admin"], role_labels: ["Admin"], passing_labels: ["Admin"] })] },
    { level: 3, label: "Bagian Keuangan", tiers: [tier({ id: "c3", roles: ["admin"], role_labels: ["Admin"], passing_labels: ["Admin"] })] },
  ],
};
const PO_KANDA = {
  doc_kind: "purchase_order", label: "Pesanan Pembelian", group: "Pembelian", has_amount: true,
  permission_label: "Pembelian & Pengadaan", source: "pt", version: 3, note: "", unused_group_rows: [],
  warnings: [{ code: "celah", level: 1, message: "Jenjang 1: nilai Rp0 s/d di bawah Rp50.000.000 tidak tercakup — dokumen di rentang itu tidak butuh persetujuan." }],
  levels: [
    { level: 1, label: "Persetujuan", tiers: [tier({ id: "p1", min_amount: 50 * JT, roles: ["manager", "finance"], role_labels: ["Manajer", "Finance"], passing_labels: ["Manajer"], no_permission_labels: ["Finance"] })] },
  ],
};
const TRANSFER = {
  doc_kind: "transfer", label: "Transfer gudang", group: "Gudang", has_amount: false, permission_label: "Stok & Persediaan",
  source: "grup", version: 1, note: "", unused_group_rows: [], warnings: [],
  levels: [{ level: 1, label: "Persetujuan", tiers: [tier({ id: "t1", any_holder: true, passing_labels: ["Semua pemegang akses"] })] }],
};

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mountView(el, { selectedEntity = "ent_kanda" } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(
      <EntityScopeProvider selectedEntity={selectedEntity} entities={ENTS}>
        {el}
        <ConfirmHost />
      </EntityScopeProvider>);
  });
  await flush();
  return host;
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
function route({ list = () => Promise.resolve({ data: { entity_id: "ent_kanda", kinds: [CA_KANDA, PO_KANDA, TRANSFER] } }),
  check = () => Promise.resolve({ data: { levels: [
    { level: 1, label: "Atasan Langsung", who: ["Admin", "Manajer"] },
    { level: 2, label: "Pimpinan", who: ["Admin"] },
    { level: 3, label: "Bagian Keuangan", who: ["Admin"] }] } }) } = {}) {
  mockGet.mockImplementation((url, cfg) => {
    if (url.endsWith("/approval-policies/check")) return check(cfg?.params);
    if (url.endsWith("/approval-policies")) return list(cfg?.params);
    return Promise.resolve({ data: [] });
  });
}

afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockReset(); mockPut.mockReset(); mockDelete.mockReset();
  document.body.innerHTML = "";
});

test("pembantu: kelompok urut, teks penyetuju & yang lolos", () => {
  expect(groupKinds([PO_KANDA, CA_KANDA, TRANSFER]).map((g) => g.group)).toEqual(["Pembelian", "Keuangan", "Gudang"]);
  expect(approverText(PO_KANDA.levels[0].tiers[0])).toBe("Manajer, Finance");
  expect(passingText(PO_KANDA.levels[0].tiers[0])).toBe("Manajer");
  expect(approverText(TRANSFER.levels[0].tiers[0])).toBe("Semua pemegang akses");
  expect(tableRows(CA_KANDA).map((r) => [r.level, r.label])).toEqual(
    [[1, "Atasan Langsung"], [2, "Pimpinan"], [3, "Bagian Keuangan"]]);
});

test("U16 (komponen): kartu Uang Muka PT Kanda — tiga jenjang berlabel, lencana sumber, yang lolos terisi", async () => {
  route();
  await mountView(<ApprovalPoliciesView />);
  expect(mockGet.mock.calls.find(([u]) => u.endsWith("/approval-policies"))[1].params).toEqual({ entity_id: "ent_kanda" });
  expect(q("appol-source-cash_advance").textContent).toBe("Aturan grup");
  // Pola UI 16 Nov (M43) — lencana asal pendek seperti daftar pengaturan ("Khusus PT ini", dulu "Aturan khusus PT ini").
  expect(q("appol-source-purchase_order").textContent).toBe("Khusus PT ini");
  // Daftar padat: satu baris per jenis dengan ringkasan; tabel jenjang baru tampil saat baris dibuka.
  expect(q("appol-summary-cash_advance").textContent).toBe("3 jenjang: Atasan Langsung → Pimpinan → Bagian Keuangan");
  expect(q("appol-summary-purchase_order").textContent).toBe("mulai Rp 50.000.000 · Manajer, Finance");
  expect(q("appol-issues-purchase_order").textContent).toContain("2 perlu dicek");   // 1 peringatan + 1 tanpa izin
  expect(q("appol-row-cash_advance-1")).toBeNull();
  for (const k of ["cash_advance", "purchase_order", "transfer"]) await click(q(`appol-toggle-${k}`));
  const rows = [1, 2, 3].map((n) => q(`appol-row-cash_advance-${n}`).textContent);
  expect(rows[0]).toContain("1 · Atasan Langsung");
  expect(rows[1]).toContain("2 · Pimpinan");
  expect(rows[2]).toContain("3 · Bagian Keuangan");
  expect(rows[0]).toContain("Admin, Manajer");
  const head = q("appol-card-cash_advance").querySelector("thead").textContent;
  ["Jenjang", "Mulai dari (Rp)", "Sampai di bawah (Rp)", "Yang boleh menyetujui", "Siapa saja yang lolos"]
    .forEach((h) => expect(head).toContain(h));
  // peran tercantum tanpa izin diberi tanda; peringatan server tampil kuning
  expect(q("appol-noperm-purchase_order").textContent).toBe("Finance: belum punya akses Pembelian & Pengadaan");
  expect(q("appol-warning-purchase_order-celah")).not.toBeNull();
  // jenis tanpa nominal tidak menampilkan kolom rupiah
  expect(q("appol-card-transfer").querySelector("thead").textContent).not.toContain("Mulai dari");
  expect(q("appol-row-transfer-1").textContent).toContain("Semua pemegang akses");
  expect(q("appol-dual-note").textContent).toContain("Kontrol Dua Orang");
  expect(q("appol-group-Keuangan")).not.toBeNull();
});

test("U16 (komponen): Coba nilai menampilkan jenjang dan siapa yang lolos", async () => {
  route();
  await mountView(<ApprovalPoliciesView />);
  // Pola UI 16 Nov (M43) — SATU penguji di bilah atas (jenis ▾ · nominal · Coba), bukan isian di tiap kartu.
  expect(q("appol-try-btn-cash_advance")).toBeNull();
  expect(q("appol-try-btn").disabled).toBe(true);                    // belum memilih jenis dokumen
  await act(async () => {
    q("appol-try-kind").value = "cash_advance";
    q("appol-try-kind").dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
  await click(q("appol-try-btn"));
  const call = mockGet.mock.calls.find(([u]) => u.endsWith("/approval-policies/check"));
  expect(call[1].params).toEqual({ doc_kind: "cash_advance", entity_id: "ent_kanda", amount: 0 });
  const res = q("appol-try-result").textContent;
  expect(res).toContain("Uang muka (panjar) · Rp 0");
  expect(res).toContain("Jenjang 1 — Atasan Langsung: Admin, Manajer");
  expect(res).toContain("Jenjang 3 — Bagian Keuangan: Admin");
});

test("memuat / galat + coba lagi / pemilih PT memuat ulang", async () => {
  let gagal = true;
  route({ list: (p) => (gagal ? Promise.reject(new Error("jaringan putus"))
    : Promise.resolve({ data: { entity_id: p.entity_id, kinds: [TRANSFER] } })) });
  await mountView(<ApprovalPoliciesView />);
  expect(q("appol-error")).not.toBeNull();
  gagal = false;
  const retry = q("appol-error").querySelector("button");
  await click(retry);
  expect(q("appol-card-transfer")).not.toBeNull();
  expect(q("appol-summary-transfer").textContent).toBe("Semua pemegang akses");
  await act(async () => {
    q("appol-entity").value = "all";
    q("appol-entity").dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
  const last = mockGet.mock.calls.filter(([u]) => u.endsWith("/approval-policies")).pop();
  expect(last[1].params).toEqual({ entity_id: "all" });
});

// ── (b) Layar penuh: Ubah / Buat aturan khusus PT ini / Kembali ke aturan grup ──────────────────────────────────────

const ADMIN = { role: "admin", permissions: { settings: ["view", "manage"] } };
const ROLES = [{ id: "admin", label: "Admin" }, { id: "manager", label: "Manajer" }, { id: "finance", label: "Finance" }];
async function type(el, value) {
  const setter = Object.getOwnPropertyDescriptor(el.constructor.prototype, "value").set;
  await act(async () => {
    setter.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await flush();
}
function routeFull(list) {
  mockGet.mockImplementation((url, cfg) => {
    if (url.endsWith("/approval-policies/kinds")) return Promise.resolve({ data: { kinds: [], roles: ROLES } });
    if (url.endsWith("/approval-policies/check")) return Promise.resolve({ data: { levels: [] } });
    if (url.endsWith("/approval-policies")) return Promise.resolve({ data: list(cfg?.params) });
    return Promise.resolve({ data: [] });
  });
}

test("layar penuh: aturan khusus PT → Ubah & Kembali ke aturan grup; aturan grup di PT → Buat aturan khusus PT ini", async () => {
  routeFull((p) => ({ entity_id: p.entity_id, kinds: [CA_KANDA, PO_KANDA] }));
  await mountView(<ApprovalRulesSettings currentUser={ADMIN} />);
  // Pola UI 16 Nov (M43) — satu tombol "Ubah" per baris; pada PT yang ikut aturan grup, Ubah = buat aturan khusus PT ini.
  expect(q("appol-create-cash_advance")).not.toBeNull();           // sumber grup di PT Kanda
  expect(q("appol-create-cash_advance").textContent).toBe("Ubah");
  expect(q("appol-create-cash_advance").getAttribute("title")).toContain("Buat aturan khusus PT ini");
  expect(q("appol-edit-purchase_order")).not.toBeNull();           // sumber PT
  expect(q("appol-reset-purchase_order")).toBeNull();              // "Kembali ke aturan grup" ada di baris yang dibuka
  await click(q("appol-toggle-purchase_order"));
  expect(q("appol-reset-purchase_order")).not.toBeNull();
  await click(q("appol-toggle-cash_advance"));
  expect(q("appol-follow-cash_advance").textContent).toContain("mengikuti aturan grup");
  expect(q("appol-reset-cash_advance")).toBeNull();
  expect(q("approval-rules-readonly")).toBeNull();
});

test("Buat aturan khusus PT ini: isian di tempat berjudul sesuai mode, PUT versi 0", async () => {
  routeFull((p) => ({ entity_id: p.entity_id, kinds: [CA_KANDA] }));
  mockPut.mockResolvedValue({ data: { ...CA_KANDA, source: "pt", version: 1 } });
  await mountView(<ApprovalRulesSettings currentUser={ADMIN} />);
  await click(q("appol-create-cash_advance"));
  const ed = q("appol-editor");
  expect(q("appol-card-cash_advance").contains(ed)).toBe(true);    // di dalam barisnya, bukan pop-up
  expect(document.body.querySelector(".modal-overlay")).toBeNull();
  expect(ed.textContent).toContain("Buat aturan khusus PT ini");
  expect(ed.textContent).toContain("Berlaku untuk: CV Kanda Suka (KND)");
  expect(q("appol-create-cash_advance")).toBeNull();               // tombol Ubah baris disembunyikan selama mengubah
  await type(q("appol-ed-reason"), "PT Kanda butuh aturan sendiri");
  await click(q("appol-editor-save"));
  expect(mockPut).toHaveBeenCalledTimes(1);
  expect(mockPut.mock.calls[0][1]).toEqual(expect.objectContaining({ entity_id: "ent_kanda", expected_version: 0 }));
  expect(q("appol-editor")).toBeNull();
});

test("Batal menutup isian tanpa PUT", async () => {
  routeFull((p) => ({ entity_id: p.entity_id, kinds: [PO_KANDA] }));
  await mountView(<ApprovalRulesSettings currentUser={ADMIN} />);
  await click(q("appol-edit-purchase_order"));
  await click(q("appol-editor-cancel"));
  expect(q("appol-editor")).toBeNull();
  expect(mockPut).not.toHaveBeenCalled();
  expect(q("appol-edit-purchase_order")).not.toBeNull();
});

test("Ubah: isian di tempat, alasan wajib, PUT seluruh jenjang dengan versi; peran registry bisa dicentang", async () => {
  routeFull((p) => ({ entity_id: p.entity_id, kinds: [PO_KANDA] }));
  mockPut.mockResolvedValue({ data: { ...PO_KANDA, version: 4 } });
  await mountView(<ApprovalRulesSettings currentUser={ADMIN} />);
  await click(q("appol-edit-purchase_order"));
  expect(q("appol-editor")).not.toBeNull();
  await click(q("appol-ed-role-0-0-admin"));
  await click(q("appol-editor-save"));
  expect(mockPut).not.toHaveBeenCalled();                          // alasan kosong → tidak terkirim
  expect(document.body.textContent).toContain("Alasan perubahan wajib diisi");
  await type(q("appol-ed-reason"), "Admin ikut menyetujui PO");
  await click(q("appol-editor-save"));
  expect(mockPut).toHaveBeenCalledTimes(1);
  const [url, body] = mockPut.mock.calls[0];
  expect(url).toBe("/api/approval-policies/purchase_order");
  expect(body).toEqual({ entity_id: "ent_kanda", expected_version: 3, reason: "Admin ikut menyetujui PO",
    levels: [{ level: 1, label: "Persetujuan", tiers: [{ min_amount: 50 * JT, max_amount: null,
      roles: ["manager", "finance", "admin"], any_holder: false }] }] });
  expect(q("appol-ok")).not.toBeNull();
});

test("Kembali ke aturan grup: alasan wajib lalu DELETE berparameter PT", async () => {
  routeFull((p) => ({ entity_id: p.entity_id, kinds: [PO_KANDA] }));
  mockDelete.mockResolvedValue({ data: { ...PO_KANDA, source: "grup" } });
  await mountView(<ApprovalRulesSettings currentUser={ADMIN} />);
  await click(q("appol-toggle-purchase_order"));
  await click(q("appol-reset-purchase_order"));
  await type(q("appol-reset-confirm-reason"), "Ikuti aturan grup lagi");
  await click(q("appol-reset-confirm-confirm"));
  expect(mockDelete).toHaveBeenCalledWith("/api/approval-policies/purchase_order",
    { params: { entity_id: "ent_kanda", reason: "Ikuti aturan grup lagi" } });
});

test("tanpa izin kelola: baca-saja, tidak ada tombol ubah", async () => {
  routeFull((p) => ({ entity_id: p.entity_id, kinds: [PO_KANDA] }));
  await mountView(<ApprovalRulesSettings currentUser={{ role: "manager", permissions: { settings: ["view"] } }} />);
  expect(q("approval-rules-readonly")).not.toBeNull();
  expect(q("appol-edit-purchase_order")).toBeNull();
  await click(q("appol-toggle-purchase_order"));
  expect(q("appol-row-purchase_order-1")).not.toBeNull();          // tetap bisa membaca jenjangnya
  expect(q("appol-reset-purchase_order")).toBeNull();
});
