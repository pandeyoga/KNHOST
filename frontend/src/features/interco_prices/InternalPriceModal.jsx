import { useState } from "react";
import { Tag } from "lucide-react";
import FormModal from "../../components/FormModal";
import KNDatePicker from "../../components/KNDatePicker";
import { formatCurrency, todayWib } from "../../utils/formatters";
import { apiErrorText } from "../../utils/apiError";
import { internalPriceBulk } from "./internalPriceApi";

const today = () => todayWib();

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

  // Fase 4 · R3 (L-03) — `.modal-card` buatan sendiri → FormModal (layar penuh di HP, Esc berlapis: dibuka di atas
  // dialog Keputusan Pemenuhan dan hanya menutup dirinya; galat di kaki pop-up). Testid isian & tombol tetap.
  return (
    <FormModal open onClose={onClose} size="sm" icon={Tag} title="Buat harga internal" testId="internal-price-modal"
      subtitle={<><b>{target.sku}</b> {target.productName} · {target.sellerName} → {target.buyerName}</>}
      onSubmit={save} busy={busy} error={error} submitDisabled={value <= 0}
      submitTestId="internal-price-save" cancelTestId="internal-price-cancel"
      submitLabel={busy ? "Menyimpan…" : "Simpan harga"}>
      <div className="space-y-2.5">
        <label className="block text-[11px] font-semibold text-[#3C3C43]">Harga per {target.unit || "satuan"} (Rp)
          <input data-testid="internal-price-input" type="number" min={0} step="1" className="field mt-1 w-full text-right"
            value={price} onChange={(e) => setPrice(e.target.value)} placeholder="0" />
        </label>
        <label className="block text-[11px] font-semibold text-[#3C3C43]">Berlaku mulai
          <KNDatePicker data-testid="internal-price-valid-from" className="mt-1 w-full font-normal" clearable={false}
            value={validFrom} onChange={setValidFrom} />
        </label>
        {value > 0 && <p className="text-[11px] text-[#6B6B73]" data-testid="internal-price-preview">Tersimpan sebagai kontrak internal aktif: {formatCurrency(value)} / {target.unit || "satuan"}.</p>}
      </div>
    </FormModal>
  );
}
