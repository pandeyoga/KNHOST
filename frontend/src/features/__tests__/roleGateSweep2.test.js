// Sisir lanjutan gerbang peran (keputusan owner 2026-10-21 #5) — gerbang lewat variabel `role` lokal kini
// mengikuti izin efektif (+ peran acuan bila server memakai role_in).
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { schedPerms } from "../admin/scheduler/SchedulerParts";
import CashAdvanceDetail from "../pettycash/CashAdvanceDetail";
import VehicleLogsView from "../pettycash/VehicleLogsView";

// KP-T4 (`0c5486ea`) — tahap uang muka boleh diputus = jawaban server `GET /approval-policies/can-decide/me` (izin +
// Aturan Persetujuan jenjang ini), bukan lagi daftar peran per tahap di layar. Render statis tidak menjalankan efek,
// jadi jawaban server per uji disuntikkan lewat tiruan `useCanDecideMap`; parameter yang ditanyakan ikut dicatat.
let mockDecide = null;
const mockAsked = [];
jest.mock("../../hooks/useCanDecide", () => ({
  useCanDecideMap: (docs, toParams) => Object.fromEntries((docs || []).map((d) => {
    mockAsked.push(toParams(d));
    return [d.id, mockDecide];
  })),
}));

const CA = { id: "ca1", number: "PD-1", status: "pending_atasan", entity_id: "ent_ksc", items: [], approvals: [],
  total_amount: 100000, created_by: "Ayu", kegiatan: "Kunjungan" };
const renderCa = (user) => renderToStaticMarkup(<CashAdvanceDetail ca={CA} currentUser={user} entities={[]} />);
const has = (html, id) => html.includes(`data-testid="${id}"`);
const ALLOWED = { allowed: true, message: "", loading: false };
const DENIED = { allowed: false, message: "Jenjang Atasan Langsung diputus Manajer.", loading: false };

test("scheduler: izin efektif scheduler.view/run/configure, bukan nama peran", () => {
  expect(schedPerms({ scheduler: ["view", "run"] })).toEqual({ view: true, run: true, configure: false });
  expect(schedPerms({})).toEqual({ view: false, run: false, configure: false });
});

describe("kasbon — tahap persetujuan = izin + jawaban server can-decide (KP-T4)", () => {
  beforeEach(() => { mockDecide = null; mockAsked.length = 0; });
  test("Manager berizin approve saja, server membolehkan jenjang: Setujui ada, Tolak tidak", () => {
    mockDecide = ALLOWED;
    const html = renderCa({ role: "manager", permissions: { cash_advance: ["view", "approve"] } });
    expect(has(html, "ca-approve-btn")).toBe(true);
    expect(has(html, "ca-reject-btn")).toBe(false);
    // status `pending_atasan` → jenjang 1 Aturan Persetujuan uang muka
    expect(mockAsked).toContainEqual({ docKind: "cash_advance", entityId: "ent_ksc", amount: 100000, level: 1 });
  });
  test("Finance berizin approve tetapi server menolak jenjang Atasan: tanpa tombol aktif, tombol mati berpetunjuk server", () => {
    mockDecide = DENIED;
    const html = renderCa({ role: "finance", permissions: { cash_advance: ["view", "approve", "reject"] } });
    expect(has(html, "ca-approve-btn")).toBe(false);
    expect(has(html, "ca-reject-btn")).toBe(false);
    expect(has(html, "ca-approve-btn-locked")).toBe(true);
    expect(html).toContain(DENIED.message);
  });
  test("Manager tanpa izin approve: tidak ada tombol tahap walau server membolehkan jenjang", () => {
    mockDecide = ALLOWED;
    const html = renderCa({ role: "manager", permissions: { cash_advance: ["view"] } });
    expect(has(html, "ca-approve-btn")).toBe(false);
    expect(has(html, "ca-approve-btn-locked")).toBe(false);
  });
  test("Jawaban server belum tiba: belum ada tombol tahap", () => {
    expect(has(renderCa({ role: "manager", permissions: { cash_advance: ["view", "approve"] } }), "ca-approve-btn")).toBe(false);
  });
});

test("log kendaraan: buat log = vehicle_log.create (Admin Sales kini dapat), tanpa nama peran", () => {
  const html = renderToStaticMarkup(<VehicleLogsView currentUser={{ role: "sales_admin", permissions: { vehicle_log: ["view", "create"] } }} />);
  expect(html).toContain("veh-log-create-btn");
  const none = renderToStaticMarkup(<VehicleLogsView currentUser={{ role: "manager", permissions: { vehicle_log: ["view"] } }} />);
  expect(none).not.toContain("veh-log-create-btn");
});
