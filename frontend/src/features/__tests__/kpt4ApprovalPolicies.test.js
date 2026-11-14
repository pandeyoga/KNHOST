// KP-T4 — Aturan Persetujuan satu tabel (docs/blueprint/unit/KP-T4.md, Layar + U16 bagian komponen).
// Data jawaban server = bentuk `GET /api/approval-policies` (`approval_policy_service.policy_view`) untuk PT Kanda:
// Uang Muka tiga jenjang (Atasan Langsung · Pimpinan · Bagian Keuangan) dan Pesanan Pembelian dengan satu peran
// tercantum yang belum memegang izin Pembelian.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import ApprovalPoliciesView from "../settings/ApprovalPoliciesView";
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
  expect(q("appol-source-purchase_order").textContent).toBe("Aturan khusus PT ini");
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
  await click(q("appol-try-btn-cash_advance"));
  const call = mockGet.mock.calls.find(([u]) => u.endsWith("/approval-policies/check"));
  expect(call[1].params).toEqual({ doc_kind: "cash_advance", entity_id: "ent_kanda", amount: 0 });
  const res = q("appol-try-result-cash_advance").textContent;
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
  await act(async () => {
    q("appol-entity").value = "all";
    q("appol-entity").dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
  const last = mockGet.mock.calls.filter(([u]) => u.endsWith("/approval-policies")).pop();
  expect(last[1].params).toEqual({ entity_id: "all" });
});
