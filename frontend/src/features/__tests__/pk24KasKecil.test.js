// PK-24 (SL-09, FY-14, FY-19, IA-05, K-17) — layar Kas Kecil (docs/blueprint/unit/PK-24.md, bagian Layar; padanan
// komponen U14). Dialog konfirmasi memakai `ConfirmHost` asli; pemilih (cmdk/radix) diganti isian polos.
//   L1  rincian LPJ bersisa terbuka: "Sisa Harus Dikembalikan Rp 200.000"; tombol Terima Pengembalian Sisa (izin
//       `cash_settlement.pay`) → pop-up Jenis kas · Rekening · Tanggal → konfirmasi "Terima Rp … dari … ke … · PT?"
//       → 1 POST …/return-remainder; sesudahnya "Sisa Dikembalikan · {nomor kas}".
//   L2  LPJ draf: Ubah/Ajukan/Unggah Bukti, TANPA Setujui; LPJ diajukan: Setujui/Tolak, tanpa Ubah & unggah.
//   L3  LPJ ditolak: pembuatnya → "Perbaiki & Ajukan Lagi" (POST …/reopen lalu form ubah); orang lain → alasan tertulis.
//   L4  ringkasan: sebelum disetujui "Sisa Uang Muka", lebih bayar "Kekurangan Dana" (bukan "Sisa Dikembalikan").
//   L5  Hutang Reimburse: tombol Bayar per baris hanya untuk `cash_settlement.pay`; membuka pop-up yang sama.
//   L6  form LPJ: Periode = pilihan bulan (bawaan bulan ini); mode ubah = PATCH; "Simpan & Ajukan Lagi" = PATCH + submit.
//   L7  cairkan PD: sesudah pop-up, konfirmasi menyebut nominal & PT sebelum POST.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import SettlementDetail from "../pettycash/SettlementDetail";
import SettlementForm from "../pettycash/SettlementForm";
import ReimbursePayablesView from "../pettycash/ReimbursePayablesView";
import CashAdvanceDetail from "../pettycash/CashAdvanceDetail";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockPatch = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: (...a) => mockPatch(...a),
    delete: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => <select data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />;
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />,
  formatDateId: (v) => String(v || ""),
}));
jest.mock("../../components/KNMonthPicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} data-kind="month" value={p.value || ""} placeholder={p.placeholder}
    onChange={(e) => p.onChange(e.target.value)} />,
  formatPeriodId: (v) => `bulan:${v}`,
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const ENTS = [{ id: "ent_ksc", legal_name: "PT Kain Suka Cita", short_name: "Sukacita" }];
const REK = [{ id: "rek_k", name: "Kas Kecil KSC", entity_id: "ent_ksc", account_type: "cash", cash_type: "kas_kecil", is_active: true },
  { id: "rek_b", name: "BCA Operasional", bank_name: "BCA", account_number: "123", entity_id: "ent_ksc", account_type: "bank",
    cash_type: "kas_besar", is_active: true }];
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(<EntityScopeProvider selectedEntity="ent_ksc" entities={ENTS}>{el}<ConfirmHost /></EntityScopeProvider>);
  });
  await flush();
  return host;
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
async function ketik(el, value) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new Event("input", { bubbles: true })); });
  await flush();
}
const dialogTitle = (testId) => q(testId)?.querySelector("[role=dialog]")?.getAttribute("aria-label");
beforeEach(() => {
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/bank-accounts") ? REK : [] }));
  mockPost.mockResolvedValue({ data: {} });
  mockPatch.mockResolvedValue({ data: {} });
});
afterEach(async () => {
  const openCancel = document.body.querySelector(".modal-overlay [data-testid$='-cancel']");
  if (openCancel) await click(openCancel);
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockReset(); mockPost.mockReset(); mockPatch.mockReset();
  document.body.innerHTML = "";
});

