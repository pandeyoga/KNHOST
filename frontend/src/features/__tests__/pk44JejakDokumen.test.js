// PK-44 (IA-04, IA-11, IA-13) — jejak dokumen membuka dokumennya (docs/blueprint/unit/PK-44.md).
//   U14 — `useFocusDoc`: jenis cocok → `buka` dipanggil SEKALI + `onClearFocus`; jenis lain → tidak dipanggil;
//         `buka` gagal → "Dokumen {nomor} tidak ditemukan di PT ini." (bukan layar kosong).
//   Pembaca fokus layar tujuan (contoh Penggajian): fokus `payroll_run` membuka rinciannya; 404 → pemberitahuan.
//   Satu panel relasi: `DocRefsPanel` berjudul "Dokumen Terkait" + "Lihat seluruh jejak", tombol "Buka" tampil bila
//         ada pembuka dokumen; simpul tanpa izin menulis alasannya (bukan tombol mati bertooltip); garis tahapan
//         tanpa daftar/tautan dokumen; detail pesanan & PO tidak lagi memasang linimasa proses terpisah.
//   Bilah kembali: `openDocument` mencatat layar asal; "← Kembali ke Jejak Dokumen" membuka jejak yang sama.
//   Kartu angka: `KpiCard` ber-`onClick` menampilkan tombol tautan baku.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import fs from "fs";
import path from "path";
import useFocusDoc from "../../hooks/useFocusDoc";
import FocusNotice from "../../components/FocusNotice";
import BackToOriginBar from "../../components/BackToOriginBar";
import DocRefsPanel from "../documents/trace/DocRefsPanel";
import useAppNavigation, { originLabel } from "../../hooks/useAppNavigation";
import { KpiCard } from "../finance/financeShared";
import PayrollRunsView from "../hr/PayrollRunsView";
import CashManagementView from "../purchasing/CashManagementView";
import ARReceiptsHistory from "../crm/ARReceiptsHistory";
import { EntityScopeProvider } from "../../context/EntityScopeContext";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }),
    patch: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    delete: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => <select data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />;
  return { __esModule: true, default: S, KNSelect: S };
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const qAll = (prefix) => [...document.body.querySelectorAll(`[data-testid^="${prefix}"]`)];
async function flush(n = 8) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(el); });
  await flush();
  return { host, root };
}
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.endsWith(k));
    const v = hit ? map[hit] : [];
    if (v && v.__status) {
      return Promise.reject(Object.assign(new Error("ditolak"), { response: { status: v.__status, data: { detail: "x" } } }));
    }
    return Promise.resolve({ data: v });
  });
}
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockReset();
  document.body.innerHTML = "";
});

function Penerima({ focusDoc, jenis, buka, onClearFocus }) {
  const fokus = useFocusDoc(focusDoc, jenis, buka, onClearFocus);
  return <FocusNotice {...fokus} testId="uji-notice" />;
}

// ── U14 ────────────────────────────────────────────────────────────────────────────────────────────────────────────
test("PK44 U14 — useFocusDoc: jenis cocok → buka sekali + onClearFocus; jenis lain → tidak dipanggil", async () => {
  const buka = jest.fn(() => Promise.resolve());
  const clear = jest.fn();
  const fd = { focus_type: "vendor_bill", focus_id: "vb1", number: "VB-1", nonce: 1 };
  const { root } = await mount(<Penerima focusDoc={fd} jenis="vendor_bill" buka={buka} onClearFocus={clear} />);
  expect(buka).toHaveBeenCalledTimes(1);
  expect(buka.mock.calls[0][0]).toBe("vb1");
  expect(clear).toHaveBeenCalledTimes(1);
  // Render ulang dengan fokus yang sama tidak membuka dua kali.
  await act(async () => { root.render(<Penerima focusDoc={fd} jenis="vendor_bill" buka={buka} onClearFocus={clear} />); });
  expect(buka).toHaveBeenCalledTimes(1);
  const buka2 = jest.fn();
  const clear2 = jest.fn();
  await mount(<Penerima focusDoc={{ focus_type: "sales_order", focus_id: "so1" }} jenis={["vendor_bill", "contra_bon"]}
    buka={buka2} onClearFocus={clear2} />);
  expect(buka2).not.toHaveBeenCalled();
  expect(clear2).not.toHaveBeenCalled();
});

test("PK44 U14b — buka gagal → 'Dokumen {nomor} tidak ditemukan di PT ini.'", async () => {
  const buka = jest.fn(() => Promise.reject(new Error("404")));
  await mount(<Penerima focusDoc={{ focus_type: "rfq", focus_id: "r1", number: "KSC/RFQ-9", nonce: 2 }} jenis="rfq"
    buka={buka} onClearFocus={() => {}} />);
  expect(q("uji-notice").textContent).toContain("Dokumen KSC/RFQ-9 tidak ditemukan di PT ini.");
});

