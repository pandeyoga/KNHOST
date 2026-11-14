// PK-36 (IC-06) — akun kontrol di layar (uji komponen; uji jalan U17 di peramban belum dilakukan).
//  · Jurnal Manual Baru: akun ber-`manual_allowed: false` tidak ada di pilihan akun; kalimat keterangan tampil hanya
//    bila ada akun yang disembunyikan.
//  · Tab Suspense: akun tujuan reklasifikasi memakai saringan yang sama.
//  · Rincian jurnal: galat 422 pembalikan tampil di DALAM pop-up alasan pembalikan.
//  · Bagan Akun: lencana "Akun kontrol" + petunjuk "Hanya berubah lewat dokumen {buku pembantu}".
//  · Buku Besar: bagan akun dimuat untuk PT yang sedang dibuka (tanda akun kontrol mengikuti pengaturan PT itu).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { AppNavProvider } from "../../context/AppNavContext";
import JournalEntryModal from "../finance/JournalEntryModal";
import JournalDetailModal from "../finance/JournalDetailModal";
import SuspensePanel from "../finance/SuspensePanel";
import ChartOfAccounts from "../finance/ChartOfAccounts";
import GeneralLedger from "../finance/GeneralLedger";
import { setAccessContext } from "../../config/roles";

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
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true, askConfirm: jest.fn(async () => true), askReason: jest.fn(async () => null),
  askText: jest.fn(async () => null), askChoice: jest.fn(async () => null), default: {},
}));
// Pemilih bawaan (cmdk/radix) & kalender (radix popover) diganti isian polos — yang diuji isi pilihannya.
jest.mock("../../components/KNSelect", () => (p) => (
  <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
    <option value="">-</option>
    {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
  </select>
));
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange && p.onChange(e.target.value)} />,
  formatDateId: (v) => String(v || ""),
}));
jest.mock("../../components/AskKnButton", () => ({ __esModule: true, AskKnButton: () => null, PENDING_KEY: "kn_tanya_pending" }));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

beforeAll(() => setAccessContext({ role: "admin" }));
afterAll(() => setAccessContext(null));

const ENTS = [{ id: "ent_ksc", legal_name: "PT Kain Suka Cita", short_name: "Sukacita" }];
const ACC = (code, name, extra = {}) => ({ code, name, type: "asset", is_postable: true, is_active: true,
  normal_balance: "debit", is_control: false, control_ledger: "", control_ledger_label: "", manual_allowed: true, ...extra });
const PIUTANG = ACC("1-1200", "Piutang Usaha", { is_control: true, control_ledger: "piutang",
  control_ledger_label: "piutang usaha", manual_allowed: false });
const ACCOUNTS = [ACC("1-1100", "Kas Besar / Bank"), PIUTANG, ACC("6-4000", "Beban Operasional Lainnya", { type: "expense" })];

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const optionValues = (id) => [...q(id).querySelectorAll("option")].map((o) => o.value).filter(Boolean);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el, selectedEntity = "ent_ksc") {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(
      <EntityScopeProvider selectedEntity={selectedEntity} entities={ENTS}>
        <AppNavProvider role="admin" onNavigateTo={() => {}} onOpenDocument={() => {}}>{el}</AppNavProvider>
      </EntityScopeProvider>);
  });
  await flush();
  return host;
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
async function type(el, value) {
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new Event("input", { bubbles: true })); });
}
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const path = String(url).split("?")[0];
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => path.endsWith(k));
    return Promise.resolve({ data: hit ? map[hit] : [] });
  });
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockReset(); mockPost.mockReset();
  document.body.innerHTML = "";
});

test("Jurnal Manual Baru: akun kontrol tidak ditawarkan + kalimat keterangan", async () => {
  routeGet({ "/finance/closing/status": { closed: false } });
  await mount(<JournalEntryModal accounts={ACCOUNTS} onClose={() => {}} onSaved={() => {}} />);
  expect(optionValues("je-line-account-0")).toEqual(["1-1100", "6-4000"]);
  expect(optionValues("je-line-account-1")).not.toContain("1-1200");
  expect(q("je-control-note").textContent).toBe("Akun piutang, hutang, persediaan, dan antar-PT tidak ada di daftar ini "
    + "karena saldonya dijaga dokumen. Koreksi lewat dokumennya.");
});

