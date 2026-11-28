// Kas & Bank bagian 3 (Tugas 4b) — layar opname kas (C3). Rancangan
// `docs/superpowers/specs/2026-11-28-kas-bank-3-kasir-dana-tetap-opname-design.md` §5.3, §5.4, §7 (7.8 butir 2, 3, 6, 8).
//  · Tab tersembunyi Kas & Bank › Opname Kas (`cash-counts`, menyorot Rekening & Saldo; hub tetap 6 tab tampak): daftar
//    (saringan status & rekening), form Hitung (rekening tunai, jumlah fisik, rincian pecahan opsional yang menjumlah ke
//    total, catatan; saldo buku & selisih tampil SESUDAH disimpan — hitung buta), Setujui = satu pop-up perlakuan selisih
//    (selisih kas / piutang karyawan + pemilih karyawan; piutang hanya untuk kurang), Tolak beralasan; Setujui DAN Tolak
//    nonaktif untuk penghitung dengan kalimat server (`kontrol.pesan` / `kontrol.tolak_pesan`). Izin menyembunyikan aksi
//    (bukan nama peran).
//  · Gelombang perbaikan akhir: Batal opname disetujui (`POST …/batal {alasan}`, `cash.approve`, bukan penghitung; status
//    "Dibatalkan"); saringan Perlakuan (daftar piutang karyawan §7.8.6) ke parameter `perlakuan` dan unduhan.
//  · Aksi "Opname" di kartu rekening tunai Rekening & Saldo; kartu Meja Keuangan "Opname kas jatuh tempo" (baris membuka
//    form terisi rekening, di tempat); pratinjau `OPK-` + Jejak; tujuan notifikasi; preset antrean Pusat Persetujuan.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CashCountsView from "../finance/cashcount/CashCountsView";
import CashCountForm from "../finance/cashcount/CashCountForm";
import OpnameKartuAksi from "../finance/cashcount/OpnameKartuAksi";
import {
  PECAHAN_RUPIAH, PILIHAN_PERLAKUAN, PILIHAN_STATUS, aksiOpname, badanHitung, barisPecahan, opsiPerlakuan, selisihTeks,
  statusOpname, totalPecahan, validasiHitung,
} from "../finance/cashcount/cashCountShared";
import CashCountPreview from "../documents/preview/bodies/CashCountPreview";
import { canPreview, previewFor } from "../documents/preview/docPreviewRegistry";
import { notifDocTarget } from "../notifications/notifDocTarget";
import { typeLabel } from "../../components/NotificationCenter";
import { QUEUE_DOC_TYPE, queueLink } from "../approvals/inboxTabs";
import { docLinkTarget, rowLink } from "../sales_admin/workDeskApi";
import FinanceDesk, { PERLU_TINDAKAN, susunKelompok } from "../finance/FinanceDesk";
import BankAccountsView from "../finance/BankAccountsView";
import { CASH_REF_DOC, REF_LABEL } from "../purchasing/CashManagementView";
import { HUB_TABS } from "../../config/hubTabs";
import { PAGE_META } from "../../config/navMeta";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { notifySuccess } from "../../utils/feedback";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a),
    patch: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
  setActiveEntity: () => {}, setAuthToken: () => {}, setLocationScope: () => {},
}));
jest.mock("../../components/KNSelect", () => {
  const Sel = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      <option value="">-</option>
      {(p.options || []).map((o) => <option key={o.value} value={o.value} disabled={o.disabled}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: Sel, KNSelect: Sel };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange(e.target.value)} />,
  formatDateId: (v) => v,
}));
const mockAskConfirm = jest.fn();
const mockAskReason = jest.fn();
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: (...a) => mockAskConfirm(...a),
  askReason: (...a) => mockAskReason(...a),
  askText: jest.fn(async () => null),
  askChoice: jest.fn(async () => null),
  REASON_MIN_LENGTH: 5,
  default: {},
}));
const mockGo = jest.fn();
const mockPreview = jest.fn();
const mockOpenDocument = jest.fn();
jest.mock("../../context/AppNavContext", () => ({
  __esModule: true,
  useAppNav: () => ({ go: mockGo, canOpen: () => true, openDocument: mockOpenDocument, previewsEnabled: true,
    openDocPreview: mockPreview, closeDocPreview: () => {}, openSupplierCard: () => {}, cardsEnabled: false }),
}));
jest.mock("../../utils/feedback", () => ({ __esModule: true, notifySuccess: jest.fn(), notifyError: jest.fn(),
  notifyInfo: jest.fn(), notifyWarning: jest.fn() }));
