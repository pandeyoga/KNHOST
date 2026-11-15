// PY-T5 — kartu "Slip Gaji Saya" di Profil Saya (uji komponen; uji jalan U13 di lingkungan A):
//  · U11 — jawaban U7 (dua slip Oktober 2026: Reguler & THR) → dua baris riwayat berlabel "Reguler" dan "THR"; baris
//    reguler dibuka → rincian memuat "Gaji Pokok", "Tunjangan — Transport", "PPh 21", dan "Gaji bersih" Rp 8.646.000;
//  · U12 — permintaan gagal (500) → "Slip belum bisa dimuat." + tombol "Coba lagi" (tidak lagi diam);
//  · keadaan kosong: "Belum ada slip gaji yang terbit." + keterangan menurut `visible_since`;
//  · tahun berjalan tanpa slip → kartu membuka tahun terbaru yang punya slip.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { MyPayslipCard, TEKS_GALAT, TEKS_KOSONG } from "../hr/MyPayslipCard";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } } },
  API: "/api",
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const teks = (el) => (el?.textContent || "").replace(/\s+/g, " ").trim();
async function settle() { for (let i = 0; i < 8; i += 1) await act(async () => {}); }
async function mount() {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<MyPayslipCard />); });
  await settle();
  return host;
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
}

const C = (code, label, kind, amount) => ({ code, label, kind, amount });
// Jawaban U7 (server PY-T5): E1 Oktober 2026 — THR dibayar sesudah reguler, jadi tampil lebih dulu.
const REGULER = { id: "slip_reg", number: "KANDA/SLIP-00001", period: "2026-10", run_type: "regular", status: "paid",
  paid_at: "2026-11-01T03:00:00+00:00", paid_date: "2026-11-01", gross: 8800000, pph21: 154000, net: 8646000,
  bank: { bank_name: "BCA" },
  components: [C("GAJI_POKOK", "Gaji Pokok", "pendapatan", 8000000), C("TUNJANGAN", "Tunjangan — Transport", "pendapatan", 500000),
    C("TUNJANGAN", "Tunjangan — Makan", "pendapatan", 300000), C("PPH21", "PPh 21", "potongan", 154000)] };
const THR = { id: "slip_thr", number: "KANDA/SLIP-00003", period: "2026-10", run_type: "thr", status: "paid",
  paid_at: "2026-11-02T03:00:00+00:00", paid_date: "2026-11-02", gross: 8000000, pph21: 686000, net: 7314000,
  bank: { bank_name: "BCA" },
  components: [C("THR", "THR 2026", "pendapatan", 8000000), C("PPH21", "PPh 21", "potongan", 686000)] };
const U7 = { employee: { id: "emp_e1", name: "E1" }, visible_since: "dibayar", year: 2026, years: [2026], payslips: [THR, REGULER] };

afterEach(() => { mockGet.mockReset(); document.body.innerHTML = ""; });

test("U11 — dua baris riwayat Reguler & THR; rincian reguler berkomponen dan Gaji bersih Rp 8.646.000", async () => {
  mockGet.mockResolvedValue({ data: U7 });
  const host = await mount();
  expect(teks(q(host, "ess-payslip-card"))).toContain("Slip Gaji Saya");
  // riwayat: dua baris berlabel jenis
  const baris = host.querySelectorAll('[data-testid^="ess-payslip-row-"]');
  expect(baris).toHaveLength(2);
  expect(teks(q(host, "ess-payslip-type-slip_reg"))).toBe("Reguler");
  expect(teks(q(host, "ess-payslip-type-slip_thr"))).toBe("THR");
  // ringkasan slip terakhir = baris pertama (THR, dibayar paling akhir)
  const ringkas = teks(q(host, "ess-payslip-latest"));
  expect(ringkas).toContain("Periode Oktober 2026 · THR");
  expect(ringkas).toContain("Gaji bersih diterima");
  expect(ringkas).toContain("Rp 7.314.000");
  expect(ringkas).toContain("Dibayar");
  expect(teks(q(host, "ess-payslip-pdf"))).toBe("Lihat slip (PDF)");
  // status bayar = ikon + teks + warna (status-pill berkelas yang ada)
  const pil = q(host, "ess-payslip-paid-slip_reg");
  expect(pil.className).toContain("status-pill status-paid");
  expect(pil.querySelector("svg")).not.toBeNull();
  expect(teks(pil)).toContain("Dibayar");
  // buka rincian baris reguler
  expect(q(host, "ess-payslip-detail-slip_reg")).toBeNull();
  const tombol = q(host, "ess-payslip-toggle-slip_reg");
  expect(tombol.getAttribute("aria-expanded")).toBe("false");
  await click(tombol);
  expect(tombol.getAttribute("aria-expanded")).toBe("true");
  const rinci = q(host, "ess-payslip-detail-slip_reg");
  expect(teks(q(host, "ess-payslip-detail-slip_reg-pendapatan"))).toContain("Pendapatan");
  expect(teks(q(host, "ess-payslip-detail-slip_reg-potongan"))).toContain("Potongan");
  for (const label of ["Gaji Pokok", "Tunjangan — Transport", "PPh 21", "Gaji bersih"]) expect(teks(rinci)).toContain(label);
  expect(teks(q(host, "ess-payslip-detail-slip_reg-net"))).toBe("Rp 8.646.000");
  expect(q(host, "ess-payslip-detail-slip_thr")).toBeNull();   // baris lain tetap tertutup
  // PDF per baris tersedia
  expect(teks(q(host, "ess-payslip-rowpdf-slip_reg"))).toBe("PDF");
  // pemilih tahun dari `years`; muatan pertama tanpa tahun (server memakai tahun berjalan WIB)
  expect(teks(q(host, "ess-payslip-years"))).toBe("2026");
  expect(mockGet).toHaveBeenCalledWith("/api/hr/payslips/me", { params: {} });
});

