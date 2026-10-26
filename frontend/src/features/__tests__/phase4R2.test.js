// Fase 4 · R2 — pop-up keuangan/kontrabon/kas kecil/dokumen → FormModal/DetailModal baku (L-03), tata letak
// Rekonsiliasi Bank, Kontrabon, Kasus Keuangan, Koreksi & Amandemen, Pusat Export (L-01/L-02).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import DecisionModal from "../purchasing/contrabon/DecisionModal";
import DeductionModal from "../purchasing/contrabon/DeductionModal";
import PayModal from "../purchasing/contrabon/PayModal";
import ReasonNoteModal from "../purchasing/contrabon/ReasonNoteModal";
import ContraBonsView from "../purchasing/contrabon/ContraBonsView";
import JournalEntryModal from "../finance/JournalEntryModal";
import JournalDetailModal from "../finance/JournalDetailModal";
import { RedeemModal, ReverseModal } from "../finance/StoreCreditModals";
import TaxInvoices from "../finance/TaxInvoices";
import BankReconciliationView from "../finance/BankReconciliationView";
import ReconContraBonModal from "../finance/bank/ReconContraBonModal";
import ReconMatchModal from "../finance/bank/ReconMatchModal";
import PaymentVarianceDialog from "../finance/payments/PaymentVarianceDialog";
import PenaltyPanel from "../finance/payments/PenaltyPanel";
import FinanceCasesView from "../finance/cases/FinanceCasesView";
import CasePlaybookWizard from "../finance/cases/CasePlaybookWizard";
import AmendmentCenterView from "../finance/amendments/AmendmentCenterView";
import VehicleLogsView from "../pettycash/VehicleLogsView";
import WhatsAppSettings from "../documents/WhatsAppSettings";
import RecordDetailModal from "../documents/RecordDetailModal";
import DocumentActionsBar from "../documents/DocumentActionsBar";
import ExportCenterView from "../export/ExportCenterView";
import GroupConsolidationView from "../finance/GroupConsolidationView";
import { askConfirm } from "../../services/confirmService";

const mockGet = jest.fn();
const mockPost = jest.fn(() => Promise.resolve({ data: {} }));
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: jest.fn(async () => false),
  askReason: jest.fn(async () => null),
  askText: jest.fn(async () => null),
  askChoice: jest.fn(async () => null),
  default: {},
}));
jest.mock("../documents/ESignModal", () => () => null);
jest.mock("../documents/WhatsAppModal", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function settle() { await act(async () => {}); await act(async () => {}); }
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await settle();
  return { host, root };
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
}
async function esc() {
  await act(async () => { document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); });
}
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.endsWith(k));
    return Promise.resolve({ data: hit ? map[hit] : [] });
  });
}
/** Pop-up baku: kartu ber-role dialog + latar `${testId}-overlay` (FormModal/DetailModal), bukan .modal-card. */
function expectStdDialog(host, testId) {
  const card = q(host, testId);
  expect(card).not.toBeNull();
  expect(card.getAttribute("role")).toBe("dialog");
  expect(q(host, `${testId}-overlay`)).not.toBeNull();
  expect(host.querySelector(".modal-card")).toBeNull();
}
const realMatchMedia = window.matchMedia;
afterEach(() => {
  mockGet.mockReset(); mockPost.mockClear(); askConfirm.mockReset(); askConfirm.mockImplementation(async () => false);
  window.matchMedia = realMatchMedia;
  document.body.innerHTML = "";
});

const CB = { id: "cb1", number: "KSC/CB-00001", supplier_name: "Solo Weave", supplier_id: "s1", entity_id: "ent_ksc",
  bills: [{ bill_id: "b1", bill_number: "INV-1", applied_amount: 1000 }], totals: { bills_total: 1000, deductions_total: 0,
    net_payable: 1000, outstanding: 1000 }, payments: [] };
