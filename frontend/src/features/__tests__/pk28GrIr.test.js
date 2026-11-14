// PK-28 (IV-03) — sisi layar tanpa peramban (uji jalan U16 di lingkungan A):
//  · Hutang › GR/IR: "Semua PT" → petunjuk pilih PT (tanpa memuat); memuat · galat (kotak merah + Coba lagi, tanpa teks
//    kosong) · kosong dibedakan. Kolom & kaki tabel sesuai spesifikasi; jurnal tak terhubung ditulis merah.
//  · Status PO: ikon + teks + warna (label server, bukan kode). Saringan Umur & sakelar "Tampilkan yang sudah nol" →
//    parameter server. Kliring hanya untuk baris `can_clear` + pemegang `accounting.manage`; baris lain menulis alasannya.
//  · Dialog kliring menyebut nominal, PO, dan PT, menuntut alasan; kirim ber-Idempotency-Key; daftar dimuat ulang.
//  · Rincian faktur: "Selisih harga terhadap PO" (sembunyi bila 0) + catatan bila selisih masih di GR/IR.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import GrIrView, { TEKS_GALAT, TEKS_KOSONG, TEKS_MEMUAT, TEKS_SEMUA_PT, alasanTidakKliring } from "../purchasing/GrIrView";
import { PriceVarianceRow } from "../purchasing/VendorBillDetailPanel";
import { AppNavProvider } from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { setAccessContext } from "../../config/roles";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockAsk = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({ askReason: (...a) => mockAsk(...a) }));
jest.mock("../../components/EntityScopeBanner", () => () => <div data-testid="grir-scope" />);
// Komponen yang menarik `@radix-ui`/`cmdk` (tidak termuat di lingkungan uji lokal) — panel faktur hanya dipakai bagian
// `PriceVarianceRow`-nya.
jest.mock("../../components/KNSelect", () => () => null);
jest.mock("../../components/KNDatePicker", () => () => null);
jest.mock("../documents/DocumentActionsBar", () => () => null);
jest.mock("../documents/trace/DocRefsPanel", () => () => null);
jest.mock("../../components/AskKnButton", () => ({ AskKnButton: () => null }));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const ENT = [{ id: "ent_ksc", legal_name: "PT Kain Suka Cita", short_name: "KSC" },
  { id: "ent_kanda", legal_name: "CV Kanda", short_name: "Kanda" }];
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function settle() { for (let i = 0; i < 5; i += 1) await act(async () => {}); }
async function mount(el, { entity = "ent_ksc", open } = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(
      <EntityScopeProvider selectedEntity={entity} entities={ENT} canSwitch>
        <AppNavProvider role="admin" onOpenDocument={open}>{el}</AppNavProvider>
      </EntityScopeProvider>);
  });
  await settle();
  return { host, root };
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
}

const LINK = (id) => ({ view: "purchasing", tab: "", focus_type: "purchase_order", focus_id: id, number: "" });
const BARIS_BOLEH = {
  po_id: "po_1", po_number: "PO/001", supplier_name: "Pemasok A", po_status: "closed_short",
  po_status_label: "ditutup-kurang", received_value: 600000, billed_value: 590000, returned_value: 0, cleared_value: 0,
  balance: 10000, last_receipt_at: "2026-11-14", age_days: 0, bucket: "0-30", unposted_variance: 0,
  open_bill_number: "", can_clear: true, link: LINK("po_1"),
};
const BARIS_JALAN = {
  ...BARIS_BOLEH, po_id: "po_2", po_number: "PO/002", po_status: "receiving", po_status_label: "sedang diterima",
  received_value: 1000000, billed_value: 1100000, balance: -100000, unposted_variance: 100000, age_days: 45,
  bucket: "31-60", can_clear: false, link: LINK("po_2"),
};
const ISI = { entity_id: "ent_ksc", items: [BARIS_BOLEH, BARIS_JALAN], total: 2, page: 1, page_size: 50,
  total_balance: -90000, filtered_balance: -90000, ledger_balance: -95000, unlinked_balance: -5000,
  mapping_ready: true, as_of: "2026-11-14" };

beforeEach(() => setAccessContext({ role: "admin" }));
afterEach(() => { mockGet.mockReset(); mockPost.mockReset(); mockAsk.mockReset(); document.body.innerHTML = ""; });

