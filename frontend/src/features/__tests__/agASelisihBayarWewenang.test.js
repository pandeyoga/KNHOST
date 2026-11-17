// Uji peran kustom 18 Nov 2026 (agen A, perburuan cacat) — keputusan selisih bayar "Hapus sisa" / "Kembalikan dana".
//
// Dulu: pilihan ber-`requires_role` menampilkan id peran mentah ("WAJIB MANAGER", "hanya bisa disimpan oleh manager /
// admin" — §3 Z6) padahal sejak KP-T4 yang memutus adalah Aturan Persetujuan `payment_variance.hapus_sisa` (bawaan: Admin,
// Manajer, Finance, dan peran kustom ber-dasar keduanya). Peran kustom tanpa peran dasar yang memegang
// `payment_variance.decide` bisa memilih "Hapus sisa" lalu ditolak server ("… Peran Anda belum tercantum di Aturan
// Persetujuan"). Kini layar bertanya `GET /approval-policies/can-decide/me` dan menonaktifkan pilihan dengan kalimat server.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import PaymentVarianceDialog from "../finance/payments/PaymentVarianceDialog";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../../components/KNSelect", () => (p) => <select data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />);
jest.mock("@/components/KNDatePicker", () => () => null);
jest.mock("../../components/MoneyInput", () => () => null);
jest.mock("../../components/CashAccountField", () => ({ __esModule: true, default: () => null,
  cashAccountBlocked: () => false, cashAccountBlockReason: () => "" }));
jest.mock("../../config/paymentMethods", () => ({ __esModule: true, canonicalMethod: (m, d) => m || d,
  usePaymentMethods: () => ({ methods: [] }) }));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  for (let i = 0; i < 6; i += 1) await act(async () => {});
  return host;
}
afterEach(() => { document.body.innerHTML = ""; mockGet.mockReset(); });

const TOLAK = "Selisih pembayaran — hapus sisa / refund senilai Rp50.000 pada jenjang 1 diputus oleh Admin, Manajer atau "
  + "Finance. Peran Anda belum tercantum di Aturan Persetujuan.";
const ASSESS = { delta: -50000, funds: 950000, expected: 1000000, entity_id: "ent_ksc", direction: "under", options: [
  { value: "outstanding", label: "Biarkan sisa ditagih", help: "h", impact: "i", available: true, requires_role: "" },
  { value: "writeoff", label: "Hapus sisa", help: "h", impact: "i", available: true, default: true, requires_role: "manager",
    max_amount: 1000000, needs_second_person_above: 1000000 },
] };
const jawab = (data) => mockGet.mockImplementation((url) => Promise.resolve({
  data: url.includes("/approval-policies/can-decide/me") ? data : {} }));

test("tanpa wewenang (Aturan Persetujuan menolak): Hapus sisa nonaktif + kalimat server, tanpa id peran mentah", async () => {
  jawab({ allowed: false, code: "batas", message: TOLAK, who: ["Admin", "Manajer", "Finance"] });
  const host = await mount(<PaymentVarianceDialog assessment={ASSESS} reasons={[]} onCancel={() => {}} onConfirm={() => {}} />);
  expect(q("pv-option-writeoff").disabled).toBe(true);
  expect(q("pv-option-wewenang-writeoff").textContent).toBe(TOLAK);
  expect(q("pv-option-outstanding").getAttribute("data-selected")).toBe("1");   // bawaan pindah ke pilihan yang boleh
  expect(host.textContent).not.toMatch(/\bmanager\b/i);
  const call = mockGet.mock.calls.find(([u]) => u.includes("/approval-policies/can-decide/me"));
  expect(call[1].params).toMatchObject({ doc_kind: "payment_variance.hapus_sisa", entity_id: "ent_ksc", amount: 50000 });
});

test("berwenang: Hapus sisa tetap bisa dipilih; label tanpa id peran mentah", async () => {
  jawab({ allowed: true, code: "", message: "" });
  const host = await mount(<PaymentVarianceDialog assessment={ASSESS} reasons={[]} onCancel={() => {}} onConfirm={() => {}} />);
  expect(q("pv-option-writeoff").disabled).toBe(false);
  expect(q("pv-option-writeoff").getAttribute("data-selected")).toBe("1");
  expect(host.textContent).not.toMatch(/\bmanager\b/i);
  expect(host.textContent).toMatch(/perlu wewenang/i);
});
