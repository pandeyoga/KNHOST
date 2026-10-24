import { useEffect, useMemo, useRef, useState } from "react";
import MediaLightbox from "../../components/MediaLightbox";
import axios, { API } from "../../services/apiClient";
import { BadgePercent, RefreshCw, Search, Plus } from "lucide-react";
import { PriceApprovalForm } from "./priceApprovals/PriceApprovalForm";
import SpecialPriceRequestForm from "../pricing/SpecialPriceRequestForm";
import { PriceApprovalCard } from "./priceApprovals/PriceApprovalCard";
import ErrorNotice from "../../components/ErrorNotice";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import { can } from "../../config/roles";

const FILTERS = [
  { id: "all", label: "Semua" },
  { id: "pending", label: "Menunggu" },
  { id: "approved", label: "Disetujui" },
  { id: "rejected", label: "Ditolak" },
  { id: "draft", label: "Draf" },
  // F1b — pengajuan dari Daftar Harga per Pelanggan bisa berakhir digantikan aturan
  // baru atau dibatalkan pengajunya; keduanya harus bisa dilihat, bukan hilang.
  { id: "superseded", label: "Digantikan" },
  { id: "revoked", label: "Diakhiri" },
  { id: "cancelled", label: "Dibatalkan" },
];

const EMPTY_FORM = {
  customer_id: "",
  product_id: "",
  requested_price: "",
  min_quantity: "",
  valid_until: "",
  reason: "",
};

/**
 * Approval Harga Khusus (Sub-fase 1.7 — Special Price / Approval Harga).
 * Sales mengajukan harga nego per customer+product → upload bukti → manager/admin
 * approve/reject. Harga disetujui dipakai otomatis di POS (override harga normal).
 * Koleksi: price_approvals (pra_). Respons BE = bare object/array.
 * Sub-komponen di ./priceApprovals/ (Form + Card) agar file < 500 baris (compliance).
 */
