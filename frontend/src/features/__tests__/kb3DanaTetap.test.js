// Kas & Bank bagian 3 (Tugas 4a) — layar rekening berjenis kas & dana tetap kas kecil. Rancangan
// `docs/superpowers/specs/2026-11-28-kas-bank-3-kasir-dana-tetap-opname-design.md` §5.1, §5.2, §5.4, §7.
//  · Form rekening baru tunai memilih jenis kas (Kas Kasir / Kas Kecil); jenis terkunci berkalimat server bila rekening
//    sudah punya kas; dana tetap (kas kecil) & lokasi (kas kasir / kas kecil) ikut dikirim; ubah = hanya yang berubah.
//  · Perubahan rekening menunggu: bidang mentah berlabel (jenis kas, dana tetap Rp, nama lokasi).
//  · Kartu rekening: jenis kas, dana tetap, lokasi, aksi "Isi ulang" (izin `cash.create`, kas kecil berdana tetap).
//  · Pop-up Isi ulang: nominal hanya-baca dari server, pilih rekening sumber, tanpa `nominal` di kiriman, alasan server
//    menonaktifkan tombol (isi ulang terbuka menghalangi yang kedua).
//  · Kas Kecil › Dana tetap: posisi per rekening, rincian, riwayat Pindah Dana isi ulang → pratinjau PDN; izin
//    menyembunyikan tab & aksi.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import BankAccountForm from "../finance/BankAccountForm";
import BankAccountChangesPanel from "../finance/BankAccountChangesPanel";
import BankAccountsView from "../finance/BankAccountsView";
import PettyCashView from "../pettycash/PettyCashView";
import IsiUlangModal from "../pettycash/IsiUlangModal";
import FundTransferPreview from "../documents/preview/bodies/FundTransferPreview";
import { alasanJenisKasTerkunci, bolehIsiUlang, jenisKasRekening, labelJenisKas } from "../finance/jenisKas";
import { ViewPresetProvider } from "../../context/ViewPresetContext";
import { notifySuccess } from "../../utils/feedback";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockPatch = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: (...a) => mockPatch(...a),
    put: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
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
// `useSites` menyimpan daftar lokasi di cache modul (sekali per sesi halaman); uji butuh jawaban per kasus → pengganti
// tanpa cache dengan kontrak yang sama (GET /warehouse-sites → `sites`, gagal → []).
jest.mock("../../components/SiteSelect", () => {
  const R = jest.requireActual("react");
  const client = jest.requireMock("../../services/apiClient");
  return {
    __esModule: true,
    default: () => null,
    useSites: () => {
      const [sites, setSites] = R.useState([]);
      R.useEffect(() => {
        let live = true;
        client.default.get(`${client.API}/warehouse-sites`).then((r) => { if (live) setSites(r.data?.sites || []); }).catch(() => {});
        return () => { live = false; };
      }, []);
      return sites;
    },
  };
});
const mockGo = jest.fn();
const mockPreview = jest.fn();
jest.mock("../../context/AppNavContext", () => ({
  __esModule: true,
  useAppNav: () => ({ go: mockGo, canOpen: () => true, openDocument: () => {}, previewsEnabled: true,
    openDocPreview: mockPreview }),
}));
jest.mock("../../utils/feedback", () => ({ __esModule: true, notifySuccess: jest.fn(), notifyError: jest.fn(),
  notifyInfo: jest.fn(), notifyWarning: jest.fn() }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const rp = (n) => new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(n)
  .replace(/\u00a0/g, " ");
const teks = (el) => (el ? el.textContent.replace(/\u00a0/g, " ") : null);
async function flush() {
  for (let i = 0; i < 4; i += 1) {
    await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  }
}
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
function routeGet(map) {
  mockGet.mockImplementation((url, cfg) => {
    const key = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => String(url).includes(k));
    if (!key) return Promise.resolve({ data: [] });
    const v = map[key];
    if (v instanceof Error) return Promise.reject(v);
    return Promise.resolve({ data: typeof v === "function" ? v(cfg, url) : v });
  });
}
const galat = (status, detail) => Object.assign(new Error(detail), { response: { status, data: { detail } } });
const gets = (potongan) => mockGet.mock.calls.filter(([u]) => String(u).includes(potongan));

let galatKonsol;
beforeEach(() => { galatKonsol = jest.spyOn(console, "error").mockImplementation(() => {}); });
afterEach(async () => {
  const panggilan = galatKonsol.mock.calls.map((c) => String(c[0]).slice(0, 200));
  galatKonsol.mockRestore();
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  [mockGet, mockPost, mockPatch, mockGo, mockPreview, notifySuccess].forEach((m) => m.mockReset());
  document.body.innerHTML = "";
  expect(panggilan).toEqual([]);
});

const M = (code, name, need) => ({ code, name, needs_account: need, needs_reference: need === "bank", needs_due_date: false });
const CARA_BAYAR = [M("transfer", "Transfer bank", "bank"), M("cash", "Tunai", "kas")];
const SITES = { sites: [{ id: "site_bdg", name: "Toko Bandung", city: "Bandung" }, { id: "site_jkt", name: "Gudang Jakarta", city: "Jakarta" }] };
const PESAN_KUNCI_KAS = "Jenis kas rekening Kas Toko tidak bisa diubah karena rekening ini sudah punya transaksi kas. "
  + "Pindahkan saldonya lewat Pindah Dana ke rekening baru dengan jenis kas yang benar.";

// ── Aturan bersama (tanpa React) ─────────────────────────────────────────────────────────────────────────────────
describe("jenisKas — kosakata & aturan layar", () => {
  test("jenis kas = server account_cash_type; label kas kasir", () => {
    expect(jenisKasRekening({ account_type: "cash", cash_type: "kas_kasir" })).toBe("kas_kasir");
    expect(jenisKasRekening({ account_type: "cash" })).toBe("kas_kecil");            // rekening lama tanpa bidang
    expect(jenisKasRekening({ account_type: "bank" })).toBe("kas_besar");
    expect(jenisKasRekening({ account_type: "cash", cash_type: "aneh" })).toBe("kas_kecil");
    expect(labelJenisKas("kas_kasir")).toBe("Kas kasir");
    expect(labelJenisKas("kas_kecil")).toBe("Kas kecil");
    expect(labelJenisKas("kas_besar")).toBe("Kas besar");
  });
  test("alasan jenis kas terkunci = kalimat server (akun buku besar / sudah punya kas)", () => {
    expect(alasanJenisKasTerkunci({ name: "Kas Toko", jenis_kas_terkunci: false })).toBe("");
    expect(alasanJenisKasTerkunci({ name: "Kas Toko", jenis_kas_terkunci: true })).toBe(PESAN_KUNCI_KAS);
    expect(alasanJenisKasTerkunci({ name: "Kas Toko", jenis_kas_terkunci: true, gl_account_code: "1-1110-02" })).toBe(
      "Jenis kas rekening Kas Toko tidak bisa diubah karena akun buku besarnya (1-1110-02) dibuat untuk jenis kas itu. "
      + "Nonaktifkan rekening ini lalu buat rekening baru dengan jenis kas yang benar.");
  });
  test("Isi ulang hanya untuk kas kecil aktif berdana tetap dan pemegang cash.create", () => {
    const kk = { account_type: "cash", cash_type: "kas_kecil", dana_tetap: 2000000, is_active: true };
    const isi = { cash: ["view", "create"] };
    expect(bolehIsiUlang(kk, isi)).toBe(true);
    expect(bolehIsiUlang(kk, { cash: ["view"] })).toBe(false);
    expect(bolehIsiUlang({ ...kk, dana_tetap: 0 }, isi)).toBe(false);
    expect(bolehIsiUlang({ ...kk, is_active: false }, isi)).toBe(false);
    expect(bolehIsiUlang({ ...kk, cash_type: "kas_kasir" }, isi)).toBe(false);
  });
});

// ── Form rekening ────────────────────────────────────────────────────────────────────────────────────────────────
describe("Form rekening — jenis kas, dana tetap, lokasi", () => {
  beforeEach(() => routeGet({ "/payment-methods": CARA_BAYAR, "/warehouse-sites": SITES }));

  test("rekening bank: tanpa isian jenis kas/dana tetap/lokasi; kiriman tetap seperti dulu", async () => {
    mockPost.mockResolvedValue({ status: 200, data: { id: "bank_1" } });
    const host = await mount(<BankAccountForm open entityId="ent_ksc" entityLabel="Sukacita" onClose={() => {}} onSaved={() => {}} />);
    expect(q(host, "bank-form-cash-type")).toBeNull();
    expect(q(host, "bank-form-dana-tetap")).toBeNull();
    expect(q(host, "bank-form-location")).toBeNull();
    await type(q(host, "bank-form-name"), "BCA Baru");
    await submit(host, "bank-form-submit");
    const body = mockPost.mock.calls[0][1];
    expect(body.account_type).toBe("bank");
    expect(Object.keys(body)).not.toEqual(expect.arrayContaining(["cash_type"]));
    expect(body).not.toHaveProperty("dana_tetap");
    expect(body).not.toHaveProperty("location_id");
  });

  test("kas tunai baru wajib memilih Kas Kasir / Kas Kecil; kas kecil mengirim dana tetap & lokasi", async () => {
    mockPost.mockResolvedValue({ status: 200, data: { id: "kk_1" } });
    const host = await mount(<BankAccountForm open entityId="ent_ksc" entityLabel="Sukacita" onClose={() => {}} onSaved={() => {}} />);
    await choose(q(host, "bank-form-type"), "cash");
    const opsi = [...q(host, "bank-form-cash-type").options].filter((o) => o.value).map((o) => [o.value, o.textContent]);
    expect(opsi).toEqual([["kas_kasir", "Kas Kasir"], ["kas_kecil", "Kas Kecil"]]);
    expect(q(host, "bank-form-dana-tetap")).toBeNull();   // belum memilih jenis
    await type(q(host, "bank-form-name"), "Kas Kecil Bandung");
    await submit(host, "bank-form-submit");
    expect(mockPost).not.toHaveBeenCalled();
    expect(teks(q(host, "bank-add-form-error"))).toBe("Pilih jenis kas: Kas Kasir atau Kas Kecil.");

    await choose(q(host, "bank-form-cash-type"), "kas_kecil");
    expect(q(host, "bank-form-dana-tetap")).not.toBeNull();
    // ketetapan R3: yang dikurangkan = sisa panjar di tangan karyawan (sama dengan pop-up Isi ulang), bukan "belum LPJ"
    expect(teks(q(host, "bank-form-dana-tetap-hint"))).toBe(
      "Isi ulang diusulkan sebesar dana tetap − saldo buku − sisa panjar di tangan karyawan.");
    const lokasi = [...q(host, "bank-form-location").options].map((o) => [o.value, o.textContent]);
    // "" = tanpa lokasi (KNSelect menyisipkan butir placeholder "Tanpa lokasi" untuk mengosongkan)
    expect(lokasi).toEqual([["", "-"], ["site_bdg", "Toko Bandung · Bandung"], ["site_jkt", "Gudang Jakarta · Jakarta"]]);
    await type(q(host, "bank-form-dana-tetap"), "2.000.000");
    await choose(q(host, "bank-form-location"), "site_bdg");
    await submit(host, "bank-form-submit");
    expect(mockPost).toHaveBeenCalledTimes(1);
    const [url, body, cfg] = mockPost.mock.calls[0];
    expect(url).toBe("/api/bank-accounts");
    expect(body).toMatchObject({ name: "Kas Kecil Bandung", account_type: "cash", cash_type: "kas_kecil",
      dana_tetap: 2000000, location_id: "site_bdg" });
    expect(cfg.headers["Idempotency-Key"]).toBeTruthy();
  });

  test("kas kasir baru: tanpa dana tetap (0), lokasi boleh; pindah jenis mengosongkan dana tetap", async () => {
    mockPost.mockResolvedValue({ status: 200, data: { id: "ks_1" } });
    const host = await mount(<BankAccountForm open entityId="ent_ksc" entityLabel="Sukacita" onClose={() => {}} onSaved={() => {}} />);
    await choose(q(host, "bank-form-type"), "cash");
    await type(q(host, "bank-form-name"), "Kasir Toko");
    await choose(q(host, "bank-form-cash-type"), "kas_kecil");
    await type(q(host, "bank-form-dana-tetap"), "500000");
    await choose(q(host, "bank-form-cash-type"), "kas_kasir");
    expect(q(host, "bank-form-dana-tetap")).toBeNull();
    expect(q(host, "bank-form-location")).not.toBeNull();
    await choose(q(host, "bank-form-location"), "site_jkt");
    await submit(host, "bank-form-submit");
    expect(mockPost.mock.calls[0][1]).toMatchObject({ account_type: "cash", cash_type: "kas_kasir", dana_tetap: 0,
      location_id: "site_jkt" });
  });

  test("ubah rekening tunai terkunci: jenis kas mati dengan kalimat server; dana tetap saja yang terkirim", async () => {
    mockPatch.mockResolvedValue({ status: 202, data: { change: { id: "bac_1" } } });
    const acc = { id: "kk_9", entity_id: "ent_ksc", name: "Kas Toko", account_type: "cash", cash_type: "kas_kecil",
      dana_tetap: 1000000, location_id: "site_bdg", location_name: "Toko Bandung", jenis_kas_terkunci: true,
      purposes: ["operasional"], payment_method_codes: ["cash"], default_receiving_methods: [], is_active: true };
    const onSaved = jest.fn();
    const host = await mount(<BankAccountForm open account={acc} onClose={() => {}} onSaved={onSaved} />);
    expect(q(host, "bank-form-cash-type").disabled).toBe(true);
    expect(q(host, "bank-form-cash-type").value).toBe("kas_kecil");
    expect(teks(q(host, "bank-form-cash-type-reason"))).toBe(PESAN_KUNCI_KAS);
    expect(q(host, "bank-form-location").value).toBe("site_bdg");
    await type(q(host, "bank-form-dana-tetap"), "3000000");
    await submit(host, "bank-form-submit");
    const [url, body] = mockPatch.mock.calls[0];
    expect(url).toBe("/api/bank-accounts/kk_9");
    expect(body).toEqual({ dana_tetap: 3000000 });
    expect(onSaved).toHaveBeenCalledWith({ pending: true, data: { change: { id: "bac_1" } } });
  });

  test("ubah rekening tunai belum terkunci: kas kecil → kas kasir mengirim jenis kas + dana tetap 0; lokasi dihapus", async () => {
    mockPatch.mockResolvedValue({ status: 200, data: {} });
    const acc = { id: "kk_8", entity_id: "ent_ksc", name: "Kas Baru", account_type: "cash", cash_type: "kas_kecil",
      dana_tetap: 750000, location_id: "site_bdg", jenis_kas_terkunci: false, purposes: ["operasional"],
      payment_method_codes: ["cash"], default_receiving_methods: [], is_active: true };
    const host = await mount(<BankAccountForm open account={acc} onClose={() => {}} onSaved={() => {}} />);
    expect(q(host, "bank-form-cash-type").disabled).toBe(false);
    expect(q(host, "bank-form-cash-type-reason")).toBeNull();
    await choose(q(host, "bank-form-cash-type"), "kas_kasir");
    await choose(q(host, "bank-form-location"), "");
    await submit(host, "bank-form-submit");
    expect(mockPatch.mock.calls[0][1]).toEqual({ cash_type: "kas_kasir", dana_tetap: 0, location_id: "" });
  });

  test("PT berkas kasir: bawaan Tunai di rekening bukan kasir mati berkalimat; rekening kas kasir boleh", async () => {
    mockPost.mockResolvedValue({ status: 200, data: { id: "kk_2" } });
    const kasir = { id: "ks_1", entity_id: "ent_ksc", name: "Kasir Toko", account_type: "cash", cash_type: "kas_kasir",
      is_active: true, purposes: ["penerimaan_pelanggan", "operasional"], payment_method_codes: ["cash"],
      default_receiving_methods: ["cash"] };
    const host = await mount(<BankAccountForm open entityId="ent_ksc" entityLabel="Sukacita" rekeningPt={[kasir]}
      onClose={() => {}} onSaved={() => {}} />);
    await choose(q(host, "bank-form-type"), "cash");
    await type(q(host, "bank-form-name"), "Kas Kecil Gudang");
    await choose(q(host, "bank-form-cash-type"), "kas_kecil");
    expect(q(host, "bank-form-default-cash").disabled).toBe(true);
    expect(teks(q(host, "bank-form-default-kasir"))).toBe(
      "PT ini punya rekening kas kasir, jadi bawaan penerimaan tunai selalu rekening kas kasir.");
    await submit(host, "bank-form-submit");
    expect(mockPost.mock.calls[0][1].default_receiving_methods).toEqual([]);
    await choose(q(host, "bank-form-cash-type"), "kas_kasir");
    expect(q(host, "bank-form-default-cash").disabled).toBe(false);
    expect(q(host, "bank-form-default-kasir")).toBeNull();
    // kasir nonaktif / bukan penerimaan pelanggan tidak memegang bawaan
    document.body.innerHTML = "";
    const host2 = await mount(<BankAccountForm open entityId="ent_ksc" entityLabel="Sukacita"
      rekeningPt={[{ ...kasir, is_active: false }]} onClose={() => {}} onSaved={() => {}} />);
    await choose(q(host2, "bank-form-type"), "cash");
    await choose(q(host2, "bank-form-cash-type"), "kas_kecil");
    expect(q(host2, "bank-form-default-cash").disabled).toBe(false);
  });

  test("daftar lokasi tidak bisa dimuat: lokasi tersimpan tetap tampil, kalimat tertulis", async () => {
    routeGet({ "/payment-methods": CARA_BAYAR, "/warehouse-sites": galat(403, "Akses ditolak") });
    const acc = { id: "kk_7", entity_id: "ent_ksc", name: "Kas Toko", account_type: "cash", cash_type: "kas_kecil",
      dana_tetap: 0, location_id: "site_bdg", location_name: "Toko Bandung", jenis_kas_terkunci: true,
      purposes: ["operasional"], payment_method_codes: ["cash"], default_receiving_methods: [], is_active: true };
    const host = await mount(<BankAccountForm open account={acc} onClose={() => {}} onSaved={() => {}} />);
    const opsi = [...q(host, "bank-form-location").options].map((o) => o.textContent);
    expect(opsi).toContain("Toko Bandung");
    expect(teks(q(host, "bank-form-location-note"))).toBe("Daftar lokasi kerja belum bisa dimuat — lokasi lain belum bisa dipilih.");
  });
});

// ── Perubahan rekening menunggu ──────────────────────────────────────────────────────────────────────────────────
describe("Perubahan rekening menunggu — bidang kas berlabel", () => {
  test("jenis kas, dana tetap (Rp), lokasi (nama), jenis rekening, saldo awal", async () => {
    routeGet({
      "/payment-methods": CARA_BAYAR, "/warehouse-sites": SITES,
      "/bank-account-changes": { total: 2, items: [
        { id: "c1", action: "ubah", account_name: "Kas Toko", entity_name: "Sukacita", requested_by: "Rina",
          created_at: "2026-11-28T03:00:00Z", status: "menunggu", blocked_reason: "",
          label_changes: [{ field: "cash_type", label: "Jenis kas", from: "kas_kecil", to: "kas_kasir" },
            { field: "dana_tetap", label: "Dana tetap", from: 0, to: 2000000 },
            { field: "location_id", label: "Lokasi", from: "", to: "site_bdg" }] },
        { id: "c2", action: "buat", account_name: "Kas Kecil Jakarta", entity_name: "Sukacita", requested_by: "Rina",
          created_at: "2026-11-28T03:00:00Z", status: "menunggu", blocked_reason: "",
          label_changes: [{ field: "account_type", label: "Jenis", to: "cash" },
            { field: "opening_balance", label: "Saldo awal", to: 250000 },
            { field: "location_id", label: "Lokasi", to: "site_hilang" }] },
      ] },
    });
    const host = await mount(<BankAccountChangesPanel entityParam="ent_ksc" canApprove />);
    expect(teks(q(host, "bank-change-lines-c1"))).toBe(
      `Jenis kas: Kas kecil → Kas kasirDana tetap: ${rp(0)} → ${rp(2000000)}Lokasi: — → Toko Bandung`);
    // lokasi yang tidak ada di daftar ditulis terang (tanpa id mentah)
    expect(teks(q(host, "bank-change-lines-c2"))).toBe(
      `Jenis: Kas tunaiSaldo awal: ${rp(250000)}Lokasi: lokasi tidak dikenal`);
  });

  test("tanpa perubahan lokasi: daftar lokasi tidak dimuat", async () => {
    routeGet({ "/payment-methods": CARA_BAYAR, "/bank-account-changes": { total: 1, items: [
      { id: "c3", action: "ubah", account_name: "Kas Toko", entity_name: "Sukacita", requested_by: "Rina",
        created_at: "2026-11-28T03:00:00Z", status: "menunggu", blocked_reason: "",
        label_changes: [{ field: "dana_tetap", label: "Dana tetap", from: 1000000, to: 1500000 }] }] } });
    const host = await mount(<BankAccountChangesPanel entityParam="ent_ksc" canApprove />);
    expect(teks(q(host, "bank-change-lines-c3"))).toBe(`Dana tetap: ${rp(1000000)} → ${rp(1500000)}`);
    expect(gets("/warehouse-sites")).toHaveLength(0);
  });
});

// ── Posisi dana tetap (data uji) ─────────────────────────────────────────────────────────────────────────────────
const PDN_LALU = { id: "pdn_0", number: "KSC/PDN-00010", status: "selesai", status_label: "Selesai", nominal: 800000,
  rekening_asal_id: "bank_bca", rekening_asal_nama: "BCA Operasional", tanggal: "2026-11-15",
  created_at: "2026-11-15T02:00:00Z", created_by: "Budi" };
const PDN_TUNGGU = { id: "pdn_9", number: "KSC/PDN-00011", status: "menunggu_persetujuan", status_label: "Menunggu persetujuan",
  nominal: 500000, rekening_asal_id: "bank_bca", rekening_asal_nama: "BCA Operasional", tanggal: "2026-11-28",
  created_at: "2026-11-28T02:00:00Z", created_by: "Rina" };
const SUMBER = [{ id: "bank_bca", name: "BCA Operasional", account_type: "bank", bank_name: "BCA", account_number: "123" },
  { id: "kb_1", name: "Kas Besar Toko", account_type: "cash", bank_name: "", account_number: "" }];
const POSISI = {
  account_id: "kk1", account_name: "Kas Kecil Toko", entity_id: "ent_ksc", is_active: true, location_id: "site_bdg",
  dana_tetap: 2000000, saldo_buku: 1200000, panjar_belum_lpj: 300000, usulan_isi_ulang: 500000,
  // ketetapan R3: panjar_belum_lpj = sisa di tangan karyawan per pencairan (250.000 belum LPJ + 50.000 sisa belum kembali)
  panjar: [
    { cash_advance_id: "ca1", nomor: "PD-0007", kegiatan: "Belanja ATK", pemohon: "Rina", nominal: 250000,
      pengeluaran_lpj: 0, dikembalikan: 0, sisa: 250000, lpj_id: "", lpj_nomor: "", keadaan: "belum_lpj",
      keadaan_label: "Belum LPJ", tanggal: "2026-11-20", kas_id: "k1", kas_nomor: "KK-0101" },
    { cash_advance_id: "ca2", nomor: "PD-0008", kegiatan: "Bensin", pemohon: "Budi", nominal: 200000,
      pengeluaran_lpj: 150000, dikembalikan: 0, sisa: 50000, lpj_id: "stl8", lpj_nomor: "LPJ-0008",
      keadaan: "sisa_belum_kembali", keadaan_label: "Sisa belum dikembalikan", tanggal: "2026-11-19", kas_id: "k8",
      kas_nomor: "KK-0099" },
  ],
  rincian: [
    { jenis: "lpj", label: "LPJ disetujui", tanggal: "2026-11-21", nomor: "LPJ-0003", dokumen: "PD-0005",
      keterangan: "PD-0005 — Bensin", ref_type: "cash_advance_settlement", ref_id: "stl3", kas_id: "k0", arah: "",
      nominal: 380000, panjar: 400000, pengeluaran: 380000, pengaruh: 380000, dicatat_pada: "2026-11-21T03:00:00Z" },
    { jenis: "kas_keluar_manual", label: "Kas keluar manual", tanggal: "2026-11-22", nomor: "KK-0102", dokumen: "",
      keterangan: "Parkir", ref_type: "manual", ref_id: "", kas_id: "k2", arah: "out", nominal: 170000, pengaruh: 170000,
      dicatat_pada: "2026-11-22T03:00:00Z" },
    { jenis: "pindah_dana_masuk", label: "Pindah Dana masuk", tanggal: "2026-11-23", nomor: "KK-0103", dokumen: "",
      keterangan: "Titip dari kasir", ref_type: "fund_transfer", ref_id: "pdn_lain", kas_id: "k3", arah: "in",
      nominal: 50000, pengaruh: -50000, dicatat_pada: "2026-11-23T03:00:00Z" },
  ],
  rincian_terpotong: false, total_rincian: 500000, sejak: PDN_LALU, isi_ulang_menunggu: null, riwayat: [PDN_LALU],
  panjar_tanpa_rekening: { jumlah: 0, total: 0, nomor: [] }, sumber: SUMBER, bisa_isi_ulang: true, alasan_isi_ulang: "",
  dihitung_pada: "2026-11-28T03:00:00Z",
};
const POSISI_TUNGGU = { ...POSISI, isi_ulang_menunggu: PDN_TUNGGU, riwayat: [PDN_TUNGGU, PDN_LALU], bisa_isi_ulang: false,
  alasan_isi_ulang: "Isi ulang rekening Kas Kecil Toko sebelumnya (KSC/PDN-00011) masih menunggu persetujuan. Selesaikan "
    + "atau batalkan Pindah Dana itu dulu." };

// ── Kartu rekening ───────────────────────────────────────────────────────────────────────────────────────────────
describe("Rekening & Saldo — kartu rekening tunai", () => {
  const REK = [
    { id: "kk1", name: "Kas Kecil Toko", entity_id: "ent_ksc", account_type: "cash", cash_type: "kas_kecil", is_active: true,
      balance: 1200000, dana_tetap: 2000000, location_id: "site_bdg", location_name: "Toko Bandung", txn_count: 3 },
    { id: "ks1", name: "Kasir Toko", entity_id: "ent_ksc", account_type: "cash", cash_type: "kas_kasir", is_active: true,
      balance: 400000, dana_tetap: 0, location_id: "site_bdg", location_name: "Toko Bandung", txn_count: 1 },
    { id: "bca", name: "BCA Operasional", entity_id: "ent_ksc", account_type: "bank", cash_type: "kas_besar", is_active: true,
      bank_name: "BCA", account_number: "123", balance: 9000000, dana_tetap: 0, location_id: "", location_name: "" },
  ];
  const pasang = (posisi = POSISI) => routeGet({ "/bank-accounts/position": null, "/bank-accounts": REK,
    "/bank-account-changes": { items: [], total: 0 }, "/kas-kecil/dana-tetap/kk1": posisi, "/payment-methods": CARA_BAYAR });

  test("jenis kas, dana tetap, lokasi tampil; Isi ulang hanya di kas kecil berdana tetap untuk cash.create", async () => {
    pasang();
    let host = await mount(<BankAccountsView selectedEntity="ent_ksc" currentUser={{ role: "x", permissions: { cash: ["view", "create"] } }} />);
    expect(teks(q(host, "bank-cash-type-kk1"))).toBe("Kas kecil");
    expect(teks(q(host, "bank-cash-type-ks1"))).toBe("Kas kasir");
    expect(teks(q(host, "bank-dana-tetap-kk1"))).toBe(`Dana tetap ${rp(2000000)}`);
    expect(q(host, "bank-dana-tetap-ks1")).toBeNull();
    expect(teks(q(host, "bank-location-kk1"))).toBe("Lokasi Toko Bandung");
    expect(teks(q(host, "bank-location-ks1"))).toBe("Lokasi Toko Bandung");
    expect(q(host, "bank-location-bca")).toBeNull();
    expect(q(host, "bank-refill-kk1")).not.toBeNull();
    expect(q(host, "bank-refill-ks1")).toBeNull();
    expect(q(host, "bank-refill-bca")).toBeNull();
    // SATU kaki per kartu (Isi ulang + Opname di kaki yang sama, testid unik) — dulu dua kaki bertumpuk ber-testid kembar
    expect(host.querySelectorAll('[data-testid="bank-card-actions-kk1"]')).toHaveLength(1);
    const kaki = q(host, "bank-card-actions-kk1");
    expect(q(kaki, "bank-refill-kk1")).not.toBeNull();
    expect(q(kaki, "bank-opname-kk1")).not.toBeNull();
    expect(host.querySelectorAll('[data-testid="bank-card-actions-ks1"]')).toHaveLength(1);   // kasir: Opname saja
    expect(q(q(host, "bank-card-actions-ks1"), "bank-opname-ks1")).not.toBeNull();
    expect(q(host, "bank-card-actions-bca")).toBeNull();                                      // bank: tanpa aksi kartu
    const aksiTestid = [...host.querySelectorAll('[data-testid^="bank-card-actions-"], [data-testid^="bank-refill-"], '
      + '[data-testid^="bank-opname-"]')].map((el) => el.getAttribute("data-testid"));
    expect(aksiTestid.length).toBe(new Set(aksiTestid).size);
    // aksi kartu bukan tombol di dalam tombol kartu (HTML sah) dan tidak membuka buku rekening
    expect(q(host, "bank-refill-kk1").closest('[data-testid="bank-card-kk1"]')).toBeNull();
    await click(q(host, "bank-refill-kk1"));
    expect(gets("/ledger")).toHaveLength(0);
    expect(q(host, "bank-ledger-modal")).toBeNull();
    expect(q(document.body, "refill-form")).not.toBeNull();
    document.body.innerHTML = "";
    host = await mount(<BankAccountsView selectedEntity="ent_ksc" currentUser={{ role: "x", permissions: { cash: ["view"] } }} />);
    expect(q(host, "bank-refill-kk1")).toBeNull();
    expect(q(host, "bank-card-actions-kk1")).toBeNull();
  });

  test("Isi ulang dari kartu: nominal dari server hanya-baca, pilih sumber, tanpa nominal di kiriman; sukses → pemberitahuan", async () => {
    pasang();
    mockPost.mockResolvedValue({ data: { id: "pdn_12", number: "KSC/PDN-00012", status: "menunggu_persetujuan",
      jenis: "isi_ulang_kas_kecil", nominal: 500000 } });
    const host = await mount(<BankAccountsView selectedEntity="ent_ksc" currentUser={{ role: "x", permissions: { cash: ["view", "create"] } }} />);
    await click(q(host, "bank-refill-kk1"));
    expect(gets("/kas-kecil/dana-tetap/kk1")).toHaveLength(1);
    expect(teks(q(host, "refill-form-title"))).toBe("Isi ulang Kas Kecil Toko");
    expect(teks(q(host, "refill-amount"))).toBe(rp(500000));
    expect(host.querySelector('[data-testid="refill-form"] input[data-testid="refill-amount"]')).toBeNull();   // bukan isian
    expect(teks(q(host, "refill-dana-tetap"))).toBe(rp(2000000));
    expect(teks(q(host, "refill-saldo"))).toBe(rp(1200000));
    expect(teks(q(host, "refill-panjar"))).toBe(rp(300000));
    const opsi = [...q(host, "refill-source").options].filter((o) => o.value).map((o) => o.textContent);
    expect(opsi).toEqual(["BCA Operasional · BCA 123", "Kas Besar Toko"]);
    expect(q(host, "refill-form-submit").disabled).toBe(true);   // sumber belum dipilih
    await choose(q(host, "refill-source"), "bank_bca");
    expect(teks(q(host, "refill-summary"))).toContain(`${rp(500000)} dipindah dari BCA Operasional ke Kas Kecil Toko`);
    await type(q(host, "refill-note"), "Isi ulang minggu ini");
    await submit(host, "refill-form-submit");
    expect(mockPost).toHaveBeenCalledTimes(1);
    const [url, body, cfg] = mockPost.mock.calls[0];
    expect(url).toBe("/api/kas-kecil/dana-tetap/kk1/isi-ulang");
    // tanpa `nominal` (server menghitung ulang); `nominal_dilihat` = angka yang DITAMPILKAN, supaya server menolak (409)
    // bila usulannya berubah sejak pop-up dibuka (bukan nominal klien)
    expect(body).toEqual({ sumber_account_id: "bank_bca", catatan: "Isi ulang minggu ini", nominal_dilihat: 500000 });
    expect(body).not.toHaveProperty("nominal");
    expect(cfg.headers["Idempotency-Key"]).toBeTruthy();
    expect(q(host, "refill-form")).toBeNull();
    expect(teks(q(host, "bank-notice"))).toBe(
      "Isi ulang KSC/PDN-00012 dicatat — menunggu persetujuan. Setujui di Kas & Bank › Pindah Dana.");
  });

  test("Isi ulang terbuka menghalangi yang kedua: tombol mati + kalimat server; galat server tampil di pop-up", async () => {
    pasang(POSISI_TUNGGU);
    const host = await mount(<BankAccountsView selectedEntity="ent_ksc" currentUser={{ role: "x", permissions: { cash: ["view", "create"] } }} />);
    await click(q(host, "bank-refill-kk1"));
    expect(teks(q(host, "refill-reason"))).toBe(POSISI_TUNGGU.alasan_isi_ulang);
    expect(teks(q(host, "refill-pending"))).toContain("KSC/PDN-00011");
    expect(q(host, "refill-source")).toBeNull();
    expect(q(host, "refill-form-submit").disabled).toBe(true);
    await submit(host, "refill-form-submit");
    expect(mockPost).not.toHaveBeenCalled();
  });

  test("galat server saat kirim tampil di dalam pop-up, posisi dimuat ulang", async () => {
    pasang();
    mockPost.mockRejectedValue(galat(409, "Isi ulang rekening Kas Kecil Toko sedang diproses orang lain. Tunggu sebentar lalu muat ulang."));
    const host = await mount(<IsiUlangModal open accountId="kk1" accountName="Kas Kecil Toko" onClose={() => {}} onSaved={() => {}} />);
    await choose(q(host, "refill-source"), "kb_1");
    await submit(host, "refill-form-submit");
    expect(teks(q(host, "refill-form-error"))).toBe(
      "Isi ulang rekening Kas Kecil Toko sedang diproses orang lain. Tunggu sebentar lalu muat ulang.");
    expect(gets("/kas-kecil/dana-tetap/kk1")).toHaveLength(2);
  });

  test("usulan berubah sejak dibuka: 409 server tampil di pop-up, nominal dimuat ulang dan dikirim lagi sebagai yang dilihat", async () => {
    let posisi = POSISI;
    routeGet({ "/kas-kecil/dana-tetap/kk1": () => posisi });
    const kalimat = "Usulan isi ulang berubah dari Rp 500.000 menjadi Rp 650.000 sejak pop-up dibuka. Muat ulang lalu periksa lagi.";
    mockPost.mockImplementationOnce(async () => {
      posisi = { ...POSISI, saldo_buku: 1050000, usulan_isi_ulang: 650000 };   // kas keluar di sela
      throw galat(409, kalimat);
    });
    mockPost.mockResolvedValueOnce({ data: { id: "pdn_13", number: "KSC/PDN-00013", status: "selesai", nominal: 650000 } });
    const onSaved = jest.fn();
    const host = await mount(<IsiUlangModal open accountId="kk1" accountName="Kas Kecil Toko" onClose={() => {}} onSaved={onSaved} />);
    expect(teks(q(host, "refill-amount"))).toBe(rp(500000));
    await choose(q(host, "refill-source"), "bank_bca");
    await submit(host, "refill-form-submit");
    expect(mockPost.mock.calls[0][1]).toMatchObject({ nominal_dilihat: 500000 });
    expect(teks(q(host, "refill-form-error"))).toBe(kalimat);
    expect(teks(q(host, "refill-amount"))).toBe(rp(650000));            // angka baru dimuat ulang di pop-up yang sama
    expect(teks(q(host, "refill-summary"))).toContain(rp(650000));
    expect(onSaved).not.toHaveBeenCalled();
    await submit(host, "refill-form-submit");
    expect(mockPost.mock.calls[1][1]).toMatchObject({ sumber_account_id: "bank_bca", nominal_dilihat: 650000 });
    expect(mockPost.mock.calls[1][2].headers["Idempotency-Key"]).not.toBe(mockPost.mock.calls[0][2].headers["Idempotency-Key"]);
    expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ number: "KSC/PDN-00013" }));
  });

  test("posisi gagal dimuat: pesan di pop-up, tombol mati; PT tanpa rekening sumber: kalimat", async () => {
    routeGet({ "/kas-kecil/dana-tetap/kk1": galat(403, "Anda tidak punya akses melihat kas.") });
    let host = await mount(<IsiUlangModal open accountId="kk1" accountName="Kas Kecil Toko" onClose={() => {}} onSaved={() => {}} />);
    expect(teks(q(host, "refill-form-error"))).toBe("Anda tidak punya akses melihat kas.");
    expect(q(host, "refill-form-submit").disabled).toBe(true);
    document.body.innerHTML = "";
    routeGet({ "/kas-kecil/dana-tetap/kk1": { ...POSISI, sumber: [] } });
    host = await mount(<IsiUlangModal open accountId="kk1" accountName="Kas Kecil Toko" onClose={() => {}} onSaved={() => {}} />);
    expect(teks(q(host, "refill-no-source"))).toBe(
      "PT ini belum punya rekening bank atau kas besar aktif untuk sumber isi ulang. Tambahkan di Rekening & Saldo.");
    expect(q(host, "refill-form-submit").disabled).toBe(true);
  });
});

