// Meja gelombang 2 · Task 8 — aksi di tempat Meja Admin Sales: tetapkan sales (berizin), catat sudah diingatkan,
// tolak permintaan internal, "Lihat" = pop-up saja. Endpoint & pemeriksaan sama dengan layar asal.
import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";
import SalesAdminDesk from "../sales_admin/SalesAdminDesk";
import MobileSalesAdminDesk from "../sales/mobile/MobileSalesAdminDesk";
import { DESK_PANELS, panelFor } from "../desks/deskPanels";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockToast = jest.fn();
const mockReason = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } } },
  API: "/api",
  setActiveEntity: () => {}, setAuthToken: () => {},
}));
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: (...a) => mockToast(...a) }));
jest.mock("../../services/confirmService", () => ({
  __esModule: true, askConfirm: jest.fn(async () => false), askReason: (...a) => mockReason(...a),
  askText: jest.fn(async () => null), askChoice: jest.fn(async () => null), default: {},
}));
jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid }) => (
    <select data-testid={tid} value={value ?? ""} onChange={(e) => onValueChange(e.target.value)}>
      <option value="" />
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>);
  return { __esModule: true, default: M, KNSelect: M };
});
jest.mock("../sales_admin/SoTrackerCard", () => () => <div data-testid="so-tracker-stub" />);
jest.mock("../sales_admin/KeepPendingPanel", () => () => null);
jest.mock("../sales_admin/CustomerGradeRulesCard", () => () => null);
jest.mock("../sales_admin/VerifyOrderDialog", () => () => null);
jest.mock("../sales_admin/FulfillmentDecisionDialog", () => () => null);

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const teks = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");
let roots = [];
async function mount(el) {
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host); roots.push(root);
  await act(async () => { root.render(el); }); await act(async () => {}); await act(async () => {});
  return host;
}
const klik = async (id) => act(async () => { q(id).dispatchEvent(new MouseEvent("click", { bubbles: true })); });
const tunggu = async () => { for (let i = 0; i < 4; i += 1) await act(async () => { await new Promise((r) => setTimeout(r, 0)); }); };   // eslint-disable-line no-await-in-loop
const ubah = async (id, nilai) => act(async () => {
  const el = q(id);
  const proto = el.tagName === "SELECT" ? HTMLSelectElement.prototype : el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, "value").set.call(el, nilai);
  el.dispatchEvent(new Event(el.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
});
function routeGet(peta) {
  mockGet.mockImplementation((u) => {
    const k = Object.keys(peta).find((x) => u.includes(x));
    return Promise.resolve({ data: k ? peta[k] : [] });
  });
}
afterEach(async () => {
  for (const r of roots) await act(async () => r.unmount());
  roots = []; document.body.innerHTML = "";
  mockGet.mockReset(); mockPost.mockReset(); mockToast.mockReset(); mockReason.mockReset();
  sessionStorage.clear();
});
const jumlahMuat = () => mockGet.mock.calls.filter(([u]) => String(u).includes("/sales-admin/desk")).length;

const TANPA = { ref_type: "customer", ref_id: "c1", number: "CUS-1", title: "Toko Baru", subtitle: "Bandung", value: 1, age_days: 4,
  entity_id: "ent_ksc", badge: "tanpa sales", action: "Tetapkan sales", action_kind: "open" };
const TAGIH = { ref_type: "sales_order", ref_id: "so1", number: "SO-1", title: "Toko D", value: 700000, entity_id: "ent_ksc",
  action: "Follow-up", action_kind: "open", age_days: 9, age_kind: "overdue", badge: "lewat", customer_id: "cus1", order_id: "so1", reminded: false };
const TAGIH_SUDAH = { ...TAGIH, ref_id: "so2", number: "SO-2", order_id: "so2", reminded: true, badge: "sudah diingatkan" };
const PIN = { ref_type: "internal_request", ref_id: "ir1", number: "PIN-1", title: "Toko Kanda", value: 3, entity_id: "ent_ksc",
  action: "Tindak", action_kind: "open", age_days: 2 };
const MANAJER = { ref_type: "sales_order", ref_id: "so5", number: "SO-5", title: "Toko M", value: 900000, entity_id: "ent_ksc",
  action: "Lihat", action_kind: "open", age_days: 1 };
const DITOLAK = { ...MANAJER, ref_id: "so6", number: "SO-6", title: "Toko H" };
const RETUR = { ref_type: "sales_return", ref_id: "rt1", number: "RT-1", title: "Toko R", value: 1, entity_id: "ent_ksc",
  action: "Proses", action_kind: "open", age_days: 1 };
const DESK = { queues: [
  { id: "pelanggan_tanpa_sales", label: "Pelanggan tanpa sales", count: 1, value_kind: "qty", rows: [TANPA] },
  { id: "jatuh_tempo", label: "Jatuh tempo & pengingat", count: 2, rows: [TAGIH, TAGIH_SUDAH] },
  { id: "permintaan_internal", label: "Permintaan internal", count: 1, rows: [PIN] },
  { id: "retur", label: "Retur", count: 1, rows: [RETUR] },
  { id: "harga_ditolak", label: "Harga ditolak", count: 1, rows: [DITOLAK] },
  { id: "menunggu_manajer", label: "Menunggu manajer", count: 1, rows: [MANAJER] },
], not_my_desk: [] };
const SALES = [{ id: "s1", name: "Sari" }, { id: "s2", name: "Budi" }];
const PETA = { "/sales-admin/desk": DESK, "/sales-users": SALES };
const PERMS = { sales_force: ["assign"], order: ["update", "view"], internal_request: ["reject", "convert"], customer: ["view"] };
const ADMIN = { permissions: PERMS };
const TANPA_IZIN = { permissions: { order: ["view"], customer: ["view"] } };

test("tetapkan sales: berizin → dialog; sales wajib, alasan opsional; kirim body benar; toast; kartu dimuat ulang", async () => {
  routeGet(PETA);
  mockPost.mockResolvedValue({ data: {} });
  await mount(<SalesAdminDesk currentUser={ADMIN} selectedEntity="ent_ksc" onOpenDocument={() => {}} />);
  const awal = jumlahMuat();
  await klik("desk-action-c1"); await tunggu();
  expect(q("assign-sales-dialog")).not.toBeNull();
  expect(mockGet.mock.calls.some(([u]) => String(u).includes("/sales-users"))).toBe(true);
  await klik("assign-sales-dialog-submit");
  expect(mockPost).not.toHaveBeenCalled();
  expect(teks(q("assign-sales-dialog-error"))).toContain("Pilih sales");
  await ubah("assign-sales-select", "s2");
  // Alasan opsional (sama dengan server & kartu pelanggan): kosong boleh kirim.
  await ubah("assign-sales-reason", "wilayah Bandung");
  await klik("assign-sales-dialog-submit"); await tunggu();
  expect(mockPost).toHaveBeenCalledWith("/api/customers/c1/reassign", { assigned_sales_id: "s2", reason: "wilayah Bandung" });
  expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: expect.stringContaining("Toko Baru") }));
  expect(q("assign-sales-dialog")).toBeNull();
  expect(jumlahMuat()).toBeGreaterThan(awal);
});