const mockToast = jest.fn();
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: (...a) => mockToast(...a) }));
// Preset navigasi (Pusat Persetujuan, kartu rekening): `mockPreset` diterapkan sekali saat layar dipasang.
let mockPreset = null;
jest.mock("../../hooks/useViewPreset", () => {
  const R = jest.requireActual("react");
  const pakai = (view, apply) => {
    R.useEffect(() => { if (mockPreset && mockPreset.view === view && apply) apply(mockPreset); }, []); // eslint-disable-line
    return mockPreset && mockPreset.view === view ? mockPreset : null;
  };
  return { __esModule: true, default: pakai, useViewPreset: pakai };
});
// Bilah halaman asli tetap dirender; props-nya direkam supaya saringan unduhan (`exportSpec`) bisa diperiksa.
const mockPagerProps = [];
jest.mock("../../components/PaginationBar", () => {
  const Asli = jest.requireActual("../../components/PaginationBar").default;
  return { __esModule: true, default: (p) => { mockPagerProps.push(p); return <Asli {...p} />; } };
});
jest.mock("../../components/AskKnButton",() => ({ __esModule: true, AskKnButton: () => null, PENDING_KEY: "x" }));
jest.mock("../sales_admin/SoTrackerCard", () => () => null);
jest.mock("../finance/TaxIssueDialog", () => () => null);

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const txt = (el) => String(el?.textContent || "").replace(/\s+/g, " ").trim();
async function flush(ms = 0) {
  for (let i = 0; i < 5; i += 1) {
    await act(async () => { await new Promise((r) => setTimeout(r, ms)); });
  }
}
const ENTS = [{ id: "ent_ksc", short_name: "KSC", legal_name: "PT Kain Suka Cita" }];
async function mount(el, selectedEntity = "ent_ksc") {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(<EntityScopeProvider selectedEntity={selectedEntity} entities={ENTS} canSwitch>{el}</EntityScopeProvider>);
  });
  await flush();
  return host;
}
async function click(el) { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await flush(); }
async function choose(el, value) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(el, value);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}
async function type(el, value) {
  const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await flush();
}
async function submit(host, id) {
  const btn = q(host, id);
  await act(async () => { btn.closest("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
  await flush();
}
const posts = (akhiran) => mockPost.mock.calls.filter(([u]) => String(u).endsWith(akhiran));
const gets = (akhiran) => mockGet.mock.calls.filter(([u]) => String(u).endsWith(akhiran));
const kunciIdem = (call) => call?.[2]?.headers?.["Idempotency-Key"];

let galatKonsol;
beforeEach(() => { galatKonsol = jest.spyOn(console, "error").mockImplementation(() => {}); });
afterEach(() => {
  const panggilan = galatKonsol.mock.calls.map((c) => String(c[0]).slice(0, 200));
  galatKonsol.mockRestore();
  [mockGet, mockPost, mockAskConfirm, mockAskReason, mockGo, mockPreview, mockOpenDocument, mockToast].forEach((m) => m.mockReset());
  notifySuccess.mockReset();
  mockPagerProps.length = 0;
  mockPreset = null;
  document.body.innerHTML = "";
  sessionStorage.clear();
  expect(panggilan).toEqual([]);
});

// ── Data ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
// Kalimat server (`cash_count_service.PESAN_ORANG_KEDUA`) — dikirim di `kontrol.pesan`, ditampilkan apa adanya.
const PESAN_ORANG_KEDUA = "Selisih opname kas ini harus diputuskan orang lain: Anda yang menghitungnya. Minta rekan yang "
  + "berizin menyetujui kas memutuskannya. Admin dapat mengubah aturan ini di Pengaturan › Persetujuan › Kontrol dua orang.";
// `cash_count_service.PESAN_TOLAK_SENDIRI` — dikirim di `kontrol.tolak_pesan` (perbaikan putaran 1 Tugas 3).
const PESAN_TOLAK_SENDIRI = "Opname kas ini Anda hitung sendiri, jadi tidak bisa Anda tolak sendiri. Minta rekan yang "
  + "berizin menyetujui kas menolaknya dengan alasan, lalu hitung ulang. Admin dapat mengubah aturan ini di Pengaturan › "
  + "Persetujuan › Kontrol dua orang.";
// Kalimat server Batal bagi penghitung (`kontrol.batal_pesan`, gelombang perbaikan akhir) — ditampilkan apa adanya.
const PESAN_BATAL_SENDIRI = "Opname kas ini Anda hitung sendiri, jadi tidak bisa Anda batalkan sendiri. Minta rekan yang "
  + "berizin menyetujui kas membatalkannya.";
const AKU = { id: "usr_hitung", name: "Sari Kasir" };
const KONTROL_SENDIRI = { dua_orang: true, sendiri: true, admin_sendiri: false, ditolak: true, pesan: PESAN_ORANG_KEDUA,
  tolak_pesan: PESAN_TOLAK_SENDIRI };
const OPK = (lain = {}) => ({
  id: "opk_1", number: "KSC/OPK-00001", entity_id: "ent_ksc", status: "menunggu_persetujuan", status_label: "Menunggu persetujuan",
  account_id: "kas_toko", account_name: "Kas Kasir Toko", cash_type: "kas_kasir", cash_type_label: "Kas kasir",
  tanggal: "2026-11-28", dihitung_pada: "2026-11-28T03:00:00+00:00", saldo_buku: 1000000, jumlah_fisik: 970000, pecahan: [],
  selisih: -30000, selisih_nominal: 30000, arah_selisih: "kurang", boleh_piutang: true, catatan: "Hitung tutup toko",
  penghitung: AKU, perlakuan: "", perlakuan_label: "", karyawan_id: "", karyawan_nama: "", karyawan_kode: "",
  cash_id: "", cash_number: "", terbit_error: "", alasan_tolak: "", dalam_proses: false,
  kontrol: { dua_orang: true, sendiri: false, admin_sendiri: false, ditolak: false, pesan: "", tolak_pesan: "" },
  jejak: [{ aksi: "hitung", oleh: AKU.name, oleh_id: AKU.id, pada: "2026-11-28T03:00:00+00:00",
    catatan: "selisih -Rp 30.000 menunggu persetujuan orang kedua" }],
  kas: null,
  ...lain,
});
const LEBIH = OPK({ id: "opk_2", number: "KSC/OPK-00002", account_id: "kas_kecil", account_name: "Kas Kecil Gudang",
  cash_type: "kas_kecil", cash_type_label: "Kas Kecil", saldo_buku: 500000, jumlah_fisik: 550000, selisih: 50000,
  selisih_nominal: 50000, arah_selisih: "lebih", boleh_piutang: false });
const SELESAI = OPK({ id: "opk_3", number: "KSC/OPK-00003", status: "selesai", status_label: "Selesai", jumlah_fisik: 1000000,
  selisih: 0, selisih_nominal: 0, arah_selisih: "", boleh_piutang: false, kontrol: undefined });
// Opname disetujui (kas penyesuaian sudah terbit) — satu-satunya keadaan yang bisa dibatalkan. Tanpa `kontrol` (server
// sebelum perbaikan Batal tidak menilai keadaan ini) layar memakai id penghitung sebagai cadangan.
const DISETUJUI = OPK({ id: "opk_4", number: "KSC/OPK-00004", status: "disetujui", status_label: "Disetujui",
  perlakuan: "piutang_karyawan", perlakuan_label: "Piutang karyawan", karyawan_id: "emp_1", karyawan_nama: "Budi Santoso",
  karyawan_kode: "KAR-001", cash_id: "cash_1", cash_number: "KSC/KK-00009", kontrol: undefined });
const BATAL = OPK({ id: "opk_5", number: "KSC/OPK-00005", status: "batal", status_label: "Dibatalkan", kontrol: undefined,
  perlakuan: "selisih_kas", perlakuan_label: "Selisih kas", cash_id: "cash_2", cash_number: "KSC/KK-00010" });
const REKENING = [
  { id: "kas_toko", name: "Kas Kasir Toko", entity_id: "ent_ksc", account_type: "cash", cash_type: "kas_kasir", is_active: true,
    balance: 1000000, inflow: 0, outflow: 0, txn_count: 3 },
  { id: "kas_kecil", name: "Kas Kecil Gudang", entity_id: "ent_ksc", account_type: "cash", cash_type: "kas_kecil", is_active: true,
    balance: 500000, inflow: 0, outflow: 0, txn_count: 2 },
  { id: "bank_bca", name: "BCA Operasional", entity_id: "ent_ksc", account_type: "bank", bank_name: "BCA", account_number: "123",
    is_active: true, balance: 5000000, inflow: 0, outflow: 0, txn_count: 1 },
  { id: "kas_lama", name: "Kas Lama", entity_id: "ent_ksc", account_type: "cash", cash_type: "kas_kecil", is_active: false,
    balance: 0, inflow: 0, outflow: 0, txn_count: 0 },
];
const KARYAWAN = [{ id: "emp_1", code: "KAR-001", name: "Budi Santoso" }, { id: "emp_2", code: "KAR-002", name: "Rina" }];
const izinLihat = { cash: ["view"] };
const izinHitung = { cash: ["view", "create"] };
const izinPenuh = { cash: ["view", "create", "approve"] };

function pasang({ items = [OPK(), LEBIH, SELESAI], rekening = REKENING } = {}) {
  mockGet.mockImplementation((url, cfg) => {
    if (url.endsWith("/cash-counts")) {
      return Promise.resolve({ data: { items, total: items.length, page: 1, page_size: 25, has_more: false } });
    }
    if (url.endsWith("/cash-counts/karyawan")) return Promise.resolve({ data: KARYAWAN });
    if (url.endsWith("/bank-accounts")) return Promise.resolve({ data: rekening });
    if (url.endsWith("/bank-account-changes")) return Promise.resolve({ data: { items: [], total: 0 } });
    return Promise.resolve({ data: null });
  });
}
const daftar = (perms, props = {}, user = { id: "usr_lain" }) => mount(<CashCountsView
  currentUser={{ ...user, permissions: perms }} selectedEntity="ent_ksc" {...props} />);

// ── Tab, tautan, kosakata ────────────────────────────────────────────────────────────────────────────────────────────
describe("Opname Kas — tab tersembunyi & tautan masuk", () => {
  test("tab `cash-counts` tersembunyi, menyorot Rekening & Saldo; hub Kas & Bank tetap 6 tab tampak", () => {
    const tabs = HUB_TABS["cash-bank"];
    expect(tabs.filter((t) => !t.hidden)).toHaveLength(6);
    expect(tabs.find((t) => t.view === "cash-counts")).toMatchObject({ label: "Opname Kas", hidden: true, aliasOf: "bank-accounts" });
    expect(PAGE_META["cash-counts"].title).toMatch(/^Opname Kas/);
  });

  test("Pusat Persetujuan: antrean cash_count membuka Opname Kas dengan saringan server; nomornya = pratinjau", () => {
    const antre = { key: "cash_count", view: "cash-counts", preset: { status: "menunggu_persetujuan" } };
    expect(queueLink(antre, () => true)).toEqual({ view: "cash-counts", preset: { status: "menunggu_persetujuan" } });
    expect(QUEUE_DOC_TYPE.cash_count).toBe("cash_count");
  });

  test("notifikasi opname menunggu / diputus membuka opnamenya (doc server, atau id dari ref)", () => {
    const tujuan = { view: "cash-counts", nav_id: "cash-bank", focus_type: "cash_count", focus_id: "opk_1" };
    expect(notifDocTarget({ type: "opname_kas_menunggu", ref: "opk_1#usr_a",
      doc: { ref_type: "cash_count", ref_id: "opk_1", number: "KSC/OPK-00001" } }).link)
      .toMatchObject({ ...tujuan, number: "KSC/OPK-00001" });
    expect(notifDocTarget({ type: "opname_kas_menunggu", ref: "opk_1#usr_a" }).link).toMatchObject(tujuan);
    expect(notifDocTarget({ type: "opname_kas_diputus", ref: "opk_1:ditolak#usr_b" }).link).toMatchObject(tujuan);
    expect(docLinkTarget({ ref_type: "cash_count", ref_id: "opk_9", number: "X" })).toMatchObject({ view: "cash-counts" });
    expect(typeLabel("opname_kas_menunggu")).toBe("Selisih opname kas menunggu");
    expect(typeLabel("opname_kas_diputus")).toBe("Opname kas diputus");
  });

  test("Meja Keuangan: 'Buka layar penuh' baris opname jatuh tempo → Opname Kas berfokus rekening", () => {
    const row = { ref_type: "bank_account", ref_id: "kas_toko", account_id: "kas_toko", number: "Kas Kasir Toko" };
    expect(rowLink(row, "opname_kas_jatuh_tempo", "finance"))
      .toMatchObject({ view: "cash-counts", nav_id: "cash-bank", focus_type: "bank_account", focus_id: "kas_toko" });
  });

  test("Transaksi Kas: kas penyesuaian opname bersumber dokumen opname (berpratinjau)", () => {
    expect(REF_LABEL.cash_count).toBe("opname kas");
    expect(CASH_REF_DOC.cash_count).toBe("cash_count");
  });
});

describe("Opname Kas — aturan layar (cashCountShared)", () => {
  test("aksi: penghitung → Setujui & Tolak nonaktif dengan kalimat server; rekan → keduanya; tanpa cash.approve → tanpa aksi", () => {
    const a = aksiOpname(OPK({ kontrol: KONTROL_SENDIRI }), izinPenuh, AKU);
    expect(a.setujui).toEqual({ label: "Setujui", alasan: PESAN_ORANG_KEDUA });
    expect(a.tolak).toEqual({ label: "Tolak", alasan: PESAN_TOLAK_SENDIRI });
    expect(a.batal).toBeNull();                                          // menunggu: diputus, bukan dibatalkan
    const rekan = aksiOpname(OPK(), izinPenuh, { id: "usr_lain" });
    expect(rekan.setujui).toEqual({ label: "Setujui", alasan: "" });
    expect(rekan.tolak).toEqual({ label: "Tolak", alasan: "" });
    expect(aksiOpname(OPK(), izinHitung)).toEqual({ setujui: null, tolak: null, batal: null });
    expect(aksiOpname(SELESAI, izinPenuh)).toEqual({ setujui: null, tolak: null, batal: null });
    expect(aksiOpname(OPK({ terbit_error: "Periode tertutup" }), izinPenuh).setujui.label).toBe("Setujui lagi");
    const sibuk = aksiOpname(OPK({ dalam_proses: true }), izinPenuh);
    expect(sibuk.setujui.alasan).toMatch(/^Sedang diproses/);
    expect(sibuk.tolak.alasan).toMatch(/^Sedang diproses/);
  });

  test("aksi Batal: hanya opname disetujui + cash.approve; penghitung → nonaktif berkalimat (server, atau id penghitung)", () => {
    expect(aksiOpname(DISETUJUI, izinPenuh, { id: "usr_lain" })).toEqual({ setujui: null, tolak: null,
      batal: { label: "Batal", alasan: "" } });
    expect(aksiOpname(DISETUJUI, izinHitung, { id: "usr_lain" }).batal).toBeNull();
    expect(aksiOpname(BATAL, izinPenuh, { id: "usr_lain" }).batal).toBeNull();
    // kalimat server bila dikirim — juga bila server mengizinkan penghitung (server penentu)
    expect(aksiOpname({ ...DISETUJUI, kontrol: { batal_pesan: PESAN_BATAL_SENDIRI } }, izinPenuh, { id: "usr_lain" }).batal)
      .toEqual({ label: "Batal", alasan: PESAN_BATAL_SENDIRI });
    expect(aksiOpname({ ...DISETUJUI, kontrol: { batal_pesan: "" } }, izinPenuh, AKU).batal.alasan).toBe("");
    // tanpa penilaian server: penghitung (id sama) tidak membatalkan putusan atas hitungannya sendiri
    expect(aksiOpname(DISETUJUI, izinPenuh, AKU).batal.alasan).toMatch(/Anda hitung sendiri, jadi tidak bisa Anda batalkan/);
    expect(aksiOpname({ ...DISETUJUI, dalam_proses: true }, izinPenuh, { id: "usr_lain" }).batal.alasan)
      .toMatch(/^Sedang diproses/);
    expect(statusOpname("batal")).toMatchObject({ label: "Dibatalkan" });
    expect(PILIHAN_STATUS.map((o) => o.value)).toContain("batal");
    expect(PILIHAN_PERLAKUAN).toEqual([{ value: "", label: "Semua perlakuan" },
      { value: "selisih_kas", label: "Selisih kas" }, { value: "piutang_karyawan", label: "Piutang karyawan" }]);
  });

  test("perlakuan: kurang → selisih kas & piutang karyawan; lebih → selisih kas saja", () => {
    expect(opsiPerlakuan(OPK()).map((o) => o.value)).toEqual(["selisih_kas", "piutang_karyawan"]);
    expect(opsiPerlakuan(LEBIH).map((o) => o.value)).toEqual(["selisih_kas"]);
    const spasi = (t) => t.replace(/\s/g, " ");   // formatCurrency memakai spasi tak-putus sesudah "Rp"
    expect(spasi(selisihTeks(OPK()))).toBe("Kurang Rp 30.000");
    expect(spasi(selisihTeks(LEBIH))).toBe("Lebih Rp 50.000");
    expect(selisihTeks(SELESAI)).toBe("Tanpa selisih");
  });

  test("pecahan: total dari lembar, baris terkirim hanya yang berlembar; badan permintaan", () => {
    expect(PECAHAN_RUPIAH.slice(0, 3)).toEqual([100000, 50000, 20000]);
    const lembar = { 100000: "9", 50000: "1", 20000: "1", 500: "0" };
    expect(totalPecahan(lembar)).toBe(970000);
    expect(barisPecahan(lembar)).toEqual([{ nilai: 100000, lembar: 9 }, { nilai: 50000, lembar: 1 }, { nilai: 20000, lembar: 1 }]);
    expect(badanHitung({ account_id: "kas_toko", jumlah_fisik: "970000", catatan: " tutup " }))
      .toEqual({ account_id: "kas_toko", jumlah_fisik: 970000, pecahan: [], catatan: "tutup" });
    expect(badanHitung({ account_id: "kas_toko", pakaiPecahan: true, lembar, catatan: "" }))
      .toEqual({ account_id: "kas_toko", jumlah_fisik: 970000, pecahan: barisPecahan(lembar), catatan: "" });
    expect(validasiHitung({ account_id: "", jumlah_fisik: "1" })).toBe("Pilih rekening tunai yang dihitung.");
    expect(validasiHitung({ account_id: "kas_toko", jumlah_fisik: "" }))
      .toBe("Isi jumlah uang fisik yang dihitung (atau rincian pecahannya).");
    expect(validasiHitung({ account_id: "kas_toko", jumlah_fisik: "0" })).toBe("");   // laci kosong = hitungan sah
    expect(validasiHitung({ account_id: "kas_toko", pakaiPecahan: true, lembar: {} }))
      .toBe("Isi jumlah uang fisik yang dihitung (atau rincian pecahannya).");
  });
});

// ── Daftar ───────────────────────────────────────────────────────────────────────────────────────────────────────────
describe("Opname Kas — daftar", () => {
  test("baris: nomor = pratinjau, rekening + jenis, saldo buku, fisik, selisih bertanda, status; saringan dropdown", async () => {
    pasang();
    const host = await daftar(izinPenuh);
    expect(q(host, "opk-row-opk_1")).not.toBeNull();
    expect(txt(q(host, "opk-row-opk_1"))).toContain("Kas Kasir Toko");
    expect(txt(q(host, "opk-row-opk_1"))).toContain("Kas kasir");
    expect(txt(q(host, "opk-diff-opk_1"))).toBe("Kurang Rp 30.000");
    expect(txt(q(host, "opk-diff-opk_2"))).toBe("Lebih Rp 50.000");
    expect(txt(q(host, "opk-status-opk_3"))).toBe("Selesai");
    await click(q(host, "opk-open-opk_1"));
    expect(mockPreview).toHaveBeenCalledWith(expect.objectContaining({ docType: "cash_count", docId: "opk_1" }));
    // Saringan rekening = rekening tunai PT (bank tidak); saringan status = dropdown.
    const pilihan = [...q(host, "opk-account").querySelectorAll("option")].map((o) => o.value);
    expect(pilihan).toEqual(expect.arrayContaining(["kas_toko", "kas_kecil"]));
    expect(pilihan).not.toContain("bank_bca");
    await choose(q(host, "opk-status"), "menunggu_persetujuan");
    await choose(q(host, "opk-account"), "kas_toko");
    const akhir = gets("/cash-counts").at(-1)[1].params;
    expect(akhir).toMatchObject({ entity_id: "ent_ksc", status: "menunggu_persetujuan", account_id: "kas_toko" });
  });

  test("izin: lihat saja → tanpa Hitung dan tanpa aksi baris; cash.create → Hitung; cash.approve → Setujui/Tolak", async () => {
    pasang();
    let host = await daftar(izinLihat);
    expect(q(host, "opk-create")).toBeNull();
    expect(q(host, "opk-approve-opk_1")).toBeNull();
    expect(q(host, "opk-reject-opk_1")).toBeNull();
    document.body.innerHTML = "";
    host = await daftar(izinHitung);
    expect(q(host, "opk-create")).not.toBeNull();
    expect(q(host, "opk-approve-opk_1")).toBeNull();
    document.body.innerHTML = "";
    host = await daftar(izinPenuh);
    expect(q(host, "opk-approve-opk_1")).not.toBeNull();
    expect(q(host, "opk-reject-opk_1")).not.toBeNull();
    expect(q(host, "opk-approve-opk_3")).toBeNull();   // selesai: tidak ada yang diputus
  });

  test("penghitung: Setujui & Tolak nonaktif dengan kalimat server (tanpa pop-up alasan, tanpa kiriman)", async () => {
    pasang({ items: [OPK({ kontrol: KONTROL_SENDIRI })] });
    const host = await daftar(izinPenuh, {}, AKU);
    expect(q(host, "opk-approve-opk_1").disabled).toBe(true);
    expect(q(host, "opk-reject-opk_1").disabled).toBe(true);
    const catatan = txt(q(host, "opk-action-note-opk_1"));
    expect(catatan).toContain(PESAN_ORANG_KEDUA);
    expect(catatan).toContain(PESAN_TOLAK_SENDIRI);
    await click(q(host, "opk-reject-opk_1"));
    expect(mockAskReason).not.toHaveBeenCalled();
    expect(mockPost).not.toHaveBeenCalled();
  });

  test("rekan: Tolak beralasan → POST reject berkunci idempotensi", async () => {
    pasang({ items: [OPK()] });
    mockAskReason.mockResolvedValue("hitung ulang besok pagi");
    mockPost.mockResolvedValue({ data: OPK({ status: "ditolak", status_label: "Ditolak", alasan_tolak: "hitung ulang besok pagi" }) });
    const host = await daftar(izinPenuh);
    expect(q(host, "opk-reject-opk_1").disabled).toBe(false);
    expect(q(host, "opk-action-note-opk_1")).toBeNull();
    await click(q(host, "opk-reject-opk_1"));
    expect(mockAskReason).toHaveBeenCalledWith(expect.objectContaining({ reasonMinLength: 5 }));
    const [panggil] = posts("/cash-counts/opk_1/reject");
    expect(panggil[1]).toEqual({ alasan: "hitung ulang besok pagi" });
    expect(kunciIdem(panggil)).toBeTruthy();
    expect(notifySuccess).toHaveBeenCalledWith(expect.stringContaining("KSC/OPK-00001"));
  });

  test("Setujui (kurang): satu pop-up — perlakuan, piutang karyawan memuat pemilih karyawan PT, ringkasan, POST approve", async () => {
    pasang();
    mockPost.mockResolvedValue({ data: OPK({ status: "disetujui", perlakuan: "piutang_karyawan", karyawan_nama: "Budi Santoso" }) });
    const host = await daftar(izinPenuh);
    await click(q(host, "opk-approve-opk_1"));
    const form = q(document.body, "opk-approve-form");
    expect(form).not.toBeNull();
    expect(txt(form)).toContain("Kurang Rp 30.000");
    const opsi = [...q(document.body, "opk-approve-treatment").querySelectorAll("option")].map((o) => o.value).filter(Boolean);
    expect(opsi).toEqual(["selisih_kas", "piutang_karyawan"]);
    expect(q(document.body, "opk-approve-employee")).toBeNull();
    await choose(q(document.body, "opk-approve-treatment"), "piutang_karyawan");
    expect(gets("/cash-counts/karyawan")[0][1].params).toMatchObject({ entity_id: "ent_ksc" });
    // Karyawan wajib sebelum kirim.
    expect(q(document.body, "opk-approve-submit").disabled).toBe(true);
    await choose(q(document.body, "opk-approve-employee"), "emp_1");
    expect(txt(q(document.body, "opk-approve-summary"))).toContain("Budi Santoso");
    expect(txt(q(document.body, "opk-approve-summary"))).toContain("piutang karyawan");
    await submit(document.body, "opk-approve-submit");
    const [panggil] = posts("/cash-counts/opk_1/approve");
    expect(panggil[1]).toEqual({ perlakuan: "piutang_karyawan", karyawan_id: "emp_1" });
    expect(kunciIdem(panggil)).toBeTruthy();
    expect(q(document.body, "opk-approve-form")).toBeNull();
    expect(notifySuccess).toHaveBeenCalled();
  });

  test("Setujui (lebih): hanya selisih kas, tanpa pemilih karyawan; 409 server tampil di pop-up yang sama", async () => {
    pasang();
    const kalimat = "Periode 2026-11 sudah ditutup. Selisih opname KSC/OPK-00002 dibukukan pada tanggal hitung (2026-11-28); "
      + "buka kembali periode itu atau tolak opname ini lalu hitung ulang. Opname tetap menunggu.";
    mockPost.mockRejectedValue({ response: { status: 409, data: { detail: kalimat } } });
    const host = await daftar(izinPenuh);
    await click(q(host, "opk-approve-opk_2"));
    const opsi = [...q(document.body, "opk-approve-treatment").querySelectorAll("option")].map((o) => o.value).filter(Boolean);
    expect(opsi).toEqual(["selisih_kas"]);
    expect(q(document.body, "opk-approve-employee")).toBeNull();
    expect(txt(q(document.body, "opk-approve-summary"))).toContain("Kas masuk Rp 50.000");
    await submit(document.body, "opk-approve-submit");
    expect(posts("/cash-counts/opk_2/approve")[0][1]).toEqual({ perlakuan: "selisih_kas", karyawan_id: "" });
    expect(txt(q(document.body, "opk-approve-form-error"))).toBe(kalimat);
    expect(q(document.body, "opk-approve-form")).not.toBeNull();
  });

  test("Batal opname disetujui: alasan ≥ 5 huruf → POST batal berkunci idempotensi; status Dibatalkan", async () => {
    pasang({ items: [DISETUJUI, BATAL] });
    mockAskReason.mockResolvedValue("karyawan salah dipilih");
    mockPost.mockResolvedValue({ data: { ...DISETUJUI, status: "batal", status_label: "Dibatalkan" } });
    const host = await daftar(izinPenuh);
    expect(txt(q(host, "opk-status-opk_5"))).toBe("Dibatalkan");
    expect(q(host, "opk-cancel-opk_5")).toBeNull();
    expect(q(host, "opk-approve-opk_4")).toBeNull();
    expect(q(host, "opk-reject-opk_4")).toBeNull();
    await click(q(host, "opk-cancel-opk_4"));
    const tanya = mockAskReason.mock.calls[0][0];
    expect(tanya).toMatchObject({ reasonMinLength: 5, danger: true });
    expect(tanya.title).toContain("KSC/OPK-00004");
    expect(tanya.message).toContain("KSC/KK-00009");
    expect(tanya.message).toContain("Budi Santoso");
    const [panggil] = posts("/cash-counts/opk_4/batal");
    expect(panggil[0]).toBe("/api/cash-counts/opk_4/batal");
    expect(panggil[1]).toEqual({ alasan: "karyawan salah dipilih" });
    expect(kunciIdem(panggil)).toBeTruthy();
    expect(notifySuccess).toHaveBeenCalledWith(expect.stringContaining("KSC/OPK-00004"));
  });

  test("Batal: penghitung → nonaktif dengan kalimat server; tanpa cash.approve → tidak ada; pop-up dibatalkan → tanpa kiriman", async () => {
    pasang({ items: [{ ...DISETUJUI, kontrol: { batal_pesan: PESAN_BATAL_SENDIRI } }] });
    let host = await daftar(izinPenuh, {}, AKU);
    expect(q(host, "opk-cancel-opk_4").disabled).toBe(true);
    expect(txt(q(host, "opk-action-note-opk_4"))).toBe(PESAN_BATAL_SENDIRI);
    document.body.innerHTML = "";
    host = await daftar(izinHitung);
    expect(q(host, "opk-cancel-opk_4")).toBeNull();
    document.body.innerHTML = "";
    pasang({ items: [DISETUJUI] });
    mockAskReason.mockResolvedValue(null);
    host = await daftar(izinPenuh);
    await click(q(host, "opk-cancel-opk_4"));
    expect(mockAskReason).toHaveBeenCalled();
    expect(mockPost).not.toHaveBeenCalled();
  });

  test("saringan Perlakuan (piutang karyawan, §7.8.6) → parameter `perlakuan` dan saringan unduhan", async () => {
    pasang({ items: [DISETUJUI] });
    const host = await daftar(izinLihat);
    const opsi = [...q(host, "opk-treatment").querySelectorAll("option")].filter((o) => o.value)
      .map((o) => [o.value, o.textContent]);
    expect(opsi).toEqual([["selisih_kas", "Selisih kas"], ["piutang_karyawan", "Piutang karyawan"]]);
    expect(gets("/cash-counts").at(-1)[1].params).not.toHaveProperty("perlakuan");
    await choose(q(host, "opk-treatment"), "piutang_karyawan");
    expect(gets("/cash-counts").at(-1)[1].params).toMatchObject({ entity_id: "ent_ksc", perlakuan: "piutang_karyawan" });
    expect(mockPagerProps.at(-1).exportSpec.filters).toContainEqual(["perlakuan", "eq", "piutang_karyawan"]);
    await choose(q(host, "opk-treatment"), "");
    expect(gets("/cash-counts").at(-1)[1].params).not.toHaveProperty("perlakuan");
  });

  test("preset Pusat Persetujuan {status} dan kartu rekening {hitung} diterapkan", async () => {
    pasang();
    mockPreset = { view: "cash-counts", status: "menunggu_persetujuan", nonce: 1 };
    let host = await daftar(izinPenuh);
    expect(gets("/cash-counts").at(-1)[1].params).toMatchObject({ status: "menunggu_persetujuan" });
    document.body.innerHTML = "";
    mockPreset = { view: "cash-counts", hitung: "kas_kecil", nonce: 2 };
    host = await daftar(izinHitung);
    expect(host).toBeTruthy();
    expect(q(document.body, "opk-form")).not.toBeNull();
    expect(q(document.body, "opk-form-account").value).toBe("kas_kecil");
  });

  test("fokus dokumen: opname → pratinjau; rekening (dari meja) → saringan rekening", async () => {
    pasang();
    const clear = jest.fn();
    await daftar(izinPenuh, { focusDoc: { focus_type: "cash_count", focus_id: "opk_1", number: "KSC/OPK-00001", nonce: 1 },
      onClearFocus: clear });
    expect(mockPreview).toHaveBeenCalledWith(expect.objectContaining({ docType: "cash_count", docId: "opk_1" }));
    expect(clear).toHaveBeenCalled();
    document.body.innerHTML = "";
    const host = await daftar(izinPenuh, { focusDoc: { focus_type: "bank_account", focus_id: "kas_toko", nonce: 2 } });
    expect(q(host, "opk-account").value).toBe("kas_toko");
    expect(gets("/cash-counts").at(-1)[1].params).toMatchObject({ account_id: "kas_toko" });
  });
});

// ── Form Hitung ──────────────────────────────────────────────────────────────────────────────────────────────────────
describe("Opname Kas — form Hitung", () => {
  const buka = (props = {}) => mount(<CashCountForm open onClose={() => {}} onSaved={() => {}} entityId="ent_ksc" {...props} />);

  test("rekening = tunai aktif saja, tanpa saldo (hitung buta); simpan → saldo buku & selisih dari server tampil", async () => {
    pasang();
    mockPost.mockResolvedValue({ data: OPK() });
    const onSaved = jest.fn();
    const host = await buka({ onSaved });
    const opsi = [...q(host, "opk-form-account").querySelectorAll("option")].filter((o) => o.value);
    expect(opsi.map((o) => o.value)).toEqual(["kas_toko", "kas_kecil"]);
    expect(opsi.map((o) => o.textContent).join(" ")).not.toMatch(/Rp/);
    expect(txt(host)).not.toContain("1.000.000");
    await choose(q(host, "opk-form-account"), "kas_toko");
    await type(q(host, "opk-form-amount"), "970000");
    await type(q(host, "opk-form-note"), "Hitung tutup toko");
    await submit(host, "opk-form-submit");
    const [panggil] = posts("/cash-counts");
    expect(panggil[1]).toEqual({ account_id: "kas_toko", jumlah_fisik: 970000, pecahan: [], catatan: "Hitung tutup toko" });
    expect(kunciIdem(panggil)).toBeTruthy();
    const hasil = q(host, "opk-form-result");
    expect(txt(q(hasil, "opk-form-result-book"))).toContain("Rp 1.000.000");
    expect(txt(q(hasil, "opk-form-result-diff"))).toContain("Kurang Rp 30.000");
    expect(txt(hasil)).toContain("KSC/OPK-00001");
    expect(txt(hasil)).toMatch(/orang kedua/);
    expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ id: "opk_1" }));
  });

  test("rincian pecahan menjumlah ke total (jumlah fisik terkunci) dan ikut terkirim", async () => {
    pasang();
    mockPost.mockResolvedValue({ data: SELESAI });
    const host = await buka({ accountId: "kas_toko" });
    expect(q(host, "opk-form-account").value).toBe("kas_toko");
    await click(q(host, "opk-form-denoms-toggle"));
    await type(q(host, "opk-form-denom-100000"), "9");
    await type(q(host, "opk-form-denom-50000"), "1");
    await type(q(host, "opk-form-denom-20000"), "1");
    expect(txt(q(host, "opk-form-denoms-total"))).toContain("Rp 970.000");
    expect(q(host, "opk-form-amount")).toBeNull();
    await submit(host, "opk-form-submit");
    expect(posts("/cash-counts")[0][1]).toEqual({ account_id: "kas_toko", jumlah_fisik: 970000,
      pecahan: [{ nilai: 100000, lembar: 9 }, { nilai: 50000, lembar: 1 }, { nilai: 20000, lembar: 1 }], catatan: "" });
    expect(txt(q(host, "opk-form-result-diff"))).toContain("Tanpa selisih");
    expect(txt(q(host, "opk-form-result"))).toMatch(/selesai/i);
  });

  test("isian kurang → kalimat di pop-up tanpa permintaan; 409 server (masih menunggu) tampil apa adanya", async () => {
    pasang();
    const kalimat = "Opname KSC/OPK-00001 untuk rekening Kas Kasir Toko masih menunggu keputusan selisih. Putuskan dulu "
      + "(setujui atau tolak) sebelum menghitung ulang.";
    mockPost.mockRejectedValue({ response: { status: 409, data: { detail: kalimat } } });
    const host = await buka();
    await submit(host, "opk-form-submit");
    expect(txt(q(host, "opk-form-error"))).toBe("Pilih rekening tunai yang dihitung.");
    expect(mockPost).not.toHaveBeenCalled();
    await choose(q(host, "opk-form-account"), "kas_toko");
    await submit(host, "opk-form-submit");
    expect(txt(q(host, "opk-form-error"))).toBe("Isi jumlah uang fisik yang dihitung (atau rincian pecahannya).");
    await type(q(host, "opk-form-amount"), "970000");
    await submit(host, "opk-form-submit");
    expect(txt(q(host, "opk-form-error"))).toBe(kalimat);
    expect(q(host, "opk-form-result")).toBeNull();
  });
});

