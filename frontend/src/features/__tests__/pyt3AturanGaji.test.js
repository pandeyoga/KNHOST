// PY-T3 — layar aturan hitung gaji (uji tanpa peramban; uji jalan = integrator di lingkungan A):
//  · Pengaturan › SDM › Kalender Libur: keterangan "Isi dari keputusan resmi…", kosong "Belum ada hari libur untuk tahun
//    ini.", kolom Tanggal · Nama · Jenis (ikon + teks + warna), "Tambah hari libur" mati beralasan saat "Semua PT" atau
//    tanpa izin, Hapus dengan konfirmasi yang menyebut tanggal dan PT.
//  · Kartu karyawan › Saldo awal pajak {tahun}: lima isian, keterangan, galat jumlah masa, badan PUT.
//  · Pusat Pengaturan: catatan pengali tunggal saat mode bertingkat (L6); tautan "Lihat dampaknya" (hasil
//    overtime-impact periode berjalan).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import HolidaysView, { alasanTambahLibur, galatLibur, JENIS, KETERANGAN, KOSONG } from "../hr/HolidaysView";
import EmployeeTaxOpeningSection, { alasanSimpanSaldo, galatSaldoAwal, KETERANGAN_SALDO } from "../hr/EmployeeTaxOpeningSection";
import SettingKeyExtra, { CATATAN_PENGALI, catatanPengali } from "../settings/config/SettingKeyExtra";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { setAccessContext } from "../../config/roles";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockPut = jest.fn();
const mockDelete = jest.fn();
const mockConfirm = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), put: (...a) => mockPut(...a),
    delete: (...a) => mockDelete(...a), patch: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({ askConfirm: (...a) => mockConfirm(...a), askReason: () => Promise.resolve("") }));
jest.mock("../../components/EntityScopeBanner", () => () => <div data-testid="scope-banner" />);
jest.mock("../../components/KNSelect", () => (p) => <select data-testid={p["data-testid"]} disabled={p.disabled} value={p.value || ""} onChange={() => {}}><option value={p.value || ""}>{p.value}</option></select>);
jest.mock("../../components/KNDatePicker", () => () => null);
jest.mock("@/components/KNDatePicker", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const ENT = [{ id: "ent_ksc", legal_name: "PT Kain Sejahtera Cemerlang", short_name: "KSC" }];
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function settle() { for (let i = 0; i < 6; i += 1) await act(async () => {}); }
async function mount(el, { entity = "ent_ksc" } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<EntityScopeProvider selectedEntity={entity} entities={ENT} canSwitch>{el}</EntityScopeProvider>); });
  await settle();
  return { host, root };
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
}

beforeEach(() => setAccessContext({ role: "admin" }));
afterEach(() => {
  mockGet.mockReset(); mockPost.mockReset(); mockPut.mockReset(); mockDelete.mockReset(); mockConfirm.mockReset();
  document.body.innerHTML = "";
});

describe("aturan murni", () => {
  test("galat isian hari libur & alasan tombol mati", () => {
    expect(galatLibur({ date: "", name: "x", kind: "nasional" })).toBe("Pilih tanggal.");
    expect(galatLibur({ date: "2026-12-25", name: " ", kind: "nasional" })).toBe("Isi nama hari libur.");
    expect(galatLibur({ date: "2026-12-25", name: "Natal", kind: "lain" })).toBe("Pilih jenis hari libur.");
    expect(galatLibur({ date: "2026-12-25", name: "Natal", kind: "cuti_bersama" })).toBe("");
    expect(alasanTambahLibur({ canWrite: false, canManage: true })).toBe("Pilih satu PT dulu untuk menambah hari libur.");
    expect(alasanTambahLibur({ canWrite: true, canManage: false })).toMatch(/izin mengatur absensi/);
    expect(Object.values(JENIS).map((j) => j.label)).toEqual(["Nasional", "Cuti bersama", "Perusahaan"]);
    Object.values(JENIS).forEach((j) => { expect(j.Icon).toBeTruthy(); expect(j.cls).toMatch(/^status-/); });
  });
  test("galat saldo awal pajak", () => {
    expect(galatSaldoAwal({ months: "0" })).toBe("Jumlah masa harus 1 sampai 11.");
    expect(galatSaldoAwal({ months: "12" })).toBe("Jumlah masa harus 1 sampai 11.");
    expect(galatSaldoAwal({ months: "6", tax_gross: -1 })).toMatch(/Bruto/);
    expect(galatSaldoAwal({ months: "6", tax_gross: 48000000, pension_deduction: "", pph21_withheld: 720000 })).toBe("");
    expect(alasanSimpanSaldo({ canWrite: true, canManage: false })).toMatch(/izin mengatur penggajian/);
  });
  test("catatan pengali tunggal hanya saat mode bertingkat", () => {
    expect(catatanPengali({ "hr.overtime.mode": { value: "bertingkat" } })).toBe(CATATAN_PENGALI);
    expect(catatanPengali({ "hr.overtime.mode": { value: "flat" } })).toBe("");
    expect(catatanPengali({})).toBe("");
  });
});

