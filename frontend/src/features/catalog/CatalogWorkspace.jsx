import ProductColorTriad from "../../components/ProductColorTriad";
import { useCallback, useEffect, useState } from "react";
import { ArrowUpRight, ChevronLeft, ChevronRight, Images, Layers3, Link2, MoreHorizontal, Package, Pencil, Plus, Wrench } from "lucide-react";
import { ListToolbar, PageHeader, SearchInput } from "../../components/ListPageParts";
import { DetailHeader } from "../../components/DetailParts";
import StatusBadge from "../../components/StatusBadge";
import { ProductGallery } from "../../components/ProductGallery";
import { formatCurrency } from "../../utils/formatters";
import { askConfirm } from "../../services/confirmService";
import { openConfig } from "../settings/config/configDeepLink";
import { openRnd } from "../rnd/rndDeepLink";
import { catalogApi, catalogChanged, catalogError } from "./catalogApi";
import { FamilyForm } from "./FamilyForm";
import { GenerateVariants } from "./GenerateVariants";
import { VariantEditor } from "./VariantEditor";
import { VariantMedia } from "./VariantMedia";
import { ProductRelations } from "./ProductRelations";
import { LinkExistingVariant } from "./LinkExistingVariant";
import { FamilyHero } from "./FamilyHero";
import FamilyDesignBar from "./FamilyDesignBar";
import { VariantCard } from "./VariantCard";
import { VariantHeader } from "./VariantHeader";
import { FamilyInfoTab } from "./FamilyInfoTab";
import AuditHistoryPanel from "../../components/AuditHistoryPanel";
import { CatalogFilters, emptyCatalogFilters } from "./CatalogFilters";
import { CatalogMenu } from "./CatalogMenu";
import MasterDataTools, { availableTools } from "./MasterDataTools";   // M20 — alat admin data master (bukan layar kerja)
import FamilyRoutesTab from "./FamilyRoutesTab";   // MP-T1 — rute produk per artikel per PT
import axios, { API } from "../../services/apiClient";
import { can } from "../../config/roles";
import { axesText, useCatalogLabels } from "./catalogLabels";   // G4-19
import "./catalog.css";

const PAGE = 24;

/**
 * Produk & Varian — katalog induk produk (artikel) + rincian induk.
 *
 * Pola UI 16 Nov (`docs/blueprint/04_POLA_UI.md`; masukan pemilik M20 "sangat kacau sekali, hancur" & M22 "UI rincian
 * per produk masih sangat kacau"):
 *  · DAFTAR (templat A): kepala satu baris (+ ?), SATU bilah daftar = cari · saringan dropdown · jumlah · "Alat data
 *    master ▾" · "+ Tambah produk". Alat admin (Data SKU & impor, tata kelola/preview legacy, lembar kerja perbaikan,
 *    sumber restock) tidak lagi terbuka di atas katalog — pindah ke halaman `MasterDataTools`, hanya untuk pemegang
 *    izinnya (syarat sama dengan dulu).
 *  · RINCIAN (templat C): kepala = nama · prefix SKU · status · aksi (aksi jarang di "Lainnya ▾"); ringkasan tanpa
 *    kartu angka kosong; label tahap/jenis kain ringkas; peringatan mutu data satu baris kecil bertautan perbaikan.
 */
