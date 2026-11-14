// PK-43 — empat alur layar keuangan tanpa pindah menu (spesifikasi `docs/blueprint/unit/PK-43.md`). Uji komponen:
//   U4  pop-up Pelunasan Antar-PT: kandidat dari `GET /interco/payment-schedule` (PT aktif = pembayar), tanggal hari ini,
//       kirim memuat `settle_date` + `bank_account_id` + Idempotency-Key, konfirmasi menyebut jumlah/nominal/PT/tanggal;
//   U15 rincian Piutang: tombol Catat Pembayaran menurut izin `ar_receipt.create`; "Semua PT" → mati + alasan tertulis;
//   telusur Laporan Keuangan → Buku Besar (preset) → rincian jurnal → dokumen sumber, tombol kembali ke laporan;
//   panel Daftar Periksa Tutup Buku (ringkasan, status ikon + teks, nilai antar-PT, Buka).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { AppNavProvider } from "../../context/AppNavContext";
import { ViewPresetProvider } from "../../context/ViewPresetContext";
import { setAccessContext } from "../../config/roles";
import IntercoSettlementModal from "../finance/interco/IntercoSettlementModal";
import ARAgingDetail from "../finance/ARAgingDetail";
import { SectionBlock, BsLine } from "../finance/FinancialStatementsParts";
import GeneralLedger from "../finance/GeneralLedger";
import JournalDetailModal from "../finance/JournalDetailModal";
import ClosingChecklistPanel, { checklistSummary, checklistWarnings, intercoValueText } from "../finance/ClosingChecklistPanel";
import FinancialStatementsView from "../finance/FinancialStatementsView";
import ClosingView from "../finance/ClosingView";
import useAppNavigation from "../../hooks/useAppNavigation";
import { todayWib } from "../../utils/formatters";

beforeAll(() => setAccessContext({ role: "admin" }));
afterAll(() => setAccessContext(null));

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockConfirm = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    put: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: (...a) => mockConfirm(...a), askReason: jest.fn(async () => null), askText: jest.fn(async () => null),
  askChoice: jest.fn(async () => null), default: {},
}));
jest.mock("../../config/paymentMethods", () => ({
  __esModule: true,
  usePaymentMethods: () => ({ methods: [{ code: "transfer", name: "Transfer bank", needs_account: "bank" }] }),
}));
jest.mock("../../components/KNSelect", () => {
  const Sel = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={!!p.disabled}
      onChange={(e) => p.onValueChange?.(e.target.value)}>
      <option value="">—</option>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: Sel, KNSelect: Sel };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange?.(e.target.value)} />,
  formatDateId: (v) => String(v || ""),
}));
jest.mock("../../components/StoreCreditBadge", () => () => null);
jest.mock("../finance/payments/PenaltyPanel", () => () => <div data-testid="stub-penalty-panel" />);
jest.mock("recharts", () => {
  const Box = () => <div />;
  return new Proxy({}, { get: () => Box });
});
jest.mock("../../components/AskKnButton", () => ({ __esModule: true, AskKnButton: () => null, PENDING_KEY: "kn_tanya_pending" }));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function settle() { for (let i = 0; i < 4; i += 1) await act(async () => {}); }
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await settle();
  return { host, root };
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
}
async function pilih(el, value) {
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set;
    setter.call(el, value);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await settle();
}
afterEach(() => { mockGet.mockReset(); mockPost.mockReset(); mockConfirm.mockReset(); document.body.innerHTML = ""; });

const ENTS = [{ id: "ent_ksc", short_name: "Sukacita" }, { id: "ent_kanda", short_name: "Kanda" }];

