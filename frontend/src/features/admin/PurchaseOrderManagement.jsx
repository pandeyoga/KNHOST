import { useEffect, useMemo, useState } from "react";
import { Plus, Boxes, ShoppingBag, Clock, CheckCircle2 } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { parseDecimal } from "../../utils/decimalInput";
import { lateState } from "./po/poUtils";
import POPaymentChips from "./po/POPaymentChips";
import POCreateForm from "./po/POCreateForm";
import { POBuyerEntitySwitch, takePODraft } from "./po/POBuyerEntitySwitch";
import PODetailPanel from "./po/PODetailPanel";
import POCompactPanel from "./po/POCompactPanel";
import POListTable from "./po/POListTable";
import POCreateMenu from "./po/POCreateMenu";
import DetailModal from "../../components/DetailModal";
import POAmendModal from "./po/POAmendModal";
import MakloonOrderCreateModal from "../purchasing/MakloonOrderCreateModal";
import ConfirmModal from "../../components/ConfirmModal";
import FormModal from "../../components/FormModal";
import ErrorNotice from "../../components/ErrorNotice";
import LineFilter from "../../components/LineFilter";   // FASE L
import { PageHeader, MetricRow, SearchBox, StatusTabs } from "../../components/ListPageParts";
import PaginationBar from "../../components/PaginationBar";
import { usePagedList } from "../../hooks/usePagedList";
import { can } from "../../config/roles";

// FASE P6 — kolom Unduh CSV (mengikuti kolom tabel + nominal yang di layar tampil kecil
// di bawah nama supplier).
import { qtyDualCsvColumns } from "../../utils/qtyDualCsv";   // FASE U — dua satuan di CSV

const CSV_COLUMNS = [
  { key: "po_number", header: "Nomor PO" },
  { header: "Tanggal", type: "date", get: (r) => r.order_date || r.created_at },
  { key: "supplier_name", header: "Supplier" },
  { key: "warehouse_name", header: "Gudang" },
  { header: "Jumlah Item", type: "int", get: (r) => r.items?.length || 0 },
  // FASE U — dua satuan, DUA pasang: yang DIPESAN (diketik saat memesan) dan yang
  // benar-benar DITERIMA (turunan dari roll yang lahir di gudang). Dipisah supaya
  // selisihnya terlihat di lembar kerja tanpa harus membuka dokumennya satu-satu.
  ...qtyDualCsvColumns({ rollHeader: "Roll Dipesan", measureHeader: "Jumlah Dipesan" }),
  ...qtyDualCsvColumns({ rollField: "received_rolls", rollHeader: "Roll Diterima",
    measureHeader: "Jumlah Diterima", measureFields: ["received_qty"] }),
  { header: "Total", type: "num", get: (r) => Number(r.grand_total ?? r.total_amount ?? 0) },
  { key: "status", header: "Status" },
  { header: "Tgl Kirim Diharap", get: (r) => String(r.expected_delivery_date || "").slice(0, 10) },
  { header: "Telat (hari)", type: "int", get: (r) => lateState(r)?.days || "" },
];

/**
 * PurchaseOrderManagement
 *
 * Manage Purchase Orders untuk inbound receiving workflow.
 * Create PO → Auto-create inbound tasks → Staff scan & receive.
 *
 * Sub-komponen (colocated di po/):
 *   - POCreateForm    — form buat PO baru
 *   - PODetailPanel   — panel detail PO dipilih
 *   - poUtils         — getStatusBadge helper
 */
const PO_TABS = [
  { key: "", label: "Semua" },
  { key: "approval", label: "Menunggu Persetujuan", statuses: "waiting_approval" },
  { key: "inbound", label: "Menunggu / Proses Terima", statuses: "pending,receiving,partial" },
  { key: "done", label: "Selesai", statuses: "completed,closed_short" },
  { key: "closed", label: "Ditolak / Batal", statuses: "rejected,cancelled" },
];
// G4-30 — PO mati tidak dihitung/ditampilkan di chip status bayar.
const DEAD_PO_STATUSES = ["rejected", "cancelled"];
const LIVE_PO_STATUSES = PO_TABS.filter((t) => t.statuses && t.key !== "closed").map((t) => t.statuses).join(",");
const PAYMENT_KEYS = ["unpaid", "partial", "paid", "settled_by_return"];

