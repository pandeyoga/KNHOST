import { ReceiptText } from "lucide-react";

/**
 * TX-T1 (K-33) — sakelar "Pesanan tanpa PPN" di checkout. Hanya dirender untuk pemegang izin `order.tax_override` di PT
 * PKP (pemanggil memutuskan lewat `can(...)`); alasan wajib, minimal 10 huruf — sama dengan server
 * (`routers/sales_orders.NON_PPN_MIN_REASON_LETTERS`, PK-45). Ringkasan harga menghitung ulang tanpa PPN saat dinyalakan.
 */
export const NON_PPN_MIN_LETTERS = 10;
export const countLetters = (t) => (String(t || "").match(/\p{L}/gu) || []).length;

export default function CheckoutNonPpn({ value }) {
  if (!value) return null;
  const { on, setOn, reason, setReason } = value;
  const kurang = on && countLetters(reason) < NON_PPN_MIN_LETTERS;
  return (
    <div className="section-card section-pad space-y-2" data-testid="checkout-non-ppn">
      <label className="flex items-start gap-2 text-fs-13 text-kn-text">
        <input type="checkbox" className="mt-0.5" data-testid="checkout-non-ppn-toggle" checked={!!on}
          onChange={(e) => setOn(e.target.checked)} />
        <span>
          <span className="flex items-center gap-1.5 font-semibold"><ReceiptText size={14} aria-hidden="true" />Pesanan tanpa PPN</span>
          <span className="block text-fs-12 text-kn-text-2">Mis. pelanggan di kawasan berikat. Pesanan dibuat tanpa PPN dan
            tanpa faktur pajak; alasan dan nama Anda tercatat di pesanan.</span>
        </span>
      </label>
      {on && (
        <div>
          <label className="field-label" htmlFor="checkout-non-ppn-reason">Alasan tanpa PPN <span className="text-kn-danger-text">*</span></label>
          <input id="checkout-non-ppn-reason" data-testid="checkout-non-ppn-reason" className="field w-full" value={reason}
            onChange={(e) => setReason(e.target.value)} placeholder="mis. Pelanggan kawasan berikat" />
          <p className={`mt-0.5 text-fs-12 ${kurang ? "text-kn-warning-text" : "text-kn-text-2"}`} data-testid="checkout-non-ppn-hint">
            {kurang ? `Alasan wajib diisi, minimal ${NON_PPN_MIN_LETTERS} huruf (sekarang ${countLetters(reason)}).`
              : "Alasan tercatat bersama pesanan."}
          </p>
        </div>
      )}
    </div>
  );
}
