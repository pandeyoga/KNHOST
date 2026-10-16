import { useState } from "react";
import ErrorNotice from "../../components/ErrorNotice";
import { formatCurrency } from "../../utils/formatters";
import { apiErrorText } from "../../utils/apiError";
import { internalPriceBulk } from "./internalPriceApi";

const today = () => new Date().toISOString().slice(0, 10);

/** Form kecil: tetapkan harga internal SATU barang untuk satu pasangan PT penjual → pembeli. */
export default function InternalPriceModal({ target, onClose, onSaved }) {
  const [price, setPrice] = useState("");
  const [validFrom, setValidFrom] = useState(today());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const value = Number(String(price).replace(",", ".")) || 0;

  async function save() {
    setBusy(true); setError("");
    try {
      await internalPriceBulk({ seller_entity_id: target.sellerId, buyer_entity_id: target.buyerId, valid_from: validFrom,
        notes: target.note || "", items: [{ product_id: target.productId, unit_price: value }] });
      onSaved?.();
    } catch (e) { setError(apiErrorText(e, "Gagal menyimpan harga internal.")); }
    finally { setBusy(false); }
  }

  return (
    <div className="modal-overlay" style={{ zIndex: 70 }} data-testid="internal-price-modal" onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
      <div className="modal-card" style={{ maxWidth: 440 }} onClick={(e) => e.stopPropagation()}>
        <p className="modal-title">Buat harga internal</p>
        <p className="modal-subtitle">
          <b>{target.sku}</b> {target.productName} · {target.sellerName} → {target.buyerName}
        </p>
        <ErrorNotice message={error} onDismiss={() => setError("")} testId="internal-price-error" />
        <div className="mt-3 space-y-2.5">
          <label className="block text-[11px] font-semibold text-[#3C3C43]">Harga per {target.unit || "satuan"} (Rp)
            <input data-testid="internal-price-input" type="number" min={0} step="1" className="field mt-1 w-full text-right"
              value={price} onChange={(e) => setPrice(e.target.value)} placeholder="0" autoFocus />
          </label>
          <label className="block text-[11px] font-semibold text-[#3C3C43]">Berlaku mulai
            <input data-testid="internal-price-valid-from" type="date" className="field mt-1 w-full"
              value={validFrom} onChange={(e) => setValidFrom(e.target.value)} />
          </label>
          {value > 0 && <p className="text-[11px] text-[#6B6B73]" data-testid="internal-price-preview">Tersimpan sebagai kontrak internal aktif: {formatCurrency(value)} / {target.unit || "satuan"}.</p>}
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <button className="secondary-button" data-testid="internal-price-cancel" onClick={onClose}>Batal</button>
          <button className="primary-button" data-testid="internal-price-save" disabled={busy || value <= 0} onClick={save}>
            {busy ? "Menyimpan…" : "Simpan harga"}
          </button>
        </div>
      </div>
    </div>
  );
}
