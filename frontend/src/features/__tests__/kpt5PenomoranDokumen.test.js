// KP-T5 — tab Pengaturan › Dokumen & Cetak › Penomoran Dokumen (`DocNumberingView`) + pratinjau nomor wizard PT.
// Uji komponen (uji jalan peramban U16 terpisah): tabel berkelompok dengan kolom spesifikasi, keterangan kepala tabel,
// jenis terkunci abu-abu tanpa tombol, pop-up Ubah (pratinjau dari server saat mengetik, Deret hanya aktif di baris grup,
// alasan wajib → satu PUT), Kembalikan ke bawaan (DELETE), tanpa izin kelola = tanpa tombol, galat + coba lagi.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";

const mockGet = jest.fn();
const mockPut = jest.fn();
const mockPost = jest.fn();
const mockDelete = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), put: (...a) => mockPut(...a), post: (...a) => mockPost(...a),
    delete: (...a) => mockDelete(...a), defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});

// eslint-disable-next-line import/first
import DocNumberingView, { bodyFromDraft, HEAD_NOTE, resetLabel, scopeLabel, tokenLabel }
  from "../settings/docnumbering/DocNumberingView";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const ENTS = [
  { id: "ent_ksc", legal_name: "PT Kain Suka Cita", short_name: "Sukacita" },
  { id: "ent_kanda", legal_name: "CV Kanda Suka", short_name: "Kanda" },
];
const ADMIN = { permissions: { settings: ["view", "manage"] } };
const PEMBACA = { permissions: { settings: ["view"] } };
const row = (kind, label, group, fmt, extra = {}) => ({
  kind, label, group, note: "", format: { prefix: "SO-", width: 5, date_token: "", reset: "tidak", scope: "per_pt", ...fmt },
  default: {}, source: "bawaan", source_label: "Bawaan", scope_source: "bawaan", next_preview: "KSC/SO-00042",
  samples: ["KSC/SO-00042", "KSC/SO-00043", "KSC/SO-00044"], last_no: 41, locked: false, locked_note: "", version: 0,
  ...extra,
});
const DATA = (over = {}) => ({
  entity_id: "ent_ksc", groups: ["Penjualan", "Pembelian", "Gudang", "Master"],
  rows: [
    row("so", "Pesanan penjualan", "Penjualan", {}),
    row("sret", "Retur penjualan", "Penjualan", { prefix: "SRET-", scope: "bersama" },
      { next_preview: "SRET-00008", source: "pt", source_label: "Khusus PT ini", version: 2 }),
    row("lot", "Nomor lot", "Gudang", { prefix: "LOT-", width: 4, date_token: "YYMM", reset: "bulanan" },
      { next_preview: "KSC/LOT-2611-0008" }),
    row("sup", "Kode pemasok", "Master", { prefix: "SUP-", scope: "bersama" },
      { locked: true, locked_note: "Tidak bisa diubah: dipakai bersama atau diturunkan dari dokumen lain.",
        next_preview: "SUP-00012" }),
  ], ...over,
});

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(props = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(<><DocNumberingView selectedEntity="ent_ksc" entities={ENTS} currentUser={ADMIN} {...props} />
      <ConfirmHost /></>);
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
  await act(async () => {
    setter.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
}
async function tunggu(ms = 400) {
  await act(async () => { await new Promise((r) => setTimeout(r, ms)); });
  await flush();
}

afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockReset(); mockPut.mockReset(); mockPost.mockReset(); mockDelete.mockReset();
  document.body.innerHTML = "";
});

test("tabel berkelompok: kolom spesifikasi, keterangan kepala, sumber, jenis terkunci tanpa tombol", async () => {
  mockGet.mockResolvedValue({ data: DATA() });
  await mount();
  expect(mockGet).toHaveBeenCalledWith("/api/doc-numbering", { params: { entity_id: "ent_ksc" } });
  expect(q("docnum-head-note").textContent).toBe(HEAD_NOTE);
  const head = [...q("docnum-group-Penjualan").querySelectorAll("th")].map((t) => t.textContent);
  expect(head.slice(0, 8)).toEqual(["Jenis dokumen", "Contoh nomor berikutnya", "Awalan", "Lebar angka",
    "Sisipan tanggal", "Mulai lagi dari 1", "Deret", "Sumber"]);
  expect(q("docnum-group-Pembelian")).toBeNull();               // kelompok tanpa baris tidak tampil
  expect(q("docnum-next-so").textContent).toBe("KSC/SO-00042");
  expect(q("docnum-source-sret").textContent).toBe("Khusus PT ini");
  expect(q("docnum-row-lot").textContent).toContain("Tahun dan bulan (2611)");
  expect(q("docnum-row-lot").textContent).toContain("Tiap bulan");
  expect(q("docnum-row-sret").textContent).toContain("Bersama semua PT");
  expect(q("docnum-locked-sup").textContent).toBe("Tidak bisa diubah: dipakai bersama atau diturunkan dari dokumen lain.");
  expect(q("docnum-edit-sup")).toBeNull();
  expect(q("docnum-edit-so")).not.toBeNull();
  expect(q("docnum-reset-sret")).not.toBeNull();                // khusus PT ini → bisa dikembalikan
  expect(q("docnum-reset-so")).toBeNull();                      // masih bawaan
  expect(document.body.textContent).not.toContain("ent_ksc");
  expect(document.body.textContent).not.toContain("per_pt");
});

