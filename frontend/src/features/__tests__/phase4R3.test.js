// Fase 4 · R3 — rantai pasok: pop-up buatan sendiri → FormModal/DetailModal (L-03), tab/kepala/tabel/KPI baku
// (L-01/L-02/L-07/L-08), pemecahan InspectionDetailPanel (< 500 baris), grid HP ber-kolom dasar, dan Lot & Silsilah
// tidak lagi memanggil /makloons untuk peran tanpa izin (crawl HP — 403 Admin Sales).
import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";

import PurchaseRequisitionDetailPanel from "../purchasing/PurchaseRequisitionDetailPanel";
import { IssueModal, ReceiveModal } from "../purchasing/makloon/MkoStepModals";
import GrnCreateWizard from "../wms/grn/GrnCreateWizard";
import RollHoldControl from "../wms/inventory/RollHoldControl";
import QcHubView from "../inspections/QcHubView";
import InspectionDetailPanel from "../inspections/InspectionDetailPanel";
import LotsView from "../inventory/lots/LotsView";
import RfidTagsView from "../rfid/RfidTagsView";
import RepairOrdersView from "../wms/repair/RepairOrdersView";
import EscalationManagement from "../manager/EscalationManagement";
import DispatchDashboard from "../logistics/DispatchDashboard";
import InventoryStatusBoard from "../inventory/InventoryStatusBoard";

jest.mock("../../services/apiClient", () => {
  const fn = { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() };
  return { __esModule: true, default: fn, API: "/api" };
});
jest.mock("../../components/KNSelect", () => {
  const Sel = ({ value, onValueChange, options = [], "data-testid": tid }) => (
    <select data-testid={tid} value={value} onChange={(e) => onValueChange?.(e.target.value)}>
      <option value="" />
      {options.map((o) => <option key={`${o.value}`} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: Sel, KNSelect: Sel };
});
jest.mock("../documents/DocumentActionsBar", () => () => null);
jest.mock("../inspections/InspectLineModal", () => () => null);
jest.mock("../inspections/InspectSheetGrid", () => () => null);
jest.mock("../wms/QCInspection", () => () => <div data-testid="qc-queue-stub" />);
jest.mock("../inspections/InspectionsView", () => () => <div data-testid="ins-docs-stub" />);
jest.mock("../internal_requests/InternalRequestCreateModal", () => () => null);
jest.mock("../rfid/RfidPrintVerifyPanel", () => () => null);
jest.mock("../settings/config/ConfigRedirectCard", () => () => null);
jest.mock("../inventory/lots/LotIdentityTrace", () => () => null);
const axios = require("../../services/apiClient").default;

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
let host; let root;
async function mount(el) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(el); });
  await flush();
}
afterEach(async () => {
  if (root) await act(async () => { root.unmount(); });
  host?.remove(); root = null;
  axios.get.mockReset(); axios.post.mockReset();
});
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const type = async (el, value) => {
  const proto = el.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
  await act(async () => { el.dispatchEvent(new Event("input", { bubbles: true })); });
};
const isFormModal = (id) => {
  const el = q(id);
  return Boolean(el && el.getAttribute("role") === "dialog" && el.classList.contains("kn-form-modal"));
};

const PR = {
  id: "pr1", number: "KSC/PR-00001", status: "pending_approval", source: "manual", entity_id: "ent1",
  total_est_amount: 1000, items: [], approval_required: true,
};

