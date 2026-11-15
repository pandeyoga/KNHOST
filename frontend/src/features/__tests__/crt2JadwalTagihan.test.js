// CR-T2 — rincian pelanggan Keuangan › Piutang menampilkan baris JADWAL TAGIHAN tersimpan (docs/blueprint/unit/CR-T2.md,
// bagian Layar; U18 = uji jalan di lingkungan A): kolom Pesanan, Tagihan (surat jalan, "Uang muka", cicilan, nota debit),
// Jatuh tempo, Nilai, Dibayar, Sisa, Telat (hari); pesanan dan jurnal terbuka lewat Jejak Dokumen; catatan kaki;
// keadaan memuat, galat, dan kosong ("Tidak ada tagihan terbuka.") dibedakan.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ARAgingDetail from "../finance/ARAgingDetail";
import { TRACE_EVENT } from "../documents/trace/traceDeepLink";
import { setAccessContext } from "../../config/roles";

beforeAll(() => setAccessContext({ role: "admin" }));
afterAll(() => setAccessContext(null));

jest.mock("../../components/AskKnButton", () => ({ __esModule: true, AskKnButton: () => null, PENDING_KEY: "kn_tanya_pending" }));
jest.mock("../finance/payments/PenaltyPanel", () => () => null);
jest.mock("../../components/StoreCreditBadge", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const norm = (s) => String(s || "").replace(/\s+/g, " ").trim();
async function flush(n = 4) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(el); });
  await flush();
  return host;
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  document.body.innerHTML = "";
});

const ITEM_DP = {
  order_id: "so2", order_number: "SO-DP", due_date: "2026-11-03", days_late: 17, overdue: true, grand_total: 2000000,
  paid_total: 0, outstanding: 2000000, ar_ledger: 800000, exposure: 1200000, denda_estimate: 0, penalties: [],
  lines: [
    { sumber: "uang_muka", ref_id: "so2", ref_number: "SO-DP", label: "Uang muka 50%", tanggal: "2026-11-03",
      jatuh_tempo: "2026-11-03", nilai: 1000000, terbayar: 0, sisa: 1000000, hari_lewat: 17, jurnal_id: "",
      line_id: "ppl_dp" },
    { sumber: "surat_jalan", ref_id: "shp1", ref_number: "SJ-9", tanggal: "2026-11-06", jatuh_tempo: "2026-11-20",
      nilai: 400000, terbayar: 0, sisa: 400000, hari_lewat: 0, jurnal_id: "je9", jurnal_number: "JU-0009",
      line_id: "ppl_sj" },
    { sumber: "belum_dikirim", ref_id: "so2", ref_number: "SO-DP", tanggal: null, jatuh_tempo: null, nilai: 600000,
      terbayar: 0, sisa: 600000, hari_lewat: 0, uang_muka: 0 }] };
const ITEM_CICIL = {
  order_id: "so3", order_number: "SO-CICIL", due_date: "2026-09-15", days_late: 35, overdue: true, grand_total: 1000000,
  paid_total: 0, outstanding: 1000000, ar_ledger: 1000000, exposure: 0, denda_estimate: 0, penalties: [],
  lines: [
    { sumber: "rencana", ref_id: "so3", ref_number: "SO-CICIL", label: "Cicilan 1", tanggal: "2026-11-15",
      jatuh_tempo: "2026-09-15", nilai: 500000, terbayar: 0, sisa: 500000, hari_lewat: 35, line_id: "ppl_c1" }] };
const DETAIL = { customer_name: "Toko DP", totals: { total: 3000000, ar_ledger: 1800000, exposure: 1200000 },
  items: [ITEM_DP, ITEM_CICIL], penalties: [] };

const props = (extra = {}) => ({ customerId: "cus1", loading: false, currentUser: { permissions: {} },
  onAccrue: () => {}, onRefresh: () => {}, onClose: () => {}, ...extra });