describe("Kalender Libur", () => {
  test("kosong + keterangan; tambah aktif untuk satu PT", async () => {
    mockGet.mockResolvedValue({ data: { rows: [], total: 0 } });
    const { host } = await mount(<HolidaysView />);
    expect(mockGet).toHaveBeenCalledWith("/api/hr/holidays", expect.objectContaining({ params: expect.any(Object) }));
    expect(q(host, "hr-holidays-note").textContent).toBe(KETERANGAN);
    expect(q(host, "hr-holidays-empty").textContent).toBe(KOSONG);
    expect(q(host, "hr-holidays-add").disabled).toBe(false);
    expect(q(host, "hr-holidays-add").textContent).toMatch("Tambah hari libur");
  });
  test("Semua PT: tombol tambah mati dengan alasan tertulis", async () => {
    mockGet.mockResolvedValue({ data: { rows: [], total: 0 } });
    const { host } = await mount(<HolidaysView />, { entity: "all" });
    expect(q(host, "hr-holidays-add").disabled).toBe(true);
    expect(q(host, "hr-holidays-add-why").textContent).toBe("Pilih satu PT dulu untuk menambah hari libur.");
  });
  test("baris: tanggal, nama, jenis berikon; hapus minta konfirmasi", async () => {
    mockGet.mockResolvedValue({ data: { rows: [{ id: "hhol_1", entity_id: "ent_ksc", date: "2026-12-25", name: "Natal", kind: "nasional" }] } });
    mockConfirm.mockResolvedValue(true);
    mockDelete.mockResolvedValue({ data: { deleted: true } });
    const { host } = await mount(<HolidaysView />);
    const row = q(host, "hr-holidays-row-hhol_1");
    expect(row.textContent).toMatch("Natal");
    const pill = q(host, "hr-holidays-kind-hhol_1");
    expect(pill.textContent).toBe("Nasional");
    expect(pill.className).toMatch("status-pill");
    expect(pill.querySelector("svg")).toBeTruthy();
    expect(q(host, "hr-holidays-table").querySelector("th.col-sticky-end")).toBeTruthy();
    await click(q(host, "hr-holidays-del-hhol_1"));
    expect(mockConfirm.mock.calls[0][0].message).toMatch(/Natal/);
    expect(mockConfirm.mock.calls[0][0].message).toMatch(/PT Kain Sejahtera Cemerlang/);
    expect(mockDelete).toHaveBeenCalledWith("/api/hr/holidays/hhol_1");
  });
  test("tanpa izin mengatur absensi: tambah mati, kolom aksi tidak tampil", async () => {
    setAccessContext({ role: "staf_sdm", permissions: { hr: ["view"] } });
    mockGet.mockResolvedValue({ data: { rows: [{ id: "hhol_1", entity_id: "ent_ksc", date: "2026-12-25", name: "Natal", kind: "nasional" }] } });
    const { host } = await mount(<HolidaysView />);
    expect(q(host, "hr-holidays-add").disabled).toBe(true);
    expect(q(host, "hr-holidays-add-why").textContent).toMatch(/izin mengatur absensi/);
    expect(q(host, "hr-holidays-del-hhol_1")).toBeNull();
  });
});