describe("L-03 — PR: Konversi & Tolak = FormModal; galat di DALAM pop-up; alasan tolak ≥ 5 huruf (K-14)", () => {
  test("Tolak: tombol mati sampai 5 huruf, galat server tampil di pop-up (bukan bilah panel)", async () => {
    axios.get.mockResolvedValue({ data: [] });
    axios.post.mockRejectedValue({ response: { status: 400, data: { detail: "PR sudah diproses." } } });
    await mount(<PurchaseRequisitionDetailPanel pr={PR} canApprove suppliers={[]} warehouses={[]}
      onBack={() => {}} onChanged={() => {}} reload={() => {}} />);
    await act(async () => { q("pr-action-reject").click(); });
    expect(isFormModal("pr-reject-modal")).toBe(true);
    expect(q("pr-reject-confirm").disabled).toBe(true);
    await type(q("pr-reject-reason"), "ok");
    expect(q("pr-reject-confirm").disabled).toBe(true);
    await type(q("pr-reject-reason"), "Di atas anggaran");
    expect(q("pr-reject-confirm").disabled).toBe(false);
    await act(async () => { q("pr-reject-confirm").click(); });
    await flush();
    expect(q("pr-reject-modal-error").textContent).toContain("PR sudah diproses.");
    expect(q("pr-reject-modal").contains(q("pr-reject-modal-error"))).toBe(true);
    expect(q("pr-detail-error")).toBeNull();
    // Batal (× baku) menutup pop-up
    await act(async () => { q("pr-reject-modal-close").click(); });
    expect(q("pr-reject-modal")).toBeNull();
  });

  test("Konversi ke PO: pop-up baku, supplier kosong → galat di pop-up", async () => {
    axios.get.mockResolvedValue({ data: [] });
    await mount(<PurchaseRequisitionDetailPanel pr={{ ...PR, status: "approved" }} canApprove suppliers={[{ id: "s1", name: "Sup" }]}
      warehouses={[]} onBack={() => {}} onChanged={() => {}} reload={() => {}} />);
    await act(async () => { q("pr-action-convert").click(); });
    expect(isFormModal("pr-convert-modal")).toBe(true);
    await act(async () => { q("pr-convert-confirm").click(); });
    expect(q("pr-convert-modal-error").textContent).toMatch(/Pilih supplier/);
  });
});

describe("L-03 — Order Makloon: Issue/Terima = FormModal (diekstrak dari panel 693 baris)", () => {
  const step = { seq: 1, input_qty: 10, input_unit: "yard", input_name: "Greige", makloon_name: "Mitra A",
    source_stock: [{ warehouse_id: "w1", available_qty: 50 }], expected_output_qty: 10, output_unit: "yard", output_sku: "OUT" };
  beforeEach(() => { axios.get.mockResolvedValue({ data: [] }); });
  test("galat onConfirm tampil di kaki pop-up Issue", async () => {
    const onConfirm = jest.fn(() => Promise.reject(new Error("Stok tidak cukup.")));
    await mount(<IssueModal step={step} warehouses={[{ id: "w1", name: "Gd", code: "G1" }]} defaultWh="w1" busy={false}
      onClose={() => {}} onConfirm={onConfirm} />);
    expect(isFormModal("mko-issue-modal")).toBe(true);
    await act(async () => { q("mko-issue-confirm").click(); });
    await flush();
    expect(onConfirm).toHaveBeenCalledWith("w1", "", "");
    expect(q("mko-issue-modal-error").textContent).toBe("Stok tidak cukup.");
  });
  test("Terima: validasi total roll tampil di pop-up; isian lengkap tetap ada", async () => {
    const onConfirm = jest.fn(() => Promise.resolve());
    await mount(<ReceiveModal step={step} warehouses={[{ id: "w1", name: "Gd", code: "G1" }]} defaultWh="w1" mkoNumber="MKO-1"
      busy={false} onClose={() => {}} onConfirm={onConfirm} />);
    for (const id of ["mko-recv-output-qty", "mko-recv-byproduct-qty", "mko-recv-warehouse", "mko-recv-colors",
      "mko-recv-repeats", "mko-recv-invoice", "mko-recv-doc-uom", "mko-recv-roll-lot-0", "mko-recv-roll-dyelot-0"]) {
      expect(q(id)).not.toBeNull();
    }
    await type(q("mko-recv-roll-len-0"), "4");
    await act(async () => { q("mko-receive-confirm").click(); });
    expect(onConfirm).not.toHaveBeenCalled();
    expect(q("mko-receive-modal-error").textContent).toMatch(/Total panjang roll/);
  });
});