const FIN = { id: "usr_fin", name: "Fina", role: "finance", permissions: { cash_settlement: ["view", "pay"], cash_advance: ["view", "disburse"] } };
const STAF = { id: "usr_sari", name: "Sari", role: "sales", permissions: { cash_settlement: ["view", "create", "update", "submit"] } };
const MGR = { id: "usr_mgr", name: "Manajer", role: "manager", permissions: { cash_settlement: ["view", "update", "approve", "reject"] } };
const lpj = (over = {}) => ({
  id: "stl1", number: "STL-0001", status: "posted_to_gl", entity_id: "ent_ksc", dibuat_oleh: "Sari", created_by: "Sari",
  created_by_id: "usr_sari", cash_advance_id: "ca1", cash_advance_number: "PD-0001", total_pengeluaran: 800000, total_pettycash: 1000000,
  sisa_kurang_dana: 200000, periode: "2026-11", expense_lines: [], attachments: [],
  sisa_dikembalikan: { amount: 200000, status: "open" }, hutang_reimburse: { amount: 0, status: "none" }, ...over,
});
const mountLpj = (stl, user, extra = {}) => mount(
  <SettlementDetail stl={stl} currentUser={user} entities={ENTS} catLabels={{}} onChanged={extra.onChanged || jest.fn()}
    onEdit={extra.onEdit || jest.fn()} flash={() => {}} />);