// ── U4 ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
test("U4 — Pelunasan Antar-PT: PT aktif pembayar, kandidat dari server, kirim bertanggal & berekening", async () => {
  const rows = [
    { interco_id: "ict1_s", number: "ICT-1", doc_date: "2026-10-05", due_date: "2026-11-04", grand_total: 22200000,
      remaining: 17200000, outstanding: 17200000, settleable: true },
    { interco_id: "ict2_s", number: "ICT-2", doc_date: "2026-10-09", due_date: "", grand_total: 3000000,
      remaining: 3000000, outstanding: 3000000, settleable: true },
  ];
  mockGet.mockImplementation((url) => Promise.resolve({
    data: url.includes("/bank-accounts")
      ? [{ id: "ba_kanda", name: "Bank Kanda", entity_id: "ent_kanda", is_active: true, cash_type: "kas_besar" },
        { id: "kk_kanda", name: "Kas Kecil Kanda", entity_id: "ent_kanda", is_active: true, cash_type: "kas_kecil" }]
      : { rows, config: { require_full_payment: true } } }));
  mockConfirm.mockResolvedValue(true);
  mockPost.mockResolvedValue({ data: { id: "ics_1" } });
  const onCreated = jest.fn();
  const r = await mount(<IntercoSettlementModal entities={ENTS} presetPayerEntityId="ent_kanda"
    onClose={() => {}} onCreated={onCreated} />);
  expect(q(r.host, "interco-settle-modal").textContent).toContain("Pelunasan Antar-PT");
  expect(q(r.host, "interco-settle-empty").textContent).toContain("Pilih PT pembayar dan PT penerima dulu.");
  await pilih(q(r.host, "interco-settle-payee"), "ent_ksc");
  const sched = mockGet.mock.calls.find(([u]) => u === "/api/interco/payment-schedule");
  expect(sched[1].params).toEqual({ payer_entity_id: "ent_kanda", payee_entity_id: "ent_ksc" });
  expect(q(r.host, "interco-settle-cand-ict1_s")).not.toBeNull();
  expect(q(r.host, "interco-settle-cand-ict2_s")).not.toBeNull();
  expect(q(r.host, "interco-settle-date").value).toBe(todayWib());
  // rekening: hanya rekening bank PT pembayar (Kas Kecil tidak dipakai pelunasan antar-PT)
  const opsi = [...q(r.host, "interco-settle-account").querySelectorAll("option")].map((o) => o.value);
  expect(opsi).toEqual(["", "ba_kanda"]);
  expect(q(r.host, "interco-settle-submit").disabled).toBe(true);
  expect(q(r.host, "interco-settle-reason").textContent).toContain("Centang minimal satu tagihan");
  // cari nomor tagihan menyaring baris; pilihan tetap
  const cari = q(r.host, "interco-settle-search");
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(cari, "ICT-2");
    cari.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await settle();
  expect(q(r.host, "interco-settle-cand-ict1_s")).toBeNull();
  expect(q(r.host, "interco-settle-cand-ict2_s")).not.toBeNull();
  await click(q(r.host, "interco-settle-search-clear"));
  await click(q(r.host, "interco-settle-check-ict1_s"));
  expect(q(r.host, "interco-settle-amount-ict1_s").textContent).toMatch(/17\.200\.000/);
  await click(q(r.host, "interco-settle-submit"));
  expect(mockConfirm.mock.calls[0][0].message).toMatch(
    /^Lunasi 1 tagihan senilai Rp\s?17\.200\.000 dari Kanda ke Sukacita pada .+\?$/);
  const [url, body, cfg] = mockPost.mock.calls[0];
  expect(url).toBe("/api/interco/settlements");
  expect(body).toMatchObject({ payer_entity_id: "ent_kanda", payee_entity_id: "ent_ksc", settle_date: todayWib(),
    bank_account_id: "ba_kanda", method: "transfer", transactions: [{ interco_id: "ict1_s", applied_amount: 17200000 }] });
  expect(cfg.headers["Idempotency-Key"]).toMatch(/^ic-stl-/);
  expect(onCreated).toHaveBeenCalled();
});

test("U4 (b) — kandidat: memuat, galat + Coba lagi, kosong; baris berjurnal gagal tidak bisa dicentang", async () => {
  let gagal = true;
  mockGet.mockImplementation((url) => {
    if (url.includes("/bank-accounts")) return Promise.resolve({ data: [] });
    if (gagal) return Promise.reject({ response: { status: 500, data: { detail: "server sibuk" } } });
    return Promise.resolve({ data: { rows: [{ interco_id: "x_s", number: "ICT-X", grand_total: 5, remaining: 5,
      outstanding: 5, settleable: false, settle_block_reason: "Jurnal transaksi ini masih gagal terbit." }] } });
  });
  const r = await mount(<IntercoSettlementModal entities={ENTS} presetPayerEntityId="ent_kanda"
    presetPayeeEntityId="ent_ksc" onClose={() => {}} />);
  const err = q(r.host, "interco-settle-load-error");
  expect(err.textContent).toContain("server sibuk");
  gagal = false;
  const retry = [...err.querySelectorAll("button")].find((b) => /Coba lagi/.test(b.textContent));
  await click(retry);
  expect(q(r.host, "interco-settle-check-x_s").disabled).toBe(true);
  expect(q(r.host, "interco-settle-block-x_s").textContent).toContain("masih gagal terbit");
  expect(q(r.host, "interco-settle-reason").textContent).toContain("Centang minimal satu tagihan");
});

