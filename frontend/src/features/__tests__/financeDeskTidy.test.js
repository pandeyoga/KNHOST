// Perapian Meja Finance (14 Nov 2026) — PENYAJIAN saja; isi & hitungan antrean tetap milik server.
//  1. antrean ber-isi tampil dulu (umur tertua → nilai → jumlah), antrean kosong dilipat jadi satu baris;
//  2. papan kontrabon yang kosong = satu baris ringkas; gagal-baca TETAP kotak penuh + Coba lagi (regresi B5);
//  3. grid: kartu terbuka sebaris sama tinggi (`stretch`), kartu ganjil terakhir merentang 2 kolom.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import FinanceDesk from "../finance/FinanceDesk";
import DeskQueueCard from "../sales_admin/DeskQueueCard";
import { compareFilledQueues, splitDeskQueues } from "../sales_admin/deskQueueOrder";

jest.mock("../../services/apiClient", () => ({ __esModule: true, default: { get: jest.fn(), post: jest.fn() }, API: "/api" }));
jest.mock("../sales_admin/SoTrackerCard", () => () => null);
jest.mock("../crm/ARReceiptModal", () => () => null);
const axios = require("../../services/apiClient").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const tick = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
const mounted = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await tick(); await tick();
  mounted.push({ host, root });
  return host;
}
afterEach(async () => {
  while (mounted.length) {
    const { host, root } = mounted.pop();
    await act(async () => { root.unmount(); });
    host.remove();
  }
});

// 11 antrean Meja Finance, urutan server (backend/services/work_desk_service.finance_desk).
const IDS = ["siap_faktur_pajak", "uang_masuk", "bayar_sebelum_kirim", "selisih_bayar", "denda_draft", "jatuh_tempo",
  "hutang_jatuh_tempo", "uang_muka_belum_kirim", "nota_batal_item", "sample_acc_bayar", "retur_putus_nilai"];
const LABEL = {
  siap_faktur_pajak: "Siap terbitkan Faktur Pajak", uang_masuk: "Uang masuk perlu dicatat & dialokasikan",
  selisih_bayar: "Selisih bayar perlu diputuskan", denda_draft: "Denda perlu diterbitkan",
  jatuh_tempo: "Jatuh tempo (sudah lewat)",
};
const row = (qid, i, value, age) => ({ ref_type: "sales_order", ref_id: `${qid}-${i}`, number: `DOC-${qid}-${i}`,
  title: `Pelanggan ${i}`, subtitle: "", value, age_days: age, badge: "", action: "Buka", action_kind: "open" });
const queue = (id, rows = []) => ({
  id, label: LABEL[id] || id, hint: `Petunjuk ${id}`, owner: "finance", value_kind: "money", value_label: "Nilai",
  count: rows.length, shown: rows.length, rows, action_label: "Buka",
  total_value: rows.reduce((s, r) => s + r.value, 0), oldest_age_days: Math.max(0, ...rows.map((r) => r.age_days)),
});
const desk = (filled = {}) => ({
  desk: "finance", queues: IDS.map((id) => queue(id, filled[id] || [])),
  totals: { open_items: 0, advance_liability: 0 }, not_my_desk: [],
});
const homeFinance = (count = 0, rows = []) => ({
  waiting_boards: [{ key: "contra_bon_approve", label: "Kontrabon menunggu persetujuan", view: "contra-bons",
    count, shown: rows.length, hidden: 0, truncated: false, rows }],
});
function routeGet({ deskData, home = homeFinance(), homeFails = false }) {
  axios.get.mockImplementation(async (url) => {
    if (url === "/api/finance/desk") return { data: deskData };
    if (url === "/api/home/finance") {
      if (homeFails) throw new Error("network");
      return { data: home };
    }
    throw new Error(`URL tak terduga: ${url}`);
  });
}
beforeEach(() => { axios.get.mockReset(); axios.post.mockReset(); });

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

