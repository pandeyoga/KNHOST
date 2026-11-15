// PY-T2 — kartu karyawan: Riwayat Kompensasi & Penugasan PT, form karyawan (uji tanpa peramban; uji jalan U15 =
// integrator di lingkungan A):
//  · U15: dua baris riwayat — 6.000.000 "Berlaku" (berakhir 30 Nov) dan 7.500.000 "Akan berlaku" (mulai 1 Des).
//  · Lencana ikon + teks + warna; baris menunggu → Sahkan (konfirmasi menyebut gaji, nama, tanggal, PT; kirim
//    ber-Idempotency-Key) dan Tolak (alasan).
//  · Tanpa izin mengubah data karyawan: "Ajukan perubahan" mati + alasan tertulis di sampingnya.
//  · Form ubah karyawan: gaji pokok, tunjangan, PT hanya-baca dengan petunjuk "Ubah lewat Riwayat Kompensasi." dan tidak
//    dikirim; form buat tetap mengirimnya.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import EmployeeCompensationSection, { badanKompensasi, galatKompensasi, galatPenugasan, rowBadge, ROW_BADGE,
  teksSahkanGaji } from "../hr/EmployeeCompensationSection";
import { badanKaryawan, EmployeeFormDrawer, PETUNJUK_RIWAYAT } from "../hr/EmployeeFormDrawer";
import { EntityScopeProvider } from "../../context/EntityScopeContext";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockPatch = jest.fn();
const mockConfirm = jest.fn();
const mockReason = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: (...a) => mockPatch(...a),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({
  askConfirm: (...a) => mockConfirm(...a), askReason: (...a) => mockReason(...a) }));
jest.mock("../../components/KNSelect", () => (p) => <select data-testid={p["data-testid"]} disabled={p.disabled} value={p.value || ""} onChange={() => {}}><option value={p.value || ""}>{p.value}</option></select>);
jest.mock("../../components/KNDatePicker", () => () => null);
jest.mock("@/components/KNDatePicker", () => () => null);
jest.mock("@/components/LocationFields", () => () => null);
jest.mock("@/components/ui/switch", () => ({ Switch: () => null }));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const ENT = [{ id: "ent_ksc", legal_name: "PT Kain Sejahtera Cemerlang", short_name: "KSC" }];
const EMP = { id: "emp_k1", name: "K1 Uji", code: "EMP-1", entity_id: "ent_ksc", base_salary: 6000000 };
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function settle() { for (let i = 0; i < 6; i += 1) await act(async () => {}); }
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<EntityScopeProvider selectedEntity="ent_ksc" entities={ENT} canSwitch>{el}</EntityScopeProvider>); });
  await settle();
  return { host, root };
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
}

const ROWS = {
  today: "2026-11-15",
  compensation: [
    { id: "hc2", status: "approved", effective_from: "2026-12-01", effective_to: "", base_salary: 7500000, entity_id: "ent_ksc",
      fixed_components: [{ component_code: "TUNJANGAN", label: "Transport", amount: 500000 }], reason: "kenaikan tahunan",
      proposed_by: { name: "Siti" }, approved_by: { name: "Budi" } },
    { id: "hc1", status: "approved", effective_from: "2026-01-01", effective_to: "2026-11-30", base_salary: 6000000, entity_id: "ent_ksc",
      fixed_components: [{ component_code: "TUNJANGAN", label: "Transport", amount: 500000 }], reason: "Migrasi",
      proposed_by: { name: "Migrasi PY-T2" }, approved_by: { name: "Migrasi PY-T2" } },
  ],
  assignments: [{ id: "ha1", status: "approved", effective_from: "2026-01-01", effective_to: "", entity_id: "ent_ksc",
    department_name: "Gudang", position_name: "Kepala" }],
  fixed_component_options: [{ code: "TUNJANGAN", name: "Tunjangan" }],
};

afterEach(() => {
  mockGet.mockReset(); mockPost.mockReset(); mockPatch.mockReset(); mockConfirm.mockReset(); mockReason.mockReset();
  document.body.innerHTML = "";
});