// ── U15 ────────────────────────────────────────────────────────────────────────────────────────────────────────────
const DETAIL = { customer_name: "Toko Uji", entity_id: "ent_ksc", totals: { total: 500000 },
  items: [{ order_id: "so1", order_number: "SO-1", grand_total: 500000, paid_total: 0, outstanding: 500000 }],
  penalties: [] };

test("U15 — Catat Pembayaran: tampil aktif berizin; tersembunyi tanpa izin; Semua PT mati + alasan tertulis", async () => {
  const onPay = jest.fn();
  const berizin = { permissions: { ar_receipt: ["create"] } };
  let r = await mount(<ARAgingDetail detail={DETAIL} customerId="c1" currentUser={berizin} selectedEntity="ent_ksc"
    onPay={onPay} onClose={() => {}} />);
  const btn = q(r.host, "ar-aging-pay");
  expect(btn.disabled).toBe(false);
  await click(btn);
  expect(onPay).toHaveBeenCalledWith();
  await click(q(r.host, "ar-aging-pay-so1"));
  expect(onPay).toHaveBeenLastCalledWith("so1");
  expect(q(r.host, "ar-aging-pay-scope-note")).toBeNull();
  await act(async () => { r.root.unmount(); });

  r = await mount(<ARAgingDetail detail={DETAIL} customerId="c1" currentUser={{ permissions: { ar_receipt: ["view"] } }}
    selectedEntity="ent_ksc" onPay={onPay} onClose={() => {}} />);
  expect(q(r.host, "ar-aging-pay")).toBeNull();
  expect(q(r.host, "ar-aging-pay-so1")).toBeNull();
  await act(async () => { r.root.unmount(); });

  onPay.mockClear();
  r = await mount(<ARAgingDetail detail={DETAIL} customerId="c1" currentUser={berizin} selectedEntity="all"
    onPay={onPay} onClose={() => {}} />);
  const mati = q(r.host, "ar-aging-pay");
  expect(mati.disabled).toBe(true);
  expect(q(r.host, "ar-aging-pay-scope-note").textContent)
    .toContain("Pilih satu PT dulu (kanan atas) untuk mencatat pembayaran.");
  await click(mati);
  expect(onPay).not.toHaveBeenCalled();
});

test("U15 (b) — pemberitahuan sukses form kwitansi tampil di rincian", async () => {
  const r = await mount(<ARAgingDetail detail={DETAIL} customerId="c1" currentUser={{ permissions: { ar_receipt: ["create"] } }}
    selectedEntity="ent_ksc" onPay={() => {}} notice="Pembayaran RC-1 (Rp 500.000) dicatat untuk Toko Uji." onClose={() => {}} />);
  expect(q(r.host, "ar-aging-detail-notice").textContent).toContain("RC-1");
});

// ── Telusur laporan → buku besar → jurnal → dokumen ───────────────────────────────────────────────────────────────
test("Telusur — baris akun Laba-Rugi/Neraca menjadi tautan; tanpa onLine tetap teks", async () => {
  const onLine = jest.fn();
  const r = await mount(<table><tbody>
    <SectionBlock section={{ key: "opex", label: "Beban", total: 70, lines: [{ code: "6-2000", name: "Beban Sewa", amount: 70 }] }}
      onLine={onLine} />
    <BsLine line={{ code: "1-1100", name: "Kas", amount: 5 }} isComp={false} />
  </tbody></table>);
  const a = q(r.host, "fs-line-6-2000");
  expect(a.getAttribute("title")).toBe("Lihat mutasi akun ini");
  await click(a);
  expect(onLine).toHaveBeenCalledWith("6-2000");
  expect(q(r.host, "fs-line-1-1100")).toBeNull();
  expect(q(r.host, "fs-bs-line-1-1100").textContent).toContain("Kas");
});

