// Perapian Meja Finance (14 Nov 2026, cabang gifted-cori `01ce23b`) — yang dipakai sesudah digabung ke desain MN-T2:
// urutan kelompok berisi umur tertua → nilai → jumlah (`deskQueueOrder`). Lipatan antrean kosong, papan kosong ringkas,
// dan kartu merentang tidak dipakai: MN-T2 menyembunyikan kelompok kosong dan memakai satu kolom (integrasi 15 Nov).
import { compareFilledQueues, splitDeskQueues } from "../sales_admin/deskQueueOrder";

// ─── urutan (modul murni) ────────────────────────────────────────────────────
test("splitDeskQueues: ber-isi urut umur tertua → nilai → jumlah; kosong tetap urutan server; masukan tidak diubah", () => {
  const input = [
    { id: "a", count: 0 },
    { id: "b", count: 2, oldest_age_days: 3, total_value: 100, value_kind: "money" },
    { id: "c", count: 1, oldest_age_days: 9, total_value: 5, value_kind: "money" },
    { id: "d", count: 0 },
    { id: "e", count: 4, oldest_age_days: 3, total_value: 900, value_kind: "money" },
    { id: "f", count: 7, oldest_age_days: 3, total_value: 900, value_kind: "money" },
  ];
  const snapshot = JSON.stringify(input);
  const { filled, empty } = splitDeskQueues(input);
  expect(filled.map((x) => x.id)).toEqual(["c", "f", "e", "b"]);   // 9 hari dulu; seri umur → nilai → jumlah
  expect(empty.map((x) => x.id)).toEqual(["a", "d"]);
  expect(JSON.stringify(input)).toBe(snapshot);
  expect(splitDeskQueues(null)).toEqual({ filled: [], empty: [] });
});

test("compareFilledQueues: yard/jumlah dokumen tidak dibandingkan dengan rupiah; seri penuh → urutan server", () => {
  const money = { count: 1, oldest_age_days: 2, total_value: 10, value_kind: "money" };
  const qty = { count: 1, oldest_age_days: 2, total_value: 99999, value_kind: "qty" };
  expect(compareFilledQueues(money, qty)).toBe(0);                  // nilai beda satuan → tidak menentukan urutan
  const { filled } = splitDeskQueues([{ id: "x", ...money }, { id: "y", ...qty }]);
  expect(filled.map((r) => r.id)).toEqual(["x", "y"]);
});
