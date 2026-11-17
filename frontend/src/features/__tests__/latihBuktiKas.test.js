// Pelatihan 18 Nov (audit dokumen cetak) — Bukti Kas: terbilang = angka tercetak (sen ikut), judul berbahasa Indonesia.
import { rpCetak, terbilang } from "../../utils/docPrint";

test("terbilang membaca sen dan rupiahnya sama dengan angka tercetak", () => {
  expect(terbilang(3268672.5)).toBe("Tiga juta dua ratus enam puluh delapan ribu enam ratus tujuh puluh dua rupiah lima puluh sen");
  expect(rpCetak(3268672.5)).toBe("Rp 3.268.672,50");
  expect(terbilang(500000)).toBe("Lima ratus ribu rupiah");
  expect(rpCetak(500000)).toBe("Rp 500.000");
  expect(terbilang(0)).toBe("Nol rupiah");
  expect(rpCetak(-1500.5)).toBe("-Rp 1.500,50");
});

test("judul voucher dalam Bahasa Indonesia (dulu Payment/Received Voucher, Petty Cash)", () => {
  const src = require("fs").readFileSync(require("path").join(__dirname, "../../utils/docPrint.js"), "utf8");
  expect(src).not.toMatch(/"Payment Voucher"|"Received Voucher"|"Petty Cash"/);
  expect(src).toMatch(/Bukti Kas Keluar/);
  expect(src).toMatch(/Bukti Kas Masuk/);
});