const LEDGER = {
  account: { code: "6-2000", name: "Beban Sewa" }, opening_balance: 30, period: { start: "2026-10-01", end: "2026-10-31" },
  total_debit: 50, total_credit: 10, balance: 70, count: 2,
  lines: [
    { entry_id: "je3", number: "JE-3", date: "2026-10-20", description: "koreksi", debit: 0, credit: 10, running_balance: 70 },
    { entry_id: "je2", number: "JE-2", date: "2026-10-05", description: "sewa", debit: 50, credit: 0, running_balance: 80 },
  ],
};
const JE2 = { id: "je2", number: "JE-2", date: "2026-10-05", description: "sewa", source_type: "vendor_bill", lines: [],
  total_debit: 50, total_credit: 50, created_by: "uji",
  source_doc: { doc_type: "vendor_bill", doc_id: "vb1", number: "VB-1", label: "Tagihan Pemasok",
    link: { view: "vendor-bills", focus_type: "vendor_bill", focus_id: "vb1", tab: "" }, link_hidden: "" } };

function glRoutes(url) {
  if (url === "/api/gl/accounts/6-2000/ledger") return { data: LEDGER };
  if (url === "/api/gl/journal/je2") return { data: JE2 };
  if (url === "/api/gl/accounts") return { data: [{ code: "6-2000", name: "Beban Sewa", is_postable: true }] };
  if (url === "/api/gl/summary") return { data: { journal_count: 3 } };
  return { data: [] };
}

test("Telusur — buku besar dari Laporan Keuangan: rentang, saldo awal, baris → rincian → dokumen sumber, kembali", async () => {
  mockGet.mockImplementation((url) => Promise.resolve(glRoutes(url)));
  const navTo = jest.fn();
  const onOpenDocument = jest.fn();
  const preset = { view: "general-ledger", nonce: 1, tab: "ledger", code: "6-2000", start: "2026-10-01",
    end: "2026-10-31", from: "financial-statements", fromTab: "pl" };
  const r = await mount(
    <AppNavProvider role="admin" onNavigateTo={navTo} onOpenDocument={() => {}}>
      <ViewPresetProvider preset={preset}>
        <GeneralLedger selectedEntity="ent_ksc" entities={ENTS} onOpenDocument={onOpenDocument} />
      </ViewPresetProvider>
    </AppNavProvider>);
  const led = mockGet.mock.calls.find(([u]) => u === "/api/gl/accounts/6-2000/ledger");
  expect(led[1].params).toEqual({ start: "2026-10-01", as_of: "2026-10-31" });
  expect(q(r.host, "gl-ledger-start").value).toBe("2026-10-01");
  expect(q(r.host, "gl-ledger-end").value).toBe("2026-10-31");
  // baris pertama = saldo awal, lalu mutasi lama → baru
  const baris = [...q(r.host, "gl-ledger").querySelectorAll("tbody tr")].map((tr) => tr.getAttribute("data-testid"));
  expect(baris).toEqual(["gl-ledger-opening", "gl-ledger-row-JE-2", "gl-ledger-row-JE-3"]);
  expect(q(r.host, "gl-ledger-opening").textContent).toMatch(/Saldo awal.*30/);
  await click(q(r.host, "gl-ledger-row-JE-2"));
  expect(q(r.host, "gl-journal-detail")).not.toBeNull();
  expect(q(r.host, "gl-journal-source").textContent).toContain("Tagihan Pemasok VB-1");
  await click(q(r.host, "gl-journal-open-source"));
  const [link] = onOpenDocument.mock.calls[0];
  expect(link).toMatchObject({ view: "vendor-bills", focus_type: "vendor_bill", focus_id: "vb1", number: "VB-1" });
  expect(link.origin).toMatchObject({ view: "general-ledger", preset: { tab: "ledger", code: "6-2000",
    start: "2026-10-01", end: "2026-10-31", from: "financial-statements", fromTab: "pl" } });
  await click(q(r.host, "gl-back-to-report"));
  expect(navTo).toHaveBeenCalledWith("financial-statements",
    expect.objectContaining({ preset: { tab: "pl", start: "2026-10-01", end: "2026-10-31" } }));
});

test("Telusur — buku besar tanpa asal laporan: tanpa tombol kembali; rentang kosong → teks kosong rentang", async () => {
  mockGet.mockImplementation((url) => Promise.resolve(url.endsWith("/ledger")
    ? { data: { ...LEDGER, opening_balance: undefined, lines: [] } } : glRoutes(url)));
  const preset = { view: "general-ledger", nonce: 1, tab: "ledger", code: "6-2000", end: "2026-10-31" };
  const r = await mount(<ViewPresetProvider preset={preset}><GeneralLedger selectedEntity="ent_ksc" entities={ENTS} /></ViewPresetProvider>);
  expect(q(r.host, "gl-back-to-report")).toBeNull();
  expect(q(r.host, "gl-ledger-empty").textContent).toBe("Tidak ada mutasi pada rentang ini.");
});

