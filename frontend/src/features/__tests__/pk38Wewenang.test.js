// PK-38 — layar (U18 bagian komponen; uji jalan peramban terpisah):
//  * Order Makloon › Catat Jasa / Terima Hasil: tanpa wewenang nilai jasa (`service_value_editable` salah) isian Ongkos
//    Jasa, Biaya Lain, PPN, No. Faktur Mitra tidak tampil; ada satu keterangan; tombol tetap; isi kirim tanpa nilai.
//  * Pesanan › Koreksi Pesanan: termin lebih longgar dari termin sekarang mati dengan petunjuk bila `can_loosen_term`
//    salah; bila benar dan dipilih → peringatan.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: jest.fn(() => Promise.resolve({ data: {} })), patch: jest.fn(),
    delete: jest.fn(), defaults: { headers: { common: {} } } },
  API: "/api",
}));
// Pemilih bawaan (cmdk/radix) diganti <select> polos; opsi `disabled` diteruskan.
jest.mock("../../components/KNSelect", () => {
  const Sel = ({ value, onValueChange, options = [], "data-testid": tid }) => (
    <select data-testid={tid} value={value || ""} onChange={(e) => onValueChange?.(e.target.value)}>
      <option value="" />
      {options.map((o) => <option key={`${o.value}`} value={o.value} disabled={!!o.disabled}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: Sel, KNSelect: Sel };
});
jest.mock("../../components/KNDatePicker", () => () => null);
jest.mock("../orders/OverrideLinesEditor", () => ({ OverrideLinesEditor: () => null }));

// eslint-disable-next-line import/first
import { RecordServiceModal, ReceiveModal, KETERANGAN_NILAI_JASA, nilaiJasaBolehDiisi } from "../purchasing/makloon/MkoStepModals";
// eslint-disable-next-line import/first
import SalesOrderOverrideDialog, { PERINGATAN_TERMIN_LONGGAR, PETUNJUK_TERMIN_MATI, terminLebihLonggar } from "../orders/SalesOrderOverrideDialog";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
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
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  document.body.innerHTML = "";
  mockGet.mockReset();
});

const STEP = { seq: 2, stage_label: "Pembuatan kasa", makloon_id: "mkl_1", makloon_name: "Mitra Kasa", input_qty: 100,
  input_unit: "meter", input_name: "Kain grey", aux_cost: 25000, tariff_basis: "lumpsum", expected_output_qty: 100,
  output_unit: "meter" };
const NILAI = ["mko-service-tariff", "mko-service-aux", "mko-service-ppn", "mko-service-invoice"];

describe("PK-38 — nilai jasa makloon", () => {
  test("aturan tampil: bawaan boleh (data lama tanpa tanda), salah = tidak boleh", () => {
    expect(nilaiJasaBolehDiisi({})).toBe(true);
    expect(nilaiJasaBolehDiisi({ service_value_editable: true })).toBe(true);
    expect(nilaiJasaBolehDiisi({ service_value_editable: false })).toBe(false);
  });

  test("Catat Jasa tanpa wewenang: isian nilai tidak tampil, keterangan tampil, isi kirim tanpa nilai", async () => {
    const onConfirm = jest.fn(() => Promise.resolve());
    await mount(<RecordServiceModal step={{ ...STEP, service_value_editable: false }} mkoNumber="MKO-1" busy={false}
      onClose={() => {}} onConfirm={onConfirm} />);
    for (const id of NILAI) expect(q(id)).toBeNull();
    expect(q("mko-service-value-note").textContent).toBe(KETERANGAN_NILAI_JASA);
    expect(q("mko-service-confirm").textContent).toMatch("Catat Jasa & Terbitkan Tagihan");
    await act(async () => { q("mko-service-confirm").click(); });
    await flush();
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onConfirm.mock.calls[0][0]).toMatchObject({ tariff: 0, ppn: 0, supplier_invoice_no: "", aux_cost: 25000 });
  });

  test("Catat Jasa dengan wewenang: isian nilai tampil, tanpa keterangan", async () => {
    await mount(<RecordServiceModal step={{ ...STEP, service_value_editable: true }} mkoNumber="MKO-1" busy={false}
      onClose={() => {}} onConfirm={() => Promise.resolve()} />);
    for (const id of NILAI) expect(q(id)).not.toBeNull();
    expect(q("mko-service-value-note")).toBeNull();
  });

  test("Terima Hasil tanpa wewenang: Ongkos Jasa, Bahan Pembantu, PPN, No. Faktur tidak tampil", async () => {
    await mount(<ReceiveModal step={{ ...STEP, service_value_editable: false }} warehouses={[{ id: "w1", name: "Gd", code: "G1" }]}
      defaultWh="w1" mkoNumber="MKO-1" busy={false} onClose={() => {}} onConfirm={() => Promise.resolve()} />);
    for (const id of ["mko-recv-tariff", "mko-recv-aux", "mko-recv-ppn", "mko-recv-invoice"]) expect(q(id)).toBeNull();
    expect(q("mko-recv-value-note").textContent).toBe(KETERANGAN_NILAI_JASA);
    expect(q("mko-recv-output-qty")).not.toBeNull();
  });
});