// ─── keadaan SEMUA kosong ────────────────────────────────────────────────────
test("semua antrean kosong: tanpa kartu besar, satu baris 'Semua 11 antrean bersih' yang bisa dibuka", async () => {
  routeGet({ deskData: desk() });
  const host = await mount(<FinanceDesk selectedEntity="all" />);

  expect(q(host, "fin-desk-queues")).toBeNull();
  for (const id of IDS) expect(q(host, `fin-desk-queue-${id}`)).toBeNull();

  const fold = q(host, "fin-desk-empty-fold");
  expect(fold.getAttribute("data-all-empty")).toBe("true");
  expect(q(host, "fin-desk-empty-fold-title").textContent).toMatch(/^Semua 11 antrean bersih — tidak ada yang perlu ditindak$/);
  expect(q(host, "fin-desk-empty-fold-summary").textContent)
    .toBe(IDS.map((id) => LABEL[id] || id).join(" · "));               // semua antrean tetap TERSEBUT

  const toggle = q(host, "fin-desk-empty-fold-toggle");
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  expect(toggle.className).toMatch(/\bghost-button\b/);                 // tombol baku (KN_37 §4)
  await act(async () => { toggle.click(); });
  expect(toggle.getAttribute("aria-expanded")).toBe("true");
  expect(toggle.textContent).toMatch(/Sembunyikan/);
  expect(q(host, "fin-desk-empty-fold-summary")).toBeNull();
  const list = q(host, "fin-desk-empty-fold-list");
  expect(toggle.getAttribute("aria-controls")).toBe(list.id);
  expect(list.querySelectorAll("li")).toHaveLength(11);
  for (const id of IDS) expect(q(host, `fin-desk-count-${id}`).textContent).toBe("0");
  expect(q(host, "fin-desk-empty-item-denda_draft").textContent).toMatch(/Denda perlu diterbitkan.*Petunjuk denda_draft/);

  expect(q(host, "fin-desk-metric-open").textContent).toMatch(/Perlu Ditindak\s*0/);
});

// ─── keadaan SEBAGIAN berisi ─────────────────────────────────────────────────
test("sebagian berisi: kartu ber-isi dulu (umur tertua), kosong dilipat, ganjil terakhir merentang 2 kolom", async () => {
  routeGet({ deskData: desk({
    siap_faktur_pajak: [row("siap_faktur_pajak", 1, 17754616.5, 0)],
    uang_masuk: [row("uang_masuk", 1, 2500000, 4), row("uang_masuk", 2, 5000000, 3)],
    selisih_bayar: [row("selisih_bayar", 1, 125000, 9)],
  }) });
  const host = await mount(<FinanceDesk selectedEntity="all" />);

  const grid = q(host, "fin-desk-queues");
  const cards = [...grid.querySelectorAll(":scope > section")];
  expect(cards.map((c) => c.getAttribute("data-testid")))
    .toEqual(["fin-desk-queue-selisih_bayar", "fin-desk-queue-uang_masuk", "fin-desk-queue-siap_faktur_pajak"]);
  // tinggi seragam: kartu terbuka ikut setinggi baris grid (bukan self-start); kartu ke-3 (ganjil) merentang.
  for (const c of cards) { expect(c.className).toMatch(/\bflex-col\b/); expect(c.className).not.toMatch(/self-start/); }
  expect(cards[2].className).toMatch(/xl:col-span-2/);
  expect(cards[0].className).not.toMatch(/col-span/);

  // angka & baris dari server tidak diubah
  expect(q(host, "fin-desk-count-uang_masuk").textContent).toBe("2");
  expect(q(host, "fin-desk-total-uang_masuk").textContent).toMatch(/7\.500\.000/);
  expect(q(host, "fin-desk-uang_masuk-row-uang_masuk-2")).not.toBeNull();
  expect(q(host, "fin-desk-metric-open").textContent).toMatch(/Perlu Ditindak\s*4/);

  // yang kosong: satu baris, tanpa kartu besar
  expect(q(host, "fin-desk-queue-denda_draft")).toBeNull();
  expect(q(host, "fin-desk-empty-fold").getAttribute("data-all-empty")).toBe("false");
  expect(q(host, "fin-desk-empty-fold-title").textContent).toMatch(/^8 antrean kosong/);
  expect(q(host, "fin-desk-empty-fold-summary").textContent).not.toMatch(/Selisih bayar|Uang masuk|Faktur Pajak/);

  // kartu ditutup pengguna → kembali memakai tingginya sendiri
  await act(async () => { q(host, "fin-desk-queue-toggle-selisih_bayar").click(); });
  expect(q(host, "fin-desk-queue-selisih_bayar").className).toMatch(/self-start/);
});