// ── Kas Kecil › Dana tetap ───────────────────────────────────────────────────────────────────────────────────────
describe("Kas Kecil — tab Dana tetap", () => {
  const WL = { items: [], total: 0, page: 1, page_size: 25, stage_counts: {} };
  const DAFTAR = { items: [POSISI, { ...POSISI_TUNGGU, account_id: "kk2", account_name: "Kas Kecil Gudang" }], total: 2,
    tanpa_dana_tetap: 1 };
  const SEMUA_IZIN = { cash_advance: ["view", "create"], cash_settlement: ["view"], cash: ["view", "create"] };

  test("tab hanya untuk cash.view; tanpa izin kas tidak ada tab & tidak memuat dana tetap", async () => {
    routeGet({ "/petty-cash/worklist": WL, "/expense-categories": [] });
    const host = await mount(<PettyCashView currentUser={{ role: "x", permissions: { cash_advance: ["view"] } }} selectedEntity="ent_ksc" entities={[]} />);
    expect(q(host, "pc-bagian")).toBeNull();
    expect(q(host, "pc-title")).not.toBeNull();
    expect(gets("/kas-kecil/dana-tetap")).toHaveLength(0);
  });

  test("posisi per rekening: dana tetap, saldo buku, panjar, usulan; isi ulang terbuka bertautan PDN; tombol mati beralasan", async () => {
    routeGet({ "/petty-cash/worklist": WL, "/expense-categories": [], "/kas-kecil/dana-tetap": DAFTAR });
    const host = await mount(<PettyCashView currentUser={{ role: "x", permissions: SEMUA_IZIN }} selectedEntity="ent_ksc" entities={[]} />);
    const tab = [...q(host, "pc-bagian").querySelectorAll("button")].map((t) => t.textContent);
    expect(tab).toEqual(["Pengajuan dana", "Dana tetap"]);
    expect(gets("/kas-kecil/dana-tetap")).toHaveLength(0);   // dimuat saat tab dibuka
    await click(q(host, "pc-bagian-dana-tetap"));
    expect(mockGet).toHaveBeenCalledWith("/api/kas-kecil/dana-tetap", { params: { entity_id: "ent_ksc" } });
    expect(q(host, "pc-title")).toBeNull();
    expect(teks(q(host, "dt-dana-kk1"))).toBe(rp(2000000));
    expect(teks(q(host, "dt-saldo-kk1"))).toBe(rp(1200000));
    expect(teks(q(host, "dt-panjar-kk1"))).toBe(rp(300000));
    expect(teks(q(host, "dt-usulan-kk1"))).toBe(rp(500000));
    expect(q(host, "dt-refill-kk1").disabled).toBe(false);
    expect(q(host, "dt-refill-kk2").disabled).toBe(true);
    expect(teks(q(host, "dt-refill-reason-kk2"))).toBe(POSISI_TUNGGU.alasan_isi_ulang);
    expect(teks(q(host, "dt-pending-kk2"))).toBe("KSC/PDN-00011");
    await click(q(host, "dt-pending-kk2"));
    expect(mockPreview).toHaveBeenCalledWith({ docType: "fund_transfer", docId: "pdn_9", number: "KSC/PDN-00011",
      entityId: "ent_ksc" });
    expect(q(host, "dt-detail-modal")).toBeNull();   // tautan nomor tidak membuka rincian baris
    expect(teks(q(host, "dt-none-note"))).toContain("1 rekening kas kecil belum memakai dana tetap");
    await click(q(host, "dt-none-link"));
    expect(mockGo).toHaveBeenCalledWith("bank-accounts");
  });

  test("rincian: baris sejak isi ulang terakhir, panjar, riwayat isi ulang → pratinjau PDN", async () => {
    routeGet({ "/petty-cash/worklist": WL, "/expense-categories": [], "/kas-kecil/dana-tetap": DAFTAR });
    const host = await mount(
      <ViewPresetProvider preset={{ view: "petty-cash", bagian: "dana-tetap", nonce: 3 }}>
        <PettyCashView currentUser={{ role: "x", permissions: SEMUA_IZIN }} selectedEntity="ent_ksc" entities={[]} />
      </ViewPresetProvider>);
    expect(q(host, "pc-bagian-dana-tetap").getAttribute("aria-pressed")).toBe("true");
    await click(q(host, "dt-open-kk1"));
    const modal = q(host, "dt-detail-modal");
    expect(modal).not.toBeNull();
    expect(teks(q(host, "dt-detail-since"))).toBe("Sejak isi ulang terakhir KSC/PDN-00010 · 15 Nov 2026");
    const baris = [...modal.querySelectorAll('[data-testid^="dt-detail-row-"]')].map((r) => teks(r));
    expect(baris).toHaveLength(3);
    expect(baris[0]).toContain("LPJ disetujui");
    expect(baris[0]).toContain("LPJ-0003");
    expect(baris[0]).toContain(`+${rp(380000)}`);
    expect(baris[0]).toContain(`Belanja ${rp(380000)} dari panjar ${rp(400000)}`);
    expect(baris[2]).toContain(`−${rp(50000)}`);
    expect(teks(q(host, "dt-detail-total"))).toContain(rp(500000));
    expect(teks(q(host, "dt-detail-advance-ca1"))).toContain("Belum LPJ");
    expect(teks(q(host, "dt-detail-advance-ca1"))).toContain(rp(250000));
    expect(teks(q(host, "dt-detail-advance-ca2"))).toContain("Sisa belum dikembalikan");
    expect(teks(q(host, "dt-detail-advance-ca2"))).toContain(`${rp(50000)}dari panjar ${rp(200000)}`);
    expect(teks(q(host, "dt-detail-identity"))).toBe(
      `Saldo buku + sisa panjar di tangan karyawan + usulan isi ulang = dana tetap ${rp(2000000)}.`);
    await click(q(host, "dt-detail-ref-2"));   // kas Pindah Dana → pratinjau PDN-nya
    expect(mockPreview).toHaveBeenLastCalledWith({ docType: "fund_transfer", docId: "pdn_lain", number: "KK-0103",
      entityId: "ent_ksc" });
    await click(q(host, "dt-history-pdn_0"));
    expect(mockPreview).toHaveBeenLastCalledWith({ docType: "fund_transfer", docId: "pdn_0", number: "KSC/PDN-00010",
      entityId: "ent_ksc" });
  });

  test("Isi ulang dari tab: pop-up yang sama; sukses memuat ulang posisi; tanpa cash.create tombol tidak ada", async () => {
    routeGet({ "/petty-cash/worklist": WL, "/expense-categories": [], "/kas-kecil/dana-tetap/kk1": POSISI,
      "/kas-kecil/dana-tetap": DAFTAR });
    mockPost.mockResolvedValue({ data: { id: "pdn_12", number: "KSC/PDN-00012", status: "selesai", nominal: 500000 } });
    let host = await mount(<PettyCashView currentUser={{ role: "x", permissions: SEMUA_IZIN }} selectedEntity="ent_ksc" entities={[]} />);
    await click(q(host, "pc-bagian-dana-tetap"));
    await click(q(host, "dt-refill-kk1"));
    await choose(q(host, "refill-source"), "bank_bca");
    await submit(host, "refill-form-submit");
    expect(mockPost.mock.calls[0][0]).toBe("/api/kas-kecil/dana-tetap/kk1/isi-ulang");
    expect(notifySuccess).toHaveBeenCalledWith("Isi ulang KSC/PDN-00012 dicatat — selesai.");
    expect(q(host, "refill-form")).toBeNull();
    expect(gets("/kas-kecil/dana-tetap").filter(([u]) => u.endsWith("/dana-tetap"))).toHaveLength(2);
    document.body.innerHTML = "";
    host = await mount(<PettyCashView currentUser={{ role: "x", permissions: { cash: ["view"] } }} selectedEntity="ent_ksc" entities={[]} />);
    // hanya izin kas: Dana tetap langsung tampil (tanpa tab tunggal), tanpa pesan "belum punya akses"
    expect(q(host, "petty-cash-no-access")).toBeNull();
    expect(q(host, "pc-bagian")).toBeNull();
    expect(q(host, "dt-row-kk1")).not.toBeNull();
    expect(q(host, "dt-refill-kk1")).toBeNull();
  });

  test("kosong & galat: satu pesan masing-masing", async () => {
    routeGet({ "/kas-kecil/dana-tetap": { items: [], total: 0, tanpa_dana_tetap: 0 } });
    let host = await mount(<PettyCashView currentUser={{ role: "x", permissions: { cash: ["view"] } }} selectedEntity="ent_ksc" entities={[]} />);
    expect(teks(q(host, "dt-empty"))).toBe("Belum ada rekening kas kecil yang memakai dana tetap. Atur dana tetap di Rekening & Saldo › Ubah rekening.");
    document.body.innerHTML = "";
    routeGet({ "/kas-kecil/dana-tetap": galat(500, "Server sibuk.") });
    host = await mount(<PettyCashView currentUser={{ role: "x", permissions: { cash: ["view"] } }} selectedEntity="ent_ksc" entities={[]} />);
    expect(teks(q(host, "dt-error"))).toContain("Server sibuk.");
    expect(q(host, "dt-empty")).toBeNull();
  });
});