const META = { exception_actions: [{ action: "accept", label: "Terima", help: "?" }], reasons: [{ code: "r1", label: "Alasan 1" }],
  deduction_kinds: [{ kind: "other", label: "Lain-lain", help: "?", needs_ref: false, posts_gl: true }] };

test("Kontrabon: 4 pop-up keputusan = FormModal (dialog, Esc menutup), testid tombol lama tetap", async () => {
  routeGet({ "/bank-accounts": [], "/contra-bons/prepare": { credits: { purchase_returns: [], supplier_advances: [] } } });
  const cases = [
    ["cb-decision-modal", "cb-decision-save", (p) => <DecisionModal cb={CB} exception={{ key: "k", amount: 5 }} meta={META} {...p} />],
    ["cb-deduction-modal", "cb-deduction-save", (p) => <DeductionModal cb={CB} meta={META} {...p} />],
    ["cb-pay-modal", "cb-pay-submit", (p) => <PayModal cb={CB} {...p} />],
    ["cb-dispute-modal", "cb-dispute-submit", (p) => <ReasonNoteModal cb={CB} kind="dispute" meta={META} {...p} />],
  ];
  for (const [tid, submit, make] of cases) {
    const onClose = jest.fn();
    const { host, root } = await mount(make({ onClose, onSaved: jest.fn(), onPaid: jest.fn(), onDone: jest.fn() }));
    expectStdDialog(host, tid);
    expect(q(host, submit)).not.toBeNull();
    await esc();
    expect(onClose).toHaveBeenCalled();
    await act(async () => { root.unmount(); });
  }
  // Sengketa wajib alasan berlabel → tombol mati sebelum dipilih.
  const { host } = await mount(<ReasonNoteModal cb={CB} kind="dispute" meta={META} onClose={() => {}} onDone={() => {}} />);
  expect(q(host, "cb-dispute-submit").disabled).toBe(true);
});

test("Jurnal: Jurnal Manual = FormModal; rincian = DetailModal, Anulir minta konfirmasi & galatnya di dalam pop-up", async () => {
  routeGet({ "/finance/closing/status": { closed: false } });
  const { host } = await mount(<JournalEntryModal accounts={[]} onClose={() => {}} onSaved={() => {}} />);
  expectStdDialog(host, "je-modal");
  expect(q(host, "je-modal-close")).not.toBeNull();
  expect(q(host, "je-submit").disabled).toBe(true);            // jurnal kosong belum seimbang
  document.body.innerHTML = "";

  const je = { id: "j1", number: "JE-1", source_type: "manual", status: "posted", lines: [], total_debit: 0, total_credit: 0 };
  const onVoid = jest.fn(async () => { throw new Error("Periode sudah ditutup"); });
  const { host: h2 } = await mount(<JournalDetailModal je={je} sourceMeta={() => ({ label: "Manual", tone: "" })}
    onClose={() => {}} onVoid={onVoid} onReverse={async () => {}} />);
  expect(q(h2, "gl-journal-detail").getAttribute("role")).toBe("dialog");
  await click(q(h2, "gl-journal-void"));
  expect(askConfirm).toHaveBeenCalled();
  expect(onVoid).not.toHaveBeenCalled();                        // dibatalkan di dialog konfirmasi
  askConfirm.mockImplementation(async () => true);
  await click(q(h2, "gl-journal-void"));
  expect(onVoid).toHaveBeenCalled();
  expect(q(h2, "gl-journal-detail-error").textContent).toMatch(/Periode sudah ditutup/);
});

