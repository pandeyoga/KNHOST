// Sisir gerbang nama peran (review 2026-10-20) — tombol mengikuti izin efektif server (satu izin per aksi),
// aturan peran server (peringkat penyetuju, Admin-only) tetap berbasis peran. Render awal (tanpa efek/jaringan).
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import POCompactPanel from "../admin/po/POCompactPanel";
import PenaltyPanel from "../finance/payments/PenaltyPanel";
import SpecialOrderShippingPanel from "../sales/SpecialOrderShippingPanel";
import QcHubView from "../inspections/QcHubView";
import VisitsView from "../hr/VisitsView";
import SupplierItemsView from "../purchasing/supplier-items/SupplierItemsView";
import ContractsView from "../purchasing/contracts/ContractsView";
import CashAdvancesView from "../pettycash/CashAdvancesView";

const html = (el) => renderToStaticMarkup(el);

describe("PO — ACC mengikuti peringkat yang dituntut dokumen, aksi lain purchase_order.update", () => {
  const po = { id: "po1", po_number: "PO-1", status: "waiting_approval", required_approval_role: "manager", items: [] };
  const render = (user) => html(<POCompactPanel po={po} currentUser={user} />);
  test("Manager tanpa purchase_order.update: tombol Setujui ada, Batalkan tidak", () => {
    const out = render({ role: "manager", permissions: { purchase_order: ["view"] } });
    expect(out).toContain("approve-po-button");
    expect(out).not.toContain("cancel-po-button");
  });
  test("Admin Sales berizin update: Batalkan ada, Setujui tidak (peringkat di bawah manajer)", () => {
    const out = render({ role: "sales_admin", permissions: { purchase_order: ["view", "update"] } });
    expect(out).not.toContain("approve-po-button");
    expect(out).toContain("cancel-po-button");
  });
});

describe("Denda — satu izin per aksi", () => {
  const rows = [{ id: "p1", number: "PN-1", status: "draft", amount: 1000, due_date: "2026-10-01", days_late: 3 }];
  const render = (perms) => html(<PenaltyPanel rows={rows} currentUser={{ role: "x", permissions: { penalty: perms } }} />);
  test("Finance (penalty.issue saja): Terbitkan ada, Ubah Nominal/Bebaskan tidak", () => {
    const out = render(["view", "issue"]);
    expect(out).toContain("penalty-issue-p1");
    expect(out).not.toContain("penalty-adjust-p1");
    expect(out).not.toContain("penalty-waive-p1");
  });
  test("adjust tanpa waive & issue: hanya Ubah Nominal", () => {
    const out = render(["view", "adjust"]);
    expect(out).toContain("penalty-adjust-p1");
    expect(out).not.toContain("penalty-waive-p1");
    expect(out).not.toContain("penalty-issue-p1");
  });
});

describe("OD — siapkan pengiriman = order.update", () => {
  const order = { id: "so1", status: "ready", linked_po_id: "po1", chain: {} };
  const render = (user) => html(<SpecialOrderShippingPanel order={order} currentUser={user} />);
  test("Admin Gudang tanpa order.update tidak melihat tombol (server menolak)", () => {
    expect(render({ role: "warehouse_admin", permissions: { order: ["view"] } })).not.toContain("od-prepare-shipment-button");
  });
  test("Sales berizin order.update melihat tombol", () => {
    expect(render({ role: "sales", permissions: { order: ["view", "update"] } })).toContain("od-prepare-shipment-button");
  });
});

describe("QC hub — antrean kedatangan butuh wms.view", () => {
  const render = (user) => html(<QcHubView currentUser={user} />);
  test("QC tanpa wms.view hanya tab dokumen", () => {
    const out = render({ role: "qc", permissions: { qc: ["view", "inspect"] } });
    expect(out).not.toContain("qc-hub-tab-queue");
    expect(out).toContain("qc-hub-tab-docs");
  });
  test("peran berizin wms.view melihat antrean", () => {
    expect(render({ role: "warehouse", permissions: { wms: ["view"] } })).toContain("qc-hub-tab-queue");
  });
});

describe("Kunjungan — dasbor penyelia butuh hr.view", () => {
  const render = (user) => html(<VisitsView currentUser={user} selectedEntity="ent_ksc" />);
  test("Manager berizin hr.view: dasbor penyelia", () => {
    expect(render({ role: "manager", permissions: { hr: ["view"] } })).not.toContain("my-visits-view");
  });
  test("Manager tanpa hr.view & Sales: tampilan Kunjungan Saya", () => {
    expect(render({ role: "manager", permissions: {} })).toContain("my-visits-view");
    expect(render({ role: "sales", permissions: { hr: ["view"] } })).toContain("my-visits-view");
  });
});

describe("Barang supplier — impor & buat dipisah", () => {
  test("izin impor saja: tombol Impor ada, Barang Baru tidak", () => {
    const out = html(<SupplierItemsView currentUser={{ role: "x", permissions: { supplier_item: ["view", "import"] } }} />);
    expect(out).toContain("supplier-items-import");
    expect(out).not.toContain("supplier-items-create");
  });
});

describe("Kontrak supplier — buat = supplier_contract.create, pintasan kebijakan = settings.view", () => {
  const render = (perms) => html(<ContractsView currentUser={{ role: "manager", permissions: perms }} />);
  test("Manager hanya-lihat kontrak: pintasan kebijakan ada, Kontrak Baru tidak", () => {
    const out = render({ supplier_contract: ["view"], settings: ["view"] });
    expect(out).toContain("contracts-policy-button");
    expect(out).not.toContain("contracts-create-button");
  });
  test("berizin create tanpa settings.view: Kontrak Baru ada, pintasan tidak", () => {
    const out = render({ supplier_contract: ["view", "create"] });
    expect(out).toContain("contracts-create-button");
    expect(out).not.toContain("contracts-policy-button");
  });
});

describe("Kasbon — buat = cash_advance.create", () => {
  test("Finance berizin create melihat tombol (sebelumnya disembunyikan nama peran)", () => {
    expect(html(<CashAdvancesView currentUser={{ role: "finance", permissions: { cash_advance: ["view", "create"] } }} />)).toContain("ca-create-btn");
  });
  test("Sales tanpa izin create tidak melihat tombol", () => {
    expect(html(<CashAdvancesView currentUser={{ role: "sales", permissions: { cash_advance: ["view"] } }} />)).not.toContain("ca-create-btn");
  });
});