describe("L1 — terima pengembalian sisa", () => {
  test("ringkasan, pop-up baku, konfirmasi, satu POST; sesudahnya Sisa Dikembalikan · nomor kas", async () => {
    const onChanged = jest.fn();
    mockPost.mockResolvedValue({ data: lpj({ sisa_dikembalikan: { amount: 200000, status: "returned", cash_txn_number: "KAS-0007" } }) });
    await mountLpj(lpj(), FIN, { onChanged });
    expect(q("stl-detail-sisa-label").textContent).toBe("Sisa Harus Dikembalikan");
    expect(q("stl-detail-sisa").textContent).toContain("200.000");
    expect(q("stl-return-btn").textContent).toContain("Terima Pengembalian Sisa Rp 200.000");
    await click(q("stl-return-btn"));
    expect(mockPost).not.toHaveBeenCalled();
    expect(q("stl-return-modal-cashtype")).not.toBeNull();
    expect(q("stl-return-modal-account")).not.toBeNull();
    expect(q("stl-return-modal-date")).not.toBeNull();
    await click(q("stl-return-modal-submit"));
    expect(mockPost).not.toHaveBeenCalled();
    expect(dialogTitle("stl-return-confirm")).toBe("Terima Rp 200.000 dari Sari ke Kas Kecil KSC · PT Kain Suka Cita?");
    await click(q("stl-return-confirm-confirm"));
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe("/api/cash-advance-settlements/stl1/return-remainder");
    expect(mockPost.mock.calls[0][1]).toEqual(expect.objectContaining({ cash_type: "kas_kecil", account_id: "rek_k" }));
    expect(mockPost.mock.calls[0][2]?.headers?.["Idempotency-Key"]).toBeTruthy();
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  test("sesudah dikembalikan: label memuat nomor kas; tombol hilang", async () => {
    await mountLpj(lpj({ sisa_dikembalikan: { amount: 200000, status: "returned", cash_txn_number: "KAS-0007" } }), FIN);
    expect(q("stl-detail-sisa-label").textContent).toBe("Sisa Dikembalikan · KAS-0007");
    expect(q("stl-return-btn")).toBeNull();
  });

  test("tanpa izin bayar: tidak ada tombol, alasan tertulis di bilah", async () => {
    await mountLpj(lpj(), MGR);
    expect(q("stl-return-btn")).toBeNull();
    expect(q("stl-remainder-bar").textContent).toContain("pemegang izin bayar kas kecil");
  });
});

describe("L2 — LPJ terkunci sesudah diajukan", () => {
  test("draf: Ubah, Ajukan, Unggah Bukti; tanpa Setujui", async () => {
    const u = { ...STAF, permissions: { cash_settlement: ["view", "update", "submit", "approve"] } };
    await mountLpj(lpj({ status: "draft", sisa_dikembalikan: undefined }), u);
    expect(q("stl-edit-btn")).not.toBeNull();
    expect(q("stl-submit-btn")).not.toBeNull();
    expect(q("stl-attach-btn")).not.toBeNull();
    expect(q("stl-approve-btn")).toBeNull();
  });
  test("diajukan: Setujui & Tolak; tanpa Ubah & unggah", async () => {
    await mountLpj(lpj({ status: "submitted", sisa_dikembalikan: undefined }), MGR);
    expect(q("stl-approve-btn")).not.toBeNull();
    expect(q("stl-reject-btn")).not.toBeNull();
    expect(q("stl-edit-btn")).toBeNull();
    expect(q("stl-attach-btn")).toBeNull();
  });
});

describe("L3 — perbaiki & ajukan lagi", () => {
  test("pembuat: POST reopen lalu form ubah (ajukan lagi)", async () => {
    const onEdit = jest.fn();
    mockPost.mockResolvedValue({ data: lpj({ status: "draft" }) });
    await mountLpj(lpj({ status: "rejected", rejected_reason: "nota buram", sisa_dikembalikan: undefined }), STAF, { onEdit });
    expect(q("stl-rejected-reason").textContent).toContain("nota buram");
    await click(q("stl-reopen-btn"));
    expect(mockPost.mock.calls[0][0]).toBe("/api/cash-advance-settlements/stl1/reopen");
    expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({ status: "draft" }), { resubmit: true });
  });
  test("bukan pembuat: tanpa tombol, alasan tertulis", async () => {
    await mountLpj(lpj({ status: "rejected", sisa_dikembalikan: undefined }), MGR);
    expect(q("stl-reopen-btn")).toBeNull();
    expect(q("stl-reopen-hint").textContent).toContain("Pembuat LPJ (Sari)");
  });
});

describe("L4 — ringkasan sisa mengikuti keadaan", () => {
  test("diajukan bersisa → Sisa Uang Muka; lebih bayar → Kekurangan Dana", async () => {
    await mountLpj(lpj({ status: "submitted", sisa_dikembalikan: undefined }), MGR);
    expect(q("stl-detail-sisa-label").textContent).toBe("Sisa Uang Muka");
    for (const r of roots) await act(async () => { r.unmount(); });
    roots = []; document.body.innerHTML = "";
    await mountLpj(lpj({ sisa_kurang_dana: -150000, sisa_dikembalikan: { amount: 0, status: "none" },
      hutang_reimburse: { amount: 150000, status: "open" } }), FIN);
    expect(q("stl-detail-sisa-label").textContent).toBe("Kekurangan Dana");
    expect(q("stl-pay-reimburse-btn").textContent).toContain("Bayar Reimburse Rp 150.000");
  });
});

describe("L5 — Hutang Reimburse: Bayar per baris", () => {
  const DATA = { total_outstanding: 150000, aging: { "0-7": 150000 }, buckets: ["0-7", "8-14", "15-30", ">30"],
    by_employee: [{ employee: "Sari", outstanding: 150000, count: 1, oldest_days: 2, aging: { "0-7": 150000 } }],
    items: [{ id: "stl9", number: "STL-0009", employee: "Sari", cash_advance_number: "PD-9", entity_id: "ent_ksc",
      approved_at: "2026-11-12", amount: 150000, days: 2, bucket: "0-7" }] };
  test("pemegang izin bayar: tombol Bayar → pop-up yang sama dengan rincian LPJ", async () => {
    mockGet.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/reimburse-payables") ? DATA
      : url.endsWith("/bank-accounts") ? REK : [] }));
    await mount(<ReimbursePayablesView currentUser={FIN} selectedEntity="ent_ksc" entities={ENTS} />);
    expect(q("rp-search")).not.toBeNull();
    await click(q("rp-pay-stl9"));
    expect(q("stl-reimburse-modal")).not.toBeNull();
    expect(q("stl-reimburse-modal-account")).not.toBeNull();
  });
  test("tanpa izin bayar: tidak ada tombol Bayar", async () => {
    mockGet.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/reimburse-payables") ? DATA : [] }));
    await mount(<ReimbursePayablesView currentUser={MGR} selectedEntity="ent_ksc" entities={ENTS} />);
    expect(q("rp-item-stl9")).not.toBeNull();
    expect(q("rp-pay-stl9")).toBeNull();
  });
});