test("Store credit & Faktur Pajak: pop-up baku; saringan status Faktur = FilterChips", async () => {
  routeGet({ "/store-credit/open-orders": [] });
  const { host } = await mount(<RedeemModal row={{ customer_id: "c1", customer_name: "Bima", balance: 5000 }} onClose={() => {}} onDone={() => {}} />);
  expectStdDialog(host, "sc-redeem-modal");
  expect(q(host, "sc-redeem-submit").disabled).toBe(true);      // tidak ada pesanan piutang
  expect(q(host, "sc-redeem-no-orders")).not.toBeNull();
  document.body.innerHTML = "";
  const { host: h2 } = await mount(<ReverseModal entry={{ id: "e1", type: "adjust", amount: 10 }} typeLabel="Sesuai" onClose={() => {}} onDone={() => {}} />);
  expectStdDialog(h2, "sc-reverse-modal");
  expect(q(h2, "sc-reverse-submit").className).toMatch(/danger-button/);
  document.body.innerHTML = "";

  routeGet({ "/tax-invoices": [{ id: "f1", number: "FKT-1", order_number: "SO-1", status: "normal", nsfp: "" }] });
  const { host: h3 } = await mount(<TaxInvoices currentUser={{ role: "admin", permissions: { tax_invoice: ["*"] } }} />);
  expect(q(h3, "fkt-filter-all").getAttribute("aria-pressed")).toBe("true");
  expect(h3.querySelector(".tab-bar")).toBeNull();
  await click(q(h3, "fkt-cancel-f1"));
  expectStdDialog(h3, "fkt-modal");
  expect(q(h3, "fkt-modal-submit").className).toMatch(/danger-button/);
  await click(q(h3, "fkt-modal-submit"));                       // alasan kosong → galat DI DALAM pop-up
  expect(q(h3, "fkt-modal-error").textContent).toMatch(/Alasan pembatalan wajib/);
  expect(mockPost).not.toHaveBeenCalled();
});

test("Rekonsiliasi Bank: PageHeader, PageTabs, saringan status FilterChips, impor = pop-up", async () => {
  routeGet({
    "/bank-accounts": [{ id: "b1", name: "BCA Giro" }],
    "/bank-reconciliation/lines": [],
    "/bank-reconciliation/summary": { statement: { net: 0, lines: 0 }, book: { net: 0 }, matched: 0, unmatched_lines: 0,
      suggested: 0, holding: { balance: 0, count: 0 }, difference: 0, unmatched_book_txns: 0 },
    "/bank-reconciliation/holding": { items: [], balance: 0, count: 0 },
    "/bank-reconciliation/rules": [], "/bank-reconciliation/formats": [],
  });
  const { host } = await mount(<BankReconciliationView />);
  expect(q(host, "recon-head").classList.contains("view-header")).toBe(true);
  expect(q(host, "recon-tabs").getAttribute("role")).toBe("tablist");
  expect(q(host, "recon-tab-lines").getAttribute("aria-selected")).toBe("true");
  expect(q(host, "recon-filter-status-all").getAttribute("aria-pressed")).toBe("true");
  expect(q(host, "recon-filter-status-unmatched")).not.toBeNull();
  expect(q(host, "recon-import-panel")).toBeNull();
  await click(q(host, "recon-import-toggle"));
  expectStdDialog(host, "recon-import-panel");
  expect(q(host, "recon-raw")).not.toBeNull();
  await click(q(host, "recon-tab-holding"));
  expect(q(host, "recon-holding-panel")).not.toBeNull();
});

test("Rekonsiliasi: Bayar kontrabon dari mutasi minta konfirmasi dulu; mode cocokkan = chip", async () => {
  routeGet({ "/contra-bons/bank-line-candidates/l1": { candidates: [{ id: "cb1", number: "CB-1", supplier_name: "Solo", exact: true, outstanding: 10 }] },
    "/bank-reconciliation/lines/l1/candidates": { candidates: [], auto_min: 80, suggest_min: 60 } });
  const line = { id: "l1", amount: 10, direction: "out", stmt_date: "2026-10-20", description: "TRF" };
  const { host } = await mount(<ReconContraBonModal line={line} onClose={() => {}} onDone={() => {}} />);
  expectStdDialog(host, "recon-contrabon-modal");
  await click(q(host, "recon-cb-pay-cb1"));
  expect(askConfirm).toHaveBeenCalled();
  expect(mockPost).not.toHaveBeenCalled();
  document.body.innerHTML = "";
  const { host: h2 } = await mount(<ReconMatchModal line={line} onClose={() => {}} onDone={() => {}} />);
  expectStdDialog(h2, "recon-match-modal");
  expect(q(h2, "recon-mode-single").getAttribute("aria-pressed")).toBe("true");
  await click(q(h2, "recon-mode-split"));
  expect(q(h2, "recon-split-submit")).not.toBeNull();          // kaki pop-up muncul di mode pecah
});

