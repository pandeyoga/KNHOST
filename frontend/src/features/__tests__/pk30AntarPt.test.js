// PK-30 — layar antar-PT: tombol keranjang menjadi "Buat Permintaan Internal" (IC-09), form transaksi baru menjaga
// harga/mode PPN dengan izin `interco.override_terms` + alasan (IC-10), rincian menampilkan penyesuaian panjang roll,
// penyimpangan harga, dan pembeli bukan PKP (IC-02/IC-10).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { FulfillmentInfo, INTERNAL_REQUEST_REASON } from "../../components/FulfillmentInfo";
import IntercoCreateModal from "../finance/interco/IntercoCreateModal";
import { IntercoTermsNotes } from "../finance/interco/IntercoDetailParts";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), defaults: { headers: { common: {} } } },
  API: "/api",
}));
// Pemilih bawaan (cmdk/radix) diganti <select> polos — yang diuji logika form, bukan pemilihnya.
jest.mock("../../components/KNSelect", () => {
  const Sel = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={!!p.disabled}
      onChange={(e) => p.onValueChange?.(e.target.value)}>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: Sel, KNSelect: Sel };
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  await act(async () => {});
  return { host, root };
}
async function choose(sel, value) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(sel, value);
    sel.dispatchEvent(new Event("change", { bubbles: true }));
  });
}
async function type(el, value) {
  await act(async () => {
    const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await act(async () => {});
}

const PRODUK = [{ id: "P1", sku: "K-01", name: "Katun" }];
const META = { defaults: { pricing_mode: "fixed_price", ppn_mode: "tanpa_ppn" } };
beforeEach(() => {
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.includes("/interco/meta") ? META : PRODUK }));
  mockPost.mockResolvedValue({ data: { id: "ic1" } });
  localStorage.setItem("kn_user", JSON.stringify({ permissions: { order: ["view", "override"] } }));
});
afterEach(() => {
  mockGet.mockReset(); mockPost.mockReset();
  localStorage.clear();
  document.body.innerHTML = "";
});

const LINE = {
  product_id: "P1", unit: "meter", primary_mode: "inter_company", own_atp: 20, own_available: 20, own_incoming: 0,
  breakdown: { inter_company: 30, backorder: 0 }, explanation: "Sebagian dari PT lain",
  cross_entity: [{ entity_id: "ent_kanda", entity_name: "Kanda" }],
};

test("U16 (komponen) — tombol keranjang: Buat Permintaan Internal, nomor permintaan, galat", async () => {
  const onReq = jest.fn();
  let r = await mount(<FulfillmentInfo line={LINE} loading={false} reqStatus={undefined} onRequestTransfer={onReq} />);
  const btn = q(r.host, "request-transfer-P1");
  expect(btn.textContent).toContain("Buat Permintaan Internal (30 meter)");
  expect(btn.textContent).not.toContain("Minta Transfer");
  expect(btn.className).toContain("secondary-button");
  await click(btn);
  expect(onReq).toHaveBeenCalledWith(LINE);
  document.body.innerHTML = "";
  r = await mount(<FulfillmentInfo line={LINE} reqStatus={{ status: "requested", number: "KSC/PIN-00007" }}
    onRequestTransfer={onReq} />);
  expect(q(r.host, "transfer-requested-P1").textContent)
    .toContain("Permintaan Internal KSC/PIN-00007 dibuat — menunggu Admin Sales.");
  document.body.innerHTML = "";
  r = await mount(<FulfillmentInfo line={LINE} reqStatus={{ status: "error", message: "Pilih PT dulu." }}
    onRequestTransfer={onReq} />);
  expect(q(r.host, "transfer-request-error-P1").textContent.trim()).toBe("Permintaan gagal dibuat: Pilih PT dulu.");
  expect(INTERNAL_REQUEST_REASON).toBe("Stok PT sendiri tidak cukup — diminta dari keranjang penjualan");
});