test("PK44 — Penggajian membaca fokus payroll_run: rincian terbuka; 404 → pemberitahuan", async () => {
  routeGet({
    "/hr/payroll/runs": [], "/entities": [],
    "/hr/payroll/runs/run1": { id: "run1", number: "KSC/PAY-00001", period: "2026-10", status: "paid", totals: {}, slips: [] },
  });
  const clear = jest.fn();
  await mount(<PayrollRunsView currentUser={{ permissions: { hr: ["view"] } }} selectedEntity="ent_ksc"
    focusDoc={{ focus_type: "payroll_run", focus_id: "run1", number: "KSC/PAY-00001", nonce: 3 }} onClearFocus={clear} />);
  expect(mockGet.mock.calls.map((c) => c[0])).toContain("/api/hr/payroll/runs/run1");
  expect(q("payroll-run-detail").textContent).toContain("KSC/PAY-00001");
  expect(clear).toHaveBeenCalled();
  document.body.innerHTML = "";
  routeGet({ "/hr/payroll/runs": [], "/entities": [], "/hr/payroll/runs/hilang": { __status: 404 } });
  await mount(<PayrollRunsView currentUser={{ permissions: { hr: ["view"] } }} selectedEntity="ent_ksc"
    focusDoc={{ focus_type: "payroll_run", focus_id: "hilang", number: "KSC/PAY-00099", nonce: 4 }} onClearFocus={() => {}} />);
  expect(q("payroll-focus-notice").textContent).toContain("Dokumen KSC/PAY-00099 tidak ditemukan di PT ini.");
  expect(q("payroll-run-detail")).toBeNull();
});

// Penggabungan dengan PK-42 — daftar berhalaman di server: fokus dicari lewat parameter cari server (`q` = nomor),
// bukan dengan memuat semua baris; ketemu → kotak cari terisi + baris disorot; tidak ada → pemberitahuan.
test("PK44 — Transaksi Kas (berhalaman server): fokus dicari lewat q nomor dan barisnya disorot", async () => {
  const t = { id: "cash1", number: "KSC/CASH-00007", txn_date: "2026-11-01", cash_type: "kas_besar", direction: "in",
    amount: 1000, entity_id: "ent_ksc", status: "posted" };
  const halaman = { items: [t], total: 1, page: 1, page_size: 50, has_more: false };
  routeGet({ "/cash-transactions": halaman, "/cash-transactions/summary": { kas_kecil: {}, kas_besar: {}, counts: {} }, "/entities": [] });
  const ents = [{ id: "ent_ksc", legal_name: "PT Kain Suka Cita", short_name: "Sukacita" }];
  await mount(<EntityScopeProvider selectedEntity="ent_ksc" entities={ents}>
    <CashManagementView currentUser={{ permissions: { cash: ["view"] } }} selectedEntity="ent_ksc"
      focusDoc={{ focus_type: "cash_transaction", focus_id: "cash1", number: "KSC/CASH-00007", nonce: 5 }} onClearFocus={() => {}} />
  </EntityScopeProvider>);
  const cari = mockGet.mock.calls.find((c) => c[0] === "/api/cash-transactions" && c[1]?.params?.q === "KSC/CASH-00007");
  expect(cari).toBeTruthy();
  expect(q("cash-txn-search").value).toBe("KSC/CASH-00007");
  expect(q("cash-row-cash1").className).toContain("row-focus");
  document.body.innerHTML = "";
  routeGet({ "/cash-transactions": { items: [], total: 0, page: 1, page_size: 50, has_more: false },
    "/cash-transactions/summary": { kas_kecil: {}, kas_besar: {}, counts: {} }, "/entities": [] });
  await mount(<EntityScopeProvider selectedEntity="ent_ksc" entities={ents}>
    <CashManagementView currentUser={{ permissions: { cash: ["view"] } }} selectedEntity="ent_ksc"
      focusDoc={{ focus_type: "cash_transaction", focus_id: "hilang", number: "KSC/CASH-00099", nonce: 6 }} onClearFocus={() => {}} />
  </EntityScopeProvider>);
  expect(q("cash-focus-notice").textContent).toContain("Dokumen KSC/CASH-00099 tidak ditemukan di PT ini.");
});

