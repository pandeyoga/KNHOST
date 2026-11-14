// KM-T1 — SDM › Kinerja & Insentif › Target & Aturan (`incentive-setup`), sisi layar tanpa peramban:
//  · tiga bagian (Target · Komponen insentif · Definisi angka) + kartu Pencocokan angka; keterangan target spesifikasi;
//  · "Semua PT" → tombol Simpan mati dengan alasan "Pilih satu PT untuk mengatur target." tertulis di sampingnya;
//  · tanpa izin `incentive.configure` → tombol mati + alasan; dengan izin → Simpan mengirim PUT hanya untuk baris diubah;
//  · komponen kosong: "Belum ada komponen. Tambahkan mis. Insentif Bulanan."; status Aktif berikon + teks;
//  · pencocokan: "Cocok" / "Selisih Rp …" berikon + daftar penyebab; definisi "Berlaku sejak … (versi n)".
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import IncentiveSetupView, { alasanTidakBisaAtur, barisTarget, KETERANGAN_TARGET, KOSONG_KOMPONEN, kosongBulan, labelPeriode, pilihanPeriode,
  TEKS_SEMUA_PT, TEKS_TANPA_IZIN } from "../incentive/IncentiveSetupView";
import { AppNavProvider } from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { setAccessContext } from "../../config/roles";

const mockGet = jest.fn();
const mockPut = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), put: (...a) => mockPut(...a), post: (...a) => mockPost(...a),
    patch: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({ askConfirm: () => Promise.resolve(true), askReason: () => Promise.resolve("") }));
jest.mock("../../components/EntityScopeBanner", () => () => <div data-testid="ins-scope" />);
jest.mock("../../components/KNSelect", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const ENT = [{ id: "ent_kanda", legal_name: "CV Kanda Suka", short_name: "Kanda" }];
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function settle() { for (let i = 0; i < 6; i += 1) await act(async () => {}); }
async function mount({ entity = "ent_kanda" } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(
      <EntityScopeProvider selectedEntity={entity} entities={ENT} canSwitch>
        <AppNavProvider role="manager"><IncentiveSetupView /></AppNavProvider>
      </EntityScopeProvider>);
  });
  await settle();
  return host;
}

const TARGETS = {
  period_type: "month", period: "2026-10", previous_period: "2026-09", bounds: { start: "2026-10-01", end: "2026-10-31" },
  all_pt: false, items: [{ id: "starg_1", sales_id: "u1", sales_name: "Andi", entity_id: "ent_kanda", target_sales_amount: 80000000,
    target_collection_amount: 40000000, target_new_customers: 2, notes: "" }],
  roster: [{ id: "u1", name: "Andi" }, { id: "u2", name: "Budi" }],
};
const DEF = { all_pt: false, version: 3, effective_from: "2026-11-14", items: [
  { field: "dasar_omzet", label: "Omzet insentif dihitung saat", value: "terkirim", value_label: "Saat barang dikirim" },
  { field: "isi_pencairan", label: "Yang dihitung sebagai pencairan", value: "uang_masuk", value_label: "Hanya uang yang masuk" }] };
const REC = {
  all_pt: false,
  omzet: { fakta: 30000000, buku: 29000000, selisih: 1000000, ok: false, pesanan: 1, jumlah_penyebab: 1,
    penyebab: [{ so_number: "SO/KMT1/O1", sebab: "Jurnal pendapatan belum terbit.", selisih: 1000000 }] },
  pencairan: { dialokasikan: 30000000, belum_dialokasikan: 2000000, kwitansi: 32000000, kas: 32000000, selisih: 0, selisih_kas: 0,
    ok: true, penyebab: [], jumlah_penyebab: 0 },
};
function api({ targets = TARGETS, components = [], def = DEF, rec = REC } = {}) {
  mockGet.mockImplementation((url) => {
    if (url === "/api/incentive/targets") return Promise.resolve({ data: targets });
    if (url === "/api/incentive/components") return Promise.resolve({ data: { items: components } });
    if (url === "/api/incentive/definitions/current") return Promise.resolve({ data: def });
    if (url === "/api/incentive/reconciliation") return Promise.resolve({ data: rec });
    return Promise.resolve({ data: {} });
  });
}
afterEach(() => { mockGet.mockReset(); mockPut.mockReset(); mockPost.mockReset(); document.body.innerHTML = ""; setAccessContext(null); });

