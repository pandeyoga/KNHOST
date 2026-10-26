/**
 * orderListParts — definisi tahap (tab status) & kolom daftar Pesanan Penjualan (fase 3 · P3, D-17 + L-04).
 *
 * D-17 (keputusan pemilik): SATU kontrol filter status = tab tahap (hitungan + nilai Rp per tab); kartu pipeline
 * yang bisa diklik dihapus; dropdown "Sub-status" hanya memuat status rinci tab aktif. Kolom dipakai
 * `ResponsiveTable` (tabel di desktop, kartu di HP 390 px — L-04).
 */
import { formatCurrency } from "../../utils/formatters";
// Keputusan pemilik K-03 (26 Okt) — "Total" dokumen = termasuk PPN; DPP (harga sebelum PPN) = rincian.
import { docDpp, docGrandTotal, docPpn } from "../../utils/taxBreakdown";
import PaymentBadge from "../../components/PaymentBadge";
import EntityBadge from "../../components/EntityBadge";
import { StagePill, SubStatusChips } from "../../components/SoStatusBadges";
import { formatQtyByUnit } from "../../utils/qtyByUnit";
import { hasPartialBackorder, isBackorderSo, visibleSubs } from "./soStatusView";

/** Tahap = tab status. `statuses` = status server di tahap itu (multi-status dikirim berkoma). */
export const ORDER_STAGES = [
  { key: "all", label: "Semua", testKey: "all", statTestId: "orders-stat-total", statuses: [] },
  { key: "reserved,waiting_approval,approved", label: "Dipesan", testKey: "reserved", statuses: ["reserved", "waiting_approval", "approved"] },
  { key: "waiting_stock", label: "Backorder", testKey: "waiting_stock", statuses: ["waiting_stock"] },
  { key: "confirmed,partially_picked,picked", label: "Diproses", testKey: "confirmed", statuses: ["confirmed", "partially_picked", "picked"] },
  { key: "partially_shipped,shipped,dispatched", label: "Dikirim", testKey: "shipped", statuses: ["partially_shipped", "shipped", "dispatched"] },
  { key: "done", label: "Selesai", testKey: "done", statuses: ["done"] },
  { key: "cancelled,expired", label: "Dibatalkan", testKey: "cancelled", statuses: ["cancelled", "expired"] },
];

// Audit UI 24 Okt (004) — pesan daftar kosong dulu menulis kode saringan mentah; kini label tahap / status rinci.
export const STATUS_FILTER_LABEL = {
  "reserved,waiting_approval,approved": "Dipesan",
  waiting_stock: "Backorder",
  "confirmed,partially_picked,picked": "Diproses",
  "partially_shipped,shipped,dispatched": "Dikirim",
  done: "Selesai",
  "cancelled,expired": "Dibatalkan / Kedaluwarsa",
  waiting_approval: "Menunggu Persetujuan",
  reserved: "Dipesan",
  approved: "Disetujui",
  confirmed: "Terkonfirmasi (Ditahan)",
  partially_picked: "Sebagian Diambil",
  picked: "Sudah Diambil (Siap)",
  partially_shipped: "Sebagian Dikirim",
  shipped: "Dikirim",
  dispatched: "Terkirim (lama)",
  cancelled: "Dibatalkan",
  expired: "Kedaluwarsa",
};

/** Opsi dropdown "Sub-status" untuk tahap aktif (kosong bila tahap hanya satu status). */
export function subStatusOptions(stageKey, byStatus = {}) {
  const st = ORDER_STAGES.find((s) => s.key === stageKey);
  if (!st || st.statuses.length < 2) return [];
  const cnt = (k) => Number(byStatus[k]?.count || 0);
  return [
    { value: "", label: `Semua sub-status ${st.label} (${st.statuses.reduce((n, k) => n + cnt(k), 0)})` },
    ...st.statuses.map((k) => ({ value: k, label: `${STATUS_FILTER_LABEL[k] || k} (${cnt(k)})` })),
  ];
}