test("PK44 — riwayat kwitansi (berhalaman server): fokus mengisi cari server dengan nomor + menyorot baris", async () => {
  const rc = { id: "rc1", number: "KSC/RC-00042", receipt_date: "2026-11-02", customer_name: "Pelanggan", method: "transfer",
    amount: 5000, status: "posted", allocations: [] };
  routeGet({ "/ar-receipts": { items: [rc], total: 1, page: 1, page_size: 25, has_more: false } });
  await mount(<ARReceiptsHistory refreshKey={0} selectedEntity="ent_ksc" currentUser={{ permissions: {} }}
    focus={{ id: "rc1", number: "KSC/RC-00042", nonce: 7 }} />);
  await act(async () => { await new Promise((r) => setTimeout(r, 450)); });
  await flush();
  expect(q("ar-history-search").value).toBe("KSC/RC-00042");
  expect(mockGet.mock.calls.some((c) => c[0] === "/api/ar-receipts" && c[1]?.params?.q === "KSC/RC-00042")).toBe(true);
  expect(q("ar-history-row-rc1").className).toContain("row-focus");
});

// ── Satu panel relasi (IA-13) ────────────────────────────────────────────────────────────────────────────────────────
const REFS = {
  doc_type: "vendor_bill", doc_id: "vb1", number: "VB-1",
  refs: [
    { rel: "parent", rel_label: "Berasal dari", doc_type: "purchase_order", doc_id: "po1", doc_number: "PO-1",
      label: "Pesanan Pembelian (PO)", alive: true, status: "approved",
      link: { view: "purchasing", tab: "", focus_type: "purchase_order", focus_id: "po1", number: "PO-1" } },
    { rel: "settled_by", rel_label: "Dilunasi oleh", doc_type: "contra_bon", doc_id: "cb1", doc_number: "CB-1",
      label: "Kontrabon (Tukar Faktur)", alive: true, amount: null, amount_hidden: true, can_open: false,
      link: { view: "contra-bons", tab: "", focus_type: "contra_bon", focus_id: "cb1", number: "CB-1" } },
  ],
};

test("PK44 — DocRefsPanel: 'Dokumen Terkait', 'Lihat seluruh jejak', tombol Buka, alasan tanpa akses tertulis", async () => {
  routeGet({ "/documents/refs/vendor_bill/vb1": REFS });
  const open = jest.fn();
  await mount(<DocRefsPanel docType="vendor_bill" docId="vb1" onOpenDocument={open} />);
  const panel = q("doc-refs-panel");
  expect(panel.textContent).toContain("Dokumen Terkait");
  expect(q("docrefs-open-trace").textContent).toContain("Lihat seluruh jejak");
  const buka = q("docrefs-open-po1");
  expect(buka.textContent).toContain("Buka");
  await act(async () => { buka.click(); });
  expect(open).toHaveBeenCalledWith(REFS.refs[0].link);
  // PK-17 — tanpa izin modul: tidak ada tombol mati, alasannya ditulis di samping.
  expect(q("docrefs-open-cb1")).toBeNull();
  expect(q("docrefs-noaccess-cb1").textContent).toContain("Tanpa akses lihat");
});

test("PK44 — DocRefsPanel withStages: garis tahapan di kepala panel, tanpa daftar/tautan dokumen", async () => {
  routeGet({
    "/documents/refs/sales_order/so1": { doc_type: "sales_order", doc_id: "so1", number: "SO-1", refs: [] },
    "/documents/relations/sales_order/so1": { stages: [
      { key: "order", label: "Pesanan Penjualan", docs: [{ type: "sales_order", id: "so1", link: { view: "orders" } }] },
      { key: "shipment", label: "Pengiriman (Surat Jalan)", docs: [], empty_hint: "Belum ada pengiriman." },
      { key: "return", label: "Retur Jual", docs: [] },
    ] },
  });
  await mount(<DocRefsPanel docType="sales_order" docId="so1" withStages />);
  expect(q("process-timeline")).not.toBeNull();
  expect(q("process-stage-count-order").textContent).toContain("1");
  expect(q("process-stage-count-shipment").textContent).toContain("belum");
  expect(qAll("doc-node-")).toHaveLength(0);   // dulu: simpul dokumen bertaut di panel kedua
  expect(q("process-timeline").querySelectorAll("svg").length).toBeGreaterThanOrEqual(3);   // ikon tiap tahap
});