export default function CatalogWorkspace({ currentUser, selectedEntity, focus, legacyView }) {
  const { fabricShort, stageShort } = useCatalogLabels();   // G4-19 / M22 — label manusia (bukan "woven")
  const [meta, setMeta] = useState(null); const [items, setItems] = useState([]); const [total, setTotal] = useState(0);
  const [query, setQuery] = useState(""); const [page, setPage] = useState(0); const [loading, setLoading] = useState(true);
  const [family, setFamily] = useState(null); const [selectedId, setSelectedId] = useState(""); const [summary, setSummary] = useState(null);
  const [error, setError] = useState(""); const [notice, setNotice] = useState(""); const [modal, setModal] = useState(""); const [tab, setTab] = useState("variants");
  const [tool, setTool] = useState("");
  const [filters, setFilters] = useState(emptyCatalogFilters); const [suppliers, setSuppliers] = useState([]);
  useEffect(() => { axios.get(`${API}/suppliers`).then(r => setSuppliers(Array.isArray(r.data) ? r.data : r.data?.items || [])).catch(() => setSuppliers([])); }, []);
  // PR-T7 (#9) — hapus permanen master = `product.view` + `product.retire` (DELETE /master/{kind}/{id}/purge → may_retire).
  const canPurge = can(currentUser?.permissions, "product", "view") && can(currentUser?.permissions, "product", "retire");
  const caps = meta?.permissions || {};
  const canAudit = can(currentUser?.permissions, "audit", "view");
  const canExport = can(currentUser?.permissions, "product", "export");
  const toolAccess = { canUpdate: !!caps.update, canExport, hasLegacy: !!legacyView };
  const tools = availableTools(toolAccess);
  const load = useCallback(async () => { setLoading(true); setError(""); try { const [m, d] = await Promise.all([catalogApi.meta(), catalogApi.list({ search: query, offset: page * PAGE, limit: PAGE, paginate: true, ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) })]); setMeta(m); setItems(d.items); setTotal(d.total); } catch (e) { setError(catalogError(e)); } finally { setLoading(false); } }, [query, page, selectedEntity, filters]);
  useEffect(() => { const t = setTimeout(load, 200); return () => clearTimeout(t); }, [load]);
  const open = useCallback(async (id, pid = "") => { setTool(""); setError(""); setSummary(null); try { const d = await catalogApi.detail(id); setFamily(d); setSelectedId(pid || d.variants[0]?.id || ""); const s = await catalogApi.summary(id); setSummary(s); } catch (e) { setError(catalogError(e)); } }, []);
  useEffect(() => { setFamily(null); setSelectedId(""); setSummary(null); }, [selectedEntity]);
  useEffect(() => { if (focus?.templateId) open(focus.templateId, focus.productId); }, [focus, open]);
  const refresh = async () => { catalogChanged(); await load(); if (family) await open(family.id, selectedId); };
  const selected = family?.variants.find(v => v.id === selectedId) || family?.variants[0];
  const stock = summary?.variants.find(v => v.id === selected?.id);
  const pages = Math.max(1, Math.ceil(total / PAGE));

  if (tool && tools.some(t => t.key === tool)) return <MasterDataTools tool={tool} access={toolAccess} legacyView={legacyView} onTool={setTool} onBack={() => { setTool(""); load(); }} />;

  const alerts = <>
    {error && <div data-testid="catalog-error" role="alert" className="catalog-alert error">{error}<button type="button" data-testid="catalog-retry" className="secondary-button btn-sm" onClick={load}>Coba lagi</button></div>}
    {notice && <div data-testid="catalog-notice" role="status" className="catalog-alert">{notice}<button type="button" data-testid="catalog-dismiss-notice" onClick={() => setNotice("")} className="link-button">Tutup</button></div>}
  </>;

  return <div className="kn-catalog" data-testid="catalog-workspace">
    {!family ? <>
      {/* Templat A — kepala SATU baris; keterangan di "?" (dulu subjudul + tombol "Data SKU & impor" & "Produk baru"
          di kepala, jauh dari daftarnya). */}
      <PageHeader icon={Layers3} testId="catalog-heading"
        title={<span data-testid="catalog-title">Produk &amp; varian</span>}
        help="Katalog bersama: induk produk (artikel) beserta variannya (SKU). Buka satu induk untuk melihat varian, foto, informasi, rute, dan riwayat perubahannya. Pemegang izin ubah/ekspor produk membuka alat admin data (Data SKU & impor, tata kelola, lembar kerja perbaikan, sumber restock) lewat tombol “Alat data master”." />
      {alerts}
      <ListToolbar testId="catalog-toolbar" actions={<>
        <CatalogMenu testId="catalog-tools" label="Alat data master" labelClass="hidden 2xl:inline" icon={Wrench} title="Alat data master — alat admin data produk (hanya pemegang izin)"
          items={tools.map(t => ({ key: t.key, label: t.label, hint: t.hint, icon: t.icon, testId: t.testId, onSelect: () => setTool(t.key) }))} />
        {caps.create && <button type="button" data-testid="catalog-create" className="primary-button" onClick={() => setModal("create")}><Plus size={14} />Tambah produk</button>}
      </>}>
        <SearchInput testId="catalog-search" placeholder="Cari nama, kategori, prefix SKU…" ariaLabel="Cari produk, kategori, atau prefix SKU" value={query}
          onChange={v => { setPage(0); setQuery(v); }} className="min-w-[200px] flex-1 !max-w-[240px]" />
        <CatalogFilters value={filters} suppliers={suppliers} allowedLines={currentUser?.allowed_line_codes} onChange={f => { setPage(0); setFilters(f); }} />
        <span data-testid="catalog-result-count" className="whitespace-nowrap text-fs-12 text-kn-text-2">{total} produk</span>
      </ListToolbar>
      {loading ? <div className="catalog-grid" data-testid="catalog-loading">{[0, 1, 2, 3].map(i => <div key={i} className="h-72 animate-pulse rounded-lg bg-kn-neutral-soft" />)}</div>
        : !items.length ? <div data-testid="catalog-empty" className="catalog-empty"><Layers3 size={36} strokeWidth={1} /><h2>{error ? "Daftar produk gagal dimuat" : `Belum ada produk${query || Object.values(filters).some(Boolean) ? " yang cocok" : ""}`}</h2>{!error && caps.create && <button type="button" data-testid="catalog-empty-create" className="primary-button" onClick={() => setModal("create")}><Plus size={14} />Buat induk produk</button>}</div>
        : <div className="catalog-grid" data-testid="catalog-grid">{items.map(t => <article key={t.id} data-testid={`catalog-card-${t.id}`} className="catalog-card">
          <div className="catalog-card-media"><ProductGallery product={t.cover_product || { name: t.name, image: t.image }} compact testId={`card-gallery-${t.id}`} /><span data-testid={`catalog-variant-count-${t.id}`} className="catalog-count">{t.variant_count} varian</span></div>
          <button type="button" data-testid={`catalog-open-${t.id}`} className="catalog-card-content" onClick={() => { setTab("variants"); open(t.id); }}><span className="catalog-category" data-testid={`catalog-category-${t.id}`}>{[t.category, fabricShort(t.fabric_type)].filter(Boolean).join(" · ") || "—"}</span><h2 data-testid={`catalog-name-${t.id}`}>{t.name}</h2><span className="catalog-axis-label" data-testid={`catalog-axes-${t.id}`}>{axesText(t.axes) || "Satu varian"}</span><span className="catalog-card-bottom"><strong data-testid={`catalog-price-${t.id}`}>{formatCurrency(t.price_min || 0)}{t.price_max > t.price_min ? ` – ${formatCurrency(t.price_max)}` : ""}</strong><ArrowUpRight size={17} /></span></button>
        </article>)}</div>}
      {pages > 1 && <footer className="catalog-pagination"><button type="button" data-testid="catalog-prev" className="secondary-button btn-sm" disabled={!page} onClick={() => setPage(page - 1)}><ChevronLeft size={14} />Sebelumnya</button><span data-testid="catalog-page">{page + 1} / {pages}</span><button type="button" data-testid="catalog-next" className="secondary-button btn-sm" disabled={(page + 1) * PAGE >= total} onClick={() => setPage(page + 1)}>Berikutnya<ChevronRight size={14} /></button></footer>}
    </> : <>
      {/* Templat C — kepala rincian: nama · prefix SKU · status · aksi. "Tautkan SKU lama" (jarang) di "Lainnya ▾". */}
      <DetailHeader onBack={() => { setFamily(null); setSelectedId(""); }} backLabel="Semua produk" backTestId="catalog-back"
        icon={Package} iconClass="text-kn-action" title={family.name} titleTestId="catalog-title"
        badges={<>
          {family.sku_prefix && <code data-testid="catalog-sku-prefix" className="catalog-prefix">{family.sku_prefix}</code>}
          <StatusBadge testId="catalog-status" status={family.status === "archived" ? "archived" : "active"}
            label={family.status === "archived" ? "Diarsipkan" : "Aktif"} />
        </>}
        subtitle={<span data-testid="catalog-subtitle">{[family.category, stageShort(family.stage), fabricShort(family.fabric_type)].filter(Boolean).join(" · ")}</span>}
        actions={<>
          {caps.update && <button type="button" data-testid="catalog-edit-family" className="secondary-button" onClick={() => setModal("edit")}><Pencil size={14} />Ubah induk</button>}
          {caps.create && <button type="button" data-testid="catalog-generate" className="primary-button" onClick={() => setModal(family.axes?.length ? "generate" : "new-variant")}><Plus size={15} />Tambah varian</button>}
          <CatalogMenu testId="catalog-more" label="Lainnya" icon={MoreHorizontal} items={[
            caps.update && { key: "link", label: "Tautkan SKU lama", hint: "Masukkan SKU yang sudah ada ke induk ini tanpa mengganti ID & dokumennya", icon: Link2, testId: "catalog-link-existing", onSelect: () => setModal("link") },
          ]} />
        </>} />
      {alerts}
      <FamilyHero family={family} summary={summary}>
        <FamilyDesignBar family={family} canEdit={!!caps.update} onChanged={refresh} />
      </FamilyHero>
      <div className="catalog-tabs" role="tablist">{[["variants", "Varian & galeri", family.variant_count], ["info", "Informasi produk", null], ["routes", "Rute", null], ...(caps.rnd_view ? [["rnd", "R&D & asal desain", null]] : []), ...(canAudit ? [["history", "Riwayat Perubahan", null]] : [])].map(([k, l, n]) => <button type="button" key={k} data-testid={`catalog-tab-${k}`} role="tab" aria-selected={tab === k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>{l}{n ? <span className="tab-count">{n}</span> : null}</button>)}</div>
      {tab === "routes" ? <FamilyRoutesTab family={family} currentUser={currentUser} selectedEntity={selectedEntity} /> : tab === "info" ? <FamilyInfoTab family={family} caps={caps} summary={summary} onPolicy={() => openConfig({ group: "rnd", key: "rnd.new_product_default_lifecycle" })} onArchive={async () => { if (!await askConfirm({ title: "Arsipkan induk ini?", message: family.name, confirmLabel: "Arsipkan", danger: true })) return; try { await catalogApi.archive(family.id); setFamily(null); load(); } catch (e) { setError(catalogError(e)); } }} /> : <div className="catalog-detail-grid">
        <aside className="catalog-variant-list"><div className="variant-list-head"><h2 data-testid="catalog-variant-list-title">Kombinasi varian</h2><span>{family.variants.length} SKU</span></div>{family.variants.map(v => <VariantCard key={v.id} variant={v} active={selected?.id === v.id} stock={summary?.variants.find(s => s.id === v.id)} onSelect={() => setSelectedId(v.id)} />)}{!family.variants.length && <p data-testid="catalog-no-variants" className="text-fs-13 text-kn-text-2">Belum ada SKU.</p>}{caps.create && !!family.axes?.length && <button type="button" data-testid="catalog-add-single" className="secondary-button btn-sm mt-1 w-full justify-center" onClick={() => setModal("new-variant")}><Plus size={13} />Satu kombinasi</button>}</aside>
        <div className="min-w-0">{selected ? <>
          <VariantHeader family={family} selected={selected} stock={stock} canUpdate={!!caps.update} canPurge={canPurge} onEdit={() => setModal("variant")} onPurged={refresh} />
          <ProductColorTriad product={selected} compact />
          {tab === "history" && canAudit ? <AuditHistoryPanel key={selected.id} entityType="product" entityId={selected.id} testIdPrefix="catalog-history" /> : tab === "rnd" ? <ProductRelations product={selected} caps={caps} onCreate={() => openRnd({ view: "rnd-specs", create: true, templateId: family.id, productId: selected.id })} /> : <VariantMedia key={`${selected.id}:${selectedEntity}`} product={selected} meta={meta} onChanged={refresh} />}
        </> : <div className="catalog-empty" data-testid="catalog-detail-empty"><Images size={30} strokeWidth={1} /><p>Tambahkan varian untuk mulai mengelola SKU dan fotonya.</p></div>}</div>
      </div>}
    </>}
    {["create", "edit"].includes(modal) && <FamilyForm template={modal === "edit" ? family : null} axisConfig={meta?.variant_axes} onClose={() => setModal("")} onSaved={async id => { setModal(""); setNotice("Induk produk tersimpan."); await load(); await open(id); }} />}
    {modal === "generate" && family && <GenerateVariants template={family} onClose={() => setModal("")} onDone={async r => { setModal(""); setNotice(`${r.created} SKU dibuat${r.skipped ? `; ${r.skipped} kombinasi sudah ada` : ""}.`); await refresh(); }} />}
    {modal === 'link' && family && <LinkExistingVariant template={family} onClose={() => setModal('')} onSaved={async () => { setModal(''); setNotice('SKU tertaut tanpa mengganti ID dan dokumennya.'); await refresh(); }} />}
    {["variant", "new-variant"].includes(modal) && family && <VariantEditor template={family} product={modal === "variant" ? selected : null} onClose={() => setModal("")} onSaved={async () => { setModal(""); setNotice("SKU tersimpan."); await refresh(); }} />}
  </div>;
}
