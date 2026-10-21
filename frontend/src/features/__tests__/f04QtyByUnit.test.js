// F-04 (uji pra-UAT 2026-10-21) — KPI POS menampilkan stok per satuan ("yard · kg"), bukan satu angka gabungan.
import { formatUnitTotals, formatQtyByUnit } from "../../utils/qtyByUnit";

test("rincian per satuan, urut nama satuan, nol diabaikan", () => {
  expect(formatUnitTotals({ yard: 1250, kg: 340.5, meter: 0 }, 1590.5)).toBe("340,5 kg · 1.250 yard");
});

test("tanpa rincian dari server → angka lama sebagai cadangan; rincian kosong → 0", () => {
  expect(formatUnitTotals(undefined, 1590.5)).toBe("1.590,5");
  expect(formatUnitTotals({}, 99)).toBe("0");
});

test("utilitas lama formatQtyByUnit (Daftar/ringkas pesanan) tetap utuh", () => {
  expect(formatQtyByUnit([{ unit: "yard", qty: 10, qty_rolls: 1 }, { unit: "kg", qty: 5 }])).toBe("10 yard (1 roll) · 5 kg");
});