test("Telusur — rincian jurnal: dokumen di luar PT → teks; jurnal manual → tanpa bilah; dimuat bila belum ada", async () => {
  const luar = { ...JE2, source_doc: { ...JE2.source_doc, link: null, link_hidden: "pt" } };
  let r = await mount(<JournalDetailModal je={luar} sourceMeta={() => ({ label: "Tagihan", tone: "" })}
    onClose={() => {}} onOpenDocument={() => {}} />);
  expect(q(r.host, "gl-journal-source-note").textContent).toBe("Tagihan Pemasok VB-1 — di luar PT Anda");
  expect(q(r.host, "gl-journal-open-source")).toBeNull();
  await act(async () => { r.root.unmount(); });
  r = await mount(<JournalDetailModal je={{ ...JE2, source_type: "manual", source_doc: null }}
    sourceMeta={() => ({ label: "Manual", tone: "" })} onClose={() => {}} onOpenDocument={() => {}} />);
  expect(q(r.host, "gl-journal-source")).toBeNull();
  await act(async () => { r.root.unmount(); });
  mockGet.mockResolvedValue({ data: JE2 });
  const { source_doc: _abaikan, ...tanpa } = JE2;
  r = await mount(<JournalDetailModal je={tanpa} sourceMeta={() => ({ label: "Tagihan", tone: "" })}
    onClose={() => {}} onOpenDocument={() => {}} />);
  expect(mockGet).toHaveBeenCalledWith("/api/gl/journal/je2");
  expect(q(r.host, "gl-journal-open-source")).not.toBeNull();
});

// ── Daftar periksa tutup buku ──────────────────────────────────────────────────────────────────────────────────────
const CEKLIS = {
  period_label: "Oktober 2026", end_date: "2026-10-31", can_close: false,
  items: [
    { key: "periode_berakhir", label: "Periode sudah berakhir", status: "ok", value: null, detail: "Periode berakhir.", link: null },
    { key: "suspense_nol", label: "Saldo akun penampung nol", status: "blocking", value: 10000000, detail: "Saldo Rp 10.000.000",
      link: { view: "general-ledger", preset: { tab: "suspense" } } },
    { key: "posting_gagal", label: "Tidak ada jurnal yang gagal diposting", status: "warning", value: 1,
      detail: "1 dokumen jurnalnya gagal.", link: { view: "posting-failures", preset: null } },
    { key: "antar_pt_cocok", label: "Saldo antar-PT di buku besar sama dengan dokumennya", status: "warning",
      value: { gl_receivable: 18200000, doc_receivable: 17200000, gl_payable: 0, doc_payable: 0 }, detail: "x",
      link: { view: "interco-transactions", preset: { tab: "balances" } } },
    { key: "gaji", label: "Penggajian periode ini sudah diposting", status: "unknown", value: null,
      detail: "Tidak terbaca: hitungan melewati batas waktu 20 detik.", link: null },
  ],
};

