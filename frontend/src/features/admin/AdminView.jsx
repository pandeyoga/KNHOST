/**
 * AdminView — master data generik + Integrasi & Audit (dipakai ulang di beberapa hub lewat prop `only`).
 *
 * Fase 3 · P2 (keputusan pemilik 26 Okt):
 *  · D-01 — tab "Template Dokumen" DICABUT: form terlengkapnya (`DocTemplateForm`) kini di Pengaturan › Dokumen &
 *    Cetak › Template Dokumen di atas tabel berlapis global → badan usaha (satu data, satu tempat).
 *  · D-21 — tab "Satuan (UOM)" DICABUT: `md-uoms` merender layar Satuan & Konversi (tabel tunggal "Satuan & faktor",
 *    form "Satuan baru" dipindah ke sana).
 *  · D-05 — "Buat Pelanggan" (Impor/Ekspor & Status) membuka `CustomerFormModal` (form pelanggan LENGKAP yang sama
 *    dengan CRM/POS) — form 8 isian di sini dihapus.
 *  · L-01 — tab internal (pil) → `PageTabs`; testid `admin-tab-<id>-button` dipertahankan (tur).
 *  · Jejak audit diekstrak ke `AdminAuditList.jsx` (batas 500 baris).
 */
import KNDatePicker from "@/components/KNDatePicker";
import { useState, useEffect, useCallback, useMemo } from "react";
import { RefreshCw, Plus, Check, AlertTriangle, Filter } from "lucide-react";
import CategoryManager from "./CategoryManager";
import IntegrationsPanel from "./IntegrationsPanel";
import GeminiIntegrationPanel from "./GeminiIntegrationPanel";
import OpenAiIntegrationPanel from "./OpenAiIntegrationPanel";
import AdminAuditList from "./AdminAuditList";
import FormModal from "../../components/FormModal";
import PageTabs from "../../components/PageTabs";
import DesktopOnlyNotice from "../../components/DesktopOnlyNotice";
import ProductMasterForm from "./products/ProductMasterForm";
import CustomerFormModal from "../crm/CustomerFormModal";
import LineFilter from "../../components/LineFilter";   // FASE L — chip penyaring lini
import ProductLifecycleCell from "../rnd/ProductLifecycleCell";
import axios, { API } from "../../services/apiClient";
import { formatCurrency } from "../../utils/formatters";
import { productMatches, supplierCodesLabel } from "../../utils/productSearch";   // MD-08
import { useEntityScope } from "../../context/EntityScopeContext";
import { scopeSuffix } from "../../utils/entityLabel";
// INV-ROLE-01 — wewenang layar dibaca dari IZIN pengguna, bukan nama peran.
import { can } from "../../config/roles";

// FASE G-0 — tab "Pengaturan" DIHAPUS (satu-satunya tempat setting = Pusat Pengaturan). FASE E-3 — tab "Entities" &
// "Users" pindah ke "Badan Usaha & Akses". FASE E-4 — tab "Warehouse" pindah ke "Gudang (Master)". Fase 3 · P2 —
// tab "Satuan (UOM)" & "Template Dokumen" pindah ke layar utamanya (lihat kepala berkas).
const ALL_TABS = [
  ["products", "Produk"], ["categories", "Kategori"], ["customers", "Pelanggan"], ["integrations", "Integrasi AI"], ["audit", "Jejak Audit"],
];
const TAB_SINGULAR = { products: "Produk", customers: "Pelanggan" };
const tabLabel = Object.fromEntries(ALL_TABS);
const statusLabel = (row) => ((row.status || (row.active === false ? "inactive" : "active")) === "inactive" ? "Nonaktif" : "Aktif");
const isInactive = (row) => statusLabel(row) === "Nonaktif";

