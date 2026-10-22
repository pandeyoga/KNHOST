// Trial 22 Okt 2026 — perbaikan temuan (docs/uat/2026-10-21/CATATAN_TEMUAN_TRIAL_22OKT.md).
// D2: hitung fisik GRN — panjang boleh diketik dalam satuan SJ/PO atau satuan dasar produk; satuan yang dipilih
//     ikut dikirim (server mengonversi ke satuan dasar). Dulu label "Panjang (meter)" tetapi angka disimpan sebagai yard.
// A2/F1: tab Cutting — pesanan catalogue tampil SATU paket (bukan 9 tugas), "Potong semua" = satu panggilan batch.
// E5: rencana pemenuhan — pilih roll (qty = jumlah panjang roll terpilih), bukan ketik bebas.
// E7: tabel meja — cari + filter status + urutan.
// F5: Lembar Inspect menyerupai kertas "DATA HASIL INSPECT" (sel KODE+POIN per 15 yard, STDRT, yard per grade);
//     grade roll diisi petugas QC (keputusan pemilik — sistem tidak mengisi otomatis).
// B6: stok di katalog/checkout HP — stok PT penjual dipisah dari stok grup; kekurangan bersatuan (kg), bukan "unit".
// B3: Barang Masuk isi manual — pilih Target mengisi kode/deskripsi/satuan/PO yang kosong; saran target dari kode/nama.
// E8/E10: alur pesanan baru — ringkasan "Sebelum masuk gudang" (normal → diminta + dua total + batas booking),
//     harga ditolak → tiga pilihan sales, dialog Admin Sales "Periksa & lepas ke gudang" (+ tahan dulu).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import GrnCountPanel from "../wms/grn/GrnCountPanel";
import GrnReviewPanel from "../wms/grn/GrnReviewPanel";
import OrderReleaseSummary from "../orders/OrderReleaseSummary";
import SoApprovalsPanel from "../orders/SoApprovalsPanel";
import VerifyOrderDialog from "../sales_admin/VerifyOrderDialog";
import { releaseMessage } from "../sales_admin/workDeskApi";
import CuttingOpsView from "../wms/CuttingOpsView";
import DeskQueueCard from "../sales_admin/DeskQueueCard";
import FulfillmentLineCard from "../sales_admin/FulfillmentLineCard";
import InspectSheetGrid, { parseCell, stdrt } from "../inspections/InspectSheetGrid";
import { MobileProductCard } from "../pos/mobile/MobileProductCard";
import { CheckoutItemCard } from "../pos/CheckoutItemCard";
import { groupByTemplate } from "../../utils/variants";
import { fillFromTarget, suggestTargets, targetLabel } from "../wms/grn/grnTargets";

const posted = [];
jest.mock("../wms/grn/grnApi", () => ({
  grnApi: {
    rolls: () => Promise.resolve([{ id: "r1", roll_no: "RL-1", grn_line_no: 1, length_initial: 109.36, unit: "yard",
      actual_task_qty: 100, lot: "L1", grade: "A", status: "receiving", scan_source: "count" }]),
    post: (...a) => { posted.push(a); return Promise.resolve({ grn: null }); },
    del: () => Promise.resolve({}),
    targets: () => Promise.resolve(global.__grnTargets || []),
    fileBlob: () => Promise.reject(new Error("tanpa foto")),
  },
  errText: () => "gagal",
}));   // bukan jest.fn: resetMocks CRA
jest.mock("../../hooks/useDomainEnums", () => () => ({ options: () => [{ value: "A", label: "A" }] }));
const apiCalls = [];
jest.mock("../../services/apiClient", () => ({
  __esModule: true, API: "/api",
  default: {
    defaults: { headers: { common: {} } },
    get: (url) => {
      apiCalls.push(["get", url]);
      if (url.endsWith("/outbound/tasks")) return Promise.resolve({ data: global.__outboundTasks || [] });
      if (url.endsWith("/warehouses")) return Promise.resolve({ data: [{ id: "wh_j", name: "Jakarta · Sukacita" }] });
      if (url.endsWith("/master/grades")) return Promise.resolve({ data: [{ code: "A", name: "A" }, { code: "B", name: "B" }] });
      if (url.includes("pending-cuts")) return Promise.resolve({ data: { items: [] } });
      return Promise.resolve({ data: { verifiable: true, ready: true, checks: [], blocking_gaps: [], warnings: [],
        order_preview: { customer_name: "Toko Uji", items: [], totals: {} } } });
    },
    post: (url, body) => {
      apiCalls.push(["post", url, body]);
      if (url.endsWith("/cut-samples")) return Promise.resolve({ data: { cut: [], failed: [] } });
      return Promise.resolve({ data: { order: { number: "SO-UJI", status: "waiting_approval" }, released: false,
        release_state: { waiting: "acc", hold: false } } });
    },
  },
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView || (() => {});
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const tick = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });

async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await tick();
  return root;
}

