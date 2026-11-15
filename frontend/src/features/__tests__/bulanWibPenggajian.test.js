// Uji jalan PY-T4 (15 Nov): daftar bulan penggajian/cuti mundur satu bulan di peramban ber-zona WIB pukul 17.00–24.00
// (`recentMonths` memakai setDate/setMonth waktu lokal sesudah menambah 7 jam). Bukti merah butuh zona proses WIB:
// `TZ=Asia/Jakarta CI=true npx craco test … bulanWibPenggajian` (kode lama: 1 gagal; kode baru: 2 lulus). Di zona UTC
// kedua versi lulus — uji ini tetap menjaga hasilnya.
import { recentMonths as bulanGaji, curMonth } from "../hr/payrollUtils";
import { recentMonths as bulanCuti } from "../hr/leaveUtils";

afterEach(() => jest.useRealTimers());

test("bulan berjalan WIB ada di urutan pertama pada pukul 22.30 WIB", () => {
  jest.useFakeTimers().setSystemTime(new Date("2026-11-15T15:30:00Z"));   // 22.30 WIB
  expect(curMonth()).toBe("2026-11");
  expect(bulanGaji(3)).toEqual(["2026-11", "2026-10", "2026-09"]);
  expect(bulanCuti(3)).toEqual(["2026-11", "2026-10", "2026-09"]);
});

test("pergantian tahun: Januari WIB lalu Desember tahun sebelumnya", () => {
  jest.useFakeTimers().setSystemTime(new Date("2025-12-31T18:00:00Z"));   // 1 Jan 2026 01.00 WIB
  expect(bulanGaji(2)).toEqual(["2026-01", "2025-12"]);
});
