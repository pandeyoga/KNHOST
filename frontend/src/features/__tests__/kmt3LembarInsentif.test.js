// KM-T3 — SDM › Kinerja & Insentif › Lembar Insentif (`incentive-sheets`), sisi layar tanpa peramban:
//  · daftar: status = ikon + teks + warna (kelas `status-*` yang ada), kosong satu kalimat, "Buat lembar" mati saat
//    "Semua PT" dengan alasan tertulis "Pilih satu PT dulu.";
//  · rincian: konfirmasi Sahkan menyebut "{n} baris · total Rp …" dan nama PT (U17 pengganti uji jalan); lembar
//    disahkan → isian nominal terkunci (teks); draf + izin siapkan → isian nominal; diajukan + izin sahkan → isian koreksi;
//    "Berubah sejak dipotret: …" tampil di rincian baris;
//  · Capaian: tombol "Buat lembar insentif dari tampilan ini" mati dengan alasan sampai sales dicentang.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import IncentiveSheetsView, { alasanBuat, TEKS_KOSONG } from "../incentive/IncentiveSheetsView";
import IncentiveSheetDetail, { alasanAjukan, bacaNominal, tampilNominal, teksBerubah, teksKonfirmasiSahkan }
  from "../incentive/IncentiveSheetDetail";
import CapaianView, { alasanBuatLembar } from "../incentive/CapaianView";
import { AppNavProvider } from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { setAccessContext } from "../../config/roles";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockConfirm = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), put: () => Promise.resolve({ data: {} }),
    patch: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: (...a) => mockConfirm(...a),
  askReason: () => Promise.resolve("alasan uji"),
  default: {},
}));
jest.mock("../../components/EntityScopeBanner", () => () => <div data-testid="scope" />);
jest.mock("../../components/KNSelect", () => () => null);
jest.mock("../../components/KNDatePicker", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const ENT = [{ id: "ent_kanda", legal_name: "CV Kanda Suka", short_name: "Kanda" }];
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const txt = (el) => (el?.textContent || "").replace(/ /g, " ");
async function settle() { for (let i = 0; i < 8; i += 1) await act(async () => {}); }
const klik = async (el) => { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await settle(); };
async function mount(node, { entity = "ent_kanda" } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(
      <EntityScopeProvider selectedEntity={entity} entities={ENT} canSwitch>
        <AppNavProvider role="manager" onOpenDocument={() => {}} onNavigateTo={() => {}}>{node}</AppNavProvider>
      </EntityScopeProvider>);
  });
  await settle();
  return host;
}
const izin = (acts) => setAccessContext({ role: "manager", permissions: { incentive: acts }, view_resources: {},
  hidden_views: [], view_actions: {} });

const SNAP = { taken_at: "2026-11-14T03:05:00+00:00", definition_version: 2, omzet: 1000000000, retur: 0,
  omzet_bersih: 1000000000, target_sales: 800000000, pct_omzet: 125, uang_masuk: 700000000, target_collection: 750000000,
  pct_pencairan: 93.3, realisasi_harga_pct: 86.2, porsi_bawah_acuan_pct: 100, catatan_data: [] };
const LEMBAR = (over) => ({
  id: "isheet_1", number: "KANDA/LIN-00001", entity_id: "ent_kanda", pay_period: "2026-11", title: "", status: "draft",
  prepared_by: { id: "u_mgr", name: "Mega" }, history: [],
  lines: [
    { id: "l_andi", sales_id: "u_andi", sales_name: "Andi", component_id: "c_bln", component_name: "Insentif Bulanan",
      basis_period_type: "month", basis_period: "2026-10", basis_label: "Okt 2026", amount: 2000000, note: "", snapshot: SNAP },
    { id: "l_budi", sales_id: "u_budi", sales_name: "Budi", component_id: "c_bln", component_name: "Insentif Bulanan",
      basis_period_type: "month", basis_period: "2026-10", basis_label: "Okt 2026", amount: 3500000, note: "",
      snapshot: { ...SNAP, omzet: 500000000, omzet_bersih: 500000000 } }],
  totals: { lines: 2, amount: 5500000 }, drift: [], ...over,
});

beforeEach(() => { mockGet.mockReset(); mockPost.mockReset(); mockConfirm.mockReset(); });

