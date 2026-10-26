/**
 * AmendmentItemRows — baris dokumen di form "Ajukan Amandemen" (diekstrak dari AmendmentProposeModal, fase 4 · R1).
 *
 * Nilai semula selalu terlihat di sebelah nilai baru. Desktop: satu baris 5 kolom (Produk · Jumlah · Harga satuan ·
 * Diskon % · kembalikan). HP (< 640 px, form layar penuh): nama produk satu baris penuh, tiga isian berlabel di
 * bawahnya — isian SAMA (keputusan pemilik: form HP = form desktop), hanya tata letaknya yang bertahap.
 *
 * `autoReasonFor` — alasan bawaan dari jenis perubahan (dulu hanya di form HP "alasan dipilih otomatis"); dipakai
 * AmendmentProposeModal bila prop `autoReason` aktif. Kode yang tidak ada di daftar alasan aktif → "" (pilih manual).
 */
import { RotateCcw } from "lucide-react";
import MoneyInput from "../../../components/MoneyInput";
import { formatCurrency, formatQty } from "../../../utils/formatters";

export const EPS = 0.0001;
export const AMD_FIELDS = ["quantity", "price", "discount_percent"];
export const clampPct = (v) => Math.min(Math.max(Number(v) || 0, 0), 100);
export const nonNeg = (v) => Math.max(Number(v) || 0, 0);

export function autoReasonFor(changes, orderDiscChanged, reasons) {
  const f = new Set(changes.map((c) => c.field));
  const code = f.has("price") ? "price_correction"
    : (f.has("discount_percent") || orderDiscChanged) ? "discount_grant"
      : f.has("quantity") ? "qty_adjustment" : "";
  return code && (reasons || []).some((r) => r.code === code) ? code : "";
}

const COLS = "grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_28px] sm:grid-cols-[1fr_96px_120px_84px_28px]";
const MLABEL = "block text-[9.5px] font-semibold uppercase tracking-wide text-[#6B6B73] sm:hidden";
const INPUT = "field !py-1 !px-1.5 text-[11px] tabular-nums";
// MoneyInput memberi awalan "Rp" lewat padding kiri 34 px — `!px-1.5` menimpanya (angka tertutup "Rp"), jadi kanan saja.
const MONEY = "field !py-1 !pr-1.5 text-[11px] tabular-nums";

export default function AmendmentItemRows({ rows, onField, onReset }) {
  return (
    <div className="rounded-md border border-[#EFF0F2] overflow-hidden" data-testid="amd-items">
      <div className={`hidden sm:grid ${COLS} gap-1 px-2.5 py-1.5 bg-[#FAFBFC] text-[10px] font-bold uppercase tracking-wide text-[#6B6B73] border-b border-[#EFF0F2]`}>
        <span>Produk</span><span>Jumlah</span><span>Harga satuan</span><span>Diskon %</span><span />
      </div>
      {rows.map((r, i) => {
        const dirty = AMD_FIELDS.some((f) => Math.abs(Number(r[f] || 0) - Number(r.orig[f] || 0)) > EPS);
        return (
          <div key={r.product_id} data-testid={`amd-item-${r.product_id}`}
            className={`grid ${COLS} items-start sm:items-center gap-1 px-2.5 py-1.5 border-b border-[#EFF0F2] last:border-0 ${dirty ? "bg-[#FFFBEF]" : ""}`}>
            <div className="col-span-4 min-w-0 sm:col-span-1">
              <p className="text-[11px] font-semibold truncate">{r.product_name}</p>
              <p className="text-[9.5px] text-[#9A9BA3] truncate">
                {r.sku}{r.unit ? ` · ${r.unit}` : ""} · semula {formatQty(r.orig.quantity)} × {formatCurrency(r.orig.price)}
                {r.orig.discount_percent > 0 ? ` · disc ${formatQty(r.orig.discount_percent)}%` : ""}
              </p>
            </div>
            <label className="min-w-0">
              <span className={MLABEL}>Jumlah</span>
              <input data-testid={`amd-item-qty-${r.product_id}`} type="number" min="0" step="any" inputMode="decimal" value={r.quantity}
                aria-label={`Jumlah ${r.product_name}`} onChange={(e) => onField(i, "quantity", nonNeg(e.target.value))} className={INPUT} />
            </label>
            <label className="min-w-0">
              <span className={MLABEL}>Harga satuan</span>
              <MoneyInput testId={`amd-item-price-${r.product_id}`} className={MONEY} value={r.price}
                aria-label={`Harga satuan ${r.product_name}`} onChange={(v) => onField(i, "price", nonNeg(v))} />
            </label>
            <label className="min-w-0">
              <span className={MLABEL}>Diskon %</span>
              <input data-testid={`amd-item-disc-${r.product_id}`} type="number" min="0" max="100" step="any" inputMode="decimal" value={r.discount_percent}
                aria-label={`Diskon % ${r.product_name}`} onChange={(e) => onField(i, "discount_percent", clampPct(e.target.value))} className={INPUT} />
            </label>
            <button type="button" data-testid={`amd-item-reset-${r.product_id}`} onClick={() => onReset(i)} disabled={!dirty}
              title={dirty ? "Kembalikan ke nilai semula" : "Belum diubah"} aria-label="Kembalikan ke nilai semula"
              className={`justify-self-end mt-5 sm:mt-0 ${dirty ? "text-[#0058CC] hover:text-[#003E92]" : "text-gray-300 cursor-not-allowed"}`}>
              <RotateCcw size={12} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
