// KF-T6 — tab Pengaturan › Persetujuan › Kontrol dua orang (`DualControlView`).
// Uji komponen (U18 bagian layar; uji jalan peramban terpisah): memuat aturan per lapisan, tombol Tim kecil (dialog
// baku + alasan wajib → satu PUT berisi 35 butir "1" pada lapisan terpilih), Simpan mati sampai ada perubahan,
// hanya-baca bila `can_edit` salah, galat + coba lagi.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";

const mockGet = jest.fn();
const mockPut = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), put: (...a) => mockPut(...a),
    post: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
// Pemilih bawaan (cmdk/radix) diganti <select> polos.
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
import DualControlView, { itemsPerubahan, sumberLabel } from "../settings/kontrol/DualControlView";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const ENTS = [
  { id: "ent_ksc", legal_name: "PT Kain Suka Cita", short_name: "Sukacita" },
  { id: "ent_kanda", legal_name: "CV Kanda Suka", short_name: "Kanda" },
];
const BAGIAN = ["Pembelian & hutang", "Penjualan & piutang", "Gudang & produksi", "SDM", "Buku besar"];
const row = (aksi, label, bagian, min, nominal, sumber = "default") => ({
  aksi, label, bagian, kelompok: "B", punya_nominal: nominal, min_orang: min, batas_nominal: nominal ? 0 : null,
  sumber, kunci_min_orang: `kontrol.${aksi}.min_orang`, kunci_batas: nominal ? `kontrol.${aksi}.batas_nominal` : null,
});
const DATA = (over = {}) => ({
  rows: [row("setujui_po", "Persetujuan PO", BAGIAN[0], "2", true),
    row("transfer_gudang", "Transfer gudang / antar-PT", BAGIAN[2], "1", false, "global"),
    row("jurnal_manual", "Jurnal manual", BAGIAN[4], "1", true, "entity")],
  bagian: BAGIAN, entity_id: "ent_ksc", admin_boleh_sendiri: true,
  admin_tetap_dua_orang: ["susut_makloon"], can_edit: true, ...over,
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
    root.render(<><DualControlView selectedEntity="ent_ksc" entities={ENTS} {...props} /><ConfirmHost /></>);
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
async function choose(el, value) {
  await act(async () => {
    el.value = value;
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}

afterEach(async () => {
  const openCancel = document.body.querySelector(".modal-overlay [data-testid$='-cancel']");
  if (openCancel) await click(openCancel);
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockReset(); mockPut.mockReset();
  document.body.innerHTML = "";
});

test("memuat aturan PT aktif: kelompok, label sumber, nominal '—' untuk aksi tanpa nominal", async () => {
  mockGet.mockResolvedValue({ data: DATA() });
  await mount();
  expect(mockGet).toHaveBeenCalledWith("/api/kontrol/aturan", { params: { entity_id: "ent_ksc" } });
  expect(q("dual-section-Pembelian & hutang")).not.toBeNull();
  expect(q("dual-section-SDM")).toBeNull();                               // kelompok tanpa baris tidak ditampilkan
  expect(q("dual-min-setujui_po").value).toBe("2");
  expect(q("dual-source-setujui_po").textContent).toBe("Bawaan");
  expect(q("dual-source-transfer_gudang").textContent).toBe("Mengikuti semua PT");
  expect(q("dual-source-jurnal_manual").textContent).toBe("Aturan PT ini");
  expect(q("dual-limit-transfer_gudang").textContent).toBe("—");
  expect(q("dual-save").disabled).toBe(true);
  expect(document.body.textContent).not.toContain("ent_ksc");
});

test("Tim kecil: dialog menyebut PT, alasan wajib, Batal = 0 PUT; lanjut = 1 PUT berisi semua min_orang '1'", async () => {
  mockGet.mockResolvedValue({ data: DATA() });
  mockPut.mockResolvedValue({ data: { count: 3 } });
  await mount();
  await click(q("dual-small-team"));
  expect(q("dual-small-team-confirm-message").textContent).toBe(
    "Semua aksi untuk Sukacita akan cukup diputuskan satu orang. Batas nominal tidak diubah. Lanjutkan?");
  await click(q("dual-small-team-confirm-cancel"));
  expect(mockPut).not.toHaveBeenCalled();

  await click(q("dual-small-team"));
  expect(q("dual-small-team-confirm-confirm").disabled).toBe(true);        // alasan wajib
  await type(q("dual-small-team-confirm-reason"), "Tim keuangan hanya satu orang");
  await click(q("dual-small-team-confirm-confirm"));
  expect(mockPut).toHaveBeenCalledTimes(1);
  const [url, body] = mockPut.mock.calls[0];
  expect(url).toBe("/api/config/values");
  expect(body.items).toEqual(["setujui_po", "transfer_gudang", "jurnal_manual"].map((a) => ({
    key: `kontrol.${a}.min_orang`, value: "1", reason: "Tim keuangan hanya satu orang",
    scope_type: "entity", scope_id: "ent_ksc" })));
  expect(q("dual-ok").textContent).toContain("Aturan kontrol dua orang tersimpan.");
});

test("Simpan mati sampai ada perubahan; satu alasan untuk semua butir; lapisan Semua PT = global", async () => {
  mockGet.mockResolvedValue({ data: DATA({ entity_id: "" }) });
  mockPut.mockResolvedValue({ data: {} });
  await mount({ selectedEntity: "all" });
  expect(mockGet).toHaveBeenCalledWith("/api/kontrol/aturan", { params: {} });
  expect(q("dual-source-transfer_gudang").textContent).toBe("Aturan semua PT");
  await choose(q("dual-min-transfer_gudang"), "2");
  await click(q("dual-admin-self"));
  expect(q("dual-save").disabled).toBe(false);
  await click(q("dual-save"));
  await type(q("dual-save-confirm-reason"), "Gudang wajib dua orang");
  await click(q("dual-save-confirm-confirm"));
  expect(mockPut).toHaveBeenCalledTimes(1);
  expect(mockPut.mock.calls[0][1].items).toEqual([
    { key: "kontrol.transfer_gudang.min_orang", value: "2", reason: "Gudang wajib dua orang", scope_type: "global", scope_id: "" },
    { key: "kontrol.admin_boleh_sendiri", value: false, reason: "Gudang wajib dua orang", scope_type: "global", scope_id: "" },
  ]);
});

test("hanya-baca bila can_edit salah: tanpa tombol simpan/tim kecil, pilihan terkunci", async () => {
  mockGet.mockResolvedValue({ data: DATA({ can_edit: false }) });
  await mount();
  expect(q("dual-readonly")).not.toBeNull();
  expect(q("dual-save")).toBeNull();
  expect(q("dual-small-team")).toBeNull();
  expect(q("dual-min-setujui_po").disabled).toBe(true);
  expect(q("dual-admin-self").disabled).toBe(true);
});

test("galat memuat tampil dengan Coba lagi", async () => {
  mockGet.mockRejectedValueOnce({ response: { status: 500, data: { detail: "Server sedang sibuk." } } });
  mockGet.mockResolvedValueOnce({ data: DATA() });
  await mount();
  expect(q("dual-error")).not.toBeNull();
  const retry = q("dual-error").querySelector("button");
  await click(retry);
  expect(q("dual-error")).toBeNull();
  expect(q("dual-min-setujui_po")).not.toBeNull();
});

test("itemsPerubahan & sumberLabel", () => {
  const d = DATA();
  expect(itemsPerubahan(d, { rows: {} }, "ent_ksc", "x")).toEqual([]);
  expect(itemsPerubahan(d, { rows: { setujui_po: { batas_nominal: "5.000.000" } } }, "ent_ksc", "x")).toEqual([
    { key: "kontrol.setujui_po.batas_nominal", value: 5000000, reason: "x", scope_type: "entity", scope_id: "ent_ksc" }]);
  expect(sumberLabel("default", false)).toBe("Bawaan");
});