test("Ubah: pratinjau dari server saat mengetik, Deret mati di baris PT, alasan wajib → satu PUT", async () => {
  mockGet.mockResolvedValue({ data: DATA() });
  mockPost.mockResolvedValue({ data: { samples: ["KSC/SP-000042", "KSC/SP-000043", "KSC/SP-000044"],
    warnings: ["Sudah ada 7 dokumen bernomor format lama; nomor lama tidak berubah."] } });
  mockPut.mockResolvedValue({ data: { label: "Pesanan penjualan", warnings: [] } });
  await mount();
  await click(q("docnum-edit-so"));
  expect(q("docnum-edit-scope").disabled).toBe(true);
  expect(q("docnum-edit-scope-note")).not.toBeNull();
  await type(q("docnum-edit-prefix"), "sp-");
  await type(q("docnum-edit-width"), "6");
  await tunggu();
  const [url, body] = mockPost.mock.calls[mockPost.mock.calls.length - 1];
  expect(url).toBe("/api/doc-numbering/preview");
  expect(body).toEqual({ kind: "so", entity_id: "ent_ksc", prefix: "SP-", width: 6, date_token: "", reset: "tidak" });
  expect(q("docnum-edit-preview").textContent).toContain("KSC/SP-000042 · KSC/SP-000043 · KSC/SP-000044");
  expect(q("docnum-edit-warning").textContent).toContain("Sudah ada 7 dokumen");
  await click(q("docnum-edit-save"));
  expect(q("docnum-save-confirm-confirm").disabled).toBe(true);   // alasan wajib
  await type(q("docnum-save-confirm-reason"), "Awalan baru PT");
  await click(q("docnum-save-confirm-confirm"));
  expect(mockPut).toHaveBeenCalledTimes(1);
  expect(mockPut.mock.calls[0]).toEqual(["/api/doc-numbering/so", { entity_id: "ent_ksc", prefix: "SP-", width: 6,
    date_token: "", reset: "tidak", reason: "Awalan baru PT", expected_version: 0 }]);
  expect(q("docnum-ok").textContent).toContain("Format Pesanan penjualan tersimpan.");
});

test("Semua PT: baris grup, Deret aktif dan ikut dikirim; Kembalikan ke bawaan = DELETE beralasan", async () => {
  const grp = DATA({ entity_id: "all" });
  grp.rows[0] = { ...grp.rows[0], source: "grup", source_label: "Aturan grup", version: 3 };
  mockGet.mockResolvedValue({ data: grp });
  mockPost.mockResolvedValue({ data: { samples: ["KODE/SO-00001"], warnings: [] } });
  mockPut.mockResolvedValue({ data: { label: "Pesanan penjualan", warnings: ["Deret baru melanjutkan dari nomor tertinggi gabungan yang sudah ada."] } });
  mockDelete.mockResolvedValue({ data: {} });
  await mount({ selectedEntity: "all" });
  expect(mockGet).toHaveBeenCalledWith("/api/doc-numbering", { params: { entity_id: "all" } });
  await click(q("docnum-edit-so"));
  expect(q("docnum-edit-scope").disabled).toBe(false);
  await act(async () => {
    q("docnum-edit-scope").value = "bersama";
    q("docnum-edit-scope").dispatchEvent(new Event("change", { bubbles: true }));
  });
  await tunggu();
  await click(q("docnum-edit-save"));
  await type(q("docnum-save-confirm-reason"), "Satu deret grup");
  await click(q("docnum-save-confirm-confirm"));
  expect(mockPut.mock.calls[0][1]).toMatchObject({ entity_id: "all", scope: "bersama", expected_version: 3 });
  expect(q("docnum-warning").textContent).toContain("gabungan");
  await click(q("docnum-reset-so"));
  await type(q("docnum-reset-confirm-reason"), "Kembali ke bawaan");
  await click(q("docnum-reset-confirm-confirm"));
  expect(mockDelete).toHaveBeenCalledWith("/api/doc-numbering/so", { params: { entity_id: "all", reason: "Kembali ke bawaan" } });
});