test("tetapkan sales: galat server tampil di dalam dialog; dialog tetap terbuka; tanpa toast", async () => {
  routeGet(PETA);
  mockPost.mockRejectedValue({ response: { status: 400, data: { detail: "Salesperson tujuan tidak valid" } } });
  await mount(<SalesAdminDesk currentUser={ADMIN} selectedEntity="ent_ksc" onOpenDocument={() => {}} />);
  await klik("desk-action-c1"); await tunggu();
  await ubah("assign-sales-select", "s1"); await ubah("assign-sales-reason", "alasan");
  await klik("assign-sales-dialog-submit"); await tunggu();
  expect(teks(q("assign-sales-dialog-error"))).toContain("Salesperson tujuan tidak valid");
  expect(q("assign-sales-dialog")).not.toBeNull();
  expect(mockToast).not.toHaveBeenCalled();
});

test("tetapkan sales: tanpa izin sales_force.assign → navigasi lama lewat pop-up (ikon pindah layar), tanpa dialog & tanpa /sales-users", async () => {
  routeGet(PETA);
  const open = jest.fn();
  await mount(<SalesAdminDesk currentUser={TANPA_IZIN} selectedEntity="ent_ksc" onOpenDocument={open} />);
  await klik("desk-action-c1"); await tunggu();
  expect(q("assign-sales-dialog")).toBeNull();
  expect(q("desk-detail")).not.toBeNull();
  expect(q("desk-detail-action-nav")).not.toBeNull();
  await klik("desk-detail-action");
  expect(open).toHaveBeenCalledWith(expect.objectContaining({ view: "customers-crm", focus_id: "c1" }));
  expect(mockGet.mock.calls.some(([u]) => String(u).includes("/sales-users"))).toBe(false);
});

test("panel pop-up antrean pelanggan_tanpa_sales terdaftar (CustomerQueuePanel) dan memuat fakta pelanggan", async () => {
  expect(DESK_PANELS["queue:pelanggan_tanpa_sales"]).toBeTruthy();
  expect(panelFor(TANPA, { id: "pelanggan_tanpa_sales" })).toBe(DESK_PANELS["queue:pelanggan_tanpa_sales"]);
  routeGet(PETA);
  await mount(<SalesAdminDesk currentUser={TANPA_IZIN} selectedEntity="ent_ksc" onOpenDocument={() => {}} />);
  await klik("desk-number-c1");
  expect(q("desk-customer-panel")).not.toBeNull();
  expect(teks(q("desk-detail-field-subtitle"))).toContain("Bandung");
});

