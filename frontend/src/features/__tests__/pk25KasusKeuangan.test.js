// PK-25 (FX-09, FX-11) — layar Kasus Keuangan & Pinjaman Antar-PT.
//  · Rincian kasus yang penyelesaiannya tersimpan tetapi jurnalnya gagal: pita "Penyelesaian tersimpan, tetapi jurnalnya
//    gagal: {galat}. Perbaiki penyebabnya lalu ulangi dari Posting Gagal.", lencana jurnal gagal, tombol selesaikan dan
//    tutup-tanpa-tindakan mati dengan alasan tertulis di sampingnya.
//  · Kasus selesai berjurnal: lencana "Jurnal terbit"; dokumen turunan antar-PT tampil sebagai tautan
//    "Dokumen antar-PT {nomor}" yang membuka tab Pinjaman Antar-PT pada dokumennya.
//  · Pinjaman Antar-PT: dokumen `kind="salah_transfer"` berlencana "Titipan salah transfer" + tautan ke kasusnya;
//    tombol Cairkan tidak tampil (sudah dicairkan), tombol Angsur tetap.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CaseDetailPanel from "../finance/cases/CaseDetailPanel";
import IntercoLoansPanel from "../finance/interco/IntercoLoansPanel";
import { AppNavProvider } from "../../context/AppNavContext";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), patch: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid }) => (
    <select data-testid={tid} value={value ?? ""} onChange={(e) => onValueChange(e.target.value)}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: M, KNSelect: M };
});
jest.mock("../../components/KNDatePicker", () => () => null);
jest.mock("../../config/roles", () => ({ __esModule: true, canCurrent: () => true }));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  return host;
}

afterEach(() => { document.body.innerHTML = ""; mockGet.mockReset(); });

const DASAR = {
  id: "fcs_1", number: "KSC/CASE-00001", status: "open", case_type: "selisih_biaya_bank",
  case_type_label: "Nominal kurang karena biaya bank", title: "Biaya bank", amount: 6500, sla_hours: 24, age_hours: 1,
  playbook: [], documents: [], attachments: [], timeline: [], refs: [], reason_codes: [],
};
const props = { reasons: [], canResolve: true, onClose() {}, onChanged() {}, onOpenWizard: jest.fn(), onError() {},
  onNotify() {} };

test("PK-25 jurnal gagal: pita, lencana, dan tombol selesaikan mati beralasan", async () => {
  const c = { ...DASAR, gl_status: "failed", gl_error: "Akun 6-8000 nonaktif",
    resolution_intent: { status: "pending", action: "bebankan_biaya_bank" } };
  const host = await mount(<CaseDetailPanel caseData={c} {...props} />);
  const pita = host.querySelector('[data-testid="case-journal-failed"]');
  expect(pita).not.toBeNull();
  expect(pita.textContent).toContain("Penyelesaian tersimpan, tetapi jurnalnya gagal: Akun 6-8000 nonaktif. "
    + "Perbaiki penyebabnya lalu ulangi dari Posting Gagal.");
  expect(host.querySelector('[data-testid="case-journal"]').getAttribute("data-status")).toBe("failed");
  expect(host.querySelector('[data-testid="case-open-wizard"]').disabled).toBe(true);
  expect(host.querySelector('[data-testid="case-reject-toggle"]').disabled).toBe(true);
  expect(host.querySelector('[data-testid="case-resolve-locked"]').textContent)
    .toBe("Penyelesaian sebelumnya belum tuntas — lanjutkan dari Posting Gagal.");
});

test("PK-25 kasus terbuka tanpa niat: tombol aktif, tanpa pita", async () => {
  const host = await mount(<CaseDetailPanel caseData={DASAR} {...props} />);
  expect(host.querySelector('[data-testid="case-journal-failed"]')).toBeNull();
  expect(host.querySelector('[data-testid="case-open-wizard"]').disabled).toBe(false);
  expect(host.querySelector('[data-testid="case-resolve-locked"]')).toBeNull();
});