test("tanpa izin kelola: tabel terbaca, tanpa tombol Ubah", async () => {
  mockGet.mockResolvedValue({ data: DATA() });
  await mount({ currentUser: PEMBACA });
  expect(q("docnum-next-so")).not.toBeNull();
  expect(q("docnum-edit-so")).toBeNull();
  expect(q("docnum-reset-sret")).toBeNull();
});

test("memuat: kerangka abu-abu; galat tampil dengan Coba lagi", async () => {
  let selesai;
  mockGet.mockReturnValueOnce(new Promise((r) => { selesai = r; }));
  await mount();
  expect(q("docnum-loading")).not.toBeNull();
  await act(async () => { selesai({ data: DATA() }); });
  await flush();
  expect(q("docnum-loading")).toBeNull();
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  document.body.innerHTML = "";
  mockGet.mockReset();
  mockGet.mockRejectedValueOnce({ response: { status: 500, data: { detail: "Server sedang sibuk." } } });
  mockGet.mockResolvedValueOnce({ data: DATA() });
  await mount();
  expect(q("docnum-error")).not.toBeNull();
  await click(q("docnum-error").querySelector("button"));
  expect(q("docnum-error")).toBeNull();
  expect(q("docnum-next-so")).not.toBeNull();
});

test("pembantu: label sisipan/pengulangan/deret dan isi permintaan", () => {
  expect(tokenLabel("YYMMDD")).toBe("Tanggal (261114)");
  expect(resetLabel("tahunan")).toBe("Tiap tahun");
  expect(scopeLabel("bersama")).toBe("Bersama semua PT");
  expect(bodyFromDraft({ prefix: " so- ", width: "6", date_token: "", reset: "tidak", scope: "per_pt" }, false))
    .toEqual({ prefix: "SO-", width: 6, date_token: "", reset: "tidak" });
  expect(bodyFromDraft({ prefix: "SO-", width: "5", date_token: "YYYY", reset: "tahunan", scope: "bersama" }, true))
    .toEqual({ prefix: "SO-", width: 5, date_token: "YYYY", reset: "tahunan", scope: "bersama" });
});

// ─── Wizard PT langkah 3: pratinjau nomor dari server (format grup yang berlaku, kode = isian) ─────────────────────
// eslint-disable-next-line import/first
import EntityWizard from "../settings/entities/EntityWizard";
// eslint-disable-next-line import/first
import { PREVIEW_KINDS } from "../settings/entities/docNumberPreview";

function wizardGets() {
  mockGet.mockImplementation((url) => {
    if (url === "/api/enums/entity_type") return Promise.resolve({ data: { values: [{ value: "PT", label: "PT" }] } });
    return Promise.reject({ response: { status: 403, data: { detail: "tanpa akses" } } });
  });
}
async function keLangkah3() {
  await type(q("entity-wizard-legal-input"), "PT Uji Nomor");
  await type(q("entity-wizard-short-input"), "Uji Nomor");
  await click(q("entity-wizard-next"));
  await type(q("entity-wizard-npwp-input"), "1234567890123456");
  await click(q("entity-wizard-next"));
  expect(q("entity-wizard-panel-3")).not.toBeNull();
}
async function mountWizard() {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(<EntityWizard entities={[]} onClose={() => {}} onCreated={() => {}} />); });
  await flush();
}

test("wizard langkah 3: empat contoh nomor dari POST /api/doc-numbering/preview dengan kode isian", async () => {
  wizardGets();
  mockPost.mockImplementation((url, body) => Promise.resolve({ data: { samples: [
    body.kind === "so" ? `${body.code}/SO-000001` : `${body.code}/${body.kind.toUpperCase()}-00001`] } }));
  await mountWizard();
  await keLangkah3();
  await tunggu();
  const calls = mockPost.mock.calls.filter(([u]) => u === "/api/doc-numbering/preview");
  expect(calls.map(([, b]) => b)).toEqual(PREVIEW_KINDS.map(([kind]) => ({ kind, entity_id: "", code: "UJINOM" })));
  expect(q("entity-wizard-number-so").textContent).toBe("UJINOM/SO-000001");   // lebar 6 dari aturan grup
  expect(q("entity-wizard-number-fkt").textContent).toBe("UJINOM/FKT-00001");
  await click(q("entity-wizard-next"));
  expect(q("entity-wizard-summary").textContent).toContain("UJINOM/SO-000001");
});

test("wizard langkah 3: pratinjau tak terbaca → bentuk cadangan KODE/SO-00001", async () => {
  wizardGets();
  mockPost.mockRejectedValue({ response: { status: 403, data: { detail: "tanpa akses" } } });
  await mountWizard();
  await keLangkah3();
  await tunggu();
  expect(q("entity-wizard-number-so").textContent).toBe("UJINOM/SO-00001");
  expect(q("entity-wizard-number-ar").textContent).toBe("UJINOM/AR-00001");
});
