// Pelatihan 18 Nov — uji variasi isian bagian Hutang · Pajak · Gaji (V6–V7): setoran bersen tidak dibulatkan di pesan,
// dan kekurangan uang sample berbayar dihitung dari uang yang tercatat masuk.
import { galatForm } from "../hr/PayrollRemittancesView";
import { sampleKurangBayar } from "../samples/SampleOrdersView";

const nb = (s) => String(s || "").replace(/[  ]/g, " ");

test("V7 — sisa PPh 21 bersen: pesan menulis sennya, nominal = sisa diterima, lebih Rp 0,5 ditolak", () => {
  const f = (amount) => galatForm({ kind: "pph21", period: "2026-10", amount, paid_date: "2026-11-18" }, 33883.5);
  expect(f("33.883,50")).toBe("");
  expect(f("33883.5")).toBe("");
  // MoneyInput mengirim teks kanonik: "33.884" yang diketik sampai di form sebagai "33884".
  expect(nb(f("33884"))).toBe("Nominal melebihi sisa kewajiban (Rp 33.883,5).");
  expect(nb(galatForm({ kind: "bpjs", period: "2026-10", amount: "200000", paid_date: "2026-11-10" }, 150000)))
    .toBe("Nominal melebihi sisa kewajiban (Rp 150.000).");
});

test("V6 — sample berbayar: kurang bayar = total − uang tercatat; lunas / gratis = 0", () => {
  expect(sampleKurangBayar({ sample_billing: "paid", grand_total: 83250, paid_total: 50000 })).toBe(33250);
  expect(sampleKurangBayar({ sample_billing: "paid", grand_total: 83250 })).toBe(83250);
  expect(sampleKurangBayar({ sample_billing: "paid", grand_total: 83250, paid_total: 83250 })).toBe(0);
  expect(sampleKurangBayar({ sample_billing: "paid", grand_total: 83250, paid_total: 100000 })).toBe(0);
  expect(sampleKurangBayar({ sample_billing: "free", grand_total: 0 })).toBe(0);
});
