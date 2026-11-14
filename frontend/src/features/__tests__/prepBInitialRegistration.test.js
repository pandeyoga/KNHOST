// PREP-B — opname awal: pendaftaran ulang stok dari fisik per gedung (KEPUTUSAN_GATE_RFID §8).
// Helper (EPC kanonik, tempel banyak kode, cakupan), metode "Pendaftaran awal" di tab Stock Opname (D-15 tetap:
// Sapu RFID hanya untuk peran RFID), rincian sesi (rekonsiliasi + persetujuan per produk), layar HP (EPC → simpan).
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import StockOpnameTab from "../wms/StockOpnameTab";
import RegistrationDetail from "../inventory/registration/RegistrationDetail";
import MobileRegistration from "../mobile/MobileRegistration";
import { canonicalEpc, scopeOptions, splitCodes } from "../inventory/registration/registrationApi";
import { AppNavProvider } from "../../context/AppNavContext";
import { setAccessContext } from "../../config/roles";

// PR-T7 — `canCurrent` kini "tidak" selama konteks izin belum dimuat (dulu "boleh"); suite ini menguji tata letak &
// alur layar dengan izin penuh seperti sebelumnya, jadi konteks diisi sebagai Admin yang sudah masuk.
beforeAll(() => setAccessContext({ role: "admin" }));
afterAll(() => setAccessContext(null));

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: jest.fn(async () => true),
  askReason: jest.fn(async () => "ACC hasil pendaftaran"),
}));
const axios = require("../../services/apiClient").default;
const confirm = require("../../services/confirmService");
// CRA `resetMocks` mengosongkan implementasi tiruan sebelum tiap uji — dipasang ulang di sini.
beforeEach(() => { confirm.askConfirm.mockResolvedValue(true); confirm.askReason.mockResolvedValue("ACC hasil pendaftaran"); });

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
let host; let root;
async function mount(el) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(el); });
  await flush(); await flush();
}
afterEach(async () => {
  if (root) await act(async () => { root.unmount(); });
  host?.remove(); root = null;
  ["get", "post", "patch", "delete"].forEach((m) => axios[m].mockReset());
  try { localStorage.clear(); } catch { /* abaikan */ }
});
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
function setValue(el, value) {
  const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}
const routes = (map) => axios.get.mockImplementation((url) => {
  const key = Object.keys(map).find((k) => url.endsWith(k));
  return Promise.resolve({ data: key ? map[key] : [] });
});
const EPC1 = "E2AABBCC0000000000000001";

describe("helper", () => {
  test("EPC kanonik sama dengan server: pemisah/huruf kecil diterima, panjang salah ditolak", () => {
    expect(canonicalEpc("e2aa-bbcc-0000-0000-0000-0001")).toBe(EPC1);
    expect(canonicalEpc("E2AABB")).toBe("");
    expect(canonicalEpc("ZZAABBCC0000000000000001")).toBe("");
  });
  test("tempel banyak kode: pisah baris/spasi/koma, kembar dibuang", () => {
    expect(splitCodes(`${EPC1}\n${EPC1}, ABC ; DEF`)).toEqual([EPC1, "ABC", "DEF"]);
  });
  test("cakupan = zona + rak", () => {
    const o = scopeOptions([{ id: "z1", name: "Zona A", racks: [{ id: "r1", name: "Rak 1" }] }]);
    expect(o.map((x) => [x.id, x.kind])).toEqual([["z1", "zona"], ["r1", "rak"]]);
    expect(o[1].label).toBe("Zona A › Rak 1");
  });
});

describe("tab Stock Opname — metode Pendaftaran awal", () => {
  test("peran gudang: chip ketiga di baris metode RFID; pilih → onMethodChange('register')", async () => {
    routes({});
    const picked = [];
    await mount(<AppNavProvider role="warehouse"><StockOpnameTab method="count" onMethodChange={(m) => picked.push(m)} warehouses={[]}
      cycleCountProps={{ token: "x", warehouses: [], products: [] }} /></AppNavProvider>);
    expect(q("wms-opname-method-row")).not.toBeNull();
    await act(async () => { q("wms-opname-method-register").click(); });
    expect(picked).toEqual(["register"]);
  });
  test("manajer (tanpa menu RFID): baris metode sendiri tanpa Sapu RFID; metode register → panel pendaftaran", async () => {
    routes({ "/registration/sessions": [{ id: "s1", number: "KSC/REG-00001", status: "running", warehouse_name: "Woven", registration: { node_labels: ["Zona A"] }, freeze: { active: true } }] });
    await mount(<AppNavProvider role="manager"><StockOpnameTab method="register" warehouses={[]}
      cycleCountProps={{ token: "x", warehouses: [], products: [] }} /></AppNavProvider>);
    expect(q("wms-opname-method-row")).toBeNull();
    expect(q("wms-opname-register-row")).not.toBeNull();
    expect(q("wms-opname-method-rfid")).toBeNull();
    expect(q("reg-panel")).not.toBeNull();
    expect(q("reg-session-s1").textContent).toContain("KSC/REG-00001");
  });
});

