// KF-T3 — kartu pengaturan menampilkan nilai yang DIPAKAI MESIN: bila aturan lain menimpanya, kartu menulis siapa yang
// menimpa + nilai tersimpan yang tidak dipakai (dan tautan ke sumbernya). Baris jadwal menyebut cakupan dan bisa
// dibatalkan oleh yang boleh mengubah kunci itu.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import SettingCard from "../SettingCard";
import { AppNavProvider } from "../../../../context/AppNavContext";
import { CONFIG_EVENT } from "../configDeepLink";

// Pemilih bawaan (KNSelect → cmdk, KNDateTimePicker → popover) diganti tiruan ringan: yang diuji hanya teks kartu.
jest.mock("../../../../components/KNSelect", () => () => null);
jest.mock("@/components/KNDateTimePicker", () => () => null);
jest.mock("../../../../services/apiClient", () => ({ __esModule: true, default: {}, API: "/api" }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const noop = () => {};

async function pasang(item, { canEdit = true, onCancelScheduled = noop, nav = null, entities = [] } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  const card = (
    <SettingCard item={item} scopeType="entity" scopeId="ent_kanda" scopeLabel="KANDA" canEdit={canEdit}
      onSave={async () => true} onReset={noop} onClearEntity={noop} onWhy={noop} onSimulate={noop}
      onHistory={noop} onCancelScheduled={onCancelScheduled} entities={entities} />
  );
  await act(async () => {
    root.render(nav ? <AppNavProvider role="admin" onNavigateTo={nav}>{card}</AppNavProvider> : card);
  });
  return host;
}

const kartu = (over) => ({
  label: "Uji", help: "", impact: "", example: "", scopes: ["global", "entity"], status: "active",
  source_layer: "code_default", source_label: "Default sistem", requires_reason: false, risk: "low",
  consumers: [], scheduled: [], overridden_by: null, ...over,
});

const PPN = kartu({
  key: "tax.ppn_rate", type: "pct", unit: "%", value: 0, stored_value: 12, risk: "high", requires_reason: true,
  overridden_by: { id: "pt_bukan_pkp", label: "Status pajak PT ini: bukan PKP", value: 0, link: { view: "entities-access" } },
});

afterEach(() => { document.body.innerHTML = ""; });

test("U17 — ditimpa: nilai mesin + lencana Ditimpa + nilai tersimpan; tautan ke layar sumbernya", async () => {
  const pindah = jest.fn();
  const host = await pasang(PPN, { nav: pindah });
  expect(q(host, "cfg-value-tax.ppn_rate").textContent).toBe("0 %");
  expect(q(host, "cfg-overridden-tax.ppn_rate").textContent).toBe("Ditimpa");
  expect(q(host, "cfg-override-note-tax.ppn_rate").textContent).toContain(
    "Ditimpa oleh: Status pajak PT ini: bukan PKP. Nilai yang tersimpan (12 %) tidak dipakai.");
  await act(async () => { q(host, "cfg-override-open-tax.ppn_rate").click(); });
  expect(pindah).toHaveBeenCalledWith("entities-access", expect.anything());
  // Tombol ubah tetap ada; yang diubah nilai tersimpan.
  expect(q(host, "cfg-input-tax.ppn_rate").value).toBe("12");
});

test("ditimpa pengaturan lain: tautan membuka kartu kuncinya", async () => {
  const item = kartu({
    key: "allocation.allow_intercompany", type: "bool", value: false, stored_value: true,
    overridden_by: { id: "wajib_transfer_antar_pt", label: "Pengaturan “Wajib transfer sebelum menjual stok PT lain” sedang aktif",
      value: false, link: { key: "inventory.intercompany_transfer_required" } },
  });
  const terima = jest.fn();
  window.addEventListener(CONFIG_EVENT, terima);
  const host = await pasang(item);
  expect(q(host, "cfg-override-note-allocation.allow_intercompany").textContent).toContain(
    "Nilai yang tersimpan (Ya / Aktif) tidak dipakai.");
  await act(async () => { q(host, "cfg-override-open-allocation.allow_intercompany").click(); });
  expect(terima).toHaveBeenCalledTimes(1);
  expect(terima.mock.calls[0][0].detail.key).toBe("inventory.intercompany_transfer_required");
  window.removeEventListener(CONFIG_EVENT, terima);
  expect(q(host, "cfg-input-allocation.allow_intercompany").getAttribute("aria-checked")).toBe("true");
});

test("tidak ditimpa: tanpa lencana dan catatan", async () => {
  const host = await pasang(kartu({ key: "tax.ppn_mode2", type: "pct", unit: "%", value: 12, stored_value: 12 }));
  expect(q(host, "cfg-overridden-tax.ppn_mode2")).toBeNull();
  expect(q(host, "cfg-override-note-tax.ppn_mode2")).toBeNull();
});

test("U17 — baris jadwal menyebut cakupan; Batalkan jadwal memanggil pembatal dengan barisnya", async () => {
  const sched = [
    { id: "cfgv_1", scope_type: "global", scope_id: "", value: 11, effective_from: "2026-12-01T03:00:00+00:00" },
    { id: "cfgv_2", scope_type: "entity", scope_id: "ent_kanda", value: 10, effective_from: "2026-12-02T03:00:00+00:00" },
  ];
  const batal = jest.fn();
  const host = await pasang(kartu({ key: "ar.grace_days", type: "duration", unit: "hari", value: 0, stored_value: 0,
    scheduled: sched }), { onCancelScheduled: batal, entities: [{ id: "ent_kanda", short_name: "KANDA" }] });
  const b0 = q(host, "cfg-sched-row-ar.grace_days-0").textContent;
  const b1 = q(host, "cfg-sched-row-ar.grace_days-1").textContent;
  expect(b0).toContain("Terjadwal: 11 hari mulai 01 Des 2026");
  expect(b0).toContain("WIB · Global");
  expect(b1).toContain("WIB · KANDA");
  expect(b1).not.toContain("ent_kanda");
  await act(async () => { q(host, "cfg-sched-cancel-ar.grace_days-1").click(); });
  expect(batal).toHaveBeenCalledTimes(1);
  expect(batal.mock.calls[0][1].id).toBe("cfgv_2");
});

test("Batalkan jadwal hanya bagi yang boleh mengubah", async () => {
  const host = await pasang(kartu({ key: "ar.grace_days", type: "duration", unit: "hari", value: 0, stored_value: 0,
    scheduled: [{ id: "cfgv_1", scope_type: "global", scope_id: "", value: 11, effective_from: "2026-12-01T03:00:00Z" }] }),
  { canEdit: false });
  expect(q(host, "cfg-sched-row-ar.grace_days-0")).not.toBeNull();
  expect(q(host, "cfg-sched-cancel-ar.grace_days-0")).toBeNull();
});

// ── Hook Pusat Pengaturan: konfirmasi + alasan (wajib untuk kunci berisiko tinggi) → API → "Jadwal dibatalkan." ──
jest.mock("../../../../services/confirmService", () => ({ askReason: jest.fn() }));
jest.mock("../configApi", () => {
  const asli = jest.requireActual("../configApi");
  return {
    ...asli,
    configApi: {
      ...asli.configApi,
      registry: jest.fn(async () => ({ groups: [{ id: "pajak", label: "Pajak", count: 1 }], caps: {} })),
      effective: jest.fn(async () => ({ items: [], groups: [] })),
      health: jest.fn(async () => ({ rows: [] })),
      cancelScheduled: jest.fn(async (b) => ({ id: b.id, cancelled_at: "2026-11-14T00:00:00Z" })),
    },
  };
});

test("useSettingsBrowser.onCancelScheduled — alasan wajib bila berisiko tinggi; batal di konfirmasi = tidak memanggil API", async () => {
  const { askReason } = require("../../../../services/confirmService");
  const { configApi } = require("../configApi");
  const { useSettingsBrowser } = require("../SettingsHub");
  let s = null;
  function Harness() { s = useSettingsBrowser({ selectedEntity: "ent_kanda" }); return null; }
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => { createRoot(host).render(<Harness />); });

  askReason.mockResolvedValueOnce(null);
  await act(async () => { await s.onCancelScheduled(PPN, { id: "cfgv_9" }); });
  expect(configApi.cancelScheduled).not.toHaveBeenCalled();
  expect(askReason.mock.calls[0][0]).toMatchObject({
    message: "Batalkan perubahan terjadwal ini? Nilai yang berlaku sekarang tidak berubah.", reasonRequired: true });

  askReason.mockResolvedValueOnce("tidak jadi naik");
  let ok;
  await act(async () => { ok = await s.onCancelScheduled(PPN, { id: "cfgv_9" }); });
  expect(ok).toBe(true);
  expect(configApi.cancelScheduled).toHaveBeenCalledWith({ id: "cfgv_9", reason: "tidak jadi naik" });
  expect(s.notice).toEqual({ msg: "Jadwal dibatalkan.", tone: "ok" });

  askReason.mockResolvedValueOnce("");
  await act(async () => { await s.onCancelScheduled({ ...PPN, requires_reason: false }, { id: "cfgv_10" }); });
  expect(askReason.mock.calls[2][0].reasonRequired).toBe(false);
  expect(configApi.cancelScheduled).toHaveBeenLastCalledWith({ id: "cfgv_10", reason: "" });
});
