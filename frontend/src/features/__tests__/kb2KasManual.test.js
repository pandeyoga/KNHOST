// Kas & Bank bagian 2 (Tugas 4) — layar: kategori kas manual tanpa Pembelian/Gaji (C5); kas keluar di atas batas PT =
// pengajuan (catatan + tombol "Ajukan", 202 → toast + baris "Menunggu persetujuan"); Setujui/Tolak/Batal pengajuan (izin,
// bukan nama peran; nonaktif untuk pengaju dengan kalimat server; satu pop-up per aksi; 409 server apa adanya);
// pratinjau dokumen `cash_out_request`; notifikasi & Pusat Persetujuan membuka pengajuannya.
// Rancangan `docs/superpowers/specs/2026-11-27-kas-bank-2-kas-manual-design.md` §5.1–§5.3.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CashManagementView, { CATEGORIES } from "../purchasing/CashManagementView";
import { PESAN_SEDANG_DIPROSES, aksiPengajuan, butuhPersetujuan, bacaBatas } from "../finance/cashout/cashOutShared";
import CashOutRequestPreview from "../documents/preview/bodies/CashOutRequestPreview";
import { canPreview, previewFor } from "../documents/preview/docPreviewRegistry";
import { notifDocTarget } from "../notifications/notifDocTarget";
import { QUEUE_DOC_TYPE, queueLink } from "../approvals/inboxTabs";
import ApprovalInbox from "../approvals/ApprovalInbox";
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
const mockOpenDocument = jest.fn();
jest.mock("../../context/AppNavContext", () => ({
  __esModule: true,
  useAppNav: () => ({ go: mockGo, canOpen: () => true, openDocument: mockOpenDocument, previewsEnabled: true,
    openDocPreview: mockPreview, closeDocPreview: () => {} }),
}));
jest.mock("../../utils/feedback", () => ({ __esModule: true, notifySuccess: jest.fn(), notifyError: jest.fn(),
  notifyInfo: jest.fn(), notifyWarning: jest.fn() }));