const grn = (target) => ({ id: "grn1", status: "counting", version: 1, lines: [{ line_no: 1, decision: "accept",
  target: { type: "po_task", po_number: "PO-1", sku: "LRK", product_name: "Lurik", ...target }, counted: { rolls: 1, qty: 100 } }] });

test("D2: hitung GRN — pilihan satuan SJ/PO vs stok, satuan terpilih dikirim, roll tampil dua satuan", async () => {
  posted.length = 0;
  const root = await mount(<GrnCountPanel grn={grn({ unit: "meter", base_unit: "yard" })} onChange={() => {}} canCount />);
  expect(q("grn-count-unit-1")).not.toBeNull();
  expect(q("grn-count-length-1").placeholder).toBe("Panjang (meter)");
  expect(q("grn-count-roll-r1").textContent).toMatch(/109\.36 yard \(= 100 meter\)/);
  const input = q("grn-count-length-1");
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, "100");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => { q("grn-count-add-1").click(); });
  await tick();
  expect(posted[0][1]).toBe("lines/1/rolls");
  expect(posted[0][2]).toMatchObject({ length: 100, length_unit: "meter" });
  act(() => root.unmount());
});

test("D2: satuan SJ = satuan stok → tanpa pemilih satuan", async () => {
  const root = await mount(<GrnCountPanel grn={grn({ unit: "yard", base_unit: "yard" })} onChange={() => {}} canCount />);
  expect(q("grn-count-unit-1")).toBeNull();
  expect(q("grn-count-length-1").placeholder).toBe("Panjang (yard)");
  act(() => root.unmount());
});


const spOrder = (status) => ({
  id: "so1", number: "SO-UJI", status: "waiting_approval", order_type: "regular", customer_id: "c1", customer_name: "Toko Uji",
  total_amount: 60000000, grand_total: 66600000, reservation_expires_at: "2026-10-25T07:00:00+00:00",
  items: [{ product_id: "p1", product_name: "Batik Mega", quantity: 500, unit: "yard", price: 120000 }],
  release: { requested: true, by: "Rina" },
  pending_approvals: [{ id: "a1", type: "special_price", status, product_id: "p1", product_name: "Batik Mega",
    normal_price: 120000, requested_price: 105000, required_role: "manager", decision_notes: status === "rejected" ? "minimal 112.000" : "" }],
});

test("E10: ringkasan — harga normal → diminta, dua total berlabel, batas booking, label menunggu ACC", async () => {
  const root = await mount(<OrderReleaseSummary order={spOrder("pending")} />);
  expect(q("order-release-label").textContent).toBe("Menunggu ACC harga");
  expect(q("order-release-prices").textContent).toMatch(/Normal Rp\s?120\.000 → diminta Rp\s?105\.000/);
  expect(q("order-release-total-normal").textContent).toMatch(/66\.600\.000/);
  // 500 yd × (120.000 − 105.000) = 7,5 jt (sebelum PPN) × rasio grand/total 1,11 = 8.325.000
  expect(q("order-release-total-requested").textContent).toMatch(/58\.275\.000/);
  expect(q("order-release-booking").textContent).toMatch(/Booking stok berakhir/);
  expect(q("order-release-step-review").textContent).toMatch(/Diperiksa Rina/);
  act(() => root.unmount());
});