describe("L-03 — GRN & roll: wizard kedatangan dan dialog tahan roll = FormModal", () => {
  test("wizard: testid lama tetap, × baku memanggil onClose", async () => {
    axios.get.mockResolvedValue({ data: [] });
    const onClose = jest.fn();
    await mount(<GrnCreateWizard preset={null} onClose={onClose} onCreated={() => {}} />);
    expect(isFormModal("grn-wizard")).toBe(true);
    expect(q("grn-wizard-next").disabled).toBe(true);
    await act(async () => { q("grn-wizard-close").click(); });
    expect(onClose).toHaveBeenCalled();
  });
  test("tahan roll: alasan ≥ 5 huruf, submit lewat FormModal", async () => {
    axios.post.mockResolvedValue({ data: {} });
    const onChanged = jest.fn();
    await mount(<RollHoldControl roll={{ id: "r1", roll_no: "R-1", status: "available" }} onChanged={onChanged} />);
    await act(async () => { q("roll-hold-btn-r1").click(); });
    expect(isFormModal("roll-hold-dialog")).toBe(true);
    expect(q("roll-hold-submit").disabled).toBe(true);
    await type(q("roll-hold-reason-input"), "Belang warna");
    await act(async () => { q("roll-hold-submit").click(); });
    await flush();
    expect(axios.post).toHaveBeenCalledWith("/api/inventory/rolls/r1/hold", { reason: "Belang warna" });
    expect(onChanged).toHaveBeenCalled();
    expect(q("roll-hold-dialog")).toBeNull();
  });
});

describe("L-01 — tab baku", () => {
  test("QC Hub tanpa `bare` memakai PageTabs (role=tablist), testid qc-hub-tab-* tetap", async () => {
    await mount(<QcHubView currentUser={{ role: "qc", permissions: { qc: ["view"] } }} />);
    const bar = q("qc-hub-tab");
    expect(bar.getAttribute("role")).toBe("tablist");
    expect(q("qc-hub-tab-queue").getAttribute("aria-selected")).toBe("true");
    await act(async () => { q("qc-hub-tab-docs").click(); });
    await flush();
    expect(q("ins-docs-stub")).not.toBeNull();
  });
});

describe("Batas 500 baris — InspectionDetailPanel dipecah tanpa mengubah perilaku", () => {
  const read = (f) => fs.readFileSync(path.join(__dirname, "..", f), "utf8");
  test("panel < 500 baris; tabel baris & riwayat di berkas sendiri", () => {
    expect(read("inspections/InspectionDetailPanel.jsx").split("\n").length).toBeLessThan(500);
    expect(read("inspections/InspectionLinesTable.jsx")).toContain("ins-hold-explainer");
    expect(read("inspections/InspectionDetailParts.jsx")).toContain("ins-detail-history");
  });
  test("baris ditahan + tombol lepas/tolak + riwayat tetap dirender", async () => {
    const doc = {
      id: "i1", number: "KSC/INS-00001", kind: "po_receipt", status: "in_progress", task_id: "t1",
      summary: { hold: 1, lines: 1, inspected: 0 },
      lines: [{ id: "l1", roll_id: "r1", roll_no: "R-01", sku: "K1", hold: true, quantity: 10, unit: "yard" }],
      history: [{ at: "2026-10-26T01:00:00Z", label: "Dibuat", actor: "Admin" }],
    };
    const meta = { can_release_hold: true, can_qc_release: true, decisions: [] };
    await mount(<InspectionDetailPanel doc={doc} meta={meta} currentUser={{ permissions: { inspection: ["decide"] } }}
      onChanged={() => {}} onClose={() => {}} />);
    expect(q("ins-line-l1")).not.toBeNull();
    expect(q("ins-line-hold-l1")).not.toBeNull();
    expect(q("ins-line-release-l1")).not.toBeNull();
    expect(q("ins-line-reject-l1")).not.toBeNull();
    expect(q("ins-hold-explainer")).not.toBeNull();
    expect(q("ins-detail-history").textContent).toContain("Dibuat");
  });
});

