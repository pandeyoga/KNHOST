// S2 (pelatihan keuangan 18 Nov) — uji jalan "Amandemen & situasi khusus pengadaan":
//   · Form tagihan pemasok menilai 3-way match dengan persen saja, padahal server (`evaluate_match`) juga memakai ambang
//     RUPIAH (`contra_bon.value_tolerance_rupiah`, bawaan Rp 50.000): selisih harga 5,7% senilai Rp 40.000 tampil
//     "Ada selisih (perlu persetujuan)" padahal server langsung memposting; lebih tagih 2 yard (Rp 28.000) tampil
//     "Lebih tagih (tidak bisa dikirim)" padahal server menerimanya dengan persetujuan. Kini ambang = konteks penagihan.
//   · Amandemen PO: qty baris yang sudah diterima terkunci total → amandemen "qty = qty diterima" (G3 V3-PO-02, menutup
//     sisa yang tidak dikirim) tidak bisa dibuat dari layar. Kini ada [Tutup sisa].
//   · Rincian roll penerimaan: baris pertama terisi otomatis (500 yard = 75,44 kg); dipecah jadi roll 100 yard tetapi
//     beratnya tetap 75,44 → "Aktual lebih besar 80%" dan penerimaan diblokir. Kini berat yang masih sepadan ikut.
//   · Tagihan selisih harga yang menunggu persetujuan: Manajer pembuat melihat [Setujui] padahal kontrol dua orang
//     menolaknya (403). Kini petunjuk "Tagihan Anda — disetujui orang lain".
//   · Daftar tagihan: draf lebih tagih yang DIBATALKAN tampil dengan "sisa" merah sebesar totalnya (Rp 10.878.000) —
//     hanya tagihan terposting/lunas yang menjadi hutang.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import VendorBillCreateModal from "../purchasing/VendorBillCreateModal";
import POAmendModal from "../admin/po/POAmendModal";
import GRCatchWeightModal from "../wms/inbound/GRCatchWeightModal";
import VendorBillsView from "../purchasing/VendorBillsView";
import { EntityScopeProvider } from "../../context/EntityScopeContext";

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
jest.mock("../../components/KNSelect", () => {
  const M = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange?.(e.target.value)}>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>);
  return { __esModule: true, default: M, KNSelect: M };
});
jest.mock("../../hooks/useCanDecide", () => ({
  __esModule: true,
  useCanDecideMap: (rows) => Object.fromEntries((rows || []).map((b) => [b.id, { allowed: true }])),
  default: () => ({ allowed: true }),
}));
jest.mock("../../components/ExportMenu", () => () => null);
jest.mock("../purchasing/VendorBillDetailPanel", () => (p) => (
  <div data-testid="stub-vb-detail" data-can-approve={String(p.canApprove)}>{p.decideHint}</div>));
jest.mock("@/components/MoneyInput", () => (p) => (
  <input data-testid={p.testId} value={p.value ?? ""} disabled={p.disabled} onChange={(e) => p.onChange(Number(e.target.value))} />));
