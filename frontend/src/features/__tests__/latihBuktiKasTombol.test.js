// Pelatihan Keuangan 18 Nov (F16) — rincian jurnal non-kas (mis. "Pendapatan Kirim") dulu tetap menampilkan
// [Bukti Kas Keluar] dan [Bukti Kas Masuk]. Bukti kas hanya untuk jurnal yang menyentuh akun kas/bank (1-11xx):
// kas masuk → Bukti Kas Masuk, kas keluar → Bukti Kas Keluar, arah campur → keduanya, tanpa kas → tidak ada.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import JournalDetailModal from "../finance/JournalDetailModal";

jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: () => Promise.resolve({ data: {} }), post: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => { createRoot(host).render(el); });
  for (let i = 0; i < 4; i += 1) { await act(async () => {}); }   // eslint-disable-line no-await-in-loop
}
afterEach(() => { document.body.innerHTML = ""; });

const je = (lines) => ({ id: "je_1", number: "KSC/JE-00001", source_type: "manual", status: "posted", date: "2026-11-17",
  description: "Uji", total_debit: 100, total_credit: 100, lines });
const L = (account_code, debit, credit) => ({ account_code, account_name: account_code, debit, credit });

test.each([
  ["pendapatan (tanpa kas)", [L("1-1200", 100, 0), L("4-1000", 0, 100)], false, false],
  ["kas masuk", [L("1-1100", 100, 0), L("1-1200", 0, 100)], false, true],
  ["kas keluar", [L("6-8000", 100, 0), L("1-1110", 0, 100)], true, false],
  ["pindah kas antar rekening", [L("1-1100", 100, 0), L("1-1110", 0, 100)], true, true],
])("%s → Bukti Kas Keluar %s, Bukti Kas Masuk %s", async (_n, lines, keluar, masuk) => {
  await mount(<JournalDetailModal je={je(lines)} sourceMeta={() => ({ label: "Manual", tone: "" })} onClose={() => {}} />);
  expect(q("gl-journal-detail")).not.toBeNull();
  expect(!!q("gl-print-payment-voucher")).toBe(keluar);
  expect(!!q("gl-print-received-voucher")).toBe(masuk);
});
