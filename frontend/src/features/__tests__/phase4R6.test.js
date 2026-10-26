// Fase 4 · R6 — sisa audit UI tahap 2 lintas layar: nomor dokumen di Jejak Audit, kode wilayah di ubah badan usaha,
// kode mentah di Meja Peran, tautan dokumen notifikasi (nota kredit/desain), sapaan Tanya KN di HP.
import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";
import AdminAuditList from "../admin/AdminAuditList";
import RoleDesk from "../desks/RoleDesk";
import { humanizeStage, humanizeSubtitle, deskNumber, humanizeQueueRows } from "../desks/deskText";
import { notifDocTarget, openNotifDocument } from "../notifications/notifDocTarget";
import { TanyaWelcome } from "../tanya/TanyaChatPane";
import EntityDetailDrawer from "../settings/entities/EntityDetailDrawer";
import { RND_EVENT } from "../rnd/rndDeepLink";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const mockGet = jest.fn();
const mockPatch = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), patch: (...a) => mockPatch(...a),
    defaults: { headers: { common: {} } } },
  API: "/api",
  setActiveEntity: () => {},
}));
const mockMyDesk = jest.fn();
jest.mock("../sales_admin/workDeskApi", () => ({
  ...jest.requireActual("../sales_admin/workDeskApi"),
  myDesk: (...a) => mockMyDesk(...a),
}));

async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  await act(async () => {});
  return { host, root };
}
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
afterEach(() => { document.body.innerHTML = ""; jest.clearAllMocks(); });

// ─── 1. Jejak Audit menyebut nomor dokumen (G5-01) ────────────────────────────────────────────────────────────
test("Jejak Audit: baris menyebut nomor dokumen dari server, bukan id teknis", async () => {
  const logs = [
    { id: "a1", action: "order_confirmed", actor: "Budi", entity_type: "sales_order", entity_id: "so_3ee0456e1a42",
      doc_number: "KSC/SO-00012", timestamp: "2026-10-26T01:00:00Z" },
    { id: "a2", action: "order_confirmed", actor: "Budi", entity_type: "sales_order", entity_id: "so_dead00000000",
      timestamp: "2026-10-26T01:00:00Z" },
  ];
  const onShowDetail = jest.fn();
  const { host, root } = await mount(<AdminAuditList auditLogs={logs} onShowDetail={onShowDetail} />);
  expect(q(host, "audit-row-doc-a1").textContent).toContain("Pesanan penjualan KSC/SO-00012");
  expect(q(host, "audit-row-doc-a2").textContent).toContain("Pesanan penjualan");
  expect(host.textContent).not.toMatch(/so_3ee0456e1a42|so_dead/);
  await act(async () => { q(host, "audit-row-a1").click(); });
  const detail = onShowDetail.mock.calls[0][0];
  expect(detail.facts).toEqual(expect.arrayContaining([{ label: "Nomor / nama", value: "KSC/SO-00012" }]));
  await act(async () => { root.unmount(); });
});

// ─── 2. Meja Peran: kode mentah di semua antrean (G5-10 sisa) ────────────────────────────────────────────────
test("deskText: tahap/status/flow/target mentah → label; id teknis tidak tampil sebagai nomor", () => {
  expect(humanizeStage("Giliran Anda — SO-1, tahap: refund_settled")).toBe("Giliran Anda — SO-1, tahap: selesai · refund");
  expect(humanizeSubtitle("waiting_approval · Budi")).toBe("Menunggu persetujuan · Budi");
  expect(humanizeSubtitle("outbound · 12 yard · Gudang A")).toBe("Kirim barang · 12 yard · Gudang A");
  expect(humanizeSubtitle("motif")).toBe("Motif");
  expect(humanizeSubtitle("Sedang diperiksa QC")).toBe("Sedang diperiksa QC");      // kalimat biasa tidak diubah
  expect(humanizeSubtitle("tunai")).toBe("tunai");                                  // kata tak dikenal tidak diubah
  expect(deskNumber({ number: "KSC/SO-00012" })).toBe("KSC/SO-00012");
  expect(deskNumber({ number: "wms_bef96c0e9725", ref_type: "wms_task", flow_type: "outbound" })).toBe("PICK-0E9725");
  expect(deskNumber({ number: "wms_bef96c0e9725", ref_type: "wms_task", flow_type: "inbound" })).toBe("GRN-0E9725");
  expect(deskNumber({ number: "sret_bd29c5d52a27", ref_type: "sales_return" })).toBe("");
  const raw = { number: "wms_bef96c0e9725", ref_type: "wms_task", subtitle: "outbound", title: "X" };
  const [qq] = humanizeQueueRows([{ id: "tugas_wms", rows: [raw] }]);
  expect(qq.rows[0]._raw).toBe(raw);                                                 // aksi memakai baris asli
});

test("Meja Saya: subjudul berlabel; tombol aksi tetap mengirim nomor asli server", async () => {
  mockMyDesk.mockResolvedValue({ title: "Meja Manajer", queues: [
    { id: "so_setuju", label: "SO menunggu persetujuan", count: 1, value_kind: "count", rows: [
      { ref_type: "sales_order", ref_id: "so_1", number: "KSC/SO-00001", title: "Toko A",
        subtitle: "waiting_approval · Budi", badge: "waiting_approval", action: "Putuskan", age_days: 1 }] },
    { id: "giliran_saya", label: "Giliran saya", count: 1, value_kind: "count", rows: [
      { ref_type: "sales_order", ref_id: "so_2", number: "KSC/SO-00002", title: "Giliran: KSC/SO-00002",
        subtitle: "tahap: cancelled", action: "Buka", age_days: 0, link: "orders" }] },
  ] });
  const onOpenDocument = jest.fn();
  const { host, root } = await mount(<RoleDesk desk="me" onOpenDocument={onOpenDocument} />);
  expect(host.textContent).toContain("Menunggu persetujuan · Budi");
  expect(host.textContent).toContain("tahap: dibatalkan");
  expect(host.textContent).not.toContain("waiting_approval ·");
  const btn = q(host, "my-desk-action-so_1");
  await act(async () => { btn.click(); });
  expect(onOpenDocument).toHaveBeenCalledWith(expect.objectContaining({ focus_id: "so_1", number: "KSC/SO-00001" }));
  await act(async () => { root.unmount(); });
});