// ── Pratinjau Pindah Dana isi ulang ──────────────────────────────────────────────────────────────────────────────
describe("Pratinjau PDN isi ulang kas kecil", () => {
  test("jenis + potret posisi saat dibuat", async () => {
    const doc = { id: "pdn_12", number: "KSC/PDN-00012", entity_id: "ent_ksc", status: "selesai", nominal: 500000, biaya: 0,
      rekening_asal: "BCA Operasional", rekening_tujuan: "Kas Kecil Toko", tanggal_kirim: "2026-11-28",
      jenis: "isi_ulang_kas_kecil", jenis_label: "Isi ulang kas kecil",
      isi_ulang: { account_id: "kk1", dana_tetap: 2000000, saldo_buku: 1200000, panjar_belum_lpj: 300000, usulan: 500000,
        rincian: POSISI.rincian, total_rincian: 500000, sejak_nomor: "KSC/PDN-00010", dihitung_pada: "2026-11-28T03:00:00Z" } };
    const host = await mount(<FundTransferPreview doc={doc} />);
    expect(teks(host)).toContain("Isi ulang kas kecil");
    const potret = teks(q(host, "doc-preview-ft-refill"));
    expect(potret).toContain(rp(2000000));
    expect(potret).toContain(rp(1200000));
    expect(potret).toContain(rp(300000));
    expect(potret).toContain(rp(500000));
    expect(potret).toContain("KSC/PDN-00010");
    const biasa = await mount(<FundTransferPreview doc={{ ...doc, id: "pdn_1", jenis: "", jenis_label: "", isi_ulang: undefined }} />);
    expect(q(biasa, "doc-preview-ft-refill")).toBeNull();
  });
});
