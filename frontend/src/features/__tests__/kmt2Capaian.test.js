// KM-T2 — SDM › Kinerja & Insentif › Capaian (`incentive-capaian`), sisi layar tanpa peramban:
//  · U16 — centang Andi dan Budi → bilah "2 baris dipilih · Omzet bersih: jumlah Rp 1.500.000.000 · rata-rata
//    Rp 750.000.000 · Uang masuk: jumlah Rp 1.220.000.000 · rata-rata Rp 610.000.000", TANPA permintaan jaringan baru;
//  · baris definisi, peringatan pencocokan, persen satu desimal berkoma ("86,2 %"), target 0 tampil "—";
//  · telusur: klik angka Uang masuk → panel "{kolom} — {sales} — {periode}" + "Jumlah Rp … dari {n} dokumen";
//  · "Semua PT" → satu kalimat tanpa memanggil server; kosong → satu kalimat; kolom margin hanya bila server mengirimnya.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CapaianView, { barisDefinisi, kolomTampil, persen, selisihPembanding, teksPeringatan, teksPilihan,
  TEKS_KOSONG, TEKS_SEMUA_PT } from "../incentive/CapaianView";
import { judulPanel, teksPilihanDokumen } from "../incentive/CapaianSourcesPanel";
import { AppNavProvider } from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { setAccessContext } from "../../config/roles";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), put: () => Promise.resolve({ data: {} }), post: () => Promise.resolve({ data: {} }),
    patch: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../components/EntityScopeBanner", () => () => <div data-testid="cap-scope" />);
jest.mock("../../components/KNSelect", () => () => null);
jest.mock("../../components/KNDatePicker", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const ENT = [{ id: "ent_kanda", legal_name: "CV Kanda Suka", short_name: "Kanda" }];
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const txt = (el) => (el?.textContent || "").replace(/\u00a0/g, " ");
async function settle() { for (let i = 0; i < 6; i += 1) await act(async () => {}); }
const klik = async (el) => { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await settle(); };
const onOpenDocument = jest.fn();
async function mount({ entity = "ent_kanda" } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(
      <EntityScopeProvider selectedEntity={entity} entities={ENT} canSwitch>
        <AppNavProvider role="manager" onOpenDocument={onOpenDocument}><CapaianView currentUser={{ id: "u_mgr" }} /></AppNavProvider>
      </EntityScopeProvider>);
  });
  await settle();
  return host;
}

const BARIS = (over) => ({
  target_sales: 0, target_collection: 0, omzet: 0, retur: 0, omzet_bersih: 0, pct_omzet: null, uang_masuk: 0,
  pct_pencairan: null, sisa_piutang: 0, lewat_tempo: 0, realisasi_harga_pct: null, rata_potongan_pct: null,
  porsi_bawah_acuan_pct: null, margin_pct: null, pelanggan_baru: 0, jumlah_pesanan: 0, catatan_data: [], has_numbers: true, ...over,
});
// Data U1 (Andi) dan U3 (Budi) — rancangan `05` §4.2, Oktober 2026.
const ANDI = BARIS({ key: "u_andi", sales_id: "u_andi", name: "Andi", target_sales: 800000000, target_collection: 750000000,
  omzet: 1000000000, omzet_bersih: 1000000000, pct_omzet: 125, uang_masuk: 700000000, pct_pencairan: 93.3,
  realisasi_harga_pct: 86.2, rata_potongan_pct: 13.8, porsi_bawah_acuan_pct: 100, margin_pct: 30, jumlah_pesanan: 1 });
const BUDI = BARIS({ key: "u_budi", sales_id: "u_budi", name: "Budi", target_sales: 500000000, target_collection: 450000000,
  omzet: 500000000, omzet_bersih: 500000000, pct_omzet: 100, uang_masuk: 520000000, pct_pencairan: 115.6,
  realisasi_harga_pct: 100, rata_potongan_pct: 0, porsi_bawah_acuan_pct: 0, margin_pct: 30, jumlah_pesanan: 1 });
