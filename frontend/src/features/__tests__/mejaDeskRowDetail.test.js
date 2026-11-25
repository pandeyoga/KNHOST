// MEJA-4 — pop-up rincian umum (§5.3): teks utuh, PT, waktu nyata, registri panel, aksi & "Buka layar penuh".
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import DeskRowDetail from "../desks/DeskRowDetail";
import { DESK_PANELS } from "../desks/deskPanels";
import { ageText } from "../sales_admin/workDeskApi";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const teks = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");
let roots = [];
async function mount(el) {
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host); roots.push(root);
  await act(async () => { root.render(el); }); await act(async () => {});
  return host;
}
const klik = async (id) => act(async () => { q(id).dispatchEvent(new MouseEvent("click", { bubbles: true })); });
afterEach(async () => { for (const r of roots) await act(async () => r.unmount()); roots = []; document.body.innerHTML = ""; });
const ENTS = [{ id: "ent_ksc", short_name: "KSC" }];
const PANJANG = "Pelanggan minta kirim Senin pagi, alamat gudang baru di Jl. Raya Bandung no. 17, hubungi Pak Ujang dulu. ".repeat(2);
const ROW = { ref_type: "sales_order", ref_id: "so1", number: "SO-1", title: "Toko A", subtitle: PANJANG, badge: "reserved",
  value: 1500000, age_days: 4, age_kind: "wait", at: "2026-11-20T03:00:00Z", entity_id: "ent_ksc", sales_name: "Ayu",
  booking_until: "2026-11-30T10:00:00Z", action: "Follow-up", action_kind: "open",
  order_lines: [{ product_name: "Kain A", sku: "KA-1", quantity: 10, unit: "yard", warehouse: "Gudang Woven" },
                { product_name: "Kain B", sku: "KB-1", quantity: 5, unit: "yard", warehouse: "" }] };
const QUEUE = { id: "jatuh_tempo", label: "Jatuh tempo", value_label: "Sisa tagihan" };
const wrap = (el) => <EntityScopeProvider selectedEntity="all" entities={ENTS}>{el}</EntityScopeProvider>;

test("panel umum: teks utuh, PT, masuk nyata, batas cadangan, semua barang", async () => {
  await mount(wrap(<DeskRowDetail row={ROW} queue={QUEUE} onClose={() => {}} onAction={() => {}} />));
  expect(teks(q("desk-detail-title"))).toContain("SO-1 · Toko A");
  expect(teks(q("desk-detail-subtitle"))).toContain("KSC");
  expect(q("desk-detail-field-subtitle").textContent).toContain(PANJANG.trim());
  expect(teks(q("desk-detail-field-entity_id"))).toContain("KSC");
  expect(teks(q("desk-detail-field-at"))).toMatch(/Masuk/);
  expect(teks(q("desk-detail-field-booking_until"))).toMatch(/Batas cadangan/);
  expect(teks(q("desk-detail-field-value"))).toMatch(/Sisa tagihan/);
  expect(document.body.querySelectorAll('[data-testid^="desk-detail-line-"]')).toHaveLength(2);
  expect(document.body.textContent).not.toMatch(/±/);
});

test("baris lewat tempo: 'lewat n hari' dan label Jatuh tempo; tanpa at → tidak ada bidang waktu; tanpa PT → tidak ada bidang PT", async () => {
  expect(ageText({ age_days: 8, age_kind: "overdue" })).toBe("lewat 8 hari");
  expect(ageText({ age_days: 0, age_kind: "overdue" })).toBe("jatuh tempo hari ini");
  expect(ageText({ age_days: 8 })).toBe("8 hari");
  await mount(wrap(<DeskRowDetail row={{ ...ROW, age_kind: "overdue", age_days: 8 }} queue={QUEUE} onClose={() => {}} />));
  expect(teks(q("desk-detail-field-at"))).toMatch(/Jatuh tempo/);
  expect(teks(q("desk-detail-field-age"))).toMatch(/lewat 8 hari/);
  for (const r of roots) await act(async () => r.unmount()); roots = []; document.body.innerHTML = "";
  await mount(wrap(<DeskRowDetail row={{ ...ROW, at: "", entity_id: "" }} queue={QUEUE} onClose={() => {}} />));
  expect(q("desk-detail-field-at")).toBeNull();
  expect(q("desk-detail-field-entity_id")).toBeNull();
  expect(document.body.textContent).not.toMatch(/tidak dikenal/i);
});

test("registri: jenis yang punya panel memakai panel itu, bukan panel umum", async () => {
  DESK_PANELS.sales_order = ({ row }) => <div data-testid="panel-uji">{row.number}</div>;
  try {
    await mount(wrap(<DeskRowDetail row={ROW} queue={QUEUE} onClose={() => {}} />));
    expect(teks(q("panel-uji"))).toBe("SO-1");
    expect(q("desk-detail-field-subtitle")).toBeNull();
  } finally { delete DESK_PANELS.sales_order; }
});

test("aksi pindah layar bertanda ikon; klik menutup lalu menjalankan aksi; Buka layar penuh; aksi tambahan", async () => {
  const onAction = jest.fn(); const onClose = jest.fn(); const onOpenFull = jest.fn();
  const lain = { ref_type: "customer", ref_id: "c1", action_kind: "receipt" };
  await mount(wrap(<DeskRowDetail row={{ ...ROW, _moreActions: [{ label: "Terima pembayaran", row: lain }] }} queue={QUEUE}
    inPlace={(r) => r.action_kind === "receipt"} onAction={onAction} onClose={onClose} onOpenFull={onOpenFull} />));
  expect(q("desk-detail-action-nav")).not.toBeNull();
  await klik("desk-detail-action");
  expect(onClose).toHaveBeenCalled(); expect(onAction).toHaveBeenCalledWith(expect.objectContaining({ ref_id: "so1" }), QUEUE);
  await klik("desk-detail-action-0");
  expect(onAction).toHaveBeenLastCalledWith(lain, QUEUE);
  await klik("desk-detail-open-full");
  expect(onOpenFull).toHaveBeenCalledWith(expect.objectContaining({ ref_id: "so1" }), QUEUE);
});

test("baris tanpa aksi: tidak ada tombol aksi", async () => {
  await mount(wrap(<DeskRowDetail row={{ ...ROW, action: "" }} queue={QUEUE} onClose={() => {}} onOpenFull={() => {}} />));
  expect(q("desk-detail-action")).toBeNull();
  expect(q("desk-detail-open-full")).not.toBeNull();
});
