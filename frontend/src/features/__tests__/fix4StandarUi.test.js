/**
 * FIX-4 (audit WMS-RFID 9 Nov 2026) — Standar UI Gudang v1 tahap 1, sisi klien.
 *  · K-B4-07 / K-B3b-04 / EXP-01 — tombol baku "Unduh ▾" (ExportMenu): Excel (.xlsx) bawaan + CSV lewat
 *    `POST /export-center/quick`, isi = saringan + cari + cakupan daftar; > 50.000 baris → job + pemberitahuan;
 *    gagal = bilah ErrorNotice; saringan layar yang belum bisa diikuti → butir dinonaktifkan beralasan.
 *  · PaginationBar `exportSpec` → ExportMenu (CSV kolom-layar lama tetap untuk butir CSV).
 *  · EXP-03 — daftar Pengiriman tidak lagi membuat CSV koma sendiri.
 *  · K-B4-02 / UI-52 / UI-53 — aplikasi HP gudang: tombol aksi `btn-touch` (≥ 48 px), isian `kn-input-touch`,
 *    info keputusan ≥ 16 px (kelas `kn-hp-*`), tanpa `text-xs`.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import axios from "axios";
import fs from "fs";
import path from "path";
import { buildExportSpec, buildExportFilter, toCondition, exportFileName, fileNameFromDisposition } from "../../utils/exportSpec";
import ExportMenu from "../../components/ExportMenu";
import PaginationBar from "../../components/PaginationBar";
import { setAccessContext } from "../../config/roles";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};   // jsdom

let captured = [];
let respond = () => ({ status: 200, data: new Blob(["x"]), headers: {} });
const realAdapter = axios.defaults.adapter;
beforeEach(() => {
  captured = [];
  axios.defaults.adapter = async (config) => {
    captured.push(config);
    const r = await respond(config);
    if (r.status >= 400) {
      const err = new Error(`HTTP ${r.status}`);
      err.response = { status: r.status, data: r.data, headers: r.headers || {}, config };
      err.config = config;
      throw err;
    }
    return { data: r.data, status: r.status, statusText: "OK", headers: r.headers || {}, config };
  };
  global.URL.createObjectURL = jest.fn(() => "blob:x");
  global.URL.revokeObjectURL = jest.fn();
  setAccessContext({ role: "warehouse", permissions: { data_export: ["view", "export"], wms: ["view"] }, view_resources: {}, hidden_views: [] });
});
afterEach(() => setAccessContext(null));
afterAll(() => { axios.defaults.adapter = realAdapter; });

async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  return { host, root };
}
const $ = (host, sel) => host.querySelector(sel);
const click = async (node) => { await act(async () => { node.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); };
const flush = async () => { for (let i = 0; i < 4; i += 1) await act(async () => {}); };

describe("exportSpec — saringan & cakupan daftar → spesifikasi Pusat Export", () => {
  test("nilai kosong (chip 'Semua') diabaikan; 'in' memecah koma", () => {
    expect(toCondition(["status", "eq", ""])).toBeNull();
    expect(toCondition(false)).toBeNull();
    expect(toCondition(["status", "in", "draft,review"])).toEqual({ field: "status", cmp: "in", value: ["draft", "review"] });
    expect(toCondition(["bin_id", "empty"])).toEqual({ field: "bin_id", cmp: "empty" });
  });
  test("grup bersarang ATAU dipertahankan, butir kosong dibuang", () => {
    const f = buildExportFilter({ filters: [["flow_type", "eq", "outbound"],
      { op: "or", items: [false, ["task_subtype", "ne", "sample_cut"]] }] });
    expect(f).toEqual({ op: "and", items: [{ field: "flow_type", cmp: "eq", value: "outbound" },
      { op: "or", items: [{ field: "task_subtype", cmp: "ne", value: "sample_cut" }] }] });
  });
  test("badan permintaan: cakupan, cari, urut, tanggal, PT, lokasi", () => {
    const b = buildExportSpec({ dataset: "goods_receipts", format: "csv", label: "kedatangan", scope: "work",
      filters: [["status", "in", ["draft"]]], search: "  SJ-01 ", sort: [{ key: "created_at", dir: "desc" }],
      dateRange: { field: "created_at", from: "2026-11-01", to: "" }, entityId: "all", locationView: true });
    expect(b).toEqual({ dataset: "goods_receipts", format: "csv", label: "kedatangan", entity_scope: "work",
      filter: { op: "and", items: [{ field: "status", cmp: "in", value: ["draft"] }] }, search: "SJ-01",
      sort: [{ key: "created_at", dir: "desc" }], date_field: "created_at", date_from: "2026-11-01", location_view: true });
  });
  test("nama berkas: header server diutamakan, cadangan ber-stempel WIB", () => {
    expect(fileNameFromDisposition('attachment; filename="kedatangan_20261109_1405.xlsx"')).toBe("kedatangan_20261109_1405.xlsx");
    expect(exportFileName("Tugas Barang Keluar", "xlsx", new Date("2026-11-09T07:05:00Z"))).toBe("tugas-barang-keluar_20261109_1405.xlsx");
  });
});

describe("ExportMenu — tombol baku Unduh", () => {
  test("Excel memanggil /export-center/quick dengan saringan & cakupan daftar lalu mengunduh berkas", async () => {
    respond = () => ({ status: 200, data: new Blob(["xlsx"]), headers: { "content-disposition": 'attachment; filename="kedatangan_x.xlsx"', "x-export-rows": "12" } });
    const { host } = await mount(<ExportMenu dataset="goods_receipts" label="kedatangan" scope="work" testId="t"
      filters={[["status", "in", "draft,review"]]} search="SJ" />);
    await click($(host, "[data-testid='t-button']"));
    expect($(host, "[data-testid='t-menu']")).not.toBeNull();
    await click($(host, "[data-testid='t-xlsx']"));
    await flush();
    const call = captured.find((c) => c.url.endsWith("/export-center/quick"));
    expect(call).toBeTruthy();
    const body = JSON.parse(call.data);
    expect(body).toMatchObject({ dataset: "goods_receipts", format: "xlsx", entity_scope: "work", search: "SJ",
      filter: { op: "and", items: [{ field: "status", cmp: "in", value: ["draft", "review"] }] } });
    expect(call.responseType).toBe("blob");
    expect(global.URL.createObjectURL).toHaveBeenCalled();
  });

  test("lebih dari 50.000 baris → pemberitahuan job (bukan unduhan terpotong)", async () => {
    respond = () => ({ status: 202, data: new Blob([JSON.stringify({ mode: "job", total: 80000, message: "80.000 baris melebihi batas unduh langsung 50.000." })]) });
    const { host } = await mount(<ExportMenu dataset="inventory_movements" label="mutasi" testId="j" />);
    await click($(host, "[data-testid='j-button']"));
    await click($(host, "[data-testid='j-csv']"));
    await flush();
    expect($(host, "[data-testid='j-job']").textContent).toContain("50.000");
    expect(global.URL.createObjectURL).not.toHaveBeenCalled();
  });

  test("galat server tampil sebagai bilah menempel dengan pesan dari badan JSON", async () => {
    respond = () => ({ status: 403, data: new Blob([JSON.stringify({ detail: { message: "Peran petugas gudang hanya boleh mengunduh dataset gudang" } })]) });
    const { host } = await mount(<ExportMenu dataset="sales_orders" label="x" testId="e" />);
    await click($(host, "[data-testid='e-button']"));
    await click($(host, "[data-testid='e-xlsx']"));
    await flush();
    expect($(host, "[data-testid='e-error']").textContent).toContain("dataset gudang");
  });

  test("saringan yang belum bisa diikuti → butir server nonaktif beralasan; CSV kolom-layar tetap bisa", async () => {
    const legacy = jest.fn();
    const { host } = await mount(<ExportMenu dataset="inventory_rolls" label="roll" testId="u" legacyCsv={legacy}
      unsupported="Saringan cek MDQ belum bisa diikuti berkas Excel" />);
    await click($(host, "[data-testid='u-button']"));
    expect($(host, "[data-testid='u-xlsx']").disabled).toBe(true);
    expect($(host, "[data-testid='u-xlsx']").textContent).toContain("MDQ");
    await click($(host, "[data-testid='u-csv']"));
    expect(legacy).toHaveBeenCalled();
    expect(captured.length).toBe(0);
  });

  test("tanpa izin data_export.export tombol tidak ditawarkan", async () => {
    setAccessContext({ role: "qc", permissions: { inventory: ["view"] }, view_resources: {}, hidden_views: [] });
    const { host } = await mount(<ExportMenu dataset="wms_tasks" label="x" testId="n" />);
    expect($(host, "[data-testid='n']")).toBeNull();
  });
});

describe("PaginationBar — exportSpec memasang ExportMenu (satu menu, dua format)", () => {
  test("exportSpec + exportConfig → menu Excel (server) & CSV (kolom layar)", async () => {
    const { host } = await mount(<PaginationBar page={1} pageSize={20} total={3} testId="pg" label="roll"
      exportConfig={{ columns: [{ key: "a", header: "A" }], rows: [{ a: 1 }], fetchAll: async () => [{ a: 1 }], filename: "r" }}
      exportSpec={{ dataset: "inventory_rolls", label: "roll" }} />);
    expect($(host, "[data-testid='pg-export-button']")).not.toBeNull();
    await click($(host, "[data-testid='pg-export-button']"));
    expect($(host, "[data-testid='pg-export-xlsx']")).not.toBeNull();
    expect($(host, "[data-testid='pg-export-csv']").textContent).toContain("Kolom persis");
    expect($(host, "[data-testid='pg-bar']").className).toContain("kn-pager");
  });
  test("tanpa exportSpec tombol CSV lama tetap (testid lama)", async () => {
    const { host } = await mount(<PaginationBar page={1} pageSize={20} total={3} testId="old"
      exportConfig={{ columns: [{ key: "a", header: "A" }], rows: [{ a: 1 }], filename: "r" }} />);
    expect($(host, "button[data-testid='old-export']").textContent).toContain("Unduh CSV");
  });
});

describe("Standar UI Gudang v1 — sumber layar (statis)", () => {
  const read = (rel) => fs.readFileSync(path.join(__dirname, "..", "..", rel), "utf8");
  test("EXP-03 — Pengiriman tidak lagi membuat CSV koma sendiri", () => {
    const v = read("features/logistics/LogisticsView.jsx");
    const h = read("features/logistics/HistoryPanel.jsx");
    expect(v).not.toMatch(/new Blob\(\[\[head\.join\(","\)/);
    expect(h).not.toMatch(/new Blob\(\[\[head\.join\(","\)/);
    expect(v).toContain("<ExportMenu");
    expect(h).toContain("<ExportMenu");
  });
  test("HP gudang: aksi btn-touch, isian kn-input-touch, tanpa text-xs / py-2 pada tombol", () => {
    for (const rel of ["features/mobile/MobileWarehouseApp.jsx", "features/mobile/MobileTaskActions.jsx",
      "features/mobile/MobileRegistration.jsx", "features/mobile/OfflineBanner.jsx"]) {
      const src = read(rel);
      expect([rel, /\btext-xs\b/.test(src)]).toEqual([rel, false]);
      expect([rel, /className="(?:primary|secondary)-button[^"]*\bpy-[0-3]\b/.test(src)]).toEqual([rel, false]);
      expect([rel, /text-\[(?:9|10|11|12|13)(?:\.5)?px\]/.test(src)]).toEqual([rel, false]);
    }
    expect(read("features/mobile/MobileWarehouseApp.jsx")).toContain("btn-touch btn-primary-cta");
    expect(read("features/mobile/MobileTaskActions.jsx")).toContain("kn-input-touch");
  });
  test("token & kelas baku: tombol utama/bahaya memakai token AA, bukan #007AFF/#FF3B30", () => {
    const comp = read("styles/components.css");
    const rule = (sel) => {
      const i = comp.indexOf(`\n${sel} {`);
      return i < 0 ? "" : comp.slice(i, comp.indexOf("}", i) + 1);
    };
    expect(rule(".primary-button")).toContain("var(--kn-action)");
    expect(rule(".danger-button")).toContain("var(--kn-danger)");
    expect(rule(".primary-button")).not.toContain("--ios-blue");
    expect(read("styles/tokens.css")).toMatch(/--kn-action:\s*#0058CC/);
    expect(read("styles/standard.css")).toMatch(/\.btn-touch[\s\S]*min-height: var\(--touch-min\)/);
  });
});