test("E10: harga ditolak → label pilih langkah + tiga tombol; Lanjut harga normal memanggil API", async () => {
  apiCalls.length = 0;
  const user = { role: "sales", permissions: { order: ["view", "update", "cancel"] } };
  const root = await mount(<SoApprovalsPanel order={spOrder("rejected")} user={user} onRefresh={() => {}} />);
  expect(q("order-release-label").textContent).toBe("Harga ditolak · pilih langkah");
  expect(q("so-appr-ask-again-a1")).not.toBeNull();
  expect(q("so-appr-cancel-order-a1")).not.toBeNull();
  await act(async () => { q("so-appr-keep-normal-a1").click(); });
  await tick();
  expect(apiCalls.some(([m, url]) => m === "post" && url === "/api/sales-orders/so1/approvals/a1/continue-normal-price")).toBe(true);
  act(() => root.unmount());
});

test("E8: dialog Admin Sales — Periksa & lepas, opsi Tahan dulu ikut terkirim", async () => {
  apiCalls.length = 0;
  let msg = "";
  const root = await mount(<VerifyOrderDialog orderId="so1" orderNumber="SO-UJI" customerName="Toko Uji"
    onClose={() => {}} onVerified={(m) => { msg = m; }} />);
  expect(q("verify-submit").textContent).toBe("Periksa & lepas ke gudang");
  await act(async () => { q("verify-hold").querySelector("input").click(); });
  expect(q("verify-submit").textContent).toBe("Periksa & tahan");
  await act(async () => { q("verify-submit").click(); });
  await tick();
  const call = apiCalls.find(([m, url]) => m === "post" && url === "/api/sales-orders/so1/review-release");
  expect(call[2]).toEqual({ note: "", hold: true });
  expect(msg).toMatch(/menunggu ACC Manajer; dilepas ke gudang otomatis sesudah ACC/);
  act(() => root.unmount());
});

test("E8: pesan sesudah periksa sesuai keadaan", () => {
  expect(releaseMessage({ released: true, order: { number: "SO-1", status: "confirmed" } })).toMatch(/dilepas ke gudang/);
  expect(releaseMessage({ order: { number: "SO-1", status: "approved" }, release_state: { hold: true } })).toMatch(/DITAHAN/);
  expect(releaseMessage({ order: { number: "SO-1", status: "waiting_approval" }, release_state: { waiting: "ditolak" } })).toMatch(/DITOLAK/);
});


test("A2/F1: tab Cutting — 9 baris catalogue jadi satu paket; Potong semua memanggil API batch", async () => {
  apiCalls.length = 0;
  global.__outboundTasks = Array.from({ length: 9 }, (_, i) => ({
    id: `t${i}`, task_subtype: "sample_cut", status: "created", picked_qty: 0, order_id: "so5", order_number: "KSC/SOS-00005",
    customer_name: "Toko Kain Sejahtera", warehouse_id: "wh_j", warehouse_name: "Jakarta · Sukacita",
    product_name: `CLOVERTEA ${i}`, quantity: 1, unit: "yard", suggested_roll_no: `RL-${i}`, suggested_roll_id: `r${i}`,
  })).concat([{ id: "so-pick", task_subtype: undefined, status: "created", order_id: "x", order_number: "KSC/SO-1" }]);
  const root = await mount(<CuttingOpsView />);
  await tick();
  const pkgs = [...document.body.querySelectorAll('[data-testid^="cutting-pkg-"]')].filter((e) => !e.dataset.testid.startsWith("cutting-pkg-cut-all"));
  expect(pkgs.map((e) => e.dataset.testid)).toEqual(["cutting-pkg-so5"]);   // satu paket; tugas SO biasa tidak ikut
  expect(q("cutting-pkg-so5").textContent).toMatch(/9 baris · dipotong 0\/9/);
  expect(q("cutting-pkg-cut-all-so5").textContent).toMatch(/Potong semua \(9\)/);
  await act(async () => { q("cutting-pkg-cut-all-so5").click(); });
  await tick();
  expect(apiCalls.filter(([m, url]) => m === "post" && url === "/api/outbound/so/so5/cut-samples")).toHaveLength(1);
  act(() => root.unmount());
});


