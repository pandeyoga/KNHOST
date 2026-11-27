/**
 * F1 — kwitansi dari mutasi bank (rancangan `2026-11-27-kwitansi-otomatis-mutasi` §5.5, §5.6, §5.8). Pemanggil rute
 * atomik Rekonsiliasi (`backend/routers/bank_reconciliation.py`); semua tulis lewat `moneyPost` (kunci idempotensi dari
 * `useIntentKey` milik layar — kirim ulang sesudah jaringan putus diputar ulang server, bukan kwitansi kedua).
 *  · `receiptFromLine` — `POST /bank-reconciliation/lines/{id}/receipt` (izin `cash.create` + `ar_receipt.create`;
 *    `payment_report.decide` bila membawa `payment_report_id`). SATU permintaan: klaim baris → kwitansi (atau Terima
 *    laporan bayar bersama mutasi) → tautan. Nominal isian WAJIB = nominal mutasi (R9: beda ≥ Rp 1 → 400 berkalimat);
 *    rekening, tanggal, PT diisi server dari mutasi. → `{receipt, line, released_order_ids}`.
 *  · `voidLineReceipt` — `POST /bank-reconciliation/lines/{id}/void-receipt` `{reason}` (izin `ar_receipt.void` +
 *    `cash.create`; alasan ≥ 5 huruf). Hanya kwitansi yang LAHIR dari mutasi itu. → `{order_released, peringatan, …}`.
 */
import { API } from "../../../services/apiClient";
import { moneyPost } from "../../../utils/moneyRequest";
import { formatCurrency } from "../../../utils/formatters";

/** Panjang minimum alasan batal (sama dengan server `ALASAN_BATAL_MIN` dan K-14). */
export const ALASAN_BATAL_MIN = 5;

export const receiptFromLine = (lineId, payload, idemKey) =>
  moneyPost(`${API}/bank-reconciliation/lines/${lineId}/receipt`, payload, idemKey).then((r) => r.data);

export const voidLineReceipt = (lineId, reason, idemKey) =>
  moneyPost(`${API}/bank-reconciliation/lines/${lineId}/void-receipt`, { reason }, idemKey).then((r) => r.data);

/**
 * Baris tercocok yang kwitansinya LAHIR dari mutasi itu (ketetapan R8 — kunci = sumber kwitansi, bukan `match_type`):
 * otomatis jalur B/C (`match_type` `auto_receipt`), atau dicatat manusia dari mutasi (`f1.status` `manual`). Jalur A
 * (mesin menautkan kwitansi yang SUDAH ada) bukan kwitansi dari mutasi — server menolaknya (409). Server tetap penentu.
 */
export function kwitansiDariMutasi(line) {
  if (!line || line.status !== "matched") return false;
  if (line.match_type === "auto_receipt") return true;
  const f1 = line.f1 || {};
  if (!f1.receipt_id) return false;
  return f1.status === "manual" || (f1.status === "otomatis" && f1.jalur !== "A");
}

/** Kalimat jumlah F1 untuk pesan sukses impor / "Cocokkan otomatis"; "" bila tidak ada kwitansi otomatis maupun kartu. */
export function ringkasF1(d) {
  const n = Number(d?.kwitansi_otomatis) || 0;
  const m = Number(d?.kartu) || 0;
  if (!n && !m) return "";
  const bagian = [];
  if (n) bagian.push(`${n} kwitansi otomatis (${formatCurrency(Number(d?.nilai_otomatis) || 0)})`);
  if (m) bagian.push(`${m} perlu dicek di Meja Keuangan`);
  return ` Mutasi berkode bayar: ${bagian.join(", ")}.`;
}
