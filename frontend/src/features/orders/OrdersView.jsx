import { useEffect, useMemo, useState } from "react";
import { BarChart2, FileText, Route } from "lucide-react";
import { SearchBox, ListToolbar } from "../../components/ListControls";
import axios, { API } from "../../services/apiClient";
import { formatCurrency } from "../../utils/formatters";
// Keputusan pemilik K-03 (26 Okt) — "Total" dokumen = termasuk PPN; DPP (harga sebelum PPN) = rincian.
import { docDpp, docGrandTotal } from "../../utils/taxBreakdown";
import PaginationBar from "../../components/PaginationBar";
import PageTabs from "../../components/PageTabs";
import ResponsiveTable from "../../components/ResponsiveTable";
import { usePagedList } from "../../hooks/usePagedList";
import useIsMobile from "../../hooks/useIsMobile";
// FASE P6 — kolom Unduh CSV. Badan usaha sengaja TIDAK diikutkan: dokumen pesanan hanya
// menyimpan `entity_id`, dan menampilkan id entitas dilarang (INV-UI-02) — sebuah kolom
// berisi `ent_ksc` tidak berarti apa pun bagi yang membuka berkasnya.
import { qtyDualCsvColumns } from "../../utils/qtyDualCsv";   // FASE U — dua satuan di CSV
import LineFilter from "../../components/LineFilter";   // FASE L
import OrderDashboard from "./OrderDashboard";
import { OrderDetailPanel } from "./OrderDetailPanel";
import SOCompactPanel from "./SOCompactPanel";
import DetailPopup from "../../components/DetailPopup";
// FASE E-8 (E8.14 · US12) — "barang saya sampai mana?" — jawaban gudang dibawa ke layar Pesanan, read-only.
import OrderJourneyPanel from "./OrderJourneyPanel";
import KNSelect from "../../components/KNSelect";
import { scopeSuffix } from "../../utils/entityLabel";
import { useEntityScope } from "../../context/EntityScopeContext";
import { ORDER_STAGES, STATUS_FILTER_LABEL, orderColumns, subStatusOptions } from "./orderListParts";
import { hasPartialBackorder, isBackorderSo } from "./soStatusView";

const CSV_COLUMNS = [
  { key: "number", header: "Nomor" },
  { key: "created_at", header: "Tanggal", type: "date" },
  { key: "customer_name", header: "Pelanggan" },
  { key: "customer_city", header: "Kota" },
  { key: "sales_name", header: "Sales" },
  { header: "Jumlah Item", type: "int", get: (r) => (r.items || []).length },
  // FASE U — dua satuan: gulungan (bisa di-SUM) + ukuran per satuan. Dokumen lama
  // tanpa `qty_rolls` menghasilkan sel KOSONG, bukan 0 (keputusan pemilik).
  ...qtyDualCsvColumns(),
  // K-03 (26 Okt) — dulu "Total (DPP)" berisi nilai BRUTO (sebelum diskon & PPN); kini total dokumen termasuk PPN
  // + kolom rincian DPP (harga sebelum PPN), sama dengan PDF SO & Pusat Dokumen.
  { header: "Total (termasuk PPN)", type: "num", get: (r) => docGrandTotal(r) },
  { header: "DPP (harga sebelum PPN)", type: "num", get: (r) => docDpp(r) },
  { key: "paid_total", header: "Sudah Dibayar", type: "num" },
  { key: "payment_status", header: "Status Bayar" },
  { key: "stage", header: "Tahap" },
  { key: "status", header: "Status" },
  // R5 (keputusan pemilik #2) — Backorder = status Menunggu stok; sisa pendingan SO hidup di tahap lain = kolom sendiri.
  { header: "Backorder", get: (r) => isBackorderSo(r) },
  { header: "Sebagian menunggu stok", get: (r) => hasPartialBackorder(r) },
];
const COLUMNS = orderColumns();

/**
 * OrdersView — Penjualan › Pesanan (SO).
 * Fase 3 · P3 (D-17 + L-01/L-04): tab Dasbor/Daftar = PageTabs (testid tur `tab-dashboard`/`tab-list` tetap);
 * SATU kontrol status = tab tahap (hitungan + nilai Rp, testid `orders-stat-*` pada nilai); kartu pipeline yang
 * bisa diklik dihapus; dropdown "Sub-status" hanya status rinci tahap aktif; daftar = ResponsiveTable (kartu di HP;
 * di HP klik baris langsung membuka rincian lengkap).
 */