// ── Pratinjau OPK- ───────────────────────────────────────────────────────────────────────────────────────────────────
describe("Opname Kas — pratinjau dokumen OPK-", () => {
  test("registri: label, izin cash.view, layar penuh ke Opname Kas (menunggu → saringan menunggu, disorot)", () => {
    const e = previewFor("cash_count");
    expect(e.label).toBe("Opname kas");
    expect(e.perm).toEqual(["cash", "view"]);
    expect(canPreview({ cash: ["view"] }, "cash_count")).toBe(true);
    expect(canPreview({ cash_advance: ["view"] }, "cash_count")).toBe(false);
    expect(e.full(OPK())).toEqual({ view: "cash-counts", nav_id: "cash-bank",
      preset: { status: "menunggu_persetujuan", sorot: "opk_1" } });
    expect(e.full(SELESAI)).toEqual({ view: "cash-counts", nav_id: "cash-bank",
      preset: { status: "", account_id: "kas_toko", sorot: "opk_3" } });
  });

  test("isi: fakta, pecahan, angka, kas penyesuaian + jurnal, riwayat; kalimat kontrol bagi penghitung", async () => {
    const doc = OPK({
      status: "disetujui", status_label: "Disetujui", perlakuan: "piutang_karyawan", perlakuan_label: "Piutang karyawan",
      karyawan_id: "emp_1", karyawan_nama: "Budi Santoso", karyawan_kode: "KAR-001", disetujui_oleh: "Dodi Penyetuju",
      disetujui_pada: "2026-11-28T05:00:00+00:00", pecahan: [{ nilai: 100000, lembar: 9, subtotal: 900000 },
        { nilai: 50000, lembar: 1, subtotal: 50000 }, { nilai: 20000, lembar: 1, subtotal: 20000 }],
      kas: { id: "cash_1", number: "KSC/KK-00009", txn_date: "2026-11-28", direction: "out", amount: 30000, status: "active",
        gl_status: "posted", gl_error: "", journal_entry_id: "je_1", journal_number: "KSC/JU-00020" },
      jejak: [...OPK().jejak, { aksi: "setujui", oleh: "Dodi Penyetuju", pada: "2026-11-28T05:00:00+00:00", catatan: "piutang karyawan" }],
    });
    const host = await mount(<CashCountPreview doc={doc} />);
    const fakta = txt(q(host, "doc-preview-opk-facts"));
    expect(fakta).toContain("Kas Kasir Toko");
    expect(fakta).toContain("Sari Kasir");
    expect(fakta).toContain("Piutang karyawan · Budi Santoso (KAR-001)");
    expect(fakta).toContain("Dodi Penyetuju");
    expect(q(host, "doc-preview-opk-denoms-row-0")).not.toBeNull();
    const angka = txt(q(host, "doc-preview-opk-totals"));
    expect(angka).toContain("Rp 1.000.000");
    expect(angka).toContain("Rp 970.000");
    expect(angka).toContain("Kurang Rp 30.000");
    expect(txt(q(host, "doc-preview-opk-cash"))).toContain("KSC/KK-00009");
    await click(q(host, "doc-preview-opk-journal"));
    expect(mockOpenDocument).toHaveBeenCalledWith(expect.objectContaining({ view: "general-ledger", focus_id: "je_1" }));
    expect(txt(q(host, "doc-preview-opk-history"))).toContain("Dihitung");
    expect(txt(q(host, "doc-preview-opk-history"))).toContain("Disetujui");
    document.body.innerHTML = "";
    const tunggu = await mount(<CashCountPreview doc={OPK({ kontrol: { ditolak: true, pesan: PESAN_ORANG_KEDUA } })} />);
    expect(txt(q(tunggu, "doc-preview-opk-control"))).toBe(PESAN_ORANG_KEDUA);
    expect(txt(q(tunggu, "doc-preview-opk-cash-empty"))).toMatch(/sesudah selisihnya disetujui/);
  });

  test("opname dibatalkan: status Dibatalkan, riwayat Batal beralasan", async () => {
    const doc = { ...BATAL, jejak: [...OPK().jejak,
      { aksi: "batal", oleh: "Dodi Penyetuju", pada: "2026-11-29T05:00:00+00:00", catatan: "karyawan salah dipilih" }] };
    const host = await mount(<CashCountPreview doc={doc} />);
    expect(txt(q(host, "doc-preview-status"))).toBe("Dibatalkan");
    expect(txt(q(host, "doc-preview-opk-history"))).toContain("Dibatalkan · Dodi Penyetuju");
    expect(txt(q(host, "doc-preview-opk-history"))).toContain("karyawan salah dipilih");
  });
});

