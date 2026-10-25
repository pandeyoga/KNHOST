// Fase 3 · P1 — pola tautan (LinkCard), pemilih PT di header (EntityRequiredNotice), MetricRow nol netral, papan
// "mode tautan" (D-07/D-28) dan satu dialog keputusan PO Custom / harga khusus (services/approvalDecisions).
import React, { act } from "react";
import { createRoot } from "react-dom/client";

import LinkCard from "../LinkCard";
import EntityRequiredNotice from "../EntityRequiredNotice";
import { MetricRow, isZeroMetric } from "../ListPageParts";
import WaitingQueueBoard from "../WaitingQueueBoard";
import { AppNavProvider } from "../../context/AppNavContext";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { boardRowLink } from "../../config/waitingBoards";
import { askReason } from "../../services/confirmService";
import {
  approvePrice, approveSpecialOrder, rejectSpecialOrder, specialOrderApprovedText,
} from "../../services/approvalDecisions";

jest.mock("../../services/apiClient", () => ({
  __esModule: true, API: "/api",
  default: { get: jest.fn(() => Promise.resolve({ data: { rows: [] } })), post: jest.fn(() => Promise.resolve({ data: {} })) },
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true, REASON_MIN_LENGTH: 5,
  askReason: jest.fn(), askConfirm: jest.fn(),
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let host; let root;
async function mount(el) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(el); });
}
afterEach(async () => { if (root) await act(async () => { root.unmount(); }); host?.remove(); root = null; });
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);

describe("LinkCard", () => {
  test("berwenang: kalimat 'kini dikelola di', tombol Buka lewat jalur navigasi bersama (alias + preset)", async () => {
    const nav = [];
    await mount(
      <AppNavProvider role="manager" onNavigateTo={(v, o) => nav.push([v, o.preset])}>
        <LinkCard testId="lk" what="Persetujuan" where="Pusat Persetujuan" view="approvals" preset={{ tab: "matrix" }}
          count={3} summary="3 menunggu" />
      </AppNavProvider>);
    expect(q("lk").textContent).toMatch(/Persetujuan kini dikelola di Pusat Persetujuan\./);
    expect(q("lk-count").textContent).toBe("3");
    await act(async () => { q("lk-open").click(); });
    expect(nav).toEqual([["approvals", { tab: "matrix" }]]);
  });

  test("tidak berwenang: ringkasan baca-saja satu baris (tanpa tombol); hideWhenDenied → tidak dirender", async () => {
    await mount(
      <AppNavProvider role="driver">
        <LinkCard testId="lk" what="Template dokumen" where="Pengaturan › Template Dokumen" view="pdf-templates" summary="3 aktif" />
        <LinkCard testId="lk2" what="x" where="y" view="pdf-templates" hideWhenDenied />
      </AppNavProvider>);
    expect(q("lk")).toBeNull();
    expect(q("lk-readonly").textContent).toMatch(/Template dokumen kini dikelola di Pengaturan › Template Dokumen\. · 3 aktif/);
    expect(q("lk-readonly").querySelector("button")).toBeNull();
    expect(q("lk2")).toBeNull();
    expect(q("lk2-readonly")).toBeNull();
  });

  test("di luar provider (mis. aplikasi HP): baca-saja, bukan tombol mati", async () => {
    await mount(<LinkCard testId="lk" what="a" where="b" view="orders" />);
    expect(q("lk-readonly")).not.toBeNull();
  });
});

