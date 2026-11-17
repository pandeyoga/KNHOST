// Pelatihan Keuangan 18 Nov (K03 Profil PT) — bagian "Riwayat perubahan" rincian PT.
// Temuan uji jalan: Manajer (tanpa izin `audit.view`) membuka rincian PT → drawer tetap memanggil riwayat (403 di konsol)
// lalu menulis "Belum ada perubahan tercatat untuk badan usaha ini." padahal riwayatnya ada. Kini: tanpa izin → riwayat
// tidak dipanggil dan layar menjelaskan aksesnya; dengan izin → riwayat tampil seperti biasa.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockAudit = jest.fn();
jest.mock("../settings/entities/entityApi", () => ({
  __esModule: true,
  ...jest.requireActual("../settings/entities/entityApi"),
  getEntity: () => Promise.resolve({ id: "ent_ksc", legal_name: "Sukacita Textile", short_name: "Sukacita", type: "PT",
    status: "active", doc_prefix: "KSC", npwp: "01.234.567.8-901.000" }),
  getReadiness: () => Promise.resolve({ percent: 75, items: [] }),
  getEntityAudit: (...a) => mockAudit(...a),
  profileSettingItems: () => Promise.resolve(null),
  patchEntity: () => Promise.resolve({}),
  cancelTaxStatus: () => Promise.resolve({}),
}));
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: () => Promise.resolve({ data: [] }), post: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => <select data-testid={p["data-testid"]} value={p.value ?? ""} onChange={() => {}} />;
  return { __esModule: true, default: S, KNSelect: S };
});

import EntityDetailDrawer, { izinAuditSesi } from "../settings/entities/EntityDetailDrawer";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 8) { for (let i = 0; i < n; i += 1) await act(async () => {}); }   // eslint-disable-line no-await-in-loop
async function mount() {
  const host = document.createElement("div");
  document.body.appendChild(host);
  await act(async () => { createRoot(host).render(<EntityDetailDrawer entityId="ent_ksc" canManage={false} onClose={() => {}} />); });
  await flush();
}
const sesi = (perms) => localStorage.setItem("kn_user", JSON.stringify({ id: "u", role: "x", permissions: perms }));
afterEach(() => { mockAudit.mockReset(); localStorage.clear(); document.body.innerHTML = ""; });

describe("Rincian PT — riwayat perubahan mengikuti izin audit", () => {
  test("izinAuditSesi: tanpa sesi = perilaku lama; dengan sesi = izin audit.view", () => {
    expect(izinAuditSesi()).toBe(true);
    sesi({ settings: ["view"] });
    expect(izinAuditSesi()).toBe(false);
    sesi({ audit: ["view"] });
    expect(izinAuditSesi()).toBe(true);
  });

  test("Manajer tanpa izin audit: riwayat tidak dipanggil, layar menjelaskan aksesnya", async () => {
    sesi({ settings: ["view"], entity: ["view"] });
    await mount();
    expect(mockAudit).not.toHaveBeenCalled();
    expect(q("entity-detail-audit-denied")).toBeTruthy();
    expect(q("entity-detail-audit-empty")).toBeNull();
  });

  test("pemegang izin audit: riwayat tampil", async () => {
    sesi({ audit: ["view"] });
    mockAudit.mockResolvedValue([{ id: "a1", action: "entity_updated", actor: "Budi", timestamp: "2026-11-17T08:00:00Z" }]);
    await mount();
    expect(mockAudit).toHaveBeenCalledWith("ent_ksc");
    expect(q("entity-detail-audit")).toBeTruthy();
    expect(q("entity-detail-audit-denied")).toBeNull();
  });

  test("server menolak (403) walau sesi lama tanpa data izin: pesan akses, bukan 'belum ada perubahan'", async () => {
    mockAudit.mockRejectedValue({ response: { status: 403 } });
    await mount();
    expect(q("entity-detail-audit-denied")).toBeTruthy();
    expect(q("entity-detail-audit-empty")).toBeNull();
  });
});
