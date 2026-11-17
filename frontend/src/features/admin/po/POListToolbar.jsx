/**
 * POListToolbar — kartu angka + bilah daftar Pesanan Pembelian (pola UI `docs/blueprint/04_POLA_UI.md` §2.A, gelombang
 * Pembelian; diekstrak dari PurchaseOrderManagement supaya berkas induk di bawah batas 500 baris).
 *   · Kartu = saringan cepat ke kunci `PO_TABS` yang sama dengan dropdown status ("Total PO" = kembali ke semua).
 *   · Status bayar = dropdown (dulu deret chip `POPaymentChips`); "Terlambat" = centang (dulu tombol merah buatan).
 *   · Satu baris: cari · status · status bayar · terlambat · lini · jumlah · aksi (+ Buat PO) di ujung kanan.
 * Nilai saringan tetap milik induk dan dikirim ke SERVER (`?status`, `?payment`, `?late`, `?line`).
 */
import { Boxes, CheckCircle2, Clock, ShoppingBag } from "lucide-react";
import KNSelect from "../../../components/KNSelect";
import LineFilter from "../../../components/LineFilter";   // FASE L
import { ListToolbar, MetricRow, SearchInput } from "../../../components/ListPageParts";

export const PO_TABS = [
  { key: "", label: "Semua" },
  { key: "approval", label: "Menunggu Persetujuan", statuses: "waiting_approval" },
  { key: "inbound", label: "Menunggu / Proses Terima", statuses: "pending,receiving,partial" },
  { key: "done", label: "Selesai", statuses: "completed,closed_short" },
  { key: "closed", label: "Ditolak / Batal", statuses: "rejected,cancelled" },
];
// Kunci = `?payment=` server.
const PAYMENT_OPTIONS = [
  { key: "", label: "Semua status bayar" }, { key: "unpaid", label: "Belum Bayar" }, { key: "partial", label: "Sebagian" },
  { key: "paid", label: "Lunas" }, { key: "settled_by_return", label: "Lunas lewat retur" },
];
export const PAYMENT_KEYS = PAYMENT_OPTIONS.map((o) => o.key).filter(Boolean);
const PO_CARDS = [
  { key: "", label: "Total PO", icon: ShoppingBag, hint: "semua status", testId: "po-metric-total" },
  { key: "approval", label: "Menunggu Persetujuan", icon: Clock, testId: "po-metric-approval" },
  { key: "inbound", label: "Menunggu / Proses Terima", icon: Boxes, testId: "po-metric-inbound" },
  { key: "done", label: "Selesai", icon: CheckCircle2, testId: "po-metric-done" },
];
// Dropdown saringan sebaris dengan cari & lini (gaya sama dengan `LineFilter`).
const FILTER_SELECT = "!h-auto !w-auto rounded-lg border border-kn-field-border bg-white !px-2 !py-1.5 text-fs-13";

export default function POListToolbar({ counts, payCounts, total, statusTab, onStatusTab, paymentFilter, onPaymentFilter,
  lateOnly, onLateOnly, search, onSearch, lineFilter, onLineFilter, allowedLines, actions }) {
  const tabCount = (t) => (t.statuses ? t.statuses.split(",").reduce((a, k) => a + (counts[k] || 0), 0) : 0);
  const totalCount = Object.values(counts).reduce((a, b) => a + b, 0);
  // G4-30 — "Semua" = seluruh PO pada lingkup (termasuk Ditolak/Batal), status bayar lain = PO hidup saja.
  const payAll = payCounts.__all ?? Object.values(payCounts).reduce((a, n) => a + (n || 0), 0);
  return (
    <>
      <MetricRow testId="po-stats" items={PO_CARDS.map(({ key, label, icon, hint, testId }) => ({
        label, icon, hint, testId, value: key ? tabCount(PO_TABS.find((t) => t.key === key)) : totalCount,
        active: !!key && statusTab === key,
        onClick: () => onStatusTab(key && statusTab !== key ? key : ""),
      }))} />
      <div className="mt-3">
        <ListToolbar testId="po-toolbar" count={`${total ?? 0} PO`} actions={actions}>
          <SearchInput testId="po-search" placeholder="Cari no. PO / supplier / gudang…" value={search}
            onChange={onSearch} className="min-w-[220px] flex-1 sm:max-w-[320px]" />
          <KNSelect data-testid="po-status-filter" aria-label="Status" className={`${FILTER_SELECT} min-w-[200px]`}
            value={statusTab} onValueChange={(v) => onStatusTab(v || "")}
            options={PO_TABS.map((t) => ({ value: t.key, label: `${t.key ? t.label : "Semua status"} (${t.key ? tabCount(t) : totalCount})` }))} />
          <KNSelect data-testid="po-payment-filter" aria-label="Status bayar" className={`${FILTER_SELECT} min-w-[170px]`}
            value={paymentFilter} onValueChange={(v) => onPaymentFilter(v || "")}
            options={PAYMENT_OPTIONS.map((o) => ({ value: o.key, label: `${o.label} (${o.key ? payCounts[o.key] || 0 : payAll})` }))} />
          <label className="inline-flex cursor-pointer items-center gap-1.5 whitespace-nowrap text-fs-13 text-kn-text"
            title="Hanya PO yang lewat tanggal kirim dijanjikan supplier & masih menunggu barang">
            <input type="checkbox" data-testid="po-filter-late" checked={lateOnly} onChange={(e) => onLateOnly(e.target.checked)} />
            Hanya terlambat
          </label>
          <LineFilter value={lineFilter} onChange={onLineFilter} storageKey="purchase-orders"
                      allowed={allowedLines} testId="po-line-filter" />
        </ListToolbar>
      </div>
    </>
  );
}