const CICI = BARIS({ key: "u_cici", sales_id: "u_cici", name: "Cici", has_numbers: false });
const DEF = { version: 2, effective_from: "2026-11-14", dasar_omzet: "terkirim", columns: { omzet: "Nilai barang terkirim (surat jalan) dalam periode, tanpa PPN." },
  labels: [{ field: "dasar_omzet", value_label: "Saat barang dikirim" }, { field: "isi_pencairan", value_label: "Hanya uang yang masuk" },
    { field: "pemilik_angka", value_label: "Sales pada pesanan" }, { field: "harga_acuan", value_label: "Harga daftar PT" }] };
const CAPAIAN = {
  entity_id: "ent_kanda", group_by: "sales", margin_visible: true, facts_as_of: "2026-11-14T03:05:00+00:00",
  period: { type: "month", key: "2026-10", label: "Oktober 2026", short_label: "Okt 2026", date_from: "2026-10-01", date_to: "2026-10-31" },
  definition: DEF, reconciliation: { omzet_ok: true, omzet_diff: 0, pencairan_ok: true, pencairan_diff: 0 },
  rows: [ANDI, BUDI, CICI], notes: [], compare: { label: "", by_key: {} },
  totals: { ...BARIS({}), omzet: 1500000000, omzet_bersih: 1500000000, uang_masuk: 1220000000, target_sales: 1300000000, target_collection: 1200000000 },
};
const SUMBER = { metric: "uang_masuk", total: 2, sum: 520000000, page: 1, page_size: 50, items: [
  { doc_type: "ar_receipt", doc_id: "rb1", doc_number: "KW/KND/RB1", date_wib: "2026-10-15", customer_name: "Toko Budi", so_id: "ob1",
    so_number: "SO/OB1", source_kind: "kas", source_label: "Kwitansi", split: 1, amount: 500000000,
    link: { view: "collection-worklist", tab: "", focus_type: "ar_receipt", focus_id: "rb1", number: "KW/KND/RB1" } },
  { doc_type: "ar_receipt", doc_id: "rb0", doc_number: "KW/KND/RB0", date_wib: "2026-10-16", customer_name: "Toko Budi", so_id: "ob0",
    so_number: "SO/OB0", source_kind: "kas", source_label: "Kwitansi", split: 1, amount: 20000000,
    link: { view: "collection-worklist", tab: "", focus_type: "ar_receipt", focus_id: "rb0", number: "KW/KND/RB0" } }] };
function api({ capaian = CAPAIAN } = {}) {
  mockGet.mockImplementation((url) => {
    if (url === "/api/incentive/achievement") return Promise.resolve({ data: capaian });
    if (url === "/api/incentive/achievement/sources") return Promise.resolve({ data: SUMBER });
    return Promise.resolve({ data: {} });
  });
}
beforeEach(() => { try { window.localStorage.clear(); } catch (_) { /* tanpa penyimpanan */ } });
afterEach(() => { mockGet.mockReset(); onOpenDocument.mockReset(); document.body.innerHTML = ""; setAccessContext(null); });

