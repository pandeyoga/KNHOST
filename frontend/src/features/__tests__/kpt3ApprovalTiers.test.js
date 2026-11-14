// KP-T3 — pilihan Aturan Persetujuan yang dipakai mesin (tanpa "Diskon (%)" dan "Owner") dan kalimat jenjang
// (docs/blueprint/unit/KP-T3.md).
// KP-T4 — layar "Jenjang yang berlaku" (`ApprovalEffectiveTiers`) dan tabel/form `approval_rules` DIGANTIKAN Aturan
// Persetujuan satu tabel (`ApprovalPoliciesView`, uji `kpt4ApprovalPolicies.test.js`); uji komponen lamanya dicabut
// bersama komponennya. Yang tersisa: pembantu murni `approvalRulesConstants` (masih dipakai tabel Master per PT).
import { DOC_TYPES, approverRoleOptions, docTypeLabel, tierLines } from "../settings/approvalRulesConstants";

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