export default function PriceApprovals({ currentUser = {}, focusDoc = null, onClearFocus }) {
  // Izin efektif = endpoint: setujui & akhiri aturan = price_approval.approve, tolak = price_approval.reject.
  const canApprove = can(currentUser?.permissions, "price_approval", "approve");
  const canReject = can(currentUser?.permissions, "price_approval", "reject");

  const [rows, setRows] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [busyId, setBusyId] = useState("");

  // form (create / edit)
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState("");
  const [form, setForm] = useState(EMPTY_FORM);
  const [formErr, setFormErr] = useState("");

  // decision (approve/reject)
  const [decideFor, setDecideFor] = useState(""); // `${id}:${mode}`
  const [decisionNotes, setDecisionNotes] = useState("");

  const fileInputs = useRef({});

  // FE-06 — dibuka dari Meja Saya / Inbox: tampilkan PENGAJUAN ASAL (bukan daftar umum). Server memeriksa
  // akses & scope lewat GET satu dokumen; dokumen hilang/di luar akses diberi pesan yang jelas.
  const [focusId, setFocusId] = useState("");
  const [focusRow, setFocusRow] = useState(null);
  const [focusMsg, setFocusMsg] = useState("");
  const loadFocus = async (id) => {
    try {
      const r = await axios.get(`${API}/price-approvals/${id}`);
      setFocusRow(r.data || null); setFocusId(id); setFocusMsg("");
    } catch (e) {
      setFocusId(""); setFocusRow(null);
      setFocusMsg(e.response?.status === 404 || e.response?.status === 403
        ? "Pengajuan yang dituju tidak ditemukan atau di luar akses Anda — mungkin sudah dihapus atau milik badan usaha lain."
        : (e.response?.data?.detail || "Gagal membuka pengajuan yang dituju."));
    }
  };
  useEffect(() => {
    const id = focusDoc?.focus_id;
    if (!id) return;
    setFilter("all"); setSearch("");
    loadFocus(id).finally(() => onClearFocus && onClearFocus());
  }, [focusDoc?.focus_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [pa, cu, pr] = await Promise.all([
        axios.get(`${API}/price-approvals`),
        axios.get(`${API}/customers`),
        axios.get(`${API}/products`),
      ]);
      setRows(Array.isArray(pa.data) ? pa.data : []);
      setCustomers(Array.isArray(cu.data) ? cu.data : []);
      setProducts(Array.isArray(pr.data) ? pr.data : []);
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat data approval harga.");
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, []);

  const resetForm = () => { setForm(EMPTY_FORM); setEditId(""); setShowForm(false); setFormErr(""); };

  const openCreate = () => { setForm(EMPTY_FORM); setEditId(""); setFormErr(""); setShowForm(true); };

  const openEdit = (r) => {
    setEditId(r.id);
    setForm({
      customer_id: r.customer_id, product_id: r.product_id,
      requested_price: String(r.requested_price ?? ""),
      min_quantity: String(r.min_quantity ?? ""),
      valid_until: (r.valid_until || "").slice(0, 10),
      reason: r.reason || "",
    });
    setFormErr("");
    setShowForm(true);
  };

  const submitForm = async (submitNow) => {
    setFormErr("");
    const price = parseFloat(form.requested_price);
    if (!form.customer_id || !form.product_id) { setFormErr("Pilih pelanggan dan produk."); return; }
    if (!price || price <= 0) { setFormErr("Harga khusus harus lebih dari 0."); return; }
    setBusyId("form");
    try {
      if (editId) {
        await axios.patch(`${API}/price-approvals/${editId}`, {
          data: {
            requested_price: price,
            min_quantity: parseFloat(form.min_quantity) || 0,
            valid_until: form.valid_until || "",
            reason: form.reason || "",
          },
        });
      } else {
        await axios.post(`${API}/price-approvals`, {
          customer_id: form.customer_id,
          product_id: form.product_id,
          requested_price: price,
          min_quantity: parseFloat(form.min_quantity) || 0,
          valid_until: form.valid_until || "",
          reason: form.reason || "",
          submit_now: !!submitNow,
        });
      }
      resetForm();
      await load();
    } catch (e) {
      setFormErr(e.response?.data?.detail || "Gagal menyimpan pengajuan.");
    } finally {
      setBusyId("");
    }
  };

  const runAction = async (id, fn) => {
    setBusyId(id);
    setError("");
    try {
      await fn();
      setDecideFor(""); setDecisionNotes("");
      await load();
      if (focusId) await loadFocus(focusId);
    } catch (e) {
      setError(e.response?.data?.detail || "Aksi gagal diproses.");
    } finally {
      setBusyId("");
    }
  };

  const submitApproval = (id) => runAction(id, () => axios.post(`${API}/price-approvals/${id}/submit`, {}));
  const approveApproval = (id, notes) => runAction(id, () => axios.post(`${API}/price-approvals/${id}/approve`, { decision_notes: notes }));
  const rejectApproval = (id, notes) => runAction(id, () => axios.post(`${API}/price-approvals/${id}/reject`, { decision_notes: notes }));
  // F1b — akhiri aturan STANDING yang sudah disetujui (promo selesai / kesepakatan batal).
  // Dulu tidak ada jalan menghentikannya: hapus ditolak (409) dan ubah hanya untuk draf.
  const revokeApproval = (id, notes) => runAction(id, () => axios.post(`${API}/price-approvals/${id}/revoke`, { decision_notes: notes }));

  const removeApproval = async (id) => {
    setBusyId(id);
    try {
      await axios.delete(`${API}/price-approvals/${id}`);
      await load();
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal menghapus pengajuan.");
    } finally {
      setBusyId("");
    }
  };

  const uploadFile = async (id, file) => {
    if (!file) return;
    setBusyId(id);
    setError("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      await axios.post(`${API}/price-approvals/${id}/attachments`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      await load();
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal mengunggah bukti.");
    } finally {
      setBusyId("");
    }
  };

  // UAT 24 Okt (P17) — lampiran dibuka di lightbox halaman yang sama (dulu blob di tab baru, tanpa thumbnail).
  const [viewer, setViewer] = useState(null);
  const viewAttachment = (id, att) => {
    const rec = rows.find((x) => x.id === id) || {};
    const list = (rec.attachments || []).filter((a) => !a.is_deleted);
    setViewer({ index: Math.max(0, list.findIndex((a) => a.id === att.id)),
      items: list.map((a) => ({ url: `${API}/price-approvals/${id}/attachments/${a.id}/download`, filename: a.original_filename,
        content_type: a.content_type })) });
  };

  const deleteAttachment = async (id, attId) => {
    setBusyId(id);
    try {
      await axios.delete(`${API}/price-approvals/${id}/attachments/${attId}`);
      await load();
    } catch (e) {
      setError("Gagal menghapus lampiran.");
    } finally {
      setBusyId("");
    }
  };

  const filtered = useMemo(() => (focusId ? [rows.find((r) => r.id === focusId) || focusRow].filter(Boolean) : rows.filter((r) => {
    if (filter !== "all" && r.status !== filter) return false;
    const hay = `${r.customer_name} ${r.product_name} ${r.sku}`.toLowerCase();
    return hay.includes(search.toLowerCase());
  })), [rows, filter, search, focusId, focusRow]);

  const counts = useMemo(() => ({
    pending: rows.filter((r) => r.status === "pending").length,
    all: rows.length,
  }), [rows]);

  return (
    <div data-testid="price-approvals-view" className="grid gap-4">
      <section className="section-card">
        {/* Audit UI 24 Okt (002) — kepala kartu membungkus di HP (dulu judul 3 baris tertimpa kotak cari);
            kicker Inggris "Sales" dilepas; tombol utama biru standar (dulu ungu #6B219A). */}
        <div className="section-head flex-wrap gap-y-2">
          <div className="flex items-center gap-2 min-w-0">
            <BadgePercent size={15} className="shrink-0 text-[#0058CC]" />
            <h2 data-testid="price-approvals-title">Persetujuan Harga Khusus</h2>
          </div>
          <div className="flex w-full items-center gap-2 sm:w-auto">
            <div className="flex min-w-0 flex-1 items-center gap-2 rounded-md border border-[#E5E5EA] bg-white px-2 py-1.5 sm:min-w-[180px]">
              <Search size={14} className="shrink-0 text-[#6B6B73]" />
              <input
                data-testid="price-approvals-search"
                className="w-full bg-transparent text-[13px] outline-none"
                placeholder="Cari pelanggan / produk…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <button
              data-testid="price-approvals-new"
              className="primary-button shrink-0 !py-1.5 text-[12px]"
              onClick={openCreate}
            >
              <Plus size={14} /> Ajukan
            </button>
            <button data-testid="price-approvals-refresh" className="icon-button" onClick={load} aria-label="Muat ulang">
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            </button>
          </div>
        </div>
        <div className="tab-bar px-4">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              data-testid={`price-approvals-filter-${f.id}`}
              onClick={() => setFilter(f.id)}
              className={`tab-button ${filter === f.id ? "active" : ""}`}
            >
              {f.label}
              {f.id === "pending" && counts.pending > 0 && (
                <span
                  data-testid="price-approvals-pending-badge"
                  className="tab-badge"
                >
                  {counts.pending}
                </span>
              )}
              {f.id === "all" && <span className="tab-badge">{counts.all}</span>}
            </button>
          ))}
        </div>
      </section>

      {/* FASE P5 — form pengajuan harga khusus menjadi POP-UP: daftar pengajuan &
          ringkasan di belakang tetap terlihat sebagai pembanding. */}
      <FormModal
        open={showForm}
        onClose={resetForm}
        title={editId ? "Ubah Pengajuan Harga" : "Ajukan Harga Khusus"}
        subtitle="Harga di luar daftar harga standar — perlu persetujuan manajer"
        icon={BadgePercent}
        size="lg"
        testId="price-approval-modal"
      >
        {/* Audit UI 24 Okt (002) — SATU alur pengajuan baru: pemilih pelanggan & produk tetap di atas, form
            harga + bukti (SpecialPriceRequestForm) terpasang sejak awal. Dulu isi modal DIGANTI begitu pelanggan &
            produk terpilih → harga/berlaku/alasan yang sudah diketik hilang & "Simpan sebagai Draft" tak tercapai. */}
        {!editId ? (
          <div className="grid gap-3" data-testid="price-approvals-create">
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1">
                <span className="field-label">Pelanggan *</span>
                <KNSelect data-testid="price-approvals-customer" className="field" searchable aria-label="Pelanggan"
                  value={form.customer_id} onValueChange={(v) => setForm((f) => ({ ...f, customer_id: v }))}
                  placeholder="— Pilih Pelanggan —"
                  options={customers.map((c) => ({ value: c.id, label: c.name }))} />
              </label>
              <label className="grid gap-1">
                <span className="field-label">Produk *</span>
                <KNSelect data-testid="price-approvals-product" className="field" searchable aria-label="Produk"
                  value={form.product_id} onValueChange={(v) => setForm((f) => ({ ...f, product_id: v }))}
                  placeholder="— Pilih Produk —"
                  options={products.map((p) => ({ value: p.id, label: `${p.name} (${p.sku})` }))} />
              </label>
            </div>
            <SpecialPriceRequestForm allowDraft
              product={products.find((p) => p.id === form.product_id)}
              customer={customers.find((c) => c.id === form.customer_id)}
              onSubmitted={() => { resetForm(); load(); }} onCancel={resetForm} />
          </div>
        ) : (
        <PriceApprovalForm
          variant="modal"
          editId={editId}
          form={form}
          setForm={setForm}
          formErr={formErr}
          busyId={busyId}
          customers={customers}
          products={products}
          onClose={resetForm}
          onSubmit={submitForm}
        />
        )}
      </FormModal>

      {error && (
        <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="price-approvals-error" />
      )}

      {focusMsg && (
        <ErrorNotice message={focusMsg} onDismiss={() => setFocusMsg("")} testId="price-approvals-focus-missing" />
      )}
      {focusId && (
        <div data-testid="price-approvals-focus" className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[#D9E7FF] bg-[#F4F8FF] px-3 py-2 text-[12px] text-[#0058CC]">
          <span>Menampilkan pengajuan yang dibuka dari antrean{focusRow?.customer_name ? ` — ${focusRow.customer_name} · ${focusRow.product_name || ""}` : ""}.</span>
          <button type="button" className="secondary-button !py-1 text-[11px]" data-testid="price-approvals-focus-clear"
            onClick={() => { setFocusId(""); setFocusRow(null); }}>Tampilkan semua pengajuan</button>
        </div>
      )}

      <section className="grid gap-3">
        {loading && (
          <div data-testid="price-approvals-loading" className="section-card animate-pulse p-8 text-center text-[13px] text-[#6B6B73]">
            Memuat pengajuan…
          </div>
        )}
        {!loading && filtered.length === 0 && (
          <div data-testid="price-approvals-empty" className="section-card p-10 text-center text-[13px] text-[#6B6B73]">
            Belum ada pengajuan harga khusus.
          </div>
        )}
        {!loading && filtered.map((r) => (
          <PriceApprovalCard
            key={r.id}
            r={r}
            canApprove={canApprove}
            canReject={canReject}
            busyId={busyId}
            decideFor={decideFor}
            setDecideFor={setDecideFor}
            decisionNotes={decisionNotes}
            setDecisionNotes={setDecisionNotes}
            fileInputs={fileInputs}
            onUpload={uploadFile}
            onSubmit={submitApproval}
            onApprove={approveApproval}
            onReject={rejectApproval}
            onRevoke={revokeApproval}
            onEdit={openEdit}
            onRemove={removeApproval}
            onViewAttachment={viewAttachment}
            onDeleteAttachment={deleteAttachment}
          />
        ))}
      </section>
      {viewer && <MediaLightbox items={viewer.items} index={viewer.index} onClose={() => setViewer(null)} testId="price-approvals-lightbox" />}
    </div>
  );
}