export default function PurchaseOrderManagement({ user, selectedEntity, onApprovePO, focusDoc, onClearFocus, onOpenDocument, onSwitchEntity, buyerEntities = [] }) {
  const [products, setProducts] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [search, setSearch] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [makloonMode, setMakloonMode] = useState(null);  // null | "buy_process" | "process_only"
  const [selectedPO, setSelectedPO] = useState(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [confirm, setConfirm] = useState(null); // { title, message, confirmLabel, danger, withReason, onConfirm }
  const [amendPO, setAmendPO] = useState(null);  // Phase 7.2 — PO yang sedang direvisi
  const [amending, setAmending] = useState(false);

  // P2 — paginasi server-side + pencarian (po_number / supplier).
  // FASE L — chip lini disaring di SERVER (daftar berhalaman).
  const [lineFilter, setLineFilter] = useState("");
  const [lateOnly, setLateOnly] = useState(false);   // chip "Terlambat" — disaring SERVER
  const [statusTab, setStatusTab] = useState("");
  const [paymentFilter, setPaymentFilter] = useState("");   // chip status bayar — disaring SERVER
  const [counts, setCounts] = useState({});
  const [payCounts, setPayCounts] = useState({});
  const poParams = useMemo(() => ({
    ...(lineFilter ? { line: lineFilter } : {}),
    ...(lateOnly ? { late: 1 } : {}),
    ...(statusTab ? { status: PO_TABS.find((t) => t.key === statusTab)?.statuses }
      // UAT 24 Okt (audit UI tahap 2) — G4-30: chip status bayar hanya untuk PO HIDUP (PO Ditolak/Batal
      // bukan "Belum Bayar"); tab "Ditolak / Batal" tetap bisa dipilih bersama chip.
      : paymentFilter ? { status: LIVE_PO_STATUSES } : {}),
    ...(paymentFilter ? { payment: paymentFilter } : {}),
  }), [lineFilter, lateOnly, statusTab, paymentFilter]);
  const paged = usePagedList("/purchase-orders", { pageSize: 20, search, params: poParams });
  const pos = paged.items;
  const loading = paged.loading;
  const fetchPOs = paged.refresh;
  useEffect(() => {
    const params = { ...(lineFilter ? { line: lineFilter } : {}), ...(lateOnly ? { late: 1 } : {}), ...(search ? { q: search } : {}),
      ...(paymentFilter ? { payment: paymentFilter } : {}) };
    axios.get(`${API}/purchase-orders/status-counts`, { params })
      .then((r) => { setCounts(r.data?.by_status || {}); }).catch(() => {});
    // G4-30 — hitungan chip bayar dari PO hidup saja: `by_payment` server ikut menghitung PO Ditolak/Batal
    // (data acuan: "Belum Bayar 30" = 24 selesai + 2 menunggu + 4 BATAL). Per chip diambil `by_status`
    // lalu status mati dikurangkan (sampai endpoint menyediakan hitungan ini — lihat laporan G4).
    const base = { ...params }; delete base.payment;
    Promise.all(["", ...PAYMENT_KEYS].map((k) => axios.get(`${API}/purchase-orders/status-counts`, { params: k ? { ...base, payment: k } : base })
      .then((r) => [k || "__all", k ? Object.entries(r.data?.by_status || {}).reduce((a, [s, n]) => a + (DEAD_PO_STATUSES.includes(s) ? 0 : n || 0), 0) : (r.data?.total || 0)])
      .catch(() => [k || "__all", 0])))
      .then((pairs) => setPayCounts(Object.fromEntries(pairs)));
  }, [lineFilter, lateOnly, search, pos, selectedEntity, paymentFilter]);
  const tabCount = (t) => (t.statuses ? t.statuses.split(",").reduce((a, k) => a + (counts[k] || 0), 0) : 0);

  const emptyForm = {
    supplier_id: "", supplier_name: "", supplier_contact: "", warehouse_id: "", ship_to_site_id: "",
    items: [], expected_delivery_date: "", notes: "",
    order_discount_percent: 0, tax_mode: "",   // P0-1 — diskon order + mode PPN Masukan
    budget_dimension: "account", budget_key: "",  // R6.3 — tag anggaran (opsional)
    created_by: user?.name || "Admin",
  };
  const [formData, setFormData] = useState(emptyForm);
  // W2-REQ-05 — pulihkan draft PO setelah ganti entitas pembeli dari form (gudang/supplier dipilih ulang per entitas).
  useEffect(() => {
    const d = takePODraft();
    if (d?.formData && d.to === selectedEntity) {
      setFormData({ ...emptyForm, ...d.formData, warehouse_id: "", ship_to_site_id: "" });
      setShowCreateForm(true);
      setNotice("Draft PO dipindah ke entitas pembeli baru — periksa lokasi kirim & pemasok.");
    }
  }, []); // eslint-disable-line
  // Fase A · PS-09/D-19 — `expected_grade` WAJIB dipilih user (tidak ada default).
  // FASE U — dua satuan: `qty_rolls` (jumlah gulungan yang DIPESAN — rencana) dan
  // `unit_factor` (panjang 1 panel PADA PESANAN INI; hanya untuk satuan bertanda
  // "faktor per dokumen" di master satuan — server menolak yang lain).
  const [newItem, setNewItem] = useState({ product_id: "", quantity: 0, unit: "meter", price: 0, discount_percent: 0, expected_grade: "", qty_rolls: "", unit_factor: "" });

  // Master data (produk/gudang/supplier) hanya untuk form Buat PO/makloon — peran finance
  // tidak punya menu Buat, jadi tidak perlu memanggil endpoint yang memang 403 baginya.
  const canCreate = can(user?.permissions, "purchase_order", "create");   // Sisir gerbang peran (2026-10-20) — POST /purchase-orders
  useEffect(() => { if (canCreate) fetchMasterData(); }, [canCreate]); // eslint-disable-line

  const fetchMasterData = async () => {
    try {
      const [pRes, wRes, sRes] = await Promise.all([
        axios.get(`${API}/products`).catch(() => ({ data: [] })),
        axios.get(`${API}/warehouses`).catch(() => ({ data: [] })),
        axios.get(`${API}/suppliers`).catch(() => ({ data: [] })),
      ]);
      setProducts(Array.isArray(pRes.data) ? pRes.data : []);
      setWarehouses(Array.isArray(wRes.data) ? wRes.data : []);
      setSuppliers(Array.isArray(sRes.data) ? sRes.data : []);
    } catch (e) { /* non-blocking */ }
  };

  const handleAddItem = () => {
    if (!newItem.product_id || !(parseDecimal(newItem.quantity) > 0)) {
      setError("Pilih produk dan masukkan qty yang valid (> 0)."); return;
    }
    // Fase A · D-19 — grade yang diharapkan WAJIB dipilih (server juga menolak).
    if (!newItem.expected_grade) {
      setError("Pilih Grade yang diharapkan untuk item ini (tidak ada nilai default)."); return;
    }
    setError("");
    const product = products.find((p) => p.id === newItem.product_id);
    setFormData({
      ...formData,
      items: [...formData.items, {
        ...newItem,
        price: parseDecimal(newItem.price) > 0 ? newItem.price : product?.price || 0,
        discount_percent: Number(newItem.discount_percent) || 0,
        // FASE U — kosong berarti "tidak menyebut jumlah roll" (null), BUKAN 0 roll.
        qty_rolls: newItem.qty_rolls === "" || newItem.qty_rolls === null
          ? null : Math.max(0, parseInt(newItem.qty_rolls, 10) || 0),
        unit_factor: newItem.unit_factor === "" ? null : parseDecimal(newItem.unit_factor),
        unit_factor_to: newItem.unit_factor ? (product?.base_unit || "yard") : "",
      }],
    });
    setNewItem({ product_id: "", quantity: 0, unit: "meter", price: 0, discount_percent: 0, expected_grade: "" });
  };

  const handleRemoveItem = (index) => {
    setFormData({ ...formData, items: formData.items.filter((_, i) => i !== index) });
  };

  const handleCreatePO = async () => {
    // UAT 24 Okt (P9) — PO dikirim ke LOKASI; gudang penerimaan diturunkan server.
    if (!formData.supplier_name || !formData.ship_to_site_id) {
      setError("Nama supplier dan lokasi kirim wajib diisi."); return;
    }
    if (formData.items.length === 0) {
      setError("Tambahkan minimal 1 item."); return;
    }
    setError("");
    setCreating(true);
    try {
      const res = await axios.post(`${API}/purchase-orders`, formData);
      const po = res.data;
      // R6.3 — tampilkan peringatan anggaran (mode WARN) bila ada.
      const bWarn = (po.budget_check?.warnings || []).join(" · ");
      setNotice(`${po.approval_required
        ? `Purchase Order ${po.po_number} dibuat. Menunggu APPROVAL role '${po.required_approval_role}' sebelum inbound task dibuat.`
        : `Purchase Order ${po.po_number} dibuat & inbound task otomatis dibuat.`}${bWarn ? ` ⚠️ Anggaran: ${bWarn}` : ""}`);
      setShowCreateForm(false);
      setFormData(emptyForm);
      fetchPOs();
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal membuat PO.");
    } finally {
      setCreating(false);
    }
  };

  const handleViewDetail = async (poId) => {
    try {
      const res = await axios.get(`${API}/purchase-orders/${poId}`);
      setSelectedPO(res.data);
    } catch {
      setError("Gagal memuat detail PO.");
    }
  };

  // EPIC6 — deep-link: auto-buka detail PO saat dinavigasi dari Document Hub.
  useEffect(() => {
    if (focusDoc?.focus_type === "purchase_order" && focusDoc?.focus_id) {
      handleViewDetail(focusDoc.focus_id);
      onClearFocus?.();
    }
  }, [focusDoc]); // eslint-disable-line

  const handleCancelPO = (poId) => {
    const po = pos.find((p) => p.id === poId);
    setConfirm({
      title: "Batalkan Pesanan Pembelian",
      message: `Yakin membatalkan ${po?.po_number || "PO ini"}? Tindakan ini tidak dapat dibatalkan.`,
      confirmLabel: "Batalkan PO",
      danger: true,
      onConfirm: async () => {
        try {
          await axios.post(`${API}/purchase-orders/${poId}/cancel`);
          setNotice(`${po?.po_number || "PO"} berhasil dibatalkan.`);
          setConfirm(null);
          await fetchPOs();
          setSelectedPO(null);
        } catch (e) {
          setError(e.response?.data?.detail || "Gagal membatalkan PO.");
          setConfirm(null);
        }
      },
    });
  };

  const handleApprovePO = async (poId) => {
    if (!onApprovePO) return;
    const result = await onApprovePO(poId);
    if (result) {
      // Rantai approval bisa bertingkat — jangan bilang "inbound task dibuat"
      // sebelum SELURUH tingkat setuju (dulu tingkat 1 dari 2 pun dilaporkan selesai).
      const po = result?.data || result;
      const stillWaiting = (po?.status || "") === "waiting_approval";
      const chain = Array.isArray(po?.approval_chain) ? po.approval_chain : [];
      const approvedLv = chain.filter((l) => l.status === "approved").length;
      setNotice(stillWaiting
        ? `Disetujui tingkat ${approvedLv || 1} dari ${chain.length || "?"} — masih menunggu peran ${(po?.required_approval_role || "berikutnya").toUpperCase()}.`
        : "PO disetujui penuh. Inbound task dibuat.");
      await fetchPOs(); await handleViewDetail(poId);
    }
  };

  const handleCloseShort = (poId) => {
    const po = pos.find((p) => p.id === poId);
    setConfirm({
      title: "Tutup PO (Kurang Terima)",
      message: `Tutup ${po?.po_number || "PO ini"}? Tugas barang masuk yang masih terbuka akan dibatalkan.`,
      confirmLabel: "Tutup PO",
      danger: false,
      withReason: true,
      reasonLabel: "Alasan tutup-kurang",
      reasonPlaceholder: "Mis. sisa barang tidak akan dikirim supplier.",
      onConfirm: async (reason) => {
        try {
          await axios.post(`${API}/purchase-orders/${poId}/close`, { reason });
          setNotice(`${po?.po_number || "PO"} ditutup (kurang terima).`);
          setConfirm(null);
          await fetchPOs();
          await handleViewDetail(poId);
        } catch (e) {
          setError(e.response?.data?.detail || "Gagal menutup PO.");
          setConfirm(null);
        }
      },
    });
  };

  const handleCloseForm = () => {
    setShowCreateForm(false);
    setFormData(emptyForm);
  };

  // Phase 7.2 — submit amandemen PO (re-approval penuh di backend).
  const handleSubmitAmend = async (payload) => {
    if (!amendPO) return;
    setAmending(true);
    try {
      const res = await axios.post(`${API}/purchase-orders/${amendPO.id}/amend`, payload);
      const po = res.data;
      setNotice(po.approval_required
        ? `PO ${po.po_number} direvisi (v${po.version}). Menunggu APPROVAL role '${po.required_approval_role}' sebelum inbound task dibuat.`
        : `PO ${po.po_number} direvisi (v${po.version}). Inbound task diperbarui otomatis.`);
      setAmendPO(null);
      await fetchPOs();
      await handleViewDetail(po.id);
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal merevisi PO.");
    } finally {
      setAmending(false);
    }
  };

  return (
    <div data-testid="po-management-panel" className="view-container">
      {notice && <div className="notice-bar success" data-testid="po-mgmt-notice"><span>{notice}</span><button onClick={() => setNotice("")}>×</button></div>}
      {error && !showCreateForm && <ErrorNotice message={error || paged.error} onRetry={fetchPOs} onDismiss={() => setError("")} testId="po-mgmt-error" />}

      <PageHeader icon={ShoppingBag} title={<span data-testid="panel-title">Pesanan Pembelian (PO)</span>}
        subtitle="Pesanan ke supplier — dari persetujuan, kedatangan barang, sampai penagihan (3-way matching)."
        actions={canCreate ? (
          <POCreateMenu onPick={(mode) => {
            if (mode === "finished") { setMakloonMode(null); setShowCreateForm(true); }
            else { setShowCreateForm(false); setMakloonMode(mode); }
          }} />
        ) : null} />

      <MetricRow testId="po-stats" items={[
        { label: "Total PO", value: Object.values(counts).reduce((a, b) => a + b, 0), icon: ShoppingBag, hint: "semua status", testId: "po-metric-total" },
        { label: "Menunggu Persetujuan", value: counts.waiting_approval || 0, icon: Clock, testId: "po-metric-approval" },
        { label: "Menunggu / Proses Terima", value: (counts.pending || 0) + (counts.receiving || 0) + (counts.partial || 0), icon: Boxes, testId: "po-metric-inbound" },
        { label: "Selesai", value: (counts.completed || 0) + (counts.closed_short || 0), icon: CheckCircle2, testId: "po-metric-done" },
      ]} />

      <SearchBox value={search} onChange={setSearch} testId="po-search" placeholder="Cari no. PO / supplier / gudang…">
        <button data-testid="po-filter-late" onClick={() => setLateOnly((v) => !v)}
          title="Hanya PO yang lewat tanggal kirim dijanjikan supplier & masih menunggu barang"
          className={`flex items-center gap-1 rounded-lg px-3 py-1.5 text-[12px] font-semibold transition-colors ${
            lateOnly ? "bg-[#C0341D] text-white" : "border border-red-200 bg-red-50 text-red-600 hover:bg-red-100"}`}>
          <Clock size={13} /> Terlambat
        </button>
        <LineFilter value={lineFilter} onChange={setLineFilter} storageKey="purchase-orders"
                    allowed={user?.allowed_line_codes} testId="po-line-filter" />
      </SearchBox>
      <POPaymentChips value={paymentFilter} onChange={setPaymentFilter} counts={payCounts} allCount={payCounts.__all ?? null} />
      <StatusTabs value={statusTab} onChange={setStatusTab} testId={(k) => `po-tab-${k || "all"}`}
        tabs={PO_TABS.map((t) => ({ ...t, count: tabCount(t) }))} />

      {/* Create Form */}
      {/* FASE P5 — form Buat PO menjadi POP-UP: daftar PO di belakang tetap terlihat.
          Dulu kartunya menyelip di tengah halaman dan mendorong tabel PO ke bawah
          lipatan, sehingga pengguna sering tidak sadar formnya sudah terbuka. */}
      <FormModal
        open={showCreateForm}
        onClose={handleCloseForm}
        title="Buat Pesanan Pembelian Baru"
        subtitle="Pilih pemasok & gudang tujuan, lalu tambahkan barang yang dibeli"
        icon={Plus}
        size="xl"
        testId="po-create-modal"
      >
        <POCreateForm
          variant="modal"
          formData={formData} setFormData={setFormData}
          newItem={newItem} setNewItem={setNewItem}
          products={products} warehouses={warehouses} suppliers={suppliers}
          submitting={creating} error={showCreateForm ? error : ""}
          onSubmit={handleCreatePO} onCancel={handleCloseForm}
          onAddItem={handleAddItem} onRemoveItem={handleRemoveItem}
          buyerSlot={<POBuyerEntitySwitch selectedEntity={selectedEntity} entities={buyerEntities}
            formData={formData} onSwitch={onSwitchEntity} />}
        />
      </FormModal>

      {/* Fase 3 · P5 — D-18 / L-06: daftar PO LEBAR PENUH; klik baris = SATU pop-up rincian. Dulu panel kanan
          360 px kosong ("Pilih PO…") + tombol "Lihat detail lengkap" ke pop-up kedua (dua tingkat rincian). */}
      <div className="section-card">
        <POListTable rows={pos} loading={loading} selectedId={selectedPO?.id}
          onOpen={handleViewDetail}
          emptyText={paymentFilter && !lateOnly ? "Tidak ada PO dengan status bayar ini." : lateOnly ? "Tidak ada PO terlambat — semua kiriman masih dalam janji supplier. 🎉" : "Belum ada Pesanan Pembelian"}
          footer={(
            <div className="px-3 py-2 border-t border-[#EFF0F2]">
              <PaginationBar
                testId="po-pager" label="PO"
                page={paged.page} pageSize={paged.pageSize} total={paged.total}
                hasMore={paged.hasMore} loading={paged.loading}
                onPrev={paged.prev} onNext={paged.next} onPageSize={paged.setPageSize}
                exportConfig={{ columns: CSV_COLUMNS, rows: pos, fetchAll: paged.fetchAll,
                  filename: "pesanan-pembelian" }}
              />
            </div>
          )} />
      </div>

      {/* Satu pop-up: kepala ringkas + aksi lifecycle (POCompactPanel) berdampingan dengan isi lengkap
          (PODetailPanel: item, pajak, penagihan, timeline, referensi). Di HP layar penuh, ringkasan di atas. */}
      {selectedPO && (
        <DetailModal onClose={() => setSelectedPO(null)} size="xl" framed
          label={`Rincian ${selectedPO.po_number || "PO"}`} testId="po-detail-popup">
          {/* Galat aksi (setujui/batal/tutup) tampil DI pop-up — bilah halaman tertutup lapisan ini. */}
          {error && <div className="mb-2"><ErrorNotice message={error} onDismiss={() => setError("")} testId="po-detail-error" /></div>}
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start">
            <div className="lg:order-2 lg:sticky lg:top-0">
              <POCompactPanel
                po={selectedPO}
                currentUser={user}
                onApprove={handleApprovePO}
                onCancel={handleCancelPO}
                onCloseShort={handleCloseShort}
                onAmend={(po) => { setError(""); setSelectedPO(null); setAmendPO(po); }}
                onOpenDocument={onOpenDocument}
              />
            </div>
            <div className="min-w-0 lg:order-1">
              <PODetailPanel
                po={selectedPO}
                currentUser={user}
                embedded
                inModal
                onClose={() => setSelectedPO(null)}
                onApprove={handleApprovePO}
                onCancel={handleCancelPO}
                onCloseShort={handleCloseShort}
                onAmend={(po) => { setError(""); setSelectedPO(null); setAmendPO(po); }}
                onOpenDocument={onOpenDocument}
              />
            </div>
          </div>
        </DetailModal>
      )}

      {makloonMode && (
        <MakloonOrderCreateModal
          selectedEntity={selectedEntity}
          initialMode={makloonMode}
          lockMode
          onClose={() => setMakloonMode(null)}
          onSaved={() => { setMakloonMode(null); setNotice("Order makloon berhasil dibuat — lihat tab 'Order Makloon'."); }}
          onError={setError}
        />
      )}

      {amendPO && (
        <POAmendModal
          po={amendPO}
          products={products}
          warehouses={warehouses}
          suppliers={suppliers}
          submitting={amending}
          onSubmit={handleSubmitAmend}
          onClose={() => { const id = amendPO?.id; setAmendPO(null); if (id) handleViewDetail(id); }}
        />
      )}

      <ConfirmModal
        open={!!confirm}
        title={confirm?.title}
        message={confirm?.message}
        confirmLabel={confirm?.confirmLabel}
        danger={confirm?.danger}
        withReason={confirm?.withReason}
        reasonLabel={confirm?.reasonLabel}
        reasonPlaceholder={confirm?.reasonPlaceholder}
        onConfirm={confirm?.onConfirm}
        onCancel={() => setConfirm(null)}
        testId="po-confirm-modal"
      />
    </div>
  );
}
