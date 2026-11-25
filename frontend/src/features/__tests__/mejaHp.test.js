// MEJA-16 — §5.8: baris HP bisa disentuh → pop-up rincian yang sama; huruf ≥ 12 px; kartu tetap bisa dibuka-tutup.
import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";
import MobileSalesAdminDesk from "../sales/mobile/MobileSalesAdminDesk";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), patch: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } } },
  API: "/api",
  setActiveEntity: () => {}, setAuthToken: () => {},
}));
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: () => {} }));
jest.mock("../sales_admin/VerifyOrderDialog", () => (p) => <div data-testid="verify-stub">{p.orderId}</div>);
jest.mock("../sales_admin/FulfillmentDecisionDialog", () => () => null);
jest.mock("../sales_admin/KeepPendingPanel", () => () => null);

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const teks = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");
let roots = [];
async function mount(el) {
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host); roots.push(root);
  await act(async () => { root.render(el); }); await act(async () => {}); await act(async () => {});
}
const klik = async (id) => act(async () => { q(id).dispatchEvent(new MouseEvent("click", { bubbles: true })); });
function routeGet(peta) {
  mockGet.mockImplementation((u) => {
    const k = Object.keys(peta).find((x) => u.includes(x));
    return Promise.resolve({ data: k ? peta[k] : [] });
  });
}
afterEach(async () => {
  for (const r of roots) await act(async () => r.unmount());
  roots = []; document.body.innerHTML = ""; mockGet.mockReset(); sessionStorage.clear();
});

const PANJANG = "Alamat kirim pindah ke gudang baru di Jl. Raya Soekarno-Hatta 117, minta telepon dulu sebelum antar.";
const DESK = { not_my_desk: ["Faktur Pajak keluaran"], queues: [{ id: "perlu_verifikasi", label: "Perlu diperiksa", count: 1, rows: [
  { ref_type: "sales_order", ref_id: "so1", number: "SO-1", title: "Toko A", subtitle: PANJANG, age_days: 1, value: 1000,
    action: "Periksa & lepas", action_kind: "verify", entity_id: "ent_ksc" }] }] };

test("sentuh baris → rincian utuh (sekali); tombol aksi tidak membuka rincian", async () => {
  routeGet({ "/sales-admin/desk": DESK });
  await mount(<MobileSalesAdminDesk selectedEntity="ent_ksc" />);
  expect(q("m-desk-row-perlu_verifikasi-so1").getAttribute("role")).toBeNull();   // R18: baris bukan kontrol
  await klik("m-desk-row-perlu_verifikasi-so1");
  expect(document.body.querySelectorAll('[data-testid="m-desk-detail"]')).toHaveLength(1);
  expect(q("m-desk-detail-field-subtitle").textContent).toContain(PANJANG);
  await act(async () => { q("m-desk-detail-close-x").click(); });
  await klik("m-desk-action-perlu_verifikasi-so1");
  expect(q("m-desk-detail")).toBeNull();
  expect(teks(q("verify-stub"))).toBe("so1");
  expect(document.body.querySelectorAll('[data-testid="verify-stub"]')).toHaveLength(1);
});

test("aksi baris: tujuan layar desktop buka pop-up dulu; tujuan layar HP langsung pindah", async () => {
  const onOpenFull = jest.fn(); const onOpenOrder = jest.fn();
  const baris = (ref_type, ref_id) => ({ ref_type, ref_id, number: `N-${ref_id}`, title: "T", age_days: 1, value: 1, action: "Buka", action_kind: "open" });
  routeGet({ "/sales-admin/desk": { queues: [{ id: "k", label: "K", count: 2, rows: [baris("tax_invoice", "x1"), baris("sales_order", "so9")] }] } });
  await mount(<MobileSalesAdminDesk selectedEntity="ent_ksc" onOpenFull={onOpenFull} onOpenOrder={onOpenOrder} />);
  await klik("m-desk-action-k-x1");
  expect(q("m-desk-detail")).not.toBeNull(); expect(onOpenFull).not.toHaveBeenCalled();
  await klik("m-desk-detail-action");
  expect(q("m-desk-detail")).toBeNull(); expect(onOpenFull).toHaveBeenCalledTimes(1); expect(q("m-desk-detail")).toBeNull();
  await klik("m-desk-action-k-so9");
  expect(onOpenOrder).toHaveBeenCalledWith("so9"); expect(q("m-desk-detail")).toBeNull();
});

test("tombol nomor dokumen (jalur papan ketik) membuka rincian", async () => {
  routeGet({ "/sales-admin/desk": DESK });
  await mount(<MobileSalesAdminDesk selectedEntity="ent_ksc" />);
  const n = q("m-desk-number-perlu_verifikasi-so1");
  expect(n.tagName).toBe("BUTTON");
  await klik("m-desk-number-perlu_verifikasi-so1");
  expect(document.body.querySelectorAll('[data-testid="m-desk-detail"]')).toHaveLength(1);
});

test("kartu tetap bisa dibuka-tutup; ? menggantikan kotak 'Meja Finance'", async () => {
  routeGet({ "/sales-admin/desk": DESK });
  await mount(<MobileSalesAdminDesk selectedEntity="ent_ksc" />);
  expect(q("m-desk-not-mine")).toBeNull();
  await klik("m-desk-help");
  expect(teks(q("m-desk-help-text"))).toMatch(/Bukan wewenang meja ini: Faktur Pajak keluaran \(ada di Meja Keuangan\)/);
  expect(document.body.textContent).not.toContain("Meja Finance");
  await klik("m-desk-queue-toggle-perlu_verifikasi");
  expect(q("m-desk-row-perlu_verifikasi-so1")).toBeNull();
});

test("huruf ≥ 12 px di meja HP Admin Sales & HP MD", () => {
  const as = fs.readFileSync(path.join(__dirname, "../sales/mobile/MobileSalesAdminDesk.jsx"), "utf8");
  expect(as).not.toMatch(/text-\[\d/);
  const md = fs.readFileSync(path.join(__dirname, "../sales/mobile/MobileMdViews.jsx"), "utf8");
  const blok = md.slice(md.indexOf("export function MobileMdDesk"), md.indexOf("export const mdRowTarget"));
  expect(blok).not.toMatch(/text-\[(?:\d|1[01])(?:\.\d+)?px\]/);
});
