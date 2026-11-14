// PK-32 (FX-12..FX-15, K-14) — sisi layar tanpa peramban:
//  · status nota seragam (Menunggu Finance · Terbit · Selesai · Batal; `offset` lama = Selesai), ikon + teks + warna;
//  · kalimat bagian tertangguh dan kelebihan bayar persis spesifikasi;
//  · rincian pesanan: bagian Tagihan tambahan (Nota Debit · Keterangan · Nilai · Jatuh tempo) dan total tagihan = nilai
//    tagihan; sisa tagihan di kepala (PaymentBadge) ikut nilai tagihan.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { NOTE_STATUS, NoteNumber, NoteRecognitionHints, NoteStatusPill, noteStatusLabel } from "../finance/amendments/CreditNoteBadges";
import OrderExtraBilling from "../orders/OrderExtraBilling";
import PaymentBadge from "../../components/PaymentBadge";
import { billingTotal, extraBillingTotal } from "../../utils/orderBilling";
import { AppNavProvider } from "../../context/AppNavContext";
import { setAccessContext } from "../../config/roles";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const teks = (el) => (el?.textContent || "").replace(/\s+/g, " ").trim();
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<AppNavProvider role="admin">{el}</AppNavProvider>); });
  return { host, root };
}
beforeEach(() => setAccessContext({ role: "admin" }));
afterEach(() => { document.body.innerHTML = ""; });

test("status nota seragam: empat label + ikon; `offset` lama dibaca Selesai", async () => {
  expect(Object.fromEntries(Object.entries(NOTE_STATUS).map(([k, v]) => [k, v.label]))).toEqual({
    pending_finance: "Menunggu Finance", issued: "Terbit", posted: "Selesai", void: "Batal" });
  expect(noteStatusLabel("offset")).toBe("Selesai");
  for (const [status, label] of [["pending_finance", "Menunggu Finance"], ["issued", "Terbit"], ["posted", "Selesai"],
    ["void", "Batal"], ["offset", "Selesai"]]) {
    const { host, root } = await mount(<NoteStatusPill note={{ id: "n1", status }} />);
    const pill = q(host, "note-status-n1");
    expect(teks(pill)).toBe(label);
    expect(pill.className).toMatch(/status-pill/);
    expect(pill.querySelector("svg")).not.toBeNull();   // ikon + teks + warna, bukan warna saja
    await act(async () => { root.unmount(); });
  }
});

test("nomor nota + lencana jurnal: gagal tampil, nota lama tanpa penanda tidak", async () => {
  let m = await mount(<NoteNumber note={{ id: "n1", number: "KSC/CN-00007", gl_status: "failed", gl_error: "Akun nonaktif" }} />);
  expect(teks(q(m.host, "note-number-n1"))).toBe("KSC/CN-00007");
  expect(q(m.host, "note-journal-n1").dataset.status).toBe("failed");
  await act(async () => { m.root.unmount(); });
  m = await mount(<NoteNumber note={{ id: "n2", number: "CN-LAMA" }} />);
  expect(q(m.host, "note-journal-n2")).toBeNull();
  await act(async () => { m.root.unmount(); });
});

test("kalimat tertangguh & kelebihan bayar (nota kredit U3)", async () => {
  const note = { id: "n3", kind: "credit_note", deferred_net: 200000, excess_payment: 200000 };
  const { host, root } = await mount(<NoteRecognitionHints note={note} />);
  expect(teks(q(host, "note-deferred-n3"))).toBe("Rp 200.000 belum mengurangi pendapatan karena barangnya belum dikirim.");
  expect(teks(q(host, "note-excess-n3"))).toBe("Kelebihan bayar Rp 200.000 tetap sebagai uang muka pelanggan.");
  await act(async () => { root.unmount(); });
  const m = await mount(<NoteRecognitionHints note={{ id: "n4", deferred_net: 0, excess_payment: 0 }} />);
  expect(q(m.host, "note-hints-n4")).toBeNull();   // tanpa kalimat bila nol
  await act(async () => { m.root.unmount(); });
});

const SO = { id: "so1", grand_total: 1000000, paid_total: 500000, payment_status: "partial",
  extra_billing_lines: [{ id: "x1", debit_note_id: "dn1", debit_note_number: "KSC/DN-00001",
    description: "Koreksi harga", net: 100000, ppn: 0, gross: 100000, due_date: "2026-12-14" }] };

test("rincian pesanan: Tagihan tambahan berkolom Nota Debit · Keterangan · Nilai · Jatuh tempo; total = nilai tagihan", async () => {
  expect(extraBillingTotal(SO)).toBe(100000);
  expect(billingTotal(SO)).toBe(1100000);
  expect(billingTotal({ grand_total: 750000 })).toBe(750000);
  const { host, root } = await mount(<OrderExtraBilling order={SO} />);
  const kepala = [...host.querySelectorAll("thead th")].map(teks);
  expect(kepala).toEqual(["Nota Debit", "Keterangan", "Nilai", "Jatuh tempo"]);
  expect([...q(host, "order-extra-billing-row-dn1").querySelectorAll("td")].map(teks)).toEqual(
    ["KSC/DN-00001", "Koreksi harga", "Rp 100.000", "14/12/2026"]);
  expect(teks(q(host, "order-extra-billing-total"))).toBe("Total tagihan Rp 1.100.000");
  expect(host.querySelector("table").className).toMatch(/data-table head-wrap/);
  await act(async () => { root.unmount(); });
  const m = await mount(<OrderExtraBilling order={{ id: "so2", grand_total: 1000000 }} />);
  expect(q(m.host, "order-extra-billing")).toBeNull();   // tanpa tagihan tambahan → bagian tidak tampil
  await act(async () => { m.root.unmount(); });
});

test("kepala pesanan: sisa tagihan memakai nilai tagihan (grand total + tagihan tambahan)", async () => {
  const { host, root } = await mount(<PaymentBadge order={SO} showRemaining testId="pb" />);
  expect([...q(host, "pb").children].map(teks)).toEqual(["Bayar Sebagian", "sisa Rp 600.000"]);
  await act(async () => { root.unmount(); });
});
