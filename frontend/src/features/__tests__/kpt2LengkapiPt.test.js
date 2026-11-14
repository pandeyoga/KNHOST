// KP-T2 — langkah "Lengkapi PT", panel Kesiapan PT, dan daftar centang "Sebelum mengarsipkan" (uji komponen; U18 uji
// jalan peramban terpisah). `EntityCompletionSteps`: 16 butir bernomor, ringkasan "{siap} dari {total} hal sudah siap",
// petunjuk hanya untuk baris belum siap, Lengkapi = ganti PT aktif dulu lalu buka layar (preset tab), Ulangi penyiapan.
// Wizard: simpan → langkah 5 (tidak menutup) → Lengkapi pada Gudang → PT baru aktif + Master Gudang; Selesai → onDone.
// Dialog arsip: `checks` server, jumlah + contoh, rupiah berpemisah ribuan, tombol mati tanpa paksa + alasan.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";
import AppNavContext from "../../context/AppNavContext";
import EntityScopeContext from "../../context/EntityScopeContext";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    put: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"] || p.testId} value={p.value ?? ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      {(p.options || []).map((o) => <option key={String(o.value)} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange(e.target.value)} />,
  formatDateId: (v) => (v ? `tgl ${String(v).slice(0, 10)}` : ""),
}));

import EntityCompletionSteps from "../settings/entities/EntityCompletionSteps";
import EntityWizard from "../settings/entities/EntityWizard";
import EntityReadinessPanel from "../settings/entities/EntityReadinessPanel";
import ArchiveEntityDialog from "../settings/entities/ArchiveEntityDialog";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const KEYS = ["provisioning", "address", "tax", "doc_prefix", "users", "finance_user", "warehouses", "bank_account",
  "cash_account", "gl_mappings", "period", "payment_term", "prices", "opening_balance", "branding", "signers"];
// KP-T9 — butir profil/akun menuju tab hub baru (Profil PT, Akun); `tab` lama tetap dikirim server.
const VIEW = { address: ["settings-pt-profile", "entities"], tax: ["settings-pt-profile", "entities"],
  doc_prefix: ["settings-pt-profile", "entities"], users: ["settings-accounts", "accounts"],
  finance_user: ["settings-accounts", "accounts"], warehouses: ["md-warehouses"], bank_account: ["bank-accounts"],
  cash_account: ["bank-accounts"], gl_mappings: ["gl-account-mappings"], period: ["closing"],
  payment_term: ["entity-masters"], prices: ["pricelist"], opening_balance: ["general-ledger"],
  branding: ["pdf-templates"], signers: ["pdf-templates"] };
const READINESS = (notReady = ["provisioning", "bank_account"]) => {
  const items = KEYS.map((key) => {
    const [view = "", tab] = VIEW[key] || [];
    const ready = !notReady.includes(key);
    return { key, label: `Label ${key}`, ready, count: ready ? 1 : 0, detail: `detail ${key}`, how_to: `cara ${key}`,
      view, ...(tab ? { tab } : {}) };
  });
  const ready = items.filter((i) => i.ready).length;
  return { entity_id: "ent_baru", items, ready, total: items.length, percent: Math.round((ready * 100) / items.length),
    is_ready: ready === items.length };
};

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
const nav = { go: jest.fn(), canOpen: () => true, openDocument: () => {}, role: "admin" };
const scope = { selectedEntity: "ent_ksc", entities: [], canWrite: true, writeBlockHint: "", pickEntity: jest.fn() };
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(
      <AppNavContext.Provider value={nav}>
        <EntityScopeContext.Provider value={scope}>{el}<ConfirmHost /></EntityScopeContext.Provider>
      </AppNavContext.Provider>,
    );
  });
  await flush();
  return host;
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
async function type(el, value) {
  const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new Event("input", { bubbles: true })); });
  await flush(2);
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  document.body.innerHTML = "";
  jest.clearAllMocks();
  scope.selectedEntity = "ent_ksc";
});

// ─── EntityCompletionSteps ───────────────────────────────────────────────────────────────────────────────────────
test("Lengkapi PT: 16 langkah bernomor, ringkasan, petunjuk hanya untuk yang belum siap", async () => {
  await mount(<EntityCompletionSteps entityId="ent_baru" data={READINESS()} canRetry testId="cs" />);
  expect(q("cs-title").textContent).toBe("Lengkapi PT");
  expect(q("cs-summary").textContent).toBe("14 dari 16 hal sudah siap");
  const rows = [...document.body.querySelectorAll("[data-testid^='cs-item-']")];
  expect(rows.map((r) => r.dataset.testid.replace("cs-item-", ""))).toEqual(KEYS);
  expect(rows[0].textContent).toMatch(/^1\./);
  expect(rows[15].textContent).toMatch(/^16\./);
  expect(q("cs-howto-bank_account").textContent).toBe("cara bank_account");
  expect(q("cs-howto-warehouses")).toBeNull();                       // baris siap: tanpa petunjuk
  expect(q("cs-goto-provisioning")).toBeNull();                      // penyiapan awal tanpa layar tujuan
  expect(q("cs-retry").textContent).toContain("Ulangi penyiapan");
  expect(q("cs-goto-warehouses").textContent).toContain("Lengkapi");
});

