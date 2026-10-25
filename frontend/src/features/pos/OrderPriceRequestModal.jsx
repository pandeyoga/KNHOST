import { useEffect, useState } from "react";
import { BadgePercent, X } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";
import { overlayDismiss } from "../../utils/overlayDismiss";
import { useEscapeClose } from "../../utils/escapeLayers";

/**
 * Trial 22 Okt 2026 (E10, keputusan pemilik) — "Minta harga khusus UNTUK PESANAN INI" dari checkout.
 * Tidak membuat pengajuan langsung: harga & alasan ikut baris pesanan, lalu server mengikatnya ke SO saat pesanan dibuat
 * (SO lahir berharga normal + entri ACC harga menunggu). Dulu checkout membuat harga LANGGANAN tanpa SO, sehingga
 * ACC Manajer tidak pernah mengubah pesanan yang sedang dibuat.
 */
export default function OrderPriceRequestModal({ open, item, normalPrice, value, onSave, onClear, onClose }) {
  useEscapeClose(open, onClose, false);
  const [price, setPrice] = useState("");
  const [reason, setReason] = useState("");
  useEffect(() => { if (open) { setPrice(value?.price ? String(value.price) : ""); setReason(value?.reason || ""); } }, [open, value]);
  if (!open || !item) return null;
  const unit = item.unit || item.product?.base_unit || "";
  const p = Number(price || 0);
  const pct = normalPrice > 0 && p > 0 ? Math.round(((p - normalPrice) / normalPrice) * 1000) / 10 : null;
  const ok = p > 0 && reason.trim().length >= 5;   // K-14
  return (
    <div className="modal-overlay" style={{ zIndex: 200 }} data-testid="order-price-request-modal" {...overlayDismiss(onClose)}>
      <div className="modal-card" style={{ maxWidth: 440 }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-2">
          <div className="modal-title flex items-center gap-2"><BadgePercent size={16} /> Minta harga khusus untuk pesanan ini</div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Tutup"><X size={16} /></button>
        </div>
        <p className="text-[12px] font-semibold text-[#1C1C1E]">{item.product?.name}</p>
        <p className="text-[11px] text-[#6B6B73]">Harga normal {formatCurrency(normalPrice)} / {unit} · {item.quantity} {unit}</p>
        <label className="mt-2 block text-[11px] font-semibold text-[#3C3C43]">Harga diminta (per {unit})
          <input data-testid="order-price-request-price" type="number" min="0" inputMode="decimal" className="field mt-1"
            value={price} onChange={(e) => setPrice(e.target.value)} placeholder="mis. 105000" />
        </label>
        {pct != null && (
          <p data-testid="order-price-request-pct" className={`mt-1 text-[11px] font-semibold ${pct < 0 ? "text-[#9A5B00]" : "text-[#6B6B73]"}`}>
            {pct > 0 ? "+" : ""}{pct}% dari harga normal · selisih {formatCurrency((p - normalPrice) * Number(item.quantity || 0))}
          </p>
        )}
        <label className="mt-2 block text-[11px] font-semibold text-[#3C3C43]">Alasan (wajib)
          <textarea data-testid="order-price-request-reason" rows={2} className="field mt-1" value={reason}
            onChange={(e) => setReason(e.target.value)} placeholder="mis. order rutin, pesaing menawar 104.000" />
        </label>
        <p className="mt-2 rounded-md bg-[#FFF7EC] px-2.5 py-1.5 text-[10.5px] text-[#9A5B00]">
          Berlaku <b>hanya untuk pesanan ini</b>. Pesanan dibuat dengan harga normal dan stok dibooking; Manajer memutuskan
          harga, lalu pesanan lanjut ke gudang. Bila ditolak: ajukan harga lain, lanjut harga normal, atau batalkan.
        </p>
        <div className="modal-actions">
          {value && <button type="button" className="btn-secondary" data-testid="order-price-request-clear" onClick={onClear}>Hapus permintaan</button>}
          <button type="button" className="btn-primary" data-testid="order-price-request-save" disabled={!ok}
            onClick={() => onSave({ price: p, reason: reason.trim() })}>Simpan</button>
        </div>
      </div>
    </div>
  );
}
