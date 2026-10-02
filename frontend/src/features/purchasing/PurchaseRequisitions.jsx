import MoneyInput from "../../components/MoneyInput";
import KNDatePicker from "@/components/KNDatePicker";
import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import {
  ClipboardList, Plus, ArrowLeft, Trash2, CheckCircle2, XCircle, Send,
  ShoppingCart, RefreshCw, AlertTriangle, Ban, Clock, FileText, Loader2,
} from "lucide-react";
import { formatCurrency, formatQty } from "../../utils/formatters";
import KNSelect from "../../components/KNSelect";
import { supplierKeywords } from "../../utils/productSearch";   // MD-08
import { DualName } from "../../components/DualName";
import ErrorNotice from "../../components/ErrorNotice";
import LineFilter from "../../components/LineFilter";   // FASE L
import { PageHeader, MetricRow, SearchBox, StatusTabs } from "../../components/ListPageParts";
import { SOURCE_LABEL, StatusPill } from "./prConstants";
import { GroupEntityNotice, isGroupEntityPartner, supplierOptionLabel }
  from "../../components/GroupEntityBadge";
import { FULFILLMENT_OPTIONS } from "./supplier-items/supplierItemsApi";
import DetailPanel from "./PurchaseRequisitionDetailPanel";

/**
 * Purchase Requisitions (Depth #2a) — Hulu procurement.
 * PR → approval (matriks 'purchase_requisition') → konversi ke PO.
 * Sumber: manual | reorder | special_order.
 */