test("teks bantu: konfirmasi Sahkan, selisih potret, isian nominal, alasan tombol", () => {
  const t = teksKonfirmasiSahkan(LEMBAR(), "CV Kanda Suka", 5500000).replace(/ /g, " ");
  expect(t).toBe("Sahkan lembar KANDA/LIN-00001? 2 baris · total Rp 5.500.000 · CV Kanda Suka. Setelah disahkan, lembar "
    + "tidak bisa diubah; koreksi dibuat sebagai penyesuaian di lembar berikutnya.");
  expect(teksBerubah({ field: "omzet_bersih", label: "Omzet bersih", diff: -50000000, current: 950000000 }).replace(/ /g, " "))
    .toBe("Berubah sejak dipotret: Omzet bersih −Rp 50.000.000");
  expect(teksBerubah({ field: "realisasi_harga_pct", label: "Realisasi harga", diff: 1.5, current: 87.7 }))
    .toBe("Berubah sejak dipotret: Realisasi harga +1,5 poin");
  expect(tampilNominal("2000000")).toBe("2.000.000");
  expect(bacaNominal("-500.000", true)).toBe("-500000");
  expect(bacaNominal("-500.000", false)).toBe("500000");   // negatif hanya baris penyesuaian
  expect(alasanBuat({ canWrite: false, canPrepare: true })).toBe("Pilih satu PT dulu.");
  expect(alasanBuat({ canWrite: true, canPrepare: false })).toMatch(/Siapkan lembar insentif/);
  expect(alasanAjukan(LEMBAR({ lines: [{ ...LEMBAR().lines[0], amount: null }] }), false))
    .toBe("Isi nominal semua baris sebelum mengajukan.");
  expect(alasanBuatLembar({ canPrepare: true, perSales: true, nPilih: 0 })).toBe("Centang sales yang akan dibuatkan lembar.");
  expect(alasanBuatLembar({ canPrepare: true, perSales: true, nPilih: 2 })).toBe("");
});

test("daftar: status berikon + teks, kosong satu kalimat, Buat lembar mati saat Semua PT dengan alasan", async () => {
  izin(["view", "prepare", "approve"]);
  mockGet.mockResolvedValue({ data: { total: 2, items: [
    { ...LEMBAR({ status: "approved", approved_by: { name: "Mega" } }), lines: [] },
    { ...LEMBAR({ id: "isheet_2", number: "KANDA/LIN-00002", status: "submitted" }), lines: [] }] } });
  const host = await mount(<IncentiveSheetsView />);
  const st = q(host, "isheets-row-status-isheet_1");
  expect(txt(st)).toBe("Disahkan");
  expect(st.className).toContain("status-done");
  expect(st.querySelector("svg")).not.toBeNull();
  expect(q(host, "isheets-row-status-isheet_2").className).toContain("status-pending");
  expect(txt(q(host, "isheets-count"))).toBe("2 dari 2 lembar");
  expect(q(host, "isheets-create").disabled).toBe(false);

  mockGet.mockResolvedValue({ data: { total: 0, items: [] } });
  const kosong = await mount(<IncentiveSheetsView />);
  expect(txt(q(kosong, "isheets-empty"))).toBe(TEKS_KOSONG);

  const semua = await mount(<IncentiveSheetsView />, { entity: "all" });
  expect(q(semua, "isheets-create").disabled).toBe(true);
  expect(txt(q(semua, "isheets-create-why"))).toBe("Pilih satu PT dulu.");
});

test("rincian disahkan: nominal terkunci, lencana Disahkan, tanpa tombol tulis", async () => {
  izin(["view", "prepare", "approve"]);
  mockGet.mockResolvedValue({ data: LEMBAR({ status: "approved" }) });
  const host = await mount(<IncentiveSheetDetail sheetId="isheet_1" onClose={() => {}} />);
  expect(txt(q(host, "isheet-status"))).toBe("Disahkan");
  expect(q(host, "isheet-amount-l_andi")).toBeNull();
  expect(txt(q(host, "isheet-amount-text-l_andi"))).toMatch(/Rp\s2\.000\.000/);
  expect(q(host, "isheet-submit")).toBeNull();
  expect(q(host, "isheet-approve")).toBeNull();
  expect(txt(q(host, "isheet-why"))).toMatch(/koreksi dibuat sebagai baris penyesuaian/);
});

test("rincian draf: isian nominal untuk penyiap; tanpa izin siapkan → teks + alasan", async () => {
  izin(["view", "prepare"]);
  mockGet.mockResolvedValue({ data: LEMBAR() });
  const host = await mount(<IncentiveSheetDetail sheetId="isheet_1" onClose={() => {}} />);
  expect(q(host, "isheet-amount-l_andi").value).toBe("2.000.000");
  expect(q(host, "isheet-submit").disabled).toBe(false);
  izin(["view"]);
  const lihat = await mount(<IncentiveSheetDetail sheetId="isheet_1" onClose={() => {}} />);
  expect(q(lihat, "isheet-amount-l_andi")).toBeNull();
  expect(q(lihat, "isheet-submit").disabled).toBe(true);
  expect(txt(q(lihat, "isheet-why"))).toMatch(/Siapkan lembar insentif/);
});

