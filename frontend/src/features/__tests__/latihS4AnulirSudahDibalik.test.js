// Pelatihan 18 Nov (uji S4 langkah 28): rincian jurnal manual yang SUDAH DIBALIK tidak boleh menampilkan [Anulir Jurnal]
// (server menolak "Jurnal sudah/sedang dibalik — tidak bisa dianulir lagi."); jurnal manual biasa tetap punya tombolnya.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import JournalDetailModal from "../finance/JournalDetailModal";

jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: () => Promise.resolve({ data: {} }), post: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } } },
  API: "/api",
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const JE = { id: "je_1", number: "KSC/JE-00290", source_type: "manual", status: "posted", date: "2026-11-18",
  entity_id: "ent_ksc", lines: [{ account_code: "6-3000", account_name: "Beban Utilitas", debit: 1000, credit: 0 },
    { account_code: "2-1900", account_name: "Kewajiban Lancar Lainnya", debit: 0, credit: 1000 }] };

async function tampil(je) {
  const host = document.createElement("div"); document.body.appendChild(host);
  await act(async () => { createRoot(host).render(<JournalDetailModal je={je} sourceMeta={() => ({ label: "Manual", color: "" })} onClose={() => {}} onVoid={() => {}} onReverse={() => {}} />); });
  return host;
}
afterEach(() => { document.body.innerHTML = ""; });

test("jurnal manual biasa: tombol Anulir dan Balik tampil", async () => {
  const h = await tampil(JE);
  expect(h.querySelector('[data-testid="gl-journal-void"]')).not.toBeNull();
  expect(h.querySelector('[data-testid="gl-journal-reverse"]')).not.toBeNull();
});

test("jurnal manual yang sudah dibalik: tanpa Anulir maupun Balik", async () => {
  const h = await tampil({ ...JE, reversed_by_entry_id: "je_2", reversed_by_entry_number: "KSC/JE-00291" });
  expect(h.querySelector('[data-testid="gl-journal-void"]')).toBeNull();
  expect(h.querySelector('[data-testid="gl-journal-reverse"]')).toBeNull();
});
