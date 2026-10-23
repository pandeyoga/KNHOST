import { useEffect, useMemo, useState } from "react";
import { Search, ShoppingCart, Users, Scissors, ShoppingBag, MapPin } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { isSampleCart } from "../../utils/sampleOrder";
import { convFactor } from "../../utils/uom";
import { formatCurrency } from "../../utils/formatters";
import { groupByTemplate } from "../../utils/variants";
import { entityFullById } from "../../utils/entityLabel";
import KNSelect from "../../components/KNSelect";
import { FacetRail, DEFAULT_FACETS } from "../pos/FacetRail";
import { PosProductCard } from "../pos/PosProductCard";
import { ReorderStrip } from "../pos/ReorderStrip";
import { PosBestSellers } from "../pos/PosBestSellers";
import CheckoutDrawer from "../pos/CheckoutDrawer";
import CreateCustomerModal from "../pos/CreateCustomerModal";
import PosStartGate, { loadPosCtx, savePosCtx } from "../pos/PosStartGate";
import { useSites } from "../../components/SiteSelect";
import ProductQuickView from "../../components/ProductQuickView";
import { useEffectivePrices, pickPrice } from "../../hooks/useEffectivePrices";

export function SalesPortal({
  data, onAdd, cart, setCart,
  selectedCustomer, setSelectedCustomer, selectedAddress, setSelectedAddress,
  onCreateCustomer, onSubmitOrder, search, setSearch, onShowDetail,
  loading = false, settings = {}, paymentTerms = [], selectedEntity = "all", entities = [], user = null,
}) {
  const [facets, setFacets] = useState(DEFAULT_FACETS);
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  // UAT 24 Okt (P8, keputusan pemilik) — "Mulai jualan": LOKASI gudang + PELANGGAN wajib dipilih sebelum katalog.
  const [siteId, setSiteId] = useState(() => loadPosCtx().site_id || "");
  const [gateForce, setGateForce] = useState(false);
  const [newCustOpen, setNewCustOpen] = useState(false);
  const [siteStock, setSiteStock] = useState(null);
  const [onlySite, setOnlySite] = useState(false);
  const sites = useSites();
  const siteName = (sites.find((x) => x.id === siteId) || {}).name || "";
  const [quickView, setQuickView] = useState({ open: false, group: null, expand: false });
  const PAGE_SIZE = 12;
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const allProducts = data.products || [];
  // FASE F — kebijakan penegakan lifecycle (dari `/api/rnd/meta`, dimuat di useAppActions).
  const rndEnforcement = data.rnd_policy?.lifecycle_enforcement || "block";
  // Nama entitas untuk panel Filter. WAJIB lewat `entityFullById`: `/api/entities`
  // tidak punya field `name`, jadi `?.name` dulu membuat panel menampilkan id
  // teknis `ent_ksc` ke sales.
  const entityName = entityFullById(entities.length ? entities : (data.entities || []),
                                    selectedEntity);

  // F1b — harga EFEKTIF per pelanggan dalam SATU panggilan (harga khusus → pelanggan →
  // PT → umum). Dulu: satu panggilan `/price-approvals/effective` per produk (≤40
  // permintaan) dan harga dasar tetap harga umum, sehingga angka di kartu bisa berbeda
  // dari angka yang tersimpan di pesanan.
  const catalogEntityId = selectedEntity && selectedEntity !== "all"
    ? selectedEntity : (selectedCustomer?.entity_id || "");
  const catalogIds = useMemo(() => allProducts.slice(0, 60).map((p) => p.id), [allProducts]);
  const { priceMap: specialMap } = useEffectivePrices({
    customerId: selectedCustomer?.id || "",
    entityId: catalogEntityId,
    productIds: catalogIds,
    delay: 450,
  });

  const products = useMemo(() => {
    const q = search.toLowerCase();
    let list = allProducts.filter((p) =>
      `${p.name} ${p.sku} ${p.category} ${p.color} ${p.motif}`.toLowerCase().includes(q));
    if (facets.categories.length) list = list.filter((p) => facets.categories.includes(p.category));
    if (facets.grades.length) list = list.filter((p) => facets.grades.includes(p.grade));
    if (facets.colors.length) list = list.filter((p) => facets.colors.includes(p.color));
    if (facets.priceMin) list = list.filter((p) => Number(p.price || 0) >= Number(facets.priceMin));
    if (facets.priceMax) list = list.filter((p) => Number(p.price || 0) <= Number(facets.priceMax));
    if (onlySite && siteStock) list = list.filter((p) => Number(siteStock[p.id]?.own_qty || 0) > 0);
    if (facets.availability === "available") list = list.filter((p) => Number(p.available_qty || 0) > 0);
    if (facets.availability === "low") list = list.filter((p) => Number(p.available_qty || 0) > 0 && Number(p.available_qty || 0) <= 40);
    const sorters = {
      price_asc: (a, b) => (a.price || 0) - (b.price || 0),
      price_desc: (a, b) => (b.price || 0) - (a.price || 0),
      avail_desc: (a, b) => (b.available_qty || 0) - (a.available_qty || 0),
      name_asc: (a, b) => `${a.name}`.localeCompare(`${b.name}`),
    };
    if (sorters[facets.sort]) list = [...list].sort(sorters[facets.sort]);
    return list;
  }, [allProducts, search, facets, onlySite, siteStock]);

  // Grup SKU → kartu (per template_id). Produk tanpa template = grup tunggal.
  const groups = useMemo(() => groupByTemplate(products), [products]);

  // Reset pagination ketika filter/pencarian berubah.
  useEffect(() => { setVisibleCount(PAGE_SIZE); }, [search, facets]); // eslint-disable-line

  const openQuickView = (group, expand = false) => setQuickView({ open: true, group, expand });
  const closeQuickView = () => setQuickView((q) => ({ ...q, open: false }));

  const cartCount = cart.length;
  const sampleMode = isSampleCart(cart);
  const cartSubtotal = cart.reduce((s, item) => {
    if (item.is_sample) {
      const sp = Number(item.sample_price) > 0 ? Number(item.sample_price) : (Number(item.sample_unit_price) > 0 ? Number(item.sample_unit_price) : (item.product.price || 0));
      return s + sp * (item.quantity || 0);
    }
    const factor = convFactor(item.product, item.unit || item.product.base_unit) ?? 1;
    // Harga dasar = harga EFEKTIF pelanggan (bukan lagi harga umum produk).
    const entry = pickPrice(specialMap[item.product.id], item.quantity);
    const basePrice = entry ? Number(entry.price) : (item.product.price || 0);
    const unit = entry?.has_special
      ? Number(entry.price)
      : Math.round(basePrice * factor * 100) / 100;
    return s + unit * (item.quantity || 0);
  }, 0);

  // Pilihan pelanggan untuk bilah atas (sekalian set alamat pertama supaya checkout
  // tidak membuka dengan alamat kosong).
  const customerOptions = useMemo(
    () => (data.customers || []).map((c) => ({
      value: c.id, label: `${c.name}${c.code ? ` · ${c.code}` : ""}`,
    })), [data.customers]);

  const pickCustomer = (id) => {
    const c = (data.customers || []).find((x) => x.id === id) || null;
    setSelectedCustomer(c);
    if (typeof setSelectedAddress === "function") {
      setSelectedAddress(c?.addresses?.[0]?.id || "");
    }
  };

  useEffect(() => {
    const ctx = loadPosCtx();
    if (!selectedCustomer && ctx.customer_id) {
      const c = (data.customers || []).find((x) => x.id === ctx.customer_id);
      if (c) pickCustomer(c.id);
    }
  }, [data.customers]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!siteId) { setSiteStock(null); return undefined; }
    let live = true;
    axios.get(`${API}/pos/site-stock`, { params: { site_id: siteId, ...(catalogEntityId ? { entity_id: catalogEntityId } : {}) } })
      .then((r) => { if (live) setSiteStock(r.data?.stock || {}); }).catch(() => { if (live) setSiteStock({}); });
    return () => { live = false; };
  }, [siteId, catalogEntityId]);
  const gateOpen = gateForce || !siteId || !selectedCustomer;
  const startSelling = ({ siteId: sid, customer }) => {
    setSiteId(sid);
    pickCustomer(customer.id);
    savePosCtx({ site_id: sid, customer_id: customer.id });
    setGateForce(false);
  };
  // SO membawa lokasi pemenuhan (alokasi roll: lokasi dulu, lalu FIFO).
  const submitWithSite = (extra = {}) => onSubmitOrder({ ...extra, fulfillment_site_id: siteId });

  const customerPriceCount = Object.values(specialMap)
    .filter((v) => v?.source === "customer").length;
  const specialPriceCount = Object.values(specialMap)
    .filter((v) => v?.source === "special_approval").length;

  if (gateOpen) {
    return (
      <div data-testid="sales-portal-view">
        <PosStartGate user={user} customers={data.customers || []} initialSiteId={siteId}
          initialCustomerId={selectedCustomer?.id || loadPosCtx().customer_id || ""}
          onStart={startSelling} onCreateCustomer={onCreateCustomer ? () => setNewCustOpen(true) : null} />
        <CreateCustomerModal open={newCustOpen} onClose={() => setNewCustOpen(false)} user={user}
          onCreateCustomer={async (form) => { await onCreateCustomer(form); setNewCustOpen(false); }} />
      </div>
    );
  }

  return (
    <div data-testid="sales-portal-view">
      {/* F1b — Pilih pelanggan DULU, sebelum menjelajah katalog.
          Dulu pemilih pelanggan hanya ada di dalam Checkout (dan Checkout hanya bisa
          dibuka setelah keranjang berisi), sehingga kasir tidak mungkin melihat harga
          langganan saat memilih barang. Bawaan tanpa pelanggan = harga PT/umum. */}
      <div className="section-card mb-3" data-testid="pos-customer-bar">
        <div className="section-body flex flex-wrap items-center gap-3 py-3">
          <div className="flex items-center gap-2">
            <Users size={15} className="text-[#0058CC]" />
            <span className="text-[11px] font-bold uppercase tracking-wide text-[#8E8E93]">
              Pelanggan
            </span>
          </div>
          <div className="w-[280px]">
            <KNSelect data-testid="pos-customer-select" className="field py-1.5 text-[12px]"
              value={selectedCustomer?.id || ""}
              onValueChange={(id) => { pickCustomer(id); savePosCtx({ site_id: siteId, customer_id: id }); }}
              placeholder="Pilih pelanggan (harga langganan otomatis)"
              options={customerOptions} searchable />
          </div>
          <span data-testid="pos-site-chip" className="inline-flex items-center gap-1 rounded-full bg-[#EEF4FF] px-2.5 py-1 text-[11.5px] font-semibold text-[#0058CC]">
            <MapPin size={12} /> {siteName || "Lokasi"}
          </span>
          <button type="button" className="secondary-button !py-1 text-[11.5px]" data-testid="pos-context-change" onClick={() => setGateForce(true)}>Ganti lokasi / pelanggan</button>
          <label className="inline-flex items-center gap-1 text-[11.5px]" data-testid="pos-only-site-label">
            <input type="checkbox" checked={onlySite} onChange={(e) => setOnlySite(e.target.checked)} data-testid="pos-only-site" /> Hanya yang ada di {siteName || "lokasi ini"}
          </label>
          <p data-testid="pos-customer-hint" className="text-[11.5px]">
            {selectedCustomer ? (
              customerPriceCount > 0 ? (
                <span className="text-[#0058CC]">
                  <b>{customerPriceCount} produk</b> memakai harga langganan
                  {specialPriceCount > 0 && <> · <b>{specialPriceCount}</b> harga khusus disetujui</>}
                  {" "}untuk {selectedCustomer.name}.
                </span>
              ) : (
                <span className="text-[#6B6B73]">
                  {selectedCustomer.name} belum punya harga langganan — memakai harga PT/umum.
                </span>
              )
            ) : (
              <span className="text-[#6B6B73]">
                Belum memilih pelanggan — harga yang tampil adalah <b>harga PT/umum</b>.
              </span>
            )}
          </p>
        </div>
      </div>

      {/* REVISI SAMPEL — penanda jenis keranjang: sales langsung tahu ini penjualan SAMPEL atau BIASA. */}
      {cartCount > 0 && (
        <div data-testid="pos-cart-kind-banner" className={`mb-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-[12px] ${sampleMode ? "border-[#F3D9A4] bg-[#FFF9EC] text-[#9A5B00]" : "border-[#CBDFFF] bg-[#F2F7FF] text-[#0058CC]"}`}>
          <span className="flex items-center gap-2 font-semibold">
            {sampleMode ? <Scissors size={14} /> : <ShoppingBag size={14} />}
            {cart.some((i) => i.is_sample) && !sampleMode ? "Keranjang CAMPUR (sample + ecer) — pisahkan dulu di checkout sebelum membuat pesanan." : sampleMode ? "Keranjang: PESANAN SAMPEL (SOS) — hanya bahan sample, maks 5 yard woven / 2 kg knitting per bahan." : "Keranjang: ORDER BIASA (PO) — pembelian roll/yard, nomor SO."}
          </span>
          <button data-testid="pos-cart-kind-clear" className="text-[11px] font-semibold underline" onClick={() => setCart([])}>Kosongkan untuk ganti jenis</button>
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
        <FacetRail products={allProducts} facets={facets} setFacets={setFacets} selectedEntity={selectedEntity} entityName={entityName} loading={loading} />

        <section className="min-w-0">
          <div className="section-card mb-4">
            <div className="section-head">
              <div className="flex items-center gap-3 min-w-0">
                <span className="kicker">Sales POS</span>
                <h2 data-testid="sales-portal-title">Katalog Kain Nusantara</h2>
              </div>
              <div className="flex items-center gap-2 rounded-md border border-[#E5E5EA] bg-white px-2 py-1.5 min-w-[240px]">
                <Search size={14} className="text-[#6B6B73]" />
                <input data-testid="product-search-input" className="w-full bg-transparent text-[13px] outline-none" placeholder="Cari SKU, motif, warna..." value={search} onChange={(e) => setSearch(e.target.value)} />
              </div>
            </div>
            <p data-testid="sales-portal-subtitle" className="px-4 py-2 text-[12px] text-[#6B6B73]">
              {groups.length} produk · {groups.reduce((t, g) => t + g.variants.length, 0)} varian · stok di {siteName || "lokasi pilihan"} ditonjolkan; lokasi lain perlu transfer. Klik produk untuk pilih varian, qty & satuan.
            </p>
          </div>

          <ReorderStrip customer={selectedCustomer} products={allProducts} onAdd={onAdd} priceMap={specialMap} />

          <PosBestSellers entityId={selectedEntity} onAdd={onAdd} priceMap={specialMap} />

          <div data-testid="product-grid" className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {loading && <div className="col-span-full animate-pulse py-10 text-center text-[13px] text-[#6B6B73]">Memuat katalog produk…</div>}
            {!loading && groups.length === 0 && <div data-testid="products-empty" className="col-span-full py-10 text-center text-[13px] text-[#6B6B73]">Tidak ada produk yang cocok dengan filter/pencarian.</div>}
            {!loading && groups.slice(0, visibleCount).map((group) => (
              <PosProductCard key={group.key} group={group} specialMap={specialMap} onOpen={openQuickView}
                rndEnforcement={rndEnforcement} siteStock={siteStock} siteName={siteName} />
            ))}
          </div>

          {!loading && groups.length > 0 && (
            <div data-testid="catalog-pagination" className="mt-4 flex flex-col items-center gap-2 pb-2">
              <p className="text-[12px] text-[#6B6B73] tabular-nums">
                Menampilkan {Math.min(visibleCount, groups.length)} dari {groups.length} produk
              </p>
              {visibleCount < groups.length && (
                <button data-testid="catalog-load-more" onClick={() => setVisibleCount((c) => c + PAGE_SIZE)}
                  className="secondary-button">
                  Muat lebih banyak ({groups.length - visibleCount} tersisa)
                </button>
              )}
            </div>
          )}
        </section>
      </div>

      {/* Persistent cart button (badge: item + subtotal) */}
      {cartCount > 0 && (
        <button data-testid="floating-cart-button" onClick={() => setCheckoutOpen(true)}
          className={`fixed bottom-6 right-6 z-[90] flex items-center gap-3 rounded-full px-5 py-3 text-white shadow-xl transition ${sampleMode ? "bg-[#9A5B00] hover:bg-[#7A4700]" : "bg-[#0058CC] hover:bg-[#0047a8]"}`}>
          <span className="relative">
            {sampleMode ? <Scissors size={20} /> : <ShoppingCart size={20} />}
            <span data-testid="cart-badge-count" className={`absolute -right-2 -top-2 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-white px-1 text-[11px] font-bold ${sampleMode ? "text-[#9A5B00]" : "text-[#0058CC]"}`}>{cartCount}</span>
          </span>
          <span className="text-left">
            <span data-testid="cart-badge-kind" className="block text-[10px] font-medium uppercase tracking-wide text-white/70">{sampleMode ? "Keranjang Sample" : "Keranjang"}</span>
            <span data-testid="cart-badge-subtotal" className="block text-[14px] font-bold tabular-nums">{formatCurrency(cartSubtotal)}</span>
          </span>
        </button>
      )}

      <ProductQuickView
        open={quickView.open}
        group={quickView.group}
        specialMap={specialMap}
        onAdd={onAdd}
        onClose={closeQuickView}
        entityId={selectedEntity && selectedEntity !== "all" ? selectedEntity : (selectedCustomer?.entity_id || "")}
        rndEnforcement={rndEnforcement}
        cartKind={cart.length === 0 ? "" : (sampleMode ? "sample" : "regular")}
        customerId={selectedCustomer?.id || ""}
        allowRollPick={!(user?.role === "sales" && settings?.allocation?.roll_pick_sales === false)}
      />

      <CheckoutDrawer
        open={checkoutOpen} onClose={() => setCheckoutOpen(false)}
        cart={cart} setCart={setCart} customers={data.customers || []}
        selectedCustomer={selectedCustomer} setSelectedCustomer={setSelectedCustomer}
        selectedAddress={selectedAddress} setSelectedAddress={setSelectedAddress}
        onCreateCustomer={onCreateCustomer} onSubmitOrder={submitWithSite}
        settings={settings} paymentTerms={paymentTerms} selectedEntity={selectedEntity} onShowDetail={onShowDetail} user={user}
      />
    </div>
  );
}