describe("Lot & Silsilah — /makloons hanya untuk peran berizin (crawl HP: 403 Admin Sales)", () => {
  const lotsGet = (url) => Promise.resolve({ data: url.includes("/lots") && !url.includes("stats") ? { items: [], total: 0 } : {} });
  test("Admin Sales (tanpa inventory.update / makloon.view) tidak memanggil /makloons", async () => {
    axios.get.mockImplementation(lotsGet);
    await mount(<LotsView user={{ role: "sales_admin", permissions: { inventory: ["view"] } }} />);
    expect(axios.get.mock.calls.some(([u]) => u === "/api/makloons")).toBe(false);
  });
  test("gudang berizin ubah + baca mitra makloon tetap memuat daftar mitra", async () => {
    axios.get.mockImplementation(lotsGet);
    await mount(<LotsView user={{ role: "warehouse", permissions: { inventory: ["view", "update"], makloon: ["view"] } }} />);
    expect(axios.get.mock.calls.some(([u]) => u === "/api/makloons")).toBe(true);
  });
});

describe("L-02/L-07 — kepala, tab & tabel baku", () => {
  test("Tag RFID: PageHeader + PageTabs + ResponsiveTable (.data-table), testid baris lama tetap", async () => {
    axios.get.mockImplementation((url) => Promise.resolve({ data:
      url.endsWith("/rfid/tags") ? { tags: [{ id: "t1", epc: "E1", sku: "K1", roll_no: "R1", roll_id: "r1" }] }
        : url.endsWith("/rfid/untagged-rolls") ? { rolls: [] } : url.endsWith("/warehouses") ? [] : {} }));
    await mount(<RfidTagsView currentUser={{}} />);
    expect(q("rfid-tags-header").classList.contains("view-header")).toBe(true);
    expect(q("rfid-tab").getAttribute("role")).toBe("tablist");
    expect(q("rfid-tab-tags")).not.toBeNull();
    const row = q("rfid-tag-row-t1");
    expect(row.closest("table").classList.contains("data-table")).toBe(true);
    expect(q("rfid-retire-t1")).not.toBeNull();
  });
  test("Perbaikan: PageHeader, status = FilterChips (bukan tab), tabel → ResponsiveTable", async () => {
    axios.get.mockResolvedValue({ data: { items: [{ id: "ro1", number: "KSC/RO-1", kind_label: "Celup ulang", partner_name: "Mitra",
      lines: [{ qty_sent: 5 }], cost_estimate: 1000, status: "draft", created_at: "2026-10-20" }], counts: { draft: 1 } } });
    await mount(<RepairOrdersView currentUser={{ permissions: {} }} />);
    await act(async () => { await new Promise((r) => setTimeout(r, 250)); });
    expect(q("repair-header").classList.contains("view-header")).toBe(true);
    expect(q("repair-tab-all").getAttribute("aria-pressed")).toBe("true");
    expect(q("repair-tab-draft").classList.contains("filter-chip")).toBe(true);
    expect(q("repair-row-ro1")).not.toBeNull();
  });
  test("Eskalasi: PageHeader + FilterChips filter-type-*; pop-up Selesaikan = FormModal", async () => {
    axios.get.mockImplementation((url) => Promise.resolve({ data: url.includes("inbound") ? [{ id: "e1", sku: "K1", product_name: "Katun",
      po_number: "PO-1", expected_qty: 10, received_qty: 8, unit: "yard", escalation: { reason: "kurang", escalated_by: "a", escalated_at: "2026-10-20T00:00:00Z" } }] : [] }));
    await mount(<EscalationManagement user={{}} />);
    expect(q("escalation-header").classList.contains("view-header")).toBe(true);
    expect(q("filter-type-inbound").classList.contains("filter-chip")).toBe(true);
    await act(async () => { q("resolve-task-e1").click(); });
    expect(isFormModal("escalation-resolve-modal")).toBe(true);
    await act(async () => { q("escalation-resolve-submit").click(); });
    expect(q("escalation-resolve-modal-error").textContent).toMatch(/catatan penyelesaian/i);
  });
});