export default function OrdersView({
  orders,
  onApprove,
  onConfirm,
  onCancel,
  onGenerateDocument,
  onShowDetail,
  onReleaseReservation,
  onSubmitForApproval,
  onMarkDelivered,
  onIssueTaxInvoice,
  user,
  loading = false,
  focusDoc,
  onClearFocus,
  onOpenDocument,
  onRefresh,
}) {
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [stage, setStage] = useState("all");
  const [subStatus, setSubStatus] = useState("");
  const statusFilter = subStatus || stage;
  // FASE E-3 — empty state WAJIB menyebut badan usaha yang sedang dilihat,
  // supaya "belum ada pesanan" tidak dikira data hilang padahal salah konteks.
  const { selectedEntity, entities } = useEntityScope();
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState("list");
  // Panel kanan punya DUA muka: "Detail & Aksi" dan "Perjalanan Pesanan" (riwayat + sumber pemenuhan).
  const [detailPane, setDetailPane] = useState("detail");
  const [showFullOrder, setShowFullOrder] = useState(false);
  const narrow = useIsMobile(640);

  // ── P2 — DAFTAR pesanan dipaginasi & dicari di SERVER ────────────────────────
  // Tab "Dasbor & Analitik" TETAP memakai prop `orders` (analitik butuh seluruh periode); yang berpindah ke server
  // hanya DAFTARNYA. FASE L — chip lini ikut dikirim ke SERVER (daftar berhalaman; saring klien = data "hilang").
  const [lineFilter, setLineFilter] = useState("");
  const listParams = useMemo(
    () => ({ ...(statusFilter === "all" ? {} : { status: statusFilter }),
             ...(lineFilter ? { line: lineFilter } : {}) }), [statusFilter, lineFilter]);
  const paged = usePagedList("/sales-orders", {
    params: listParams, search: searchQuery, pageSize: 20, enabled: viewMode === "list",
  });
  // Hitungan tab & nilai Rp memakai AGREGAT server supaya angkanya tidak menyusut mengikuti isi halaman.
  const [summary, setSummary] = useState(null);
  useEffect(() => {
    let alive = true;
    axios.get(`${API}/sales-orders/stats/summary`, { params: lineFilter ? { line: lineFilter } : {} })
      .then((r) => { if (alive) setSummary(r.data || null); })
      .catch(() => { if (alive) setSummary(null); });
    return () => { alive = false; };
  }, [paged.total, orders.length, lineFilter]);

  // EPIC6 — deep-link: auto-pilih order saat dinavigasi dari Document Hub.
  useEffect(() => {
    if (focusDoc?.focus_type === "sales_order" && focusDoc?.focus_id) {
      setViewMode("list");
      setStage("all");
      setSubStatus("");
      if (focusDoc.number) setSearchQuery(`"${focusDoc.number}"`);   // tanda kutip = nomor tepat (bukan substring)
      setSelectedOrder(focusDoc.focus_id);
      onClearFocus?.();
    }
  }, [focusDoc]); // eslint-disable-line

  // M16 (pemilik 16 Nov) — panel kanan HANYA untuk pesanan yang tampil (dan tersorot) di daftar. Dulu jatuh ke daftar
  // dasbor sebagai cadangan: sesudah ganti tab/cari/halaman panel masih menceritakan pesanan lain (mis. pesanan batal
  // di samping baris "Selesai · Lunas"), tanpa tanda pesanan mana yang dibuka.
  const sel = selectedOrder ? (paged.items.find((o) => o.id === selectedOrder) || null) : null;
  const filteredOrders = paged.items;   // penyaringan status & pencarian dilakukan SERVER

  const byStatus = summary?.by_status || {};
  const sCnt = (keys) => keys.reduce((n, k) => n + Number(byStatus[k]?.count || 0), 0);
  // K-03 (26 Okt) — nilai tahap = total termasuk PPN (sama dengan kolom daftar); server lama → `total_amount`.
  const stAmt = (v) => Number(v?.grand_total ?? v?.total_amount ?? 0);
  const amtOf = (keys) => (keys.length === 0
    ? Object.values(byStatus).reduce((s, v) => s + stAmt(v), 0)
    : keys.reduce((s, k) => s + stAmt(byStatus[k]), 0));
  const countOf = (st) => (st.key === "all" ? Number(summary?.total_orders ?? paged.total ?? 0) : sCnt(st.statuses));
  // UAT 24 Okt (audit UI tahap 2) — G2-05 · P-04: Backorder = status `waiting_stock` (sama dengan daftar); SO lain
  // yang punya sisa backorder di tahap lain disebut di tooltip.
  // Fase 4 · R5 — server kini menghitung `backorder_count` = waiting_stock (keputusan pemilik #2) dan menyebut SO HIDUP
  // lain ber-baris pendingan di `partial_backorder_count` (SO batal ber-penanda basi tidak lagi ikut). Server lama:
  // selisih `backorder_count` (has_backorder) − waiting_stock seperti sebelumnya.
  const partialBo = summary?.partial_backorder_count != null
    ? Number(summary.partial_backorder_count || 0)
    : Math.max(0, Number(summary?.backorder_count || 0) - sCnt(["waiting_stock"]));
  const backorderHint = partialBo > 0
    ? `Menunggu stok penuh. ${partialBo} SO lain (tahap lain) sebagian masih menunggu stok.` : "";
  const subOptions = subStatusOptions(stage, byStatus);

  /** Sesudah aksi yang mengubah status, HALAMAN yang sedang dibuka ikut dimuat ulang. */
  const refreshBoth = () => { onRefresh?.(); paged.refresh(); };
  const withRefresh = (fn) => (fn
    ? async (...args) => { const r = await fn(...args); paged.refresh(); return r; }
    : fn);
  const pickRow = (order) => {
    if (narrow) { setSelectedOrder(order.id); setShowFullOrder(true); return; }   // HP: langsung rincian lengkap
    setSelectedOrder(order.id === selectedOrder ? null : order.id);
  };

  return (
    <div data-testid="orders-view" className="flex flex-col gap-3">
      <PageTabs testId="orders-mode-tabs" value={viewMode} onChange={setViewMode} ariaLabel="Mode layar Pesanan"
        tabs={[
          { key: "dashboard", label: "Dasbor & Analitik", icon: BarChart2, testId: "tab-dashboard" },
          { key: "list", label: "Daftar Pesanan", icon: FileText, testId: "tab-list" },
        ]} />

      {viewMode === "dashboard" && <OrderDashboard orders={orders} loading={loading} summary={summary} />}

      {viewMode === "list" && (
        <>
          <ListToolbar testId="orders-toolbar">
            <SearchBox value={searchQuery} onChange={setSearchQuery} testId="orders-search-input"
              placeholder='Cari nomor, pelanggan, produk… ("SO-0001" = nomor tepat)' />
            {/* M17 (pemilik 16 Nov) — tab tahap bernilai diganti SATU dropdown "Tahap" (jumlah + nilai, total termasuk
                PPN) di bilah daftar; D-17 tetap: satu kontrol status. */}
            <KNSelect data-testid="orders-stage" aria-label="Tahap pesanan" className="field w-auto"
              value={stage} onValueChange={(k) => { setStage(k); setSubStatus(""); }}
              options={ORDER_STAGES.map((st) => ({
                value: st.key,
                label: `${st.key === "all" ? "Semua tahap" : st.label} (${countOf(st)}) · ${formatCurrency(amtOf(st.statuses))}`,
              }))} />
            {subOptions.length > 0 && (
              <KNSelect data-testid="orders-status-detail" aria-label="Sub-status"
                className="field !py-1 !text-[11px] w-auto"
                value={subStatus} onValueChange={setSubStatus} options={subOptions} />
            )}
            <LineFilter value={lineFilter} onChange={setLineFilter} storageKey="orders"
                        allowed={user?.allowed_line_codes} testId="orders-line-filter" />
            <span className="text-fs-12 text-kn-text-2" data-testid="orders-stage-note">nilai = total termasuk PPN</span>
            {backorderHint && (
              <span className="text-fs-12 text-kn-warning-text" data-testid="orders-backorder-hint">{backorderHint}</span>
            )}
          </ListToolbar>

          {/* M16/pola UI — kolom kanan hanya bila ada pesanan dipilih; tanpa pilihan tabel memakai lebar penuh (dulu kotak
              kosong "Pilih pesanan…" 320 px di samping tabel). */}
          <div className={`grid gap-3 ${sel ? "lg:grid-cols-[1fr_320px]" : ""}`}>
            <section className="section-card min-w-0">
              {/* Audit UI 24 Okt (004) — "Memuat pesanan…" hanya ikut halaman server (bukan muat dasbor global). */}
              <ResponsiveTable testId="orders" columns={COLUMNS} rowKey="id"
                rows={paged.loading ? [] : filteredOrders} loading={paged.loading}
                rowTestId={(o) => `order-card-${o.id}`} onRowClick={pickRow}
                rowClassName={(o) => (selectedOrder === o.id ? "bg-[#EFF4FF]" : "")}
                empty={searchQuery.trim()
                  ? `Tidak ada pesanan yang cocok dengan “${searchQuery.trim()}” ${scopeSuffix(entities, selectedEntity)}.`
                  : statusFilter === "all"
                    ? `Belum ada pesanan aktif ${scopeSuffix(entities, selectedEntity)}.`
                    : `Tidak ada pesanan berstatus “${STATUS_FILTER_LABEL[statusFilter] || statusFilter}” ${scopeSuffix(entities, selectedEntity)}.`}
                footer={!paged.loading && filteredOrders.length > 0 && (
                  <div className="px-3 py-2 border-t border-[#EFF0F2]">
                    <PaginationBar
                      page={paged.page} pageSize={paged.pageSize} total={paged.total}
                      hasMore={paged.hasMore} loading={paged.loading}
                      onPrev={paged.prev} onNext={paged.next} onPageSize={paged.setPageSize}
                      testId="orders-pager" label="pesanan"
                      exportConfig={{ columns: CSV_COLUMNS, rows: filteredOrders,
                        fetchAll: paged.fetchAll, filename: "pesanan-penjualan" }}
                    />
                  </div>
                )} />
            </section>

            {sel ? (
              <div className="grid gap-2 content-start min-w-0 lg:sticky lg:top-2 lg:max-h-[calc(100vh-1rem)] lg:overflow-y-auto"
                data-testid="order-side-pane">
                <div className="flex min-w-0 items-baseline gap-2 px-1" data-testid="order-pane-identity">
                  <span className="font-mono text-fs-13 font-bold text-kn-text">{sel.number}</span>
                  <span className="min-w-0 truncate text-fs-12 text-kn-text-2">{sel.customer_name || ""}</span>
                </div>
                <PageTabs testId="order-pane-switch" value={detailPane} onChange={setDetailPane} ariaLabel="Panel pesanan"
                  tabs={[
                    { key: "detail", label: "Detail & Aksi", icon: FileText, testId: "order-pane-detail" },
                    { key: "journey", label: "Perjalanan Pesanan", icon: Route, testId: "order-pane-journey" },
                  ]} />

                {detailPane === "journey" ? (
                  <OrderJourneyPanel orderId={sel.id} orderNumber={sel.number} />
                ) : (
                  /* UI/UX 2026-06 — panel kanan = ringkasan; detail penuh + aksi di pop-up. */
                  <SOCompactPanel order={sel}
                    onClose={() => setSelectedOrder(null)}
                    onOpenFull={() => setShowFullOrder(true)} />
                )}

                <DetailPopup open={showFullOrder} onClose={() => setShowFullOrder(false)}
                  title={sel.number} subtitle={sel.customer_name} testId="so-detail-popup">
                  <OrderDetailPanel
                    order={sel}
                    user={user}
                    onRefresh={refreshBoth}
                    onApprove={withRefresh(onApprove)}
                    onConfirm={withRefresh(onConfirm)}
                    onCancel={withRefresh(onCancel)}
                    onGenerateDocument={onGenerateDocument}
                    onReleaseReservation={withRefresh(onReleaseReservation)}
                    onSubmitForApproval={withRefresh(onSubmitForApproval)}
                    onMarkDelivered={withRefresh(onMarkDelivered)}
                    onIssueTaxInvoice={withRefresh(onIssueTaxInvoice)}
                    onOpenDocument={onOpenDocument}
                    onClose={() => setShowFullOrder(false)}
                    embedded
                  />
                </DetailPopup>
              </div>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}