test("Selisih bayar & denda: FormModal; Terbitkan denda minta konfirmasi", async () => {
  const { host } = await mount(<PaymentVarianceDialog assessment={{ delta: -50, funds: 950, expected: 1000, options: [] }}
    reasons={[]} onCancel={() => {}} onConfirm={() => {}} />);
  expectStdDialog(host, "payment-variance-dialog");
  expect(q(host, "pv-submit").disabled).toBe(true);
  document.body.innerHTML = "";
  routeGet({});
  const rows = [{ id: "p1", number: "PN-1", status: "draft", amount: 1000, due_date: "2026-10-01", days_late: 3 }];
  const { host: h2 } = await mount(<PenaltyPanel rows={rows} currentUser={{ role: "admin", permissions: { penalty: ["*"] } }} />);
  await click(q(h2, "penalty-issue-p1"));
  expect(askConfirm).toHaveBeenCalled();
  expect(mockPost).not.toHaveBeenCalled();
  await click(q(h2, "penalty-waive-p1"));
  expectStdDialog(h2, "penalty-dialog");
  expect(q(h2, "penalty-dialog-submit").disabled).toBe(true);   // alasan wajib
});

test("Kendaraan (dibuka dari HP): PageTabs + MetricRow + tabel baku; Catat Perjalanan = FormModal", async () => {
  routeGet({ "/vehicle-usage-logs": [{ id: "l1", number: "VL-1", tanggal: "2026-10-20", total: 1000, jarak_tempuh: 10 }],
    "/vehicles": [], "/vehicle-usage-logs/summary": { count: 1, grand_total: 1000, per_vehicle: [] } });
  const user = { role: "admin", permissions: { vehicle_log: ["*"] } };
  const { host } = await mount(<VehicleLogsView currentUser={user} />);
  expect(q(host, "veh-tabs").getAttribute("role")).toBe("tablist");
  expect(q(host, "veh-metrics").querySelectorAll(".metric-card").length).toBe(4);
  expect(q(host, "veh-log-row-l1")).not.toBeNull();
  expect(q(host, "veh-log-edit-l1")).not.toBeNull();
  await click(q(host, "veh-log-create-btn"));
  expectStdDialog(host, "veh-log-modal");
  expect(q(host, "veh-log-vehicle")).not.toBeNull();
  expect(q(host, "veh-log-pemakai")).not.toBeNull();           // isian HP = desktop (tidak diringkas)
  await click(q(host, "veh-tab-vehicles"));
  expect(q(host, "veh-empty")).not.toBeNull();
});