describe("EntityRequiredNotice", () => {
  const ENT = [{ id: "ent_ksc", code: "KSC", name: "PT Kain Sukacita", short_name: "Sukacita" }, { id: "ent_kanda", code: "KND", name: "PT Kanda", short_name: "Kanda" }];

  test("mode 'Semua' + akun bisa berganti PT: kartu muncul; memilih PT = mengganti PT di HEADER", async () => {
    const picked = [];
    await mount(
      <EntityScopeProvider selectedEntity="all" entities={ENT} canSwitch pickEntity={(id) => picked.push(id)}>
        <EntityRequiredNotice what="tutup buku" testId="closing-ent" />
      </EntityScopeProvider>);
    expect(q("closing-ent").textContent).toMatch(/Pilih badan usaha untuk tutup buku/);
    await act(async () => { q("closing-ent-pick-ent_kanda").click(); });
    expect(picked).toEqual(["ent_kanda"]);
  });

  test("PT sudah dipilih, atau akun satu-PT: tidak tampil; `when` menimpa", async () => {
    await mount(
      <>
        <EntityScopeProvider selectedEntity="ent_ksc" entities={ENT} canSwitch pickEntity={() => {}}>
          <EntityRequiredNotice testId="a" />
        </EntityScopeProvider>
        <EntityScopeProvider selectedEntity="all" entities={ENT} canSwitch={false} pickEntity={() => {}}>
          <EntityRequiredNotice testId="b" />
        </EntityScopeProvider>
        <EntityScopeProvider selectedEntity="ent_ksc" entities={ENT} canSwitch pickEntity={() => {}}>
          <EntityRequiredNotice testId="c" when />
        </EntityScopeProvider>
      </>);
    expect(q("a")).toBeNull();
    expect(q("b")).toBeNull();
    expect(q("c")).not.toBeNull();
  });
});

describe("MetricRow — nol netral (L-08)", () => {
  test("isZeroMetric mengenali bentuk nol yang lazim", () => {
    ["0", 0, "Rp 0", "Rp 0", "0,00", "0 roll", "0%", " 0 "].forEach((v) => expect([v, isZeroMetric(v)]).toEqual([v, true]));
    ["10", "Rp 1.000", "0,5", "-", "—", null, undefined, "05"].forEach((v) => expect([v, isZeroMetric(v)]).toEqual([v, false]));
  });

  test("nilai nol tidak memakai warna tone; nilai bukan nol tetap", async () => {
    await mount(<MetricRow testId="kpi" items={[
      { label: "Selisih", value: "Rp 0", tone: "#C62828" },
      { label: "Terlambat", value: "3", tone: "#C62828" },
    ]} />);
    const vals = host.querySelectorAll(".metric-value");
    expect(vals[0].className).toMatch(/metric-zero/);
    expect(vals[0].getAttribute("style")).toBeNull();
    expect(vals[1].className).not.toMatch(/metric-zero/);
    expect(vals[1].style.color).toBe("rgb(198, 40, 40)");
  });
});

describe("papan antrean mode tautan (D-07/D-28)", () => {
  const board = {
    key: "special_order", view: "special-orders", count: 1, shown: 1, hidden: 0, truncated: false,
    rows: [{ id: "so1", number: "SORD-26-0001", title: "Pelanggan A", amount: 5000000, days_waiting: 4,
      action: { label: "Setujui", path: "/special-orders/so1/approve" } }],
  };

  test("mode bawaan (act): tombol keputusan tetap ada — perilaku papan lain tidak berubah", async () => {
    await mount(<WaitingQueueBoard board={board} testIdBase="b" rowTestIdBase="b-row" onNavigate={() => {}} />);
    expect(q("b").getAttribute("data-board-mode")).toBe("act");
    expect(q("b-row-act-so1")).not.toBeNull();
  });

  test("mode tautan: TANPA tombol Setujui; klik baris membuka dokumennya (boardRowLink → openDocument)", async () => {
    const opened = []; const navs = [];
    await mount(<WaitingQueueBoard board={board} testIdBase="b" rowTestIdBase="b-row" mode="link"
      onNavigate={(v) => navs.push(v)} onOpenRow={(r) => opened.push(boardRowLink(board, r))} />);
    expect(q("b").getAttribute("data-board-mode")).toBe("link");
    expect(q("b-row-act-so1")).toBeNull();
    await act(async () => { q("b-row-so1").click(); });
    expect(opened).toEqual([{ view: "special-orders", focus_type: "special_order", focus_id: "so1", number: "SORD-26-0001" }]);
    expect(navs).toEqual([]);
    await act(async () => { q("b-goto").click(); });
    expect(navs).toEqual(["special-orders"]);                 // tombol "Buka …" papan tetap membuka layarnya
  });

  test("boardRowLink: papan tanpa jenis fokus hanya membuka layarnya", () => {
    expect(boardRowLink({ key: "inspection_hold", view: "inspections" }, { id: "ins1", number: "KSC/INS-00001" }))
      .toEqual({ view: "inspections", focus_type: "inspection", focus_id: "ins1", number: "KSC/INS-00001" });
    expect(boardRowLink({ key: "transfer", view: "operations" }, { id: "t1" })).toEqual({ view: "operations" });
  });
});