test("Daftar periksa — ringkasan, status ikon + teks, nilai antar-PT, Buka membawa asal Tutup Buku", async () => {
  const navTo = jest.fn();
  const r = await mount(<AppNavProvider role="admin" onNavigateTo={navTo} onOpenDocument={() => {}}>
    <ClosingChecklistPanel state="ok" data={CEKLIS} load={() => {}} />
  </AppNavProvider>);
  expect(q(r.host, "closing-checklist-summary").textContent)
    .toBe("1 beres · 2 perlu dilihat · 1 harus diselesaikan · 1 tidak terbaca");
  const sus = q(r.host, "closing-check-suspense_nol-status");
  expect(sus.textContent).toContain("Harus diselesaikan");
  expect(sus.querySelector("svg")).not.toBeNull();
  expect(sus.className).toContain("status-pill");
  expect(q(r.host, "closing-check-periode_berakhir-status").textContent).toContain("Beres");
  expect(q(r.host, "closing-check-posting_gagal-status").textContent).toContain("Perlu dilihat");
  expect(q(r.host, "closing-check-gaji-status").textContent).toContain("Tidak terbaca");
  expect(q(r.host, "closing-check-antar_pt_cocok-value").textContent).toBe(intercoValueText(CEKLIS.items[3].value));
  expect(intercoValueText(CEKLIS.items[3].value)).toMatch(
    /^Piutang: buku Rp\s?18\.200\.000 · dokumen Rp\s?17\.200\.000 · selisih Rp\s?1\.000\.000 — Utang: buku Rp\s?0 · dokumen Rp\s?0 · selisih Rp\s?0$/);
  expect(q(r.host, "closing-check-periode_berakhir-open")).toBeNull();
  await click(q(r.host, "closing-check-suspense_nol-open"));
  expect(navTo).toHaveBeenCalledWith("general-ledger",
    expect.objectContaining({ preset: { tab: "suspense", from: { view: "closing" } } }));
  expect(checklistSummary([])).toBe("0 beres · 0 perlu dilihat · 0 harus diselesaikan");
  expect(checklistWarnings(CEKLIS)).toEqual(["Tidak ada jurnal yang gagal diposting: 1 dokumen jurnalnya gagal.",
    "Saldo antar-PT di buku besar sama dengan dokumennya: x"]);
});

test("Daftar periksa — memuat, galat + Coba lagi, kosong dibedakan; belum dimuat = tidak tampil", async () => {
  const load = jest.fn();
  let r = await mount(<ClosingChecklistPanel state="idle" data={null} load={load} />);
  expect(q(r.host, "closing-checklist")).toBeNull();
  await act(async () => { r.root.unmount(); });
  r = await mount(<ClosingChecklistPanel state="loading" data={null} load={load} />);
  expect(q(r.host, "closing-checklist-loading")).not.toBeNull();
  await act(async () => { r.root.unmount(); });
  r = await mount(<ClosingChecklistPanel state="error" data={null} error="" load={load} />);
  const err = q(r.host, "closing-checklist-error");
  expect(err.textContent).toContain("Daftar periksa gagal dimuat.");
  await click([...err.querySelectorAll("button")].find((b) => /Coba lagi/.test(b.textContent)));
  expect(load).toHaveBeenCalled();
  await act(async () => { r.root.unmount(); });
  r = await mount(<ClosingChecklistPanel state="ok" data={{ items: [] }} load={load} />);
  expect(q(r.host, "closing-checklist-empty")).not.toBeNull();
  expect(q(r.host, "closing-checklist-summary")).toBeNull();
});


// ── Laporan Keuangan: klik akun → preset buku besar; kembali → periode yang sama ─────────────────────────────────────
const IS = { revenue_total: 0, gross_profit: 0, net_income: -70, net_margin: 0, gross_margin: 0,
  sections: [{ key: "opex", label: "Beban Operasional", total: 70, lines: [{ code: "6-2000", name: "Beban Sewa", amount: 70 }] }] };
const BS = { assets_total: 5, liabilities_total: 0, equity_total: 5, balanced: true, comparative: false,
  assets: { sections: [{ key: "cur", label: "Aset Lancar", total: 5, lines: [{ code: "1-1100", name: "Kas", amount: 5 }] }] },
  liabilities: { sections: [] }, equity: { lines: [], current_earnings: 5 } };

test("Telusur — Laba-Rugi: rentang yang dikembalikan buku besar dipakai, klik akun membawa rentangnya", async () => {
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.includes("income-statement") ? IS : BS }));
  const navTo = jest.fn();
  const r = await mount(<AppNavProvider role="admin" onNavigateTo={navTo} onOpenDocument={() => {}}>
    <ViewPresetProvider preset={{ view: "financial-statements", nonce: 2, tab: "pl", start: "2026-10-01", end: "2026-10-31" }}>
      <FinancialStatementsView selectedEntity="ent_ksc" />
    </ViewPresetProvider>
  </AppNavProvider>);
  const is = mockGet.mock.calls.find(([u]) => u === "/api/finance/income-statement");
  expect(is[1].params).toMatchObject({ start: "2026-10-01", end: "2026-10-31" });
  await click(q(r.host, "fs-line-6-2000"));
  expect(navTo).toHaveBeenCalledWith("general-ledger", expect.objectContaining({ preset: { tab: "ledger",
    code: "6-2000", start: "2026-10-01", end: "2026-10-31", from: "financial-statements", fromTab: "pl" } }));
});