describe("CR-T2 — Jadwal Tagihan di rincian pelanggan", () => {
  test("kolom spesifikasi, label baris, jatuh tempo tertua dulu, telat ikon + teks, catatan kaki", async () => {
    await mount(<ARAgingDetail detail={DETAIL} {...props()} />);
    const head = [...q("ar-billing-schedule-table").querySelectorAll("th")].map((th) => norm(th.textContent));
    expect(head).toEqual(["Pesanan", "Tagihan", "Jatuh tempo", "Nilai", "Dibayar", "Sisa", "Telat (hari)"]);
    const rows = [...q("ar-billing-schedule-table").querySelectorAll("tbody tr")]
      .map((tr) => [...tr.querySelectorAll("td")].map((td) => norm(td.textContent)));
    expect(rows.map((r) => [r[0], r[1], r[5], r[6]])).toEqual([
      ["SO-CICIL", "Cicilan 1", "Rp 500.000", "35"],
      ["SO-DP", "Uang muka 50%", "Rp 1.000.000", "17"],
      ["SO-DP", "Surat jalan SJ-9 Jurnal JU-0009", "Rp 400.000", "0"]]);
    const telat = q("ar-schedule-so2-uang_muka").querySelector(".status-pill");
    expect(telat.querySelector("svg")).not.toBeNull();
    expect(q("ar-billing-schedule").textContent).not.toContain("Belum dikirim");   // bagian belum dikirim tidak ikut
    expect(norm(q("ar-billing-schedule-note").textContent)).toBe(
      "Umur dihitung per tagihan: surat jalan, uang muka, atau baris rencana.");
  });

  test("pesanan dan jurnal terbuka lewat Jejak Dokumen (L8)", async () => {
    const seen = [];
    const on = (e) => seen.push(e.detail);
    window.addEventListener(TRACE_EVENT, on);
    await mount(<ARAgingDetail detail={DETAIL} {...props()} />);
    await act(async () => { q("ar-schedule-journal-je9").click(); });
    await act(async () => { q("ar-schedule-so3-rencana").querySelector("button").click(); });
    window.removeEventListener(TRACE_EVENT, on);
    expect(seen).toEqual([{ docType: "journal_entry", docId: "je9", number: "JU-0009" },
      { docType: "sales_order", docId: "so3", number: "SO-CICIL" }]);
  });

  test("kosong: hanya bagian belum dikirim → 'Tidak ada tagihan terbuka.'", async () => {
    const satu = { ...ITEM_DP, lines: [ITEM_DP.lines[2]] };
    await mount(<ARAgingDetail detail={{ ...DETAIL, items: [satu] }} {...props()} />);
    expect(norm(q("ar-billing-schedule-empty").textContent)).toBe("Tidak ada tagihan terbuka.");
    expect(q("ar-billing-schedule-table")).toBeNull();
  });

  test("memuat dan galat dibedakan dari kosong", async () => {
    await mount(<ARAgingDetail detail={null} {...props({ loading: true })} />);
    expect(q("ar-aging-detail-loading")).not.toBeNull();
    expect(q("ar-aging-detail-empty")).toBeNull();
    let ulang = 0;
    await mount(<ARAgingDetail detail={null} {...props({ error: "Rincian piutang pelanggan ini gagal dimuat.",
      onRefresh: () => { ulang += 1; } })} />);
    const galat = q("ar-aging-detail-error");
    expect(galat.getAttribute("role")).toBe("alert");
    expect(galat.querySelector("svg")).not.toBeNull();
    expect(q("ar-aging-detail-empty")).toBeNull();
    await act(async () => { galat.querySelector("button").click(); });
    expect(ulang).toBe(1);
  });
});

describe("CR-T2 — Jadwal Tagihan panjang: kotak cari + saringan lewat jatuh tempo", () => {
  test("lebih dari 8 baris → cari dan saringan tampil; hasil kosong dibedakan dari tidak ada tagihan", async () => {
    const lines = Array.from({ length: 10 }, (_, i) => ({ sumber: "surat_jalan", ref_id: `s${i}`, ref_number: `SJ-${i}`,
      jatuh_tempo: `2026-10-${String(i + 1).padStart(2, "0")}`, nilai: 1000, terbayar: 0, sisa: 1000,
      hari_lewat: i < 3 ? 5 : -2, line_id: `l${i}` }));
    const it = { ...ITEM_CICIL, order_id: "so9", order_number: "SO-PANJANG", lines };
    await mount(<ARAgingDetail detail={{ ...DETAIL, items: [it] }} {...props()} />);
    expect(q("ar-billing-schedule-filters")).not.toBeNull();
    await act(async () => { q("ar-billing-schedule-overdue").click(); });
    expect(q("ar-billing-schedule-overdue").getAttribute("aria-pressed")).toBe("true");
    expect(q("ar-billing-schedule-table").querySelectorAll("tbody tr").length).toBe(3);
    const input = q("ar-billing-schedule-search");
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
    await act(async () => { setter.call(input, "tidak-ada"); input.dispatchEvent(new Event("input", { bubbles: true })); });
    expect(norm(q("ar-billing-schedule-nomatch").textContent)).toBe("Tidak ada tagihan yang cocok dengan saringan.");
    expect(q("ar-billing-schedule-empty")).toBeNull();
  });
});
