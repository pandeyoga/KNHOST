// Kas & Bank bagian 1 (Tugas 6) — layar: Pindah Dana, Akun per rekening (alat pindah saldo), kolom "Akun buku besar" di
// Rekening & Saldo, kas manual tanpa kategori Transfer/Top-up, pratinjau dokumen `fund_transfer`, pratinjau refund
// ber-rekening. Rancangan `docs/superpowers/specs/2026-11-27-kas-bank-1-rekening-pindah-dana-design.md` §5.2–§5.4.
// Izin menyembunyikan aksi (bukan nama peran); satu pop-up per aksi; sidik yang dilihat dikirim saat menyetujui; 409
// "Angka berubah, muat ulang." tampil + angka dimuat ulang; selisih wajib dicentang (R10).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import FundTransfersView from "../finance/fundtransfer/FundTransfersView";
import { aksiPindahDana, validasiPindahDana } from "../finance/fundtransfer/fundTransferShared";
import AkunPerRekeningView from "../finance/cutover/AkunPerRekeningView";
import { alasanTidakBisaSiapkan } from "../finance/cutover/cutoverShared";
import CashManagementView, { CATEGORIES, CASH_REF_DOC, REF_LABEL } from "../purchasing/CashManagementView";
import BankAccountsView, { AkunBukuBesar } from "../finance/BankAccountsView";
import BankAccountChangesPanel from "../finance/BankAccountChangesPanel";
import ReturnSettleModal from "../sales/ReturnSettleModal";
import FundTransferPreview from "../documents/preview/bodies/FundTransferPreview";
import { canPreview, previewFor } from "../documents/preview/docPreviewRegistry";
import { HUB_TABS } from "../../config/hubTabs";
import { queueLink } from "../approvals/inboxTabs";

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
}));
jest.mock("../../components/KNSelect", () => {
  const Sel = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      <option value="">-</option>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
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
jest.mock("../../context/AppNavContext", () => ({
  __esModule: true,
  useAppNav: () => ({ go: mockGo, canOpen: () => true, openDocument: () => {}, previewsEnabled: true,
    openDocPreview: mockPreview }),
}));
jest.mock("../../utils/feedback", () => ({ __esModule: true, notifySuccess: jest.fn(), notifyError: jest.fn(),
  notifyInfo: jest.fn(), notifyWarning: jest.fn() }));
jest.mock("../../hooks/useViewPreset", () => ({ __esModule: true, default: () => null, useViewPreset: () => null }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const qa = (host, sel) => host.querySelectorAll(sel);
async function flush(ms = 0) {
  for (let i = 0; i < 3; i += 1) {
    // eslint-disable-next-line no-await-in-loop
    await act(async () => { await new Promise((r) => setTimeout(r, ms)); });
  }
}
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await flush();
  return host;
}
async function click(el) { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await flush(); }
async function choose(el, value) {
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set;
    setter.call(el, value);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}
async function type(el, value) {
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
    setter.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await flush();
}
async function submit(host, id) {
  const btn = q(host, id);
  await act(async () => { btn.closest("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
  await flush();
}
const izinPenuh = { cash: ["view", "create", "delete", "approve"], accounting: ["view", "manage"] };
const posts = (akhiran) => mockPost.mock.calls.filter(([u]) => String(u).endsWith(akhiran));
const gets = (akhiran) => mockGet.mock.calls.filter(([u]) => String(u).endsWith(akhiran));

// Tiap layar baru dirender tanpa galat/peringatan React di konsol (dispatch Tugas 6).
let galatKonsol;
beforeEach(() => { galatKonsol = jest.spyOn(console, "error").mockImplementation(() => {}); });
afterEach(() => {
  const panggilan = galatKonsol.mock.calls.map((c) => String(c[0]).slice(0, 200));
  galatKonsol.mockRestore();
  mockGet.mockReset(); mockPost.mockReset(); mockAskConfirm.mockReset(); mockAskReason.mockReset(); mockGo.mockReset();
  mockPreview.mockReset(); document.body.innerHTML = "";
  expect(panggilan).toEqual([]);
});

// ── Pindah Dana ──────────────────────────────────────────────────────────────────────────────────────────────────────
const DOK = {
  menunggu: { id: "pdn_1", number: "KSC/PDN-00001", entity_id: "ent_ksc", status: "menunggu_persetujuan", nominal: 500000, biaya: 0,
    rekening_asal: "BCA Operasional", rekening_tujuan: "Kas Toko", tanggal_kirim: "2026-11-27", tanggal_terima: "2026-11-27",
    kontrol: { dua_orang: true, sendiri: false, ditolak: false, pesan: "" } },
  perjalanan: { id: "pdn_2", number: "KSC/PDN-00002", entity_id: "ent_ksc", status: "dalam_perjalanan", nominal: 2000000, biaya: 6500,
    rekening_asal: "BCA Operasional", rekening_tujuan: "Mandiri", tanggal_kirim: "2026-11-26", tanggal_terima: "2026-11-28", dua_tahap: true },
  selesai: { id: "pdn_3", number: "KSC/PDN-00003", entity_id: "ent_ksc", status: "selesai", nominal: 100000, biaya: 0,
    rekening_asal: "Kas Toko", rekening_tujuan: "Kas Kecil", tanggal_kirim: "2026-11-25" },
};
const REKENING = [
  { id: "bank_bca", name: "BCA Operasional", entity_id: "ent_ksc", account_type: "bank", bank_name: "BCA", account_number: "123",
    is_active: true, balance: 5000000 },
  { id: "bank_kt", name: "Kas Toko", entity_id: "ent_ksc", account_type: "cash", cash_type: "kas_besar", is_active: true, balance: 2000000 },
];

function pasangDaftar(items = Object.values(DOK)) {
  mockGet.mockImplementation((url) => {
    if (url.endsWith("/fund-transfers")) return Promise.resolve({ data: { items, total: items.length, page: 1, page_size: 25, has_more: false } });
    if (url.endsWith("/bank-accounts")) return Promise.resolve({ data: REKENING });
    return Promise.resolve({ data: [] });
  });
}
const pindahDana = (perms) => mount(<FundTransfersView currentUser={{ role: "finance", permissions: perms }} selectedEntity="ent_ksc" />);

/** Tangkapan 27 Nov (temuan 1): kalimat alasan/anulir di sel aksi `text-right` (mewarisi `white-space: nowrap` dari
 *  components.css untuk kolom angka) harus membungkus sendiri — kalau tidak, tabel melebar dan kalimatnya terpotong. */
function expectBungkus(el) {
  expect(el.closest("td").classList.contains("text-right")).toBe(true);
  expect(el.classList.contains("whitespace-normal")).toBe(true);
  expect(el.className).toMatch(/max-w-\[\d+px\]/);
}

describe("Pindah Dana — daftar, izin, satu pop-up", () => {
  test("tab hub Kas & Bank: Pindah Dana tampak (6 tab), Akun per rekening tersembunyi menyorot Rekening & Saldo", () => {
    const tabs = HUB_TABS["cash-bank"];
    expect(tabs.filter((t) => !t.hidden).map((t) => t.label)).toEqual(
      ["Rekening & Saldo", "Transaksi Kas", "Rekonsiliasi", "Kas Kecil", "Titipan Sales", "Pindah Dana"]);
    expect(tabs.find((t) => t.view === "kas-per-rekening")).toMatchObject({ hidden: true, aliasOf: "bank-accounts" });
  });

  test("antrean Persetujuan Menunggu di beranda membuka Pindah Dana dengan saringan dari server", () => {
    const q = { key: "fund_transfer", view: "fund-transfers", preset: { status: "menunggu_persetujuan" } };
    expect(queueLink(q, () => true)).toEqual({ view: "fund-transfers", preset: { status: "menunggu_persetujuan" } });
    expect(queueLink({ key: "pindah_saldo_kas", view: "kas-per-rekening" }, () => true)).toEqual({ view: "kas-per-rekening" });
  });

  test("izin lihat saja: tanpa tombol buat dan tanpa aksi baris; nomor = tautan pratinjau", async () => {
    pasangDaftar();
    const host = await pindahDana({ cash: ["view"] });
    expect(q(host, "ft-row-pdn_1")).not.toBeNull();
    expect(q(host, "ft-create")).toBeNull();
    for (const id of ["pdn_1", "pdn_2", "pdn_3"]) {
      expect(q(host, `ft-approve-${id}`)).toBeNull();
      expect(q(host, `ft-receive-${id}`)).toBeNull();
      expect(q(host, `ft-cancel-${id}`)).toBeNull();
    }
    await click(q(host, "ft-open-pdn_1"));
    expect(mockPreview).toHaveBeenCalledWith({ docType: "fund_transfer", docId: "pdn_1", number: "KSC/PDN-00001", entityId: "ent_ksc" });
  });

  test("aksi mengikuti izin & status: Setujui (cash.approve) di menunggu, Terima (cash.create) di perjalanan, Batal (cash.delete)", async () => {
    pasangDaftar();
    let host = await pindahDana({ cash: ["view", "approve"] });
    expect(q(host, "ft-approve-pdn_1")).not.toBeNull();
    expect(q(host, "ft-receive-pdn_2")).toBeNull();
    expect(q(host, "ft-cancel-pdn_3")).toBeNull();
    document.body.innerHTML = "";
    host = await pindahDana({ cash: ["view", "create"] });
    expect(q(host, "ft-approve-pdn_1")).toBeNull();
    expect(q(host, "ft-receive-pdn_2")).not.toBeNull();
    expect(q(host, "ft-create")).not.toBeNull();
    document.body.innerHTML = "";
    host = await pindahDana({ cash: ["view", "delete"] });
    expect([...qa(host, "[data-testid^='ft-cancel-']")].map((b) => b.dataset.testid)).toEqual(
      ["ft-cancel-pdn_1", "ft-cancel-pdn_2", "ft-cancel-pdn_3"]);
  });

  test("Setujui nonaktif dengan alasan tertulis bila kontrol dua orang menolak pembuatnya", async () => {
    const pesan = "Pindah dana antar rekening harus diputuskan orang lain: Anda yang mengajukannya.";
    pasangDaftar([{ ...DOK.menunggu, kontrol: { dua_orang: true, sendiri: true, ditolak: true, pesan } }]);
    const host = await pindahDana(izinPenuh);
    expect(q(host, "ft-approve-pdn_1").disabled).toBe(true);
    expect(q(host, "ft-action-note-pdn_1").textContent).toBe(pesan);
    expectBungkus(q(host, "ft-action-note-pdn_1"));
  });

  test("Setujui: konfirmasi menyebut nominal & rekening → POST approve berkunci idempotensi", async () => {
    pasangDaftar([DOK.menunggu]);
    mockAskConfirm.mockResolvedValue(true);
    mockPost.mockResolvedValue({ data: { ...DOK.menunggu, status: "selesai" } });
    const host = await pindahDana(izinPenuh);
    await click(q(host, "ft-approve-pdn_1"));
    expect(mockAskConfirm).toHaveBeenCalledTimes(1);
    expect(mockAskConfirm.mock.calls[0][0].message).toMatch(/Rp\s?500\.000 dari BCA Operasional ke Kas Toko/);
    const [[url, body, cfg]] = posts("/fund-transfers/pdn_1/approve");
    expect(url).toBe("/api/fund-transfers/pdn_1/approve");
    expect(body).toEqual({});
    expect(cfg.headers["Idempotency-Key"]).toMatch(/^pdna-/);
  });

  test("Batal: alasan wajib (askReason ≥ 5 huruf) → POST cancel {alasan}; batal = tidak ada permintaan", async () => {
    pasangDaftar([DOK.selesai]);
    mockAskReason.mockResolvedValueOnce(null);
    const host = await pindahDana(izinPenuh);
    await click(q(host, "ft-cancel-pdn_3"));
    expect(posts("/cancel")).toHaveLength(0);
    mockAskReason.mockResolvedValueOnce("salah rekening tujuan");
    mockPost.mockResolvedValue({ data: { ...DOK.selesai, status: "batal" } });
    await click(q(host, "ft-cancel-pdn_3"));
    expect(mockAskReason.mock.calls[1][0]).toMatchObject({ reasonMinLength: 5, danger: true });
    expect(posts("/fund-transfers/pdn_3/cancel")[0][1]).toEqual({ alasan: "salah rekening tujuan" });
  });

  test("Teruskan pembatalan: konfirmasi menyebut alasan tercatat (tanpa alasan baru) → POST cancel {alasan lama}", async () => {
    const tertunda = { ...DOK.selesai, status: "batal", batal_tertunda: true, alasan_batal: "salah rekening tujuan" };
    pasangDaftar([tertunda]);
    mockAskConfirm.mockResolvedValue(true);
    mockPost.mockResolvedValue({ data: { ...tertunda, batal_tertunda: false } });
    const host = await pindahDana(izinPenuh);
    expect(q(host, "ft-cancel-pdn_3").textContent).toMatch(/Teruskan pembatalan/);
    await click(q(host, "ft-cancel-pdn_3"));
    expect(mockAskReason).not.toHaveBeenCalled();
    expect(mockAskConfirm.mock.calls[0][0]).toMatchObject({ testId: "ft-cancel-resume", danger: true });
    expect(mockAskConfirm.mock.calls[0][0].message).toMatch(/alasan yang sudah tercatat: "salah rekening tujuan"/);
    expect(posts("/fund-transfers/pdn_3/cancel")[0][1]).toEqual({ alasan: "salah rekening tujuan" });
  });

  test("Batal dokumen menunggu: kas belum terbit → cukup ditandai batal; kas terbit sebagian (kas_ids) → kas dibalik", async () => {
    pasangDaftar([DOK.menunggu, { ...DOK.menunggu, id: "pdn_4", number: "KSC/PDN-00004", terbit_error: "Rekening berubah.",
      kas_ids: { kirim: "cash_k", biaya: "cash_b" } }]);
    mockAskReason.mockResolvedValue(null);
    const host = await pindahDana(izinPenuh);
    await click(q(host, "ft-cancel-pdn_1"));
    expect(mockAskReason.mock.calls[0][0].message).toMatch(/Kasnya belum terbit/);
    await click(q(host, "ft-cancel-pdn_4"));
    expect(mockAskReason.mock.calls[1][0].message).toMatch(/Semua kas dokumen ini dibalik/);
    expect(posts("/cancel")).toHaveLength(0);
  });

  test("Terima: satu pop-up bertanggal (bawaan rencana) → POST receive {tanggal}; galat server tampil di pop-up", async () => {
    pasangDaftar([DOK.perjalanan]);
    const host = await pindahDana(izinPenuh);
    await click(q(host, "ft-receive-pdn_2"));
    expect(qa(document.body, ".kn-modal-overlay, .modal-overlay").length).toBe(1);
    expect(q(host, "ft-receive-date").value).toBe("2026-11-28");
    mockPost.mockRejectedValueOnce({ response: { status: 409, data: { detail: "Pindah Dana KSC/PDN-00002 sudah diterima." } } });
    await submit(host, "ft-receive-submit");
    expect(posts("/fund-transfers/pdn_2/receive")[0][1]).toEqual({ tanggal: "2026-11-28" });
    expect(q(host, "ft-receive-form").textContent).toMatch(/sudah diterima/);
    expect(q(host, "ft-error")).toBeNull();   // galat aksi pop-up tidak digandakan di bilah layar
  });

  test("Buat: satu pop-up FormModal, validasi di layar, ringkasan menyebut nominal & PT, POST /fund-transfers", async () => {
    pasangDaftar([]);
    mockPost.mockResolvedValue({ data: { ...DOK.selesai, number: "KSC/PDN-00009" } });
    const host = await pindahDana(izinPenuh);
    await click(q(host, "ft-create"));
    expect(qa(document.body, ".kn-modal-overlay, .modal-overlay").length).toBe(1);
    expect(q(host, "ft-form")).not.toBeNull();
    await submit(host, "ft-form-submit");
    expect(q(host, "ft-form").textContent).toMatch(/Pilih rekening asal dan rekening tujuan\./);
    expect(posts("/fund-transfers")).toHaveLength(0);
    await choose(q(host, "ft-form-from"), "bank_bca");
    await choose(q(host, "ft-form-to"), "bank_kt");
    await type(q(host, "ft-form-amount"), "750000");
    await type(q(host, "ft-form-fee"), "6500");
    expect(q(host, "ft-form-summary").textContent).toMatch(/Rp\s?750\.000 dipindah dari BCA Operasional ke Kas Toko/);
    await submit(host, "ft-form-submit");
    const [[url, body, cfg]] = posts("/fund-transfers");
    expect(url).toBe("/api/fund-transfers");
    expect(body).toMatchObject({ entity_id: "ent_ksc", rekening_asal_id: "bank_bca", rekening_tujuan_id: "bank_kt",
      nominal: 750000, biaya: 6500, tanggal_terima: "" });
    expect(cfg.headers["Idempotency-Key"]).toMatch(/^pdn-/);
  });

  test("aturan aksi & validasi (fungsi murni)", () => {
    expect(aksiPindahDana({ ...DOK.selesai, status: "batal", batal_tertunda: true }, izinPenuh).batal.label).toBe("Teruskan pembatalan");
    expect(aksiPindahDana({ ...DOK.perjalanan, dalam_proses: true }, izinPenuh).terima.alasan).toMatch(/Sedang diproses/);
    expect(aksiPindahDana({ ...DOK.selesai, status: "batal" }, izinPenuh)).toMatchObject({ setujui: null, terima: null, batal: null });
    const isi = { rekening_asal_id: "a", rekening_tujuan_id: "b", nominal: "10", biaya: "" };
    expect(validasiPindahDana(isi)).toBe("");
    expect(validasiPindahDana({ ...isi, rekening_tujuan_id: "a" })).toBe("Rekening asal dan tujuan tidak boleh sama.");
    expect(validasiPindahDana({ ...isi, biaya: "-1" })).toBe("Biaya transfer tidak boleh negatif.");
    expect(validasiPindahDana({ ...isi, tanggal_kirim: "2026-11-27", tanggal_terima: "2026-11-26" }))
      .toBe("Tanggal terima tidak boleh sebelum tanggal kirim.");
  });
});

// ── Pratinjau dokumen ────────────────────────────────────────────────────────────────────────────────────────────────
describe("Registri pratinjau dokumen — fund_transfer", () => {
  test("terdaftar: label Pindah Dana, izin cash.view, layar penuh Kas & Bank › Pindah Dana", () => {
    const e = previewFor("fund_transfer");
    expect(e.label).toBe("Pindah Dana");
    expect(e.perm).toEqual(["cash", "view"]);
    expect(e.full({ id: "pdn_1", number: "KSC/PDN-00001" })).toMatchObject({ view: "fund-transfers", focus_type: "fund_transfer",
      focus_id: "pdn_1" });
    expect(canPreview({ cash: ["view"] }, "fund_transfer")).toBe(true);
    expect(canPreview({ accounting: ["view"] }, "fund_transfer")).toBe(false);
  });

  test("isi pratinjau: fakta, kas dokumen (dibatalkan/jurnal), total keluar asal, riwayat", async () => {
    const doc = { ...DOK.perjalanan, kas: [
      { id: "k1", number: "KSC/CASH-1", peran: "Kas keluar rekening asal", account_name: "BCA Operasional", direction: "out",
        amount: 2000000, txn_date: "2026-11-26", status: "posted", gl_status: "posted", journal_number: "JE-1" },
      { id: "k2", number: "KSC/CASH-2", peran: "Biaya transfer", account_name: "BCA Operasional", direction: "out", amount: 6500,
        txn_date: "2026-11-26", status: "void", void_journal_number: "JE-9" }],
      jejak: [{ aksi: "buat", oleh: "Rina", pada: "2026-11-26T02:00:00Z" },
        { aksi: "terima", oleh: "Budi", pada: "2026-11-27T03:00:00Z", catatan: "diterima 2026-11-27" }] };
    const host = await mount(<FundTransferPreview doc={doc} push={() => {}} canPush={() => false} currentUser={{ permissions: {} }} />);
    expect(q(host, "doc-preview-ft-cash").textContent).toMatch(/Jurnal JE-1/);
    expect(q(host, "doc-preview-ft-cash").textContent).toMatch(/Dibatalkan · pembalik JE-9/);
    expect(q(host, "doc-preview-totals").textContent).toMatch(/Keluar dari rekening asal\s*Rp\s?2\.006\.500/);
    expect(q(host, "doc-preview-ft-history").textContent).toMatch(/Dibuat · Rina/);
    // Tangkapan 27 Nov (temuan 3): tanggal ISO di catatan server ditulis dengan pemformat tanggal baku.
    expect(q(host, "doc-preview-ft-history").textContent).toMatch(/Diterima rekening tujuan · Budi · .* — diterima 27 Nov 2026/);
    expect(q(host, "doc-preview-ft-history").textContent).not.toMatch(/2026-11-27/);
  });
});

// ── Akun per rekening ────────────────────────────────────────────────────────────────────────────────────────────────
const PV = {
  entity_id: "ent_ksc", pt: "Sukacita", aktif: false, aktif_sejak: "", total_dipindah: 7000000, posting_gagal: 0,
  posting_gagal_rincian: [], sidik: "sidik_a", usulan: null,
  rekening: [{ id: "bank_bca", nama: "BCA Operasional", cash_type: "kas_besar", aktif: true, akun_tujuan: "1-1100-01",
    akun_tujuan_nama: "BCA Operasional", akun_tujuan_baru: true, saldo_buku: 5000000,
    asal: [{ akun: "1-1100", nama: "Kas Besar / Bank", jumlah: 5000000 }], dipindah: 5000000, selisih: 0 }],
  kas_tanpa_rekening: { tunggal: [], tetap: 0, tetap_rincian: [] }, akun_lama: [], baris_jurnal: [],
};
const USULAN = { id: "psk_ent_ksc_001", entity_id: "ent_ksc", label: "Pindah saldo kas Sukacita", status: "menunggu",
  total_dipindah: 7000000, disiapkan_oleh: "Sinta", disiapkan_pada: "2026-11-27T01:00:00Z",
  kontrol: { dua_orang: true, sendiri: false, ditolak: false, pesan: "" } };

function pasangAlat({ pv = PV, usulan = [USULAN], urutan = null } = {}) {
  let n = 0;
  mockGet.mockImplementation((url) => {
    if (url.endsWith("/kas-per-rekening/ent_ksc/pratinjau")) {
      const isi = urutan ? urutan[Math.min(n, urutan.length - 1)] : pv;
      n += 1;
      return Promise.resolve({ data: isi });
    }
    if (url.endsWith("/kas-per-rekening/usulan")) return Promise.resolve({ data: { items: usulan, total: usulan.length } });
    if (url.endsWith("/gl/accounts")) return Promise.resolve({ data: [] });
    return Promise.resolve({ data: [] });
  });
}
const alat = (perms) => mount(<AkunPerRekeningView currentUser={{ role: "finance", permissions: perms }} selectedEntity="ent_ksc" />);

describe("Akun per rekening — pratinjau, siapkan, setujui dengan sidik", () => {
  test("tanpa accounting.manage: layar hanya memberi tahu, pratinjau tidak diminta", async () => {
    pasangAlat();
    const host = await alat({ cash: ["view", "approve"], accounting: ["view"] });
    expect(q(host, "ps-no-access").textContent).toMatch(/Akuntansi' tingkat kelola/);
    expect(gets("/pratinjau")).toHaveLength(0);
    expect(q(host, "ps-prepare")).toBeNull();
  });

  test("pratinjau tabel: akun tujuan (sub-akun baru), asal saldo; Siapkan nonaktif bila ada usulan menunggu", async () => {
    pasangAlat({ pv: { ...PV, usulan: USULAN } });
    const host = await alat(izinPenuh);
    expect(q(host, "ps-target-bank_bca").textContent).toMatch(/1-1100-01 · BCA Operasional/);
    expect(q(host, "ps-target-bank_bca").textContent).toMatch(/sub-akun baru/);
    expect(q(host, "ps-prepare").disabled).toBe(true);
    expect(q(host, "ps-prepare-why").textContent).toMatch(/masih menunggu persetujuan/);
  });

  test("posting kas gagal/tertunda: Siapkan nonaktif dengan jumlahnya + tautan Posting Gagal", async () => {
    pasangAlat({ pv: { ...PV, posting_gagal: 2, posting_gagal_rincian: [{ jenis: "cash_transaction", label: "Transaksi Kas",
      jumlah: 2, tempat: "posting_gagal", arahan: "ulangi di Keuangan › Posting Gagal", contoh: [] }] }, usulan: [] });
    const host = await alat(izinPenuh);
    expect(q(host, "ps-prepare").disabled).toBe(true);
    expect(q(host, "ps-prepare-why").textContent).not.toMatch(/Posting Gagal/);   // arahan per jenis ada di rincian
    expect(q(host, "ps-pending-postings").textContent).toMatch(/2 posting kas gagal atau tertunda/);
    expect(q(host, "ps-pending-cash_transaction").textContent).toMatch(/Transaksi Kas: 2 — ulangi di Keuangan › Posting Gagal/);
    await click(q(host, "ps-open-posting-failures"));
    expect(mockGo).toHaveBeenCalledWith("posting-failures");
    expect(alasanTidakBisaSiapkan({ ...PV, aktif: true }, { canManage: true })).toMatch(/sudah memakai akun per rekening/);
  });

  test("posting tertunda di luar Posting Gagal: nomor dokumen + arahan; tombol hanya ke layar yang mendaftarnya", async () => {
    const rincian = [
      { jenis: "gaji_jalur_lama", label: "Penggajian yang jurnal bayarnya sudah terbit tetapi kasnya belum tercatat", jumlah: 1,
        tempat: "proses_gaji", arahan: "catat pembayarannya lewat Bayar di SDM › Penggajian › Proses Gaji", contoh: ["PAY/KSC/7"] },
      { jenis: "kas_tertunda", label: "Transaksi kas yang jurnalnya belum selesai atau sedang dibatalkan", jumlah: 1,
        tempat: "tunggu", arahan: "jurnal atau pembatalannya sedang berjalan — muat ulang sebentar lagi", contoh: ["KAS-0009"] },
    ];
    pasangAlat({ pv: { ...PV, posting_gagal: 2, posting_gagal_rincian: rincian }, usulan: [] });
    const host = await alat(izinPenuh);
    expect(q(host, "ps-pending-gaji_jalur_lama").textContent).toMatch(/: 1 \(PAY\/KSC\/7\) — catat pembayarannya lewat Bayar/);
    expect(q(host, "ps-pending-kas_tertunda").textContent).toMatch(/\(KAS-0009\) — jurnal atau pembatalannya sedang berjalan/);
    expect(q(host, "ps-open-posting-failures")).toBeNull();          // tidak ada yang tampil di Posting Gagal
    await click(q(host, "ps-open-hr-payroll-runs"));
    expect(mockGo).toHaveBeenCalledWith("hr-payroll-runs");
  });

  test("PT sudah aktif: saldo akun vs buku kas + dipindah saat disetujui, tanpa selisih palsu; selisih nyata diperingatkan", async () => {
    const rekAktif = { ...PV.rekening[0], akun_tujuan_baru: false, akun_tujuan_buatan_sistem: true, saldo_akun_tujuan: 5000000,
      saldo_buku: 5000000, saldo_sesudah: 5000000, selisih: 0 };
    const pvAktif = { ...PV, aktif: true, aktif_sejak: "2026-11-27T02:00:00Z", sidik: "", baris_jurnal: [], rekening: [rekAktif],
      akun_lama: [{ akun: "1-1100", nama: "Kas Besar / Bank", saldo: 40000, dipindah: 5000000, sisa: 40000 }],
      pindah_saldo: { id: "psk_ent_ksc_001", journal_number: "JE-77", status: "disetujui" } };
    pasangAlat({ pv: pvAktif, usulan: [{ ...USULAN, status: "disetujui", journal_number: "JE-77" }] });
    let host = await alat(izinPenuh);
    const kepala = q(host, "ps-accounts").querySelector("thead").textContent;
    expect(kepala).toMatch(/Saldo akun/);
    expect(kepala).toMatch(/Dipindah saat disetujui/);
    expect(kepala).toMatch(/Selisih akun − buku kas/);
    expect(kepala).not.toMatch(/Dipindah dari/);
    expect(q(host, "ps-accounts-gl-bank_bca").textContent).toMatch(/5\.000\.000/);
    expect(q(host, "ps-accounts-diff-bank_bca").textContent).toBe("—");
    expect(q(host, "ps-target-bank_bca").textContent).not.toMatch(/sub-akun baru/);
    expect(q(host, "ps-active-check").textContent).toMatch(/sama dengan saldo buku kasnya/);
    expect(q(host, "ps-old-accounts").querySelector("thead").textContent).toMatch(/Dipindah saat disetujui.*Saldo sekarang/);
    expect(q(host, "ps-old-accounts").querySelector("thead").textContent).not.toMatch(/Sisa/);
    expect(q(host, "ps-sec-journal")).toBeNull();
    expect(q(host, "ps-mode").textContent).toMatch(/memakai akun per rekening sejak .*jurnal JE-77/);
    expect(q(host, "ps-prepare").disabled).toBe(true);
    document.body.innerHTML = "";
    pasangAlat({ pv: { ...pvAktif, rekening: [{ ...rekAktif, saldo_akun_tujuan: 5005000, selisih: 5000 }] }, usulan: [] });
    host = await alat(izinPenuh);
    expect(q(host, "ps-accounts-diff-bank_bca").textContent).toMatch(/5\.000/);
    expect(q(host, "ps-active-check").textContent).toMatch(/1 rekening berselisih dengan buku kasnya: BCA Operasional Rp\s?5\.000/);
  });

  test("Siapkan: rekening berakun pilihan Finance bisa kembali ke sub-akun buatan sistem (dikirim \"\")", async () => {
    const rekFinance = { ...PV.rekening[0], akun_tujuan: "1-1105", akun_tujuan_nama: "Bank BCA (Finance)", akun_tujuan_baru: false,
      akun_tujuan_buatan_sistem: false };
    pasangAlat({ pv: { ...PV, rekening: [rekFinance] }, usulan: [] });
    mockPost.mockResolvedValue({ data: { ...USULAN } });
    const host = await alat(izinPenuh);
    await click(q(host, "ps-prepare"));
    const pilih = q(host, "ps-prepare-account-bank_bca");
    expect([...pilih.options].map((o) => o.textContent)).toContain("Sub-akun baru (dibuat sistem)");
    await choose(pilih, "__subakun_baru__");
    await submit(host, "ps-prepare-submit");
    expect(posts("/kas-per-rekening/ent_ksc/siapkan")[0][1]).toEqual({ pilihan_akun: { bank_bca: "" } });
    // Akun sekarang = sub-akun buatan sistem → tanpa pilihan kembali (sudah buatan sistem)
    document.body.innerHTML = "";
    pasangAlat({ pv: { ...PV, rekening: [{ ...rekFinance, akun_tujuan: "1-1100-01", akun_tujuan_buatan_sistem: true }] }, usulan: [] });
    const host2 = await alat(izinPenuh);
    await click(q(host2, "ps-prepare"));
    expect([...q(host2, "ps-prepare-account-bank_bca").options].map((o) => o.textContent)).not.toContain("Sub-akun baru (dibuat sistem)");
  });

  test("ganti PT cepat: jawaban pratinjau PT lama yang terlambat tidak ditampilkan dengan label PT baru", async () => {
    let lepasLama;
    const pvKanda = { ...PV, entity_id: "ent_kanda", rekening: [{ ...PV.rekening[0], id: "bank_kanda", nama: "BRI Kanda" }] };
    mockGet.mockImplementation((url) => {
      if (url.endsWith("/kas-per-rekening/ent_ksc/pratinjau")) return new Promise((r) => { lepasLama = r; });
      if (url.endsWith("/kas-per-rekening/ent_kanda/pratinjau")) return Promise.resolve({ data: pvKanda });
      if (url.endsWith("/kas-per-rekening/usulan")) return Promise.resolve({ data: { items: [], total: 0 } });
      return Promise.resolve({ data: [] });
    });
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    const view = (e) => <AkunPerRekeningView currentUser={{ role: "finance", permissions: izinPenuh }} selectedEntity={e} />;
    await act(async () => { root.render(view("ent_ksc")); });
    await act(async () => { root.render(view("ent_kanda")); });
    await flush();
    expect(q(host, "ps-target-bank_kanda")).not.toBeNull();
    await act(async () => { lepasLama({ data: PV }); });
    await flush();
    expect(q(host, "ps-target-bank_kanda")).not.toBeNull();
    expect(q(host, "ps-target-bank_bca")).toBeNull();
    await act(async () => { root.unmount(); });
  });

  test("409 'Angka berubah' lalu muat ulang gagal: kalimat 409 dan galat muat sama-sama tampil", async () => {
    let n = 0;
    mockGet.mockImplementation((url) => {
      if (url.endsWith("/kas-per-rekening/ent_ksc/pratinjau")) {
        n += 1;
        return n <= 2 ? Promise.resolve({ data: PV })
          : Promise.reject({ response: { status: 500, data: { detail: "Database sibuk." } } });
      }
      if (url.endsWith("/kas-per-rekening/usulan")) return Promise.resolve({ data: { items: [USULAN], total: 1 } });
      return Promise.resolve({ data: [] });
    });
    mockPost.mockRejectedValueOnce({ response: { status: 409, data: { detail: "Angka berubah, muat ulang." } } });
    const host = await alat(izinPenuh);
    await click(q(host, "ps-approve-psk_ent_ksc_001"));
    await submit(host, "ps-approve-submit");
    expect(q(host, "ps-approve-form").textContent).toMatch(/Angka berubah, muat ulang\./);
    expect(q(host, "ps-approve-form").textContent).toMatch(/Database sibuk\./);
  });

  test("Siapkan: satu pop-up dengan ringkasan total & PT → POST siapkan {pilihan_akun}", async () => {
    pasangAlat({ usulan: [] });
    mockPost.mockResolvedValue({ data: { ...USULAN } });
    const host = await alat(izinPenuh);
    await click(q(host, "ps-prepare"));
    expect(qa(document.body, ".kn-modal-overlay, .modal-overlay").length).toBe(1);
    expect(q(host, "ps-prepare-summary").textContent).toMatch(/Rp\s?7\.000\.000/);
    await submit(host, "ps-prepare-submit");
    expect(posts("/kas-per-rekening/ent_ksc/siapkan")[0][1]).toEqual({ pilihan_akun: {} });
  });

  test("Setujui: pratinjau dimuat ULANG saat pop-up dibuka dan sidik yang dilihat dikirim", async () => {
    pasangAlat({ urutan: [PV, { ...PV, sidik: "sidik_b", total_dipindah: 7100000 }] });
    mockPost.mockResolvedValue({ data: { ...USULAN, status: "disetujui", journal_number: "JE-77" } });
    const host = await alat(izinPenuh);
    await click(q(host, "ps-approve-psk_ent_ksc_001"));
    expect(gets("/pratinjau")).toHaveLength(2);
    expect(q(host, "ps-approve-total").textContent).toMatch(/7\.100\.000/);
    await submit(host, "ps-approve-submit");
    expect(posts("/usulan/psk_ent_ksc_001/setujui")[0][1]).toEqual({ sidik: "sidik_b", selisih_diperiksa: false });
  });

  test("409 'Angka berubah, muat ulang.': kalimat tampil di pop-up, angka dimuat ulang, sidik baru dikirim berikutnya", async () => {
    pasangAlat({ urutan: [PV, PV, { ...PV, sidik: "sidik_c", total_dipindah: 7200000 }] });
    mockPost.mockRejectedValueOnce({ response: { status: 409, data: { detail: "Angka berubah, muat ulang." } } });
    const host = await alat(izinPenuh);
    await click(q(host, "ps-approve-psk_ent_ksc_001"));
    await submit(host, "ps-approve-submit");
    expect(posts("/setujui")[0][1].sidik).toBe("sidik_a");
    expect(q(host, "ps-approve-form").textContent).toMatch(/Angka berubah, muat ulang\./);
    expect(gets("/pratinjau")).toHaveLength(3);
    expect(q(host, "ps-approve-total").textContent).toMatch(/7\.200\.000/);
    mockPost.mockResolvedValueOnce({ data: { ...USULAN, status: "disetujui" } });
    await submit(host, "ps-approve-submit");
    expect(posts("/setujui")[1][1].sidik).toBe("sidik_c");
  });

  test("selisih (R10): rekening berselisih tampil + kotak centang wajib; dikirim selisih_diperiksa true", async () => {
    const pvSelisih = { ...PV, rekening: [{ ...PV.rekening[0], selisih: 5000 }] };
    pasangAlat({ pv: pvSelisih });
    mockPost.mockResolvedValue({ data: { ...USULAN, status: "disetujui" } });
    const host = await alat(izinPenuh);
    await click(q(host, "ps-approve-psk_ent_ksc_001"));
    expect(q(host, "ps-approve-diff-bank_bca").textContent).toMatch(/BCA Operasional berselisih Rp\s?5\.000/);
    expect(q(host, "ps-approve-submit").disabled).toBe(true);
    await click(q(host, "ps-approve-diff-check"));
    expect(q(host, "ps-approve-submit").disabled).toBe(false);
    await submit(host, "ps-approve-submit");
    expect(posts("/setujui")[0][1]).toEqual({ sidik: "sidik_a", selisih_diperiksa: true });
  });

  test("selisih dijawab server (409 centang) walau pratinjau tanpa selisih: kalimat tampil dan kotak centang muncul", async () => {
    pasangAlat();
    const kalimat = "Rekening BCA Operasional berselisih Rp 5.000 dengan buku kasnya — centang 'sudah diperiksa' untuk melanjutkan.";
    mockPost.mockRejectedValueOnce({ response: { status: 409, data: { detail: kalimat } } });
    const host = await alat(izinPenuh);
    await click(q(host, "ps-approve-psk_ent_ksc_001"));
    expect(q(host, "ps-approve-diff-check")).toBeNull();
    await submit(host, "ps-approve-submit");
    expect(q(host, "ps-approve-form").textContent).toContain(kalimat);
    expect(q(host, "ps-approve-diff-check")).not.toBeNull();
  });

  test("penyiap sendiri: Setujui nonaktif dengan pesan kontrol; Tolak memakai alasan", async () => {
    const pesan = "Pindah saldo kas ke akun per rekening harus diputuskan orang lain: Anda yang mengajukannya.";
    pasangAlat({ usulan: [{ ...USULAN, kontrol: { dua_orang: true, sendiri: true, ditolak: true, pesan } }] });
    mockAskReason.mockResolvedValue("angka belum dicek");
    mockPost.mockResolvedValue({ data: { ...USULAN, status: "ditolak" } });
    const host = await alat(izinPenuh);
    expect(q(host, "ps-approve-psk_ent_ksc_001").disabled).toBe(true);
    expect(q(host, "ps-approve-why-psk_ent_ksc_001").textContent).toBe(pesan);
    expectBungkus(q(host, "ps-approve-why-psk_ent_ksc_001"));
    await click(q(host, "ps-reject-psk_ent_ksc_001"));
    expect(posts("/usulan/psk_ent_ksc_001/tolak")[0][1]).toEqual({ alasan: "angka belum dicek" });
  });
});

// ── Rekening & Saldo · perubahan rekening ────────────────────────────────────────────────────────────────────────────
describe("Rekening & Saldo — akun buku besar per rekening", () => {
  test("kartu: kode + nama sub-akun bila PT aktif; penanda bila PT belum memakai akun per rekening", async () => {
    const aktif = await mount(<AkunBukuBesar a={{ id: "b1", gl_account_code: "1-1100-01", gl_account_name: "BCA Operasional",
      akun_per_rekening_aktif: true }} />);
    expect(q(aktif, "bank-gl-b1").textContent).toBe("Akun buku besar 1-1100-01 · BCA Operasional");
    const belum = await mount(<AkunBukuBesar a={{ id: "b2", gl_account_code: "", akun_per_rekening_aktif: false }} />);
    expect(q(belum, "bank-gl-b2").textContent).toBe("PT belum memakai akun per rekening");
  });

  test("layar: penanda PT + tautan 'Siapkan pindah saldo' hanya untuk accounting.manage", async () => {
    mockGet.mockImplementation((url) => {
      if (url.endsWith("/bank-accounts")) return Promise.resolve({ data: [{ ...REKENING[0], akun_per_rekening_aktif: false }] });
      if (url.endsWith("/bank-account-changes")) return Promise.resolve({ data: { items: [], total: 0 } });
      return Promise.resolve({ data: null });
    });
    let host = await mount(<BankAccountsView selectedEntity="ent_ksc" currentUser={{ role: "finance", permissions: izinPenuh }} />);
    expect(q(host, "bank-gl-bank_bca").textContent).toBe("PT belum memakai akun per rekening");
    expect(q(host, "bank-gl-mode").textContent).toMatch(/PT belum memakai akun per rekening/);
    await click(q(host, "bank-gl-mode-link"));
    expect(mockGo).toHaveBeenCalledWith("kas-per-rekening");
    document.body.innerHTML = "";
    host = await mount(<BankAccountsView selectedEntity="ent_ksc" currentUser={{ role: "finance", permissions: { cash: ["view"] } }} />);
    expect(q(host, "bank-gl-mode-link")).toBeNull();
  });

  test("perubahan rekening menunggu: field akun buku besar berlabel 'Akun buku besar'", async () => {
    mockGet.mockResolvedValue({ data: { total: 1, items: [{ id: "bac1", action: "buat", account_name: "BCA Baru", entity_name: "Sukacita",
      changes: [{ field: "gl_account_code", to: "1-1100-02" }],
      label_changes: [{ field: "gl_account_code", to: "1-1100-02", label: "Akun buku besar" }] }] } });
    const host = await mount(<BankAccountChangesPanel entityParam="ent_ksc" canApprove />);
    expect(q(host, "bank-change-lines-bac1").textContent).toBe("Akun buku besar: 1-1100-02");
  });
});

// ── Transaksi Kas (kas manual) ───────────────────────────────────────────────────────────────────────────────────────
describe("Transaksi Kas — Transfer/Top-up ditutup, kas Pindah Dana bertautan dokumen", () => {
  function pasangKas(items = []) {
    mockGet.mockImplementation((url) => {
      if (url.endsWith("/cash-transactions/summary")) return Promise.resolve({ data: { kas_kecil: {}, kas_besar: {}, kas_kecil_per_entity: {} } });
      if (url.endsWith("/cash-transactions")) return Promise.resolve({ data: { items, total: items.length, page: 1, page_size: 50 } });
      if (url.endsWith("/bank-accounts")) return Promise.resolve({ data: [{ ...REKENING[1], cash_type: "kas_kecil" }] });
      return Promise.resolve({ data: [] });
    });
  }

  test("kategori Transfer/Top-up hilang dari form; petunjuk + tautan 'Pakai Pindah Dana' ke tab baru", async () => {
    // Kas & Bank 2 (Tugas 4, C5) — Pembelian & Gaji juga ditutup untuk kas manual baru (uji lengkap: kb2KasManual.test.js).
    expect(CATEGORIES.map((c) => c.value)).toEqual(["operasional", "modal", "lain"]);
    expect(CATEGORIES.some((c) => /transfer|top-?up/i.test(c.label))).toBe(false);
    pasangKas();
    const host = await mount(<CashManagementView currentUser={{ role: "finance", permissions: { cash: ["view", "create"] } }} selectedEntity="ent_ksc" />);
    await click(q(host, "create-cash-button"));
    const opsi = [...q(host, "cash-category-select").options].map((o) => o.textContent);
    expect(opsi.join("|")).not.toMatch(/Transfer|Top-up/);
    expect(q(host, "cash-fund-transfer-link").textContent).toMatch(/Setor tunai, isi kas kecil, atau pindah antar rekening\?/);
    expect(q(host, "cash-fund-transfer-link").textContent).toMatch(/Catat biaya bank/);
    await click(q(host, "cash-fund-transfer-link").querySelector("button"));
    expect(mockGo).toHaveBeenCalledWith("fund-transfers");
  });

  test("kas ber-ref_type fund_transfer: sumber = tautan pratinjau Pindah Dana, anulir lewat dokumennya", async () => {
    expect(REF_LABEL.fund_transfer).toBe("Pindah Dana");
    expect(CASH_REF_DOC.fund_transfer).toBe("fund_transfer");
    pasangKas([{ id: "cash_1", number: "KSC/CASH-1", ref_type: "fund_transfer", ref_id: "pdn_1", fund_transfer_number: "KSC/PDN-00001",
      direction: "out", amount: 500000, cash_type: "kas_besar", entity_id: "ent_ksc", category: "pindah dana", status: "posted" }]);
    const host = await mount(<CashManagementView currentUser={{ role: "finance", permissions: { cash: ["view", "create", "delete"] } }} selectedEntity="ent_ksc" />);
    expect(q(host, "cash-source-cash_1").textContent).toBe("Pindah Dana KSC/PDN-00001");
    await click(q(host, "cash-source-cash_1"));
    expect(mockPreview).toHaveBeenCalledWith({ docType: "fund_transfer", docId: "pdn_1", number: "KSC/PDN-00001", entityId: "ent_ksc" });
    expect(q(host, "void-cash-cash_1")).toBeNull();
    expect(q(host, "void-cash-note-cash_1").textContent).toBe("Anulir lewat Pindah Dana KSC/PDN-00001");
    expectBungkus(q(host, "void-cash-note-cash_1"));
  });
});

// ── Retur: pratinjau refund ber-rekening ─────────────────────────────────────────────────────────────────────────────
test("pratinjau keputusan retur mengirim rekening refund pilihan (refund_account_id)", async () => {
  mockGet.mockImplementation((url) => {
    if (url.endsWith("/bank-accounts")) return Promise.resolve({ data: [{ ...REKENING[0], cash_type: "kas_besar" }] });
    return Promise.resolve({ data: [] });
  });
  mockPost.mockResolvedValue({ data: { gross_amount: 0, split: [], journal: [], lines: [], blocked: "" } });
  const ret = { id: "sret_9", number: "SRET-9", entity_id: "ent_ksc", return_type: "retur", items: [{ quantity_returned: 1 }], roll_locations: {} };
  await mount(<ReturnSettleModal ret={ret} open onClose={() => {}} onSettle={async () => null} />);
  await flush(450);
  const [url, body] = posts("/settle-preview").at(-1);
  expect(url).toBe("/api/sales-returns/sret_9/settle-preview");
  expect(body).toMatchObject({ outcome: "refund", refund_account_id: "bank_bca" });
});