describe("fungsi murni", () => {
  test("persen satu desimal berkoma; kosong = —", () => {
    expect(persen(86.2)).toBe("86,2 %");
    expect(persen(100)).toBe("100,0 %");
    expect(persen(null)).toBe("—");
  });
  test("baris definisi dan peringatan pencocokan", () => {
    expect(barisDefinisi(DEF)).toBe("Omzet: Saat barang dikirim · Pencairan: Hanya uang yang masuk · Milik: Sales pada pesanan · "
      + "Harga acuan: Harga daftar PT — berlaku sejak 14 Nov 2026 (versi 2)");
    expect(teksPeringatan({ omzet_ok: true, pencairan_ok: true })).toBe("");
    expect(teksPeringatan({ omzet_ok: false, omzet_diff: 1000000, pencairan_ok: true, pencairan_diff: 0 }).replace(/\u00a0/g, " "))
      .toBe("Angka belum cocok dengan pembukuan (omzet selisih Rp 1.000.000, pencairan selisih Rp 0). Lihat rinciannya di tab Target & Aturan.");
  });
  test("selisih pembanding: '+Rp 480.000.000 dari Sep 2026'", () => {
    const s = selisihPembanding(500000000, 20000000, "Sep 2026");
    expect(`${s.angka} ${s.dari}`.replace(/\u00a0/g, " ")).toBe("+Rp 480.000.000 dari Sep 2026");
    expect(selisihPembanding(0, 20000000, "Sep 2026").angka.replace(/\u00a0/g, " ")).toBe("−Rp 20.000.000");
  });
  test("U16 (fungsi) — jumlah & rata-rata pilihan dari angka yang tampil", () => {
    expect(teksPilihan([ANDI, BUDI], new Set(["u_andi", "u_budi"])).replace(/\u00a0/g, " ")).toBe(
      "2 baris dipilih · Omzet bersih: jumlah Rp 1.500.000.000 · rata-rata Rp 750.000.000 · Uang masuk: jumlah Rp 1.220.000.000 · rata-rata Rp 610.000.000");
    expect(teksPilihan([ANDI], new Set())).toBe("");
    // pengelompokan tanpa uang masuk (kategori): bagian uang masuk tidak ditulis
    expect(teksPilihan([{ ...ANDI, uang_masuk: null }], new Set(["u_andi"])).replace(/\u00a0/g, " ")).toBe(
      "1 baris dipilih · Omzet bersih: jumlah Rp 1.000.000.000 · rata-rata Rp 1.000.000.000");
    expect(teksPilihanDokumen(SUMBER.items, new Set(["ar_receipt:rb1:ob1:kas", "ar_receipt:rb0:ob0:kas"])).replace(/\u00a0/g, " ")).toBe(
      "2 dokumen dipilih · jumlah Rp 520.000.000 · rata-rata Rp 260.000.000");
    expect(judulPanel({ metricLabel: "Uang masuk", name: "Budi", periodLabel: "Oktober 2026" })).toBe("Uang masuk — Budi — Oktober 2026");
  });
  test("kolom: pilihan per kelompok; margin hanya bila dikirim; kolom per-sales hanya saat per sales", () => {
    const f = (k, o) => kolomTampil(k, o).map((c) => c.f);
    expect(f("ringkas", { perSales: true, marginVisible: true })).toEqual(["omzet", "pct_omzet", "omzet_bersih", "uang_masuk", "pct_pencairan", "realisasi_harga_pct"]);
    expect(f("harga", { perSales: true, marginVisible: false })).not.toContain("margin_pct");
    expect(f("harga", { perSales: true, marginVisible: true })).toContain("margin_pct");
    expect(f("semua", { perSales: false, marginVisible: true })).not.toContain("target_sales");
    expect(f("omzet", { perSales: true, marginVisible: true })).toEqual(["target_sales", "omzet", "pct_omzet", "retur", "omzet_bersih"]);
  });
});