test("Lengkapi: mengganti PT aktif lebih dulu lalu membuka layar (dengan preset tab bila ada)", async () => {
  await mount(<EntityCompletionSteps entityId="ent_baru" data={READINESS()} testId="cs" />);
  expect(q("cs-retry")).toBeNull();                                  // tanpa izin ubah PT: tanpa tombol ulang
  await click(q("cs-goto-warehouses"));
  expect(scope.pickEntity).toHaveBeenCalledWith("ent_baru");
  expect(nav.go).toHaveBeenCalledWith("md-warehouses", {});
  expect(scope.pickEntity.mock.invocationCallOrder[0]).toBeLessThan(nav.go.mock.invocationCallOrder[0]);
  await click(q("cs-goto-users"));
  expect(nav.go).toHaveBeenLastCalledWith("settings-accounts", {});   // KP-T9 — tab Akun (tanpa preset)
  scope.selectedEntity = "ent_baru";                                 // dipasang ulang dengan PT aktif = PT ini
  scope.pickEntity.mockClear();
  await mount(<EntityCompletionSteps entityId="ent_baru" data={READINESS()} testId="cs2" />);
  await click(q("cs2-goto-address"));
  expect(scope.pickEntity).not.toHaveBeenCalled();                  // PT sudah aktif
  expect(nav.go).toHaveBeenLastCalledWith("settings-pt-profile", { preset: { entity_id: "ent_baru" } });   // KP-T9
});

test("Ulangi penyiapan: POST retry, kesiapan baru dikirim ke pemanggil; kosong & memuat dibedakan", async () => {
  const fresh = READINESS(["bank_account"]);
  mockPost.mockResolvedValue({ data: { entity_id: "ent_baru", provisioning: { coa: true, config_layer: true,
    group_partners: true }, errors: {}, readiness: fresh } });
  const onUpdated = jest.fn();
  await mount(<EntityCompletionSteps entityId="ent_baru" data={READINESS()} canRetry onUpdated={onUpdated} testId="cs" />);
  await click(q("cs-retry"));
  expect(mockPost).toHaveBeenCalledWith("/api/entities/ent_baru/provisioning/retry");
  expect(onUpdated).toHaveBeenCalledWith(fresh, expect.objectContaining({ entity_id: "ent_baru" }));
  await mount(<EntityCompletionSteps entityId="" data={null} testId="kosong" />);
  expect(q("kosong-empty").textContent).toBe("Pilih PT untuk melihat daftar kesiapannya.");
  await mount(<EntityCompletionSteps entityId="ent_x" data={null} loading testId="muat" />);
  expect(q("muat-loading")).not.toBeNull();
});

// ─── Wizard langkah 5 ─────────────────────────────────────────────────────────────────────────────────────────────
test("Wizard: simpan → langkah 5 Lengkapi PT (tidak menutup); Lengkapi Gudang → PT baru aktif + Master Gudang; Selesai", async () => {
  mockGet.mockImplementation((url) => {
    if (url === "/api/enums/entity_type") return Promise.resolve({ data: { values: [{ value: "PT", label: "PT" }] } });
    if (url === "/api/config/effective") return Promise.reject({ response: { status: 403, data: { detail: "x" } } });
    return Promise.resolve({ data: [] });
  });
  const saved = { id: "ent_baru", legal_name: "PT Baru Jaya", doc_prefix: "BARU",
    provisioning: { number_preview: "BARU/SO-00001" }, readiness: READINESS() };
  mockPost.mockResolvedValue({ data: saved });
  const onCreated = jest.fn();
  const onDone = jest.fn();
  const onClose = jest.fn();
  await mount(<EntityWizard entities={[]} canManage onClose={onClose} onCreated={onCreated} onDone={onDone} />);
  await type(q("entity-wizard-legal-input"), "PT Baru Jaya");
  await type(q("entity-wizard-short-input"), "BARU");
  await click(q("entity-wizard-next"));
  await type(q("entity-wizard-npwp-input"), "01.234.567.8-901.000");
  await click(q("entity-wizard-next"));
  await click(q("entity-wizard-next"));
  expect(q("entity-wizard-panel-4").textContent).toContain("Lengkapi PT");
  await click(q("entity-wizard-submit"));

  expect(onCreated).toHaveBeenCalledWith(saved);
  expect(onClose).not.toHaveBeenCalled();
  expect(q("entity-wizard")).not.toBeNull();                         // wizard tidak menutup
  expect(q("entity-wizard-panel-5")).not.toBeNull();
  expect(q("entity-wizard").textContent).toContain("Langkah 5 dari 5 · Lengkapi PT");
  expect(q("entity-wizard-completion-title").textContent).toBe("Lengkapi PT");
  expect(q("entity-wizard-completion-summary").textContent).toBe("14 dari 16 hal sudah siap");
  expect(q("entity-wizard-later").textContent).toBe("Langkah ini bisa dilanjutkan kapan saja dari tab Kesiapan.");
  expect(q("entity-wizard-completion-retry")).not.toBeNull();       // canManage → boleh ulangi penyiapan
  expect(q("entity-wizard-submit")).toBeNull();                      // tidak bisa simpan ganda
  expect(q("entity-wizard-step-1").disabled).toBe(true);
  expect(q("entity-wizard-step-4").disabled).toBe(true);

  await click(q("entity-wizard-completion-goto-warehouses"));
  expect(scope.pickEntity).toHaveBeenCalledWith("ent_baru");
  expect(nav.go).toHaveBeenCalledWith("md-warehouses", {});

  await click(q("entity-wizard-done"));
  expect(onDone).toHaveBeenCalledWith(saved);
});

