import { AlertTriangle, ShoppingBag, Scissors } from "lucide-react";

// Keranjang berisi sampel + ecer sekaligus: server menolak (SAMPLE_MIXED) — user pilih satu jenis dulu.
export function MixedCartNotice({ cart, setCart }) {
  const samples = cart.filter((it) => it.is_sample);
  const retail = cart.filter((it) => !it.is_sample);
  const toRetail = () => setCart((cur) => cur.map((it) => (it.is_sample ? { ...it, is_sample: false, sample_kind: undefined, sample_price: null } : it)));
  const keepSamples = () => setCart((cur) => cur.filter((it) => it.is_sample));
  return (
    <div data-testid="mixed-cart-notice" role="alert" className="rounded-md border border-[#F5C2C2] bg-[#FDF1F1] p-3 text-[11.5px] text-[#8A1F1F]">
      <p className="flex items-center gap-1.5 font-bold"><AlertTriangle size={14} /> Keranjang campur: {samples.length} baris sampel + {retail.length} baris ecer</p>
      <p className="mt-1">Pesanan sampel (SOS-) dan pesanan biasa (SO-) tidak bisa dibuat dalam satu pesanan. Pilih salah satu:</p>
      <div className="mt-2 flex flex-wrap gap-2">
        <button type="button" data-testid="mixed-cart-all-retail" onClick={toRetail} className="secondary-button !h-8 text-[11.5px]">
          <ShoppingBag size={13} /> Jadikan semua ecer</button>
        <button type="button" data-testid="mixed-cart-keep-samples" onClick={keepSamples} className="secondary-button !h-8 text-[11.5px]">
          <Scissors size={13} /> Lanjut sampel saja (hapus {retail.length} baris ecer)</button>
      </div>
      <p className="mt-1.5 text-[10.5px] text-[#A04545]">Baris ecer yang dihapus bisa dimasukkan lagi sebagai pesanan biasa setelah pesanan sampel dibuat.</p>
    </div>
  );
}
