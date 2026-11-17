// PK-18 (UX-04, L8) — sisi layar tanpa peramban:
//  · Panel Posting Gagal membedakan tiga keadaan: memuat · galat (kotak merah + Coba lagi, TANPA "Semua posting tercatat")
//    · kosong (hanya sesudah muat berhasil). Saringan jenis dari `labels`/`counts` server, kolom "PT", nomor = tautan.
//  · Ulang Posting mati (alasan tertulis) bagi yang tidak memegang `accounting.manage`.
//  · JournalStatusBadge: terbit → buka jurnal; gagal → ke Posting Gagal (pemegang accounting.view); diproses; lainnya
//    tidak tampil. Ikon + teks + warna.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import PostingFailuresView, { TEKS_GALAT, TEKS_KOSONG, KETERANGAN } from "../finance/PostingFailuresView";
import JournalStatusBadge, { JournalStatusBar } from "../../components/JournalStatusBadge";
import { AppNavProvider } from "../../context/AppNavContext";
import { setAccessContext } from "../../config/roles";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../components/KNSelect", () => {   // pola UI 16 Nov — saringan jenis = dropdown → <select> setara
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange?.(e.target.value)}>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({ askConfirm: () => Promise.resolve(true) }));
jest.mock("../../components/EntityBadge", () => (p) => <span data-testid="pt">{p.entityId}</span>);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function settle() { for (let i = 0; i < 4; i += 1) await act(async () => {}); }
async function mount(el, nav = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(<AppNavProvider role="admin" onNavigateTo={nav.go} onOpenDocument={nav.open}>{el}</AppNavProvider>);
  });
  await settle();
  return { host, root };
}
// Pola UI 16 Nov — saringan chip kini dropdown (FilterSelect); pilih nilai seperti pengguna memilih opsi.
async function pilih(el, v) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(el, v);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await act(async () => {}); await act(async () => {});
}

async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
}

const BARIS = {
  kind: "vendor_bill", kind_label: "Faktur Pemasok", id: "vb_1", number: "VB/001", entity_id: "ent_ksc",
  amount: 11100000, error: "Akun 2-1100 nonaktif", failed_at: "2026-11-14T01:00:00+00:00",
  link: { view: "vendor-bills", tab: "", focus_type: "vendor_bill", focus_id: "vb_1", number: "VB/001" },
};
const ISI = { items: [BARIS], total: 1, counts: { vendor_bill: 1, cash_transaction: 0 },
  labels: { vendor_bill: "Faktur Pemasok", cash_transaction: "Transaksi Kas" }, page: 1, page_size: 50 };

beforeEach(() => setAccessContext({ role: "admin" }));
afterEach(() => { mockGet.mockReset(); mockPost.mockReset(); document.body.innerHTML = ""; });

test("U15 — galat muat: kotak merah + Coba lagi, teks kosong TIDAK tampil", async () => {
  mockGet.mockRejectedValueOnce({ response: { status: 503, data: { detail: "Server sedang tidak bisa dihubungi" } } });
  const { host } = await mount(<PostingFailuresView />);
  const galat = q(host, "pf-error");
  expect(galat).not.toBeNull();
  expect(galat.textContent).toContain(TEKS_GALAT);
  expect(galat.textContent).toContain("Server sedang tidak bisa dihubungi");
  expect(q(host, "pf-empty")).toBeNull();
  expect(host.textContent).not.toContain("Semua posting tercatat");
  mockGet.mockResolvedValueOnce({ data: { ...ISI, items: [], total: 0, counts: {} } });
  const coba = [...galat.querySelectorAll("button")].find((b) => /Coba lagi/.test(b.textContent));
  await click(coba);
  expect(q(host, "pf-error")).toBeNull();
  expect(q(host, "pf-empty").textContent).toBe(TEKS_KOSONG);
});

test("memuat: teks memuat, tanpa teks kosong", async () => {
  mockGet.mockImplementation(() => new Promise(() => {}));
  const { host } = await mount(<PostingFailuresView />);
  expect(q(host, "pf-loading").textContent).toContain("Memuat daftar posting gagal…");
  expect(q(host, "pf-empty")).toBeNull();
});

