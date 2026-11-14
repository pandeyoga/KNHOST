// KP-T6 — dokumen & cetak per PT (uji komponen; U14 uji jalan peramban terpisah). Perancang dokumen: identitas kop
// hanya-baca dari Profil PT (tanpa isian teks), kotak "Kop PT ini masih memakai teks lama" dengan dua tombol (alasan +
// konfirmasi yang menyebut PT), pemilih "Berlaku untuk" (lapisan PT: isian lain abu-abu, tanda "khusus PT ini" + kembali
// ke aturan semua PT), keterangan token {{rekening_bank}}. Profil PT: tiga isian kop baru.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockPatch = jest.fn();
const mockPut = jest.fn();
const mockDelete = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: (...a) => mockPatch(...a),
    put: (...a) => mockPut(...a), delete: (...a) => mockDelete(...a), defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
// Pemilih bawaan (cmdk/radix) diganti elemen polos.
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"] || p.testId} value={p.value ?? ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      {(p.options || []).map((o) => <option key={String(o.value)} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("@/components/ui/switch", () => ({
  __esModule: true,
  Switch: (p) => <input type="checkbox" data-testid={p["data-testid"]} checked={!!p.checked} disabled={p.disabled}
    onChange={(e) => p.onCheckedChange && p.onCheckedChange(e.target.checked)} />,
}));
jest.mock("@/components/ui/tabs", () => {
  const R = require("react");
  const Ctx = R.createContext("");
  return {
    __esModule: true,
    Tabs: ({ value, children }) => <Ctx.Provider value={value}>{children}</Ctx.Provider>,
    TabsContent: ({ value, children }) => (R.useContext(Ctx) === value ? <div data-testid={`tab-isi-${value}`}>{children}</div> : null),
  };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange(e.target.value)} />,
  formatDateId: (v) => (v ? `tgl ${String(v).slice(0, 10)}` : ""),
}));

import PdfTemplateDesigner from "../pdf/PdfTemplateDesigner";
import EntityDetailDrawer from "../settings/entities/EntityDetailDrawer";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(<>{el}<ConfirmHost /></>); });
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
async function choose(el, value) {
  const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new Event("change", { bubbles: true })); });
  await flush(4);
}

const ENTITIES = [{ id: "ent_ksc", legal_name: "Sukacita Textile" }, { id: "ent_kanda", legal_name: "Kanda Fabric" }];
const PT_KEYS = ["intro_text", "closing_note", "footer_text", "show_place_date", "place", "signature_slots",
  "watermark_text", "watermark_opacity"];
const GROUP = { paper_size: "A4", place: "Bandung", show_place_date: true, closing_note: "Terima kasih.", intro_text: "",
  signature_slots: [], watermark_text: "", footer_text: "", sections: {}, table: {} };
const PLACEHOLDERS = [{ token: "nomor", label: "Nomor dokumen" },
  { token: "rekening_bank", label: "Rekening bank pembayaran PT",
    note: "Rekening bank pembayaran PT. Kosong bila PT punya lebih dari satu rekening dan belum ada rekening tujuan di pesanan." }];
const BRANDING_LAMA = {
  entity_id: "ent_kanda", company_name: "Kanda Fabric", address: "Alamat Lama 1", npwp: "02.345.678.9-012.000",
  phone: "", email: "", tagline: "", website: "", logo_src: "", signatures: [], identity_source: "teks_lama",
  identity_conflicts: [{ field: "address", label: "Alamat", print_value: "Alamat Lama 1", profile_value: "Jl. Baru 9, Jakarta" }],
};

function template(params) {
  const pt = params?.entity_id;
  return {
    data: {
      doc_type: "__default__", scope: pt || "all", config: pt ? { ...GROUP, place: "Jakarta" } : GROUP,
      group_config: GROUP, pt_layer_keys: PT_KEYS, pt_override_keys: pt ? ["place"] : [],
      meta: { customized: !!pt, version: pt ? 1 : 0, override_keys: pt ? ["place"] : [] },
      defaults: GROUP, default_effective: GROUP, placeholders: PLACEHOLDERS,
      key_labels: { place: "Tempat", paper_size: "Ukuran kertas" },
    },
  };
}