/** Kolom daftar pesanan. Testid lama baris/sel dipertahankan (tur `order-card-*`, uji K-03). */
export function orderColumns() {
  return [
    { key: "number", header: "Pesanan", mobile: "title", render: (order) => (
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-1.5">
          <span data-testid={`order-number-${order.id}`} className="text-[12px] font-bold text-[#007AFF]">{order.number}</span>
          <EntityBadge entityId={order.entity_id} />
          {/* R5 — Backorder = status Menunggu stok; sisa pendingan di tahap lain = "Sebagian menunggu stok". */}
          {isBackorderSo(order) && (
            <span data-testid={`order-backorder-chip-${order.id}`}
              className="rounded-sm bg-[#FFF1EA] px-1 py-0.5 text-[10px] font-bold uppercase tracking-wide text-[#B23B14]">Backorder</span>
          )}
          {hasPartialBackorder(order) && (
            <span data-testid={`order-partial-stock-chip-${order.id}`} title="Sebagian qty pesanan ini menunggu barang masuk"
              className="rounded-sm bg-[#FFF7EF] px-1 py-0.5 text-[10px] font-semibold text-[#8C4A00]">Sebagian menunggu stok</span>
          )}
          {order.has_sample && (
            <span data-testid={`order-sample-chip-${order.id}`}
              className="rounded-sm bg-[#FFF3D6] px-1 py-0.5 text-[10px] font-bold uppercase tracking-wide text-[#9A5B00]">Sample</span>
          )}
        </div>
        <span className="block text-[11px] font-normal text-[#6B6B73]">
          {(order.items || []).length} item · <PaymentBadge order={order} showRemaining testId={`order-payment-${order.id}`} />
        </span>
      </div>
    ) },
    { key: "customer", header: "Pelanggan", mobile: "subtitle", render: (order) => (
      <span data-testid={`order-customer-${order.id}`} className="text-[11px] text-[#3C3C43]">{order.customer_name}</span>
    ) },
    { key: "qty", header: "Qty Pesan", priority: 2, render: (order) => {
      const its = order.items || [];
      const units = [...new Set(its.map((it) => it.unit).filter(Boolean))];
      return (
        <div className="text-[11px] tabular-nums" data-testid={`order-qty-cell-${order.id}`}>
          <p className="font-semibold" data-testid={`order-qty-${order.id}`}>{formatQtyByUnit(its)}</p>
          <p className="text-[10px] text-[#6B6B73]">{its.length} item{units.length > 1 ? " · campuran" : ""}</p>
        </div>
      );
    } },
    { key: "total", align: "right", priority: 1, mobileLabel: "Total (termasuk PPN)",
      header: (
        <span data-testid="orders-col-total" title="Total dokumen termasuk PPN (setelah diskon). Baris kecil = DPP (harga sebelum PPN); rincian lengkap di detail pesanan.">Total (termasuk PPN)</span>
      ),
      render: (order) => (
        <div className="text-right tabular-nums">
          <p data-testid={`order-total-${order.id}`} className="text-[11.5px] font-bold">{formatCurrency(docGrandTotal(order))}</p>
          {docPpn(order) > 0 && (
            <p data-testid={`order-dpp-${order.id}`} className="text-[10px] text-[#6B6B73]">DPP {formatCurrency(docDpp(order))}</p>
          )}
        </div>
      ) },
    { key: "date", header: "Tanggal", priority: 3, render: (order) => (
      <span className="text-[10.5px] text-[#6B6B73]" data-testid={`order-date-${order.id}`}>
        {order.created_at ? new Date(order.created_at).toLocaleDateString("id-ID", { day: "2-digit", month: "short" }) : "—"}
      </span>
    ) },
    { key: "stage", header: "Tahap", mobile: "badge", render: (order) => (
      <div className="flex flex-col items-start gap-0.5 min-w-0">
        <StagePill order={order} testId={`order-status-${order.id}`} />
        <SubStatusChips subs={visibleSubs(order)} testIdPrefix={`order-row-substatus-${order.id}`} />
      </div>
    ) },
  ];
}
