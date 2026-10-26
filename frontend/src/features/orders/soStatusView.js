/**
 * UAT 24 Okt (audit UI tahap 2) — bantu tampilan status SO untuk layar Penjualan (desktop & HP).
 *  - visibleSubs : sub-status yang labelnya sama dengan tahap tidak diulang ("Dibatalkan · Dibatalkan").
 *  - isClosedSo  : SO batal/kedaluwarsa — alokasi, status bayar & progres tidak relevan lagi.
 *  - lotModeLabel / lotSelectionLabel : kode kebijakan lot ("prefer_single", "fefo") → kata Indonesia.
 *  - allocationExplain : penjelasan alokasi dari server diawali qty bertitik ("1.09 dari Lot …") → "1,09 meter dari Lot …".
 */
import { getStage, getSubStatus, stageMeta, subStatusLabel } from "../../utils/soStatus";
import { formatQty } from "../../utils/formatters";

export function visibleSubs(order) {
  const stage = String(stageMeta(getStage(order)).label || "").toLowerCase();
  return (getSubStatus(order) || []).filter((k) => String(subStatusLabel(k)).toLowerCase() !== stage);
}

export const isClosedSo = (order) => ["cancelled", "expired"].includes(order?.status);

/**
 * Fase 4 · R5 (keputusan pemilik #2, 26 Okt) — "Backorder" di layar Pesanan = SO berstatus Menunggu stok SAJA (tab,
 * kartu, `backorder_count` server). `has_backorder` tetap penanda BARIS pendingan untuk pemenuhan; pada SO hidup di
 * tahap lain ia disebut "sebagian menunggu stok" (bukan Backorder). SO tutup — batal/kedaluwarsa/selesai/terkirim —
 * mengabaikan penanda basi itu (sama dengan `alert_ops_service.SO_CLOSED_STATUSES`).
 */
const SO_STOCK_CLOSED = ["cancelled", "expired", "rejected", "void", "done", "delivered", "completed", "closed", "shipped", "dispatched"];
export const isBackorderSo = (order) => order?.status === "waiting_stock";
export const hasPartialBackorder = (order) => Boolean(order?.has_backorder) && !isBackorderSo(order)
  && !SO_STOCK_CLOSED.includes(order?.status);

const LOT_MODE = { single: "Satu lot", mixed: "Campur lot", prefer_single: "Utamakan satu lot", strict_single: "Wajib satu lot", any: "Bebas" };
const LOT_SELECTION = { fifo: "FIFO (masuk pertama)", fefo: "FEFO (kedaluwarsa pertama)", lifo: "LIFO", manual: "Manual" };
export const lotModeLabel = (v) => LOT_MODE[String(v || "").toLowerCase()] || String(v || "").replaceAll("_", " ");
export const lotSelectionLabel = (v) => LOT_SELECTION[String(v || "").toLowerCase()] || String(v || "").toUpperCase();

export function allocationExplain(text, unit = "") {
  if (!text) return text;
  return String(text).replace(/^(\d+(?:\.\d+)?)(?=\s+dari\s)/, (m) => `${formatQty(Number(m))}${unit ? ` ${unit}` : ""}`);
}