test("U17 pengganti: Sahkan meminta konfirmasi '2 baris · total Rp …' + nama PT, lalu lencana Disahkan", async () => {
  izin(["view", "approve"]);
  mockGet.mockResolvedValue({ data: LEMBAR({ status: "submitted", submitted_by: { id: "u_sa", name: "Sari" } }) });
  mockConfirm.mockResolvedValue(true);
  mockPost.mockResolvedValue({ data: LEMBAR({ status: "approved", approved_by: { id: "u_mgr", name: "Mega" } }) });
  const host = await mount(<IncentiveSheetDetail sheetId="isheet_1" onClose={() => {}} />);
  expect(q(host, "isheet-correct-l_budi")).not.toBeNull();   // pemutus boleh mengoreksi nominal
  await klik(q(host, "isheet-approve"));
  expect(mockConfirm).toHaveBeenCalledTimes(1);
  const msg = String(mockConfirm.mock.calls[0][0].message).replace(/ /g, " ");
  expect(msg).toContain("2 baris · total Rp 5.500.000 · CV Kanda Suka");
  expect(mockPost.mock.calls[0][0]).toBe("/api/incentive/sheets/isheet_1/approve");
  expect(mockPost.mock.calls[0][2].headers["Idempotency-Key"]).toMatch(/^isheet-act-/);
  expect(txt(q(host, "isheet-status"))).toBe("Disahkan");
  expect(q(host, "isheet-correct-l_budi")).toBeNull();
  expect(q(host, "isheet-amount-l_budi")).toBeNull();
});

test("rincian: 'Berubah sejak dipotret' tampil di rincian baris (bahan penyesuaian)", async () => {
  izin(["view"]);
  mockGet.mockResolvedValue({ data: LEMBAR({ status: "approved", drift: [
    { line_id: "l_andi", field: "omzet_bersih", label: "Omzet bersih", snapshot: 1000000000, current: 950000000, diff: -50000000 }] }) });
  const host = await mount(<IncentiveSheetDetail sheetId="isheet_1" onClose={() => {}} />);
  expect(txt(q(host, "isheet-drift-flag-l_andi"))).toBe("Berubah sejak dipotret");
  await klik(q(host, "isheet-toggle-l_andi"));
  expect(txt(q(host, "isheet-drift-l_andi-omzet_bersih"))).toMatch(/Omzet bersih −Rp\s50\.000\.000/);
  expect(txt(q(host, "isheet-taken-l_andi"))).toMatch(/definisi versi 2/);
  expect(q(host, "isheet-drift-flag-l_budi")).toBeNull();
  expect(txt(q(host, "isheet-count"))).toBe("2 dari 2 baris");   // daftar baris bisa dicari (KN_37 §6)
});

test("Capaian: tombol Buat lembar insentif mati sampai sales dicentang", async () => {
  izin(["view", "prepare"]);
  const BARIS = { target_sales: 800000000, target_collection: 750000000, omzet: 1000000000, retur: 0, omzet_bersih: 1000000000,
    pct_omzet: 125, uang_masuk: 700000000, pct_pencairan: 93.3, realisasi_harga_pct: 86.2, catatan_data: [], has_numbers: true,
    jumlah_pesanan: 1 };
  mockGet.mockResolvedValue({ data: { entity_id: "ent_kanda", group_by: "sales", margin_visible: false, facts_as_of: "",
    period: { type: "month", key: "2026-10", label: "Oktober 2026", date_from: "2026-10-01", date_to: "2026-10-31" },
    definition: null, reconciliation: { omzet_ok: true, pencairan_ok: true }, notes: [], compare: { label: "", by_key: {} },
    rows: [{ ...BARIS, key: "u_andi", sales_id: "u_andi", name: "Andi" }, { ...BARIS, key: "u_budi", sales_id: "u_budi", name: "Budi" }],
    totals: { ...BARIS } } });
  const host = await mount(<CapaianView currentUser={{ id: "u_mgr" }} />);
  expect(q(host, "cap-make-sheet").disabled).toBe(true);
  expect(txt(q(host, "cap-make-sheet-why"))).toBe("Centang sales yang akan dibuatkan lembar.");
  await klik(q(host, "cap-check-u_andi"));
  await klik(q(host, "cap-check-u_budi"));
  expect(q(host, "cap-make-sheet").disabled).toBe(false);
  expect(q(host, "cap-make-sheet-why")).toBeNull();
  izin(["view"]);
  const lihat = await mount(<CapaianView currentUser={{ id: "u_fin" }} />);
  expect(txt(q(lihat, "cap-make-sheet-why"))).toMatch(/Siapkan lembar insentif/);
});