function setupApi(branding = BRANDING_LAMA) {
  mockGet.mockImplementation((url, opts) => {
    if (url === "/api/pdf/templates") return Promise.resolve({ data: { data: [], placeholders: PLACEHOLDERS } });
    if (url.startsWith("/api/pdf/templates/")) return Promise.resolve(template(opts?.params));
    if (url.startsWith("/api/pdf/branding/")) return Promise.resolve({ data: branding });
    if (url.startsWith("/api/pdf/sample/")) return Promise.resolve({ data: { source_id: null, label: "Faktur" } });
    return Promise.resolve({ data: {} });
  });
  mockPut.mockImplementation((url, body, opts) => Promise.resolve(
    url.startsWith("/api/pdf/branding/") ? { data: branding } : template(opts?.params)));
  mockPost.mockResolvedValue({ data: { ...branding, identity_source: "profil", identity_conflicts: [], address: "Jl. Baru 9, Jakarta" } });
}

const ADMIN = { role: "admin", permissions: { pdf_template: ["view", "manage"], entity: ["view", "update"] } };

async function designer(user = ADMIN) {
  await mount(<PdfTemplateDesigner currentUser={user} selectedEntity="ent_kanda" entities={ENTITIES} />);
  await flush(8);
}

beforeEach(() => {
  mockGet.mockReset(); mockPost.mockReset(); mockPut.mockReset(); mockPatch.mockReset(); mockDelete.mockReset();
});
afterEach(() => {
  roots.forEach((r) => act(() => r.unmount()));
  roots = [];
  document.body.innerHTML = "";
});

describe("KP-T6 · perancang dokumen", () => {
  test("U14 (komponen) — kop tanpa isian teks identitas; identitas hanya-baca dari Profil PT", async () => {
    setupApi({ ...BRANDING_LAMA, identity_source: "profil", identity_conflicts: [], address: "Jl. Baru 9, Jakarta" });
    await designer();
    await click(q("pdf-tab-kop"));
    ["pdf-brand-name", "pdf-brand-address", "pdf-brand-phone", "pdf-brand-npwp", "pdf-brand-email",
      "pdf-brand-website", "pdf-brand-tagline"].forEach((id) => expect(q(id)).toBeNull());
    expect(q("pdf-brand-identity-address").textContent).toContain("Jl. Baru 9, Jakarta");
    expect(q("pdf-brand-identity-source").textContent).toBe("Diambil dari Profil PT.");
    expect(q("pdf-brand-conflicts")).toBeNull();
    // simpan kop = hanya gambar (tanpa teks identitas)
    await click(q("pdf-brand-save"));
    const [url, body] = mockPut.mock.calls.find(([u]) => u === "/api/pdf/branding/ent_kanda");
    expect(url).toBe("/api/pdf/branding/ent_kanda");
    expect(Object.keys(body)).toEqual([]);
  });

  test("U14 (komponen) — kotak teks lama: tabel selisih + dua tombol; pilihan meminta alasan & menyebut PT", async () => {
    setupApi();
    await designer();
    await click(q("pdf-tab-kop"));
    const box = q("pdf-brand-conflicts");
    expect(box.textContent).toContain("Kop PT ini masih memakai teks lama");
    expect(q("pdf-brand-conflicts-table").textContent).toContain("Yang tercetak sekarang");
    expect(q("pdf-brand-conflicts-table").textContent).toContain("Di Profil PT");
    expect(q("pdf-brand-conflict-address").textContent).toContain("Alamat Lama 1");
    expect(q("pdf-brand-copy-to-profile").textContent).toBe("Salin teks kop ke Profil PT");
    await click(q("pdf-brand-use-profile"));
    expect(q("pdf-identity-confirm").textContent).toContain("Kanda Fabric");
    expect(q("pdf-identity-confirm-confirm").disabled).toBe(true);           // alasan wajib
    await type(q("pdf-identity-confirm-reason"), "Alamat pindah");
    await click(q("pdf-identity-confirm-confirm"));
    expect(mockPost).toHaveBeenCalledWith("/api/pdf/branding/ent_kanda/identity",
      { action: "pakai_profil", reason: "Alamat pindah" });
    expect(q("pdf-brand-conflicts")).toBeNull();
  });

  test("kotak teks lama tanpa akses ubah Profil PT: tombol disembunyikan, alasan dijelaskan", async () => {
    setupApi();
    await designer({ role: "x", permissions: { pdf_template: ["view", "manage"] } });
    await click(q("pdf-tab-kop"));
    expect(q("pdf-brand-use-profile")).toBeNull();
    expect(q("pdf-brand-conflicts-noaccess")).not.toBeNull();
  });

  test("U14 (komponen) — Berlaku untuk: lapisan PT memuat/menyimpan ber-entity_id; isian grup abu-abu", async () => {
    setupApi();
    await designer();
    const sel = q("pdf-scope-select");
    expect([...sel.options].map((o) => o.textContent)).toEqual(["Semua PT", "Hanya Kanda Fabric"]);
    // tombol mati diberi alasan tertulis (standar UI), bukan hanya tooltip
    expect(q("pdf-reset-default").disabled).toBe(true);
    expect(q("pdf-reset-reason").textContent).toContain("belum ada setelan khusus");
    expect(q("pdf-download-reason").textContent).toContain("belum ada dokumen contoh");
    await choose(sel, "pt");
    expect(q("pdf-reset-default").disabled).toBe(false);
    expect(q("pdf-reset-reason")).toBeNull();
    expect(mockGet.mock.calls.some(([u, o]) => u === "/api/pdf/templates/__default__"
      && o?.params?.entity_id === "ent_kanda")).toBe(true);
    expect(q("pdf-layer-info-pt").textContent).toContain("khusus PT ini: Tempat");
    // Layout = aturan semua PT
    expect(q("pdf-group-only-layout").textContent.trim()).toBe("Diatur untuk semua PT.");
    expect(q("pdf-fieldset-layout").disabled).toBe(true);
    // Footer: tempat ditimpa PT → tanda + kembali ke aturan semua PT; nomor halaman dikunci
    await click(q("pdf-tab-footer"));
    expect(q("pdf-show-page-numbers").disabled).toBe(true);
    expect(q("pdf-place").value).toBe("Jakarta");
    expect(q("pdf-pt-mark-place").textContent).toContain("khusus PT ini");
    await click(q("pdf-pt-revert-place"));
    expect(q("pdf-place").value).toBe("Bandung");
    expect(q("pdf-pt-mark-place")).toBeNull();
    await click(q("pdf-save-template"));
    const put = mockPut.mock.calls.find(([u]) => u === "/api/pdf/templates/__default__");
    expect(put[2]).toEqual({ params: { entity_id: "ent_kanda" } });
    expect(q("pdf-reset-default").textContent).toContain("Kembali ke aturan semua PT");
  });

  test("naskah memuat keterangan {{rekening_bank}}", async () => {
    setupApi();
    await designer();
    await click(q("pdf-tab-naskah"));
    expect(q("pdf-closing-note-chip-rekening_bank")).not.toBeNull();
    expect(q("pdf-token-note-rekening_bank").textContent).toContain(
      "Kosong bila PT punya lebih dari satu rekening dan belum ada rekening tujuan di pesanan.");
  });
});

