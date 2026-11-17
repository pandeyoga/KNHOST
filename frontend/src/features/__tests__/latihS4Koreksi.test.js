// Pelatihan keuangan 18 Nov 2026 — situasi S4 "Koreksi & pembatalan" (uji jalan docs/pelatihan/2026-11-18_keuangan/uji/
// situasi/S4_koreksi_pembatalan.js). Temuan layar yang diperbaiki:
//  · Pesan halaman sesudah batal bayar tagihan tampil mentah "VB-00012: payment_void." → kalimat pengguna.
//  · Alasan batal bayar ditulis DI DALAM pil status (huruf kapital tiap kata, tidak turun baris) → teks biasa + nama pembatal.
//  · Kwitansi yang dianulir masih menampilkan selisih "Kurang Bayar · perlu diputus" → "Ikut dianulir".
//  · Anulir jurnal manual hanya Ya/Batal (tanpa alasan, standar N5) → minta alasan, sebut nominal & PT; alasan tampil di
//    rincian jurnal yang dianulir.
//  · Reklasifikasi Akun Sementara selalu bertanggal hari ini → ada isian tanggal (saldo bulan lalu dibersihkan di bulannya).
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    put: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: jest.fn(), askReason: jest.fn(), askText: jest.fn(), askChoice: jest.fn(), default: {},
}));
jest.mock("../../components/AskKnButton", () => ({ __esModule: true, AskKnButton: () => null, PENDING_KEY: "x" }));
jest.mock("../../components/KNSelect", () => {
  // eslint-disable-next-line global-require
  const React = require("react");
  const M = ({ value, onValueChange, options = [], "data-testid": tid }) => React.createElement("select",
    { "data-testid": tid, value: value || "", onChange: (e) => onValueChange && onValueChange(e.target.value) },
    [React.createElement("option", { key: "", value: "" }, "-"),
      ...options.map((o) => React.createElement("option", { key: o.value, value: o.value }, o.label))]);
  return { __esModule: true, default: M, KNSelect: M };
});

/* eslint-disable import/first */
import VendorBillPayments from "../purchasing/VendorBillPayments";
import { PESAN_AKSI_TAGIHAN } from "../purchasing/VendorBillsView";
import { VarianceCell } from "../crm/ARReceiptsHistory";
import JournalDetailModal from "../finance/JournalDetailModal";
import SuspensePanel from "../finance/SuspensePanel";
import { askReason } from "../../services/confirmService";
import { todayWib } from "../../utils/formatters";
import { REF_LABEL } from "../purchasing/CashManagementView";
/* eslint-enable import/first */

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
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = []; document.body.innerHTML = "";
});
beforeEach(() => {
  mockGet.mockImplementation(() => Promise.resolve({ data: {} }));
  mockPost.mockImplementation(() => Promise.resolve({ data: { number: "KSC/JE-9", date: "2026-10-31" } }));
  askReason.mockImplementation(async () => null);
});

test("Batal bayar tagihan: pesan halaman berbahasa pengguna (bukan 'payment_void')", () => {
  expect(PESAN_AKSI_TAGIHAN.payment_void).toMatch(/pembayaran dibatalkan/);
  expect(Object.values(PESAN_AKSI_TAGIHAN).join(" ")).not.toMatch(/_/);
});

test("Pembayaran dibatalkan: pil hanya 'Dibatalkan'; alasan & pembatal teks biasa (tidak dikapitalkan, bisa turun baris)", async () => {
  const bill = { id: "vb1", payments: [
    { id: "p1", amount: 1864800, method: "transfer", cash_txn_number: "KSC/CASH-1", voided: true,
      void_reason: "Salah rekening: dibayar dari Kas Toko, seharusnya transfer BCA", voided_by: "Peserta Keuangan 76" },
    { id: "p2", amount: 1864800, method: "transfer", cash_txn_number: "KSC/CASH-2" }] };
  await mount(<VendorBillPayments bill={bill} canVoid onAction={() => {}} />);
  expect(q("vb-payment-voided-p1").textContent.trim()).toBe("Dibatalkan");
  const alasan = q("vb-payment-void-reason-p1");
  expect(alasan.className).not.toMatch(/status-pill/);
  expect(alasan.textContent).toBe("Salah rekening: dibayar dari Kas Toko, seharusnya transfer BCA · Peserta Keuangan 76");
  expect(q("vb-payment-void-p1")).toBeNull();          // yang sudah batal tidak bisa dibatalkan lagi
  expect(q("vb-payment-void-p2")).not.toBeNull();
});

