/**
 * PK-13 (UX-03, FY-17) — konfirmasi seragam untuk aksi uang sekali klik.
 *
 * Isi pesan selalu: `{effect}` lalu baris "Nominal **Rp …** · **{nama lengkap PT}**". Nama PT dari
 * `entityFullById(entities, entityId)`; id PT tidak pernah ditampilkan (tidak dikenal → "Entitas aktif"). Bila dialog
 * ditutup atau Batal ditekan, pemanggil TIDAK mengirim apa pun ke server.
 *
 *   if (!(await confirmMoney({ title, effect, amount, entityId, entities, confirmLabel, testId }))) return;
 *   const alasan = await reasonMoney({ ...sama, reasonLabel: "Alasan penolakan" });
 *   if (alasan === null) return;
 */
import React from "react";
import { askConfirm, askReason, REASON_MIN_LENGTH } from "../services/confirmService";
import { entityFullById } from "./entityLabel";

/** "Rp 12.500.000" — spasi biasa (bukan NBSP) supaya teks bisa dicari/diuji. */
export function rupiahText(value) {
  const n = Math.round(Number(value) || 0);
  const s = Math.abs(n).toLocaleString("id-ID", { maximumFractionDigits: 0 });
  return `${n < 0 ? "-" : ""}Rp ${s}`;
}

export function moneyMessage({ effect, amount, entityId, entities }) {
  const pt = entityFullById(entities, entityId);
  return React.createElement(React.Fragment, null,
    effect,
    React.createElement("br"),
    "Nominal ", React.createElement("strong", null, rupiahText(amount)),
    // Nama lengkap sudah memuat bentuk badan usaha ("PT …", "CV …") — tanpa awalan "PT " supaya tidak tertulis ganda.
    " · ", React.createElement("strong", null, pt));
}

export function confirmMoney({ title, effect, amount, entityId, entities, confirmLabel, danger = false, testId }) {
  return askConfirm({
    title, danger, testId, confirmLabel,
    message: moneyMessage({ effect, amount, entityId, entities }),
  });
}

export function reasonMoney({ title, effect, amount, entityId, entities, confirmLabel, danger = false, testId,
  reasonLabel = "Alasan" }) {
  return askReason({
    title, danger, testId, confirmLabel, reasonLabel, reasonRequired: true, reasonMinLength: REASON_MIN_LENGTH,
    message: moneyMessage({ effect, amount, entityId, entities }),
  });
}

// ── Tagihan pemasok (A1–A5) — kalimat satu tempat supaya daftar, detail, dan notifikasi sama persis ──────────────────
const billAmount = (bill) => (bill?.financials?.grand_total ?? bill?.grand_total ?? 0);

export function confirmBillApprove(bill, entities) {
  return confirmMoney({
    title: `Setujui tagihan ${bill.bill_number || ""}?`.replace("  ", " "),
    effect: `Hutang kepada ${bill.supplier_name || "pemasok"} akan dijurnal. Sesudah disetujui, tagihan hanya bisa `
      + "dibatalkan dengan jurnal pembalik.",
    amount: billAmount(bill), entityId: bill.entity_id, entities,
    confirmLabel: "Setujui & Posting", testId: "vb-approve-confirm",
  });
}

export function askBillReject(bill, entities) {
  return reasonMoney({
    title: `Tolak tagihan ${bill.bill_number || ""}?`,
    effect: `Tagihan dari ${bill.supplier_name || "pemasok"} ditolak dan tidak dijurnal.`,
    amount: billAmount(bill), entityId: bill.entity_id, entities,
    confirmLabel: "Tolak Tagihan", danger: true, testId: "vb-reject-confirm", reasonLabel: "Alasan penolakan",
  });
}

export function askBillCancel(bill, entities) {
  const posted = bill.status === "posted";
  return reasonMoney({
    title: `Batalkan tagihan ${bill.bill_number || ""}?`,
    effect: posted
      ? `Tagihan dari ${bill.supplier_name || "pemasok"} dibatalkan dan jurnal hutangnya dibalik.`
      : `Tagihan dari ${bill.supplier_name || "pemasok"} dibatalkan.`,
    amount: billAmount(bill), entityId: bill.entity_id, entities,
    confirmLabel: "Batalkan Tagihan", danger: true, testId: "vb-cancel-confirm", reasonLabel: "Alasan pembatalan",
  });
}