test("F5: sel lembar inspect — KODE+POIN, beberapa per sel; isian salah ditandai; STDRT = poin×3600÷(yd×inci)", () => {
  expect(parseCell("CG2 ko1, BL4")).toEqual({ defects: [{ code: "CG", point_value: 2 }, { code: "KO", point_value: 1 },
    { code: "BL", point_value: 4 }], bad: [] });
  expect(parseCell("CG5 x").bad).toEqual(["CG5", "x"]);
  expect(stdrt(6, 100, 58)).toBe(3.72);
  expect(stdrt(6, 0, 58)).toBeNull();
});

test("F5: Lembar Inspect menyimpan baris via bagian QC (interval, lebar inci→cm, yard per grade, tolak)", async () => {
  apiCalls.length = 0;
  const doc = { id: "ins1", number: "INS-1", status: "in_progress", spk_date: "2026-10-22", supplier_name: "PT Uji",
    lines: [{ id: "l1", roll_id: "r1", roll_no: "RL-1", article: "Batik", quantity: 100, unit: "yard", defects: [] }] };
  const root = await mount(<InspectSheetGrid doc={doc} meta={{ defect_codes: [{ code: "CG", label: "" }] }} editable onSaved={() => {}} />);
  const typeIn = async (id, v) => { const el = q(id); await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, v); el.dispatchEvent(new Event("input", { bubbles: true })); }); };
  await typeIn("ins-sheet-width-l1", "58");
  await typeIn("ins-sheet-cell-l1-0", "CG2");
  await typeIn("ins-sheet-cell-l1-2", "KO4");
  expect(q("ins-sheet-points-l1").textContent).toBe("6");
  expect(q("ins-sheet-stdrt-l1").textContent).toBe("3.72");
  await act(async () => { q("ins-sheet-reject-l1").click(); });
  // F5 (keputusan pemilik) — grade roll diisi petugas; tanpa grade simpan ditolak di layar.
  await act(async () => { q("ins-sheet-save").click(); });
  expect(q("ins-sheet-error").textContent).toMatch(/Pilih grade roll: RL-1/);
  expect(apiCalls.some(([m, url]) => m === "post" && url.includes("/lines/l1/inspect"))).toBe(false);
  expect(q("ins-sheet-grade-rule").textContent).toMatch(/diisi petugas QC/);
  const sel = q("ins-sheet-grade-l1");
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(sel, "B"); sel.dispatchEvent(new Event("change", { bubbles: true })); });
  await act(async () => { q("ins-sheet-save").click(); });
  await tick();
  const call = apiCalls.find(([m, url]) => m === "post" && url === "/api/inspections/ins1/lines/l1/inspect");
  expect(call[2]).toMatchObject({ part: "qc", inspect_length_yard: 100, width_actual: 147.3, decision: "tolak", grade: "B",
    defects: [{ code: "CG", point_value: 2, interval: 0, count: 1, note: "" }, { code: "KO", point_value: 4, interval: 2, count: 1, note: "" }] });
  act(() => root.unmount());
});