describe("Saldo awal pajak", () => {
  const EMP = { id: "emp_k7", name: "K7 Uji", entity_id: "ent_ksc" };
  const USER = { role: "admin", permissions: { hr: ["view", "view_pii", "manage_payroll"] } };
  test("judul bertahun, keterangan, simpan mengirim lima isian", async () => {
    mockGet.mockResolvedValue({ data: { year: 2026, months: 6, tax_gross: 48000000, pension_deduction: 0, pph21_withheld: 720000, note: "" } });
    mockConfirm.mockResolvedValue(true);
    mockPut.mockResolvedValue({ data: {} });
    const { host } = await mount(<EmployeeTaxOpeningSection employee={EMP} currentUser={USER} />);
    expect(q(host, "emp-tax-opening-title").textContent).toMatch(/^Saldo awal pajak \d{4}$/);
    expect(q(host, "emp-tax-opening-note").textContent).toBe(KETERANGAN_SALDO);
    expect(q(host, "emp-tax-opening-months").value).toBe("6");
    await click(q(host, "emp-tax-opening-save"));
    expect(mockConfirm).toHaveBeenCalled();
    const [url, body] = mockPut.mock.calls[0];
    expect(url).toBe("/api/hr/employees/emp_k7/tax-opening");
    expect(body).toEqual(expect.objectContaining({ months: 6, tax_gross: 48000000, pension_deduction: 0, pph21_withheld: 720000 }));
  });
  test("tanpa izin mengatur penggajian: simpan mati + alasan", async () => {
    mockGet.mockResolvedValue({ data: null });
    const { host } = await mount(<EmployeeTaxOpeningSection employee={EMP} currentUser={{ role: "staf", permissions: { hr: ["view", "view_pii"] } }} />);
    expect(q(host, "emp-tax-opening-save").disabled).toBe(true);
    expect(q(host, "emp-tax-opening-why").textContent).toMatch(/izin mengatur penggajian/);
  });
});

describe("Pusat Pengaturan — kunci khusus", () => {
  test("pengali tunggal: catatan saat bertingkat", async () => {
    const { host } = await mount(<SettingKeyExtra item={{ key: "hr.overtime.multiplier" }} peers={{ "hr.overtime.mode": { value: "bertingkat" } }} />);
    expect(q(host, "cfg-extra-multiplier").textContent).toMatch("Dipakai hanya bila cara hitung pengali = flat.");
  });
  test("sumber lembur: Lihat dampaknya membuka hasil periode berjalan", async () => {
    mockGet.mockResolvedValue({ data: { rows: [{ employee_id: "e1", employee_name: "K5", days: 1, minutes: 120, amount: 105000 }],
      total_minutes: 120, total_amount: 105000 } });
    const { host } = await mount(<SettingKeyExtra item={{ key: "hr.overtime.sumber" }} scopeType="entity" scopeId="ent_ksc" />);
    await click(q(host, "cfg-overtime-impact-open"));
    const [url, opt] = mockGet.mock.calls[0];
    expect(url).toBe("/api/hr/payroll/overtime-impact");
    expect(opt.params.entity_id).toBe("ent_ksc");
    expect(opt.params.period).toMatch(/^\d{4}-\d{2}$/);
    expect(document.body.querySelector('[data-testid="cfg-overtime-impact-table"]').textContent).toMatch("K5");
  });
  test("sumber lembur tanpa PT terpilih: petunjuk, bukan tombol", async () => {
    const { host } = await mount(<SettingKeyExtra item={{ key: "hr.overtime.sumber" }} scopeType="global" scopeId="" />);
    expect(q(host, "cfg-overtime-impact-open")).toBeNull();
    expect(q(host, "cfg-overtime-impact-why").textContent).toMatch(/Pilih satu PT/);
  });
});