jest.mock("@/components/KNDatePicker", () => () => null);
jest.mock("../purchasing/GrnDocVariance", () => () => null);
jest.mock("../../components/SiteSelect", () => () => null);
jest.mock("../../hooks/useUomConversions", () => () => ({}));
jest.mock("../../hooks/useDomainEnums", () => () => ({ options: () => [{ value: "A", label: "A" }] }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 8) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
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
function setVal(el, v) {
  const proto = el.tagName === "SELECT" ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, "value").set.call(el, String(v));
  el.dispatchEvent(new Event(el.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
}
async function isi(id, v) { await act(async () => { setVal(q(id), v); }); await flush(); }

const CTX = {
  po_id: "po_s2", po_number: "KSC/PO-00077", entity_id: "ent_ksc", receipt_variances: [],
  tolerances: { qty_pct: 0, price_pct: 5, value_rp: 50000 },
  items: [{ po_line_id: "L1", line_no: 1, product_id: "p1", product_name: "Grey", sku: "G-1", ordered_qty: 1000,
    received_qty: 600, already_billed_qty: 0, billable_received: 600, billable_ordered: 1000, po_price: 14000 }],
};

beforeEach(() => {
  mockGet.mockImplementation((url) => Promise.resolve({
    data: url.endsWith("/billing-context") ? CTX
      : url.endsWith("/settings/effective") ? { purchasing: { bill_price_tolerance_percent: 5, bill_qty_tolerance_percent: 0 } } : {},
  }));
});
afterEach(() => { roots.forEach((r) => act(() => r.unmount())); roots = []; document.body.innerHTML = ""; });

async function bukaForm() {
  await mount(<VendorBillCreateModal open pos={[{ id: "po_s2", po_number: "KSC/PO-00077", supplier_name: "Latihan" }]}
    selectedEntity="ent_ksc" onClose={() => {}} onCreated={() => {}} />);
  await isi("vb-po-select", "po_s2");
  expect(q("vb-item-row-0")).not.toBeNull();
}

describe("S2 — form tagihan memakai ambang yang sama dengan server", () => {
  test("selisih harga 5,7% senilai Rp 40.000 (≤ Rp 50.000) = cocok bersih, seperti server", async () => {
    await bukaForm();
    await isi("vb-item-billed-0", 50);
    await isi("vb-item-price-0", 14800);   // (14.800 − 14.000) × 50 = 40.000; 5,7% > 5%
    expect(q("vb-overall-match").textContent).toMatch(/Cocok bersih/);
    expect(q("vb-submit-now").textContent).toMatch(/Kirim & Posting/);
    expect(q("vb-tolerance-note").textContent).toMatch(/selisih ≤ Rp\s?50\.000 diabaikan/);
  });

  test("selisih harga Rp 500.000 tetap perlu persetujuan", async () => {
    await bukaForm();
    await isi("vb-item-billed-0", 500);
    await isi("vb-item-price-0", 15000);
    expect(q("vb-overall-match").textContent).toMatch(/Ada selisih/);
    expect(q("vb-submit-now").textContent).toMatch(/minta persetujuan/);
  });

  test("lebih tagih 2 yard (Rp 28.000) = perlu persetujuan, bukan ditahan; lebih 100 yard = ditahan", async () => {
    await bukaForm();
    await isi("vb-item-billed-0", 602);
    expect(q("vb-overall-match").textContent).toMatch(/Ada selisih/);
    expect(q("vb-submit-now").disabled).toBe(false);
    await isi("vb-item-billed-0", 700);
    expect(q("vb-overall-match").textContent).toMatch(/Lebih tagih/);
    expect(q("vb-submit-now").disabled).toBe(true);
  });
});

describe("S2 — amandemen PO: tutup sisa baris yang sudah diterima", () => {
  const PO = {
    id: "po_s2", po_number: "KSC/PO-00078", version: 1, supplier_id: "s1", supplier_name: "Latihan",
    ship_to_site_id: "site1", items: [{ product_id: "p1", sku: "G-1", product_name: "Grey", quantity: 1000, unit: "yard",
      price: 14000, discount_percent: 0, received_qty: 600 }],
  };
  test("qty terkunci, [Tutup sisa] menjadikan qty = qty diterima dan terkirim ke server; [Urungkan] mengembalikan", async () => {
    const kirim = jest.fn();
    await mount(<POAmendModal po={PO} products={[]} suppliers={[]} onSubmit={kirim} onClose={() => {}} />);
    expect(q("po-amend-item-qty-0").disabled).toBe(true);
    expect(q("po-amend-item-close-0").textContent).toMatch(/Sisa 400 yard belum diterima/);
    await act(async () => { q("po-amend-item-close-rest-0").click(); });
    await flush();
    expect(q("po-amend-item-qty-0").value).toBe("600");
    expect(q("po-amend-item-close-0").textContent).toMatch(/1\.000 → 600/);
    await act(async () => { q("po-amend-item-close-undo-0").click(); });
    await flush();
    expect(q("po-amend-item-qty-0").value).toBe("1000");
    await act(async () => { q("po-amend-item-close-rest-0").click(); });
    const ta = q("po-amend-reason");
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set.call(ta, "Pemasok tidak sanggup mengirim sisa");
      ta.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await flush();
    await act(async () => { q("po-amend-submit").click(); });
    expect(kirim).toHaveBeenCalledTimes(1);
    expect(kirim.mock.calls[0][0].items[0]).toMatchObject({ product_id: "p1", quantity: 600, price: 14000 });
  });

  test("baris belum diterima tidak menampilkan Tutup sisa", async () => {
    await mount(<POAmendModal po={{ ...PO, items: [{ ...PO.items[0], received_qty: 0 }] }} products={[]} suppliers={[]}
      onSubmit={() => {}} onClose={() => {}} />);
    expect(q("po-amend-item-close-0")).toBeNull();
    expect(q("po-amend-item-qty-0").disabled).toBe(false);
  });
});

describe("S2 — rincian roll: memecah baris pertama ikut menghitung ulang beratnya", () => {
  function Wadah({ awal, task }) {
    const [rolls, setRolls] = React.useState(awal);
    return (<>
      <GRCatchWeightModal task={task} product={{ base_unit: "meter", kg_per_meter: 0.15 }} rolls={rolls} setRolls={setRolls}
        onSubmit={() => {}} onClose={() => {}} lotFields={{ supplier_lot: "L", lot_number: "", shade_ref: "", supplier_dn: "SJ" }}
        setLotFields={() => {}} lotSettings={{}} />
      <output data-testid="berat">{rolls.map((r) => r.weight).join("|")}</output>
    </>);
  }
  const task = { unit: "meter", received_qty: 500, sku: "G", product_name: "Grey", po_id: "po1" };

  test("panjang baris terisi otomatis diubah → berat sepadan ikut berubah", async () => {
    await mount(<Wadah task={task} awal={[{ length: 500, weight: 75, dye_lot: "D", grade: "A" }]} />);
    await isi("gr-roll-length-0", 100);
    expect(q("berat").textContent).toBe("15");
  });

  test("berat aktual (catch-weight) yang diketik tidak diubah, dan tidak mengubah panjang", async () => {
    await mount(<Wadah task={task} awal={[{ length: 100, weight: 15, dye_lot: "D", grade: "A" }]} />);
    await isi("gr-roll-weight-0", 16.2);
    expect(q("gr-roll-length-0").value).toBe("100");
    await isi("gr-roll-length-0", 90);
    expect(q("berat").textContent).toBe("16.2");
  });
});

describe("S2 — pembuat tagihan tidak ditawari menyetujui tagihannya sendiri", () => {
  const MGR = { id: "u_mgr", role: "manager", permissions: { vendor_bill: ["view", "create", "update", "approve"] } };
  const bill = (id, by) => ({ id, bill_number: id.toUpperCase(), status: "pending_approval", supplier_name: "CV A",
    entity_id: "ent_ksc", items: [], grand_total: 8325000, created_by_id: by, financials: { outstanding: 8325000 } });
  test("baris milik sendiri tanpa [Setujui]; milik orang lain tetap ada; rincian memberi petunjuk", async () => {
    mockGet.mockImplementation((url) => Promise.resolve({ data:
      url.endsWith("/vendor-bills") ? { items: [bill("vba", "u_mgr"), bill("vbb", "u_lain")], total: 2, has_more: false }
        : url.endsWith("/vendor-bills/vba") ? bill("vba", "u_mgr")
          : url.endsWith("/purchase-orders") ? [] : {} }));
    await mount(<EntityScopeProvider selectedEntity="ent_ksc" entities={[{ id: "ent_ksc", short_name: "Sukacita" }]}>
      <VendorBillsView currentUser={MGR} selectedEntity="ent_ksc" /></EntityScopeProvider>);
    expect(q("vb-row-vba")).not.toBeNull();
    expect(q("vb-quick-approve-vba")).toBeNull();
    expect(q("vb-quick-approve-vbb")).not.toBeNull();
    await act(async () => { q("vb-open-vba").click(); });
    await flush();
    expect(q("stub-vb-detail").getAttribute("data-can-approve")).toBe("false");
    expect(q("stub-vb-detail").textContent).toMatch(/Tagihan Anda — disetujui orang lain/);
  });

  test("draf lebih tagih yang dibatalkan tidak tampil sebagai sisa hutang; tagihan terposting tetap", async () => {
    mockGet.mockImplementation((url) => Promise.resolve({ data:
      url.endsWith("/vendor-bills") ? { items: [{ ...bill("vbc", "u_lain"), status: "cancelled", grand_total: 10878000,
        financials: { outstanding: 10878000 } }, { ...bill("vbp", "u_lain"), status: "posted" }], total: 2, has_more: false }
        : url.endsWith("/purchase-orders") ? [] : {} }));
    await mount(<EntityScopeProvider selectedEntity="ent_ksc" entities={[{ id: "ent_ksc", short_name: "Sukacita" }]}>
      <VendorBillsView currentUser={MGR} selectedEntity="ent_ksc" /></EntityScopeProvider>);
    expect(q("vb-sisa-vbc").textContent.trim()).toBe("—");
    expect(q("vb-sisa-vbp").textContent).toMatch(/8\.325\.000/);
  });
});