test("E7: antrean meja — chip filter status & urutan terbaru", async () => {
  const rows = [
    { ref_type: "sales_order", ref_id: "a", number: "SO-A", title: "Toko A", badge: "reserved", value: 10, age_days: 5 },
    { ref_type: "sales_order", ref_id: "b", number: "SO-B", title: "Toko B", badge: "waiting_stock", value: 30, age_days: 1 },
    { ref_type: "sales_order", ref_id: "c", number: "SO-C", title: "Toko C", badge: "reserved", value: 20, age_days: 3 },
  ];
  const root = await mount(<DeskQueueCard queue={{ id: "perlu_verifikasi", label: "Uji", count: 3, rows }} testPrefix="t" defaultOpen />);
  const nums = () => [...document.body.querySelectorAll('[data-testid^="t-number-"]')].map((e) => e.textContent);
  expect(nums()).toEqual(["SO-A", "SO-B", "SO-C"]);
  await act(async () => { q("t-q-perlu_verifikasi-status-waiting_stock").click(); });
  expect(nums()).toEqual(["SO-B"]);
  await act(async () => { q("t-q-perlu_verifikasi-status-all").click(); });
  const sel = q("t-q-perlu_verifikasi-sort");
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(sel, "newest"); sel.dispatchEvent(new Event("change", { bubbles: true })); });
  expect(nums()).toEqual(["SO-B", "SO-C", "SO-A"]);
  act(() => root.unmount());
});


test("E5: pilih roll stok sendiri → qty otomatis = panjang roll terpilih (dibatasi kekurangan)", async () => {
  let value = { stock: 0, reorder: 0, wait: 0, ic: {}, stockRolls: [], icRolls: {} };
  const line = { product_id: "p1", product_name: "Batik", sku: "BTK", unit: "yard", backorder_qty: 60, planned_qty: 0,
    own_available: 100, own_by_warehouse: [{ warehouse_id: "w", warehouse_name: "Jakarta", available_qty: 100 }],
    own_rolls: [{ id: "r1", roll_no: "RL-1", length_remaining: 40, warehouse_name: "Jakarta" },
                { id: "r2", roll_no: "RL-2", length_remaining: 40, warehouse_name: "Jakarta" }],
    other_entities: [], incoming_total: 0, incoming_claimed_by_older: 0 };
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host);
  const render = () => root.render(<FulfillmentLineCard line={line} value={value} onChange={(v) => { value = v; }} />);
  await act(async () => { render(); });
  await act(async () => { q("fulfill-stock-pick-p1-toggle").click(); });
  await act(async () => { q("fulfill-stock-pick-p1-roll-r2").click(); });
  expect(value.stockRolls).toEqual(["r2"]);
  expect(value.stock).toBe(40);
  await act(async () => { render(); });
  await act(async () => { q("fulfill-stock-pick-p1-roll-r1").click(); });
  expect(value.stockRolls).toEqual(["r2", "r1"]);
  expect(value.stock).toBe(60);                                          // dibatasi kekurangan 60
  act(() => root.unmount());
});


test("B6: kartu katalog HP — stok PT penjual (kosong) dipisah dari stok grup", async () => {
  const [group] = groupByTemplate([{ id: "p1", sku: "ALC-14", name: "ALICE KNIT", template_id: "t1", base_unit: "kg", price: 10,
    available_qty: 9285.19, roll_count: 465, entity_available_qty: 0, entity_roll_count: 0, stock_entity_name: "Sukacita" }]);
  const root = await mount(<MobileProductCard group={group} onOpen={() => {}} />);
  expect(q("mobile-product-own-p1").textContent).toBe("Sukacita: kosong");
  expect(q("mobile-product-available-p1").parentElement.textContent).toMatch(/^Grup: 465 roll \/ 9\.285,19 kg/);
  act(() => root.unmount());
});

