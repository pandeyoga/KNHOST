// A2 (pelatihan keuangan 18 Nov) — temuan uji jalan Pengadaan sampai Bayar:
//   · pembuat PO di Persetujuan Pembelian dulu hanya melihat "—" (tanpa alasan) → kini "PO Anda — disetujui orang lain";
//   · pesan "Inbound task otomatis dibuat" → Bahasa Indonesia;
//   · Jejak Dokumen menampilkan kode mentah "Converted" / "Scheduled payment" / "Assigned";
//   · Dokumen Terkait di rincian tagihan menulis kode sumber jurnal "vendor_bill".
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { docStatusLabel } from "../../utils/docStatus";
import PurchaseApprovalView from "../purchasing/PurchaseApprovalView";
import DocRefsPanel from "../documents/trace/DocRefsPanel";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    put: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../hooks/useCanDecide", () => ({
  __esModule: true,
  useCanDecideMap: (rows) => Object.fromEntries((rows || []).map((p) => [p.id, { allowed: true }])),
  default: () => ({ allowed: true }),
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const PO = {
  id: "po_a2", po_number: "KSC/PO-00099", status: "waiting_approval", supplier_name: "Latihan 99 · Pemasok",
  warehouse_name: "Jakarta", items: [{}], total_amount: 105000000, grand_total: 116550000, ppn_amount: 11550000,
  created_by_id: "user_manager_01", version: 1,
  approval_chain: [{ level: 1, required_role: "manager", status: "pending", label: "Manajer" }],
};

async function render(user) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<PurchaseApprovalView currentUser={user} selectedEntity="ent_ksc" />); });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  return { host, root };
}

beforeEach(() => {
  mockGet.mockReset(); mockPost.mockReset();
  mockGet.mockImplementation(() => Promise.resolve({ data: [PO] }));
});

test("pembuat PO melihat alasan kunci, bukan tanda strip", async () => {
  const { host, root } = await render({ id: "user_manager_01", role: "manager", permissions: {} });
  const lock = host.querySelector('[data-testid="po-approve-locked-po_a2"]');
  expect(lock).not.toBeNull();
  expect(lock.textContent).toContain("PO Anda — disetujui orang lain");
  expect(host.querySelector('[data-testid="po-approve-po_a2"]')).toBeNull();
  act(() => root.unmount());
});

test("penyetuju lain mendapat tombol Setujui; pesan sesudah setuju berbahasa Indonesia", async () => {
  mockPost.mockImplementation(() => Promise.resolve({ data: { ...PO, status: "pending", approval_status: "approved" } }));
  const { host, root } = await render({ id: "user_admin_01", role: "admin", permissions: {} });
  const btn = host.querySelector('[data-testid="po-approve-po_a2"]');
  expect(btn).not.toBeNull();
  await act(async () => { btn.click(); });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  const notice = host.querySelector('[data-testid="po-approval-notice"]');
  expect(notice.textContent).toContain("Tugas Barang Masuk untuk gudang otomatis dibuat");
  expect(notice.textContent).not.toMatch(/Inbound task/);
  act(() => root.unmount());
});

test("label status Jejak Dokumen alur pengadaan tidak mentah", () => {
  expect(docStatusLabel("converted")).toBe("Dikonversi");
  expect(docStatusLabel("assigned")).toBe("Ditugaskan");
  expect(docStatusLabel("scheduled_payment")).toBe("Dijadwalkan bayar");
});

test("Dokumen Terkait: catatan jurnal berlabel, bukan kode sumber", async () => {
  mockGet.mockImplementation(() => Promise.resolve({ data: { number: "VB-00099", refs: [
    { rel: "journaled_by", rel_label: "Dijurnal di", doc_type: "journal_entry", doc_id: "je_a2", doc_number: "KSC/JE-00099",
      label: "Jurnal", status: "posted", note: "vendor_bill" }] } }));
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<DocRefsPanel docType="vendor_bill" docId="vb_a2" />); });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  const row = host.querySelector('[data-testid="docrefs-row-je_a2"]');
  expect(row.textContent).toContain("Tagihan Supplier");
  expect(row.textContent).not.toContain("vendor_bill");
  act(() => root.unmount());
});