// ── Rekening & Saldo ─────────────────────────────────────────────────────────────────────────────────────────────────
describe("Rekening & Saldo — aksi Opname di kartu rekening tunai", () => {
  test("komponen kartu: rekening tunai aktif + cash.create → Opname membuka form terisi; selain itu tidak tampil", async () => {
    const host = await mount(<OpnameKartuAksi a={REKENING[0]} currentUser={{ permissions: izinHitung }} />);
    await click(q(host, "bank-opname-kas_toko"));
    expect(mockGo).toHaveBeenCalledWith("cash-counts", { preset: { hitung: "kas_toko", account_id: "kas_toko" } });
    for (const [a, perms] of [[REKENING[2], izinHitung], [REKENING[3], izinHitung], [REKENING[0], izinLihat]]) {
      document.body.innerHTML = "";
      const h = await mount(<OpnameKartuAksi a={a} currentUser={{ permissions: perms }} />);
      expect(q(h, `bank-opname-${a.id}`)).toBeNull();
    }
  });

  test("layar: kartu tunai bertombol Opname (di luar tombol kartu), kartu bank tidak", async () => {
    pasang();
    const host = await mount(<BankAccountsView selectedEntity="ent_ksc" currentUser={{ role: "finance", permissions: izinPenuh }} />);
    const tombol = q(host, "bank-opname-kas_toko");
    expect(tombol).not.toBeNull();
    expect(tombol.closest(`[data-testid="bank-card-kas_toko"]`)).toBeNull();   // bukan tombol di dalam tombol
    expect(q(host, "bank-opname-bank_bca")).toBeNull();
    await click(tombol);
    expect(mockGo).toHaveBeenCalledWith("cash-counts", { preset: { hitung: "kas_toko", account_id: "kas_toko" } });
  });
});

