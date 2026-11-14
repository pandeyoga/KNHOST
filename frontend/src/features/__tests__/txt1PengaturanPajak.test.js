// TX-T1 — layar pajak: pratinjau harga memakai faktor & cara bulat pengaturan PT (sama dengan server), rincian faktur
// "Aturan pajak saat terbit" + lencana "Data pajak belum lengkap", pilihan kode transaksi dari daftar PT, bagian
// "Data pajak" form pelanggan, sakelar "Pesanan tanpa PPN" di checkout. Uji komponen (uji jalan peramban terpisah, U16).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { computeOrderPreview, roundTax } from "../../utils/pricing";
import { taxBreakdownRows, taxRuleRows, dppFactorText } from "../../utils/taxBreakdown";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), patch: () => Promise.resolve({ data: {} }),
    put: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
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
jest.mock("../documents/DocumentActionsBar", () => () => null);

// eslint-disable-next-line import/first
import TaxInvoices from "../finance/TaxInvoices";
// eslint-disable-next-line import/first
import CustomerTaxSection, { taxIdWarning, taxProfileFromForm, taxFormFromProfile } from "../crm/CustomerTaxSection";
// eslint-disable-next-line import/first
import CheckoutNonPpn from "../pos/CheckoutNonPpn";

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
  await act(async () => { root.render(el); });
  await flush();
  return host;
}
async function click(el) { await act(async () => { el.click(); }); await flush(); }
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  document.body.innerHTML = "";
  mockGet.mockReset();
});

const TAX = { ppn_rate: 12, dpp_nilai_lain: true, ppn_mode: "excluded", is_pkp: true,
  dpp_nilai_lain_pembilang: 11, dpp_nilai_lain_penyebut: 12, pembulatan_tingkat: "dokumen", pembulatan_satuan: "dua_desimal" };
const item = (price, quantity = 1) => ({ product: { price }, quantity });

// ── pratinjau = server (U1, U4, U5, U6) ─────────────────────────────────────────────────────────────────────────────
test("U1/U4: faktor DPP nilai lain dari pengaturan (bawaan 11/12; 12/12 → DPP = harga)", () => {
  const a = computeOrderPreview([item(1_200_000, 10)], 0, { tax: TAX });
  expect([a.dpp, a.ppn, a.grand, a.dppFactorLabel]).toEqual([11_000_000, 1_320_000, 13_320_000, "11/12"]);
  const b = computeOrderPreview([item(1_200_000, 10)], 0, { tax: { ...TAX, dpp_nilai_lain_pembilang: 12 } });
  expect([b.dpp, b.ppn]).toEqual([12_000_000, 1_440_000]);
  // server lama tanpa kunci faktor → bawaan registry 11/12 (perilaku sebelum TX-T1)
  const c = computeOrderPreview([item(1_200_000, 10)], 0, { tax: { ppn_rate: 12, dpp_nilai_lain: true } });
  expect([c.dpp, c.ppn]).toEqual([11_000_000, 1_320_000]);
});

test("U5/U6: rupiah penuh; per baris lawan per dokumen", () => {
  const rp = { ...TAX, pembulatan_satuan: "rupiah_penuh" };
  const a = computeOrderPreview([item(1_234_567)], 0, { tax: rp });
  expect([a.ppn, a.dpp, a.grand]).toEqual([135_802, 1_131_686, 1_370_369]);
  const dua = [item(100_005), item(100_005)];
  expect(computeOrderPreview(dua, 0, { tax: { ...rp, pembulatan_tingkat: "baris" } }).ppn).toBe(22_002);
  expect(computeOrderPreview(dua, 0, { tax: rp }).ppn).toBe(22_001);
  expect(roundTax(135_802.37, "dua_desimal")).toBe(135_802.37);
  expect(roundTax(11_000.55, "rupiah_penuh")).toBe(11_001);
});