test("Kwitansi dianulir: selisih kurang bayar tidak lagi 'perlu diputus'", async () => {
  const v = { direction: "under", delta: -99999.5, decision_kind: "", reversed_decision_id: "pvd_1" };
  await mount(<div data-testid="sel-batal"><VarianceCell v={v} isVoid /></div>);
  expect(q("sel-batal").textContent).toBe("Ikut dianulir");
  await mount(<div data-testid="sel-hidup"><VarianceCell v={v} /></div>);
  expect(q("sel-hidup").textContent).toMatch(/perlu diputus/);   // kwitansi hidup tanpa keputusan tetap ditandai
});

test("Anulir jurnal manual meminta alasan (menyebut nominal & PT) dan meneruskannya; jurnal dianulir menampilkan alasannya", async () => {
  const je = { id: "j1", number: "KSC/JE-1", source_type: "manual", status: "posted", entity_id: "ent_ksc", total_debit: 1276000,
    total_credit: 1276000, lines: [] };
  const ents = [{ id: "ent_ksc", short_name: "Sukacita" }];
  const onVoid = jest.fn(async () => {});
  await mount(<JournalDetailModal je={je} entities={ents} sourceMeta={() => ({ label: "Manual", tone: "" })}
    onClose={() => {}} onVoid={onVoid} onReverse={async () => {}} />);
  await act(async () => { q("gl-journal-void").click(); });
  await flush();
  expect(onVoid).not.toHaveBeenCalled();                    // dialog dibatalkan
  const o = askReason.mock.calls[0][0];
  expect(o.message).toMatch(/Rp\s?1\.276\.000/);
  expect(o.message).toMatch(/Sukacita/);
  askReason.mockImplementation(async () => "Salah ketik nominal");
  await act(async () => { q("gl-journal-void").click(); });
  await flush();
  expect(onVoid).toHaveBeenCalledWith(je, "Salah ketik nominal");

  for (const r of roots) await act(async () => { r.unmount(); });
  roots = []; document.body.innerHTML = "";
  await mount(<JournalDetailModal je={{ ...je, status: "void", voided_by: "Dewi Manager", void_reason: "Salah ketik nominal" }}
    entities={ents} sourceMeta={() => ({ label: "Manual", tone: "" })} onClose={() => {}} onVoid={onVoid} onReverse={async () => {}} />);
  expect(q("gl-journal-void-note").textContent).toMatch(/Dianulir oleh Dewi Manager.*Salah ketik nominal/);
  expect(q("gl-journal-void")).toBeNull();
});

test("Reklasifikasi Akun Sementara mengirim tanggal jurnal (bawaan hari ini, bisa diubah ke bulan saldonya)", async () => {
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.includes("/gl/suspense")
    ? { balance: -188000, entry_count: 0, items: [] } : {} }));
  const accounts = [{ code: "4-9000", name: "Pendapatan Lain-lain", is_postable: true }];
  await mount(<SuspensePanel accounts={accounts} entities={[{ id: "ent_ksc", short_name: "Sukacita" }]} selectedEntity="ent_ksc"
    onNotice={() => {}} />);
  expect(q("suspense-date")).not.toBeNull();
  const pilih = (tid, v) => {
    const el = q(tid);
    const setter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, "value").set;
    setter.call(el, v);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  };
  await act(async () => { pilih("suspense-target", "4-9000"); });
  await act(async () => { q("suspense-submit").click(); });
  await flush();
  const [url, body] = mockPost.mock.calls[0];
  expect(url).toBe("/api/gl/suspense/reclass");
  expect(body).toMatchObject({ amount: 188000, side: "credit", target_account: "4-9000", entity_id: "ent_ksc", date: todayWib() });
});

test("Kas bayar gaji & setoran gaji menyebut layar asalnya (bukan 'dokumen lain')", () => {
  expect(REF_LABEL.payroll_run).toMatch(/Proses Gaji/);
  expect(REF_LABEL.statutory_remittance).toMatch(/Setoran/);
});
