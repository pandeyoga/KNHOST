// KF-T2 — "Batas retur umum" (Kebijakan Retur) dan "Aturan jadwal bayar" (Antar-PT › Jadwal Bayar) kini kartu Pusat
// Pengaturan yang dikunci ke kuncinya, bukan form yang menulis `PUT /api/settings` (docs/blueprint/unit/KF-T2.md, Layar).
// Uji komponen pelengkap U15 (uji jalan peramban terpisah). Data = bentuk `GET /api/config/registry|effective`.
import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";
import ReturnGeneralLimits, { RETURN_LIMIT_KEYS } from "../sales/ReturnGeneralLimits";
import IntercoPaymentSchedule from "../finance/interco/IntercoPaymentSchedule";
import { configApi } from "../settings/config/configApi";
import { setAccessContext } from "../../config/roles";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    patch: () => Promise.resolve({ data: {} }), isCancel: () => false, defaults: { headers: { common: {} } } },
  API: "/api",
}));
// Pemilih bawaan (cmdk/radix) diganti <select> polos.
jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid }) => (
    <select data-testid={tid} value={value ?? ""} onChange={(e) => onValueChange?.(e.target.value)}>
      {options.map((o) => <option key={`${o.value}`} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: M, KNSelect: M };
});

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
let mounted = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  for (let i = 0; i < 6; i += 1) await act(async () => {});
  mounted.push({ host, root });
  return host;
}
afterEach(async () => {
  for (const m of mounted) { await act(async () => { m.root.unmount(); }); m.host.remove(); }
  mounted = [];
  mockGet.mockReset();
  jest.restoreAllMocks();
});

const item = (key, group, label, value, type = "duration") => ({
  key, group, label, value, default: value, type, status: "active", scopes: ["global", "entity"], help: "", impact: "",
  example: "", source_layer: "code_default", source_label: "Bawaan", can_edit: true, unit: type === "duration" ? "hari" : "",
  min: null, max: null, options: [], columns: [], row_shape: "",
});
const RETUR = [
  item("returns.customer_window_days", "retur", "Batas retur pelanggan sejak surat jalan", 21),
  item("returns.supplier_window_days", "retur", "Batas retur ke pemasok sejak barang diterima", 21),
  item("returns.supplier_reminder_days", "retur", "Ingatkan sebelum batas retur pemasok habis", 3),
  item("returns.bill_first", "retur", "Potong tagihan pesanan asal lebih dulu", true, "bool"),
  { ...item("returns.grade_price_factors", "retur", "Harga per grade (% dari harga produk)", { A: 100, B: 70 }, "table"), row_shape: "map" },
  item("returns.evidence_required_submit", "retur", "Bukti foto wajib sebelum retur diajukan", false, "bool"),
];
const ANTAR_PT = [
  item("interco_payment.cutoff_day", "antar-entitas", "Tanggal tutup tagihan antar-PT", 0, "int"),
  item("interco_payment.allow_netting", "antar-entitas", "Izinkan saling hapus hutang antar-PT", false, "bool"),
  item("antar_entitas.pricing_mode", "antar-entitas", "Mode harga antar-PT (bawaan)", "fixed_price", "text"),
];
const CAPS = { settings_manage: true, settings_view: true, global_write: true, read_scope: "" };
const TOLAK = { response: { status: 403, data: { detail: "Anda belum punya akses untuk melihat pengaturan." } } };

function spies(entries, group, { tolak = false } = {}) {
  if (tolak) {
    jest.spyOn(configApi, "registry").mockRejectedValue(TOLAK);
    jest.spyOn(configApi, "effective").mockRejectedValue(TOLAK);
  } else {
    jest.spyOn(configApi, "registry").mockResolvedValue({
      groups: [{ id: group, label: group, question: "?", count: entries.length }], entries, caps: CAPS });
    jest.spyOn(configApi, "effective").mockResolvedValue({ items: entries });
  }
  jest.spyOn(configApi, "health").mockResolvedValue({ rows: [] });
}

beforeEach(() => {
  setAccessContext({ role: "admin", permissions: {}, view_resources: {}, hidden_views: [] });
});

