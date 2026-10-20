// Sisir lanjutan gerbang peran (keputusan owner 2026-10-21 #5) — gerbang lewat variabel `role` lokal kini
// mengikuti izin efektif (+ peran acuan bila server memakai role_in).
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { schedPerms } from "../admin/scheduler/SchedulerParts";
import CashAdvanceDetail from "../pettycash/CashAdvanceDetail";
import VehicleLogsView from "../pettycash/VehicleLogsView";

const CA = { id: "ca1", number: "PD-1", status: "pending_atasan", entity_id: "ent_ksc", items: [], approvals: [],
  total_amount: 100000, created_by: "Ayu", kegiatan: "Kunjungan" };
const renderCa = (user) => renderToStaticMarkup(<CashAdvanceDetail ca={CA} currentUser={user} entities={[]} />);

test("scheduler: izin efektif scheduler.view/run/configure, bukan nama peran", () => {
  expect(schedPerms({ scheduler: ["view", "run"] })).toEqual({ view: true, run: true, configure: false });
  expect(schedPerms({})).toEqual({ view: false, run: false, configure: false });
});

describe("kasbon — tahap persetujuan = izin + peran tahap server", () => {
  test("Manager berizin approve saja: Setujui ada, Tolak tidak", () => {
    const html = renderCa({ role: "manager", permissions: { cash_advance: ["view", "approve"] } });
    expect(html).toContain("ca-approve-btn");
    expect(html).not.toContain("ca-reject-btn");
  });
  test("Finance berizin approve tetapi bukan peran tahap Atasan: tidak ada tombol tahap", () => {
    const html = renderCa({ role: "finance", permissions: { cash_advance: ["view", "approve", "reject"] } });
    expect(html).not.toContain("ca-approve-btn");
  });
  test("Manager tanpa izin approve: tidak ada tombol tahap", () => {
    expect(renderCa({ role: "manager", permissions: { cash_advance: ["view"] } })).not.toContain("ca-approve-btn");
  });
});

test("log kendaraan: buat log = vehicle_log.create (Admin Sales kini dapat), tanpa nama peran", () => {
  const html = renderToStaticMarkup(<VehicleLogsView currentUser={{ role: "sales_admin", permissions: { vehicle_log: ["view", "create"] } }} />);
  expect(html).toContain("veh-log-create-btn");
  const none = renderToStaticMarkup(<VehicleLogsView currentUser={{ role: "manager", permissions: { vehicle_log: ["view"] } }} />);
  expect(none).not.toContain("veh-log-create-btn");
});