test("Form antar-PT tanpa izin override: harga & mode terkunci, tidak mengirim penyimpangan", async () => {
  const ents = [{ id: "ent_a", short_name: "Sukacita" }, { id: "ent_b", short_name: "Cipta" }];
  const { host } = await mount(<IntercoCreateModal entities={ents} currentEntityId="ent_a" onClose={() => {}}
    onCreated={() => {}} />);
  expect(q(host, "interco-create-pricing").disabled).toBe(true);
  expect(q(host, "interco-create-ppn").disabled).toBe(true);
  expect(q(host, "interco-create-price-0").disabled).toBe(true);
  expect(q(host, "interco-create-price-locked").textContent).toContain("Ubah harga/PPN di luar kontrak");
  // bawaan pengaturan PT penjual tampil di pilihan pertama
  expect(q(host, "interco-create-ppn").options[0].textContent).toContain("Tanpa PPN");
  await choose(q(host, "interco-create-buyer"), "ent_b");
  await choose(q(host, "interco-create-line-0").querySelector("select"), "P1");
  await click(q(host, "interco-create-submit"));
  const [, body] = mockPost.mock.calls[0];
  expect(body).toMatchObject({ pricing_mode: "", ppn_mode: "", items: [{ product_id: "P1", unit_price: null }] });
  expect(body.override_reason).toBeUndefined();
});

test("Form antar-PT dengan izin override: ubah harga → alasan wajib, terkirim bersama", async () => {
  const ents = [{ id: "ent_a", short_name: "Sukacita" }, { id: "ent_b", short_name: "Cipta" }];
  const { host } = await mount(<IntercoCreateModal entities={ents} currentEntityId="ent_a" canOverride
    onClose={() => {}} onCreated={() => {}} />);
  await choose(q(host, "interco-create-buyer"), "ent_b");
  await choose(q(host, "interco-create-line-0").querySelector("select"), "P1");
  expect(q(host, "interco-create-override-reason")).toBeNull();          // belum menyimpang
  await choose(q(host, "interco-create-ppn"), "tanpa_ppn");                 // sama dengan bawaan → bukan penyimpangan
  expect(q(host, "interco-create-override-reason")).toBeNull();
  await type(q(host, "interco-create-price-0"), "20000");
  expect(q(host, "interco-create-override-reason")).not.toBeNull();
  expect(q(host, "interco-create-submit").disabled).toBe(true);
  expect(q(host, "interco-create-reason-needed").textContent).toContain("minimal 5 huruf");
  await type(q(host, "interco-create-override-reason"), "harga cuci gudang");
  expect(q(host, "interco-create-submit").disabled).toBe(false);
  await click(q(host, "interco-create-submit"));
  const [, body] = mockPost.mock.calls[0];
  expect(body).toMatchObject({ ppn_mode: "", override_reason: "harga cuci gudang",
    items: [{ product_id: "P1", unit_price: 20000 }] });
});

test("Rincian: penyesuaian panjang, harga di luar kontrak, pembeli bukan PKP", async () => {
  const seller = {
    items: [{ product_id: "P1", unit: "meter" }], tax_amount: 275000, tax_warning: "pembeli_non_pkp",
    length_adjustment: { from_subtotal: 2500000, to_subtotal: 3250000, lines: [{ product_id: "P1", from_qty: 100, to_qty: 130 }] },
    terms_override: { by: "Rina Manajer", reason: "harga cuci gudang" },
  };
  const { host } = await mount(<IntercoTermsNotes seller={seller} buyer={seller} />);
  const adj = q(host, "interco-detail-length-adjustment").textContent;
  expect(adj).toContain("Disesuaikan ke panjang roll aktual: 100 → 130 meter, nilai");
  expect(adj).toMatch(/2\.500\.000.*3\.250\.000/);
  expect(q(host, "interco-detail-terms-override").textContent)
    .toBe("Harga/PPN di luar kontrak oleh Rina Manajer: harga cuci gudang");
  expect(q(host, "interco-detail-tax-warning").textContent).toMatch(/PT pembeli bukan PKP: PPN masukan .*275\.000.* tidak dapat\s*dikreditkan\./);
  document.body.innerHTML = "";
  const kosong = await mount(<IntercoTermsNotes seller={{ items: [] }} buyer={{}} />);
  expect(q(kosong.host, "interco-detail-notes")).toBeNull();
});
