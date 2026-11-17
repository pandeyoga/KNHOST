// Uji peran kustom 18 Nov 2026 (agen A, perburuan cacat) — [Setujui kontrabon] mengikuti Aturan Persetujuan server.
//
// Langkah ulang di layar: peran kustom TANPA peran dasar yang izinnya disalin dari Finance (memegang `contra_bon.approve`)
// membuka kontrabon Terverifikasi → tombol [Setujui kontrabon] tampil → diklik → 403 "Persetujuan kontrabon … diputus oleh
// Admin, Manajer, Finance … Peran Anda belum tercantum di Aturan Persetujuan." Pintu server
// (`contra_bon_service.approve` → `approval_policy_service.can_decide("contra_bon_approve", …)`) memutus dari tabel
// Aturan Persetujuan; layar dulu hanya membaca izin. Kini layar menanyakan `GET /approval-policies/can-decide/me` (pola
// tagihan pemasok, KP-T4): tidak lolos → tombol tidak tampil, pesan server tampil sebagai petunjuk.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { AppNavProvider } from "../../context/AppNavContext";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), patch: () => Promise.resolve({ data: {} }),
    put: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../components/AskKnButton", () => ({ __esModule: true, AskKnButton: () => null, PENDING_KEY: "x" }));
jest.mock("../documents/DocumentActionsBar", () => () => null);
jest.mock("../documents/trace/DocRefsPanel", () => () => null);

/* eslint-disable import/first */
import ContraBonDetailPanel, { cbDecideParams } from "../purchasing/contrabon/ContraBonDetailPanel";
import BUILTIN from "../../config/__tests__/fixtures/access_builtin_fixture.json";
/* eslint-enable import/first */

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const ENT = [{ id: "ent_ksc", short_name: "Sukacita", legal_name: "PT Kain Suka Cita" }];
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 10) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(
      <AppNavProvider role="admin">
        <EntityScopeProvider selectedEntity="ent_ksc" entities={ENT} canSwitch>{el}<ConfirmHost /></EntityScopeProvider>
      </AppNavProvider>);
  });
  await flush();
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = []; document.body.innerHTML = "";
});

const TOLAK = "Persetujuan kontrabon senilai Rp1.287.600 pada jenjang 1 diputus oleh Admin, Manajer atau Finance. "
  + "Peran Anda belum tercantum di Aturan Persetujuan.";
let jawab = { allowed: false, message: TOLAK };
beforeEach(() => {
  jawab = { allowed: false, message: TOLAK };
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.includes("/approval-policies/can-decide/me") ? jawab : {} }));
});

const CB = (status) => ({ id: "cb1", number: "KSC/CB-1", status, status_label: status, supplier_name: "Pemasok S",
  entity_id: "ent_ksc", bills: [], deductions: [], decisions: [], payments: [], timeline: [],
  totals: { bills_total: 1287600, deductions_total: 0, net_payable: 1287600, paid_total: 0, outstanding: 1287600 } });
// Peran kustom tanpa peran dasar, izin = salinan Finance bawaan (memegang contra_bon.approve).
const KUSTOM = { id: "u_k", role: "cr_uji_salinan_finance", permissions: BUILTIN.permissions.finance };

test("Terverifikasi + Aturan Persetujuan menolak peran ini: tombol Setujui tidak tampil, pesan server jadi petunjuk", async () => {
  expect(KUSTOM.permissions.contra_bon).toContain("approve");
  await mount(<ContraBonDetailPanel cb={CB("verified")} meta={{}} currentUser={KUSTOM} onClose={() => {}} onChanged={() => {}} />);
  expect(q("cb-action-primary")).toBeNull();
  expect(q("cb-decide-hint").textContent).toBe(TOLAK);
  const call = mockGet.mock.calls.find(([u]) => u.includes("/approval-policies/can-decide/me"));
  expect(call[1].params).toMatchObject({ doc_kind: "contra_bon_approve", entity_id: "ent_ksc", amount: 1287600 });
});

test("Terverifikasi + Aturan Persetujuan meloloskan: tombol Setujui kontrabon tampil", async () => {
  jawab = { allowed: true, message: "" };
  await mount(<ContraBonDetailPanel cb={CB("verified")} meta={{}} currentUser={KUSTOM} onClose={() => {}} onChanged={() => {}} />);
  expect(q("cb-action-primary").textContent).toMatch(/Setujui kontrabon/);
  expect(q("cb-decide-hint")).toBeNull();
});

test("Langkah lain tidak bertanya ke Aturan Persetujuan (Dijadwalkan bayar → Catat pembayaran langsung)", async () => {
  await mount(<ContraBonDetailPanel cb={CB("scheduled_payment")} meta={{}} currentUser={KUSTOM} onClose={() => {}} onChanged={() => {}} />);
  expect(q("cb-action-primary").textContent).toMatch(/Catat pembayaran/);
  expect(mockGet.mock.calls.some(([u]) => u.includes("/approval-policies/can-decide/me"))).toBe(false);
  expect(cbDecideParams(CB("approved"))).toBeNull();
});