test("PK-25 kasus salah PT selesai: lencana jurnal terbit + tautan dokumen antar-PT", async () => {
  const buka = jest.fn();
  const c = { ...DASAR, case_type: "salah_entitas", status: "resolved", gl_status: "posted", journal_entry_id: "je_1",
    documents: [
      { kind: "journal_entry", id: "je_1", number: "KND/JE-1", label: "Jurnal PT penerima" },
      { kind: "interco_loan", id: "icl_case_fcs_1_b", number: "KND/ICL-00007", label: "Dokumen antar-PT" }] };
  const host = await mount(
    <AppNavProvider onOpenDocument={buka}><CaseDetailPanel caseData={c} {...props} /></AppNavProvider>);
  expect(host.querySelector('[data-testid="case-journal"]').getAttribute("data-status")).toBe("posted");
  const tautan = host.querySelector('[data-testid="case-doc-interco-icl_case_fcs_1_b"]');
  expect(tautan.textContent).toContain("Dokumen antar-PT KND/ICL-00007");
  await act(async () => { tautan.click(); });
  expect(buka).toHaveBeenCalledWith(expect.objectContaining({ view: "interco-transactions", tab: "loans",
    focus_type: "interco_loan", focus_id: "icl_case_fcs_1_b" }));
});

test("PK-25 pinjaman antar-PT: dokumen salah transfer berlencana dan menaut ke kasus", async () => {
  const salah = { id: "icl_case_fcs_1_l", number: "KSC/ICL-00003", role: "lender", kind: "salah_transfer",
    status: "disbursed", principal: 2000000, outstanding: 2000000, borrower_entity_name: "PT Kanda",
    lender_entity_name: "PT KSC", purpose: "Pelanggan membayar ke PT yang salah — kasus KND/CASE-00001",
    origin: { kind: "finance_case", id: "fcs_1", number: "KND/CASE-00001" } };
  const biasa = { id: "icl_2", number: "KSC/ICL-00004", role: "lender", status: "draft", principal: 100,
    outstanding: 100, borrower_entity_name: "PT Kanda", lender_entity_name: "PT KSC", purpose: "modal kerja" };
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/meta")
    ? { statuses: [{ id: "disbursed", label: "Sudah dicairkan" }, { id: "draft", label: "Draf (belum dicairkan)" }],
      kinds: [{ id: "pinjaman", label: "Pinjaman antar-PT" }, { id: "salah_transfer", label: "Titipan salah transfer" }] }
    : { items: [salah, biasa], summary: {} } }));
  const kejadian = [];
  const dengar = (e) => kejadian.push(e.detail);
  window.addEventListener("kn-open-finance-case", dengar);
  const host = await mount(<IntercoLoansPanel entities={[]} entityId="ent_ksc" canWrite />);
  const lencana = host.querySelector('[data-testid="loan-kind-icl_case_fcs_1_l"]');
  expect(lencana.textContent).toContain("Titipan salah transfer");
  expect(lencana.querySelector("svg")).not.toBeNull();                               // ikon + teks + warna
  expect(host.querySelector('[data-testid="loan-kind-icl_2"]')).toBeNull();
  expect(host.querySelector('[data-testid="loan-status-icl_case_fcs_1_l"]').textContent).toBe("Sudah dicairkan");
  expect(host.querySelector('[data-testid="loan-disburse-icl_case_fcs_1_l"]')).toBeNull();
  expect(host.querySelector('[data-testid="loan-repay-icl_case_fcs_1_l"]')).not.toBeNull();
  expect(host.querySelector('[data-testid="loan-disburse-icl_2"]')).not.toBeNull();
  await act(async () => { host.querySelector('[data-testid="loan-case-icl_case_fcs_1_l"]').click(); });
  window.removeEventListener("kn-open-finance-case", dengar);
  expect(kejadian).toEqual([expect.objectContaining({ caseId: "fcs_1", number: "KND/CASE-00001" })]);
});