describe("L-08 — KPI baku: nilai 0 netral, tanpa aksen ungu", () => {
  test("Dasbor Pengiriman: KPI bernilai 0 abu netral", async () => {
    axios.get.mockResolvedValue({ data: { kpi: { unassigned_sj: 0, waiting_pickup: 2, late: 0 }, today: "2026-10-26" } });
    await mount(<DispatchDashboard params={{}} refreshKey={0} canManage canUpdate onOpen={() => {}} onCreate={() => {}}
      onGotoList={() => {}} onGotoFleet={() => {}} />);
    const zero = q("dispatch-kpi-unassigned").querySelector("p.text-\\[20px\\]");
    expect(zero.style.color).toBe("rgb(142, 142, 147)");
    const two = q("dispatch-kpi-waiting-pickup").querySelector("p.text-\\[20px\\]");
    expect(two.style.color).toBe("rgb(0, 88, 204)");
  });
  test("Papan Status Persediaan: KPI = MetricRow (metric-card, nol netral)", async () => {
    axios.get.mockResolvedValue({ data: [] });
    await mount(<InventoryStatusBoard currentUser={{ permissions: {} }} />);
    expect(q("status-board-metrics")).not.toBeNull();
    expect(q("sb-metric-products").classList.contains("metric-card")).toBe(true);
    expect(q("sb-metric-products").querySelector(".metric-zero")).not.toBeNull();
  });
});

describe("Grid HP — kolom dasar eksplisit di himpunan berkas R3", () => {
  // Pola `grid gap-3 lg:grid-cols-[…]` tanpa `grid-cols-1`: kolom implisit `auto` melebarkan halaman di 390 px.
  const ROOT = path.join(__dirname, "..");
  const DIRS = ["wms", "inventory", "inspections", "purchasing", "logistics", "rfid", "production", "transfers", "interco_prices"];
  const SKIP = ["purchasing/contrabon/", "purchasing/InputTax", "purchasing/CashManagementView.jsx", "purchasing/PrCreateModal.jsx"];
  const walk = (dir) => fs.readdirSync(dir, { withFileTypes: true }).flatMap((d) => (d.isDirectory()
    ? (d.name === "__tests__" ? [] : walk(path.join(dir, d.name))) : (/\.jsx?$/.test(d.name) ? [path.join(dir, d.name)] : [])));
  test("tidak ada className grid ber-`sm|md|lg|xl:grid-cols-[…]` tanpa grid-cols dasar", () => {
    const bad = [];
    DIRS.flatMap((d) => walk(path.join(ROOT, d))).forEach((file) => {
      const rel = path.relative(ROOT, file).split(path.sep).join("/");
      if (SKIP.some((s) => rel.startsWith(s))) return;
      const src = fs.readFileSync(file, "utf8");
      for (const m of src.matchAll(/className=\{?(["`])((?:(?!\1)[\s\S])*?)\1/g)) {
        const cls = m[2];
        if (/(^|\s)(sm|md|lg|xl):grid-cols-\[/.test(cls) && /(^|\s)grid(\s|$)/.test(cls) && !/(^|\s)grid-cols-/.test(cls)) {
          bad.push(`${rel}: ${cls.slice(0, 80)}`);
        }
      }
    });
    expect(bad).toEqual([]);
  });
});
