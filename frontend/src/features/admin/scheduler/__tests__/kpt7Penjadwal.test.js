// KP-T7 — Penjadwal & Notifikasi: job bersatuan menit diatur dalam menit (dulu selalu "jam" + `interval_hours` yang tidak
// pernah dipakai), job teknis hanya-baca, kolom Penerima & Ambang untuk PT aktif dengan tautan Ubah ke Pusat Pengaturan,
// dan editor baku tabel penerima (pilihan peran ganda) + daftar peran berpilihan.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { ScheduleEditor, JobPolicyCells } from "../SchedulerParts";
import SettingTableEditor from "../../../settings/config/SettingTableEditor";
import SettingEditor from "../../../settings/config/SettingEditor";
import { formatValue } from "../../../settings/config/configApi";
import { CONFIG_EVENT } from "../../../settings/config/configDeepLink";
import { registerDynamicRoles } from "../../../../config/roles";

// Pemilih bawaan (KNSelect → cmdk) diganti tiruan ringan: yang diuji kotak centang & teks.
jest.mock("../../../../components/KNSelect", () => () => null);
jest.mock("../../../finance/financeShared", () => ({ Badge: () => null }));
jest.mock("@/hooks/useListSearch", () => () => ({ toolbar: null, pageRows: [] }));
jest.mock("../../../../services/apiClient", () => ({ __esModule: true, default: {}, API: "/api" }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);

async function pasang(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  return host;
}

async function ketik(input, nilai) {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  await act(async () => {
    setter.call(input, String(nilai));
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

const RESERVASI = { id: "reservation_expiry", kind: "interval", interval_unit: "menit", interval_value: 30,
  interval_minutes: 30, interval_hours: null, locked: false };

test("U14 — job bersatuan menit: isian 'menit', nilai awal = selang pemicu, simpan mengirim interval_minutes", async () => {
  const simpan = jest.fn();
  const host = await pasang(<ScheduleEditor job={RESERVASI} onSave={simpan} saving={false} />);
  const isian = q(host, "job-interval-reservation_expiry");
  expect(isian.value).toBe("30");
  expect(isian.getAttribute("max")).toBe("1440");
  expect(q(host, "job-interval-unit-reservation_expiry").textContent).toBe("menit");
  await ketik(isian, 45);
  await act(async () => { q(host, "job-schedule-save-reservation_expiry").click(); });
  expect(simpan).toHaveBeenCalledWith({ interval_minutes: 45 });
});

test("job bersatuan jam tetap 'jam' + interval_hours; job teknis hanya-baca", async () => {
  const simpan = jest.fn();
  const host = await pasang(<ScheduleEditor job={{ id: "ops_stalled", kind: "interval", interval_unit: "jam",
    interval_value: 4, interval_hours: 4 }} onSave={simpan} saving={false} />);
  expect(q(host, "job-interval-unit-ops_stalled").textContent).toBe("jam");
  expect(q(host, "job-interval-ops_stalled").getAttribute("max")).toBe("24");
  await act(async () => { q(host, "job-schedule-save-ops_stalled").click(); });
  expect(simpan).toHaveBeenCalledWith({ interval_hours: 4 });
  const kunci = await pasang(<ScheduleEditor job={{ id: "rfid_gate_txn_retry", kind: "interval",
    interval_unit: "menit", interval_value: 2, locked: true }} onSave={simpan} saving={false} />);
  expect(q(kunci, "job-locked-rfid_gate_txn_retry").textContent).toBe("Jadwal teknis — tidak diubah dari layar.");
  expect(q(kunci, "job-interval-rfid_gate_txn_retry")).toBeNull();
  expect(q(kunci, "job-schedule-save-rfid_gate_txn_retry")).toBeNull();
});

test("U14 — kolom Penerima & Ambang terisi untuk Hutang Supplier; Ubah membuka kuncinya; tanpa nilai = —", async () => {
  const ap = { id: "ap_due", recipients: "Manajer", recipient_key: "notif.reminder_recipients",
    thresholds: [{ key: "notif.ap_due_soon_days", label: "Ingatkan hutang jatuh tempo dalam (hari)", value: 7,
      unit: "hari", text: "7 hari", group: "notifikasi" },
    { key: "notif.max_alerts_per_run", label: "Paling banyak peringatan per sekali jalan", value: 40,
      unit: "peringatan", text: "40 peringatan", group: "notifikasi" }] };
  const host = await pasang(<table><tbody><tr><JobPolicyCells job={ap} canEdit /></tr></tbody></table>);
  expect(q(host, "job-recipients-ap_due").textContent).toBe("ManajerUbah");
  expect(q(host, "job-thresholds-ap_due").textContent).toBe("7 hari · 40 peringatanUbah");
  const dibuka = [];
  const dengar = (e) => dibuka.push(e.detail);
  window.addEventListener(CONFIG_EVENT, dengar);
  await act(async () => { q(host, "job-thresholds-ap_due-edit").click(); });
  await act(async () => { q(host, "job-recipients-ap_due-edit").click(); });
  window.removeEventListener(CONFIG_EVENT, dengar);
  expect(dibuka).toEqual([{ key: "notif.ap_due_soon_days", group: "notifikasi" },
    { key: "notif.reminder_recipients", group: "notifikasi" }]);
  const lihat = await pasang(<table><tbody><tr><JobPolicyCells job={ap} canEdit={false} /></tr></tbody></table>);
  expect(q(lihat, "job-recipients-ap_due-edit")).toBeNull();
  const kosong = await pasang(<table><tbody><tr><JobPolicyCells job={{ id: "ai_fact_sync", recipients: "",
    thresholds: [] }} canEdit /></tr></tbody></table>);
  expect(q(kosong, "job-recipients-ai_fact_sync").textContent).toBe("—");
  expect(q(kosong, "job-thresholds-ai_fact_sync").textContent).toBe("—");
});

const PERAN = [{ value: "manager", label: "Manajer" }, { value: "warehouse", label: "Gudang" }];
const PENERIMA = { key: "notif.reminder_recipients", type: "table", row_shape: "list", status: "active",
  columns: [
    { name: "reminder", label: "Pengingat", type: "enum", options: [{ value: "ap_due", label: "Hutang" }] },
    { name: "mode", label: "Cara menentukan", type: "enum", options: [] },
    { name: "roles", label: "Peran", type: "multi", default: [], options: PERAN, options_source: "roles",
      disabled_when: { field: "mode", equals: "izin" } },
    { name: "permission", label: "Izin", type: "enum", options: [], disabled_when: { field: "mode", equals: "peran" } },
  ] };

test("tabel penerima: kolom Peran = pilihan ganda (peran bawaan + peran kustom), mati bila cara = izin", async () => {
  registerDynamicRoles([{ id: "cr_bayar_kpt7", custom: true, label: "Bayar Tagihan", long_label: "Bayar Tagihan" }]);
  const ubah = jest.fn();
  const nilai = [{ reminder: "ap_due", mode: "peran", roles: ["manager"], permission: "" },
    { reminder: "ap_due", mode: "izin", roles: [], permission: "vendor_bill.pay" }];
  const host = await pasang(<SettingTableEditor entry={PENERIMA} value={nilai} onChange={ubah} disabled={false} />);
  const grup = q(host, "cfg-input-notif.reminder_recipients-0-roles");
  expect(Array.from(grup.querySelectorAll("label")).map((l) => l.textContent)).toEqual(
    ["Manajer", "Gudang", "Bayar Tagihan"]);
  expect(q(host, "cfg-input-notif.reminder_recipients-0-roles-manager").checked).toBe(true);
  await act(async () => { q(host, "cfg-input-notif.reminder_recipients-0-roles-warehouse").click(); });
  expect(ubah).toHaveBeenLastCalledWith([{ ...nilai[0], roles: ["manager", "warehouse"] }, nilai[1]]);
  expect(q(host, "cfg-input-notif.reminder_recipients-1-roles-manager").disabled).toBe(true);
  registerDynamicRoles([]);
});

test("daftar berpilihan (peran penerima WhatsApp): kotak centang + label, bukan id teknis", async () => {
  const entry = { key: "notif.wa_broadcast_roles", type: "list", options: PERAN, label: "Peran WA" };
  const ubah = jest.fn();
  const host = await pasang(<SettingEditor entry={entry} value={["manager"]} onChange={ubah} disabled={false} />);
  await act(async () => { q(host, "cfg-input-notif.wa_broadcast_roles-warehouse").click(); });
  expect(ubah).toHaveBeenLastCalledWith(["manager", "warehouse"]);
  expect(formatValue(entry, ["manager", "warehouse"])).toBe("Manajer · Gudang");
  expect(formatValue({ type: "list" }, [-3, 0])).toBe("-3 · 0");
});