test("daftar: keterangan, saringan dari server (jenis 0 disembunyikan), kolom PT, nomor = tautan, ulang", async () => {
  mockGet.mockResolvedValue({ data: ISI });
  const open = jest.fn();
  const { host } = await mount(<PostingFailuresView />, { open });
  expect(q(host, "pf-keterangan").textContent).toBe(KETERANGAN);
  const pfOpt = (v) => [...q(host, "pf-filter").options].find((o) => o.value === v) || null;
  expect(pfOpt("vendor_bill").textContent).toContain("Faktur Pemasok");
  expect(pfOpt("cash_transaction")).toBeNull();
  const kepala = [...q(host, "pf-table").querySelectorAll("th")].map((t) => t.textContent);
  expect(kepala).toContain("PT");
  expect(kepala).not.toContain("Entitas");
  await click(q(host, "pf-open-vb_1"));
  expect(open).toHaveBeenCalledWith(expect.objectContaining({ view: "vendor-bills", focus_id: "vb_1" }));
  expect(mockGet.mock.calls[0][1].params).toEqual(expect.objectContaining({ page: 1, page_size: 50 }));
  await pilih(q(host, "pf-filter"), "vendor_bill");
  expect(mockGet.mock.calls.at(-1)[1].params).toEqual(expect.objectContaining({ kind: "vendor_bill", page: 1 }));
  mockPost.mockResolvedValueOnce({ data: { kind: "vendor_bill", id: "vb_1", gl_status: "posted" } });
  await click(q(host, "pf-retry-vb_1"));
  expect(mockPost).toHaveBeenCalledWith("/api/finance/posting-failures/vendor_bill/vb_1/retry");
  expect(q(host, "pf-msg").textContent).toContain("jurnal terbit");
});

test("tanpa accounting.manage: Ulang Posting mati dengan alasan tertulis", async () => {
  setAccessContext({ role: "finance", permissions: { accounting: ["view"] } });
  mockGet.mockResolvedValue({ data: ISI });
  const { host } = await mount(<PostingFailuresView />);
  expect(q(host, "pf-retry-vb_1").disabled).toBe(true);
  expect(q(host, "pf-no-manage").textContent).toContain("akses kelola Akuntansi");
});

test("U16 — lencana jurnal: gagal → Posting Gagal; terbit → buka jurnal; status lain tidak tampil", async () => {
  const go = jest.fn();
  const open = jest.fn();
  const { host } = await mount(
    <div>
      <JournalStatusBar doc={{ gl_status: "failed", gl_error: "Akun 2-1100 nonaktif" }} testId="j-gagal" />
      <JournalStatusBadge status="posted" journalEntryId="je_1" testId="j-terbit" />
      <JournalStatusBadge status="pending" testId="j-proses" />
      <JournalStatusBadge status="not_required" testId="j-tidak" />
      <JournalStatusBadge testId="j-lama" />
    </div>, { go, open });
  expect(q(host, "j-gagal").textContent).toBe("Jurnal gagal");
  expect(q(host, "j-gagal").getAttribute("title")).toContain("Akun 2-1100 nonaktif");
  expect(q(host, "j-gagal-error").textContent).toBe("Akun 2-1100 nonaktif");
  expect(q(host, "j-gagal").querySelector("svg")).not.toBeNull();
  await click(q(host, "j-gagal"));
  expect(go).toHaveBeenCalledWith("posting-failures", expect.anything());
  expect(q(host, "j-terbit").textContent).toBe("Jurnal terbit");
  await click(q(host, "j-terbit"));
  expect(open).toHaveBeenCalledWith(expect.objectContaining({ view: "general-ledger", focus_type: "journal_entry",
    focus_id: "je_1" }));
  expect(q(host, "j-proses").textContent).toBe("Jurnal diproses");
  expect(q(host, "j-tidak")).toBeNull();
  expect(q(host, "j-lama")).toBeNull();
});

test("lencana gagal tanpa accounting.view: tidak bisa diklik ke Posting Gagal", async () => {
  setAccessContext({ role: "purchasing", permissions: { vendor_bill: ["view"] } });
  const { host } = await mount(<JournalStatusBadge status="failed" error="x" testId="j" />);
  expect(q(host, "j").tagName).toBe("SPAN");
});