// ─── 3. Notifikasi → dokumennya (G5-09) ───────────────────────────────────────────────────────────────────────
test("notifDocTarget: nota kredit → detail SO; desain → rincian desain lewat kanal R&D; lainnya null", () => {
  const cn = { type: "od_cancel_credit_note", link: "orders",
    doc: { ref_type: "sales_order", ref_id: "so_9", number: "KSC/SO-00389", label: "Nota kredit KSC/CN-00052 di KSC/SO-00389" } };
  expect(notifDocTarget(cn)).toEqual({ link: expect.objectContaining({ view: "orders", nav_id: "sales-orders",
    focus_type: "sales_order", focus_id: "so_9", number: "KSC/SO-00389" }) });
  const dsg = { type: "design_lifecycle", link: "rnd-designs", doc: { ref_type: "design", ref_id: "dsgn_1", number: "BDI-01" } };
  expect(notifDocTarget(dsg)).toEqual({ rnd: { view: "rnd-designs", designId: "dsgn_1" } });
  expect(notifDocTarget({ type: "turn", link: "operations" })).toBeNull();
  expect(notifDocTarget({ doc: { ref_type: "jenis_tak_dikenal", ref_id: "x" } })).toBeNull();

  const openDocument = jest.fn();
  expect(openNotifDocument(cn, openDocument)).toBe(true);
  expect(openDocument).toHaveBeenCalledWith(expect.objectContaining({ focus_id: "so_9" }));
  const seen = [];
  const h = (e) => seen.push(e.detail);
  window.addEventListener(RND_EVENT, h);
  expect(openNotifDocument(dsg, openDocument)).toBe(true);
  window.removeEventListener(RND_EVENT, h);
  expect(seen).toEqual([{ view: "rnd-designs", designId: "dsgn_1" }]);
  expect(openNotifDocument({ type: "turn" }, openDocument)).toBe(false);
});

// ─── 4. Ubah badan usaha memakai pemilih wilayah (G5-25) ──────────────────────────────────────────────────────
test("Detail Badan Usaha: Kota teks bebas diganti pemilih wilayah; kota lama ditandai; simpan hanya yang berubah", async () => {
  const ent = { id: "ent_ksc", legal_name: "PT Sukacita", short_name: "Sukacita", type: "PT", status: "active",
    doc_prefix: "KSC", city: "Bandung", address: "Jl. A", phone: "0811", email: "", npwp: "", logo_url: "",
    fiscal_year_start: "01-01", country: "", country_code: "", province: "", province_code: "", city_code: "",
    district: "", district_code: "", postal_code: "" };
  mockGet.mockImplementation((url) => {
    if (url === "/api/entities/ent_ksc") return Promise.resolve({ data: ent });
    if (url.endsWith("/readiness")) return Promise.resolve({ data: { items: [], percent: 0 } });
    if (url.endsWith("/audit")) return Promise.resolve({ data: [] });
    return Promise.resolve({ data: [] });   // /wilayah/*
  });
  mockPatch.mockResolvedValue({ data: ent });
  const { host, root } = await mount(<EntityDetailDrawer entityId="ent_ksc" canManage onClose={() => {}} />);
  expect(q(host, "entity-detail-city-input")).toBeNull();
  expect(q(host, "entity-detail-loc-fields")).not.toBeNull();
  expect(q(host, "entity-detail-location-legacy").textContent).toContain("Bandung");
  const phone = q(host, "entity-detail-phone-input");
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  await act(async () => { setter.call(phone, "0812"); phone.dispatchEvent(new Event("input", { bubbles: true })); });
  await act(async () => { q(host, "entity-detail-save").click(); });
  expect(mockPatch).toHaveBeenCalledWith("/api/entities/ent_ksc", { data: { phone: "0812" } });
  await act(async () => { root.unmount(); });
});

// ─── 5. Tanya KN di HP: saran pembuka tidak tertutup kotak input (G5-62) ───────────────────────────────────────
test("Tanya KN: sapaan HP ringkas (saran 2 kolom, terpotong ≤3 baris + tooltip teks lengkap)", async () => {
  const css = fs.readFileSync(path.join(__dirname, "../tanya/tanya.css"), "utf8");
  expect(css).toMatch(/\.tanya-page\.compact \.tanya-welcome-prompts \{ grid-template-columns: repeat\(2/);
  expect(css).toMatch(/\.tanya-page\.compact \.tanya-welcome-mark \{ display: none; \}/);
  expect(css).not.toMatch(/\.tanya-page\.compact \.tanya-scroll > \.tanya-col \{ padding-bottom: 72px; \}/);
  const label = "Berapa uang masuk dari pelanggan minggu ini dan siapa yang jatuh tempo besok?";
  const { host, root } = await mount(<TanyaWelcome prompts={[{ label }]} onPick={() => {}} />);
  expect(q(host, "tanya-welcome-prompt-0").getAttribute("title")).toBe(label);
  await act(async () => { root.unmount(); });
});