test("B6: checkout — baris stok memakai stok PT penjual + kurangnya; tanpa pratinjau = roll grup", async () => {
  const item = { product: { id: "p1", sku: "ALC-14", name: "ALICE KNIT", base_unit: "kg", price: 10, roll_count: 465 }, quantity: 100 };
  const line = { product_id: "p1", unit: "kg", requested_qty: 100, own_available: 0, breakdown: { backorder: 0, inter_company: 100 } };
  const root = await mount(<CheckoutItemCard item={item} allocationLine={line} stockEntityName="Sukacita"
    onRemove={() => {}} onUpdateQty={() => {}} onUpdateDiscount={() => {}} />);
  expect(q("cart-item-rolls-p1").textContent).toMatch(/^Stok Sukacita: 0 kg · kurang 100 kg \(diatur Admin Sales\)/);
  await act(async () => { root.render(<CheckoutItemCard item={item} onRemove={() => {}} onUpdateQty={() => {}} onUpdateDiscount={() => {}} />); });
  expect(q("cart-item-rolls-p1").textContent).toMatch(/^465 roll di grup/);
  act(() => root.unmount());
});

test("B3: target GRN — isian otomatis hanya kolom kosong, saran dari kode/nama versi supplier, label bisa dicari", () => {
  const t = { type: "po_task", task_id: "t1", po_number: "KSC/PO-00002", product_name: "Lurik Klasik Solo", sku: "LRK-01",
    supplier_sku: "SUP-77", supplier_item_name: "Lurik Solo Motif A", unit: "meter" };
  const other = { ...t, task_id: "t2", po_number: "KSC/PO-00003", product_name: "Batik Mega", sku: "BTK", supplier_sku: "", supplier_item_name: "" };
  expect(fillFromTarget({ item_code: "", description: "", unit: "", po_ref: "" }, t))
    .toEqual({ item_code: "SUP-77", description: "Lurik Solo Motif A", unit: "meter", po_ref: "KSC/PO-00002" });
  expect(fillFromTarget({ item_code: "X1", description: "tertulis di SJ", unit: "yd", po_ref: "" }, t))
    .toEqual({ item_code: "X1", description: "tertulis di SJ", unit: "yd", po_ref: "KSC/PO-00002" });   // ketikan SJ tidak ditimpa
  expect(suggestTargets([t, other], "sup-77", "").map((h) => [h.t.task_id, h.why])).toEqual([["t1", "kode cocok"]]);
  expect(suggestTargets([t, other], "", "lurik solo").map((h) => h.t.task_id)).toEqual(["t1"]);
  expect(suggestTargets([t, other], "", "ab")).toEqual([]);
  expect(targetLabel(t)).toBe("KSC/PO-00002 · Lurik Klasik Solo (meter) · supplier: SUP-77 Lurik Solo Motif A");
});

test("B3: form baris manual — ketik kode supplier → saran target → isian terisi dari target", async () => {
  global.__grnTargets = [{ type: "po_task", task_id: "t1", po_number: "KSC/PO-00002", product_name: "Lurik Klasik Solo",
    sku: "LRK-01", supplier_sku: "SUP-77", supplier_item_name: "Lurik Solo Motif A", unit: "meter" }];
  const root = await mount(<GrnReviewPanel grn={{ id: "g1", status: "review", version: 2, partner_type: "supplier", files: [], lines: [], dn: {} }}
    onChange={() => {}} canReview />);
  const code = q("grn-line-code");
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(code, "sup-77");
    code.dispatchEvent(new Event("input", { bubbles: true }));
  });
  expect(q("grn-line-target-hints").textContent).toMatch(/KSC\/PO-00002 · Lurik Klasik Solo .* kode cocok/);
  await act(async () => { q("grn-line-target-hint-po_task:t1").click(); });
  expect(q("grn-line-target-hints")).toBeNull();
  expect([q("grn-line-code").value, q("grn-line-desc").value, q("grn-line-unit").value, q("grn-line-po-ref").value])
    .toEqual(["sup-77", "Lurik Solo Motif A", "meter", "KSC/PO-00002"]);
  act(() => root.unmount());
  global.__grnTargets = [];
});
