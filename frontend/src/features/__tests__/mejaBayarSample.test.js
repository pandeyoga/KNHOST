// MEJA-11 — §5.4: setujui bayar sample = cek uang masuk + konfirmasi, sama di daftar & meja.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import SampleAdminDesk from "../samples/SampleAdminDesk";
import SampleOrdersView from "../samples/SampleOrdersView";
import SamplePaymentApproveDialog from "../samples/SamplePaymentApproveDialog";
import { cekUangMasukSample } from "../samples/samplePayment";
import fs from "fs";
import path from "path";

const mockToast = jest.fn();
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: (...a) => mockToast(...a) }));
jest.mock("../samples/sampleApi", () => ({
  sampleDesk: jest.fn(), approveSamplePayment: jest.fn(), confirmSampleOrder: jest.fn(), listSampleOrders: jest.fn(),
  sampleStats: jest.fn().mockResolvedValue({}), cancelSampleOrder: jest.fn(),
}));
jest.mock("../sales_admin/SoTrackerCard", () => () => <div data-testid="so-tracker-stub" />);
jest.mock("../samples/CatalogueCreateModal", () => () => null);
jest.mock("../samples/CatalogueComponents", () => () => null);
jest.mock("../samples/CuttingDesk", () => () => null);
jest.mock("../samples/CuttingLocations", () => () => null);
const api = require("../samples/sampleApi");

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
afterEach(async () => {
  for (const r of roots) await act(async () => r.unmount());
  roots = []; document.body.innerHTML = "";
  mockToast.mockReset(); sessionStorage.clear();
});

function berkasSumber(dir = path.join(__dirname, "..", "..")) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((d) => {
    const p = path.join(dir, d.name);
    if (d.isDirectory()) return d.name === "__tests__" ? [] : berkasSumber(p);
    return /\.jsx?$/.test(d.name) ? [p] : [];
  });
}
const baca = (f) => fs.readFileSync(f, "utf8");

test("cekUangMasukSample", () => {
  expect(cekUangMasukSample({ sample_billing: "paid", grand_total: 83250, paid_total: 50000 }))
    .toEqual({ total: 83250, masuk: 50000, kurang: 33250 });
  expect(cekUangMasukSample({ sample_billing: "free", grand_total: 0 }).kurang).toBe(0);
});

test("meja: uang kurang → peringatan & 'Tetap setujui'; endpoint dipanggil sesudah konfirmasi", async () => {
  const baris = { ref_type: "sample_order", ref_id: "sos1", number: "KSC/SOS-1", title: "Toko S", age_days: 1, entity_id: "ent_ksc",
    action: "Setujui Bayar", action_kind: "approve_payment", sample_billing: "paid", grand_total: 83250, paid_total: 50000, badge: "waiting_approval" };
  api.sampleDesk.mockResolvedValue({ queues: [{ id: "bayar_sampel", label: "Bayar", count: 1, rows: [baris] }] });
  api.approveSamplePayment.mockResolvedValue({});
  await mount(<SampleAdminDesk currentUser={{ permissions: { sample_order: ["view", "approve_payment"] } }} onOpenDocument={() => {}} />);
  await klik("sample-desk-action-sos1");
  expect(api.approveSamplePayment).not.toHaveBeenCalled();
  expect(teks(q("sample-approve-short"))).toMatch(/kurang Rp\s?33\.250/);
  expect(teks(q("sample-approve-submit"))).toBe("Tetap setujui");
  await klik("sample-approve-submit");
  expect(api.approveSamplePayment).toHaveBeenCalledWith("sos1");
  expect(mockToast).toHaveBeenCalled();
});

test("lunas: tanpa peringatan, tombol 'Setujui pembayaran'", async () => {
  await mount(<SamplePaymentApproveDialog order={{ id: "s2", number: "SOS-2", sample_billing: "paid", grand_total: 10000, paid_total: 10000 }}
    onClose={() => {}} onDone={() => {}} />);
  expect(q("sample-approve-short")).toBeNull();
  expect(teks(q("sample-approve-submit"))).toBe("Setujui pembayaran");
});

test("galat di dalam pop-up; pop-up tetap terbuka", async () => {
  api.approveSamplePayment.mockRejectedValueOnce({ response: { data: { detail: "Sudah disetujui orang lain." } } });
  const onDone = jest.fn();
  await mount(<SamplePaymentApproveDialog order={{ id: "s3", number: "SOS-3", sample_billing: "paid", grand_total: 10000, paid_total: 10000 }}
    onClose={() => {}} onDone={onDone} />);
  await klik("sample-approve-submit");
  expect(teks(q("sample-approve-error"))).toContain("Sudah disetujui orang lain.");
  expect(q("sample-approve")).not.toBeNull();
  expect(onDone).not.toHaveBeenCalled();
});

test("daftar Pesanan Sample memakai pop-up yang sama (bukan askConfirm)", async () => {
  api.approveSamplePayment.mockClear();
  api.listSampleOrders.mockResolvedValue([{ id: "so1", number: "KSC/SOS-00029", customer_name: "Toko Kain Sejahtera",
    sample_billing: "paid", status: "waiting_approval", grand_total: 83250, paid_total: 50000, items: [], fulfillment_method: "kirim" }]);
  await mount(<SampleOrdersView user={{ role: "finance", permissions: { sample_order: ["view", "approve_payment"] } }}
    focusDoc={{ focus_type: "sample_order", focus_id: "so1" }} onClearFocus={() => {}} />);
  await klik("sample-detail-approve-payment");
  expect(q("sample-approve")).not.toBeNull();
  expect(q("sample-approve-short")).not.toBeNull();
  expect(api.approveSamplePayment).not.toHaveBeenCalled();
});

test("setiap pemanggil setujui bayar memakai SamplePaymentApproveDialog", () => {
  const salah = berkasSumber().filter((f) => !f.endsWith("features/samples/sampleApi.js") && /\bapproveSamplePayment\(/.test(baca(f))
    && !baca(f).includes("SamplePaymentApproveDialog"));
  expect(salah).toEqual([]);
});
