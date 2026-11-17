// PY-T1 — layar Komponen & Masukan tanpa peramban (uji jalan U17 di lingkungan A):
//  · "Semua PT" → tombol tambah mati + "Pilih satu PT dulu" tertulis; kartu komponen diganti petunjuk.
//  · Tabel komponen: sepuluh kolom spesifikasi + kolom aksi `col-sticky-end`; "belum dipakai" ditulis di layar.
//  · Masukan: status ikon + teks; kosong "Belum ada masukan untuk periode ini."; Sahkan → konfirmasi menyebut nominal,
//    karyawan, PT, kirim ber-Idempotency-Key; Batalkan meminta alasan.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import PayComponentsView, { alasanTambahKomponen, alasanTambahMasukan, galatKomponen, galatMasukan, INPUT_STATUS,
  TEKS_SEMUA_PT } from "../hr/PayComponentsView";
import { AppNavProvider } from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { setAccessContext } from "../../config/roles";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockConfirm = jest.fn();
const mockReason = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({
  askConfirm: (...a) => mockConfirm(...a), askReason: (...a) => mockReason(...a) }));
jest.mock("../../components/EntityScopeBanner", () => () => <div data-testid="paycomp-scope" />);
jest.mock("../../components/KNSelect", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const ENT = [{ id: "ent_kanda", legal_name: "CV Kanda", short_name: "Kanda" }];
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function settle() { for (let i = 0; i < 6; i += 1) await act(async () => {}); }
async function mount(el, { entity = "ent_kanda" } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(
      <EntityScopeProvider selectedEntity={entity} entities={ENT} canSwitch>
        <AppNavProvider role="admin">{el}</AppNavProvider>
      </EntityScopeProvider>);
  });
  await settle();
  return { host, root };
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
}

const COMPS = [
  { id: "pc1", code: "GAJI_POKOK", name: "Gaji Pokok", kind: "pendapatan", calc: "tetap_bulanan", bucket: "base_salary", taxable: true,
    in_bpjs_base: true, in_overtime_base: true, prorate: false, account_code: "", is_active: true, system: true, allowed_run_types: ["regular"] },
  { id: "pc2", code: "BONUS", name: "Bonus", kind: "pendapatan", calc: "masukan", bucket: "other_earnings", taxable: true,
    account_code: "", is_active: true, system: false, allowed_run_types: ["regular", "susulan"] },
];
const INP = { id: "pinp_1", employee_name: "Andi", component_code: "BONUS", component_name: "Bonus", label: "Bonus A", amount: 2000000,
  pay_period: "2026-11", source_type: "manual", status: "pending", reason: "persetujuan direksi" };

function api({ comps = COMPS, items = [INP] } = {}) {
  mockGet.mockImplementation((url) => {
    if (url === "/api/hr/payroll/components") return Promise.resolve({ data: { items: comps } });
    if (url === "/api/hr/payroll/inputs") return Promise.resolve({ data: { items, total: items.length } });
    return Promise.resolve({ data: [] });
  });
}

afterEach(() => {
  mockGet.mockReset(); mockPost.mockReset(); mockConfirm.mockReset(); mockReason.mockReset();
  document.body.innerHTML = "";
});

describe("aturan murni", () => {
  test("alasan tombol mati ditulis, bukan tooltip", () => {
    expect(alasanTambahKomponen({ canWrite: false, canManage: true })).toBe(TEKS_SEMUA_PT);
    expect(alasanTambahKomponen({ canWrite: true, canManage: false })).toMatch(/butuh izin/);
    expect(alasanTambahKomponen({ canWrite: true, canManage: true })).toBe("");
    expect(alasanTambahMasukan({ canWrite: true, canCreate: false })).toMatch(/izin menyiapkan gaji/);
  });
  test("galat isian komponen & masukan", () => {
    expect(galatKomponen({ code: "bonus", name: "x", allowed_run_types: ["regular"] })).toMatch(/huruf besar/);
    expect(galatKomponen({ code: "POT", name: "Potongan", kind: "potongan", allowed_run_types: ["regular"] }))
      .toBe("Komponen potongan wajib punya akun.");
    expect(galatKomponen({ code: "BONUS", name: "Bonus", kind: "pendapatan", allowed_run_types: [] })).toMatch(/jenis proses/);
    expect(galatMasukan({ employee_id: "e", component_code: "BONUS", pay_period: "2026-11", amount: "0", reason: "x" })).toMatch(/tidak nol/);
    expect(galatMasukan({ employee_id: "e", component_code: "BONUS", pay_period: "2026-11", amount: "-5000", reason: "" }))
      .toBe("Alasan wajib diisi.");
    expect(galatMasukan({ employee_id: "e", component_code: "BONUS", pay_period: "2026-11", amount: "-5000", reason: "koreksi" })).toBe("");
  });
  test("status masukan: empat status, tiap status berikon dan berteks", () => {
    expect(Object.keys(INPUT_STATUS)).toEqual(["pending", "approved", "used", "cancelled"]);
    expect(Object.values(INPUT_STATUS).map((s) => s.label)).toEqual(["Menunggu disahkan", "Disahkan", "Terpakai", "Dibatalkan"]);
    Object.values(INPUT_STATUS).forEach((s) => expect(s.Icon).toBeTruthy());
  });
});