test("jatuh tempo: belum diingatkan + order.update → 'Catat sudah diingatkan' POST mark; toast; kartu dimuat ulang", async () => {
  routeGet(PETA);
  mockPost.mockResolvedValue({ data: {} });
  await mount(<SalesAdminDesk currentUser={ADMIN} selectedEntity="ent_ksc" onOpenDocument={() => {}} />);
  const awal = jumlahMuat();
  expect(teks(q("desk-action-so1"))).toBe("Catat sudah diingatkan");
  await klik("desk-action-so1"); await tunggu();
  expect(mockPost).toHaveBeenCalledWith("/api/collection-reminders/mark",
    { customer_id: "cus1", order_id: "so1", note: "Pengingat penagihan SO-1" });
  expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: expect.stringContaining("Toko D") }));
  expect(jumlahMuat()).toBeGreaterThan(awal);
});

test("jatuh tempo: sudah diingatkan atau tanpa order.update → tetap Follow-up (navigasi lama)", async () => {
  routeGet(PETA);
  const open = jest.fn();
  await mount(<SalesAdminDesk currentUser={ADMIN} selectedEntity="ent_ksc" onOpenDocument={open} />);
  expect(teks(q("desk-action-so2"))).toBe("Follow-up");
  await klik("desk-action-so2");
  expect(q("desk-detail")).not.toBeNull();
  expect(mockPost).not.toHaveBeenCalled();
  await act(async () => { q("desk-detail-close-x").click(); });
  for (const r of roots) await act(async () => r.unmount()); roots = [];
  await mount(<SalesAdminDesk currentUser={TANPA_IZIN} selectedEntity="ent_ksc" onOpenDocument={open} />);
  expect(teks(q("desk-action-so1"))).toBe("Follow-up");
});

test("jatuh tempo: galat catat tampil di kotak galat meja, tanpa toast", async () => {
  routeGet(PETA);
  mockPost.mockRejectedValue({ response: { status: 500, data: { detail: "Gagal mencatat." } } });
  await mount(<SalesAdminDesk currentUser={ADMIN} selectedEntity="ent_ksc" onOpenDocument={() => {}} />);
  await klik("desk-action-so1"); await tunggu();
  expect(teks(q("desk-error"))).toContain("Gagal mencatat.");
  expect(mockToast).not.toHaveBeenCalled();
});

test("permintaan internal: 'Tolak' di pop-up; batal di askReason = tanpa panggilan; alasan → POST reject; Tindak tetap pindah layar", async () => {
  routeGet(PETA);
  mockPost.mockResolvedValue({ data: {} });
  const open = jest.fn();
  await mount(<SalesAdminDesk currentUser={ADMIN} selectedEntity="ent_ksc" onOpenDocument={open} />);
  await klik("desk-action-ir1");                       // "Tindak" = pindah layar → pop-up dulu
  expect(q("desk-detail-action-nav")).not.toBeNull();
  expect(teks(q("desk-detail-action-0"))).toBe("Tolak");
  mockReason.mockResolvedValueOnce(null);
  await klik("desk-detail-action-0"); await tunggu();
  expect(mockReason).toHaveBeenCalledWith(expect.objectContaining({ title: expect.stringContaining("PIN-1") }));
  expect(mockPost).not.toHaveBeenCalled();
  await klik("desk-action-ir1");
  mockReason.mockResolvedValueOnce("stok dipakai pesanan sendiri");
  await klik("desk-detail-action-0"); await tunggu();
  expect(mockPost).toHaveBeenCalledWith("/api/internal-requests/ir1/reject", { reason: "stok dipakai pesanan sendiri" });
  expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: "PIN-1 ditolak." }));
  expect(open).not.toHaveBeenCalled();
});

test("permintaan internal: tanpa izin internal_request.reject tidak ada 'Tolak'", async () => {
  routeGet(PETA);
  await mount(<SalesAdminDesk currentUser={{ permissions: { internal_request: ["convert"] } }} selectedEntity="ent_ksc" onOpenDocument={() => {}} />);
  await klik("desk-action-ir1");
  expect(q("desk-detail-action-0")).toBeNull();
});

test("'Lihat' (menunggu manajer, harga ditolak) membuka pop-up saja: tanpa navigasi; layar penuh hanya lewat 'Buka layar penuh'", async () => {
  routeGet(PETA);
  const open = jest.fn();
  await mount(<SalesAdminDesk currentUser={ADMIN} selectedEntity="ent_ksc" onOpenDocument={open} />);
  await klik("desk-action-so6"); await tunggu();
  expect(q("desk-detail")).not.toBeNull();
  expect(q("desk-detail-action")).toBeNull();
  expect(open).not.toHaveBeenCalled();
  await klik("desk-detail-open-full");
  expect(open).toHaveBeenCalledWith(expect.objectContaining({ view: "orders", focus_id: "so6" }));
});