test("Semua PT: petunjuk pilih PT, daftar tidak dimuat", async () => {
  const { host } = await mount(<GrIrView />, { entity: "all" });
  expect(q(host, "grir-entity-required").textContent).toContain(TEKS_SEMUA_PT);
  expect(mockGet).not.toHaveBeenCalled();
  expect(q(host, "grir-table")).toBeNull();
});

test("memuat, galat + Coba lagi (tanpa teks kosong), lalu kosong", async () => {
  mockGet.mockImplementationOnce(() => new Promise(() => {}));
  const a = await mount(<GrIrView />);
  expect(q(a.host, "grir-loading").textContent).toBe(TEKS_MEMUAT);
  expect(q(a.host, "grir-empty")).toBeNull();
  document.body.innerHTML = "";
  mockGet.mockRejectedValueOnce({ response: { status: 503, data: { detail: "Server sibuk" } } });
  const { host } = await mount(<GrIrView />);
  const galat = q(host, "grir-error");
  expect(galat.textContent).toContain(TEKS_GALAT);
  expect(galat.textContent).toContain("Server sibuk");
  expect(q(host, "grir-empty")).toBeNull();
  mockGet.mockResolvedValueOnce({ data: { ...ISI, items: [], total: 0, total_balance: 0, ledger_balance: 0, unlinked_balance: 0 } });
  await click([...galat.querySelectorAll("button")].find((b) => /Coba lagi/.test(b.textContent)));
  expect(q(host, "grir-error")).toBeNull();
  expect(q(host, "grir-empty").textContent).toBe(TEKS_KOSONG);
});

test("kolom, status ikon+teks, kaki tabel, jurnal tak terhubung merah, tautan PO", async () => {
  mockGet.mockResolvedValue({ data: ISI });
  const open = jest.fn();
  const { host } = await mount(<GrIrView />, { open });
  const kepala = [...q(host, "grir-table").querySelectorAll("thead th")].map((th) => th.textContent);
  expect(kepala).toEqual(["PO", "Pemasok", "Status PO", "Nilai diterima", "Sudah ditagih", "Diretur", "Dikliring",
    "Sisa GR/IR", "Umur (hari)", "Aksi"]);
  expect(q(host, "grir-table").className).toContain("head-wrap");
  expect([...q(host, "grir-table").querySelectorAll("thead th")].pop().className).toContain("col-sticky-end");
  const pil = q(q(host, "grir-row-po_1"), "grir-po-status");
  expect(pil.className).toContain("status-pill");
  expect(pil.querySelector("svg")).not.toBeNull();
  expect(pil.textContent).toBe("Ditutup-kurang");
  expect(q(host, "grir-row-po_2").textContent).not.toContain("receiving");
  expect(q(host, "grir-variance-po_2").textContent).toMatch(/termasuk selisih harga Rp\s100\.000/);
  expect(q(host, "grir-total").textContent).toMatch(/-Rp\s90\.000|−Rp\s90\.000|Rp\s-90\.000/);
  expect(q(host, "grir-ledger").textContent).toMatch(/95\.000/);
  expect(q(host, "grir-unlinked").className).toContain("text-kn-danger-text");
  expect(q(host, "grir-unlinked").textContent).toMatch(/5\.000 berasal dari jurnal yang tidak terhubung ke PO\./);
  await click(q(host, "grir-open-po_1"));
  expect(open).toHaveBeenCalledWith(expect.objectContaining({ focus_type: "purchase_order", focus_id: "po_1", number: "PO/001" }));
});

test("Kliring hanya untuk baris boleh + accounting.manage; baris lain menulis alasan", async () => {
  mockGet.mockResolvedValue({ data: ISI });
  const { host } = await mount(<GrIrView />);
  expect(q(host, "grir-clear-po_1")).not.toBeNull();
  expect(q(host, "grir-clear-po_2")).toBeNull();
  expect(q(host, "grir-why-po_2").textContent).toBe("PO masih berjalan");
  expect(q(host, "grir-no-manage")).toBeNull();
  document.body.innerHTML = "";
  setAccessContext({ role: "finance", permissions: { vendor_bill: ["view"], accounting: ["view"] } });
  const b = await mount(<GrIrView />);
  expect(q(b.host, "grir-clear-po_1")).toBeNull();
  expect(q(b.host, "grir-no-manage").textContent).toBe("Kliring butuh akses kelola Akuntansi.");
});

