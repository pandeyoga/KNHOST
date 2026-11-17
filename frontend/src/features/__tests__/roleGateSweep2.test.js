// Sisir lanjutan gerbang peran (keputusan owner 2026-10-21 #5) — gerbang lewat variabel `role` lokal kini
// mengikuti izin efektif (+ peran acuan bila server memakai role_in).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { schedPerms } from "../admin/scheduler/SchedulerParts";
import CashAdvanceDetail from "../pettycash/CashAdvanceDetail";
import VehicleLogsView from "../pettycash/VehicleLogsView";

// KP-T4 (0c5486e, 14 Nov) — tahap kasbon yang boleh diputus = jawaban server `GET /api/approval-policies/can-decide/me`
// (izin + Aturan Persetujuan jenjang berjalan), bukan lagi daftar peran per tahap di layar (`stageRoles`
// manager/admin yang dulu diuji di sini). Uji memalsukan jawaban server itu; isi layar dibaca sesudah efek berjalan.
const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } } },
  API: "/api",
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const CA = { id: "ca1", number: "PD-1", status: "pending_atasan", entity_id: "ent_ksc", items: [], approvals: [],
  total_amount: 100000, created_by: "Ayu", kegiatan: "Kunjungan" };
const HINT = "Jenjang 1 diputus peran Atasan Langsung menurut Aturan Persetujuan.";

/** Jawaban server can-decide/me: `allowed` untuk jenjang berjalan; selain itu daftar kosong. */
function serverDecides(allowed) {
  mockGet.mockImplementation((url) => (String(url).endsWith("/approval-policies/can-decide/me")
    ? Promise.resolve({ data: allowed ? { allowed: true } : { allowed: false, message: HINT } })
    : Promise.resolve({ data: [] })));
}
let mounted = [];
async function renderCa(user) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<CashAdvanceDetail ca={CA} currentUser={user} entities={[]} />); });
  await act(async () => {}); await act(async () => {});
  mounted.push({ host, root });
  return host.innerHTML;
}
afterEach(async () => {
  for (const m of mounted) { await act(async () => { m.root.unmount(); }); m.host.remove(); }
  mounted = [];
});

test("scheduler: izin efektif scheduler.view/run/configure, bukan nama peran", () => {
  expect(schedPerms({ scheduler: ["view", "run"] })).toEqual({ view: true, run: true, configure: false });
  expect(schedPerms({})).toEqual({ view: false, run: false, configure: false });
});

describe("kasbon — tahap persetujuan = izin + jawaban server (Aturan Persetujuan), bukan nama peran", () => {
  test("server: boleh memutus jenjang ini · izin approve saja → Setujui ada, Tolak tidak", async () => {
    serverDecides(true);
    const html = await renderCa({ role: "manager", permissions: { cash_advance: ["view", "approve"] } });
    expect(html).toContain("ca-approve-btn");
    expect(html).not.toContain("ca-approve-btn-locked");
    expect(html).not.toContain("ca-reject-btn");
    // Pertanyaan ke server memakai jenis dokumen, PT, nominal, dan nomor jenjang status `pending_atasan` (= 1).
    const call = mockGet.mock.calls.find(([u]) => String(u).endsWith("/approval-policies/can-decide/me"));
    expect(call[1].params).toMatchObject({ doc_kind: "cash_advance", entity_id: "ent_ksc", amount: 100000, level: 1 });
  });
  test("peran kustom tanpa acuan, izin approve + reject, server membolehkan → Setujui & Tolak", async () => {
    serverDecides(true);
    const html = await renderCa({ role: "cr_kasir", permissions: { cash_advance: ["view", "approve", "reject"] } });
    expect(html).toContain("ca-approve-btn");
    expect(html).toContain("ca-reject-btn");
  });
  test("berizin approve tetapi server menolak (bukan pemutus jenjang 1): tombol tahap terkunci + alasan server", async () => {
    serverDecides(false);
    const html = await renderCa({ role: "finance", permissions: { cash_advance: ["view", "approve", "reject"] } });
    expect(html).not.toContain("data-testid=\"ca-approve-btn\"");
    expect(html).not.toContain("ca-reject-btn");
    expect(html).toContain("ca-approve-btn-locked");
    expect(html).toContain(HINT);
  });
  test("tanpa izin approve: tidak ada tombol tahap walau server membolehkan (nama peran Manajer tidak berarti)", async () => {
    serverDecides(true);
    const html = await renderCa({ role: "manager", permissions: { cash_advance: ["view"] } });
    expect(html).not.toContain("ca-approve-btn");
    expect(html).not.toContain("ca-reject-btn");
  });
});

test("log kendaraan: buat log = vehicle_log.create (Admin Sales kini dapat), tanpa nama peran", () => {
  const html = renderToStaticMarkup(<VehicleLogsView currentUser={{ role: "sales_admin", permissions: { vehicle_log: ["view", "create"] } }} />);
  expect(html).toContain("veh-log-create-btn");
  const none = renderToStaticMarkup(<VehicleLogsView currentUser={{ role: "manager", permissions: { vehicle_log: ["view"] } }} />);
  expect(none).not.toContain("veh-log-create-btn");
});