describe("KF-T2 · Batas retur umum (Kebijakan Retur)", () => {
  test("kartu Pusat Pengaturan untuk tepat lima kunci returns.*", async () => {
    spies(RETUR, "retur");
    const host = await mount(<ReturnGeneralLimits selectedEntity="ent_ksc" entities={[]} />);
    expect(q(host, "return-general-limits").textContent).toContain("Batas retur umum");
    for (const k of RETURN_LIMIT_KEYS) expect(q(host, `cfg-card-wrap-${k}`)).not.toBeNull();
    expect(q(host, "cfg-card-wrap-returns.evidence_required_submit")).toBeNull();
    expect(q(host, "return-limits-readonly")).toBeNull();
  });

  test("tanpa akses baca Pusat Pengaturan (403) → satu baris hanya-baca dari pengaturan efektif", async () => {
    spies([], "retur", { tolak: true });
    mockGet.mockImplementation((url) => Promise.resolve({
      data: url.includes("/settings/effective") ? { returns: { customer_window_days: 21, supplier_window_days: 14 } } : {} }));
    const host = await mount(<ReturnGeneralLimits selectedEntity="ent_ksc" entities={[]} />);
    expect(q(host, "return-limits-readonly").textContent.replace(/\s+/g, " ").trim())
      .toBe("Batas retur umum: pelanggan 21 hari sejak surat jalan · pemasok 14 hari sejak barang diterima.");
    expect(q(host, "cfg-card-wrap-returns.customer_window_days")).toBeNull();
    expect(q(host, "cfg-denied")).toBeNull();
  });
});

describe("KF-T2 · Aturan jadwal bayar (Antar-PT › Jadwal Bayar)", () => {
  const JADWAL = { rows: [], pairs: [], config: { allow_netting: false, require_full_payment: true, cutoff_day: null,
    payment_day: null, basis: null, reminder_days: 3 }, cutoff_status: "not_configured", netting: "disabled",
  note: "Cutoff & acuan periode pembayaran belum diatur — periode bayar & pengingat belum jalan." };

  test("kartu interco_payment.* menggantikan form lama; kunci antar-PT lain tidak ikut", async () => {
    spies(ANTAR_PT, "antar-entitas");
    mockGet.mockImplementation((url) => Promise.resolve({ data: url.includes("/interco/payment-schedule") ? JADWAL : {} }));
    const host = await mount(<IntercoPaymentSchedule selectedEntity="ent_ksc" entities={[]} />);
    expect(q(host, "interco-payment-rules").textContent).toContain("Aturan jadwal bayar");
    expect(q(host, "cfg-card-wrap-interco_payment.cutoff_day")).not.toBeNull();
    expect(q(host, "cfg-card-wrap-interco_payment.allow_netting")).not.toBeNull();
    expect(q(host, "cfg-card-wrap-antar_entitas.pricing_mode")).toBeNull();
    expect(q(host, "interco-cutoff-form")).toBeNull();
    expect(q(host, "interco-schedule-rules").textContent).toContain("saling hapus antar tagihan dinonaktifkan");
  });

  test("tanpa akses baca → bagian aturan tidak tampil; jadwal tetap tampil", async () => {
    spies([], "antar-entitas", { tolak: true });
    mockGet.mockImplementation((url) => Promise.resolve({
      data: url.includes("/interco/payment-schedule") ? { ...JADWAL, netting: "allowed",
        config: { ...JADWAL.config, allow_netting: true, require_full_payment: false } } : {} }));
    const host = await mount(<IntercoPaymentSchedule selectedEntity="ent_ksc" entities={[]} />);
    expect(q(host, "interco-schedule-panel")).not.toBeNull();
    expect(q(host, "interco-payment-rules")).toBeNull();
    expect(q(host, "interco-schedule-rules").textContent).toContain("Pelunasan sebagian diperbolehkan");
    expect(q(host, "interco-schedule-rules").textContent).toContain("diizinkan");
  });
});

test("KF-T2 · U14 (pelengkap) — tidak ada layar yang menulis PUT /api/settings; panel lama dihapus", () => {
  const src = path.resolve(__dirname, "../..");
  const pola = /axios\.put\(\s*[`"'](?:\$\{API\})?\/settings[`"'?]/;
  const temuan = [];
  const jalan = (dir) => fs.readdirSync(dir, { withFileTypes: true }).forEach((d) => {
    const p = path.join(dir, d.name);
    if (d.isDirectory()) { if (d.name !== "node_modules") jalan(p); return; }
    if (/\.jsx?$/.test(d.name) && pola.test(fs.readFileSync(p, "utf8"))) temuan.push(path.relative(src, p));
  });
  jalan(src);
  expect(temuan).toEqual([]);
  expect(fs.existsSync(path.join(src, "features/sales/ReturnAssumptionsPanel.jsx"))).toBe(false);
});
