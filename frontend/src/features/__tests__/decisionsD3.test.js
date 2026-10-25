// Keputusan pemilik 26 Okt (audit UI tahap 2) — agen D3: K-08 bobot nilai desainer = 100%, K-11 Admin Sample tanpa
// keputusan PO custom (SORD) di HP + papan PO Custom sales hanya pelanggan sendiri, K-12 tab Ringkas HP per peran,
// K-14 alasan minimum seragam 5 huruf, K-16 labdip tanpa handfeel ACC boleh dengan peringatan + alasan.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import MobileOpsApp from "../mobile/MobileOpsApp";
import { designerTiles, sampleAdminTiles, roleSummaryKind } from "../mobile/MobileRoleSummary";
import { weightSetSummaries } from "../settings/config/configApi";
import { gradeFormula } from "../designer/designerMeta";
import { askReason, REASON_MIN_LENGTH } from "../../services/confirmService";
import ConfirmHost from "../../components/ConfirmHost";
import SampleFormModal from "../rnd/SampleFormModal";

const mockGet = jest.fn();
const mockCreate = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../tanya/TanyaKnView", () => () => null);
jest.mock("../sales/mobile/MobilePwa", () => ({ MobilePushBanner: () => null, syncPushSubscription: () => {}, dropPushSubscription: async () => {} }));
jest.mock("../rnd/rndApi", () => ({
  createSample: (...a) => mockCreate(...a),
  listColors: () => Promise.resolve([]),
  listDesigns: () => Promise.resolve([]),
  listSamples: () => Promise.resolve({ items: [] }),
  rndMeta: () => Promise.resolve({ policy: {} }),
  sampleTypes: () => Promise.resolve([{ value: "labdip", label: "Labdip" }, { value: "handfeel", label: "Handfeel" }]),
  labdipHistory: () => Promise.resolve({ items: [] }),
  revalPartners: () => Promise.resolve({ items: [] }),
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
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
function typeInto(el, value) {
  const proto = el.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}

afterEach(() => { mockGet.mockReset(); mockCreate.mockReset(); document.body.innerHTML = ""; });

// ── K-08 ──────────────────────────────────────────────────────────────────────
test("K-08: bobot bawaan 30/30/20/20 dibaca sebagai porsi 100% (layar KPI & Pusat Pengaturan)", () => {
  const w = { on_time: 30, score: 30, acc: 20, design: 20, penalty_rework: 0.3, penalty_overdue: 0.5 };
  const text = gradeFormula(w);
  expect(text).toContain("tepat waktu 30%");
  expect(text).toContain("nilai versi desain 20% = 100%");
  expect(text).not.toContain("penyetaraan");                 // jumlah setelan sudah 100 → tanpa catatan penyetaraan
  const items = [
    { key: "rnd.kpi_weight_on_time", value: 30 }, { key: "rnd.kpi_weight_score", value: 30 },
    { key: "rnd.kpi_weight_acc", value: 20 }, { key: "rnd.kpi_weight_design", value: 20 },
  ];
  const [s] = weightSetSummaries(items);
  expect(s.total).toBe(100);
  expect(s.parts.map((p) => p.share)).toEqual([30, 30, 20, 20]);
  // Setelan lama 40/40/20/20 (= 120) → layar menyebut porsi efektif hasil penyetaraan server.
  const [old] = weightSetSummaries(items.map((i) => ({ ...i, value: i.value === 30 ? 40 : i.value })));
  expect(old.total).toBe(120);
  expect(old.parts.map((p) => p.share)).toEqual([33.3, 33.3, 16.7, 16.7]);
  // Kelompok bobot tidak lengkap di daftar (mis. hasil pencarian satu kunci) → tidak dirangkum.
  expect(weightSetSummaries(items.slice(0, 2))).toEqual([]);
});

// ── K-11 ──────────────────────────────────────────────────────────────────────
test("K-11: Admin Sample tidak mendapat tab/aksi PO custom (SORD) di HP walau izin belum termuat", async () => {
  routeGet({ "/notifications": [], "/sample-orders/desk": { queues: [] } });
  const noPerms = await mount(<MobileOpsApp user={{ role: "sample_admin", name: "Yoga" }} />);
  // Izin belum termuat: harga khusus/antrean masih mengikuti aturan lama, tetapi daftar PO custom tidak pernah dimuat.
  expect(mockGet.mock.calls.some(([url]) => String(url).includes("/special-orders"))).toBe(false);
  act(() => noPerms.root.unmount());

  mockGet.mockClear();
  const granted = { role: "sample_admin", name: "Yoga", permissions: { order: ["view", "approve"], sample_order: ["view"] } };
  const { host } = await mount(<MobileOpsApp user={granted} />);
  expect(q(host, "mobile-tab-btn-queue")).toBeNull();          // satu-satunya isi tab = PO custom → tab tidak ada
  expect(mockGet.mock.calls.some(([url]) => String(url).includes("/special-orders"))).toBe(false);

  // Manajer tetap memutus PO custom di HP.
  const mgr = { role: "manager", permissions: { order: ["approve"], price_approval: ["approve"], approval: ["view"] } };
  routeGet({ "/notifications": [], "/special-orders": [], "/price-approvals": [], "/approvals/my-queue": { items: [] } });
  const r2 = await mount(<MobileOpsApp user={mgr} />);
  expect(q(r2.host, "mobile-tab-btn-queue")).not.toBeNull();
});

// ── K-12 ──────────────────────────────────────────────────────────────────────
test("K-12: pemetaan angka Ringkas desainer & admin sample", () => {
  expect(roleSummaryKind("designer")).toBe("designer");
  expect(roleSummaryKind("sample_admin")).toBe("sample_admin");
  expect(roleSummaryKind("manager")).toBe("");
  const d = designerTiles({ open: 4, overdue: 1, due_soon: 2, due_soon_days: 3, revision: 1, delivered: 0 });
  expect(d.map((t) => t.key)).toEqual(["open", "overdue", "due_soon", "revision", "delivered"]);
  expect(d.find((t) => t.key === "due_soon").label).toBe("Tenggat ≤ 3 hari");
  // Server lama tanpa `due_soon` → kartunya tidak tampil (bukan 0 palsu).
  expect(designerTiles({ open: 2, overdue: 0, revision: 0, delivered: 1 }).some((t) => t.key === "due_soon")).toBe(false);
  const s = sampleAdminTiles({ queues: [{ id: "bayar_sampel", count: 2, total_value: 150000 }, { id: "di_gudang", count: 5 }] });
  expect(s[0]).toMatchObject({ key: "bayar_sampel", label: "Menunggu persetujuan bayar", value: 2, tone: "warning" });
  expect(s[1]).toMatchObject({ key: "di_gudang", label: "Dipotong / disiapkan gudang", value: 5 });
});

test("K-12: tab Ringkas HP desainer berisi angka pekerjaannya (bukan stok/pelanggan) + label sumber", async () => {
  routeGet({ "/notifications": [], "/design-requests": { summary: { open: 3, overdue: 1, due_soon: 2, due_soon_days: 3, revision: 1, delivered: 0 } } });
  const designer = { role: "designer", name: "Rani", permissions: { design_request: ["view"] } };
  const { host } = await mount(<MobileOpsApp user={designer} initialTab="kpi" />);
  expect(q(host, "mo-role-kpi-designer")).not.toBeNull();
  expect(q(host, "mo-role-kpi-open").textContent).toContain("3");
  expect(q(host, "mo-role-kpi-due_soon").textContent).toContain("Tenggat ≤ 3 hari");
  expect(q(host, "mo-role-kpi-source").textContent).toContain("ditugaskan ke Anda");
  expect(q(host, "mo-kpi")).toBeNull();                          // panel gudang/penjualan lama tidak dipakai
  const dsrCall = mockGet.mock.calls.find(([url]) => String(url).includes("/design-requests"));
  expect(dsrCall[1].params).toMatchObject({ mine: true, page: 1, page_size: 1 });
  expect(mockGet.mock.calls.some(([url]) => String(url).endsWith("/dashboard"))).toBe(false);
});

test("K-12: tab Ringkas HP admin sample = antrean SOS per tahap dari Meja Admin Sample", async () => {
  routeGet({ "/notifications": [], "/sample-orders/desk": { queues: [
    { id: "bayar_sampel", count: 1, total_value: 90000 }, { id: "siap_gudang", count: 2 }, { id: "di_gudang", count: 0 },
    { id: "kirim_ambil", count: 4 }, { id: "selesai", count: 7 }] } });
  const { host } = await mount(<MobileOpsApp user={{ role: "sample_admin", permissions: { sample_order: ["view"] } }} initialTab="kpi" />);
  expect(q(host, "mo-role-kpi-sample_admin")).not.toBeNull();
  expect(q(host, "mo-role-kpi-bayar_sampel").textContent).toContain("Menunggu persetujuan bayar");
  expect(q(host, "mo-role-kpi-kirim_ambil").textContent).toContain("4");
  expect(q(host, "mo-role-kpi-source").textContent).toContain("Meja Admin Sample");
});

// ── K-14 ──────────────────────────────────────────────────────────────────────
test("K-14: askReason bawaan menuntut minimal 5 huruf; catatan opsional tidak dibatasi", async () => {
  expect(REASON_MIN_LENGTH).toBe(5);
  const { host } = await mount(<ConfirmHost />);
  let res;
  await act(async () => { res = askReason({ title: "Tolak dokumen" }); });
  const ta = q(host, "confirm-modal-reason");
  await act(async () => { typeInto(ta, "abcd"); });
  expect(q(host, "confirm-modal-confirm").disabled).toBe(true);
  expect(q(host, "confirm-modal-reason-hint").textContent).toContain("minimal 5");
  await act(async () => { typeInto(ta, "abcde"); });
  expect(q(host, "confirm-modal-confirm").disabled).toBe(false);
  await act(async () => { q(host, "confirm-modal-confirm").click(); });
  await expect(res).resolves.toBe("abcde");

  // Catatan opsional (reasonRequired:false) tetap boleh kosong.
  let res2;
  await act(async () => { res2 = askReason({ title: "Setujui", reasonRequired: false }); });
  expect(q(host, "confirm-modal-confirm").disabled).toBe(false);
  await act(async () => { q(host, "confirm-modal-confirm").click(); });
  await expect(res2).resolves.toBe("");
});

// ── K-16 ──────────────────────────────────────────────────────────────────────
test("K-16: Sample Labdip Baru tanpa handfeel ACC — opsi lanjut dengan peringatan + alasan wajib", async () => {
  routeGet({});
  const { host } = await mount(<SampleFormModal lockType="labdip" onClose={() => {}} />);
  expect(q(host, "sample-parent-wrap")).not.toBeNull();
  const skip = q(host, "sample-parent-skip");
  expect(skip).not.toBeNull();
  expect(q(host, "sample-parent-skip-warning")).toBeNull();
  await act(async () => { skip.click(); });
  expect(q(host, "sample-parent-skip-warning").textContent).toContain("Peringatan");
  const ta = q(host, "sample-parent-skip-reason");
  await act(async () => { typeInto(ta, "abc"); });
  expect(q(host, "sample-parent-skip-hint").textContent).toContain("Minimal 5");
  await act(async () => { typeInto(ta, "kain sama dengan produk berjalan"); });
  expect(q(host, "sample-parent-skip-hint")).toBeNull();
});

// ── K-08 + K-11 di Pusat Pengaturan ───────────────────────────────────────────
test("K-08/K-11: Pusat Pengaturan menampilkan jumlah bobot 100% dan batas baca MD", async () => {
  const { configApi } = require("../settings/config/configApi");
  const SettingsHub = require("../settings/config/SettingsHub").default;
  const w = (key, label, value) => ({
    key, label, value, default: value, type: "pct", unit: "%", status: "active", scopes: ["global"], group: "rnd",
    help: "", impact: "", example: "", source_layer: "code_default", source_label: "Bawaan sistem", can_edit: true,
  });
  const items = [
    w("rnd.kpi_weight_on_time", "Bobot ketepatan waktu", 30), w("rnd.kpi_weight_score", "Bobot skor", 30),
    w("rnd.kpi_weight_acc", "Bobot ACC", 20), w("rnd.kpi_weight_design", "Bobot nilai desain", 20),
  ];
  const spies = [
    jest.spyOn(configApi, "registry").mockResolvedValue({
      groups: [{ id: "rnd", label: "R&D & Desain", question: "Bagaimana R&D bekerja?", count: 4 }],
      caps: { settings_manage: false, impact_apply: false, read_scope: "R&D & Desain" } }),
    jest.spyOn(configApi, "effective").mockResolvedValue({ items }),
    jest.spyOn(configApi, "health").mockResolvedValue({ rows: [] }),
  ];
  const { host } = await mount(<SettingsHub currentUser={{ role: "md", permissions: { rnd: ["view", "manage"] } }} entities={[]} />);
  await act(async () => {});
  expect(q(host, "cfg-read-scope").textContent).toContain("R&D & Desain");
  expect(q(host, "cfg-limited-rights")).toBeNull();
  expect(q(host, "cfg-weight-total-rnd-designer-grade-sum").textContent).toBe("100%");
  spies.forEach((s) => s.mockRestore());
});