test("PK44 — detail pesanan & PO: satu panel relasi (tanpa linimasa proses terpisah), cetak berjudul 'Cetak Dokumen'", () => {
  const src = (rel) => fs.readFileSync(path.join(__dirname, "..", rel), "utf8");
  for (const f of ["orders/OrderDetailPanel.jsx", "admin/po/PODetailPanel.jsx"]) {
    const s = src(f);
    expect(s).not.toMatch(/<ProcessTimeline/);
    expect((s.match(/<DocRefsPanel/g) || []).length).toBe(1);
    expect(s).toMatch(/<DocRefsPanel[^>]*withStages/);
    expect(s).toMatch(/title="Cetak Dokumen/);
  }
  for (const f of ["purchasing/VendorBillDetailPanel.jsx", "purchasing/contrabon/ContraBonDetailPanel.jsx",
    "wms/inbound/InboundTaskPanel.jsx"]) {
    expect(src(f)).toMatch(/<DocRefsPanel[^>]*onOpenDocument=\{onOpenDocument\}/);
  }
  expect(src("purchasing/VendorBillDetailPanel.jsx")).toMatch(/label="Tagihan Pemasok"/);
});

// ── Bilah kembali (IA-11) ───────────────────────────────────────────────────────────────────────────────────────────
test("PK44 — BackToOriginBar: '← Kembali ke {asal}' memanggil onBack dengan asalnya", async () => {
  const onBack = jest.fn();
  const origin = { view: "doc-trace", label: "Jejak Dokumen" };
  await mount(<BackToOriginBar origin={origin} onBack={onBack} />);
  expect(q("back-to-origin").textContent).toContain("Kembali ke Jejak Dokumen");
  await act(async () => { q("back-to-origin").click(); });
  expect(onBack).toHaveBeenCalledWith(origin);
});

function NavHarness({ out }) {
  const nav = useAppNavigation({ role: "admin", setSidebarOpen: () => {} });
  out.current = nav;
  return null;
}

test("PK44 — openDocument mencatat layar asal; kembali dari dokumen membuka jejak yang sama", async () => {
  localStorage.setItem("kn_user", JSON.stringify({ role: "admin" }));
  expect(originLabel("doc-trace")).toBe("Jejak Dokumen");
  const out = { current: null };
  await mount(<NavHarness out={out} />);
  await act(async () => { out.current.handleNavSelect("doc-trace", "doc-trace"); });
  const link = { view: "vendor-bills", tab: "", focus_type: "vendor_bill", focus_id: "vb1", number: "VB-1",
    from_trace: { docType: "purchase_order", docId: "po1", number: "PO-1" } };
  await act(async () => { out.current.openDocument(link); });
  expect(out.current.activeView).toBe("vendor-bills");
  expect(out.current.focusDoc).toMatchObject({ focus_type: "vendor_bill", focus_id: "vb1",
    origin: { view: "doc-trace", label: "Jejak Dokumen" } });
  expect(out.current.backTo).toMatchObject({ view: "doc-trace", label: "Jejak Dokumen", at: "vendor-bills" });
  const seen = [];
  const h = (e) => seen.push(e.detail);
  window.addEventListener("kn-open-trace", h);
  await act(async () => { out.current.goBack(out.current.backTo); });
  window.removeEventListener("kn-open-trace", h);
  expect(seen).toEqual([{ docType: "purchase_order", docId: "po1", number: "PO-1" }]);
  expect(out.current.backTo).toBeNull();
  // Dokumen di layar yang sama tidak memasang bilah kembali (asal = tujuan).
  await act(async () => { out.current.openDocument(link); });
  expect(out.current.backTo).toBeNull();
  // Memilih menu lain menghapus bilah kembali.
  await act(async () => { out.current.handleNavSelect("doc-trace", "doc-trace"); });
  await act(async () => { out.current.openDocument(link); });
  expect(out.current.backTo).not.toBeNull();
  await act(async () => { out.current.handleNavSelect("orders", "orders"); });
  expect(out.current.backTo).toBeNull();
  // Kartu angka: `preset.from` → bilah kembali ke layar kartu.
  await act(async () => { out.current.navigateTo("ar-aging", { preset: { from: { view: "finance-tower" } } }); });
  expect(out.current.backTo).toMatchObject({ view: "finance-tower", label: "Dasbor Keuangan", at: "ar-aging" });
});

// ── Kartu angka (IA-11) ──────────────────────────────────────────────────────────────────────────────────────────────
test("PK44 — KpiCard ber-onClick menampilkan tombol tautan baku", async () => {
  const onClick = jest.fn();
  await mount(<div><KpiCard testId="k1" label="Piutang" value="Rp 1" onClick={onClick} actionLabel="Buka Piutang" />
    <KpiCard testId="k2" label="Modal Kerja" value="Rp 2" /></div>);
  const b = q("k1-open");
  expect(b.className).toContain("link-button");
  expect(b.textContent).toContain("Buka Piutang");
  await act(async () => { b.click(); });
  expect(onClick).toHaveBeenCalledTimes(1);
  expect(q("k2-open")).toBeNull();
});
