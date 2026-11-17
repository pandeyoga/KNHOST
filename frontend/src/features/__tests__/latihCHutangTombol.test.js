// Pelatihan keuangan 18 Nov 2026 — temuan uji jalan bagian C (docs/pelatihan/2026-11-18_keuangan/uji/F11, F12):
//  · F11 — tombol Kirim/Batalkan tagihan pemasok hanya untuk `vendor_bill.update` (Finance = lihat & bayar, K-17: dulu
//    tombol Batalkan tampil lalu ditolak 403 di server).
//  · F15 — nominal setoran BPJS/PPh 21 dibaca seperti isian rupiah lain (koma desimal, titik ribuan).
//  · F12 — rincian kontrabon untuk pemegang izin bayar tanpa izin ubah (Finance) tidak lagi berbunyi "hanya bisa memantau
//    … keputusan atas uang ada di Keuangan"; ia diberi tahu langkah berikutnya & kapan bisa membayar.
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
jest.mock("../purchasing/GrnDocVariance", () => () => null);

/* eslint-disable import/first */
import VendorBillDetailPanel from "../purchasing/VendorBillDetailPanel";
import ContraBonDetailPanel from "../purchasing/contrabon/ContraBonDetailPanel";
import { galatForm } from "../hr/PayrollRemittancesView";
import { can } from "../../config/roles";
import BUILTIN from "../../config/__tests__/fixtures/access_builtin_fixture.json";
/* eslint-enable import/first */

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const ENT = [{ id: "ent_ksc", short_name: "Sukacita", legal_name: "PT Kain Suka Cita" }];
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 8) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
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
beforeEach(() => { mockGet.mockImplementation(() => Promise.resolve({ data: {} })); });

const BILL = (status) => ({ id: "vb1", bill_number: "VB-1", supplier_name: "Pemasok S", entity_id: "ent_ksc", status, items: [],
  financials: { grand_total: 7000000, outstanding: 7000000, amount_paid: 0 }, timeline: [], match_status: "matched" });

test.each(Object.keys(BUILTIN.permissions))("F11 — tagihan pemasok, peran bawaan %s: Kirim/Batalkan = vendor_bill.update", async (role) => {
  const perms = BUILTIN.permissions[role];
  const user = { id: `u_${role}`, role, permissions: perms };
  const boleh = can(perms, "vendor_bill", "update");
  await mount(<VendorBillDetailPanel bill={BILL("posted")} canApprove={false} currentUser={user} onClose={() => {}} onAction={() => {}} />);
  const posted = Boolean(q("vb-action-cancel-posted"));
  const bayar = Boolean(q("vb-action-pay"));
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = []; document.body.innerHTML = "";
  await mount(<VendorBillDetailPanel bill={BILL("draft")} canApprove={false} currentUser={user} onClose={() => {}} onAction={() => {}} />);
  expect({ posted, draftCancel: Boolean(q("vb-action-cancel")), draftSubmit: Boolean(q("vb-action-submit")), bayar })
    .toEqual({ posted: boleh, draftCancel: boleh, draftSubmit: boleh, bayar: can(perms, "vendor_bill", "pay") });
});

const CB = (status) => ({ id: "cb1", number: "KSC/CB-1", status, status_label: status, supplier_name: "Pemasok S",
  entity_id: "ent_ksc", bills: [], deductions: [], decisions: [], payments: [], timeline: [],
  totals: { bills_total: 100, deductions_total: 0, net_payable: 100, paid_total: 0, outstanding: 100 } });

// K-FIN-01 (pemilik 17 Nov 2026 malam) — Finance bawaan kini memegang izin kontrabon Manajer (ubah, verifikasi, setujui).
// Teks "langkah berikutnya" untuk pemegang lihat + bayar saja diuji dengan izin bentuk PK-38 (`contra_bon: view, pay`).
const FIN_LIHAT_BAYAR = { ...BUILTIN.permissions.finance, contra_bon: ["view", "pay"] };

test("K-FIN-01 — Finance bawaan di kontrabon Disetujui: aksi utama sama dengan Manajer", async () => {
  const aksi = async (role) => {
    await mount(<ContraBonDetailPanel cb={CB("approved")} meta={{}} currentUser={{ id: `u_${role}`, role,
      permissions: BUILTIN.permissions[role] }} onClose={() => {}} onChanged={() => {}} />);
    const out = { utama: q("cb-action-primary")?.textContent || null, bacaSaja: Boolean(q("cb-detail-readonly")) };
    for (const r of roots) await act(async () => { r.unmount(); });
    roots = []; document.body.innerHTML = "";
    return out;
  };
  const mgr = await aksi("manager");
  expect(mgr.utama).not.toBeNull();
  expect(await aksi("finance")).toEqual(mgr);
});

test("F12 — pemegang lihat + bayar (bentuk PK-38) di kontrabon Disetujui: langkah berikutnya milik Manajer, bukan 'hanya bisa memantau'", async () => {
  const fin = { id: "u_fin", role: "finance", permissions: FIN_LIHAT_BAYAR };
  await mount(<ContraBonDetailPanel cb={CB("approved")} meta={{}} currentUser={fin} onClose={() => {}} onChanged={() => {}} />);
  const t = q("cb-detail-readonly").textContent;
  expect(t).toMatch(/Langkah berikutnya — Jadwalkan pembayaran/);
  expect(t).toMatch(/Dijadwalkan bayar/);
  expect(t).not.toMatch(/hanya bisa memantau/);
  expect(q("cb-action-primary")).toBeNull();
});

test("F12 — pemegang lihat + bayar di kontrabon Dijadwalkan bayar: tombol Catat pembayaran, tanpa teks hanya-baca", async () => {
  const fin = { id: "u_fin", role: "finance", permissions: FIN_LIHAT_BAYAR };
  await mount(<ContraBonDetailPanel cb={CB("scheduled_payment")} meta={{}} currentUser={fin} onClose={() => {}} onChanged={() => {}} />);
  expect(q("cb-action-primary").textContent).toMatch(/Catat pembayaran/);
  expect(q("cb-detail-readonly")).toBeNull();
});

test("F12 — Gudang (lihat saja) tetap membaca teks pemantau", async () => {
  const wh = { id: "u_wh", role: "warehouse", permissions: BUILTIN.permissions.warehouse };
  await mount(<ContraBonDetailPanel cb={CB("approved")} meta={{}} currentUser={wh} onClose={() => {}} onChanged={() => {}} />);
  expect(q("cb-detail-readonly").textContent).toMatch(/hanya bisa memantau/);
});

test("F15 — nominal setoran: koma desimal & titik ribuan dibaca benar (dulu '40864,5' → NaN → 'Nominal harus lebih dari 0')", () => {
  const f = (amount) => galatForm({ kind: "pph21", period: "2026-10", amount, paid_date: "2026-11-18" }, 50000);
  expect(f("40864,5")).toBe("");
  expect(f("40.864,50")).toBe("");
  expect(f("45240")).toBe("");
  expect(f("50.000,01")).toMatch(/melebihi sisa/);
  expect(f("0")).toBe("Nominal harus lebih dari 0.");
});
