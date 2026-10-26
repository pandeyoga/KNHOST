import { useEffect, useMemo, useState } from "react";
import { Truck, Plus, ArrowRight, Search } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import FilterChips from "../../components/FilterChips";
import LineFilter from "../../components/LineFilter";
import { apiErrorText } from "../../utils/apiError";
import { notifySuccess } from "../../utils/feedback";
import { askConfirm, askReason } from "../../services/confirmService";
import { formatQty } from "../../utils/formatters";
import { statusLabel, TRANSFER_STATUS_FILTERS } from "./transfer/transferConstants";
import TransferCreateForm from "./transfer/TransferCreateForm";
import TransferList, { transferKindOf } from "./transfer/TransferList";
import FormModal from "../../components/FormModal";
import TransferDetailModal from "./transfer/TransferDetailModal";

/**
 * TransferManagement
 *
 * Panel untuk mengelola transfer antar gudang dengan workflow:
 * draft → waiting_approval → approved → picking → staging → dispatched → completed
 *
 * Fase 3 · P5 — D-16: SATU daftar untuk transfer antar gudang DAN antar badan usaha (PT). Dulu transfer antar-PT
 * tampil dua kali (di daftar ini + sub-tab "Antar entitas (PT)" dengan kartu & tombol bergaya lain). Kini kolom
 * "Jenis" + saringan Jenis (Semua · Antar gudang · Antar PT), satu pop-up rincian dengan aksi sesuai jenis.
 * `kind`/`onKindChange` = saringan terkendali (preset alias `interco-transfers`); tanpa itu `initialKind`.
 *
 * Sub-components live in ./transfer/ (kept under file-size limits per KN_02).
 */
