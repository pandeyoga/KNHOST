/** P05 IMP-17 + L03 LN-034 — uji ulang SKU aktif per supplier: SKU tetap, histori & kelayakan per supplier terlihat. */
import { useEffect, useState } from "react";
import ProductSelect from "../../components/ProductSelect";
import KNSelect from "../../components/KNSelect";
import { labdipHistory, revalPartners } from "./rndApi";
import SupplierEligibilityPanel from "./SupplierEligibilityPanel";

const RESULT = { acc: "ACC", revisi: "Revisi", tolak: "Tolak" };

function HistoryList({ data }) {
  if (!data) return null;
  if (!data.items.length) return <p className="text-[11px] text-[#8E8E93]" data-testid="existing-sku-history-empty">Belum ada uji tercatat untuk SKU ini.</p>;
  return (
    <ul className="max-h-40 divide-y divide-[#F2F3F5] overflow-y-auto rounded-md border border-[#EFF0F2] bg-white" data-testid="existing-sku-history">
      {data.items.slice(0, 12).map((r) => (
        <li key={r.round_id || `${r.sample_id}-${r.round_no}`} className="flex flex-wrap gap-x-2 px-2 py-1 text-[10.5px]" data-testid={`existing-sku-history-${r.round_id}`}>
          <b>{r.sample_number}</b><span className="uppercase text-[#6B6B73]">{r.type_code}</span>
          <span>{r.supplier_name || "—"}</span>
          <span className="text-[#3C3C43]">pelaksana: {r.performed_by || r.recorded_by || "—"}</span>
          <span className="ml-auto font-semibold">{RESULT[r.result] || "berjalan"}{r.score != null ? ` · ${r.score}` : ""}</span>
        </li>
      ))}
    </ul>
  );
}

function PartnerFields({ supplierId, reason, onChange }) {
  const [partners, setPartners] = useState([]);
  useEffect(() => {
    revalPartners().then((r) => setPartners(r?.items || [])).catch(() => setPartners([]));
  }, []);
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      <label className="block">
        <span className="mb-1 block text-[10.5px] font-semibold text-[#6B6B73]">Supplier / mitra yang diuji ulang *</span>
        <KNSelect data-testid="existing-sku-supplier" className="field" value={supplierId} searchable
          options={[{ value: "", label: "— pilih supplier / makloon —" },
            ...partners.map((p) => ({ value: p.id, label: `${p.name}${p.code ? ` · ${p.code}` : ""} (${p.partner_kind})` }))]}
          onValueChange={(v) => onChange({ supplierId: v })} />
      </label>
      <label className="block">
        <span className="mb-1 block text-[10.5px] font-semibold text-[#6B6B73]">Alasan siklus uji ulang *</span>
        <input className="field" data-testid="existing-sku-reason" value={reason} onChange={(e) => onChange({ reason: e.target.value })}
          placeholder="mis. supplier baru, keluhan pelanggan, ganti benang" />
      </label>
    </div>
  );
}

export default function ExistingSkuSection({ product, onPick, supplierId = "", reason = "", onRevalChange }) {
  const [hist, setHist] = useState(null);
  useEffect(() => {
    setHist(null);
    if (!product?.id) return;
    labdipHistory({ product_id: product.id, type_code: "" }).then(setHist).catch(() => setHist({ items: [] }));
  }, [product?.id]);
  return (
    <div className="grid gap-2" data-testid="existing-sku-section">
      <ProductSelect value={product?.id || ""} valueName={product ? `${product.sku} — ${product.name}` : ""}
        stage="finished" label="Pilih SKU aktif…" triggerTestId="existing-sku-select" onSelect={onPick} />
      <PartnerFields supplierId={supplierId} reason={reason} onChange={onRevalChange} />
      <p className="text-[10.5px] text-[#6B6B73]">SKU, spesifikasi, dan master tidak diubah. Hasil uji dicatat per supplier — lulus di supplier A tidak berarti lulus di supplier B. Proofing memakai artwork existing yang sudah ACC.</p>
      {product && <SupplierEligibilityPanel productId={product.id} />}
      {product && <HistoryList data={hist} />}
    </div>
  );
}