test("retur tetap pindah layar: pop-up dulu, aksi bertanda ikon pindah layar", async () => {
  routeGet(PETA);
  const open = jest.fn();
  await mount(<SalesAdminDesk currentUser={ADMIN} selectedEntity="ent_ksc" onOpenDocument={open} />);
  await klik("desk-action-rt1");
  expect(q("desk-detail-action-nav")).not.toBeNull();
  expect(open).not.toHaveBeenCalled();
});

// ── HP ──
test("HP: tetapkan sales (berizin) → dialog yang sama; kirim; toast; antrean dimuat ulang", async () => {
  routeGet(PETA);
  mockPost.mockResolvedValue({ data: {} });
  await mount(<MobileSalesAdminDesk selectedEntity="ent_ksc" currentUser={ADMIN} />);
  const awal = jumlahMuat();
  await klik("m-desk-action-pelanggan_tanpa_sales-c1"); await tunggu();
  expect(q("assign-sales-dialog")).not.toBeNull();
  await ubah("assign-sales-select", "s1"); await ubah("assign-sales-reason", "wilayah");
  await klik("assign-sales-dialog-submit"); await tunggu();
  expect(mockPost).toHaveBeenCalledWith("/api/customers/c1/reassign", { assigned_sales_id: "s1", reason: "wilayah" });
  expect(mockToast).toHaveBeenCalled();
  expect(jumlahMuat()).toBeGreaterThan(awal);
});

test("HP: catat sudah diingatkan, tolak PIN dari pop-up, 'Lihat' hanya pop-up", async () => {
  routeGet(PETA);
  mockPost.mockResolvedValue({ data: {} });
  const onOpenOrder = jest.fn();
  await mount(<MobileSalesAdminDesk selectedEntity="ent_ksc" currentUser={ADMIN} onOpenOrder={onOpenOrder} />);
  await klik("m-desk-action-jatuh_tempo-so1"); await tunggu();
  expect(mockPost).toHaveBeenCalledWith("/api/collection-reminders/mark", expect.objectContaining({ customer_id: "cus1", order_id: "so1" }));
  mockPost.mockClear();
  await klik("m-desk-number-permintaan_internal-ir1");
  mockReason.mockResolvedValueOnce("tidak ada stok");
  await klik("m-desk-detail-action-0"); await tunggu();
  expect(mockPost).toHaveBeenCalledWith("/api/internal-requests/ir1/reject", { reason: "tidak ada stok" });
  await klik("m-desk-action-menunggu_manajer-so5");
  expect(q("m-desk-detail")).not.toBeNull();
  expect(onOpenOrder).not.toHaveBeenCalled();
});

test("HP: tanpa izin assign → pop-up dulu (tujuan layar desktop), tanpa dialog", async () => {
  routeGet(PETA);
  await mount(<MobileSalesAdminDesk selectedEntity="ent_ksc" currentUser={TANPA_IZIN} />);
  await klik("m-desk-action-pelanggan_tanpa_sales-c1");
  expect(q("assign-sales-dialog")).toBeNull();
  expect(q("m-desk-detail")).not.toBeNull();
});

test("berkas baru: tanpa text-[Npx], hex mentah, <button> bergaya sendiri, DetailPopup", () => {
  for (const f of ["../sales_admin/AssignSalesDialog.jsx", "../desks/CustomerQueuePanel.jsx"]) {
    const src = fs.readFileSync(path.join(__dirname, f), "utf8");
    expect(src).not.toMatch(/text-\[\d+px\]/);
    expect(src).not.toMatch(/#[0-9a-fA-F]{6}\b/);
    expect(src).not.toMatch(/DetailPopup|window\.(alert|confirm|prompt)/);
    expect(src).not.toMatch(/<button[^>]*className="(?!(primary|secondary|link|icon)-button)/);
  }
});

test("tetapkan sales: alasan kosong tetap terkirim (opsional)", async () => {
  routeGet(PETA);
  mockPost.mockResolvedValue({ data: {} });
  await mount(<SalesAdminDesk currentUser={ADMIN} selectedEntity="ent_ksc" onOpenDocument={() => {}} />);
  await klik("desk-action-c1"); await tunggu();
  await ubah("assign-sales-select", "s2");
  await klik("assign-sales-dialog-submit"); await tunggu();
  expect(mockPost).toHaveBeenCalledWith("/api/customers/c1/reassign", { assigned_sales_id: "s2", reason: "" });
});