describe("rincian sesi — rekonsiliasi & persetujuan per produk", () => {
  const session = { id: "s1", number: "KSC/REG-00001", name: "Uji", status: "pending_approval", warehouse_name: "Woven",
    registration: { node_labels: ["Zona A"], groups: {} }, freeze: { active: true, label: "Zona A", since: "2026-11-08T10:00:00" },
    freeze_mode_label: "Beku per zona/rak", epc_mode_label: "EPC bawaan tag dibaca",
    progress: { racks: [{ rack_id: "r1", rack: "Rak A1", zone: "Zona A", bins: 2, lines: 3, done: true }], racks_total: 1, racks_done: 1, lines: 3, unmapped: 1, unverified_length: 1, pending_write: 0 } };
  const rec = { totals: { reused_rolls: 1, new_rolls: 1, missing_rolls: 1, value_net: -120 }, policy: "K-OPN-01",
    groups: [{ key: "p1|ent_ksc", product_id: "p1", sku: "SKU-1", product_name: "Katun", owner_entity_id: "ent_ksc", unit: "yard",
      old_rolls: 2, old_qty: 90, registered_rolls: 2, registered_qty: 80, reuse: 1, new: 1, missing_rolls: 1, unverified_length: 1,
      unit_cost: 10, cost_basis: "wac_gudang", value_net: -120, notes: [], result: null }],
    unmapped: [{ id: "l9", bin_code: "A1-01", qty: 10, unit: "yard", note: "biru bunga", has_photo: false }] };
  test("penyetuju melihat kelompok produk, baris belum dikenali, dan menyetujui satu produk", async () => {
    routes({ "/registration/sessions/s1": session, "/registration/sessions/s1/reconcile": rec });
    axios.post.mockResolvedValue({ data: { complete: false, results: {} } });
    await mount(<RegistrationDetail sessionId="s1" />);
    expect(q("reg-detail-status").textContent).toBe("Menunggu persetujuan");
    expect(q("reg-freeze").textContent).toContain("Zona A");
    expect(q("reg-group-p1").textContent).toContain("SKU-1");
    expect(q("reg-group-p1").textContent).toContain("2 roll");
    expect(q("reg-unmapped-l9")).not.toBeNull();
    await act(async () => { q("reg-approve-p1").click(); });
    await flush(); await flush();
    const call = axios.post.mock.calls.find((c) => c[0].endsWith("/registration/sessions/s1/approve"));
    expect(call[1]).toMatchObject({ group_keys: ["p1|ent_ksc"], reason: "ACC hasil pendaftaran", accept_exceptions: false });
  });
});

describe("HP — Daftar Awal", () => {
  const sess = (mode) => [{ id: "s1", number: "KSC/REG-00001", warehouse_name: "Woven", status: "running", registration: { epc_mode: mode } }];
  const bins = { bins: [{ id: "b1", code: "A1-01", rack_id: "r1", rack: "Rak A1", zone: "Zona A" }] };
  test("EPC dipindai (Enter) → antre; produk belum dikenali + keterangan → simpan mengirim EPC & bin aktif", async () => {
    localStorage.setItem("kn_reg_bin_s1", "b1");
    routes({ "/registration/sessions": sess("read"), "/registration/sessions/s1/bins": bins, "/registration/sessions/s1/lines": { lines: [] } });
    axios.post.mockImplementation((url, body) => Promise.resolve({ data: url.endsWith("/epc-check")
      ? { results: body.codes.map((e) => ({ epc: e, ok: true })) }
      : { id: "l1", epc_display: "E2AA-…", bin_code: "A1-01", qty: null, qty_input: 12, unit_input: "yard", status: "draft", tag_state: "read" } }));
    await mount(<MobileRegistration />);
    const epc = q("mreg-epc");
    await act(async () => { setValue(epc, EPC1.toLowerCase()); });
    await act(async () => { epc.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })); });
    await flush();
    expect(q("mreg-queue").textContent).toContain(EPC1);
    await act(async () => { q("mreg-unrec").click(); });
    await act(async () => { setValue(q("mreg-note"), "kain biru motif bunga"); setValue(q("mreg-qty"), "12"); });
    expect(q("mreg-length-state").textContent).toContain("belum terverifikasi");
    await act(async () => { q("mreg-save").click(); });
    await flush();
    const save = axios.post.mock.calls.find((c) => c[0].endsWith("/registration/sessions/s1/lines"));
    expect(save[1]).toMatchObject({ epc: EPC1, bin_id: "b1", unrecognized: true, note: "kain biru motif bunga", qty: 12 });
    expect(q("mreg-line-l1")).not.toBeNull();
  });
  test("mode EPC sistem: tanpa kolom EPC, simpan tanpa EPC, tombol 'Tag sudah ditulis'", async () => {
    localStorage.setItem("kn_reg_bin_s1", "b1");
    routes({ "/registration/sessions": sess("system"), "/registration/sessions/s1/bins": bins, "/registration/sessions/s1/lines": { lines: [] } });
    axios.post.mockResolvedValue({ data: { id: "l2", epc_display: "E2FF-…", bin_code: "A1-01", qty_input: 5, unit_input: "yard", status: "draft", tag_state: "pending_write" } });
    await mount(<MobileRegistration />);
    expect(q("mreg-epc")).toBeNull();
    expect(q("mreg-system-epc")).not.toBeNull();
    await act(async () => { q("mreg-unrec").click(); });
    await act(async () => { setValue(q("mreg-note"), "abu polos"); setValue(q("mreg-qty"), "5"); });
    await act(async () => { q("mreg-save").click(); });
    await flush();
    const save = axios.post.mock.calls.find((c) => c[0].endsWith("/lines"));
    expect(save[1].epc).toBeUndefined();
    expect(q("mreg-written-l2")).not.toBeNull();
    expect(q("mreg-msg").textContent).toContain("Tulis EPC");
  });
  test("tanpa sesi berjalan → petunjuk, bukan form kosong", async () => {
    routes({ "/registration/sessions": [] });
    await mount(<MobileRegistration />);
    expect(q("mreg-empty")).not.toBeNull();
  });
});