test("Dokumen: Pengaturan WA = FormModal + PageTabs; rincian rekaman & pratinjau = DetailModal", async () => {
  routeGet({ "/deliveries/whatsapp/settings": { provider: "simulated", simulate: true, enabled: false },
    "/pdf/doc-types": [], "/deliveries/whatsapp/rules": { rules: [] } });
  const { host } = await mount(<WhatsAppSettings open onClose={() => {}} />);
  expectStdDialog(host, "wa-settings-modal");
  expect(q(host, "wa-tab-settings").getAttribute("aria-selected")).toBe("true");
  expect(q(host, "wa-set-save")).not.toBeNull();
  await click(q(host, "wa-tab-rules"));
  expect(q(host, "wa-rules")).not.toBeNull();
  expect(q(host, "wa-set-save")).toBeNull();                   // kaki Simpan hanya di tab Koneksi
  await click(q(host, "wa-rule-add"));
  expectStdDialog(host, "wa-rule-form");
  document.body.innerHTML = "";

  const { host: h2 } = await mount(<RecordDetailModal open onClose={() => {}} title="Faktur INV-1" code="INV-1"
    itemColumns={[{ key: "a", label: "A" }]} items={[{ a: "x" }]} />);
  expect(q(h2, "record-detail-modal").getAttribute("role")).toBe("dialog");
  expect(q(h2, "record-detail-items").classList.contains("data-table")).toBe(true);
  document.body.innerHTML = "";

  mockGet.mockImplementation(() => Promise.resolve({ data: "<p>doc</p>" }));
  const { host: h3 } = await mount(<DocumentActionsBar docType="sales_order" sourceId="so1" label="SO" esignable={false}
    currentUser={{ role: "admin" }} autoCheckSignature={false} />);
  await click(q(h3, "doc-act-preview"));
  expect(q(h3, "doc-act-preview-modal").getAttribute("role")).toBe("dialog");
  expect(q(h3, "doc-act-preview-close")).not.toBeNull();
});

test("Kontrabon: PageHeader, PageTabs (cb-tab-*), saringan status = FilterChips berhitung", async () => {
  routeGet({ "/contra-bons/meta": META, "/contra-bons": [], "/contra-bons/status-counts": { draft: 2, paid: 1 },
    "/contra-bons/summary": { waiting_count: 0, scheduled_count: 0, due_soon_count: 0, disputed_count: 0, overdue_count: 0 } });
  const { host } = await mount(<ContraBonsView currentUser={{ role: "admin", permissions: { contra_bon: ["*"] } }}
    selectedEntity="all" entities={[]} />);
  expect(q(host, "cb-head").classList.contains("view-header")).toBe(true);
  expect(q(host, "cb-tab-list").getAttribute("aria-selected")).toBe("true");
  expect(q(host, "cb-filter-status-all").getAttribute("aria-pressed")).toBe("true");
  expect(q(host, "cb-filter-status-draft").textContent).toMatch(/2/);
  expect(q(host, "cb-filter-status-all").textContent).toMatch(/3/);
  await click(q(host, "cb-new"));
  expectStdDialog(host, "cb-create-wizard");
});

test("Kasus Keuangan (dibuka dari HP): PageHeader, chip jenis/status; di layar sempit rincian = DetailModal", async () => {
  window.matchMedia = () => ({ matches: true, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });
  const kasus = { id: "k1", number: "FC-1", status: "open", case_type: "double_payment", case_type_label: "Bayar ganda",
    amount: 0, actions: [], playbook: [], timeline: [], documents: [], evidence: [] };
  routeGet({ "/finance-cases": [kasus], "/finance-cases/stats": { open: 1, total: 1, by_status: { open: 1 },
    by_type: [{ case_type: "double_payment", label: "Bayar ganda", open: 1, total: 1 }] },
  "/finance-cases/policy": { approval_above: 0 } });
  const { host } = await mount(<FinanceCasesView currentUser={{ role: "admin", permissions: { finance_case: ["*"] } }}
    selectedEntity="all" entities={[]} />);
  expect(q(host, "case-head").classList.contains("view-header")).toBe(true);
  expect(q(host, "case-chip-double_payment").getAttribute("aria-pressed")).toBe("false");
  expect(q(host, "case-filter-status-open").textContent).toMatch(/1/);
  expect(q(host, "case-detail-empty")).toBeNull();              // tidak ada kolom samping di layar sempit
  await click(q(host, "case-row-k1"));
  expect(q(host, "case-detail-modal").getAttribute("role")).toBe("dialog");
  expect(q(host, "case-detail")).not.toBeNull();
});