describe("fungsi murni", () => {
  test("alasan tombol mati: Semua PT lebih dulu, lalu izin", () => {
    expect(alasanTidakBisaAtur({ canWrite: false, canConfigure: true })).toBe("Pilih satu PT untuk mengatur target.");
    expect(alasanTidakBisaAtur({ canWrite: true, canConfigure: false })).toBe(TEKS_TANPA_IZIN);
    expect(alasanTidakBisaAtur({ canWrite: true, canConfigure: true })).toBe("");
  });
  test("label & pilihan periode", () => {
    expect(labelPeriode("quarter", "2026-Q4")).toBe("Triwulan IV 2026");
    expect(labelPeriode("year", "2027")).toBe("Tahun buku 2027");
    expect(pilihanPeriode("quarter", "2026-Q4").map((o) => o.value)).toContain("2026-Q1");
    expect(pilihanPeriode("year", "2026").map((o) => o.value)).toEqual(["2027", "2026", "2025", "2024"]);
  });
  test("bulan kosong = satu kalimat, bukan deretan Rp 0", () => {
    expect(kosongBulan({ omzet: { pesanan: 0, fakta: 0, buku: 0 }, pencairan: { dialokasikan: 0, belum_dialokasikan: 0, kwitansi: 0, kas: 0 } })).toBe(true);
    expect(kosongBulan(REC)).toBe(false);
  });
  test("baris target = daftar sales ∪ target tersimpan", () => {
    const rows = barisTarget(TARGETS.roster, TARGETS.items);
    expect(rows.map((r) => [r.sales_id, r.target_sales_amount, r.saved])).toEqual([["u1", "80000000", true], ["u2", "", false]]);
  });
});

describe("layar Target & Aturan", () => {
  test("tiga bagian + keterangan; komponen kosong; definisi berversi; pencocokan berikon", async () => {
    setAccessContext({ role: "manager", permissions: { incentive: ["view", "configure"] } });
    api();
    const host = await mount();
    expect(q(host, "ins-target-note").textContent).toBe(KETERANGAN_TARGET);
    expect(q(host, "ins-comp-empty").textContent).toBe(KOSONG_KOMPONEN);
    expect(q(host, "ins-def-version").textContent).toContain("(versi 3)");
    expect(q(host, "ins-def-dasar_omzet").textContent).toBe("Saat barang dikirim");
    expect(q(host, "ins-def-open-config")).not.toBeNull();
    const st = q(host, "ins-rec-omzet-status");
    expect(st.textContent).toMatch(/^Selisih Rp\s?1\.000\.000$/);
    expect(st.querySelector("svg")).not.toBeNull();
    expect(q(host, "ins-rec-pencairan-status").textContent).toBe("Cocok");
    expect(q(host, "ins-rec-omzet-sebab").textContent).toContain("Jurnal pendapatan belum terbit.");
    expect(q(host, "ins-target-table").querySelectorAll("tbody tr")).toHaveLength(2);
    expect(q(host, "ins-target-sales-u1").value).toBe("80.000.000");
    // Simpan mati sampai ada baris yang diubah; mengirim PUT hanya untuk baris itu
    expect(q(host, "ins-target-save").disabled).toBe(true);
    expect(q(host, "ins-target-dirty").textContent).toContain("Belum ada perubahan");
    const inp = q(host, "ins-target-sales-u2");
    await act(async () => {
      const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
      set.call(inp, "50.000.000");
      inp.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await settle();
    expect(q(host, "ins-target-save").disabled).toBe(false);
    mockPut.mockResolvedValue({ data: {} });
    await act(async () => { q(host, "ins-target-save").dispatchEvent(new MouseEvent("click", { bubbles: true })); });
    await settle();
    expect(mockPut).toHaveBeenCalledTimes(1);
    expect(mockPut.mock.calls[0][1]).toMatchObject({ sales_id: "u2", period_type: "month", period: "2026-10", target_sales_amount: 50000000 });
  });

  test("Semua PT: tombol mati dengan alasan tertulis; pencocokan meminta satu PT", async () => {
    setAccessContext({ role: "manager", permissions: { incentive: ["view", "configure"] } });
    api({ targets: { ...TARGETS, all_pt: true, roster: [] }, rec: { all_pt: true }, def: { all_pt: true, items: [] } });
    const host = await mount({ entity: "all" });
    expect(q(host, "ins-target-save").disabled).toBe(true);
    expect(q(host, "ins-target-why").textContent).toBe(TEKS_SEMUA_PT);
    expect(q(host, "ins-comp-add").disabled).toBe(true);
    expect(q(host, "ins-rec-all")).not.toBeNull();
    expect(q(host, "ins-def-all")).not.toBeNull();
  });

  test("tanpa izin Konfigurasi: tombol mati + alasan; tautan Pusat Pengaturan tidak tampil; komponen berstatus berikon", async () => {
    setAccessContext({ role: "finance", permissions: { incentive: ["view"] } });
    api({ components: [{ id: "c1", code: "IB", name: "Insentif Bulanan", basis_label: "Bulanan", columns_label: ["Omzet"], is_active: false }] });
    const host = await mount();
    expect(q(host, "ins-target-why").textContent).toBe(TEKS_TANPA_IZIN);
    expect(q(host, "ins-comp-edit-IB").disabled).toBe(true);
    expect(q(host, "ins-def-open-config")).toBeNull();
    const pill = q(host, "ins-comp-active-IB");
    expect(pill.textContent).toBe("Nonaktif");
    expect(pill.querySelector("svg")).not.toBeNull();
  });
});
