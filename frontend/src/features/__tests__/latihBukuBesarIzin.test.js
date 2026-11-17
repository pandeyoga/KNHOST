// Pelatihan Keuangan 18 Nov (F16) — Buku Besar & Bagan Akun untuk Finance (izin `accounting: ["view"]`, K-09).
// Temuan uji jalan: Finance melihat [Jurnal Baru], [Sinkronkan], [Balik Jurnal], [Tambah Akun], ikon ubah/hapus dan
// tombol "Dipakai Sukacita" — semuanya memanggil endpoint ber-izin create/manage/void → 403. Kini tombolnya mengikuti izin;
// Admin / Manajer (izin lengkap) tetap melihatnya; komponen tanpa data izin = perilaku lama (server tetap menegakkan).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import GeneralLedger from "../finance/GeneralLedger";
import ChartOfAccounts from "../finance/ChartOfAccounts";
import JournalDetailModal from "../finance/JournalDetailModal";
import { izinAkuntansi } from "../finance/useJournalActions";
import { AppNavProvider } from "../../context/AppNavContext";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }),
    patch: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../components/KNSelect", () => {
  const Pilih = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      <option value="">-</option>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: Pilih, KNSelect: Pilih };
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function flush() { for (let i = 0; i < 4; i += 1) { await act(async () => {}); } }   // eslint-disable-line no-await-in-loop
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await flush();
  return host;
}
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.endsWith(k));
    return Promise.resolve({ data: hit ? map[hit] : [] });
  });
}
const FINANCE = { id: "u_fin", role: "finance", permissions: { accounting: ["view"], gl_mapping: ["view", "update"] } };
const MANAGER = { id: "u_mgr", role: "manager", permissions: { accounting: ["view", "create", "void", "manage"] } };
const sesi = (u) => localStorage.setItem("kn_user", JSON.stringify(u));
afterEach(() => { mockGet.mockReset(); localStorage.clear(); document.body.innerHTML = ""; });

const JE = { id: "je_1", number: "KSC/JE-00096", source_type: "manual", status: "posted", date: "2026-11-17",
  description: "Penerimaan", total_debit: 100, total_credit: 100,
  lines: [{ account_code: "1-1100", account_name: "Kas", debit: 100, credit: 0 },
    { account_code: "1-1200", account_name: "Piutang", debit: 0, credit: 100 }] };
const GL_ROUTES = { "/gl/summary": { journal_count: 1, total_debit: 100, total_credit: 100, balanced: true },
  "/gl/accounts": [], "/gl/journal": { items: [JE], total: 1 } };

describe("izinAkuntansi — dari sesi tersimpan", () => {
  test("Finance: view saja; Manajer: lengkap; tanpa sesi: perilaku lama", () => {
    sesi(FINANCE);
    expect(["view", "create", "manage", "void"].map(izinAkuntansi)).toEqual([true, false, false, false]);
    sesi(MANAGER);
    expect(["create", "manage", "void"].map(izinAkuntansi)).toEqual([true, true, true]);
    localStorage.clear();
    expect(izinAkuntansi("void")).toBe(true);
  });
});

describe("Buku Besar › Jurnal", () => {
  test.each([[FINANCE, false], [MANAGER, true]])("%o → tombol tulis tampil %s", async (u, tampil) => {
    sesi(u);
    routeGet(GL_ROUTES);
    const host = await mount(<AppNavProvider role={u.role} onNavigateTo={jest.fn()}>
      <GeneralLedger selectedEntity="ent_ksc" entities={[]} /></AppNavProvider>);
    expect(!!q(host, "gl-new-journal")).toBe(tampil);
    expect(!!q(host, "gl-sync")).toBe(tampil);
    await act(async () => { q(host, "gl-journal-row-je_1").dispatchEvent(new MouseEvent("click", { bubbles: true })); });
    await flush();
    expect(q(document.body, "gl-journal-detail")).not.toBeNull();
    expect(!!q(document.body, "gl-journal-reverse")).toBe(tampil);
    expect(!!q(document.body, "gl-journal-void")).toBe(tampil);
  });

  test("rincian jurnal tanpa onVoid → tombol Anulir tidak tampil", async () => {
    const host = await mount(<JournalDetailModal je={JE} sourceMeta={() => ({ label: "Manual", tone: "" })}
      onClose={() => {}} />);
    expect(q(host.ownerDocument.body, "gl-journal-void")).toBeNull();
    expect(q(host.ownerDocument.body, "gl-journal-reverse")).toBeNull();
  });
});

describe("Bagan Akun", () => {
  const AKUN = [{ code: "1-1200", name: "Piutang Usaha", type: "asset", is_postable: true, normal_balance: "debit",
    is_active: true, entity_active: true, is_control: true },
  // K01 — ikon hapus di bagan PT hanya untuk akun khusus PT itu (akun warisan template tidak bisa dihapus dari sini).
  { code: "6-4950", name: "Beban Latihan", type: "expense", is_postable: true, normal_balance: "debit", is_active: true,
    entity_id: "ent_ksc" }];
  test.each([[FINANCE, false], [MANAGER, true]])("%o → tambah/ubah/hapus tampil %s", async (u, tampil) => {
    routeGet({ "/gl/accounts": AKUN });
    const host = await mount(<ChartOfAccounts entities={[{ id: "ent_ksc", short_name: "Sukacita" }]} currentUser={u}
      selectedEntity="ent_ksc" />);
    expect(q(host, "coa-row-1-1200")).not.toBeNull();
    expect(!!q(host, "coa-add-toggle")).toBe(tampil);
    expect(!!q(host, "coa-edit-1-1200")).toBe(tampil);
    expect(!!q(host, "coa-delete-6-4950")).toBe(tampil);
    expect(q(host, "coa-delete-1-1200")).toBeNull();               // warisan Template Global: tidak dihapus dari bagan PT
    expect(q(host, "coa-detail-1-1200")).not.toBeNull();          // riwayat akun tetap bisa dibaca
    const t = q(host, "coa-toggle-entity-active-1-1200");
    if (t) expect(t.disabled).toBe(!tampil);
  });
});