test("Jurnal Manual Baru: PT mengizinkan (tidak ada akun disembunyikan) → kalimat tidak tampil", async () => {
  routeGet({ "/finance/closing/status": { closed: false } });
  const izin = ACCOUNTS.map((a) => ({ ...a, manual_allowed: true }));
  await mount(<JournalEntryModal accounts={izin} onClose={() => {}} onSaved={() => {}} />);
  expect(optionValues("je-line-account-0")).toEqual(["1-1100", "1-1200", "6-4000"]);
  expect(q("je-control-note")).toBeNull();
});

test("Suspense: akun tujuan reklasifikasi tanpa akun kontrol", async () => {
  routeGet({ "/gl/suspense": { balance: -100000, entry_count: 0, items: [] } });
  await mount(<SuspensePanel refreshKey={0} accounts={[...ACCOUNTS, ACC("1-9999", "Suspense")]} entities={ENTS}
    selectedEntity="ent_ksc" onNotice={() => {}} onChanged={() => {}} />);
  expect(optionValues("suspense-target")).toEqual(["1-1100", "6-4000"]);
});

test("Rincian jurnal: galat 422 pembalikan tampil di dalam pop-up alasan pembalikan", async () => {
  const pesan = "Jurnal KSC/JE-00012 berasal dari Antar-PT dan menyentuh akun kontrol antar-PT. Batalkan atau koreksi "
    + "dokumen sumbernya; pembalikan manual ditolak.";
  const je = { id: "je_1", number: "KSC/JE-00012", entity_id: "ent_ksc", source_type: "interco_transaction",
    status: "posted", date: "2026-11-14", description: "Antar-PT", total_debit: 100000, total_credit: 100000,
    lines: [{ account_code: "1-1250", account_name: "Piutang Antar-PT", debit: 100000, credit: 0 },
      { account_code: "4-1000", account_name: "Pendapatan", debit: 0, credit: 100000 }] };
  const onReverse = jest.fn(() => Promise.reject({ response: { status: 422, data: { detail: pesan } } }));
  await mount(<JournalDetailModal je={je} sourceMeta={() => ({ label: "Antar-PT", tone: "" })} entities={ENTS}
    selectedEntity="ent_ksc" onClose={() => {}} onVoid={() => {}} onReverse={onReverse} />);
  await click(q("gl-journal-reverse"));
  await type(q("gl-reverse-reason"), "salah catat antar-PT");
  await click(q("gl-reverse-submit"));
  expect(onReverse).toHaveBeenCalledTimes(1);
  const err = q("gl-reverse-error");
  expect(err).not.toBeNull();
  expect(err.textContent).toContain("pembalikan manual ditolak");
  expect(q("gl-reverse-form").contains(err)).toBe(true);
  expect(q("gl-journal-detail-error")).toBeNull();
});

test("Bagan Akun: lencana Akun kontrol dengan petunjuk dokumen buku pembantunya", async () => {
  routeGet({ "/gl/accounts": ACCOUNTS });
  await mount(<ChartOfAccounts entities={[]} currentUser={{ role: "admin", permissions: { audit: ["view"] } }} />);
  const badge = q("coa-badge-control-1-1200");
  expect(badge.textContent.trim()).toBe("Akun kontrol");
  expect(badge.getAttribute("title")).toBe("Hanya berubah lewat dokumen piutang usaha");
  expect(q("coa-badge-control-6-4000")).toBeNull();
});

test("Buku Besar: bagan akun dimuat untuk PT yang sedang dibuka; Semua PT = lapisan global", async () => {
  routeGet({ "/gl/summary": {}, "/gl/accounts": ACCOUNTS, "/gl/journal": { items: [], total: 0 } });
  await mount(<GeneralLedger selectedEntity="ent_ksc" entities={ENTS} />);
  const panggil = mockGet.mock.calls.filter(([u]) => String(u).endsWith("/gl/accounts"));
  expect(panggil.length).toBeGreaterThan(0);
  expect(panggil[0][1]).toEqual({ params: { entity_id: "ent_ksc" } });
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockClear();
  await mount(<GeneralLedger selectedEntity="all" entities={ENTS} />, "all");
  const semua = mockGet.mock.calls.filter(([u]) => String(u).endsWith("/gl/accounts"));
  expect(semua[0][1]).toBeUndefined();
});
