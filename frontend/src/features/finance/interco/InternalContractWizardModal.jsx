/**
 * FASE G-6 — Wizard **KONTRAK INTERNAL** (`partner_kind="entity"`).
 *
 * Keuangan bisa menerbitkan harga tetap PT-A → PT-B untuk barang tertentu
 * tanpa membuka layar Kontrak umum. Setelah tersimpan, transaksi antar-PT
 * dengan `pricing_mode="fixed_price"` untuk barang itu langsung SIAP DITERBITKAN.
 *
 * Fase 3 · P4 (L-03) — overlay `fixed inset-0` buatan sendiri → `FormModal` baku; tombol hitam → `primary-button`.
 */
import { useEffect, useState } from "react";
import KNDatePicker from "@/components/KNDatePicker";
import MoneyInput from "@/components/MoneyInput";
import { Handshake } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import FormModal from "../../../components/FormModal";
import { KNSelect } from "../../../components/KNSelect";
import ErrorNotice from "../../../components/ErrorNotice";
import { apiErrorText } from "../../../utils/apiError";
import { todayWib } from "../../../utils/formatters";

export default function InternalContractWizardModal({
  entities = [], sellerEntityId = "", buyerEntityId = "",
  onClose, onCreated,
}) {
  const [seller, setSeller] = useState(sellerEntityId);
  const [buyer, setBuyer]   = useState(buyerEntityId);
  const [products, setProducts] = useState([]);
  const [productId, setProductId] = useState("");
  const [rate, setRate] = useState("");
  const [validFrom, setValidFrom] = useState(todayWib());
  const [validTo, setValidTo] = useState("");
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    axios.get(`${API}/products`, { params: { limit: 500 } })
      .then((r) => setProducts(Array.isArray(r.data) ? r.data : (r.data.items || [])))
      .catch(() => setProducts([]));
  }, []);

  const entOptions = entities
    .filter((e) => e.status !== "inactive")
    .map((e) => ({ value: e.id, label: e.short_name || e.legal_name || e.name || e.id }));
  const prodOptions = products.map((p) => ({
    value: p.id,
    label: `${p.sku || ""} · ${p.name || ""}`,
  }));

  // UAT 24 Okt (audit UI tahap 2) — G1-30: PT lawan tanpa PT sendiri; tombol nonaktif sampai isian wajib lengkap.
  const canSubmit = !!seller && !!buyer && seller !== buyer && !!productId && parseFloat(rate) > 0 && !!validFrom;

  const submit = async () => {
    setErr("");
    if (!seller || !buyer) { setErr("PT penjual & pembeli wajib dipilih."); return; }
    if (seller === buyer) { setErr("PT penjual & pembeli harus berbeda."); return; }
    if (!productId) { setErr("Produk wajib dipilih."); return; }
    const rateNum = parseFloat(rate);
    if (!rateNum || rateNum <= 0) { setErr("Harga per unit harus > 0."); return; }
    setBusy(true);
    try {
      await axios.post(`${API}/supplier-contracts`, {
        contract_type: "internal",
        entity_id: seller,
        partner_id: buyer,
        product_id: productId,
        tariff_basis: "lumpsum",
        tariff_rate: rateNum,
        tariff_qty_source: "output",
        valid_from: validFrom,
        valid_to: validTo,
        title: title || `Harga internal ${seller}→${buyer}`,
        notes,
        status: "active",
      }, { headers: { "X-Entity-Id": seller } });
      onCreated?.();
    } catch (e) { setErr(apiErrorText(e)); }
    finally { setBusy(false); }
  };

  return (
    <FormModal open onClose={onClose} icon={Handshake} testId="interco-contract-modal" busy={busy}
      title="Kontrak Internal"
      subtitle="Tetapkan harga jual antar-PT untuk satu produk. Transaksi ber-mode Harga tetap setelahnya akan otomatis memakai harga ini."
      footer={(
        <div className="flex items-center justify-end gap-2">
          <button type="button" onClick={onClose} data-testid="interco-contract-cancel" className="secondary-button"
            disabled={busy}>
            Batal
          </button>
          <button
            type="button"
            onClick={submit} disabled={busy || !canSubmit}
            data-testid="interco-contract-submit"
            className="primary-button"
          >
            {busy ? "Menerbitkan..." : "Terbitkan Kontrak Internal"}
          </button>
        </div>
      )}>
      <div className="space-y-4">
        {err && <ErrorNotice message={err} onDismiss={() => setErr("")} />}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="PT Penjual (penerbit kontrak)" required>
            <KNSelect value={seller} onValueChange={setSeller} options={entOptions.filter((o) => o.value !== buyer)} placeholder="Pilih PT penjual" data-testid="interco-contract-seller" />
          </Field>
          <Field label="PT Pembeli (partner)" required>
            <KNSelect value={buyer} onValueChange={setBuyer} options={entOptions.filter((o) => o.value !== seller)} placeholder="Pilih PT pembeli" data-testid="interco-contract-buyer" />
          </Field>
          <Field label="Produk" required>
            <KNSelect value={productId} onValueChange={setProductId} options={prodOptions} placeholder="Pilih produk" data-testid="interco-contract-product" />
          </Field>
          <Field label="Harga per unit (Rp)" required>
            <MoneyInput
              value={rate}
              onChange={(v) => setRate(v)}
              testId="interco-contract-rate"
              className="w-full px-3 py-2 text-sm border border-[#E5E5EA] rounded-lg focus:outline-none focus:border-[#0058CC]"
            />
          </Field>
          <Field label="Berlaku sejak" required>
            <KNDatePicker value={validFrom} onChange={setValidFrom} data-testid="interco-contract-valid-from" clearable={false} />
          </Field>
          <Field label="Berlaku hingga (opsional)">
            <KNDatePicker value={validTo} onChange={setValidTo} data-testid="interco-contract-valid-to" placeholder="Tanpa batas" />
          </Field>
        </div>

        <Field label="Judul (opsional)">
          <input
            value={title} onChange={(e) => setTitle(e.target.value)}
            data-testid="interco-contract-title"
            className="w-full px-3 py-2 text-sm border border-[#E5E5EA] rounded-lg"
          />
        </Field>
        <Field label="Catatan (opsional)">
          <textarea
            value={notes} onChange={(e) => setNotes(e.target.value)} rows={2}
            data-testid="interco-contract-notes"
            className="w-full px-3 py-2 text-sm border border-[#E5E5EA] rounded-lg"
          />
        </Field>
      </div>
    </FormModal>
  );
}

function Field({ label, required = false, children }) {
  return (
    <div>
      <label className="block text-xs font-medium text-[#3C3C43] mb-1">{label}{required && <span className="text-[#C0392B]"> *</span>}</label>
      {children}
    </div>
  );
}