export default function AdminView({
  data,
  auditLogs,
  auditFilters,
  setAuditFilters,
  onAdminCreate,
  onAdminPatch,
  onAdminDelete,
  onImportMaster,
  onExportMaster,
  onRefreshAudit,
  onShowDetail,
  onSeedDemo,
  onReload,   // FASE F — muat ulang data master setelah produk dirilis ke produksi
  currentUser,
  only,   // opsional: array tab id (mis. ["products"]) untuk embed master data di domain hub
}) {
  const [tab, setTab] = useState(Array.isArray(only) && only.length ? only[0] : "products");
  // FASE E-3 (user story 7) — di mode "Semua Entitas" pembuatan data DIMATIKAN (pelanggan ber-badan-usaha).
  const { canWrite, writeBlockHint, selectedEntity: scopeEntityId, entities: scopeEntities } = useEntityScope();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [categories, setCategories] = useState([]);
  const [salesOwners, setSalesOwners] = useState([]);   // PS-20 — daftar sales utk produk eksklusif
  const [salesUsers, setSalesUsers] = useState([]);     // D-05 — sales penanggung jawab pelanggan (sumber sama dgn CRM)
  const loadCategories = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/product-categories`);
      setCategories(Array.isArray(res.data) ? res.data : []);
    } catch (_) { /* non-blocking: form produk fallback ke daftar baku */ }
  }, []);
  useEffect(() => { loadCategories(); }, [loadCategories]);
  const loadSalesOwners = useCallback(async () => {
    // AUDIT PERAN (2026-08-15) — `GET /products/sales-owners` digerbang `product.update` (hanya admin); peran lain
    // tidak memanggilnya (dulu 403 tertelan di setiap pembukaan layar). Pemilih pemilik produk eksklusif pun hanya
    // dirender bagi yang boleh menyunting.
    if (!can(currentUser?.permissions || {}, "product", "update")) {
      setSalesOwners([]);
      return;
    }
    try {
      const res = await axios.get(`${API}/products/sales-owners`);
      setSalesOwners(Array.isArray(res.data) ? res.data : []);
    } catch (_) { /* non-blocking: hanya admin (product:update) yang berhak */ }
  }, [currentUser]);
  useEffect(() => { loadSalesOwners(); }, [loadSalesOwners]);
  useEffect(() => {
    if (tab !== "customers" || !showCreateForm) return undefined;
    let live = true;
    const params = scopeEntityId && scopeEntityId !== "all" ? { entity_id: scopeEntityId } : {};
    axios.get(`${API}/sales-users`, { params })
      .then((r) => { if (live) setSalesUsers(Array.isArray(r.data) ? r.data : []); })
      .catch(() => {});
    return () => { live = false; };
  }, [tab, showCreateForm, scopeEntityId]);
  // Opsi dropdown kategori (aktif saja) untuk form produk; fallback 7 kategori baku.
  const categoryOptions = (categories.length
    ? categories.filter((c) => c.status === "active")
    : ["Batik", "Tenun", "Lurik", "Songket", "Ulos", "Jumputan", "Endek"].map((n) => ({ name: n })))
    .map((c) => ({ value: c.name, label: c.name }));
  // Fase A (PS-01/02/03/09) — field domain tekstil wajib ada di state form.
  const emptyProduct = { sku: "", name: "", category: "Batik", variant: "Regular", color: "", color_code: "", color_name: "", color_hex: "", stage: "finished", fabric_type: "woven", line_code: "", yarn_count: "", yarn_count_system: "", motif: "", grade: "A", supplier: "", base_unit: "meter", price: 0, gramasi: 0, lebar: 0, image: "", description: "", uom_conversions: [], exclusivity: "umum", owner_sales_ids: [] };
  const [product, setProduct] = useState(emptyProduct);
  const [savingProduct, setSavingProduct] = useState(false);
  const [editingProductId, setEditingProductId] = useState(null);
  const [productError, setProductError] = useState("");
  const [showImportExport, setShowImportExport] = useState(false);
  // FASE L — penyaring lini pada Master Produk (records sudah dipagar server lewat `line_scope`).
  const [lineFilter, setLineFilter] = useState("");
  const [importFile, setImportFile] = useState(null);
  const [importPreview, setImportPreview] = useState(null);
  const [importLoading, setImportLoading] = useState(false);

  // Sub-fase 1.13 — helper form produk (uom_conversions + create/edit)
  const resetProductForm = () => { setProduct(emptyProduct); setEditingProductId(null); setProductError(""); };
  const updateConv = (idx, key, val) => setProduct({
    ...product,
    uom_conversions: (product.uom_conversions || []).map((c, i) => i === idx ? { ...c, [key]: val } : c),
  });
  const addConv = () => setProduct({ ...product, uom_conversions: [...(product.uom_conversions || []), { from_unit: "", to_unit: product.base_unit || "meter", factor: 0 }] });
  const removeConv = (idx) => setProduct({ ...product, uom_conversions: (product.uom_conversions || []).filter((_, i) => i !== idx) });
  // Sub-fase 1.13 — validasi konversi: unit wajib diisi, factor > 0, from != to.
  const validateConversions = () => {
    const rows = product.uom_conversions || [];
    for (let i = 0; i < rows.length; i++) {
      const from = String(rows[i].from_unit || "").trim();
      const to = String(rows[i].to_unit || "").trim();
      const factor = Number(rows[i].factor);
      if (!from || !to) return `Konversi #${i + 1}: unit "Dari" dan "Ke" wajib diisi.`;
      if (from.toLowerCase() === to.toLowerCase()) return `Konversi #${i + 1}: unit "Dari" dan "Ke" tidak boleh sama.`;
      if (!(factor > 0)) return `Konversi #${i + 1}: faktor harus lebih besar dari 0.`;
    }
    return "";
  };
  const saveProduct = async () => {
    const err = validateConversions();
    if (err) { setProductError(err); return; }
    setProductError(""); setSavingProduct(true);
    // Fase A — form TIDAK direset bila server menolak supaya isian pengguna tidak hilang & pesan validasi terbaca.
    const res = editingProductId
      ? await onAdminPatch("products", editingProductId, product)
      : await onAdminCreate("products", product);
    setSavingProduct(false);
    if (res && res.ok === false) { setProductError(res.error || "Gagal menyimpan produk."); return; }
    resetProductForm();
    setShowCreateForm(false);   // sukses → modal ditutup (bukan berpindah diam-diam ke mode Buat)
  };
  const loadProductForEdit = (row) => {
    setProduct({
      sku: row.sku || "", name: row.name || "", category: row.category || "", variant: row.variant || "",
      color: row.color || "", color_code: row.color_code || "", color_name: row.color_name || "", color_hex: row.color_hex || "",
      stage: row.stage || "finished", fabric_type: row.fabric_type || "",
      line_code: row.line_code || "",          // FASE L — lini kerja MD
      yarn_count: row.yarn_count || "", yarn_count_system: row.yarn_count_system || "",
      motif: row.motif || "", grade: row.grade || "", supplier: row.supplier || "",
      base_unit: row.base_unit || "meter", price: Number(row.price || 0), hpp: Number(row.hpp || 0), hpp_source: row.hpp_source || "",
      gramasi: Number(row.gramasi || 0), lebar: Number(row.lebar || 0), image: row.image || "", description: row.description || "", uom_conversions: row.uom_conversions || [],
      exclusivity: row.exclusivity || "umum", owner_sales_ids: row.owner_sales_ids || [],
    });
    setEditingProductId(row.id);
    setShowCreateForm(true);  // F3 — buka form saat Edit (sebelumnya tetap tertutup)
  };

  // G5-17 — laci rincian Master Data: isi yang berarti per jenis + kalimat aksi yang sesuai baris.
  const masterDetail = (row) => {
    const facts = tab === "customers" ? [
      { label: "PIC toko", value: row.pic_name || "—" }, { label: "HP/WhatsApp", value: row.phone || "—" },
      { label: "Kota", value: row.city || "—" }, { label: "Sales penanggung jawab", value: row.assigned_sales_name || row.sales_pic || "—" },
      { label: "Batas kredit", value: Number(row.credit_limit) > 0 ? formatCurrency(row.credit_limit) : "Tanpa batas" },
    ] : [];
    return { title: row.name || row.legal_name || row.code || row.email,
      body: `${TAB_SINGULAR[tab] || "Data"} — ${isInactive(row) ? "Aktifkan" : "Nonaktifkan"} ada di baris daftar.`,
      facts: [...facts, { label: "Status", value: statusLabel(row) }] };
  };
  const tabs = Array.isArray(only) && only.length ? ALL_TABS.filter(([id]) => only.includes(id)) : ALL_TABS;
  // Embedded (1 tab): sembunyikan header + bilah tab internal — konteks sudah dari HubTabs + PageMeta.
  const embedded = Array.isArray(only) && only.length === 1;
  const currentResource = tab;
  // FASE E-3 — daftar record per tab; tab tanpa daftar mengembalikan [] (dulu jatuh ke daftar pengguna).
  const records = useMemo(() => ({ products: data.products, customers: data.customers }[tab] || []),
    [tab, data.products, data.customers]);

  // FASE L — penyaring lini WAJIB dideklarasikan SETELAH `records` (dulu TDZ → layar Produk & Harga blank).
  const [productQuery, setProductQuery] = useState("");   // MD-08 — cari kode KN / kode pabrik
  const [recordQuery, setRecordQuery] = useState("");
  const visibleRecords = useMemo(() => {
    let rows = records;
    if (tab !== "products" && recordQuery.trim()) {
      const t = recordQuery.trim().toLowerCase();
      rows = (rows || []).filter((r) => Object.values(r || {}).filter((v) => typeof v === "string" || typeof v === "number").join(" ").toLowerCase().includes(t));
    }
    if (tab === "products" && lineFilter) {
      const want = lineFilter.split(",").map((s) => s.trim()).filter(Boolean);
      rows = (rows || []).filter((r) => want.includes(String(r.line_code || "")));
    }
    if (tab === "products" && productQuery.trim()) rows = (rows || []).filter((r) => productMatches(r, productQuery));
    return rows;
  }, [records, tab, lineFilter, productQuery, recordQuery]);

  const handleDryRunImport = async () => {
    if (!importFile) return;
    setImportLoading(true);
    const result = await onImportMaster(currentResource, importFile, true);
    setImportPreview(result);
    setImportLoading(false);
  };
  const [modalBusy, setModalBusy] = useState(false);
  const runAuditFilter = async () => {
    setModalBusy(true);
    try { onRefreshAudit(); setShowCreateForm(false); } finally { setModalBusy(false); }
  };

  return (
    <div data-testid="admin-view">
      {!embedded && (
      <section className="section-card mb-3">
        <div className="section-head">
          {/* Audit UI 099 — judul mengikuti tab yang benar-benar tampil. */}
          <div className="flex items-center gap-3 min-w-0">
            <span className="kicker">{Array.isArray(only) && only.length ? "Pengaturan Sistem" : "Admin Master Data"}</span>
            <h2>{tabs.map(([, label]) => label).join(" · ")}</h2>
          </div>
        </div>
        <div className="px-3 pb-2">
          <DesktopOnlyNotice testId="settings-desktop-notice" what="Pengaturan" />
          <PageTabs testId="admin-tabs" tabTestId={(id) => `admin-tab-${id}-button`} value={tab} onChange={setTab}
            ariaLabel="Tab master data" tabs={tabs.map(([id, label]) => ({ key: id, label }))} />
        </div>
      </section>
      )}
      {tab === "categories" && <CategoryManager onChanged={loadCategories} />}
      {tab === "integrations" && <div className="grid gap-3"><IntegrationsPanel /><GeminiIntegrationPanel /><OpenAiIntegrationPanel /></div>}
      {/* Audit UI 099 — "Reset Demo Data" (menghapus data) di zona berbahaya terpisah. */}
      {!embedded && onSeedDemo && tab === "integrations" && (
        <section className="section-card mt-3" data-testid="admin-danger-zone">
          <div className="section-head">
            <div className="min-w-0">
              <span className="kicker !text-[#C0392B]">Zona berbahaya</span>
              <h2>Reset data demo</h2>
              <p className="text-[11.5px] text-[#6B6B73]">Menghapus seluruh data lalu mengisi ulang dengan data contoh. Hanya untuk lingkungan uji/demo — tidak bisa dibatalkan.</p>
            </div>
            <button data-testid="admin-seed-demo-button" onClick={onSeedDemo}
              className="ml-auto secondary-button !text-[#C0392B] !border-[#F1CFCB] hover:!bg-[#FDF3F2]"
              title="Hapus semua data & isi ulang dengan data demo (tidak bisa dibatalkan)">
              <RefreshCw size={13} /> Reset Data Demo
            </button>
          </div>
        </section>
      )}
      {tab !== "categories" && tab !== "integrations" && (
      <section className="flex flex-col gap-3">
        {/* FASE P4 — form master data = POP-UP; tombolnya di ATAS daftar. */}
        {tab !== "audit" && (
          <button data-testid="toggle-admin-create-form-button" className="primary-button self-start"
            disabled={tab === "customers" && !canWrite} title={tab === "customers" && !canWrite ? writeBlockHint : undefined}
            onClick={() => setShowCreateForm(true)}>
            <Plus size={14} /> Buat {TAB_SINGULAR[tab] || "Data"}
          </button>
        )}
        {tab === "customers" && !canWrite && <p data-testid="admin-customer-scope-note" className="text-[10.5px] text-[#8C4A00]">{writeBlockHint}</p>}
        {/* D-05 — satu form pelanggan (CRM) dengan isian lengkap; pelanggan lahir di PT header. */}
        {tab === "customers" && (
          <CustomerFormModal open={showCreateForm} editTarget={null} currentUser={currentUser} salesUsers={salesUsers}
            selectedEntity={scopeEntityId} onClose={() => setShowCreateForm(false)}
            onSaved={async () => { setShowCreateForm(false); await onReload?.(); }} />
        )}
        <FormModal
          open={showCreateForm && tab !== "customers"}
          onClose={() => setShowCreateForm(false)}
          title={tab === "audit" ? "Filter Jejak Audit" : editingProductId ? "Ubah Produk" : `Buat ${TAB_SINGULAR[tab] || "Data Master"}`}
          subtitle={tab === "products" ? "Data induk produk. Harga di sini = harga dasar untuk pesanan BARU; pesanan yang sudah dibuat tidak berubah."
            : "Persempit jejak audit berdasarkan pelaku, modul, aksi, dan rentang tanggal."}
          icon={tab === "audit" ? Filter : Plus}
          size="md"
          testId="admin-create-form"
          onSubmit={tab === "audit" ? runAuditFilter : null}
          submitLabel="Terapkan Filter"
          busy={modalBusy}
          submitTestId={tab === "audit" ? "refresh-audit-button" : ""}
        >
          {tab === "products" && (
            <ProductMasterForm
              product={product}
              setProduct={setProduct}
              editingProductId={editingProductId}
              productError={productError}
              saving={savingProduct}
              categoryOptions={categoryOptions}
              salesOwners={salesOwners}
              onSave={saveProduct}
              onCancel={resetProductForm}
              addConv={addConv}
              updateConv={updateConv}
              removeConv={removeConv}
            />
          )}
          {tab === "audit" && <div data-testid="audit-filter-panel" className="grid gap-2">
            <label className="grid gap-1 text-[11px] font-semibold text-[#3C3C43]">Pelaku
              <input data-testid="audit-actor-filter-input" className="field" placeholder="nama / email pelaku" value={auditFilters.actor} onChange={(e) => setAuditFilters({ ...auditFilters, actor: e.target.value })} /></label>
            <label className="grid gap-1 text-[11px] font-semibold text-[#3C3C43]">Modul / entitas
              <input data-testid="audit-module-filter-input" className="field" placeholder="mis. pengguna, pesanan" value={auditFilters.module} onChange={(e) => setAuditFilters({ ...auditFilters, module: e.target.value })} /></label>
            <label className="grid gap-1 text-[11px] font-semibold text-[#3C3C43]">Kunci aksi
              <input data-testid="audit-action-filter-input" className="field" placeholder="mis. masuk, buat" value={auditFilters.action} onChange={(e) => setAuditFilters({ ...auditFilters, action: e.target.value })} /></label>
            <div className="grid grid-cols-2 gap-2">
              <label className="grid gap-1 text-[11px] font-semibold text-[#3C3C43]">Dari tanggal
                <KNDatePicker data-testid="audit-date-from-input" placeholder="Dari" value={auditFilters.date_from} onChange={(v) => setAuditFilters({ ...auditFilters, date_from: v })} /></label>
              <label className="grid gap-1 text-[11px] font-semibold text-[#3C3C43]">Sampai tanggal
                <KNDatePicker data-testid="audit-date-to-input" placeholder="Sampai" min={auditFilters.date_from} value={auditFilters.date_to} onChange={(v) => setAuditFilters({ ...auditFilters, date_to: v })} /></label>
            </div>
          </div>}
        </FormModal>
        <div className="section-card">
          <div className="section-head flex items-center justify-between gap-2">
            <h2>{tab === "audit" ? "Jejak Audit" : `Daftar ${tabLabel[tab] || "Data"}`}</h2>
            {tab === "audit" && (
              <button type="button" data-testid="toggle-admin-create-form-button" className="secondary-button text-[11px]" onClick={() => setShowCreateForm(true)}>
                <Filter size={13} /> Filter
              </button>
            )}
            {tab !== "audit" && (
              <button type="button" data-testid="admin-toggle-import-export" className="secondary-button text-[11px]"
                onClick={() => setShowImportExport((v) => !v)}>
                {showImportExport ? "Tutup Impor / Ekspor" : "Impor / Ekspor CSV"}
              </button>
            )}
          </div>
          <div className="section-body">
          {tab !== "audit" && showImportExport && <div data-testid="admin-import-export-panel" className="mb-3 grid gap-2 rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2.5">
            <p className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Impor / Ekspor massal — {tabLabel[tab] || currentResource}</p>
            <p className="text-[10.5px] text-[#6B6B73]">Unggah CSV/XLSX untuk membuat atau memperbarui banyak baris sekaligus. Gunakan <b>Pratinjau (dry-run)</b> dulu untuk melihat dampaknya tanpa menyimpan.</p>
            {currentResource === "customers" && (
              <p data-testid="admin-import-customer-columns" className="text-[10.5px] text-[#6B6B73]">
                Kolom pelanggan: <b>name</b> (wajib), <b>sales_email</b> atau <b>sales_name</b> (sales penanggung jawab — wajib untuk pelanggan baru),
                code (opsional, unik — kosong = nomor otomatis CUST-xxxx), pic_name, phone, email, city, address, type, npwp.
                Hasil Ekspor CSV memakai format yang sama.
              </p>
            )}
            <input data-testid="admin-import-file-input" className="field" type="file" accept=".csv,.xlsx" onChange={(e) => setImportFile(e.target.files?.[0] || null)} />
            <div className="flex flex-wrap gap-1.5">
              <button data-testid="admin-dry-run-button" className="secondary-button" disabled={importLoading || !importFile} onClick={handleDryRunImport}>{importLoading ? "Memeriksa…" : "Pratinjau (dry-run)"}</button>
              <button data-testid="admin-import-button" className="secondary-button" disabled={!importFile} onClick={() => { onImportMaster(currentResource, importFile, false); setImportPreview(null); }}>Impor</button>
              <button data-testid="admin-export-csv-button" className="secondary-button" onClick={() => onExportMaster(currentResource, "csv")}>Ekspor CSV</button>
              {tab === "products" && (
                <button data-testid="admin-export-yarn-button" className="secondary-button" title="Katalog benang + kode versi supplier — untuk dibagikan ke pabrik"
                  onClick={() => onExportMaster("yarn", "csv")}>Ekspor Katalog Benang</button>
              )}
            </div>
            {importPreview && (
              <div data-testid="import-preview-result" className="rounded-md border border-[#EFF0F2] bg-white p-2 text-[11.5px]">
                <p className="font-bold mb-1">Pratinjau: {importPreview.total} baris</p>
                <p className="text-green-700 inline-flex items-center gap-1"><Check size={12} /> Akan dibuat: {importPreview.created}</p>
                <p className="text-blue-700">~ Akan diperbarui: {importPreview.updated}</p>
                {(importPreview.errors || []).length > 0 && (
                  <div className="mt-1 max-h-24 overflow-auto">
                    <p className="text-red-700 font-bold inline-flex items-center gap-1"><AlertTriangle size={12} /> {importPreview.errors.length} galat:</p>
                    {(importPreview.errors || []).map((e, i) => <p key={i} className="text-red-600 text-[10.5px]">{e}</p>)}
                  </div>
                )}
                <button data-testid="confirm-import-button" className="mt-1 primary-button text-[11px]" onClick={() => { onImportMaster(currentResource, importFile, false); setImportPreview(null); }}>Konfirmasi Impor</button>
              </div>
            )}
          </div>}
          {tab === "audit" && <AdminAuditList auditLogs={auditLogs} scopeEntities={scopeEntities} onShowDetail={onShowDetail} />}
          {tab !== "audit" && (
          <div className="grid gap-2">
            {tab === "products" && (
              <>
                <input data-testid="admin-products-search" className="field mb-1" value={productQuery}
                  onChange={(e) => setProductQuery(e.target.value)}
                  placeholder="Cari SKU / nama produk atau kode / nama versi supplier…" />
                <LineFilter value={lineFilter} onChange={setLineFilter} storageKey="admin-products"
                            allowed={currentUser?.allowed_line_codes} className="mb-1"
                            testId="admin-products-line-filter" />
              </>
            )}
            {tab !== "products" && (
              <input data-testid="admin-records-search" className="field mb-1" value={recordQuery}
                onChange={(e) => setRecordQuery(e.target.value)} placeholder={`Cari ${(tabLabel[tab] || tab).toLowerCase()}…`} />
            )}
            {visibleRecords.length === 0 && (
              <div data-testid={`admin-records-empty-${tab}`} className="px-3 py-8 text-center text-[12px] text-[#6B6B73]">Belum ada {(tabLabel[tab] || tab).toLowerCase()} {scopeSuffix(scopeEntities, scopeEntityId)}.</div>
            )}
            {visibleRecords.map((row) => (
              <div data-testid={`admin-record-${tab}-${row.id}`} key={row.id} role="button" tabIndex={0} className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] interactive-card flex flex-col gap-2 p-2.5 md:flex-row md:items-center md:justify-between" onClick={() => onShowDetail(tab === "products"
                ? {
                    title: row.name,
                    body: `${row.sku || "SKU —"}${row.category ? ` · ${row.category}` : ""}${row.variant ? ` · ${row.variant}` : ""}${row.description ? ` — ${row.description}` : ""}`,
                    facts: [
                      { label: "Harga Jual", value: Number(row.price) > 0 ? `${formatCurrency(row.price)} / ${row.base_unit || "unit"}` : "Belum diisi" },
                      { label: "HPP (dari pembelian)", value: Number(row.hpp) > 0 ? `${formatCurrency(row.hpp)} / ${row.base_unit || "unit"}` : "Belum ada penerimaan PO" },
                      { label: "Lini · Grade", value: `${row.line_code ? `Lini ${row.line_code}` : "Lini belum diisi"} · Grade ${row.grade || "—"}` },
                      { label: "Spesifikasi", value: row.stage === "yarn"
                        ? [row.yarn_count ? `${row.yarn_count}${row.yarn_count_system ? ` ${row.yarn_count_system}` : ""}` : null, row.yarn_material, row.yarn_ply ? `${row.yarn_ply} ply` : null, row.yarn_twist ? `puntiran ${row.yarn_twist}` : null, row.yarn_dye_status].filter(Boolean).join(" · ") || "benang —"
                        : [row.fabric_type, Number(row.gramasi) > 0 ? `${row.gramasi} gsm` : null, Number(row.lebar) > 0 ? `lebar ${row.lebar}` : null].filter(Boolean).join(" · ") || "—" },
                      { label: "Status", value: `${statusLabel(row)} · tahap ${row.stage || "finished"}` },
                    ],
                  }
                : masterDetail(row))}>
                <div className="min-w-0">
                  <p data-testid={`admin-record-title-${row.id}`} className="text-[12.5px] font-semibold truncate">{row.name || row.legal_name || row.code || row.email}</p>
                  <p data-testid={`admin-record-meta-${row.id}`} className="text-[11px] text-[#3C3C43] truncate">
                    {row.sku || row.code || row.role || row.short_name || row.city} • <span className={isInactive(row) ? "text-[#8E8E93]" : "text-[#1A7A3A]"}>{statusLabel(row)}</span>{tab === "products" ? supplierCodesLabel(row) : ""}
                  </p>
                  {tab === "products" && (
                    <div data-testid={`admin-product-domain-${row.id}`} className="mt-1 flex flex-wrap items-center gap-1">
                      <ProductLifecycleCell product={row}
                        canManage={row.spec_id ? can(currentUser?.permissions, "rnd", "decide") : can(currentUser?.permissions, "product", "update")}
                        onPatch={(id, patch) => onAdminPatch("products", id, patch)}
                        onDone={onReload} />
                      <span className="status-pill pill-muted">{row.stage || "finished"}</span>
                      <span className="status-pill pill-muted">{row.fabric_type || "fabric_type?"}</span>
                      {/* FASE L — lini kerja MD; warnanya dibedakan dari `fabric_type`. */}
                      <span data-testid={`admin-product-line-${row.id}`} className="status-pill"
                        style={row.line_code ? { background: "#EFF4FF", color: "#0058CC" } : { background: "#F5F5F7", color: "#8E8E93" }}>
                        {row.line_code ? `Lini ${row.line_code}` : "Lini belum diisi"}
                      </span>
                      <span className="status-pill pill-success">Grade {row.grade || "—"}</span>
                      {Number(row.gramasi) > 0 && <span className="status-pill pill-muted tabular-nums">{row.gramasi} gsm</span>}
                      {row.needs_review && (
                        <span data-testid={`admin-product-needs-review-${row.id}`} className="status-pill pill-warning">
                          <AlertTriangle size={10} /> Perlu dilengkapi
                        </span>
                      )}
                      {row.exclusivity === "sales_tertentu" && (
                        <span data-testid={`admin-product-exclusive-${row.id}`} className="status-pill" style={{ background: "#EDE6FB", color: "#6D4AC0" }}>
                          Eksklusif · {(row.owner_sales_ids || []).length} sales
                        </span>
                      )}
                    </div>
                  )}
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {tab === "products" && <button data-testid={`admin-edit-products-${row.id}-button`} className="secondary-button" onClick={(e) => { e.stopPropagation(); loadProductForEdit(row); window.scrollTo({ top: 0, behavior: "smooth" }); }}>Ubah</button>}
                  {tab !== "products" && isInactive(row) && <button data-testid={`admin-update-${tab}-${row.id}-button`} className="secondary-button" onClick={(e) => { e.stopPropagation(); onAdminPatch(tab, row.id, { status: "active" }); }}>Aktifkan</button>}
                  {!isInactive(row) && <button data-testid={`admin-delete-${tab}-${row.id}-button`} className="secondary-button !border-[#F1CFCB] !text-[#C0392B] hover:!border-[#E3A9A3] hover:!bg-[#FDF3F2]" onClick={(e) => { e.stopPropagation(); onAdminDelete(tab, row.id); }}>Nonaktifkan</button>}
                </div>
              </div>
            ))}
          </div>
          )}
          </div>
        </div>
      </section>
      )}
    </div>
  );
}