describe("Komponen & Masukan", () => {
  beforeEach(() => setAccessContext({ role: "admin" }));

  test("tabel komponen: kolom spesifikasi, kolom aksi lekat kanan, tanda belum dipakai tertulis", async () => {
    api();
    const { host } = await mount(<PayComponentsView />);
    const heads = [...q(host, "paycomp-table").querySelectorAll("thead th")].map((th) => th.textContent);
    // Sepuluh isian spesifikasi dalam 7 kolom (+ Aksi) supaya tabel muat di kartu pada 1024 px.
    expect(heads).toEqual(["Kode", "Nama", "Jenis · cara hitung", "Kena pajak", "Dasar BPJS · lembur · diprorata*", "Akun",
      "Aktif", "Aksi"]);
    expect(q(host, "paycomp-row-GAJI_POKOK").textContent).toContain("Tetap bulanan");
    expect(q(host, "paycomp-flags-GAJI_POKOK").textContent).toBe("Dasar BPJS · Dasar lembur");
    expect(q(host, "paycomp-flags-BONUS").textContent).toBe("—");
    expect(q(host, "paycomp-table").querySelector("thead th:last-child").className).toContain("col-sticky-end");
    expect(q(host, "paycomp-table").className).toContain("head-wrap");
    // PY-T3 — tanda Dasar BPJS, Dasar lembur, Diprorata kini dipakai hitungan gaji: keterangan "belum dipakai" dicabut.
    expect(q(host, "paycomp-unused-note").textContent).not.toMatch(/belum dipakai/);
    expect(q(host, "paycomp-unused-note").textContent).toMatch(/Diprorata = dibagi/);
    expect(q(host, "paycomp-row-GAJI_POKOK").textContent).toContain("Bawaan");
    expect(q(host, "paycomp-add").disabled).toBe(false);
  });

  test("Semua PT: tombol tambah mati dengan alasan tertulis; komponen diganti petunjuk", async () => {
    api();
    const { host } = await mount(<PayComponentsView />, { entity: "all" });
    expect(q(host, "paycomp-add").disabled).toBe(true);
    expect(q(host, "paycomp-add-why").textContent).toBe(TEKS_SEMUA_PT);
    expect(q(host, "paycomp-all-pt")).toBeTruthy();
    expect(q(host, "payinput-add").disabled).toBe(true);
  });

  test("masukan kosong: satu kalimat kosong", async () => {
    api({ items: [] });
    const { host } = await mount(<PayComponentsView />);
    expect(q(host, "payinput-empty").textContent).toBe("Belum ada masukan untuk periode ini.");
  });

  test("Sahkan: konfirmasi menyebut nominal, karyawan, PT; kirim ber-kunci", async () => {
    api();
    mockConfirm.mockResolvedValue(true);
    mockPost.mockResolvedValue({ data: { ...INP, status: "approved" } });
    const { host } = await mount(<PayComponentsView />);
    expect(q(host, "payinput-status-pinp_1").textContent).toBe("Menunggu disahkan");
    expect(q(host, "payinput-status-pinp_1").querySelector("svg")).toBeTruthy();
    await click(q(host, "payinput-approve-pinp_1"));
    const arg = mockConfirm.mock.calls[0][0];
    expect(arg.title).toContain("Rp");
    expect(arg.message).toContain("Andi");
    expect(arg.message).toContain("CV Kanda");
    const [url, , cfg] = mockPost.mock.calls[0];
    expect(url).toBe("/api/hr/payroll/inputs/pinp_1/approve");
    expect(cfg.headers["Idempotency-Key"]).toBeTruthy();
  });

  test("Batalkan meminta alasan; tanpa alasan tidak dikirim", async () => {
    api();
    mockReason.mockResolvedValue(null);
    const { host } = await mount(<PayComponentsView />);
    await click(q(host, "payinput-cancel-pinp_1"));
    expect(mockReason).toHaveBeenCalled();
    expect(mockPost).not.toHaveBeenCalled();
  });
});

// K-SDM-01 (audit pelatihan 18 Nov) — nominal masukan gaji: dulu kotak teks membuang semua selain angka, sehingga
// "8.000.000,00" tersimpan Rp 800.000.000 (100×). Kini isian rupiah baku `MoneyInput`.
describe("K-SDM-01 — nominal masukan gaji ditulis cara orang Indonesia", () => {
  const ketik = async (el, v) => {
    const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
    await act(async () => { set.call(el, v); el.dispatchEvent(new Event("input", { bubbles: true })); });
    await settle();
  };
  test("\"8.000.000,00\" terbaca Rp 8.000.000 (bukan 800 juta); minus penyesuaian tidak bermerah", async () => {
    api({ items: [] });
    const { host } = await mount(<PayComponentsView />);
    await click(q(host, "payinput-add"));
    const amt = q(document.body, "payinput-form-amount");
    expect(amt).toBeTruthy();
    await ketik(amt, "8.000.000,00");
    expect(q(document.body, "payinput-form-amount-preview").textContent).toMatch(/^Rp\s?8\.000\.000 · Rupiah bulat/);
    await ketik(amt, "-250.000");
    expect(q(document.body, "payinput-form-amount-preview").textContent).toMatch(/250\.000/);
    expect(amt.className).not.toMatch(/D14343/);
  });
  test("sen ditolak: rupiah bulat", () => {
    expect(galatMasukan({ employee_id: "e", component_code: "RAPEL", pay_period: "2026-11", amount: "8000000.5", reason: "x" }))
      .toMatch(/rupiah bulat/);
    expect(galatMasukan({ employee_id: "e", component_code: "RAPEL", pay_period: "2026-11", amount: "8000000", reason: "x" })).toBe("");
  });
});