const TERMS = [
  { code: "CBD", name: "CBD — Bayar Sebelum Kirim", dp_percent: 100, net_days: 0 },
  { code: "DP50", name: "DP 50% + Pelunasan", dp_percent: 50, net_days: 14 },
  { code: "NET14", name: "Kredit NET 14 Hari", dp_percent: 0, net_days: 14 },
  { code: "NET30", name: "Kredit NET 30 Hari", dp_percent: 0, net_days: 30 },
];
const ORDER = { id: "so_1", number: "SO-1", customer_name: "Toko", payment_term_code: "CBD", items: [] };

function stubApi(ctx) {
  mockGet.mockImplementation((url) => {
    if (url.endsWith("/override-context")) return Promise.resolve({ data: ctx });
    if (url.endsWith("/payment-terms")) return Promise.resolve({ data: TERMS });
    return Promise.resolve({ data: {} });
  });
}
const opsi = (code) => q("override-term").querySelector(`option[value="${code}"]`);

describe("PK-38 — ganti termin di Koreksi Pesanan", () => {
  test("arah termin sama dengan server", () => {
    const t = Object.fromEntries(TERMS.map((x) => [x.code, x]));
    expect(terminLebihLonggar(t.CBD, t.NET30)).toBe(true);
    expect(terminLebihLonggar(t.NET30, t.CBD)).toBe(false);
    expect(terminLebihLonggar(t.DP50, t.NET30)).toBe(true);
    expect(terminLebihLonggar(t.NET14, t.NET30)).toBe(true);
    expect(terminLebihLonggar(t.NET30, t.NET14)).toBe(false);
    expect(terminLebihLonggar(null, t.NET30)).toBe(true);   // termin tak dikenal = 0 % / 0 hari
  });

  test("tanpa izin: termin lebih longgar mati dengan petunjuk; yang lebih ketat tetap bisa dipilih", async () => {
    stubApi({ locked_reason: "", addresses: [], can_loosen_term: false,
      current_term: { code: "CBD", dp_percent: 100, net_days: 0 } });
    await mount(<SalesOrderOverrideDialog order={ORDER} onClose={() => {}} onDone={() => {}} />);
    expect(opsi("NET30").disabled).toBe(true);
    expect(opsi("NET30").textContent).toContain(PETUNJUK_TERMIN_MATI);
    expect(opsi("DP50").disabled).toBe(true);
    expect(opsi("CBD").disabled).toBe(false);
    expect(q("override-term-loosen-warning")).toBeNull();
  });

  test("dengan izin: termin lebih longgar bisa dipilih dan peringatan tampil", async () => {
    stubApi({ locked_reason: "", addresses: [], can_loosen_term: true,
      current_term: { code: "CBD", dp_percent: 100, net_days: 0 } });
    await mount(<SalesOrderOverrideDialog order={ORDER} onClose={() => {}} onDone={() => {}} />);
    expect(opsi("NET30").disabled).toBe(false);
    const sel = q("override-term");
    await act(async () => {
      sel.value = "NET30";
      sel.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await flush();
    expect(q("override-term-loosen-warning").textContent).toBe(PERINGATAN_TERMIN_LONGGAR);
  });
});