// ── Meja Keuangan ────────────────────────────────────────────────────────────────────────────────────────────────────
const BARIS_MEJA = { ref_type: "bank_account", ref_id: "kas_toko", number: "Kas Kasir Toko", title: "Kas kasir",
  subtitle: "belum pernah diopname · tiap 1 hari", value: 1000000, age_days: 2, at: "2026-11-26T03:00:00+00:00",
  age_kind: "overdue", badge: "lewat", action: "Opname", action_kind: "open", entity_id: "ent_ksc", account_id: "kas_toko",
  cash_type: "kas_kasir", jarak_hari: 1, jatuh_tempo: "2026-11-26T03:00:00+00:00", opname_terakhir_id: "",
  opname_terakhir_nomor: "", opname_terakhir_pada: "" };
const MEJA = { queues: [{ id: "opname_kas_jatuh_tempo", label: "Opname kas jatuh tempo", count: 1, rows: [BARIS_MEJA],
  oldest_age_days: 2, action_label: "Opname", value_label: "Saldo buku" }], not_my_desk: [] };

describe("Meja Keuangan — Opname kas jatuh tempo", () => {
  test("kelompok tampil bagi pemegang cash.create (penghitung), tidak bagi yang lain", () => {
    const g = PERLU_TINDAKAN.find((x) => x.queues?.includes("opname_kas_jatuh_tempo"));
    expect(g).toMatchObject({ key: "opname_kas", label: "Opname kas jatuh tempo" });
    const ada = (perms) => susunKelompok(perms, { desk: MEJA }).some((x) => x.id === "opname_kas");
    expect(ada({ payment_variance: ["decide"], cash: ["view", "create"] })).toBe(true);
    const kelompok = susunKelompok({ cash: ["create"] }, { desk: MEJA }).find((x) => x.id === "opname_kas");
    expect(kelompok).toMatchObject({ value_label: "Saldo buku", count: 1, total_value: 1000000 });
    expect(ada({ payment_variance: ["decide"], cash: ["view"] })).toBe(false);
  });

  test("petunjuk kelompok menyebut jarak opname dari data server (pengaturan `kas.opname_*_hari`), bukan tertulis mati", () => {
    const kecil = { ...BARIS_MEJA, ref_id: "kas_kecil", account_id: "kas_kecil", number: "Kas Kecil Gudang",
      title: "Kas kecil", cash_type: "kas_kecil", jarak_hari: 3 };
    const meja = { ...MEJA, queues: [{ ...MEJA.queues[0], count: 2, rows: [BARIS_MEJA, kecil] }] };
    const g = susunKelompok({ cash: ["create"] }, { desk: meja }).find((x) => x.id === "opname_kas");
    expect(g.hint).toContain("kas kasir tiap 1 hari");
    expect(g.hint).toContain("kas kecil tiap 3 hari");
    expect(g.hint).toContain("Pengaturan");
    expect(g.hint).not.toMatch(/tiap hari|tiap minggu/);
  });

  test("baris 'Opname' membuka form Hitung di tempat, terisi rekening; tersimpan → hasil di pop-up + kartu dimuat ulang", async () => {
    mockGet.mockImplementation((url) => {
      if (url.includes("/finance/desk")) return Promise.resolve({ data: MEJA });
      if (url.endsWith("/bank-accounts")) return Promise.resolve({ data: REKENING });
      return Promise.resolve({ data: null });
    });
    mockPost.mockResolvedValue({ data: SELESAI });
    const perms = { payment_variance: ["decide"], cash: ["view", "create"] };
    const host = await mount(<FinanceDesk currentUser={{ permissions: perms }} selectedEntity="ent_ksc" />);
    const aksi = q(host, "fin-desk-opname_kas-action-kas_toko");
    expect(txt(aksi)).toBe("Opname");
    const sebelum = gets("/finance/desk").length;
    await click(aksi);
    expect(q(document.body, "opk-form")).not.toBeNull();
    expect(q(document.body, "opk-form-account").value).toBe("kas_toko");
    await type(q(document.body, "opk-form-amount"), "1000000");
    await submit(document.body, "opk-form-submit");
    expect(posts("/cash-counts")[0][1]).toMatchObject({ account_id: "kas_toko", jumlah_fisik: 1000000 });
    expect(txt(q(document.body, "opk-form-result"))).toContain("KSC/OPK-00003");
    expect(gets("/finance/desk").length).toBeGreaterThan(sebelum);
    await click(q(document.body, "opk-form-done"));
    expect(q(document.body, "opk-form")).toBeNull();
    expect(mockGo).not.toHaveBeenCalled();
  });
});