describe("aturan murni", () => {
  test("lencana baris menurut status dan tanggal", () => {
    const t = "2026-11-15";
    expect(rowBadge({ status: "pending", effective_from: "2026-12-01" }, t)).toBe("pending");
    expect(rowBadge({ status: "approved", effective_from: "2026-12-01" }, t)).toBe("akan");
    expect(rowBadge({ status: "approved", effective_from: "2026-01-01", effective_to: "2026-11-30" }, t)).toBe("berlaku");
    expect(rowBadge({ status: "approved", effective_from: "2026-01-01", effective_to: "2026-10-31" }, t)).toBe("berakhir");
    expect(rowBadge({ status: "rejected" }, t)).toBe("rejected");
    expect(Object.values(ROW_BADGE).map((b) => b.label)).toEqual(
      ["Menunggu disahkan", "Berlaku", "Akan berlaku", "Berakhir", "Ditolak", "Dibatalkan"]);
    Object.values(ROW_BADGE).forEach((b) => { expect(b.Icon).toBeTruthy(); expect(b.cls).toMatch(/^status-/); });
  });
  test("galat isian & badan permintaan", () => {
    expect(galatKompensasi({ effective_from: "", base_salary: "1", reason: "x" })).toBe("Pilih tanggal berlaku.");
    expect(galatKompensasi({ effective_from: "2026-12-01", base_salary: "", reason: "x" })).toMatch(/gaji pokok/);
    expect(galatKompensasi({ effective_from: "2026-12-01", base_salary: "7500000", reason: " " })).toBe("Alasan wajib diisi.");
    expect(galatKompensasi({ effective_from: "2026-12-01", base_salary: "7500000", reason: "naik", fixed_components: [] })).toBe("");
    expect(galatPenugasan({ entity_id: "", effective_from: "2026-12-01", reason: "x" })).toBe("Pilih PT tujuan.");
    expect(badanKompensasi({ effective_from: "2026-12-01", base_salary: "7500000", reason: " naik ",
      fixed_components: [{ component_code: "TUNJANGAN", label: "Transport ", amount: "500000" }] })).toEqual({
      effective_from: "2026-12-01", base_salary: 7500000, reason: "naik",
      fixed_components: [{ component_code: "TUNJANGAN", label: "Transport", amount: 500000 }] });
    expect(teksSahkanGaji({ base_salary: 7500000, effective_from: "2026-12-01" }, "K1 Uji", "PT X"))
      .toMatch(/^Sahkan gaji pokok Rp\s?7\.500\.000 untuk K1 Uji, berlaku .*2026, di PT X\?$/);
  });
  test("form ubah tidak mengirim gaji, tunjangan, PT; form buat mengirimnya", () => {
    const f = { name: "A", base_salary: "5000000", allowances: [{ name: "Makan", amount: 300000 }], entity_id: "ent_ksc", phone: "1" };
    const ubah = badanKaryawan(f, true);
    expect(ubah).not.toHaveProperty("base_salary");
    expect(ubah).not.toHaveProperty("allowances");
    expect(ubah).not.toHaveProperty("entity_id");
    expect(ubah.phone).toBe("1");
    expect(badanKaryawan(f, false)).toMatchObject({ base_salary: 5000000, entity_id: "ent_ksc",
      allowances: [{ name: "Makan", amount: 300000 }] });
  });
});