jest.mock("../../hooks/useViewPreset", () => ({ __esModule: true, default: () => null, useViewPreset: () => null }));
jest.mock("../approvals/MyApprovalsPanel", () => () => null);

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const txt = (el) => String(el?.textContent || "").replace(/ /g, " ");
async function flush(ms = 0) {
  for (let i = 0; i < 4; i += 1) {
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
const posts = (akhiran) => mockPost.mock.calls.filter(([u]) => String(u).endsWith(akhiran));
const gets = (akhiran) => mockGet.mock.calls.filter(([u]) => String(u).endsWith(akhiran));

// Tiap layar dirender tanpa galat/peringatan React di konsol.
let galatKonsol;
beforeEach(() => { galatKonsol = jest.spyOn(console, "error").mockImplementation(() => {}); });
afterEach(() => {
  const panggilan = galatKonsol.mock.calls.map((c) => String(c[0]).slice(0, 200));
  galatKonsol.mockRestore();
  mockGet.mockReset(); mockPost.mockReset(); mockAskConfirm.mockReset(); mockAskReason.mockReset(); mockGo.mockReset();
  mockPreview.mockReset(); mockOpenDocument.mockReset(); notifySuccess.mockReset(); document.body.innerHTML = "";
  expect(panggilan).toEqual([]);
});

// Kalimat server (`cash_out_request_service`) — dikirim di `kontrol`, ditampilkan apa adanya.
const PESAN_ORANG_KEDUA = "Kas keluar manual ini harus disetujui orang lain: Anda yang mengajukannya. Minta orang lain yang "
  + "berizin menyetujui kas. Admin dapat menaikkan batas atau mengubah aturan ini di Pengaturan › Persetujuan › Kontrol dua orang.";
const PESAN_TOLAK_SENDIRI = "Pengajuan ini Anda ajukan sendiri, jadi tidak bisa Anda tolak. Pakai Batal bila tidak jadi.";
const AKU = { id: "usr_aju", name: "Rina Pengaju" };
const REKAN = { id: "usr_setuju", name: "Dodi Penyetuju" };
const PKK = (lain = {}) => ({
  id: "pkk_1", number: "KSC/PKK-00001", entity_id: "ent_ksc", status: "menunggu_persetujuan", status_label: "Menunggu persetujuan",
  cash_type: "kas_besar", direction: "out", amount: 3500000, category: "operasional", description: "Sewa tenda acara",
  account_id: "bank_bca", account_name: "BCA Operasional", txn_date: "2026-11-27T03:00:00+00:00", pengaju: AKU,
  created_by: AKU.name, cash_id: "", cash_number: "", terbit_error: "", dalam_proses: false,
  created_at: "2026-11-27T03:00:00+00:00",
  kontrol: { dua_orang: true, sendiri: false, admin_sendiri: false, ditolak: false, pesan: "", tolak_pesan: "" },
  jejak: [{ aksi: "ajukan", oleh: AKU.name, oleh_id: AKU.id, pada: "2026-11-27T03:00:00+00:00", catatan: "menunggu persetujuan orang kedua" }],
  ...lain,
});
const SENDIRI = { dua_orang: true, sendiri: true, admin_sendiri: false, ditolak: true, pesan: PESAN_ORANG_KEDUA,
  tolak_pesan: PESAN_TOLAK_SENDIRI };
const REKENING = [{ id: "bank_bca", name: "BCA Operasional", entity_id: "ent_ksc", account_type: "bank", cash_type: "kas_besar",
  is_active: true }];

/** GET palsu: ringkasan & daftar kas kosong (kecuali `kas`), rekening satu, batas PT, daftar pengajuan menunggu. */
function pasang({ menunggu = [], kas = [], batas = { entity_id: "ent_ksc", min_orang: "1", batas_nominal: 1000000, semua: false } } = {}) {
  const state = { menunggu };
  mockGet.mockImplementation((url) => {
    if (url.endsWith("/cash-transactions/summary")) return Promise.resolve({ data: { kas_kecil: {}, kas_besar: {}, kas_kecil_per_entity: {} } });
    if (url.endsWith("/cash-transactions")) return Promise.resolve({ data: { items: kas, total: kas.length, page: 1, page_size: 50 } });
    if (url.endsWith("/bank-accounts")) return Promise.resolve({ data: REKENING });
    if (url.endsWith("/entities")) return Promise.resolve({ data: [{ id: "ent_ksc", short_name: "Sukacita" }] });
    if (url.endsWith("/cash-out-requests/batas")) return Promise.resolve({ data: batas });
    if (url.endsWith("/cash-out-requests")) {
      const items = state.menunggu;
      return Promise.resolve({ data: { items, total: items.length, page: 1, page_size: 10, has_more: false } });
    }
    return Promise.resolve({ data: [] });
  });
  return state;
}
const layar = (perms, user = AKU, entity = "ent_ksc") => mount(
  <CashManagementView currentUser={{ ...user, role: "finance", permissions: perms }} selectedEntity={entity} />);
const IZIN_AJU = { cash: ["view", "create"], budget: [] };
const IZIN_SETUJU = { cash: ["view", "approve"] };

// ── 1. Kategori (C5) ─────────────────────────────────────────────────────────────────────────────────────────────────
describe("kategori kas manual", () => {
  test("form tanpa Pembelian & Gaji; label lama tetap untuk kas lama", async () => {
    expect(CATEGORIES.map((c) => c.value)).toEqual(["operasional", "modal", "lain"]);
    pasang({ kas: [
      { id: "c_beli", number: "KSC/CASH-1", category: "pembelian", direction: "out", amount: 10000, cash_type: "kas_besar",
        entity_id: "ent_ksc", ref_type: "manual", status: "posted" },
      { id: "c_gaji", number: "KSC/CASH-2", category: "gaji", direction: "out", amount: 20000, cash_type: "kas_besar",
        entity_id: "ent_ksc", ref_type: "manual", status: "posted" }] });
    const host = await layar(IZIN_AJU);
    expect(txt(q(host, "cash-row-c_beli"))).toMatch(/Pembelian/);
    expect(txt(q(host, "cash-row-c_gaji"))).toMatch(/Gaji \/ Upah/);
    await click(q(host, "create-cash-button"));
    const opsi = [...q(host, "cash-category-select").options].map((o) => o.textContent);
    expect(opsi).toEqual(["-", "Operasional", "Setoran Modal", "Lain-lain"]);
  });
});

// ── 2. Form: catatan + "Ajukan" di atas batas PT ─────────────────────────────────────────────────────────────────────
describe("form Catat Transaksi — kas keluar di atas batas", () => {
  test("di atas batas: catatan 'Di atas Rp 1.000.000 …' dan tombol Ajukan; sama dengan batas / kas masuk: Catat Transaksi", async () => {
    pasang();
    const host = await layar(IZIN_AJU);
    await click(q(host, "create-cash-button"));
    expect(gets("/cash-out-requests/batas").at(-1)[1]).toEqual({ params: { entity_id: "ent_ksc" } });
    await type(q(host, "cash-amount-input"), "1000000");
    expect(q(host, "cash-approval-note")).toBeNull();
    expect(txt(q(host, "submit-cash-button"))).toMatch(/Catat Transaksi/);
    await type(q(host, "cash-amount-input"), "1000001");
    expect(txt(q(host, "cash-approval-note"))).toBe("Di atas Rp 1.000.000 — akan diajukan untuk disetujui orang kedua.");
    expect(txt(q(host, "submit-cash-button"))).toMatch(/Ajukan/);
    await choose(q(host, "cash-direction-select"), "in");
    expect(q(host, "cash-approval-note")).toBeNull();
    expect(txt(q(host, "submit-cash-button"))).toMatch(/Catat Transaksi/);
  });

  test("min_orang 2: setiap kas keluar diajukan", async () => {
    pasang({ batas: { entity_id: "ent_ksc", min_orang: "2", batas_nominal: 1000000, semua: true } });
    const host = await layar(IZIN_AJU);
    await click(q(host, "create-cash-button"));
    await type(q(host, "cash-amount-input"), "10000");
    expect(txt(q(host, "cash-approval-note"))).toBe("Semua kas keluar manual PT ini diajukan untuk disetujui orang kedua.");
    expect(txt(q(host, "submit-cash-button"))).toMatch(/Ajukan/);
  });

  test("aturan murni: hanya kas keluar; batas 0 tidak dipakai; jawaban bukan batas → tanpa catatan", () => {
    const b = bacaBatas({ min_orang: "1", batas_nominal: 0 });
    expect(butuhPersetujuan(b, { direction: "out", amount: "99999999" }).butuh).toBe(false);
    expect(bacaBatas([])).toBeNull();
    expect(butuhPersetujuan(null, { direction: "out", amount: "5000000" })).toEqual({ butuh: false, catatan: "" });
  });

  test("202 → toast 'Diajukan … menunggu persetujuan', form tertutup, baris muncul di Menunggu persetujuan (tanpa kas)", async () => {
    const state = pasang();
    const host = await layar(IZIN_AJU);
    expect(q(host, "cash-out-pending")).toBeNull();               // tidak ada yang menunggu → bagian tidak digambar
    await click(q(host, "create-cash-button"));
    await choose(q(host, "cash-type-select"), "kas_besar");     // rekening BCA (kas besar) terisi otomatis
    await type(q(host, "cash-amount-input"), "3500000");
    await type(q(host, "cash-description-input"), "Sewa tenda acara");
    const req = PKK({ kontrol: SENDIRI });
    mockPost.mockImplementation(async () => { state.menunggu = [req]; return { status: 202, data: { request: req } }; });
    const daftarSebelum = gets("/cash-transactions").length;
    await submit(host, "submit-cash-button");
    const [url, body, cfg] = posts("/cash-transactions").at(-1);
    expect(url).toBe("/api/cash-transactions");
    expect(body).toMatchObject({ direction: "out", amount: 3500000, category: "operasional", account_id: "bank_bca" });
    expect(cfg.headers["Idempotency-Key"]).toMatch(/^kas-/);
    expect(notifySuccess).toHaveBeenCalledTimes(1);
    expect(txt({ textContent: notifySuccess.mock.calls[0][0] })).toBe(
      "Diajukan KSC/PKK-00001 (Rp 3.500.000) — menunggu persetujuan orang kedua. Kas keluar baru tercatat sesudah disetujui.");
    expect(q(host, "cash-form")).toBeNull();
    expect(q(host, "cash-notice")).toBeNull();                    // bukan "Transaksi … dicatat"
    expect(q(host, "cash-out-row-pkk_1")).not.toBeNull();
    expect(txt(q(host, "cash-out-pending-count"))).toBe("1");
    expect(gets("/cash-transactions").length).toBe(daftarSebelum); // daftar kas tidak berubah: belum ada kas
  });

  test("202 dengan peringatan anggaran (mode Peringatkan): peringatan tampil di bilah pemberitahuan (§7.8.4)", async () => {
    const state = pasang();
    const host = await layar(IZIN_AJU);
    await click(q(host, "create-cash-button"));
    await choose(q(host, "cash-type-select"), "kas_besar");
    await type(q(host, "cash-amount-input"), "3500000");
    await type(q(host, "cash-description-input"), "Sewa tenda acara");
    const req = PKK({ kontrol: SENDIRI, budget_check: { mode: "warn", warnings: ["Beban Operasional Lainnya terpakai 92% dari pagu."] } });
    mockPost.mockImplementation(async () => { state.menunggu = [req]; return { status: 202, data: { request: req } }; });
    await submit(host, "submit-cash-button");
    expect(notifySuccess).toHaveBeenCalledTimes(1);
    expect(txt(q(host, "cash-notice"))).toBe("Pengajuan KSC/PKK-00001 menunggu persetujuan orang kedua. "
      + "Peringatan anggaran: Beban Operasional Lainnya terpakai 92% dari pagu.");
    expect(q(host, "cash-out-row-pkk_1")).not.toBeNull();
  });
});

// ── 3. Bagian "Menunggu persetujuan" ─────────────────────────────────────────────────────────────────────────────────
describe("Menunggu persetujuan", () => {
  test("kolom nomor, tanggal, rekening, kategori, nominal, pengaju; nomor PKK membuka pratinjau", async () => {
    pasang({ menunggu: [PKK()] });
    const host = await layar(IZIN_SETUJU, REKAN);
    expect(txt(q(host, "cash-out-pending-title"))).toBe("Menunggu persetujuan");
    expect(gets("/cash-out-requests").at(-1)[1].params).toMatchObject({ status: "menunggu_persetujuan", entity_id: "ent_ksc" });
    expect(txt(q(host, "cash-out-date-pkk_1"))).toBe("27 Nov 2026");
    expect(txt(q(host, "cash-out-account-pkk_1"))).toBe("BCA Operasional");
    expect(txt(q(host, "cash-out-category-pkk_1"))).toBe("Operasional");
    expect(txt(q(host, "cash-out-amount-pkk_1"))).toBe("−Rp 3.500.000");
    expect(txt(q(host, "cash-out-requester-pkk_1"))).toBe("Rina Pengaju");
    await click(q(host, "cash-out-open-pkk_1"));
    expect(mockPreview).toHaveBeenCalledWith({ docType: "cash_out_request", docId: "pkk_1", number: "KSC/PKK-00001",
      entityId: "ent_ksc" });
  });

  test("tanpa cash.approve: Setujui & Tolak tidak ditawarkan; pengaju tetap bisa Batal; pemegang cash.delete juga", async () => {
    pasang({ menunggu: [PKK({ kontrol: { ...SENDIRI, ditolak: false } })] });
    let host = await layar(IZIN_AJU);
    expect(q(host, "cash-out-approve-pkk_1")).toBeNull();
    expect(q(host, "cash-out-reject-pkk_1")).toBeNull();
    expect(q(host, "cash-out-cancel-pkk_1").disabled).toBe(false);
    document.body.innerHTML = "";
    // orang lain: tanpa cash.delete tidak ada Batal; dengan cash.delete ada
    pasang({ menunggu: [PKK()] });
    host = await layar({ cash: ["view", "create"] }, REKAN);
    expect(q(host, "cash-out-actions-pkk_1")).toBeNull();
    document.body.innerHTML = "";
    pasang({ menunggu: [PKK()] });
    host = await layar({ cash: ["view", "delete"] }, REKAN);
    expect(q(host, "cash-out-cancel-pkk_1").disabled).toBe(false);
    expect(q(host, "cash-out-approve-pkk_1")).toBeNull();
  });

  test("pengaju pemegang cash.approve: Setujui & Tolak nonaktif dengan kalimat server; Batal aktif", async () => {
    pasang({ menunggu: [PKK({ kontrol: SENDIRI })] });
    const host = await layar({ cash: ["view", "create", "approve"] });
    expect(q(host, "cash-out-approve-pkk_1").disabled).toBe(true);
    expect(q(host, "cash-out-reject-pkk_1").disabled).toBe(true);
    expect(q(host, "cash-out-reject-pkk_1").getAttribute("title")).toBe(PESAN_TOLAK_SENDIRI);
    expect(txt(q(host, "cash-out-action-note-pkk_1"))).toBe(PESAN_ORANG_KEDUA);
    expect(q(host, "cash-out-cancel-pkk_1").disabled).toBe(false);
    // Admin pengaju yang diizinkan memutus sendiri (bukan di daftar admin-tetap): Setujui aktif, Tolak tetap nonaktif.
    const a = aksiPengajuan(PKK({ kontrol: { ...SENDIRI, ditolak: false, admin_sendiri: true, pesan: "" } }),
      { cash: ["approve"] }, AKU);
    expect(a.setujui.alasan).toBe("");
    expect(a.tolak.alasan).toBe(PESAN_TOLAK_SENDIRI);
  });

  test("Setujui: SATU pop-up konfirmasi (nominal & PT) → approve berkunci; toast; kas & daftar dimuat ulang", async () => {
    const state = pasang({ menunggu: [PKK()] });
    const host = await layar(IZIN_SETUJU, REKAN);
    mockAskConfirm.mockResolvedValue(true);
    mockPost.mockImplementation(async () => {
      state.menunggu = [];
      return { data: { ...PKK(), status: "disetujui", cash_id: "cash_9", cash_number: "KSC/CASH-00009" } };
    });
    const kasSebelum = gets("/cash-transactions/summary").length;
    await click(q(host, "cash-out-approve-pkk_1"));
    expect(mockAskConfirm).toHaveBeenCalledTimes(1);
    expect(mockAskReason).not.toHaveBeenCalled();
    const opsi = mockAskConfirm.mock.calls[0][0];
    expect(opsi.title).toBe("Setujui kas keluar KSC/PKK-00001?");
    expect(txt({ textContent: opsi.message })).toMatch(/^Rp 3\.500\.000 keluar dari BCA Operasional \(Sukacita\) — Operasional · Sewa tenda acara\./);
    const [url, body, cfg] = posts("/approve").at(-1);
    expect(url).toBe("/api/cash-out-requests/pkk_1/approve");
    expect(body).toEqual({});
    expect(cfg.headers["Idempotency-Key"]).toMatch(/^pkk-/);
    expect(notifySuccess).toHaveBeenCalledWith("Kas keluar KSC/PKK-00001 disetujui — kas KSC/CASH-00009 tercatat.");
    expect(gets("/cash-transactions/summary").length).toBeGreaterThan(kasSebelum);
    expect(q(host, "cash-out-pending")).toBeNull();               // tidak ada lagi yang menunggu
  });

  test("Setujui: peringatan anggaran saat diajukan di konfirmasi, hasil periksa ulang saat disetujui di toast", async () => {
    const aju = { mode: "warn", warnings: ["Beban Operasional Lainnya terpakai 92% dari pagu."] };
    const setuju = { mode: "warn", warnings: ["Beban Operasional Lainnya melewati pagu Rp 500.000."] };
    const state = pasang({ menunggu: [PKK({ budget_check: aju })] });
    const host = await layar(IZIN_SETUJU, REKAN);
    mockAskConfirm.mockResolvedValue(true);
    mockPost.mockImplementation(async () => {
      state.menunggu = [];
      return { data: { ...PKK(), status: "disetujui", cash_id: "cash_9", cash_number: "KSC/CASH-00009", budget_check_setuju: setuju } };
    });
    await click(q(host, "cash-out-approve-pkk_1"));
    expect(txt({ textContent: mockAskConfirm.mock.calls[0][0].message })).toMatch(
      / saldo kas berkurang\. Peringatan anggaran saat diajukan: Beban Operasional Lainnya terpakai 92% dari pagu\.$/);
    expect(notifySuccess).toHaveBeenCalledWith("Kas keluar KSC/PKK-00001 disetujui — kas KSC/CASH-00009 tercatat. "
      + "Peringatan anggaran: Beban Operasional Lainnya melewati pagu Rp 500.000.");
  });

  test("sedang diproses (kunci saga): Setujui/Tolak/Batal nonaktif dengan kalimat yang menunjuk Kunci Saga", async () => {
    expect(PESAN_SEDANG_DIPROSES).toBe("Sedang diproses — muat ulang sebentar lagi. Bila beberapa menit kemudian masih "
      + "tertahan, minta admin melepas kuncinya di Pengaturan › Kunci Saga.");
    const a = aksiPengajuan(PKK({ dalam_proses: true }), { cash: ["view", "approve", "delete"] }, REKAN);
    expect([a.setujui.alasan, a.tolak.alasan, a.batal.alasan]).toEqual(Array(3).fill(PESAN_SEDANG_DIPROSES));
    pasang({ menunggu: [PKK({ dalam_proses: true })] });
    const host = await layar({ cash: ["view", "approve", "delete"] }, REKAN);
    expect(q(host, "cash-out-approve-pkk_1").disabled).toBe(true);
    expect(q(host, "cash-out-reject-pkk_1").disabled).toBe(true);
    expect(q(host, "cash-out-cancel-pkk_1").disabled).toBe(true);
    expect(txt(q(host, "cash-out-action-note-pkk_1"))).toBe(PESAN_SEDANG_DIPROSES);
  });

  test("Tolak: alasan wajib (askReason ≥ 5 huruf) → reject {alasan}; pop-up dibatalkan → tidak ada kiriman", async () => {
    pasang({ menunggu: [PKK()] });
    const host = await layar(IZIN_SETUJU, REKAN);
    mockAskReason.mockResolvedValueOnce(null);
    await click(q(host, "cash-out-reject-pkk_1"));
    expect(mockAskReason).toHaveBeenCalledTimes(1);
    expect(mockAskReason.mock.calls[0][0]).toMatchObject({ reasonRequired: true, reasonMinLength: 5, confirmLabel: "Tolak" });
    expect(mockPost).not.toHaveBeenCalled();
    mockAskReason.mockResolvedValueOnce("bukan biaya kantor");
    mockPost.mockResolvedValue({ data: { ...PKK(), status: "ditolak" } });
    await click(q(host, "cash-out-reject-pkk_1"));
    expect(mockAskReason).toHaveBeenCalledTimes(2);
    expect(mockAskConfirm).not.toHaveBeenCalled();
    const [url, body] = posts("/reject").at(-1);
    expect(url).toBe("/api/cash-out-requests/pkk_1/reject");
    expect(body).toEqual({ alasan: "bukan biaya kantor" });
    expect(notifySuccess).toHaveBeenCalledWith("Pengajuan KSC/PKK-00001 ditolak.");
  });

  test("Batal (pengaju): satu pop-up alasan → cancel {alasan}", async () => {
    pasang({ menunggu: [PKK({ kontrol: SENDIRI })] });
    const host = await layar(IZIN_AJU);
    mockAskReason.mockResolvedValueOnce("tidak jadi sewa");
    mockPost.mockResolvedValue({ data: { ...PKK(), status: "dibatalkan" } });
    await click(q(host, "cash-out-cancel-pkk_1"));
    expect(mockAskReason).toHaveBeenCalledTimes(1);
    expect(mockAskReason.mock.calls[0][0]).toMatchObject({ confirmLabel: "Batalkan", cancelLabel: "Tutup" });   // bukan "Batal" ganda
    expect(mockAskConfirm).not.toHaveBeenCalled();
    expect(posts("/cancel").at(-1).slice(0, 2)).toEqual(["/api/cash-out-requests/pkk_1/cancel", { alasan: "tidak jadi sewa" }]);
  });

  test.each([
    ["anggaran", "Anggaran terlampaui: Beban Operasional Lainnya sisa Rp 0. Pengajuan KSC/PKK-00001 tetap menunggu."],
    ["periode", "Periode November 2026 sudah ditutup. Pengajuan KSC/PKK-00001 tetap menunggu — batalkan lalu ajukan ulang dengan tanggal di periode yang terbuka."],
    ["sudah diputus", "Pengajuan kas keluar KSC/PKK-00001 sudah ditolak, jadi tidak bisa disetujui."],
  ])("409 %s: kalimat server tampil apa adanya di bagian ini", async (_jenis, kalimat) => {
    pasang({ menunggu: [PKK()] });
    const host = await layar(IZIN_SETUJU, REKAN);
    mockAskConfirm.mockResolvedValue(true);
    mockPost.mockRejectedValue({ response: { status: 409, data: { detail: kalimat } } });
    await click(q(host, "cash-out-approve-pkk_1"));
    expect(txt(q(host, "cash-out-error"))).toContain(kalimat);
    expect(notifySuccess).not.toHaveBeenCalled();
  });

  test("kas yang terbit dari pengajuan: sumber = nomor PKK (pratinjau), tetap bisa dianulir di sini", async () => {
    pasang({ kas: [{ id: "cash_9", number: "KSC/CASH-00009", ref_type: "manual", ref_id: "pkk_1",
      cash_out_request_number: "KSC/PKK-00001", direction: "out", amount: 3500000, cash_type: "kas_besar", entity_id: "ent_ksc",
      category: "operasional", status: "posted" }] });
    const host = await layar({ cash: ["view", "delete"] }, REKAN);
    expect(txt(q(host, "cash-source-row-cash_9"))).toBe("Dari pengajuan KSC/PKK-00001");
    await click(q(host, "cash-request-cash_9"));
    expect(mockPreview).toHaveBeenCalledWith({ docType: "cash_out_request", docId: "pkk_1", number: "KSC/PKK-00001",
      entityId: "ent_ksc" });
    expect(q(host, "void-cash-cash_9")).not.toBeNull();
  });

  test("fokus dokumen cash_out_request (notifikasi / Jejak) → pratinjau pengajuan", async () => {
    pasang();
    const onClear = jest.fn();
    await mount(<CashManagementView currentUser={{ ...REKAN, role: "finance", permissions: IZIN_SETUJU }} selectedEntity="ent_ksc"
      focusDoc={{ focus_type: "cash_out_request", focus_id: "pkk_7", number: "KSC/PKK-00007", nonce: 1 }} onClearFocus={onClear} />);
    expect(mockPreview).toHaveBeenCalledWith({ docType: "cash_out_request", docId: "pkk_7", number: "KSC/PKK-00007" });
    expect(onClear).toHaveBeenCalled();
  });
});

// ── 4. Pratinjau dokumen ─────────────────────────────────────────────────────────────────────────────────────────────
describe("pratinjau cash_out_request", () => {
  test("registri: label, izin cash.view, pemuat /cash-out-requests/{id}, layar penuh per status", async () => {
    const e = previewFor("cash_out_request");
    expect(e.label).toBe("Pengajuan kas keluar");
    expect(canPreview({ cash: ["view"] }, "cash_out_request")).toBe(true);
    expect(canPreview({ accounting: ["view"] }, "cash_out_request")).toBe(false);
    mockGet.mockResolvedValue({ data: PKK() });
    expect((await e.load("pkk_1")).number).toBe("KSC/PKK-00001");
    expect(mockGet).toHaveBeenCalledWith("/api/cash-out-requests/pkk_1");
    expect(e.full(PKK())).toEqual({ view: "cash-management", nav_id: "cash-bank",
      preset: { status: "menunggu_persetujuan", sorot: "pkk_1" } });
    expect(e.full(PKK({ status: "disetujui", cash_id: "cash_9", cash_number: "KSC/CASH-00009" }))).toEqual({
      view: "cash-management", nav_id: "cash-bank", focus_type: "cash_transaction", focus_id: "cash_9", number: "KSC/CASH-00009" });
    expect(e.full(PKK({ status: "ditolak" }))).toBeNull();
  });

  test("isi: fakta, status, kas yang terbit (jurnal), alasan tolak, riwayat", async () => {
    const doc = PKK({ status: "disetujui", disetujui_oleh: REKAN.name, disetujui_pada: "2026-11-27T05:00:00+00:00",
      cash_id: "cash_9", cash_number: "KSC/CASH-00009",
      kas: { id: "cash_9", number: "KSC/CASH-00009", txn_date: "2026-11-27T03:00:00+00:00", amount: 3500000, status: "posted",
        gl_status: "posted", journal_number: "KSC/JE-00012", journal_entry_id: "je_12" },
      jejak: [PKK().jejak[0], { aksi: "setujui", oleh: REKAN.name, pada: "2026-11-27T05:00:00+00:00", catatan: "kas KSC/CASH-00009" }] });
    const host = await mount(<CashOutRequestPreview doc={doc} push={() => {}} canPush={() => false} currentUser={{ permissions: {} }} />);
    expect(txt(q(host, "doc-preview-status"))).toBe("Disetujui");
    expect(txt(q(host, "doc-preview-cor-facts"))).toMatch(/Rekening\s*BCA Operasional/);
    expect(txt(q(host, "doc-preview-cor-facts"))).toMatch(/Pengaju\s*Rina Pengaju/);
    expect(txt(q(host, "doc-preview-cor-facts"))).toMatch(/Disetujui\s*Dodi Penyetuju/);
    expect(txt(q(host, "doc-preview-cor-cash"))).toMatch(/KSC\/CASH-00009/);
    expect(txt(q(host, "doc-preview-cor-cash"))).toMatch(/JurnalKSC\/JE-00012/);   // label "Jurnal" (bukan "Keterangan" kedua)
    expect(txt(q(host, "doc-preview-cor-cash"))).not.toMatch(/Keterangan/);
    await click(q(host, "doc-preview-cor-journal"));   // nomor jurnal = tautan ke Buku Besar
    expect(mockOpenDocument).toHaveBeenCalledWith({ view: "general-ledger", focus_type: "journal_entry", focus_id: "je_12" });
    expect(txt(q(host, "doc-preview-totals"))).toMatch(/Nominal kas keluar\s*Rp 3\.500\.000/);
    expect(txt(q(host, "doc-preview-cor-history"))).toMatch(/Diajukan · Rina Pengaju/);
    expect(txt(q(host, "doc-preview-cor-history"))).toMatch(/Disetujui · Dodi Penyetuju · .* — kas KSC\/CASH-00009/);
    document.body.innerHTML = "";
    const tolak = await mount(<CashOutRequestPreview doc={PKK({ status: "ditolak", ditolak_oleh: REKAN.name,
      alasan_tolak: "bukan biaya kantor", kas: null })} push={() => {}} canPush={() => false} currentUser={{ permissions: {} }} />);
    expect(txt(q(tolak, "doc-preview-cor-facts"))).toMatch(/Alasan tolak\s*bukan biaya kantor/);
    expect(txt(q(tolak, "doc-preview-cor-cash-empty"))).toBe("Tidak ada kas yang tercatat.");
  });
});

// ── 5. Notifikasi & Pusat Persetujuan ────────────────────────────────────────────────────────────────────────────────
describe("notifikasi & Pusat Persetujuan membuka pengajuan", () => {
  test("notifDocTarget: kas_keluar_* ber-doc → Transaksi Kas fokus pengajuan; tanpa doc → id dari ref", () => {
    const doc = { ref_type: "cash_out_request", ref_id: "pkk_1", number: "KSC/PKK-00001", label: "Pengajuan kas keluar KSC/PKK-00001" };
    expect(notifDocTarget({ type: "kas_keluar_diajukan", link: "/?view=cash-management", ref: "pkk_1#usr_setuju", doc }))
      .toEqual({ link: expect.objectContaining({ view: "cash-management", nav_id: "cash-bank", focus_type: "cash_out_request",
        focus_id: "pkk_1", number: "KSC/PKK-00001" }) });
    expect(notifDocTarget({ type: "kas_keluar_diputus", link: "/?view=cash-management", ref: "pkk_2:ditolak#usr_aju" }))
      .toEqual({ link: expect.objectContaining({ view: "cash-management", focus_type: "cash_out_request", focus_id: "pkk_2" }) });
    expect(notifDocTarget({ type: "lain", link: "/?view=cash-management", ref: "pkk_3" })).toBeNull();
  });

  test("antrean Kas keluar manual menunggu: chip/baris membuka Transaksi Kas dengan preset; nomor PKK = pratinjau", async () => {
    expect(QUEUE_DOC_TYPE.cash_out_request).toBe("cash_out_request");
    const PRESET = { status: "menunggu_persetujuan" };
    expect(queueLink({ key: "cash_out_request", view: "cash-management", preset: PRESET })).toEqual({ view: "cash-management",
      preset: PRESET });
    mockGet.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/approvals/backlog") ? {
      total: 1, items: [{ key: "cash_out_request", label: "Kas keluar manual menunggu", view: "cash-management", count: 1, preset: PRESET }],
      all_items: [{ key: "cash_out_request", count: 1 }],
      oldest: [{ key: "cash_out_request", id: "pkk_1", number: "KSC/PKK-00001", title: "Sewa tenda acara", entity_id: "ent_ksc",
        queue_label: "Kas keluar manual menunggu", view: "cash-management", days_waiting: 0, preset: PRESET }],
    } : [] }));
    const onNavigate = jest.fn();
    const host = await mount(<ApprovalInbox currentUser={{ role: "manager", permissions: { approval: ["view"], cash: ["view"] } }}
      onNavigate={onNavigate} />);
    await click(q(host, "approval-inbox-backlog-cash_out_request"));
    expect(onNavigate.mock.calls.at(-1)[1]).toBe("cash-management");
    expect(onNavigate.mock.calls.at(-1)[3]).toEqual({ preset: PRESET });
    await click(q(host, "approval-inbox-other-doc-pkk_1"));
    expect(mockPreview).toHaveBeenCalledWith({ docType: "cash_out_request", docId: "pkk_1", number: "KSC/PKK-00001",
      entityId: "ent_ksc" });
    await click(q(host, "approval-inbox-other-open-pkk_1"));
    expect(onNavigate.mock.calls.at(-1)[3]).toEqual({ preset: PRESET });
  });
});