describe("approvalDecisions — satu dialog Setujui/Tolak", () => {
  const order = { id: "so1", number: "SORD-26-0001", customer_name: "Pelanggan A", total_amount: 5000000,
    custom_item: { description: "Songket merah 50 yd" } };
  beforeEach(() => askReason.mockReset());

  test("setuju: catatan opsional, catatan bawaan HP bila kosong, kalimat hasil berantai", async () => {
    askReason.mockResolvedValueOnce("");
    const api = { post: jest.fn().mockResolvedValue({ data: { status: "approved", chain: { design_request: { number: "DSR-0012" }, samples: [{ number: "SMP-0031" }] } } }) };
    const res = await approveSpecialOrder(order, { defaultNote: "Disetujui dari HP", api });
    const dlg = askReason.mock.calls[0][0];
    expect(dlg).toMatchObject({ title: "Setujui SORD-26-0001 · Pelanggan A", confirmLabel: "Setujui", reasonRequired: false });
    expect(dlg.message).toMatch(/^Songket merah 50 yd · Rp/);
    expect(api.post).toHaveBeenCalledWith("/api/special-orders/so1/approve", { notes: "Disetujui dari HP" });
    expect(res.message).toBe("Pesanan disetujui. Diteruskan otomatis: DSR-0012, SMP-0031.");
    expect(specialOrderApprovedText({ status: "pending_approval" })).toMatch(/menunggu tingkat persetujuan berikutnya/);
  });

  test("batal → null tanpa panggilan API; tolak: alasan wajib ≥5 huruf (K-14)", async () => {
    const api = { post: jest.fn().mockResolvedValue({ data: { status: "rejected" } }) };
    askReason.mockResolvedValueOnce(null);
    expect(await approveSpecialOrder(order, { api })).toBeNull();
    expect(api.post).not.toHaveBeenCalled();
    askReason.mockResolvedValueOnce("  harga di bawah HPP ");
    const res = await rejectSpecialOrder(order, { api });
    expect(askReason.mock.calls[1][0]).toMatchObject({ confirmLabel: "Tolak", danger: true, reasonRequired: true, reasonMinLength: 5 });
    expect(api.post).toHaveBeenCalledWith("/api/special-orders/so1/reject", { reason: "harga di bawah HPP" });
    expect(res.message).toBe("SORD-26-0001 ditolak.");
  });

  test("harga khusus memakai dialog yang sama", async () => {
    askReason.mockResolvedValueOnce("ok");
    const api = { post: jest.fn().mockResolvedValue({ data: {} }) };
    const res = await approvePrice({ id: "pa1", customer_name: "Toko B", product_name: "Batik", requested_price: 90000, normal_price: 100000, unit: "yard" }, { api });
    expect(askReason.mock.calls[0][0].title).toBe("Setujui harga khusus · Toko B");
    expect(api.post).toHaveBeenCalledWith("/api/price-approvals/pa1/approve", { decision_notes: "ok" });
    expect(res.message).toBe("Harga khusus disetujui.");
  });
});