describe("KP-T6 · Profil PT", () => {
  test("isian Nama di kop surat, Slogan, Situs web; disimpan lewat PATCH", async () => {
    const ent = { id: "ent_kanda", legal_name: "Kanda Fabric", short_name: "Kanda", type: "CV", status: "active",
      doc_prefix: "KANDA", print_name: "", tagline: "", website: "", default_tax_mode: "non_ppn" };
    mockGet.mockImplementation((url) => {
      if (url === "/api/entities/ent_kanda") return Promise.resolve({ data: ent });
      if (url.includes("readiness")) return Promise.resolve({ data: { items: [] } });
      return Promise.resolve({ data: [] });
    });
    mockPatch.mockResolvedValue({ data: { ...ent, print_name: "KANDA TEKSTIL" } });
    await mount(<EntityDetailDrawer entityId="ent_kanda" canManage onClose={() => {}} />);
    await flush(8);
    expect(q("entity-detail-print_name-input")).not.toBeNull();
    expect(q("entity-detail-print_name-hint").textContent).toBe("Kosongkan untuk memakai nama legal.");
    expect(q("entity-detail-tagline-input")).not.toBeNull();
    expect(q("entity-detail-website-input")).not.toBeNull();
    await type(q("entity-detail-print_name-input"), "KANDA TEKSTIL");
    await click(q("entity-detail-save"));
    const call = mockPatch.mock.calls.find(([u]) => u === "/api/entities/ent_kanda");
    expect(call[1]).toEqual({ data: { print_name: "KANDA TEKSTIL" } });
  });
});