// ─── Panel Kesiapan PT ────────────────────────────────────────────────────────────────────────────────────────────
test("Panel Kesiapan PT: judul baru, pilihan awal = PT aktif, daftar dari komponen yang sama", async () => {
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.includes("ent_kanda") ? READINESS([]) : READINESS() }));
  const ents = [{ id: "ent_ksc", short_name: "KSC", status: "active" }, { id: "ent_kanda", short_name: "Kanda", status: "active" }];
  await mount(<EntityReadinessPanel entities={ents} selectedEntity="ent_kanda" canManage />);
  expect(q("entity-readiness-title").textContent).toBe("Kesiapan PT");
  expect(mockGet).toHaveBeenCalledWith("/api/entities/ent_kanda/readiness");
  expect(q("readiness-steps-title").textContent).toBe("Lengkapi PT");
  expect(q("readiness-summary").textContent).toContain("16 dari 16 hal sudah siap");
  expect(document.body.querySelectorAll("[data-testid^='readiness-steps-item-']").length).toBe(16);
});

// ─── Dialog arsip ─────────────────────────────────────────────────────────────────────────────────────────────────
const IMPACT = {
  entity_id: "ent_kanda", entity_name: "Kanda", active_users: [], home_users: [], employees: 1,
  open_documents: [{ collection: "cash_advances", label: "Uang muka", count: 1, examples: ["KANDA/PD-90001"] }],
  open_documents_total: 1,
  balances: [{ key: "hutang", label: "Hutang pemasok belum lunas", amount: 300000 },
    { key: "kas_bank", label: "Saldo kas dan bank", amount: 250000 }],
  periods: { journals_after_last_closing: 0 }, first_document: null,
  checks: [
    { key: "pengguna", label: "Pengguna ber-PT utama di sini", ok: true, detail: "Tidak ada" },
    { key: "dokumen", label: "Dokumen terbuka", ok: false, detail: "1 dokumen: Uang muka 1 (KANDA/PD-90001)" },
    { key: "saldo", label: "Saldo yang masih hidup", ok: false, detail: "…" },
    { key: "karyawan", label: "Karyawan terdaftar", ok: false, detail: "1 karyawan belum dipindahkan atau diakhiri" },
    { key: "periode", label: "Tutup buku", ok: true, detail: "Semua jurnal sudah masuk periode tertutup" },
  ],
  blockers: ["1 dokumen masih terbuka (Uang muka 1) — selesaikan atau batalkan dulu"], can_archive: false,
};

test("Dialog arsip: daftar centang 'Sebelum mengarsipkan' = checks server; jumlah, contoh, rupiah; tombol mati tanpa paksa", async () => {
  mockGet.mockResolvedValue({ data: IMPACT });
  await mount(<ArchiveEntityDialog entity={{ id: "ent_kanda", legal_name: "Kanda" }} onClose={() => {}} onDone={() => {}} />);
  expect(q("entity-archive-checks").textContent).toContain("Sebelum mengarsipkan");
  const rows = [...document.body.querySelectorAll("[data-testid^='entity-archive-check-']")]
    .filter((r) => r.dataset.ok);
  expect(rows.map((r) => [r.dataset.testid.replace("entity-archive-check-", ""), r.dataset.ok])).toEqual([
    ["pengguna", "ya"], ["dokumen", "tidak"], ["saldo", "tidak"], ["karyawan", "tidak"], ["periode", "ya"]]);
  expect(q("entity-archive-check-docs").textContent).toContain("Uang muka: 1");
  expect(q("entity-archive-check-docs").textContent).toContain("KANDA/PD-90001");
  expect(q("entity-archive-balance-hutang").textContent.replace(/\s/g, " ")).toContain("Rp 300.000");
  expect(q("entity-archive-balance-kas_bank").textContent.replace(/\s/g, " ")).toContain("Rp 250.000");
  expect(q("entity-archive-check-karyawan").textContent).toContain("1 karyawan");
  expect(q("entity-archive-submit").disabled).toBe(true);
  await click(q("entity-archive-force"));
  expect(q("entity-archive-submit").disabled).toBe(true);           // paksa tanpa alasan tetap mati
  await type(q("entity-archive-reason"), "Tutup usaha");
  expect(q("entity-archive-submit").disabled).toBe(false);
});