test("alasan tidak bisa dikliring", () => {
  expect(alasanTidakKliring({ ...BARIS_BOLEH, balance: 0 }, true)).toBe("Sisa sudah nol");
  expect(alasanTidakKliring(BARIS_JALAN, true)).toBe("PO masih berjalan");
  expect(alasanTidakKliring({ ...BARIS_BOLEH, open_bill_number: "VB-9" }, true)).toBe("Faktur VB-9 belum diposting");
  expect(alasanTidakKliring(BARIS_BOLEH, false)).toBe("Akun selisih belum diatur");
  expect(alasanTidakKliring(BARIS_BOLEH, true)).toBe("");
});

test("akun selisih belum diatur → pemberitahuan tertulis", async () => {
  mockGet.mockResolvedValue({ data: { ...ISI, mapping_ready: false } });
  const { host } = await mount(<GrIrView />);
  expect(q(host, "grir-mapping-missing").textContent).toContain("Pengaturan › Keuangan & Pajak › Pemetaan Akun");
});

test("dialog kliring menyebut nominal, PO, PT; alasan wajib; kirim ber-Idempotency-Key lalu muat ulang", async () => {
  mockGet.mockResolvedValue({ data: ISI });
  mockAsk.mockResolvedValueOnce("satu meter tidak ditagih pemasok");
  mockPost.mockResolvedValueOnce({ data: { clearing: { gl_status: "posted" }, balance: 0 } });
  const { host } = await mount(<GrIrView />);
  const n = mockGet.mock.calls.length;
  await click(q(host, "grir-clear-po_1"));
  const opts = mockAsk.mock.calls[0][0];
  expect(opts.title).toBe("Kliring sisa GR/IR?");
  expect(opts.message).toMatch(/^Sisa GR\/IR Rp\s10\.000 pada PO PO\/001 \(PT Kain Suka Cita\) akan dipindahkan ke akun selisih harga pembelian\. Tindakan ini menerbitkan jurnal\.$/);
  expect([opts.reasonLabel, opts.confirmLabel, opts.cancelLabel]).toEqual(["Alasan", "Kliring", "Batal"]);
  const [url, body, cfg] = mockPost.mock.calls[0];
  expect(url).toBe("/api/finance/gr-ir/po_1/clear");
  expect(body).toEqual({ reason: "satu meter tidak ditagih pemasok" });
  expect(cfg.headers["Idempotency-Key"]).toMatch(/^grir-/);
  expect(mockGet.mock.calls.length).toBe(n + 1);
  expect(q(host, "grir-msg").textContent).toContain("dikliring, jurnal terbit");
});

test("dialog dibatalkan → tidak ada kiriman", async () => {
  mockGet.mockResolvedValue({ data: ISI });
  mockAsk.mockResolvedValueOnce(null);
  const { host } = await mount(<GrIrView />);
  await click(q(host, "grir-clear-po_1"));
  expect(mockPost).not.toHaveBeenCalled();
});

test("saringan Umur dan sakelar 'Tampilkan yang sudah nol' dikirim ke server", async () => {
  mockGet.mockResolvedValue({ data: ISI });
  const { host } = await mount(<GrIrView />);
  expect(mockGet.mock.calls[0][1].params).toMatchObject({ status: "terbuka", page: 1, page_size: 50 });
  await click(q(host, "grir-umur->90"));
  expect(mockGet.mock.calls.at(-1)[1].params).toMatchObject({ bucket: ">90", status: "terbuka" });
  await act(async () => { q(host, "grir-show-zero").click(); });
  await settle();
  expect(mockGet.mock.calls.at(-1)[1].params).toMatchObject({ bucket: ">90", status: "semua" });
});

test("rincian faktur: selisih harga terhadap PO", async () => {
  const a = await mount(<PriceVarianceRow bill={{ price_variance_amount: 0 }} />);
  expect(q(a.host, "vb-price-variance")).toBeNull();
  document.body.innerHTML = "";
  const b = await mount(<PriceVarianceRow bill={{ price_variance_amount: 100000, price_variance_posted: true }} />);
  expect(q(b.host, "vb-price-variance-amount").textContent).toMatch(/Rp\s100\.000/);
  expect(q(b.host, "vb-price-variance-unposted")).toBeNull();
  document.body.innerHTML = "";
  const c = await mount(<PriceVarianceRow bill={{ price_variance_amount: -50000, price_variance_posted: false }} />);
  expect(q(c.host, "vb-price-variance-unposted").textContent).toBe(
    "Selisih ini masih berada di akun GR/IR karena akun \"Selisih harga pembelian\" belum diatur di Pemetaan Akun.");
});
