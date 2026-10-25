// UAT 24 Okt (audit UI tahap 2) — G5b: tab HP Ops dari izin (G5-08), lencana "Putuskan di HP" hanya untuk dokumen yang
// ada di daftar (G5-09), Kesehatan Konfigurasi tanpa vonis saat gagal (G5-15), label kolom master (G5-03),
// pembersih teks pengaturan (G5-61), tombol WA/TTD dokumen batal (G5-50 / G4-15).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import MobileOpsApp from "../mobile/MobileOpsApp";
import ConfigHealthPanel from "../settings/config/ConfigHealthPanel";
import DocumentActionsBar from "../documents/DocumentActionsBar";
import { cellText, COLUMNS } from "../settings/masters/masterFieldsConfig";
import { cleanCfgText, isDeprecatedSetting, configApi } from "../settings/config/configApi";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../tanya/TanyaKnView", () => () => null);
jest.mock("../sales/mobile/MobilePwa", () => ({ MobilePushBanner: () => null, syncPushSubscription: () => {}, dropPushSubscription: async () => {} }));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};   // jsdom tidak menyediakannya
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  await act(async () => {});
  return { host, root };
}

function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).find((k) => url.includes(k));
    if (!hit) return Promise.resolve({ data: [] });
    const v = map[hit];
    return v instanceof Error ? Promise.reject(v) : Promise.resolve({ data: v });
  });
}

afterEach(() => { mockGet.mockReset(); document.body.innerHTML = ""; });

test("G5-08: peran tanpa izin persetujuan tidak mendapat tab Persetujuan/Antrean; bilah ≤ 5 tab", async () => {
  routeGet({ "/notifications": [], "/dashboard": {} });
  const designer = { role: "designer", name: "Rani", permissions: { design_request: ["view"] } };
  const { host } = await mount(<MobileOpsApp user={designer} />);
  expect(q(host, "mobile-tab-btn-queue")).toBeNull();
  expect(q(host, "mobile-tab-btn-matrix")).toBeNull();
  expect(q(host, "mobile-tab-btn-desktop")).toBeNull();          // dilebur ke Ringkas & app bar
  expect(q(host, "mobile-tab-btn-notif")).not.toBeNull();

  const admin = { role: "admin", name: "Admin", permissions: { price_approval: ["*"], order: ["*"], approval: ["*"], makloon_order: ["*"] } };
  const r2 = await mount(<MobileOpsApp user={admin} />);
  expect(q(r2.host, "mobile-tab-btn-queue")).not.toBeNull();
  expect(r2.host.querySelectorAll('[data-testid^="mobile-tab-btn-"]').length).toBeLessThanOrEqual(5);
});

test("G5-09: lencana 'Putuskan di HP' hanya untuk dokumen yang ada di daftar Persetujuan", async () => {
  routeGet({
    "/notifications/unread-count": { count: 3 },
    "/notifications": [
      { id: "n1", type: "special_order_approval", ref: "so_custom_appr:sord_a#u1", title: "PO custom menunggu persetujuan: SORD-1", link: "special-orders", severity: "warning" },
      { id: "n2", type: "special_order_approval", ref: "so_custom_appr:sord_x#u1", title: "PO custom menunggu persetujuan: SORD-9", link: "special-orders", severity: "warning" },
      { id: "n3", type: "turn", title: "Giliran Anda — Kirim pesanan: KSC/SO-00001", body: "Toko · tahap: shipped", link: "operations" },
    ],
    "/special-orders": [{ id: "sord_a", number: "SORD-1", status: "pending_approval", customer_name: "Toko" }],
    "/price-approvals": [],
  });
  const admin = { role: "admin", permissions: { price_approval: ["*"], order: ["*"], approval: ["*"] } };
  const { host } = await mount(<MobileOpsApp user={admin} initialTab="notif" />);
  expect(q(host, "mo-notif-decide-n1")).not.toBeNull();
  expect(q(host, "mo-notif-decide-n2")).toBeNull();     // dokumennya tidak ada di daftar Persetujuan
  expect(q(host, "mo-notif-decide-n3")).toBeNull();
  expect(q(host, "mo-notif-n3").textContent).toContain("tahap: dikirim");
  expect(q(host, "mo-notif-n3").textContent).not.toContain("shipped");
});

test("G5-15: galat muat Kesehatan Konfigurasi tidak diikuti vonis hijau & KPI", async () => {
  const spy = jest.spyOn(configApi, "health").mockRejectedValue({ response: { status: 403, data: { detail: "Permission ditolak: settings.view" } } });
  const { host } = await mount(<ConfigHealthPanel />);
  expect(q(host, "cfg-health-verdict")).toBeNull();
  expect(q(host, "cfg-health-kpi-OK")).toBeNull();
  expect(host.textContent).not.toContain("Permission ditolak");
  spy.mockRestore();
});

test("G5-03: kolom master berlabel (dokumen, peran, persen diskon, proses, tahap)", () => {
  const rule = { doc_type: "discount", min_amount: 0, max_amount: 10, required_role: "manager" };
  const col = (kind, key) => COLUMNS[kind].find((c) => c.key === key);
  const fmt = (v) => `Rp ${v}`;
  expect(cellText(col("approval-rules", "doc_type"), rule, fmt)).toBe("Diskon (%)");
  expect(cellText(col("approval-rules", "max_amount"), rule, fmt)).toBe("10%");
  expect(cellText(col("approval-rules", "required_role"), rule, fmt)).not.toBe("manager");
  expect(cellText(col("approval-rules", "min_amount"), { doc_type: "sales_order", min_amount: 5 }, fmt)).toBe("Rp 5");
  expect(cellText(col("process-stages", "process_type"), { process_type: "pre_treatment" })).not.toContain("_");
  expect(cellText(col("product-lines", "stage_sequence"), { stage_sequence: ["benang", "tenun", "inspect"] })).toBe("Benang · Tenun · Inspeksi");
});

test("G5-61: teks pengaturan tanpa backtick/kode; setting '(Lama)' dikenali usang", () => {
  expect(cleanCfgText("Dibaca `rnd.lifecycle_enforcement` (KN-D16).")).toBe("Dibaca rnd.lifecycle_enforcement.");
  expect(isDeprecatedSetting({ label: "(Lama) Batas ronde — TIDAK DIPAKAI LAGI", status: "active" })).toBe(true);
  expect(isDeprecatedSetting({ label: "Batas ronde", status: "active" })).toBe(false);
});

test("G5-50/G4-15: dokumen batal tidak menawarkan Kirim WA & Tanda Tangan", async () => {
  routeGet({ "/pdf/doc-types": [{ doc_type: "sales_order", label: "SO", esignable: true }] });
  const user = { role: "admin" };
  const live = await mount(<DocumentActionsBar docType="sales_order" sourceId="so1" label="SO" esignable currentUser={user} autoCheckSignature={false} />);
  expect(q(live.host, "doc-act-wa")).not.toBeNull();
  const dead = await mount(<DocumentActionsBar docType="sales_order" sourceId="so2" label="SO" esignable currentUser={user} autoCheckSignature={false} status="cancelled" />);
  expect(q(dead.host, "doc-act-wa")).toBeNull();
  expect(q(dead.host, "doc-act-esign")).toBeNull();
  const hidden = await mount(<DocumentActionsBar docType="sales_order" sourceId="so3" label="SO" esignable currentUser={user} autoCheckSignature={false} hideWhatsapp />);
  expect(q(hidden.host, "doc-act-wa")).toBeNull();
});
