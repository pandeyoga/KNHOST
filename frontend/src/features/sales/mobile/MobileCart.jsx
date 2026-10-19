import { useState } from "react";
import { Minus, Plus, Trash2, ShoppingCart, Scissors } from "lucide-react";
import { PosFBT } from "../../pos/PosFBT";
import CheckoutDrawer from "../../pos/CheckoutDrawer";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import { onImageError, productImage } from "../../../utils/productImage";
import { useEffectivePrices, pickPrice, sourceMeta } from "../../../hooks/useEffectivePrices";
import { clampSampleQty, isSampleCart } from "../../../utils/sampleOrder";

/** Keranjang HP — checkout memakai CheckoutDrawer desktop (3 langkah: pelanggan & alamat → termin & lot → review)
 * supaya HP setara desktop: kirim/ambil sendiri, faktur pajak, gate kredit, lot campur, sampel gratis/berbayar, minta harga khusus per baris. */
export default function MobileCart({
  cart, setCart, data, selectedCustomer, setSelectedCustomer,
  selectedAddress, setSelectedAddress, paymentTerms = [], onSubmitOrder, onAdd,
  entityId, onBrowse, onDone, user, settings = {}, onCreateCustomer,
}) {
  const [checkout, setCheckout] = useState(false);
  const sampleCart = isSampleCart(cart);
  const { priceMap } = useEffectivePrices({
    customerId: selectedCustomer?.id || "",
    entityId: entityId && entityId !== "all" ? entityId : (selectedCustomer?.entity_id || ""),
    productIds: cart.map((i) => i.product.id),
    enabled: cart.length > 0 && !!selectedCustomer?.id,
  });
  const linePrices = {};
  cart.forEach((i) => { linePrices[i.product.id] = i.is_sample ? null : pickPrice(priceMap[i.product.id], i.quantity); });
  const unitPrice = (it) => Number(linePrices[it.product.id]?.price ?? it.product?.price ?? 0);
  const lineTotal = (it) => unitPrice(it) * Number(it.quantity || 0);
  const subtotal = cart.reduce((s, it) => s + lineTotal(it), 0);
  const setQty = (it, qv) => setCart((cur) => cur.map((x) => x.product.id === it.product.id
    ? { ...x, quantity: x.is_sample ? (clampSampleQty(x.product, qv, x.sample_kind) || 0.5) : Math.max(1, qv) } : x));
  const removeItem = (pid) => setCart((cur) => cur.filter((it) => it.product.id !== pid));
  const submit = async (opts) => { const ok = await onSubmitOrder(opts); if (ok) onDone?.(); };

  if (cart.length === 0) {
    return (
      <div data-testid="mobile-cart-empty" className="flex flex-col items-center gap-3 py-20 text-center m-muted">
        <ShoppingCart size={34} className="text-[#C7C7CC]" />
        <p className="text-[14px] font-semibold text-[#1C1C1E]">Keranjang kosong</p>
        <p className="text-[12px]">Tambahkan produk dari katalog untuk membuat pesanan.</p>
        <button data-testid="mobile-cart-browse" onClick={onBrowse} className="primary-button mt-2 px-5 py-2.5">Mulai Belanja</button>
      </div>
    );
  }

  return (
    <div data-testid="mobile-cart" className="space-y-3" style={{ paddingBottom: "110px" }}>
      <div className="flex items-center gap-2">
        {sampleCart ? <Scissors size={16} className="text-[#9A5B00]" /> : <ShoppingCart size={16} className="text-[#0058CC]" />}
        <h2 className="m-section-title">{sampleCart ? "Keranjang Sampel" : "Keranjang"} ({cart.length})</h2>
      </div>
      {sampleCart && <p data-testid="mobile-cart-sample-banner" className="rounded-lg border border-[#F3D9A4] bg-[#FFF9EC] px-3 py-2 text-[11px] text-[#9A5B00]">Pesanan <b>SAMPEL</b> (SOS-) — dipotong gudang dari roll. Gratis / berbayar dipilih saat checkout.</p>}
      <div className="space-y-2.5">
        {cart.map((it) => {
          const lp = linePrices[it.product.id];
          return (
            <div key={it.product.id} data-testid={`mobile-cart-item-${it.product.id}`} className="m-card flex items-center gap-2.5 p-2.5">
              <img src={productImage(it.product)} onError={onImageError} alt={it.product.name} className="h-14 w-14 rounded-lg object-cover" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-[12.5px] font-semibold">{it.product.name}</p>
                {it.is_sample ? (
                  <p className="text-[11px] font-semibold text-[#9A5B00]" data-testid={`mobile-cart-sample-${it.product.id}`}><Scissors size={10} className="mr-0.5 inline" /> Sampel · {formatQty(it.quantity)} {it.unit}</p>
                ) : (
                  <p className="text-[11px] tabular-nums m-muted" data-testid={`mobile-cart-price-${it.product.id}`}>
                    {formatCurrency(unitPrice(it))}/{it.unit}
                    {lp && ["customer", "special_approval"].includes(lp.source) && (
                      <span className="ml-1 rounded px-1 text-[9.5px] font-bold" style={{ color: sourceMeta(lp.source).fg, background: sourceMeta(lp.source).bg }} data-testid={`mobile-cart-price-source-${it.product.id}`}>{sourceMeta(lp.source).label}</span>
                    )}
                    {unitPrice(it) !== Number(it.product.price || 0) && <span className="ml-1 line-through">{formatCurrency(it.product.price)}</span>}
                  </p>
                )}
                {it.purchase_mode === "roll" && <p className="text-[10.5px] text-[#0058CC]" data-testid={`mobile-cart-rolls-${it.product.id}`}>{(it.rolls_snapshot || []).length} roll dipilih · qty terkunci</p>}
                {!it.is_sample && <p className="text-[12px] font-bold tabular-nums text-[#0058CC]">{formatCurrency(lineTotal(it))}</p>}
              </div>
              <div className="flex flex-col items-end gap-1.5">
                <button data-testid={`mobile-cart-remove-${it.product.id}`} className="text-[#C0392B]" onClick={() => removeItem(it.product.id)} aria-label="Hapus"><Trash2 size={15} /></button>
                {it.purchase_mode !== "roll" && (
                  <div className="flex items-center rounded-lg border border-[#E5E5EA]">
                    <button data-testid={`mobile-cart-minus-${it.product.id}`} className="px-2.5 py-1.5 text-[#6B6B73]" onClick={() => setQty(it, Number(it.quantity) - (it.is_sample ? 0.5 : 1))} aria-label="Kurangi"><Minus size={13} /></button>
                    <span data-testid={`mobile-cart-qty-${it.product.id}`} className="min-w-[30px] text-center text-[12.5px] tabular-nums">{formatQty(it.quantity)}</span>
                    <button data-testid={`mobile-cart-plus-${it.product.id}`} className="px-2.5 py-1.5 text-[#6B6B73]" onClick={() => setQty(it, Number(it.quantity) + (it.is_sample ? 0.5 : 1))} aria-label="Tambah"><Plus size={13} /></button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {onAdd && cart[0] && !sampleCart && (
        <PosFBT productId={cart[0].product.id} entityId={entityId} onAdd={onAdd} excludeIds={cart.map((it) => it.product.id)} />
      )}

      <div className="m-cta-bar">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[12px] m-muted">{sampleCart ? "Sampel" : "Estimasi subtotal"}</span>
          <span data-testid="mobile-cart-subtotal" className="text-[16px] font-bold tabular-nums">{sampleCart ? `${cart.length} item` : formatCurrency(subtotal)}</span>
        </div>
        <button data-testid="mobile-checkout-btn" className={`primary-button w-full justify-center py-3 ${sampleCart ? "!bg-[#9A5B00]" : ""}`} onClick={() => setCheckout(true)}>
          Lanjut ke Checkout
        </button>
      </div>

      <CheckoutDrawer open={checkout} onClose={() => setCheckout(false)} cart={cart} setCart={setCart}
        customers={data?.customers || []} selectedCustomer={selectedCustomer} setSelectedCustomer={setSelectedCustomer}
        selectedAddress={selectedAddress} setSelectedAddress={setSelectedAddress} onCreateCustomer={onCreateCustomer}
        onSubmitOrder={submit} settings={settings} paymentTerms={paymentTerms} selectedEntity={entityId} user={user} />
    </div>
  );
}
