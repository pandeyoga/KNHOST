// KP-T3 — Aturan Persetujuan: pilihan palsu dibuang (Owner, Diskon), "Jenjang yang berlaku" per PT, catatan peran
// tak dikenal / hasil migrasi, dan peringatan server di pop-up hasil simpan (docs/blueprint/unit/KP-T3.md, Layar + U14).
// Data jawaban server = bentuk `GET /api/approval-rules/effective` setelah U6 (PT Kanda: aturan PO ≥ Rp500 jt → Admin).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import ApprovalRulesSettings from "../settings/ApprovalRulesSettings";
import { DOC_TYPES, approverRoleOptions, docTypeLabel, tierLines } from "../settings/approvalRulesConstants";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
// Pemilih bawaan (cmdk/radix) diganti <select> polos yang tetap memperlihatkan pilihannya.
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange?.(e.target.value)}>
      <option value="">{p.placeholder || ""}</option>
      {(p.options || []).filter((o) => o.value !== "").map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      {(p.options || []).filter((o) => o.value === "").map((o) => <option key="__kosong" data-kosong="1">{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const ENTS = [{ id: "ent_ksc", name: "PT Kain Suka Cita", code: "KSC" }, { id: "ent_kanda", name: "CV Kanda Suka", code: "KND" }];
const ADMIN = { role: "admin", permissions: { settings: ["view", "manage"] } };
const JT = 1000000;
const DIREKSI = { level: 2, min_amount: 500 * JT, role: "admin", role_label: "Admin", label: "Direksi", role_known: true, source: "grup" };
const PO_GRUP = {
  doc_type: "purchase_order", label: "Pesanan Pembelian", source: "grup",
  tiers: [
    { level: 1, rule_id: "r1", sort: 1, min_amount: 0, max_amount: 100 * JT, required_role: "", required_role_label: "Tanpa persetujuan", role_known: true },
    { level: 1, rule_id: "r2", sort: 2, min_amount: 100 * JT, max_amount: null, required_role: "manager", required_role_label: "Manajer", role_known: true },
  ],
  extra_levels: [DIREKSI], unused_group_rules: [], warnings: [],
};
const W_CELAH = { code: "celah", from_amount: 0, to_amount: 500 * JT,
  message: "Nilai Rp0 s/d < Rp500.000.000 tidak tercakup aturan, sehingga lolos tanpa persetujuan." };
const W_LONGGAR = { code: "lebih_longgar_dari_grup", from_amount: 100 * JT, to_amount: 500 * JT,
  message: "PT ini punya aturan sendiri, jadi aturan grup untuk Pesanan Pembelian tidak dipakai. Akibatnya nilai Rp100.000.000 s/d < Rp500.000.000 lolos tanpa persetujuan, padahal aturan grup menuntut Manajer." };
const PO_KANDA = {
  doc_type: "purchase_order", label: "Pesanan Pembelian", source: "pt",
  tiers: [{ level: 1, rule_id: "rk", sort: 1, min_amount: 500 * JT, max_amount: null, required_role: "admin", required_role_label: "Admin", role_known: true }],
  extra_levels: [DIREKSI],
  unused_group_rules: [
    { rule_id: "r1", min_amount: 0, max_amount: 100 * JT, required_role: "", required_role_label: "Tanpa persetujuan" },
    { rule_id: "r2", min_amount: 100 * JT, max_amount: null, required_role: "manager", required_role_label: "Manajer" },
  ],
  warnings: [W_CELAH, W_LONGGAR],
};
const SO_KOSONG = { doc_type: "sales_order", label: "Pesanan Penjualan", source: "kosong", tiers: [], extra_levels: [], unused_group_rules: [], warnings: [] };
const EFEKTIF = {
  ent_ksc: { entity_id: "ent_ksc", entity_name: "PT Kain Suka Cita", doc_types: [SO_KOSONG, PO_GRUP] },
  ent_kanda: { entity_id: "ent_kanda", entity_name: "CV Kanda Suka", doc_types: [SO_KOSONG, PO_KANDA] },
};
const RULES = [
  { id: "a1", doc_type: "purchase_order", entity_id: "all", min_amount: 0, max_amount: 100 * JT, required_role: "", sort: 1, active: true, required_role_label: "Tanpa persetujuan", role_known: true },
  { id: "a2", doc_type: "sales_order", entity_id: "all", min_amount: 0, max_amount: null, required_role: "owner", sort: 1, active: true, required_role_label: "owner", role_known: false },
  { id: "a3", doc_type: "purchase_order", entity_id: "ent_kanda", min_amount: 0, max_amount: null, required_role: "manager", sort: 1, active: true, required_role_label: "Manajer", role_known: true, migrated_from_role: "owner" },
];

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount({ selectedEntity = "ent_ksc" } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(
      <EntityScopeProvider selectedEntity={selectedEntity} entities={ENTS}>
        <ApprovalRulesSettings currentUser={ADMIN} />
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
async function pick(el, value) {
  await act(async () => {
    el.value = value;
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}
const optionLabels = (id) => [...q(id).querySelectorAll("option")].map((o) => o.textContent).filter(Boolean);
const effCalls = () => mockGet.mock.calls.filter(([url]) => url.endsWith("/approval-rules/effective"));
function route({ effective = (ent) => Promise.resolve({ data: EFEKTIF[ent] }) } = {}) {
  mockGet.mockImplementation((url, cfg) => {
    if (url.endsWith("/approval-rules/effective")) return effective(cfg?.params?.entity_id);
    if (url.endsWith("/approval-rules")) return Promise.resolve({ data: RULES });
    return Promise.resolve({ data: [] });
  });
}

afterEach(async () => {
  const openCancel = document.body.querySelector(".modal-overlay [data-testid$='-cancel']");
  if (openCancel) await click(openCancel);
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockReset(); mockPost.mockReset();
  document.body.innerHTML = "";
});

test("pilihan: jenis dokumen tanpa Diskon, peran penyetuju tanpa Owner (label registry)", () => {
  expect(DOC_TYPES.map((t) => t.value)).toEqual(["sales_order", "purchase_order", "purchase_requisition"]);
  expect(approverRoleOptions()).toEqual([
    { value: "", label: "Tanpa persetujuan (lolos otomatis)" },
    { value: "manager", label: "Manajer" },
    { value: "admin", label: "Admin" },
  ]);
  expect(docTypeLabel("discount")).toBe("Diskon (%)");   // baris lama tetap terbaca, bukan pilihan
});

test("kalimat jenjang: grup + jenjang tambahan Direksi", () => {
  expect(tierLines(PO_GRUP).map((l) => l.text)).toEqual([
    "Rp0 s/d < Rp100.000.000 — tanpa persetujuan",
    "≥ Rp100.000.000 — Manajer",
    "≥ Rp500.000.000 — ditambah Direksi (Admin)",
  ]);
});

test("U14: PT Kanda — kartu PO berlencana 'Aturan khusus PT ini', dua peringatan kuning, aturan grup tak dipakai", async () => {
  route();
  await mount({ selectedEntity: "all" });
  // Mode "Semua PT": pemilih kosong dengan petunjuk; belum ada panggilan.
  expect(q("approval-effective-pick").textContent).toBe("Pilih PT untuk melihat jenjang yang berlaku.");
  expect(effCalls()).toHaveLength(0);
  await pick(q("approval-effective-entity"), "ent_kanda");
  expect(effCalls().at(-1)[1].params).toEqual({ entity_id: "ent_kanda" });
  expect(q("tier-source-purchase_order").textContent).toBe("Aturan khusus PT ini");
  const warn = [q("tier-warning-purchase_order-celah"), q("tier-warning-purchase_order-lebih_longgar_dari_grup")];
  warn.forEach((w) => expect(w.className).toContain("notice-bar warning"));
  expect(warn[1].textContent).toContain("padahal aturan grup menuntut Manajer");
  expect(q("tier-lines-purchase_order").textContent).toContain("≥ Rp500.000.000 — Admin");
  expect(q("tier-unused-purchase_order")).toBeNull();
  const toggle = q("tier-unused-toggle-purchase_order");
  expect(toggle.textContent).toBe("Lihat 2 aturan grup yang tidak dipakai");
  await click(toggle);
  expect([...q("tier-unused-purchase_order").querySelectorAll("li")].map((li) => li.textContent)).toEqual([
    "Rp0 s/d < Rp100.000.000 — tanpa persetujuan", "≥ Rp100.000.000 — Manajer"]);
  // Jenis tanpa aturan: lencana + kalimat kosong.
  expect(q("tier-source-sales_order").textContent).toBe("Belum ada aturan");
  expect(q("tier-empty-sales_order").textContent).toBe("Belum ada aturan untuk PT ini.");
  expect(document.body.textContent).not.toContain("ent_kanda");
});

test("PT aktif jadi bawaan; kartu grup tanpa tautan aturan tak dipakai", async () => {
  route();
  await mount({ selectedEntity: "ent_ksc" });
  expect(effCalls()[0][1].params).toEqual({ entity_id: "ent_ksc" });
  expect(q("tier-source-purchase_order").textContent).toBe("Aturan grup");
  expect(q("tier-unused-toggle-purchase_order")).toBeNull();
  expect([...q("tier-lines-purchase_order").querySelectorAll("li")].map((li) => li.textContent)).toEqual([
    "Rp0 s/d < Rp100.000.000 — tanpa persetujuan", "≥ Rp100.000.000 — Manajer",
    "≥ Rp500.000.000 — ditambah Direksi (Admin)"]);
});

test("memuat = kerangka abu-abu; galat = ErrorNotice dengan coba lagi", async () => {
  let gagal = true;
  let tahan;
  route({ effective: (ent) => (gagal ? Promise.reject({ response: { data: { detail: "Server sibuk" } } })
    : new Promise((res) => { tahan = () => res({ data: EFEKTIF[ent] }); })) });
  await mount({ selectedEntity: "ent_ksc" });
  expect(q("approval-effective-error").textContent).toContain("Server sibuk");
  gagal = false;
  await click(q("approval-effective-error-retry"));
  expect(q("approval-effective-loading")).not.toBeNull();
  await act(async () => { tahan(); });
  await flush();
  expect(q("approval-effective-loading")).toBeNull();
  expect(q("tier-card-purchase_order")).not.toBeNull();
});

test("tabel: 'Semua PT', peran tak dikenal ditandai, catatan hasil migrasi", async () => {
  route();
  await mount();
  expect(q("rule-row-a1").textContent).toContain("Semua PT");
  expect(document.body.textContent).not.toContain("Semua entitas");
  expect(q("rule-role-unknown-a2").textContent).toBe("peran tidak dikenal — diperlakukan sebagai Manajer");
  expect(q("rule-row-a2").textContent).toContain("owner");
  expect(q("rule-role-migrated-a3").textContent).toBe(
    "Dulu dipilih “owner”, yang selama ini sama dengan Manajer. Ubah ke Admin bila yang dimaksud Direksi.");
});

test("form: tanpa Diskon & Owner, 'Berlaku untuk PT', keterangan menggantikan; peringatan simpan di pop-up", async () => {
  route();
  mockPost.mockResolvedValue({ data: { id: "baru", doc_type: "purchase_order", warnings: [W_CELAH, W_LONGGAR] } });
  await mount();
  await click(q("create-rule-btn"));
  expect(optionLabels("rule-doc-type")).not.toContain("Diskon (%)");
  expect(optionLabels("rule-doc-type")).toEqual(["Pesanan Penjualan (SO)", "Pesanan Pembelian (PO)", "Permintaan Pembelian (PR)"]);
  expect(optionLabels("rule-required-role")).toEqual(["Manajer", "Admin", "Tanpa persetujuan (lolos otomatis)"]);
  expect(optionLabels("rule-required-role").join(" ")).not.toMatch(/Owner/);
  expect(optionLabels("rule-entity-id")[0]).toBe("Semua PT (aturan grup)");
  expect(q("rule-form").textContent).toContain("Berlaku untuk PT");
  expect(q("rule-form").textContent).not.toContain("Cakupan Entitas");
  expect(q("rule-entity-help").textContent).toBe(
    "Aturan khusus PT menggantikan semua aturan grup untuk jenis dokumen yang sama.");
  expect(q("rule-entity-help").querySelector("strong").textContent).toBe("menggantikan");
  const n0 = effCalls().length;
  await act(async () => { q("rule-form").querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
  await flush();
  expect(mockPost).toHaveBeenCalledTimes(1);
  const dlg = q("approval-rule-warnings");
  expect(dlg.querySelector("[role=dialog]").getAttribute("aria-label")).toBe("Aturan tersimpan. Perhatikan:");
  expect(q("approval-rule-warnings-message").textContent).toContain(W_CELAH.message);
  expect(q("approval-rule-warnings-message").textContent).toContain(W_LONGGAR.message);
  expect(effCalls().length).toBeGreaterThan(n0);   // jenjang dimuat ulang setelah simpan
  await click(q("approval-rule-warnings-confirm"));
  expect(q("approval-rule-warnings")).toBeNull();
});
