// KF-T4 (U14, uji komponen) — kartu Pengaturan tanpa tombol "Default": pengembali nilai berarti persis seperti labelnya,
// Simpan mati sampai alasan terisi bila wajib, draf dikosongkan saat ganti PT; editor daftar/tabel/rujukan tanpa
// mengetik kode; tautan langsung membaca indeks registry (id kelompok lama diterjemahkan).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import SettingCard from "../SettingCard";
import SettingEditor from "../SettingEditor";
import { CONFIG_EVENT, groupForKey, openConfig, resolveGroupId, sectionForKey } from "../configDeepLink";

jest.mock("../../../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("@/components/KNDateTimePicker", () => () => null);
jest.mock("../../../../components/KNDatePicker", () => (p) => <input data-testid={p["data-testid"]} value={p.value || ""}
  onChange={(e) => p.onChange(e.target.value)} />);
jest.mock("../../../../services/apiClient", () => ({ __esModule: true, default: {}, API: "/api" }));
jest.mock("../../../../services/confirmService", () => ({ askConfirm: jest.fn(async () => true), askReason: jest.fn() }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const noop = () => {};
afterEach(() => { document.body.innerHTML = ""; });

function pasang(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  return { host, root, render: async (node) => { await act(async () => { root.render(node); }); } };
}

const kartu = (over) => ({
  key: "tax.dpp_nilai_lain", label: "Pakai DPP Nilai Lain (11/12)", help: "Penjelasan.", impact: "Dampak.",
  example: "Contoh angka.", type: "bool", default: true, value: true, stored_value: true, scopes: ["global", "entity"],
  status: "active", source_layer: "global", source_label: "Aturan grup", requires_reason: true, risk: "high",
  consumers: ["services/config_service.py:compute_tax"], scheduled: [], overridden_by: null, never_changed: false,
  permission_label: "Pengaturan, Pengguna & Hak Akses", ...over,
});

function card(item, props = {}) {
  return (
    <SettingCard item={item} scopeType="entity" scopeId="ent_kanda" scopeLabel="KANDA" canEdit
      onSave={async () => true} onReset={noop} onClearEntity={noop} onWhy={noop} onSimulate={noop}
      onHistory={noop} {...props} />
  );
}

test("U14 — Satu PT, nilai warisan: tanpa Default/Ikuti nilai grup; keterangan Mengikuti nilai grup; contoh langsung tampil", async () => {
  const m = pasang();
  await m.render(card(kartu({ value: false, stored_value: false })));
  expect(m.host.textContent).not.toMatch(/Default/);
  expect(q(m.host, "cfg-clear-entity-tax.dpp_nilai_lain")).toBeNull();
  expect(q(m.host, "cfg-inherited-tax.dpp_nilai_lain").textContent).toBe("Mengikuti nilai grup");
  expect(q(m.host, "cfg-layer-badge-tax.dpp_nilai_lain").textContent).toBe("Aturan grup");
  // nilai ≠ bawaan → tautan teks "Pakai nilai bawaan sistem untuk PT ini" → onReset(item, "entity")
  expect(q(m.host, "cfg-reset-tax.dpp_nilai_lain").textContent).toBe("Pakai nilai bawaan sistem untuk PT ini");
  expect(q(m.host, "cfg-example-tax.dpp_nilai_lain").textContent).toContain("Contoh angka.");
  expect(q(m.host, "cfg-scope-can-tax.dpp_nilai_lain").textContent).toBe("Bisa dibedakan untuk: Semua PT · Satu PT");
  expect(m.host.textContent).not.toMatch(/entitas|wiring|setting/i);
});

test("U14 — Satu PT, nilai khusus PT: Ikuti nilai grup memanggil pencabut; lencana Khusus KANDA", async () => {
  const cabut = jest.fn();
  const m = pasang();
  await m.render(card(kartu({ source_layer: "entity", source_label: "Khusus PT" }), { onClearEntity: cabut }));
  expect(q(m.host, "cfg-layer-badge-tax.dpp_nilai_lain").textContent).toBe("Khusus KANDA");
  expect(q(m.host, "cfg-inherited-tax.dpp_nilai_lain")).toBeNull();
  // nilai = bawaan → tidak ada tawaran "Pakai nilai bawaan sistem untuk PT ini"
  expect(q(m.host, "cfg-reset-tax.dpp_nilai_lain")).toBeNull();
  await act(async () => { q(m.host, "cfg-clear-entity-tax.dpp_nilai_lain").click(); });
  expect(cabut).toHaveBeenCalledTimes(1);
  expect(q(m.host, "cfg-clear-entity-tax.dpp_nilai_lain").textContent).toContain("Ikuti nilai grup");
});

test("U14 — berisiko tinggi: Simpan mati sampai alasan terisi; draf kosong sesudah ganti PT", async () => {
  const simpan = jest.fn(async () => true);
  const m = pasang();
  const item = kartu();
  await m.render(card(item, { onSave: simpan }));
  const save = () => q(m.host, "cfg-save-tax.dpp_nilai_lain");
  expect(save().disabled).toBe(true);
  await act(async () => { q(m.host, "cfg-input-tax.dpp_nilai_lain").click(); });   // ubah draf
  expect(q(m.host, "cfg-dirty-tax.dpp_nilai_lain")).not.toBeNull();
  expect(save().disabled).toBe(true);                                                 // alasan wajib belum diisi
  const reason = q(m.host, "cfg-reason-tax.dpp_nilai_lain");
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
    setter.call(reason, "koreksi tarif");
    reason.dispatchEvent(new Event("input", { bubbles: true }));
  });
  expect(save().disabled).toBe(false);
  // ganti PT → draf, alasan, jadwal dikosongkan
  await m.render(card(item, { onSave: simpan, scopeId: "ent_ksc", scopeLabel: "KSC" }));
  expect(q(m.host, "cfg-dirty-tax.dpp_nilai_lain")).toBeNull();
  expect(save().disabled).toBe(true);
  await act(async () => { q(m.host, "cfg-input-tax.dpp_nilai_lain").click(); });
  expect(q(m.host, "cfg-reason-tax.dpp_nilai_lain").value).toBe("");
});

test("Semua PT: Pakai nilai bawaan sistem + daftar PT bernilai sendiri yang bisa diklik", async () => {
  const reset = jest.fn();
  const pilih = jest.fn();
  const m = pasang();
  await m.render(card(kartu({ value: false, stored_value: false, entity_overrides: [
    { entity_id: "ent_kanda", entity_label: "KANDA", value: true }] }),
  { scopeType: "global", scopeId: "", onReset: reset, onPickEntity: pilih }));
  await act(async () => { q(m.host, "cfg-reset-tax.dpp_nilai_lain").click(); });
  expect(reset).toHaveBeenCalledWith(expect.objectContaining({ key: "tax.dpp_nilai_lain" }), "global");
  expect(q(m.host, "cfg-entity-overrides-tax.dpp_nilai_lain").textContent).toContain("PT dengan nilai sendiri: KANDA = Ya / Aktif");
  await act(async () => { q(m.host, "cfg-entity-override-tax.dpp_nilai_lain-ent_kanda").click(); });
  expect(pilih).toHaveBeenCalledWith("ent_kanda");
});

test("kartu hanya-grup, terkunci, dan diubah di layar lain", async () => {
  const m = pasang();
  await m.render(card(kartu({ key: "ui.show_coming_soon", scopes: ["global"], requires_reason: false, risk: "low" })));
  expect(q(m.host, "cfg-global-only-ui.show_coming_soon").textContent)
    .toBe("Satu nilai untuk seluruh grup — tidak dibedakan per PT. Mengubah di sini berlaku untuk semua PT.");
  await m.render(card(kartu({ key: "lot.require_dye_lot", permission_label: "Stok & Persediaan" }), { canEdit: false }));
  expect(q(m.host, "cfg-readonly-lot.require_dye_lot").textContent)
    .toBe("Hanya pemegang akses 'Stok & Persediaan' yang boleh mengubah pengaturan ini.");
  await m.render(card(kartu({ key: "receiving.mode", type: "enum", edit_at: { view: "settings-receiving-ocr",
    preset: { tab: "mode" }, label: "Penerimaan & OCR › Mode Penerimaan" } })));
  expect(q(m.host, "cfg-input-receiving.mode")).toBeNull();
  expect(q(m.host, "cfg-edit-at-link-receiving.mode").textContent).toContain("Ubah di Penerimaan & OCR › Mode Penerimaan");
});

test("kartu ringkas satu baris terbuka saat diklik", async () => {
  const buka = jest.fn();
  const m = pasang();
  await m.render(card(kartu(), { collapsible: true, open: false, onToggle: buka }));
  expect(q(m.host, "cfg-value-tax.dpp_nilai_lain")).toBeNull();
  expect(q(m.host, "cfg-compact-value-tax.dpp_nilai_lain").textContent).toBe("Ya / Aktif");
  await act(async () => { q(m.host, "cfg-card-toggle-tax.dpp_nilai_lain").click(); });
  expect(buka).toHaveBeenCalledWith("tax.dpp_nilai_lain");
});

// ── editor tanpa mengetik kode ───────────────────────────────────────────────────────────────────────────────────────
async function editor(entry, value) {
  const ubah = jest.fn();
  const m = pasang();
  await m.render(<SettingEditor entry={entry} value={value} onChange={ubah} />);
  return { host: m.host, ubah };
}

test("daftar peran = kotak centang berlabel nama peran", async () => {
  const { host, ubah } = await editor({ key: "ai.margin_roles", type: "list", items: "roles",
    ref_options: [{ value: "admin", label: "Admin" }, { value: "manager", label: "Manajer" }] }, ["admin"]);
  expect(q(host, "cfg-input-ai.margin_roles").textContent).toBe("AdminManajer");
  await act(async () => { q(host, "cfg-input-ai.margin_roles-opt-manager").querySelector("input").click(); });
  expect(ubah).toHaveBeenCalledWith(["admin", "manager"]);
});

test("daftar berurutan: PT pemilik stok terkunci di urutan pertama", async () => {
  const opts = [{ value: "owner", label: "PT pemilik stok" }, { value: "lot", label: "Lot yang sama" },
    { value: "location", label: "Lokasi gudang" }];
  const { host, ubah } = await editor({ key: "allocation.priority_order", type: "list", items: "options", ordered: true,
    options: opts }, ["owner", "lot", "location"]);
  expect(q(host, "cfg-input-allocation.priority_order-up-owner")).toBeNull();
  expect(q(host, "cfg-input-allocation.priority_order-up-lot").disabled).toBe(true);
  await act(async () => { q(host, "cfg-input-allocation.priority_order-up-location").click(); });
  expect(ubah).toHaveBeenCalledWith(["owner", "location", "lot"]);
});

test("deret angka menaik dengan pratinjau kolom; rujukan master = daftar pilih", async () => {
  let r = await editor({ key: "ar.aging_buckets", type: "list", items: "int_asc", unit: "" }, [30, 60, 90]);
  expect(q(r.host, "cfg-input-ar.aging_buckets-preview").textContent).toBe("kolom 1–30, 31–60, 61–90, di atas 90 hari");
  r = await editor({ key: "finance.default_payment_term_code", type: "text", ref: "payment_term", default: "NET30",
    ref_options: [{ value: "NET30", label: "NET30 · Tempo 30 hari" }, { value: "CBD", label: "CBD · Bayar dulu" }] }, "NET30");
  const sel = q(r.host, "cfg-input-finance.default_payment_term_code");
  expect(sel.tagName).toBe("SELECT");
  expect([...sel.options].map((o) => o.textContent)).toEqual(["NET30 · Tempo 30 hari", "CBD · Bayar dulu"]);
});

test("tabel berkelompok: baris jenis dokumen tanpa pembaca tampil hanya-baca 'belum dipakai'", async () => {
  const entry = { key: "approval.extra_levels", type: "table", row_shape: "grouped_list", role_options: [
    { value: "admin", label: "Admin" }], columns: [
    { name: "doc_type", label: "Jenis dokumen", type: "enum", options: [
      { value: "purchase_order", label: "Pesanan Pembelian (PO)" },
      { value: "sales_order", label: "Pesanan penjualan", not_used: true }] },
    { name: "min_amount", label: "Mulai nilai (Rp)", type: "money" },
    { name: "role", label: "Peran penyetuju", type: "enum", ref: "role" },
    { name: "label", label: "Nama tingkat", type: "text" }] };
  const { host } = await editor(entry, {
    purchase_order: [{ min_amount: 500000000, role: "admin", label: "Direksi" }],
    sales_order: [{ min_amount: 1, role: "admin", label: "Lama" }] });
  expect(q(host, "cfg-input-approval.extra_levels-row-0")).not.toBeNull();
  expect(q(host, "cfg-input-approval.extra_levels-row-1-unused").textContent).toContain("belum dipakai");
});

test("tautan langsung membaca indeks registry; id kelompok lama diterjemahkan", () => {
  expect(groupForKey("ar.grace_days")).toBe("pembayaran-pelanggan");
  expect(sectionForKey("ar.grace_days")).toBe("denda");
  expect(resolveGroupId("lot")).toEqual({ group: "penerimaan", section: "nomor-lot" });
  const terima = jest.fn();
  window.addEventListener(CONFIG_EVENT, terima);
  openConfig({ group: "notifikasi" });
  window.removeEventListener(CONFIG_EVENT, terima);
  expect(terima.mock.calls[0][0].detail).toEqual({ key: "", group: "persetujuan", section: "pemberitahuan" });
});