test("Telusur — Neraca: tanggal neraca dikembalikan; klik akun mengirim end tanpa start", async () => {
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.includes("balance-sheet") ? BS : IS }));
  const navTo = jest.fn();
  const r = await mount(<AppNavProvider role="admin" onNavigateTo={navTo} onOpenDocument={() => {}}>
    <ViewPresetProvider preset={{ view: "financial-statements", nonce: 3, tab: "bs", start: "", end: "2026-10-31" }}>
      <FinancialStatementsView selectedEntity="ent_ksc" />
    </ViewPresetProvider>
  </AppNavProvider>);
  const bs = mockGet.mock.calls.find(([u]) => u === "/api/finance/balance-sheet");
  expect(bs[1].params).toMatchObject({ as_of: "2026-10-31" });
  await click(q(r.host, "fs-line-1-1100"));
  const [, opts] = navTo.mock.calls[0];
  expect(opts.preset).toEqual({ tab: "ledger", code: "1-1100", end: "2026-10-31", from: "financial-statements", fromTab: "bs" });
});

function NavHarness({ out }) {
  out.current = useAppNavigation({ role: "admin", setSidebarOpen: () => {} });
  return null;
}

test("Telusur — kembali dari dokumen sumber membuka buku besar dengan preset yang sama", async () => {
  localStorage.setItem("kn_user", JSON.stringify({ role: "admin" }));
  const out = { current: null };
  await mount(<NavHarness out={out} />);
  await act(async () => { out.current.handleNavSelect("general-ledger", "general-ledger"); });
  const preset = { tab: "ledger", code: "6-2000", start: "2026-10-01", end: "2026-10-31" };
  await act(async () => { out.current.openDocument({ view: "vendor-bills", focus_type: "vendor_bill", focus_id: "vb1",
    number: "VB-1", origin: { view: "general-ledger", preset } }); });
  expect(out.current.activeView).toBe("vendor-bills");
  expect(out.current.backTo).toMatchObject({ view: "general-ledger", at: "vendor-bills" });
  await act(async () => { out.current.goBack(out.current.backTo); });
  expect(out.current.activeView).toBe("general-ledger");
  expect(out.current.viewPreset).toMatchObject({ view: "general-ledger", ...preset });
});

// ── Tutup Buku: daftar periksa dimuat bersama Pratinjau; butir peringatan ikut di konfirmasi ─────────────────────────
test("Tutup Buku — Pratinjau memuat daftar periksa; konfirmasi menyebut butir 'perlu dilihat'", async () => {
  const PV = { period_label: "Oktober 2026", period_ended: true, can_close: true, net_income: 0, residual_net_income: 0,
    revenue_total: 0, expense_total: 0, closing_lines: [], suspense_balance: 0, suspense_warning: false };
  const DATA = { ...CEKLIS, can_close: true, items: CEKLIS.items.filter((it) => it.status !== "blocking") };
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/checklist") ? DATA
    : url.endsWith("/preview") ? PV : [] }));
  mockConfirm.mockResolvedValue(false);
  const admin = { role: "admin", permissions: { accounting: ["view", "manage"] } };
  const r = await mount(<AppNavProvider role="admin" onNavigateTo={() => {}} onOpenDocument={() => {}}>
    <ClosingView selectedEntity="ent_ksc" entities={ENTS} currentUser={admin} />
  </AppNavProvider>);
  expect(q(r.host, "closing-checklist")).toBeNull();
  await click(q(r.host, "closing-preview-btn"));
  const call = mockGet.mock.calls.find(([u]) => u === "/api/finance/closing/checklist");
  expect(call[1].params).toMatchObject({ entity_id: "ent_ksc", period_type: "month" });
  expect(q(r.host, "closing-checklist-summary").textContent).toBe("1 beres · 2 perlu dilihat · 0 harus diselesaikan · 1 tidak terbaca");
  // urutan layar: pemilih periode → daftar periksa → pratinjau
  const box = q(r.host, "closing-checklist");
  expect(box.compareDocumentPosition(q(r.host, "closing-preview")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  await click(q(r.host, "closing-close-btn"));
  const msg = mockConfirm.mock.calls[0][0].message;
  const host = document.createElement("div");
  const root = createRoot(host);
  await act(async () => { root.render(msg); });
  expect(host.textContent).toContain("Tidak ada jurnal yang gagal diposting: 1 dokumen jurnalnya gagal.");
  expect(mockPost).not.toHaveBeenCalled();
});