export default function TransferManagement({
  user, focusTransferId = "", onFocusConsumed, kind: kindProp, onKindChange, initialKind = "all",
}) {
  const [transfers, setTransfers] = useState([]);
  const [products, setProducts] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedTransfer, setSelectedTransfer] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [filterStatus, setFilterStatus] = useState("all");
  const [kindLocal, setKindLocal] = useState(initialKind);
  const kind = kindProp ?? kindLocal;
  const setKind = (k) => { setKindLocal(k); onKindChange?.(k); };
  const [lineFilter, setLineFilter] = useState("");   // FASE L — dulu hanya di daftar antar-PT
  const [search, setSearch] = useState("");

  // FASE P5 — galat muncul DI TEMPAT pengguna sedang bekerja, bukan lewat `alert()`
  // yang memblokir peramban:
  //   · `formError`   → di dalam pop-up "Transfer Gudang Baru" (kaki modal),
  //   · `actionError` → di dalam modal detail (Setujui/Tolak/Batal gagal di sana),
  //   · `error`       → bilah menempel di halaman untuk kegagalan memuat daftar.
  // Kalau galat aksi ditaruh di bilah halaman, ia tertutup modal detail → efeknya
  // sama dengan senyap, padahal justru di situ uang & stok berpindah.
  const [formError, setFormError] = useState("");
  const [actionError, setActionError] = useState("");
  const [saving, setSaving] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    source_warehouse_id: "",
    dest_warehouse_id: "",
    items: [],
    notes: ""
  });
  const [newItem, setNewItem] = useState({ product_id: "", qty: 0, unit: "meter" });

  useEffect(() => {
    fetchTransfers();
  }, [filterStatus, lineFilter]); // eslint-disable-line
  useEffect(() => { fetchMasterData(); }, []);

  // Saringan Jenis & cari dihitung di peramban (satu muatan, hitungan per jenis tetap benar).
  const kindCounts = useMemo(() => ({
    all: transfers.length,
    intra_entity: transfers.filter((t) => transferKindOf(t) === "intra_entity").length,
    inter_entity: transfers.filter((t) => transferKindOf(t) === "inter_entity").length,
  }), [transfers]);
  const shown = useMemo(() => {
    const q = search.trim().toLowerCase();
    return transfers.filter((t) => {
      if (kind !== "all" && transferKindOf(t) !== kind) return false;
      if (!q) return true;
      const hay = [t.code, t.source_warehouse_name, t.dest_warehouse_name, t.source_entity_name, t.dest_entity_name,
        t.requested_by, t.sales_order_number, ...(t.items || []).map((i) => `${i.sku || ""} ${i.product_name || ""}`)]
        .filter(Boolean).join(" ").toLowerCase();
      return hay.includes(q);
    });
  }, [transfers, kind, search]);

  // Deep-link dari Meja Admin Gudang ("Setujui") → transfer yang diklik langsung terbuka.
  useEffect(() => {
    if (!focusTransferId || !transfers.length) return;
    const t = transfers.find((x) => x.id === focusTransferId);
    if (t) { setSelectedTransfer(t); setActionError(""); }
    onFocusConsumed?.();
  }, [focusTransferId, transfers]); // eslint-disable-line

  const fetchTransfers = async () => {
    setLoading(true);
    try {
      const params = {};
      if (filterStatus !== "all") params.status = filterStatus;
      if (lineFilter) params.line = lineFilter;
      const response = await axios.get(`${API}/transfers`, { params });
      setTransfers(Array.isArray(response.data) ? response.data : []);
      setError("");
    } catch (error) {
      setError(apiErrorText(error, "Gagal memuat daftar transfer."));
    } finally {
      setLoading(false);
    }
  };

  const fetchMasterData = async () => {
    try {
      const [productsRes, warehousesRes] = await Promise.all([
        axios.get(`${API}/products`),
        axios.get(`${API}/warehouses`)
      ]);
      setProducts(productsRes.data);
      setWarehouses(warehousesRes.data);
    } catch (error) {
      console.error("Error fetching master data:", error);
    }
  };

  const resetForm = () => setFormData({ source_warehouse_id: "", dest_warehouse_id: "", items: [], notes: "", sales_order_id: "" });

  const handleCreateTransfer = async () => {
    if (!formData.source_warehouse_id || !formData.dest_warehouse_id) {
      setFormError("Pilih gudang asal dan gudang tujuan terlebih dahulu.");
      return;
    }
    if (formData.items.length === 0) {
      setFormError("Tambahkan minimal 1 barang yang akan dipindah.");
      return;
    }
    setFormError("");
    setSaving(true);
    try {
      const items = formData.items.map(({ rolls, ...it }) => it);   // snapshot roll hanya untuk tampilan
      const res = await axios.post(`${API}/transfers`, { ...formData, items, requested_by: user?.name || "User" });
      notifySuccess("Transfer dibuat",
        res.data?.code ? `${res.data.code} menunggu persetujuan manajer.` : "Menunggu persetujuan manajer.");
      setShowCreateForm(false);
      resetForm();
      fetchTransfers();
    } catch (error) {
      setFormError(apiErrorText(error, "Gagal membuat transfer."));
    } finally {
      setSaving(false);
    }
  };

  const handleAddItem = (picked) => {
    if (!picked?.product_id || !(picked.roll_ids || []).length) {
      setFormError("Pilih produk lalu pilih roll yang akan dipindah.");
      return;
    }
    setFormError("");
    setFormData({ ...formData, items: [...formData.items, picked] });
    setNewItem({ product_id: "", qty: 0, unit: "meter" });
  };

  const handleRemoveItem = (index) => {
    setFormData({ ...formData, items: formData.items.filter((_, i) => i !== index) });
  };

  const handleApprove = async (transferId, ruleReason = "") => {
    // UAT 24 Okt (audit UI tahap 2) — persetujuan (memesan roll; antar-PT memindah kepemilikan + jurnal) dulu sekali klik.
    const t = (selectedTransfer && selectedTransfer.id === transferId) ? selectedTransfer : (transfers || []).find((x) => x.id === transferId) || {};
    const ic = t.transfer_kind === "inter_entity";
    const items = (t.items || []).map((it) => `${it.product_name || it.sku} ${formatQty(it.qty)} ${it.unit || ""}`.trim()).join(", ");
    if (!(await askConfirm({
      title: `Setujui transfer ${t.code || ""}?`.replace("  ", " "),
      message: `${t.source_warehouse_name || "Gudang asal"} → ${t.dest_warehouse_name || "gudang tujuan"}${items ? `: ${items}` : ""}.`
        + (ic ? " Kepemilikan barang pindah ke badan usaha tujuan dan jurnal antar-PT dibuat." : " Gudang asal lalu bisa mulai pengambilan."),
      confirmLabel: ic ? "Setujui & pindahkan kepemilikan" : "Setujui",
    }))) return;
    setActionError("");
    try {
      await axios.post(`${API}/transfers/${transferId}/approve`, { approved_by: user?.name || "Manager", rule_exception_reason: ruleReason });
      notifySuccess("Transfer disetujui", ic
        ? "Kepemilikan barang pindah ke badan usaha tujuan; jurnal antar-PT dibuat."
        : "Gudang asal bisa mulai pengambilan barang.");
      fetchTransfers();
      setSelectedTransfer(null);
    } catch (error) {
      setActionError(apiErrorText(error, "Gagal menyetujui transfer."));
    }
  };

  const handleReject = async (transferId) => {
    // FASE P5 — dulu `prompt("Alasan reject:")`: tak bisa divalidasi (spasi pun lolos),
    // tak bisa diberi konteks, dan bisa dibungkam permanen oleh peramban.
    const reason = await askReason({
      title: "Tolak transfer ini?",
      message: "Roll yang sudah ditahan akan dilepas kembali ke gudang asal. "
        + "Alasan dicatat pada dokumen supaya pengaju tahu apa yang harus diperbaiki.",
      reasonLabel: "Alasan penolakan",
      reasonMinLength: 5,
      reasonPlaceholder: "Contoh: stok gudang asal masih dipakai SO-0007",
      confirmLabel: "Tolak Transfer",
      danger: true,
      testId: "transfer-reject-confirm",
    });
    if (reason === null) return;
    setActionError("");
    try {
      await axios.post(`${API}/transfers/${transferId}/reject`, { rejected_by: user?.name || "Manager", reason });
      notifySuccess("Transfer ditolak", "Roll yang tertahan sudah dilepas ke gudang asal.");
      fetchTransfers();
      setSelectedTransfer(null);
    } catch (error) {
      setActionError(apiErrorText(error, "Gagal menolak transfer."));
    }
  };

  const handleUpdateStatus = async (transferId, newStatus) => {
    setActionError("");
    try {
      await axios.post(`${API}/transfers/${transferId}/status`, { status: newStatus, updated_by: user?.name || "Warehouse" });
      notifySuccess("Status transfer diperbarui", `Sekarang: ${statusLabel(newStatus)}.`);
      fetchTransfers();
      setSelectedTransfer(null);
    } catch (error) {
      setActionError(apiErrorText(error, "Gagal memperbarui status transfer."));
    }
  };

  const handleCancel = async (transferId) => {
    // Berdampak STOK (roll yang tertahan dilepas) → keputusan pemilik: alasan WAJIB,
    // dan alasannya benar-benar disimpan (`cancelled_reason` + audit log), bukan
    // ditanyakan lalu dibuang.
    const reason = await askReason({
      title: "Batalkan transfer ini?",
      message: "Semua roll yang tertahan untuk transfer ini dilepas kembali menjadi tersedia "
        + "di gudang asal. Transfer yang sudah dibatalkan tidak bisa dijalankan lagi.",
      reasonLabel: "Alasan pembatalan",
      reasonPlaceholder: "Contoh: permintaan gudang tujuan dibatalkan",
      confirmLabel: "Batalkan Transfer",
      danger: true,
      testId: "transfer-cancel-confirm",
    });
    if (reason === null) return;
    setActionError("");
    try {
      await axios.delete(`${API}/transfers/${transferId}`, { params: { reason } });
      notifySuccess("Transfer dibatalkan", "Stok yang tertahan sudah dilepas kembali.");
      fetchTransfers();
      setSelectedTransfer(null);
    } catch (error) {
      setActionError(apiErrorText(error, "Gagal membatalkan transfer."));
    }
  };

  return (
    <div data-testid="transfer-management-panel" className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex items-center justify-center w-10 h-10 shrink-0 rounded-full bg-[#007AFF]/10">
            <Truck className="text-[#007AFF]" size={20} />
          </div>
          <div className="min-w-0">
            <h2 data-testid="panel-title" className="text-lg font-semibold text-[#000000]">
              Transfer
            </h2>
            <p data-testid="panel-subtitle" className="text-sm text-[#3C3C43]">
              Antar gudang dan antar badan usaha (PT) — satu daftar
            </p>
          </div>
        </div>
        <button data-testid="create-transfer-button" onClick={() => setShowCreateForm(true)} className="primary-button">
          <Plus size={14} /> Buat Transfer
        </button>
      </div>

      {/* Saringan — Jenis (D-16), status, lini, cari. Saringan = chip, bukan tab (L-01). */}
      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-2">
        <FilterChips testId="trf-kind" ariaLabel="Jenis transfer" value={kind} onChange={setKind}
          options={[
            { key: "all", label: "Semua jenis", count: kindCounts.all },
            { key: "intra_entity", label: "Antar gudang", count: kindCounts.intra_entity },
            { key: "inter_entity", label: "Antar PT", count: kindCounts.inter_entity },
          ]} />
        <FilterChips testId="filter-status" ariaLabel="Status transfer" value={filterStatus} onChange={setFilterStatus}
          options={TRANSFER_STATUS_FILTERS.map((s) => ({ key: s, label: s === "all" ? "Semua status" : statusLabel(s) }))} />
        <div className="flex flex-wrap items-center gap-2">
          <LineFilter value={lineFilter} onChange={setLineFilter} storageKey="transfers"
            allowed={user?.allowed_line_codes} testId="trf-line-filter" />
          <label className="flex min-w-0 flex-1 items-center gap-2 rounded-md border border-[#E5E5EA] bg-white px-2 py-1.5 sm:max-w-xs">
            <Search size={14} className="shrink-0 text-[#6B6B73]" />
            <input data-testid="trf-search" className="w-full min-w-0 bg-transparent text-[13px] outline-none"
              placeholder="Cari kode / gudang / PT / produk…" value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
        </div>
      </div>

      {/* Create Form */}
      {/* FASE P4 — form transfer menjadi POP-UP: daftar transfer di belakang tetap
          terlihat, jadi pengguna bisa membandingkan sambil mengisi. */}
      <FormModal
        open={showCreateForm}
        onClose={() => { setShowCreateForm(false); setFormError(""); resetForm(); }}
        title="Transfer Gudang Baru"
        subtitle="Pilih gudang asal & tujuan, lalu tambahkan barang yang dipindah"
        icon={ArrowRight}
        size="lg"
        testId="transfer-form"
        onSubmit={handleCreateTransfer}
        submitLabel="Buat Transfer"
        submitTestId="submit-transfer-button"
        cancelTestId="cancel-form-button"
        busy={saving}
        error={formError}
        // UAT 24 Okt (audit UI tahap 2) — "Buat Transfer" dulu aktif pada form kosong.
        submitDisabled={!formData.source_warehouse_id || !formData.dest_warehouse_id
          || formData.source_warehouse_id === formData.dest_warehouse_id || !(formData.items || []).length}
      >
        <TransferCreateForm
          variant="modal"
          formData={formData}
          setFormData={setFormData}
          newItem={newItem}
          setNewItem={setNewItem}
          products={products}
          warehouses={warehouses}
          onAddItem={handleAddItem}
          onAddItems={(list) => setFormData((f) => ({ ...f, items: [...f.items, ...list] }))}
          onRemoveItem={handleRemoveItem}
          onSubmit={handleCreateTransfer}
          onClose={() => { setShowCreateForm(false); setFormError(""); resetForm(); }}
        />
      </FormModal>

      {/* Transfers List */}
      <ErrorNotice message={error} onRetry={fetchTransfers} onDismiss={() => setError("")} testId="transfer-error" />
      <TransferList rows={shown} loading={loading}
        emptyText={transfers.length
          ? "Tidak ada transfer yang cocok dengan saringan."
          : "Belum ada transfer. Buat transfer untuk memindahkan stok antar gudang."}
        onOpen={(transfer) => { setSelectedTransfer(transfer); setActionError(""); }} />

      {/* Detail Modal */}
      {selectedTransfer && (
        <TransferDetailModal
          transfer={selectedTransfer}
          user={user}
          onClose={() => { setSelectedTransfer(null); setActionError(""); }}
          onApprove={handleApprove}
          onReject={handleReject}
          onUpdateStatus={handleUpdateStatus}
          onCancel={handleCancel}
          actionError={actionError}
          onDismissActionError={() => setActionError("")}
          onReceiptChanged={(st) => { fetchTransfers(); if (st) setSelectedTransfer((t) => (t ? { ...t, status: st } : t)); }}
        />
      )}
    </div>
  );
}