describe("layar Capaian", () => {
  test("U16 — centang Andi dan Budi: bilah jumlah pilihan tanpa permintaan jaringan baru", async () => {
    setAccessContext({ role: "manager", permissions: { incentive: ["view", "view_margin"] } });
    api();
    const host = await mount();
    expect(txt(q(host, "cap-definition"))).toContain("berlaku sejak 14 Nov 2026 (versi 2)");
    expect(q(host, "cap-warning")).toBeNull();
    expect(q(host, "cap-row-u_cici")).toBeNull();                       // tanpa angka → disembunyikan (bawaan)
    expect(txt(q(host, "cap-count"))).toContain("1 tanpa angka disembunyikan");
    expect(txt(q(host, "cap-row-u_andi"))).toContain("86,2 %");
    expect(txt(q(host, "cap-asof"))).toBe("Data per pukul 10:05 WIB");
    expect(q(host, "cap-head-omzet").getAttribute("title")).toContain("terkirim");
    const panggilan = mockGet.mock.calls.length;
    await klik(q(host, "cap-check-u_andi"));
    await klik(q(host, "cap-check-u_budi"));
    expect(txt(q(host, "cap-selection"))).toContain(
      "2 baris dipilih · Omzet bersih: jumlah Rp 1.500.000.000 · rata-rata Rp 750.000.000 · Uang masuk: jumlah Rp 1.220.000.000 · rata-rata Rp 610.000.000");
    expect(mockGet.mock.calls.length).toBe(panggilan);
  });

  test("telusur uang masuk Budi → panel dua kwitansi Rp 520.000.000; nomor membuka kwitansi", async () => {
    setAccessContext({ role: "manager", permissions: { incentive: ["view"] } });
    api();
    const host = await mount();
    await klik(q(host, "cap-drill-uang_masuk-u_budi"));
    expect(txt(q(document.body, "cap-src-title"))).toBe("Uang masuk — Budi — Oktober 2026");
    const [url, cfg] = mockGet.mock.calls[mockGet.mock.calls.length - 1];
    expect(url).toBe("/api/incentive/achievement/sources");
    expect(cfg.params).toMatchObject({ metric: "uang_masuk", sales_id: "u_budi", period_type: "month", period: "2026-10" });
    expect(txt(q(document.body, "cap-src-sum"))).toBe("Jumlah Rp 520.000.000 dari 2 dokumen");
    expect(q(document.body, "cap-src-table").querySelectorAll("tbody tr")).toHaveLength(2);
    await klik(q(document.body, "cap-src-check-rb0"));
    expect(txt(q(document.body, "cap-src-selection"))).toBe("1 dokumen dipilih · jumlah Rp 20.000.000 · rata-rata Rp 20.000.000");
    await klik(q(document.body, "cap-src-open-rb0"));
    expect(onOpenDocument).toHaveBeenCalledWith(expect.objectContaining({ view: "collection-worklist", focus_type: "ar_receipt", focus_id: "rb0", number: "KW/KND/RB0" }));
  });

  test("peringatan pencocokan; target 0 tampil —; pembanding di bawah omzet bersih", async () => {
    setAccessContext({ role: "manager", permissions: { incentive: ["view"] } });
    api({ capaian: { ...CAPAIAN, reconciliation: { omzet_ok: false, omzet_diff: -50000, pencairan_ok: true, pencairan_diff: 0 },
      rows: [{ ...BUDI, target_sales: 0, pct_omzet: null }], compare: { label: "Sep 2026", by_key: { u_budi: { omzet_bersih: 20000000, uang_masuk: 0 } }, totals: { omzet_bersih: 20000000, uang_masuk: 0 } } } });
    window.localStorage.setItem("kn.capaian.tampilan.u_mgr", JSON.stringify({ kolom: "omzet" }));   // tampilan tersimpan
    const host = await mount();
    const sel = q(host, "cap-row-u_budi").querySelectorAll("td");
    expect(sel[1].textContent).toBe("—");                                 // kolom Target (Omzet) dengan target 0
    expect(q(host, "cap-head-target_sales")).not.toBeNull();
    expect(txt(q(host, "cap-warning"))).toContain("omzet selisih Rp 50.000");
    expect(q(host, "cap-warning").querySelector("svg")).not.toBeNull();
    expect(txt(q(host, "cap-cmp-omzet_bersih-u_budi"))).toBe("+Rp 480.000.000 dari Sep 2026");
  });

  test("Semua PT: satu kalimat, tanpa memanggil server", async () => {
    setAccessContext({ role: "manager", permissions: { incentive: ["view"] } });
    api();
    const host = await mount({ entity: "all" });
    expect(txt(q(host, "cap-all-pt"))).toBe(TEKS_SEMUA_PT);
    expect(mockGet).not.toHaveBeenCalled();
  });

  test("kosong: satu kalimat, tanpa tabel", async () => {
    setAccessContext({ role: "manager", permissions: { incentive: ["view"] } });
    api({ capaian: { ...CAPAIAN, rows: [CICI] } });
    const host = await mount();
    expect(txt(q(host, "cap-empty"))).toBe(TEKS_KOSONG);
    expect(q(host, "cap-table")).toBeNull();
  });
});