describe("L6 — form LPJ", () => {
  test("Periode = pilihan bulan, bawaan bulan ini", async () => {
    await mount(<SettlementForm categories={[]} selectedEntity="ent_ksc" onCancel={() => {}} onSaved={() => {}} />);
    const el = q("stl-periode");
    expect(el.getAttribute("data-kind")).toBe("month");
    expect(el.value).toMatch(/^\d{4}-\d{2}$/);
  });
  test("ubah draf = PATCH; Simpan & Ajukan Lagi = PATCH lalu POST submit", async () => {
    const onSaved = jest.fn();
    const rec = lpj({ status: "draft", periode: "Juli 2026", last_rejected_reason: "nota buram",
      expense_lines: [{ date: "2026-11-10", description: "bensin", category: "transportasi", amount: 300000 }] });
    mockPatch.mockResolvedValue({ data: rec });
    mockPost.mockResolvedValue({ data: { ...rec, status: "submitted" } });
    await mount(<SettlementForm categories={[]} selectedEntity="ent_ksc" record={rec} resubmit onCancel={() => {}} onSaved={onSaved} />);
    expect(q("stl-form-rejected").textContent).toContain("nota buram");
    expect(q("stl-periode").getAttribute("placeholder")).toContain("Juli 2026");
    expect(q("stl-submit").textContent).toBe("Simpan & Ajukan Lagi");
    await ketik(q("stl-periode"), "2026-07");
    await click(q("stl-submit"));
    expect(mockPatch).toHaveBeenCalledTimes(1);
    expect(mockPatch.mock.calls[0][0]).toBe("/api/cash-advance-settlements/stl1");
    expect(mockPatch.mock.calls[0][1]).toEqual(expect.objectContaining({ periode: "2026-07" }));
    expect(mockPost.mock.calls[0][0]).toBe("/api/cash-advance-settlements/stl1/submit");
    expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ status: "submitted" }));
  });
});

describe("L7 — cairkan PD: konfirmasi nominal & PT", () => {
  test("pop-up → konfirmasi → satu POST disburse", async () => {
    const ca = { id: "ca1", number: "PD-0003", status: "approved", entity_id: "ent_ksc", total_amount: 500000,
      lines: [], approvals: [], created_by: "Sari" };
    mockPost.mockResolvedValue({ data: { ...ca, status: "disbursed" } });
    await mount(<CashAdvanceDetail ca={ca} currentUser={FIN} entities={ENTS} onEdit={() => {}} onChanged={() => {}} flash={() => {}} />);
    await click(q("ca-disburse-btn"));
    await click(q("ca-disburse-confirm"));
    expect(mockPost).not.toHaveBeenCalled();
    const msg = q("ca-disburse-money-confirm-message");
    expect(msg.textContent).toContain("Rp 500.000");
    expect(msg.textContent).toContain("PT Kain Suka Cita");
    await click(q("ca-disburse-money-confirm-confirm"));
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe("/api/cash-advances/ca1/disburse");
    expect(mockPost.mock.calls[0][1]).toEqual(expect.objectContaining({ cash_type: "kas_kecil", account_id: "rek_k" }));
  });
});
