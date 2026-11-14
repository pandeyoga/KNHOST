// PK-46 — kartu pengaturan BERTANGGAL (tabel PPh 21): di bawah kotak "Berlaku sejak" ada teks bantu bahwa slip periode
// sebelum tanggal itu tetap memakai tabel lama. Kunci biasa tidak menampilkannya.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import SettingCard from "../SettingCard";

// Pemilih bawaan (KNSelect → cmdk, KNDateTimePicker → popover) diganti tiruan ringan: yang diuji hanya teks kartu.
jest.mock("../../../../components/KNSelect", () => () => null);
jest.mock("@/components/KNDateTimePicker", () => () => null);
jest.mock("../../../../services/apiClient", () => ({ __esModule: true, default: {}, API: "/api" }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);

async function bukaJadwal(item) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  const noop = () => {};
  await act(async () => {
    root.render(
      <SettingCard item={item} scopeType="global" scopeId="" canEdit onSave={async () => true}
        onReset={noop} onClearEntity={noop} onWhy={noop} onSimulate={noop} onHistory={noop} />,
    );
  });
  await act(async () => { q(host, `cfg-input-${item.key}`).click(); });            // nilai berubah → kotak simpan
  await act(async () => { q(host, `cfg-sched-toggle-${item.key}`).click(); });    // "Jadwalkan berlaku sejak…"
  return host;
}

const kartu = (over) => ({
  label: "Uji", help: "", impact: "", example: "", type: "bool", value: false, default: false,
  scopes: ["global"], status: "active", source_layer: "code_default", source_label: "Default sistem",
  requires_reason: true, risk: "high", consumers: [], scheduled: [], ...over,
});

afterEach(() => { document.body.innerHTML = ""; });

test("kunci bertanggal: teks bantu slip periode lama di bawah 'Berlaku sejak'", async () => {
  const host = await bukaJadwal(kartu({ key: "hr.pph21.uji", bertanggal: true }));
  expect(host.textContent).toContain("Berlaku sejak");
  const em = q(host, "cfg-efffrom-bertanggal-hr.pph21.uji");
  expect(em).not.toBeNull();
  expect(em.textContent).toBe("Slip dengan periode sebelum tanggal ini tetap memakai tabel lama.");
});

test("kunci biasa: teks bantu itu tidak tampil", async () => {
  const host = await bukaJadwal(kartu({ key: "sales.uji", bertanggal: false }));
  expect(host.textContent).toContain("Berlaku sejak");
  expect(q(host, "cfg-efffrom-bertanggal-sales.uji")).toBeNull();
  expect(host.textContent).not.toContain("tetap memakai tabel lama");
});