test("dua antrean berisi: tidak ada kartu yang merentang (baris penuh)", async () => {
  routeGet({ deskData: desk({ siap_faktur_pajak: [row("siap_faktur_pajak", 1, 100, 1)],
    jatuh_tempo: [row("jatuh_tempo", 1, 50, 30)] }) });
  const host = await mount(<FinanceDesk selectedEntity="all" />);
  const cards = [...q(host, "fin-desk-queues").querySelectorAll(":scope > section")];
  expect(cards.map((c) => c.getAttribute("data-testid"))).toEqual(["fin-desk-queue-jatuh_tempo", "fin-desk-queue-siap_faktur_pajak"]);
  for (const c of cards) expect(c.className).not.toMatch(/col-span/);
  expect(q(host, "fin-desk-empty-fold-title").textContent).toMatch(/^9 antrean kosong/);
});

// ─── papan kontrabon ─────────────────────────────────────────────────────────
test("papan kontrabon kosong = satu baris ringkas (ikon + teks), tautan Buka Kontrabon tetap ada", async () => {
  routeGet({ deskData: desk() });
  const host = await mount(<FinanceDesk selectedEntity="all" />);
  const board = q(host, "fin-home-board-contra_bon_approve");
  expect(board.getAttribute("data-board-compact")).toBe("empty");
  expect(q(host, "fin-home-board-contra_bon_approve-empty").textContent)
    .toMatch(/Tidak ada kontrabon yang menunggu persetujuan/);
  expect(board.querySelector("svg")).not.toBeNull();                    // status = ikon + teks + warna
  const goto = q(host, "fin-home-board-contra_bon_approve-goto");
  expect(goto.className).toMatch(/\blink-button\b/);
  expect(goto.disabled).toBe(false);
});

test("papan kontrabon berisi tetap papan penuh; gagal dibaca tetap kotak penuh + Coba lagi (B5)", async () => {
  const r = { id: "cb1", number: "CB-001", title: "PT Pemasok", amount: 1000000, days_waiting: 3 };
  routeGet({ deskData: desk(), home: homeFinance(1, [r]) });
  let host = await mount(<FinanceDesk selectedEntity="all" />);
  expect(q(host, "fin-home-board-contra_bon_approve").getAttribute("data-board-compact")).toBeNull();
  expect(q(host, "fin-home-board-contra_bon_approve-list")).not.toBeNull();

  routeGet({ deskData: desk(), homeFails: true });
  host = await mount(<FinanceDesk selectedEntity="all" />);
  expect(q(host, "fin-home-board-contra_bon_approve").getAttribute("data-board-compact")).toBeNull();
  expect(q(host, "fin-home-board-contra_bon_approve-unreadable")).not.toBeNull();
  expect(q(host, "fin-home-board-contra_bon_approve-retry")).not.toBeNull();
});

// ─── kompatibilitas meja lain ────────────────────────────────────────────────
test("DeskQueueCard tanpa `stretch` tetap self-start (Meja Admin Sales/Meja Saya tidak berubah)", async () => {
  const host = await mount(<DeskQueueCard queue={queue("uang_masuk", [row("uang_masuk", 1, 10, 1)])} testPrefix="x" />);
  expect(q(host, "x-queue-uang_masuk").className).toBe("section-card self-start");
});