test("Rincian PPN: pecahan dari potret dokumen; aturan saat terbit", () => {
  const doc = { ppn_rate: 12, ppn_amount: 1_440_000, grand_total: 13_440_000, dpp: 12_000_000, dpp_nilai_lain: true,
    tax_snapshot: { ppn_rate: 12, dpp_nilai_lain: true, dpp_pembilang: 12, dpp_penyebut: 12, ppn_mode: "excluded",
      pembulatan_tingkat: "baris", pembulatan_satuan: "rupiah_penuh", is_pkp: true, berlaku_pada: "2026-11-14T03:00:00+00:00" } };
  expect(taxBreakdownRows(doc).map((r) => r.label)).toContain("DPP nilai lain (12/12)");
  expect(dppFactorText({})).toBe("11/12");   // dokumen lama
  const rows = taxRuleRows(doc);
  expect(rows.map((r) => r.key)).toEqual(["tarif", "faktor", "bulat", "mode", "berlaku"]);
  expect(rows.find((r) => r.key === "bulat").value).toBe("per baris, rupiah penuh");
  expect(taxRuleRows({ tax_snapshot: { is_pkp: false } })).toEqual([{ key: "pkp", label: "PPN", value: "Tanpa PPN (bukan PKP)" }]);
  expect(taxRuleRows({})).toBeNull();
});

// ── Faktur Keluaran (U7/U8 layar, U10, U16 sebagian) ────────────────────────────────────────────────────────────────
const FKT = {
  id: "f1", number: "FKT-1", order_number: "SO-1", status: "normal", nsfp: "", entity_id: "ent_ksc", kode_transaksi: "04",
  customer_name: "Toko Uji", ppn_rate: 12, ppn_amount: 1_320_000, grand_total: 13_320_000, dpp: 11_000_000, dpp_nilai_lain: true,
  customer_tax: { id_type: "", id_number: "", tax_name: "Toko Uji", tax_address: "", is_pkp: null },
  data_incomplete: ["identitas_pajak", "alamat_pajak"],
  tax_snapshot: { ppn_rate: 12, dpp_nilai_lain: true, dpp_pembilang: 11, dpp_penyebut: 12, ppn_mode: "excluded",
    pembulatan_tingkat: "dokumen", pembulatan_satuan: "dua_desimal", is_pkp: true, berlaku_pada: "2026-11-14T03:00:00+00:00" },
};
function routeGet(map) {
  mockGet.mockImplementation((url, cfg) => {
    const key = Object.keys(map).find((k) => url.endsWith(k));
    const v = key ? map[key] : [];
    return Promise.resolve({ data: typeof v === "function" ? v(cfg) : v });
  });
}

test("Faktur Keluaran: status ikon+teks, lencana data belum lengkap, rincian aturan saat terbit, kode dari daftar PT", async () => {
  routeGet({ "/tax-invoices": [FKT],
    "/settings/effective": (cfg) => ({ tax: { kode_transaksi_diizinkan: cfg?.params?.entity_id === "ent_ksc" ? ["01", "04", "08"] : [] } }) });
  await mount(<TaxInvoices currentUser={{ role: "admin", permissions: { tax_invoice: ["*"] } }} />);
  const pill = q("fkt-status");
  expect(pill.className).toMatch(/status-pill/);
  expect(pill.querySelector("svg")).not.toBeNull();             // ikon + teks + warna
  expect(q("fkt-incomplete-f1").textContent).toMatch(/Data pajak belum lengkap/);
  expect(q("fkt-table").className).toMatch(/data-table head-wrap/);
  expect(document.body.querySelector("th.col-sticky-end")).not.toBeNull();
  await click(q("fkt-detail-f1"));
  expect(q("fkt-detail").getAttribute("role")).toBe("dialog");
  expect(q("fkt-rule-tarif").textContent).toMatch(/12%/);
  expect(q("fkt-rule-faktor").textContent).toMatch(/11\/12/);
  expect(q("fkt-detail-incomplete").textContent).toMatch(/Identitas pajak \(NPWP\/NIK\) belum diisi/);
  await click(q("fkt-detail-close"));
  await click(q("fkt-nsfp-f1"));
  const opts = [...q("fkt-kode-select").querySelectorAll("option")].map((o) => o.value);
  expect(opts).toEqual(["01", "04", "08"]);                     // daftar kode PT faktur (bukan daftar tertulis)
  expect(mockGet.mock.calls.some(([u, c]) => u.endsWith("/settings/effective") && c?.params?.entity_id === "ent_ksc")).toBe(true);
});