describe("Riwayat Kompensasi di kartu karyawan", () => {
  test("U15 — dua baris: 6.000.000 Berlaku, 7.500.000 Akan berlaku; penugasan PT", async () => {
    mockGet.mockResolvedValue({ data: ROWS });
    const { host } = await mount(<EmployeeCompensationSection employee={EMP} currentUser={{ permissions: { hr: ["view", "update"], payroll: ["approve"] } }} />);
    expect(mockGet).toHaveBeenCalledWith("/api/hr/employees/emp_k1/compensation");
    expect(q(host, "emp-comp-status-hc1").textContent).toBe("Berlaku");
    expect(q(host, "emp-comp-status-hc2").textContent).toBe("Akan berlaku");
    expect(q(host, "emp-comp-row-hc1").textContent).toMatch(/6\.000\.000/);
    expect(q(host, "emp-comp-row-hc2").textContent).toMatch(/7\.500\.000/);
    expect(q(host, "emp-comp-row-hc2").textContent).toMatch(/Transport/);
    expect(q(host, "emp-asg-row-ha1").textContent).toMatch(/PT Kain Sejahtera Cemerlang/);
    expect(q(host, "emp-asg-status-ha1").textContent).toBe("Berlaku");
    expect(q(host, "emp-comp-table").querySelector("th.col-sticky-end").textContent).toBe("Aksi");
    expect(q(host, "emp-comp-add").disabled).toBe(false);
  });

  test("baris menunggu: Sahkan meminta konfirmasi bernominal + PT dan mengirim kunci; Tolak meminta alasan", async () => {
    const pending = { id: "hc3", status: "pending", effective_from: "2027-01-01", base_salary: 8000000, entity_id: "ent_ksc",
      fixed_components: [], reason: "promosi", proposed_by: { name: "Siti" }, approved_by: {} };
    mockGet.mockResolvedValue({ data: { ...ROWS, compensation: [pending, ...ROWS.compensation] } });
    mockConfirm.mockResolvedValue(true);
    mockReason.mockResolvedValue("belum disetujui direksi");
    mockPost.mockResolvedValue({ data: {} });
    const { host } = await mount(<EmployeeCompensationSection employee={EMP} currentUser={{ permissions: { hr: ["update"], payroll: ["approve"] } }} />);
    expect(q(host, "emp-comp-status-hc3").textContent).toBe("Menunggu disahkan");
    await click(q(host, "emp-hist-approve-hc3"));
    const pesan = mockConfirm.mock.calls[0][0].message;
    expect(pesan).toMatch(/Sahkan gaji pokok Rp\s?8\.000\.000 untuk K1 Uji, berlaku .*2027, di PT Kain Sejahtera Cemerlang\?/);
    const [url, , cfg] = mockPost.mock.calls[0];
    expect(url).toBe("/api/hr/compensation/hc3/approve");
    expect(cfg.headers["Idempotency-Key"]).toBeTruthy();
    await click(q(host, "emp-hist-reject-hc3"));
    expect(mockReason).toHaveBeenCalled();
    expect(mockPost.mock.calls[1][0]).toBe("/api/hr/compensation/hc3/reject");
    expect(mockPost.mock.calls[1][1]).toEqual({ reason: "belum disetujui direksi" });
  });

  test("tanpa izin mengubah: tombol mati dengan alasan tertulis; tanpa izin sahkan: kolom aksi tidak tampil", async () => {
    mockGet.mockResolvedValue({ data: ROWS });
    const { host } = await mount(<EmployeeCompensationSection employee={EMP} currentUser={{ permissions: { hr: ["view"] } }} />);
    expect(q(host, "emp-comp-add").disabled).toBe(true);
    expect(q(host, "emp-comp-add-why").textContent).toBe("Mengajukan perubahan butuh izin mengubah data karyawan.");
    expect(q(host, "emp-asg-add").disabled).toBe(true);
    expect(q(host, "emp-comp-table").querySelector("th.col-sticky-end")).toBeNull();
  });

  test("galat muat → pesan + Coba lagi; kosong → satu kalimat", async () => {
    mockGet.mockRejectedValueOnce({ response: { status: 500, data: { detail: "server mati" } } });
    const { host } = await mount(<EmployeeCompensationSection employee={EMP} currentUser={{ permissions: {} }} />);
    expect(q(host, "emp-comp-error")).toBeTruthy();
    document.body.innerHTML = "";
    mockGet.mockResolvedValue({ data: { today: "2026-11-15", compensation: [], assignments: [], fixed_component_options: [] } });
    const m2 = await mount(<EmployeeCompensationSection employee={EMP} currentUser={{ permissions: {} }} />);
    expect(q(m2.host, "emp-comp-empty").textContent).toMatch(/Belum ada riwayat kompensasi/);
    expect(m2.host.querySelectorAll("[data-testid='emp-comp-empty']").length).toBe(1);
  });
});

describe("Form karyawan", () => {
  test("mode ubah: gaji, tunjangan, PT hanya-baca + petunjuk; simpan tanpa ketiganya", async () => {
    mockPatch.mockResolvedValue({ data: {} });
    const emp = { ...EMP, allowances: [{ name: "Transport", amount: 500000 }], status: "active" };
    const { host } = await mount(<EmployeeFormDrawer open editEmployee={emp} entities={ENT} onClose={() => {}} />);
    const gaji = document.querySelector("[data-testid='employee-salary-input']");
    expect(gaji.disabled).toBe(true);
    expect(document.querySelector("[data-testid='employee-salary-hint']").textContent).toBe(PETUNJUK_RIWAYAT);
    expect(document.querySelector("[data-testid='employee-entity-select']").disabled).toBe(true);
    expect(document.querySelector("[data-testid='employee-allowance-hint']").textContent).toBe(PETUNJUK_RIWAYAT);
    expect(document.querySelector("[data-testid='employee-add-allowance']")).toBeNull();
    await click(document.querySelector("[data-testid='employee-save-button']"));
    const [url, body] = mockPatch.mock.calls[0];
    expect(url).toBe("/api/hr/employees/emp_k1");
    expect(body.data).not.toHaveProperty("base_salary");
    expect(body.data).not.toHaveProperty("allowances");
    expect(body.data).not.toHaveProperty("entity_id");
    expect(host).toBeTruthy();
  });
});