test("U12 — permintaan gagal (500) → teks galat + Coba lagi, lalu berhasil dimuat ulang", async () => {
  mockGet.mockRejectedValueOnce({ response: { status: 500, data: { detail: "boom" } } });
  const host = await mount();
  const galat = q(host, "ess-payslip-error");
  expect(galat).not.toBeNull();
  expect(TEKS_GALAT).toBe("Slip belum bisa dimuat.");
  expect(teks(galat)).toContain("Slip belum bisa dimuat. Coba lagi");
  expect(teks(galat)).not.toContain("boom");
  expect(q(host, "ess-payslip-empty")).toBeNull();
  mockGet.mockResolvedValueOnce({ data: U7 });
  await click(q(host, "ess-payslip-error-retry"));
  expect(q(host, "ess-payslip-error")).toBeNull();
  expect(host.querySelectorAll('[data-testid^="ess-payslip-row-"]')).toHaveLength(2);
});

test("kosong — 'Belum ada slip gaji yang terbit.' dengan keterangan menurut pengaturan PT", async () => {
  mockGet.mockResolvedValue({ data: { employee: { id: "e" }, visible_since: "dibayar", year: 2026, years: [], payslips: [] } });
  let host = await mount();
  expect(teks(q(host, "ess-payslip-empty"))).toContain(TEKS_KOSONG);
  expect(teks(q(host, "ess-payslip-empty-hint"))).toBe("Slip muncul setelah gaji dibayar.");
  expect(q(host, "ess-payslip-latest")).toBeNull();
  document.body.innerHTML = "";
  mockGet.mockResolvedValue({ data: { employee: { id: "e" }, visible_since: "disahkan", year: 2026, years: [], payslips: [] } });
  host = await mount();
  expect(teks(q(host, "ess-payslip-empty-hint"))).toBe("Slip muncul setelah penggajian disahkan.");
});

test("tahun berjalan tanpa slip → tahun terbaru yang punya slip dibuka; pilih tahun memuat ulang", async () => {
  const des = { ...REGULER, id: "slip_des", period: "2025-12", paid_date: "2025-12-28", net: 8000000 };
  const nov = { ...REGULER, id: "slip_nov", period: "2025-11", paid_date: "2025-11-28", net: 7900000 };
  mockGet.mockImplementation((url, cfg) => {
    const y = cfg?.params?.year;
    if (!y) return Promise.resolve({ data: { employee: { id: "e" }, visible_since: "dibayar", year: 2026, years: [2025, 2024], payslips: [] } });
    if (y === 2025) return Promise.resolve({ data: { employee: { id: "e" }, visible_since: "dibayar", year: 2025, years: [2025, 2024], payslips: [des, nov] } });
    return Promise.resolve({ data: { employee: { id: "e" }, visible_since: "dibayar", year: 2024, years: [2025, 2024],
      payslips: [{ ...REGULER, id: "slip_lama", period: "2024-06", paid_date: "2024-06-28", net: 7000000 }] } });
  });
  const host = await mount();
  expect(host.querySelectorAll('[data-testid^="ess-payslip-row-"]')).toHaveLength(2);
  expect(teks(q(host, "ess-payslip-latest"))).toContain("Periode Desember 2025");
  expect(mockGet).toHaveBeenLastCalledWith("/api/hr/payslips/me", { params: { year: 2025 } });
  await click(q(host, "ess-payslip-years-2024"));
  expect(mockGet).toHaveBeenLastCalledWith("/api/hr/payslips/me", { params: { year: 2024 } });
  expect(host.querySelectorAll('[data-testid^="ess-payslip-row-"]')).toHaveLength(1);
  // ringkasan tetap slip terakhir (Desember 2025), bukan baris tahun yang sedang dilihat
  expect(teks(q(host, "ess-payslip-latest"))).toContain("Periode Desember 2025");
});