export default function PurchaseRequisitions({ currentUser, selectedEntity = "all", focusDoc, onClearFocus }) {
  const [view, setView] = useState("list");            // list | create | detail
  const [items, setItems] = useState([]);
  const [byStatus, setByStatus] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);

  // master data
  const [products, setProducts] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [suppliers, setSuppliers] = useState([]);

  const role = currentUser?.role;
  const canApprove = role === "admin" || role === "manager";

  useEffect(() => { loadMasters(); }, []);             // eslint-disable-line
  const [lineFilter, setLineFilter] = useState("");   // FASE L
  useEffect(() => { load(); }, [statusFilter, selectedEntity, lineFilter]); // eslint-disable-line

  async function loadMasters() {
    try {
      const [p, w, s] = await Promise.all([
        axios.get(`${API}/products`).catch(() => ({ data: [] })),
        axios.get(`${API}/warehouses`).catch(() => ({ data: [] })),
        axios.get(`${API}/suppliers`).catch(() => ({ data: [] })),
      ]);
      setProducts(Array.isArray(p.data) ? p.data : (p.data?.items || []));
      setWarehouses(Array.isArray(w.data) ? w.data : (w.data?.items || []));
      setSuppliers(Array.isArray(s.data) ? s.data : (s.data?.items || []));
    } catch (e) { /* non-blocking */ }
  }

  async function load() {
    setLoading(true);
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      if (lineFilter) params.line = lineFilter;          // FASE L — disaring di server
      const res = await axios.get(`${API}/purchase-requisitions`, { params });
      setItems(res.data?.items || []);
      setByStatus(res.data?.by_status || {});
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat Purchase Requisition.");
    } finally {
      setLoading(false);
    }
  }

  function flash(msg) { setToast(msg); setTimeout(() => setToast(""), 3500); }

  // Deep-link dari Meja MD → langsung buka PR yang diklik.
  useEffect(() => {
    if (focusDoc?.focus_type === "purchase_requisition" && focusDoc.focus_id) {
      openDetail(focusDoc.focus_id);
      onClearFocus?.();
    }
  }, [focusDoc?.focus_id]); // eslint-disable-line

  async function openDetail(id) {
    try {
      const res = await axios.get(`${API}/purchase-requisitions/${id}`);
      setSelected(res.data); setView("detail");
    } catch (e) { flash(e.response?.data?.detail || "Gagal memuat detail PR."); }
  }

  const tabs = [
    { key: "", label: "Semua" },
    { key: "draft", label: "Draf" },
    { key: "pending_approval", label: "Menunggu Persetujuan" },
    { key: "approved", label: "Disetujui" },
    { key: "converted", label: "Jadi PO" },
    { key: "rejected", label: "Ditolak" },
  ];

  if (view === "create") {
    return (
      <CreateForm
        products={products} warehouses={warehouses} suppliers={suppliers}
        selectedEntity={selectedEntity}
        onCancel={() => setView("list")}
        onCreated={(pr) => { flash(`${pr.number} dibuat.`); setView("list"); load(); }}
      />
    );
  }

  if (view === "detail" && selected) {
    return (
      <DetailPanel
        pr={selected} canApprove={canApprove} suppliers={suppliers} warehouses={warehouses}
        onBack={() => { setSelected(null); setView("list"); load(); }}
        onChanged={(msg) => { flash(msg); }}
        reload={openDetail}
      />
    );
  }

  const q = search.trim().toLowerCase();
  const shown = !q ? items : items.filter((pr) => [pr.number, pr.warehouse_name, ...(pr.items || []).map((it) => it.product_name)]
    .some((v) => (v || "").toLowerCase().includes(q)));
  const total = Object.values(byStatus).reduce((a, b) => a + (b || 0), 0) || items.length;

  return (
    <div data-testid="purchase-requisitions-view" className="view-container">
      {toast && <div className="notice-bar success" data-testid="pr-toast"><span>{toast}</span><button onClick={() => setToast("")}>×</button></div>}
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="pr-error" />

      <PageHeader icon={ClipboardList} title={<span data-testid="pr-title">Permintaan Pembelian (PR)</span>}
        subtitle="Kebutuhan barang dari gudang, saran reorder, atau pesanan khusus — disetujui dulu, lalu dikonversi menjadi PO."
        actions={<>
          <button data-testid="pr-refresh" className="secondary-button" onClick={load} aria-label="Muat ulang">
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Muat ulang
          </button>
          <button data-testid="pr-create-btn" className="primary-button" onClick={() => setView("create")}>
            <Plus size={14} /> PR Baru
          </button>
        </>} />

      <MetricRow testId="pr-metrics" items={[
        { label: "Total PR", value: total, icon: ClipboardList, hint: "semua status", testId: "pr-metric-total" },
        { label: "Menunggu Persetujuan", value: byStatus.pending_approval || 0, icon: Clock, testId: "pr-metric-pending" },
        { label: "Disetujui", value: byStatus.approved || 0, icon: CheckCircle2, testId: "pr-metric-approved" },
        { label: "Jadi PO", value: byStatus.converted || 0, icon: FileText, testId: "pr-metric-converted" },
      ]} />

      <SearchBox value={search} onChange={setSearch} testId="pr-search" placeholder="Cari no. PR / barang / gudang…">
        <LineFilter value={lineFilter} onChange={setLineFilter} storageKey="purchase-requisitions"
                    allowed={currentUser?.allowed_line_codes} testId="pr-line-filter" />
      </SearchBox>
      <StatusTabs value={statusFilter} onChange={setStatusFilter} testId={(k) => `pr-tab-${k || "all"}`}
        tabs={tabs.map((t) => ({ ...t, count: t.key ? byStatus[t.key] : 0 }))} />

      {loading ? (
        <div data-testid="pr-loading" className="loading-state"><Loader2 size={22} className="spin" /><p>Memuat permintaan pembelian…</p></div>
      ) : shown.length === 0 ? (
        <div data-testid="pr-empty" className="empty-state">
          <ClipboardList size={30} style={{ opacity: 0.3 }} />
          <p className="font-semibold">{q || statusFilter ? "Tidak ada PR yang cocok dengan filter ini." : "Belum ada Permintaan Pembelian."}</p>
          <p className="text-sm text-muted">Klik <b>PR Baru</b> untuk mengajukan kebutuhan barang.</p>
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table" style={{ minWidth: 860 }}>
            <thead>
              <tr><th>Nomor</th><th>Barang / Gudang</th><th>Sumber</th><th className="text-right">Estimasi</th><th>Status</th><th className="text-right">Aksi</th></tr>
            </thead>
            <tbody>
              {shown.map((pr) => (
                <tr key={pr.id} data-testid={`pr-row-${pr.id}`} className="cursor-pointer" onClick={() => openDetail(pr.id)}>
                  <td><span className="font-mono font-semibold">{pr.number}</span></td>
                  <td className="max-w-[420px]">
                    <p className="truncate font-medium">{pr.items?.[0]?.product_name || "-"}{pr.items?.length > 1 ? ` +${pr.items.length - 1}` : ""}</p>
                    <p className="text-xs text-muted">{pr.warehouse_name || "—"}</p>
                  </td>
                  <td><span className="feature-badge">{SOURCE_LABEL[pr.source] || String(pr.source || "—").replace(/_/g, " ")}</span></td>
                  <td className="text-right font-semibold tabular-nums">{formatCurrency(pr.total_est_amount)}</td>
                  <td><StatusPill status={pr.status} /></td>
                  <td className="text-right" onClick={(e) => e.stopPropagation()}>
                    <button data-testid={`pr-open-${pr.id}`} className="link-button" onClick={() => openDetail(pr.id)}>Detail →</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


// ─── Create Form ─────────────────────────────────────────────────────────────
function CreateForm({ products, warehouses, suppliers, selectedEntity, onCancel, onCreated }) {
  const [lines, setLines] = useState([]);
  const [warehouseId, setWarehouseId] = useState("");
  const [supplierId, setSupplierId] = useState("");
  const [reason, setReason] = useState("");
  const [neededBy, setNeededBy] = useState("");
  const [submitNow, setSubmitNow] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [pickProduct, setPickProduct] = useState("");
  const [pickArticle, setPickArticle] = useState("");
  const [templates, setTemplates] = useState([]);
  const [eligible, setEligible] = useState(null);
  const [showAllSup, setShowAllSup] = useState(false);
  useEffect(() => {
    axios.get(`${API}/product-templates`, { params: { limit: 500 } })
      .then((r) => setTemplates(Array.isArray(r.data) ? r.data : (r.data?.items || []))).catch(() => setTemplates([]));
  }, []);
  const active = useMemo(() => products.filter((p) => p.status !== "inactive"), [products]);
  const articleOptions = useMemo(() => articleOptionsOf(active, templates), [active, templates]);
  const colorOptions = useMemo(() => colorOptionsOf(active, pickArticle), [active, pickArticle]);
  const lineKey = lines.map((l) => l.product_id).join(",");
  useEffect(() => {
    if (!lineKey) { setEligible(null); return; }
    axios.get(`${API}/purchase-requisitions/eligible-suppliers`, { params: { product_ids: lineKey } })
      .then((r) => setEligible(r.data)).catch(() => setEligible(null));
  }, [lineKey]);
  const supplierChoices = useMemo(() => {
    if (!eligible || showAllSup) return suppliers;
    const ok = new Set(eligible.common || []);
    return suppliers.filter((s) => ok.has(s.id));
  }, [suppliers, eligible, showAllSup]);
  const noEligible = !!eligible && !showAllSup && supplierChoices.length === 0;

  const total = useMemo(() => lines.reduce((s, l) => s + (Number(l.est_price) || 0) * (Number(l.quantity) || 0), 0), [lines]);
  // FASE E-7 (E7.2) — pemasok terpilih dipakai untuk lencana + mematikan tombol Simpan.
  const selectedSupplier = useMemo(
    () => suppliers.find((s) => s.id === supplierId) || null, [suppliers, supplierId]);
  const supplierIsGroupEntity = isGroupEntityPartner(selectedSupplier);

  function addLine() {
    const p = products.find((x) => x.id === pickProduct);
    if (!p) return;
    if (lines.some((l) => l.product_id === p.id)) { setErr("Produk sudah ditambahkan."); return; }
    setLines([...lines, {
      product_id: p.id, sku: p.sku, product_name: p.name, supplier_alias: p.supplier_alias,
      kn_color: p.color_name || p.variant_attrs?.color || "",
      quantity: p.reorder_qty || 100, unit: p.base_unit || "meter",
      est_price: p.harga_pokok || p.price || 0,
      fulfillment_mode: "purchase",
    }]);
    setPickProduct(""); setPickArticle(""); setErr("");
  }
  function updLine(i, k, v) { setLines(lines.map((l, idx) => idx === i ? { ...l, [k]: v } : l)); }
  function rmLine(i) { setLines(lines.filter((_, idx) => idx !== i)); }

  async function submit() {
    if (lines.length === 0) { setErr("Tambahkan minimal satu item."); return; }
    if (!warehouseId) { setErr("Pilih gudang tujuan."); return; }
    setBusy(true); setErr("");
    try {
      const payload = {
        items: lines.map((l) => ({
          product_id: l.product_id, quantity: Number(l.quantity), unit: l.unit,
          est_price: Number(l.est_price), fulfillment_mode: l.fulfillment_mode || "purchase",
          // FASE U — kosong dikirim sebagai `null` (BUKAN 0): "tidak menyebut jumlah
          // roll" berbeda arti dari "nol gulungan".
          qty_rolls: (l.qty_rolls === "" || l.qty_rolls === null || l.qty_rolls === undefined)
            ? null : Math.max(0, parseInt(l.qty_rolls, 10) || 0),
        })),
        warehouse_id: warehouseId,
        entity_id: selectedEntity && selectedEntity !== "all" ? selectedEntity : "",
        preferred_supplier_id: supplierId,
        reason, needed_by_date: neededBy, source: "manual", submit_now: submitNow,
      };
      const res = await axios.post(`${API}/purchase-requisitions`, payload);
      onCreated(res.data);
    } catch (e) {
      setErr(e.response?.data?.detail || "Gagal membuat PR.");
    } finally { setBusy(false); }
  }

  return (
    <div data-testid="pr-create-form" className="grid gap-4">
      <section className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2">
            <button className="icon-button" onClick={onCancel}><ArrowLeft size={15} /></button>
            <h2>Buat Permintaan Pembelian</h2>
          </div>
        </div>
        <div className="section-body grid gap-3">
          {err && <div className="notice-bar danger" data-testid="pr-form-error"><span>{err}</span><button onClick={() => setErr("")}>×</button></div>}

          {/* Item picker */}
          <div className="grid gap-1.5">
            <label className="text-[11px] font-bold uppercase text-[#6B6B73]">Tambah Item — pilih artikel, lalu warna</label>
            <div className="grid gap-2 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_auto]">
              <KNSelect
                data-testid="pr-article-select"
                className="form-input"
                value={pickArticle}
                onValueChange={(v) => { setPickArticle(v); setPickProduct(""); }}
                placeholder="1. Pilih artikel (nama KN / nama supplier)"
                options={articleOptions}
              />
              <KNSelect
                data-testid="pr-product-select"
                className="form-input"
                value={pickProduct}
                onValueChange={setPickProduct}
                disabled={!pickArticle}
                placeholder={pickArticle ? "2. Pilih warna (KN / supplier)" : "Pilih artikel dulu"}
                options={colorOptions}
              />
              <button data-testid="pr-add-line" className="btn-secondary" onClick={addLine} disabled={!pickProduct}><Plus size={14} /> Tambah</button>
            </div>
          </div>

          {/* Lines */}
          {lines.length > 0 && (
            <div className="rounded-md border border-[#EFF0F2] overflow-hidden">
              <div className="grid grid-cols-[1.3fr_150px_100px_74px_120px_110px_40px] bg-[#FAFBFC] px-3 py-1.5 text-[10px] font-bold uppercase text-[#6B6B73]">
                <span>Produk</span><span>Pemenuhan</span><span className="text-right">Qty</span><span className="text-right">Roll</span><span className="text-right">Est. Harga</span><span className="text-right">Subtotal</span><span></span>
              </div>
              {lines.map((l, i) => (
                <div key={i} data-testid={`pr-line-${i}`} className="grid grid-cols-[1.3fr_150px_100px_74px_120px_110px_40px] items-center gap-1 px-3 py-2 border-t border-[#F4F5F7]">
                  <div className="min-w-0"><DualName item={l} testId={`pr-line-dualname-${i}`} /><p className="text-[10px] text-[#9A9BA3]">{l.sku} · {l.unit}</p></div>
                  <KNSelect data-testid={`pr-mode-${i}`} className="form-input"
                    value={l.fulfillment_mode || "purchase"}
                    onValueChange={(v) => updLine(i, "fulfillment_mode", v)}
                    options={FULFILLMENT_OPTIONS} />
                  <input type="number" data-testid={`pr-qty-${i}`} className="form-input text-right" value={l.quantity} onChange={(e) => updLine(i, "quantity", e.target.value)} />
                  {/* FASE U — DUA SATUAN: jumlah roll pada PR adalah RENCANA, jadi diketik
                      (§U.D). Dibiarkan kosong = "tidak menyebut jumlah roll" → dokumen
                      tampil "—", bukan 0 roll. */}
                  <input type="number" min="0" data-testid={`pr-rolls-${i}`} className="form-input text-right"
                    placeholder="Roll" title="Jumlah roll (gulungan) yang diminta — boleh dikosongkan"
                    value={l.qty_rolls ?? ""} onChange={(e) => updLine(i, "qty_rolls", e.target.value)} />
                  <MoneyInput testId={`pr-price-${i}`} className="form-input text-right" value={l.est_price} onChange={(v) => updLine(i, "est_price", v)} />
                  <span className="text-[12px] tabular-nums text-right font-semibold">{formatCurrency((Number(l.est_price) || 0) * (Number(l.quantity) || 0))}</span>
                  <button className="icon-button text-red-500" onClick={() => rmLine(i)}><Trash2 size={14} /></button>
                </div>
              ))}
              <div className="flex justify-between items-center px-3 py-2 border-t border-[#EFF0F2] bg-[#FAFBFC]">
                <span className="text-[11px] font-bold uppercase text-[#6B6B73]">Total Estimasi</span>
                <span data-testid="pr-form-total" className="text-[15px] font-bold tabular-nums text-[#0058CC]">{formatCurrency(total)}</span>
              </div>
            </div>
          )}
          {lines.some((l) => l.fulfillment_mode === "makloon") && (
            <p data-testid="pr-makloon-note" className="text-[11.5px] text-[#8C4A00] bg-[#FFF8EE] border border-[#FFE2B8] rounded-md px-3 py-2">
              Baris ber-mode <b>Proses via Makloon</b> tidak masuk PO. Setelah PR disetujui,
              buka detail PR → panel <b>Pemenuhan & Realisasi</b> → tombol
              <b> Buat Order Makloon</b> (bahan, mitra & qty terisi otomatis dari Resep Proses).
            </p>
          )}

          {/* Fields */}
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <label className="text-[11px] font-bold uppercase text-[#6B6B73]">Gudang Tujuan *</label>
              <KNSelect
                data-testid="pr-warehouse"
                className="form-input"
                value={warehouseId}
                onValueChange={setWarehouseId}
                placeholder="— Pilih gudang —"
                options={warehouses.map((w) => ({ value: w.id, label: w.name }))}
              />
            </div>
            <div className="grid gap-1.5">
              <label className="text-[11px] font-bold uppercase text-[#6B6B73]">Supplier Preferensi</label>
              <KNSelect
                data-testid="pr-supplier"
                className="form-input"
                value={supplierId}
                onValueChange={setSupplierId}
                placeholder={eligible && !showAllSup ? "— Supplier berkontrak / terdaftar —" : "— Opsional —"}
                options={supplierChoices.map((s) => ({ value: s.id, label: supplierOptionLabel(s) }))}
              />
              {eligible && !showAllSup && !noEligible && (
                <p data-testid="pr-supplier-filter-note" className="text-[11px] text-[#6B6B73]">
                  Hanya supplier yang punya kontrak aktif / terdaftar di Barang Supplier untuk semua item.{" "}
                  <button type="button" className="font-semibold text-[#0058CC]" onClick={() => setShowAllSup(true)} data-testid="pr-supplier-show-all">Tampilkan semua</button>
                </p>
              )}
              {noEligible && (
                <p data-testid="pr-supplier-none" className="rounded-md border border-[#FFE2B8] bg-[#FFF8EE] px-2.5 py-1.5 text-[11.5px] text-[#8C4A00]">
                  Belum ada supplier berkontrak atau terdaftar di Barang Supplier untuk item ini.{" "}
                  <button type="button" className="font-semibold underline" onClick={() => setShowAllSup(true)} data-testid="pr-supplier-show-all">Tampilkan semua supplier</button>
                </p>
              )}
              {/* FASE E-7 (E7.2) — pagar dipasang SEJAK di hulu: PR yang menunjuk badan
                  usaha grup akan ditolak saat realisasi ke PO, jadi lebih baik dijelaskan
                  sekarang daripada setelah lewat persetujuan. */}
              {isGroupEntityPartner(selectedSupplier) && (
                <GroupEntityNotice partner={selectedSupplier} docLabel="Permintaan Pembelian (PR) biasa" />
              )}
            </div>
            <div className="grid gap-1.5">
              <label className="text-[11px] font-bold uppercase text-[#6B6B73]">Dibutuhkan Sebelum</label>
              <KNDatePicker data-testid="pr-needed-by" value={neededBy} onChange={setNeededBy} />
            </div>
            <div className="grid gap-1.5">
              <label className="text-[11px] font-bold uppercase text-[#6B6B73]">Alasan / Justifikasi</label>
              <input data-testid="pr-reason" className="form-input" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Restock produksi…" />
            </div>
          </div>

          <label className="flex items-center gap-2 text-[12px]">
            <input type="checkbox" data-testid="pr-submit-now" checked={submitNow} onChange={(e) => setSubmitNow(e.target.checked)} />
            Langsung ajukan persetujuan (jika di bawah ambang, otomatis disetujui)
          </label>

          <div className="flex justify-end gap-2 pt-1">
            <button className="btn-secondary" onClick={onCancel}>Batal</button>
            <button data-testid="pr-submit" className="btn-primary" onClick={submit}
              disabled={busy || supplierIsGroupEntity}
              title={supplierIsGroupEntity
                ? `${selectedSupplier?.name} adalah badan usaha di dalam grup — pakai menu Antar Entitas`
                : ""}>
              {supplierIsGroupEntity ? "Pakai menu Antar Entitas" : busy ? "Menyimpan…" : "Simpan PR"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}


/** Opsi artikel (induk): nama KN + nama versi supplier (dari varian) — dicari di kedua versi. */
function articleOptionsOf(products, templates) {
  const tplById = Object.fromEntries(templates.map((t) => [t.id, t]));
  const groups = {};
  products.forEach((p) => { const k = p.template_id && tplById[p.template_id] ? `t:${p.template_id}` : `p:${p.id}`; (groups[k] = groups[k] || []).push(p); });
  return Object.entries(groups).map(([k, ps]) => {
    const t = k.startsWith("t:") ? tplById[k.slice(2)] : null;
    const sup = [...new Set(ps.map((p) => p.supplier_alias?.name).filter(Boolean))];
    const kn = t ? `${t.sku_prefix ? `${t.sku_prefix} · ` : ""}${t.name}` : `${ps[0].sku} · ${ps[0].name}`;
    return { value: k, label: `${kn}${sup.length ? `  —  Supplier: ${sup.slice(0, 2).join(" / ")}` : ""}`,
      keywords: [...sup, ...ps.flatMap(supplierKeywords), ...ps.map((p) => p.sku)] };
  }).sort((a, b) => a.label.localeCompare(b.label));
}

/** Opsi warna (varian) dari artikel terpilih: warna KN + warna versi supplier. */
function colorOptionsOf(products, article) {
  if (!article) return [];
  const ps = article.startsWith("p:") ? products.filter((p) => p.id === article.slice(2)) : products.filter((p) => p.template_id === article.slice(2));
  return ps.map((p) => {
    const kn = p.color_name || p.variant_attrs?.color || p.name;
    const sup = p.supplier_alias?.color;
    return { value: p.id, label: `${kn}${p.variant_attrs?.grade ? ` · grade ${p.variant_attrs.grade}` : ""}${sup ? `  —  Supplier: ${sup}` : ""}  (${p.sku})`,
      keywords: [p.sku, p.name, sup, ...supplierKeywords(p)].filter(Boolean) };
  });
}