test("Wizard kasus = FormModal; Koreksi & Amandemen tanpa tab tunggal, status = chip", async () => {
  const kasus = { id: "k1", number: "FC-1", case_type: "x", case_type_label: "X", amount: 0, playbook: ["Langkah"],
    actions: [{ code: "a1", label: "Aksi", effect: "e", produces: "p", needs: [] }] };
  const { host } = await mount(<CasePlaybookWizard caseData={kasus} reasons={[]} entities={[]} customers={[]}
    suppliers={[]} accounts={[]} policy={{ approval_above: 0 }} onClose={() => {}} onDone={() => {}} />);
  expectStdDialog(host, "case-wizard");
  expect(q(host, "case-wizard-submit")).not.toBeNull();
  document.body.innerHTML = "";

  routeGet({ "/amendments": [], "/amendments/stats/summary": { total: 4, pending_approval: 1, rejected: 0 } });
  const { host: h2 } = await mount(<AmendmentCenterView currentUser={{ role: "admin", permissions: { finance_amendment: ["*"] } }}
    selectedEntity="all" />);
  expect(q(h2, "amd-tab-daftar")).toBeNull();
  expect(q(h2, "amd-reasons-link")).not.toBeNull();
  expect(q(h2, "amd-filter-all").getAttribute("aria-pressed")).toBe("true");
  expect(q(h2, "amd-filter-pending_approval").textContent).toMatch(/1/);
  expect(q(h2, "amd-kpi-rejected").querySelector(".metric-zero")).not.toBeNull();   // nol netral
});

test("Pusat Export: PageHeader + PageTabs (export-tab-*)", async () => {
  routeGet({ "/export-center/datasets": { datasets: [], unavailable: [], comparators: {} } });
  const { host } = await mount(<ExportCenterView selectedEntity="all" />);
  expect(q(host, "export-head").classList.contains("view-header")).toBe(true);
  expect(q(host, "export-tabs").getAttribute("role")).toBe("tablist");
  expect(q(host, "export-tab-builder").getAttribute("aria-selected")).toBe("true");
  await click(q(host, "export-tab-jobs"));
  expect(q(host, "export-tab-jobs").getAttribute("aria-selected")).toBe("true");
});

test("Konsolidasi (G1-33): entri eliminasi basi → peringatan jumlah + total, tanpa tombol hapus; field tak ada → diam", async () => {
  const base = { entities: [], gross: {}, elimination: {}, consolidated: {}, balanced: true };
  routeGet({ "/finance/consolidation/summary": { ...base, eliminations_stale: [
    { id: "e1", name: "Auto G-6: Eliminasi antar-PT KSC/IC-00018", pair_id: "p1", ic_ar_eliminated: 11100, gl_entries_left: 0 },
    { id: "e2", name: "Eliminasi antar-PT CST/IC-00001", pair_id: "p2", ic_ar_eliminated: 6979014, gl_entries_left: 2 },
  ], eliminations_stale_count: 2 }, "/finance/consolidation/eliminations": [], "/gl/accounts": [] });
  const { host } = await mount(<GroupConsolidationView entities={[]} />);
  const box = q(host, "cons-stale-elims");
  expect(box).not.toBeNull();
  expect(box.textContent).toMatch(/2 entri eliminasi otomatis antar-PT sudah basi/);
  expect(q(host, "cons-stale-elims-total").textContent).toMatch(/6\.990\.114/);
  expect(q(host, "cons-stale-elims-split").textContent).toMatch(/1 entri tanpa jurnal.*Sinkron Antar-PT/);
  expect(q(host, "cons-stale-elims-split").textContent).toMatch(/1 entri jurnal transaksinya MASIH ada/);
  expect(q(host, "cons-stale-elims-list").textContent).not.toMatch(/Auto G-6/);   // kode fase dibersihkan
  expect(box.querySelector("button")).toBeNull();                                  // tanpa tombol hapus
  document.body.innerHTML = "";
  routeGet({ "/finance/consolidation/summary": base, "/finance/consolidation/eliminations": [], "/gl/accounts": [] });
  const { host: h2 } = await mount(<GroupConsolidationView entities={[]} />);
  expect(q(h2, "group-consolidation-view")).not.toBeNull();
  expect(q(h2, "cons-stale-elims")).toBeNull();
});