test("Faktur lama tanpa potret: rincian menulis aturan lama", async () => {
  routeGet({ "/tax-invoices": [{ ...FKT, tax_snapshot: undefined, customer_tax: undefined, data_incomplete: undefined,
    customer_npwp: "01.234.567.8-901.000" }] });
  await mount(<TaxInvoices currentUser={{ role: "admin", permissions: { tax_invoice: ["view"] } }} />);
  expect(q("fkt-incomplete-f1")).toBeNull();
  await click(q("fkt-detail-f1"));
  expect(q("fkt-detail-rules-lama").textContent).toMatch(/tarif 12%/);
  expect(q("fkt-detail-buyer").textContent).toMatch(/NPWP 01\.234/);
});

// ── Data pajak pelanggan (U9 layar) ─────────────────────────────────────────────────────────────────────────────────
function TaxHost({ init = {}, kodePt = ["01", "02", "04"], onState }) {
  const [f, setF] = React.useState({ name: "Toko A", npwp: "", ...taxFormFromProfile(null), ...init });
  React.useEffect(() => { onState && onState(f); }, [f, onState]);
  return <CustomerTaxSection number={6} f={f} set={(k, v) => setF((s) => ({ ...s, [k]: v }))} kodePt={kodePt} defaultOpen />;
}

test("Form pelanggan › Data pajak: NPWP/NIK, peringatan bentuk tanpa menghalangi, kode PT + Ikut PT", async () => {
  let last = null;
  await mount(<TaxHost onState={(f) => { last = f; }} init={{ npwp: "01.234" }} />);
  expect(q("customer-npwp-warning").textContent).toMatch(/NPWP berisi 5 angka/);
  expect([...q("customer-tax-kode").querySelectorAll("option")].map((o) => o.textContent)).toEqual(["Ikut PT", "01", "02", "04"]);
  expect([...q("customer-tax-pkp").querySelectorAll("option")].map((o) => o.textContent)).toEqual(["Belum diisi", "PKP", "Bukan PKP"]);
  await act(async () => {
    const sel = q("customer-tax-id-type");
    sel.value = "nik"; sel.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
  expect(q("customer-npwp")).toBeNull();
  expect(q("customer-tax-nik")).not.toBeNull();
  await click(q("customer-tax-always").querySelector("input"));
  const tp = taxProfileFromForm(last);
  expect(tp).toEqual({ id_type: "nik", nik: "", tax_name: "", tax_address: "", is_pkp: null, kode_transaksi: "",
    always_tax_invoice: true });
  expect(taxIdWarning("NIK", "12ab")).toBe("NIK hanya boleh berisi angka.");
  expect(taxIdWarning("NIK", "3273011234560001")).toBe("");
  expect(taxFormFromProfile({ is_pkp: false }).tax_pkp).toBe("bukan");
});

// ── Checkout: pesanan tanpa PPN (U11 layar) ─────────────────────────────────────────────────────────────────────────
function NonPpnHost({ onState }) {
  const [on, setOn] = React.useState(false);
  const [reason, setReason] = React.useState("");
  React.useEffect(() => { onState && onState({ on, reason }); }, [on, reason, onState]);
  return <CheckoutNonPpn value={{ on, setOn, reason, setReason }} />;
}

test("Checkout: sakelar Pesanan tanpa PPN + alasan wajib; pratinjau tanpa PPN", async () => {
  await mount(<NonPpnHost />);
  expect(q("checkout-non-ppn-reason")).toBeNull();
  await click(q("checkout-non-ppn-toggle"));
  expect(q("checkout-non-ppn-reason")).not.toBeNull();
  expect(q("checkout-non-ppn-hint").textContent).toMatch(/minimal 10 huruf/);
  const p = computeOrderPreview([item(1_200_000, 10)], 0, { tax: TAX }, { taxOverride: "non_ppn" });
  expect([p.ppn, p.grand, p.isPkp]).toEqual([0, 12_000_000, false]);
  // tanpa izin: pemanggil tidak mengirim `value` → tidak tampil
  document.body.innerHTML = "";
  await mount(<CheckoutNonPpn value={null} />);
  expect(q("checkout-non-ppn")).toBeNull();
});
