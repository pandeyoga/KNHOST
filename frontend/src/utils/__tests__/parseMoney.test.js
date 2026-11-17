// Uji variasi isian pelatihan keuangan 18 Nov — pembaca nominal rupiah `utils/parseMoney` (dipakai `MoneyInput`).
// Bentuk yang diuji = yang benar-benar diketik/ditempel peserta (mutasi BCA, kwitansi, nota) + bentuk yang DIPEGANG
// pemanggil MoneyInput (angka, String(angka), teks kanonik, teks lama).
import { parseMoney, isMoneyDraft, moneyText, heldMoney } from "../parseMoney";
import { parseDecimal } from "../decimalInput";

describe("parseMoney — cara orang Indonesia menulis uang", () => {
  test.each([
    ["3.374.123", 3374123],
    ["3374123", 3374123],
    ["3,374,123", 3374123],
    ["3374122,5", 3374122.5],
    ["3374122.5", 3374122.5],
    ["3374122,50", 3374122.5],
    ["3.374.122,50", 3374122.5],
    ["3,374,122.50", 3374122.5],
    ["Rp 3.374.123", 3374123],
    ["Rp3.374.123", 3374123],
    ["Rp. 3.374.123,-", 3374123],
    ["IDR 3,374,123.00", 3374123],
    ["  3 374 123  ", 3374123],
    ["Rp 3.374.123", 3374123],
    ["1.500", 1500],
    ["1,500", 1500],
    ["12.50", 12.5],
    ["0,500", 0.5],
    ["1234.567", 1234.567],
    ["99.999.999.999", 99999999999],
    ["0", 0],
    ["-100", -100],
    ["-Rp 1.500", -1500],
    ["3374122,", 3374122],
    ["3.374.", 3374],
  ])("%s → %d", (txt, n) => {
    expect(parseMoney(txt)).toBe(n);
  });

  test.each(["", "abc", "Rp", "-", ",", "3.374.1a"])("%s → NaN", (txt) => {
    expect(Number.isNaN(parseMoney(txt))).toBe(true);
  });

  test("angka dibiarkan", () => { expect(parseMoney(3374122.5)).toBe(3374122.5); });
});

describe("isMoneyDraft — yang boleh diketik/ditempel", () => {
  test.each(["", "3", "3.", "3.374.", "3.374.123", "3,374,123", "Rp 3.374.123", "Rp", "R", "IDR 1", "-", "-100",
    "3 374 123", "3.374.123,-", "3374122,5"])("boleh: %s", (t) => { expect(isMoneyDraft(t)).toBe(true); });
  test.each(["abc", "3x", "1e5", "Rp 1.000 (transfer)", "+-1", "#100"])("ditolak: %s", (t) => {
    expect(isMoneyDraft(t)).toBe(false);
  });
});

describe("moneyText — nilai yang diterima pemanggil MoneyInput", () => {
  // Pemanggil membaca nilai dengan tiga cara: Number(v) (kwitansi, kas, LPJ), parseDecimal(v) (anggaran, aset),
  // atau mengirim teksnya ke backend (`core_utils.parse_decimal`, titik = desimal untuk teks polos). Ketiganya harus
  // mendapat nominal yang sama dengan pratinjau.
  test.each([
    ["3.374.123", 3374123], ["3374122,5", 3374122.5], ["Rp 3.374.122,50", 3374122.5], ["3,374,123", 3374123],
    ["1.500", 1500], ["0", 0], ["-100", -100],
  ])("%s → kanonik dibaca sama oleh Number & parseDecimal", (txt, n) => {
    const v = moneyText(txt);
    expect(v).toMatch(/^-?\d+(\.\d+)?$/);
    expect(Number(v)).toBe(n);
    expect(parseDecimal(v)).toBe(n);
  });
  test.each(["", "Rp", "-", "abc"])("%s → '' (kosong)", (t) => { expect(moneyText(t)).toBe(""); });
});

describe("heldMoney — nilai yang dipegang pemanggil", () => {
  test.each([
    [3374122.5, 3374122.5], ["3374122.5", 3374122.5], [String(1.5), 1.5], ["1500", 1500], ["0", 0],
    ["3.374.123", 3374123], ["10,5", 10.5],
  ])("%p → %d", (v, n) => { expect(heldMoney(v)).toBe(n); });
  test.each([null, undefined, ""])("%p → NaN", (v) => { expect(Number.isNaN(heldMoney(v))).toBe(true); });
});
