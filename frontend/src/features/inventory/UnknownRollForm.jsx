/** OPS-01 — kode roll tak dikenal: penyetuju menetapkan produk, pemilik & qty sebelum roll baru dibuat. */
import KNSelect from "../../components/KNSelect";

export default function UnknownRollForm({ lines, products = [], owners = [], specs, setSpecs }) {
  if (!lines.length) return null;
  const set = (id, patch) => setSpecs({ ...specs, [id]: { ...(specs[id] || {}), ...patch } });
  return (
    <div className="grid gap-1.5 rounded border border-[#FFE1B3] bg-[#FFF8EC] p-2" data-testid="unknown-roll-form">
      <p className="text-[11.5px] font-semibold">Kode tak dikenal — tetapkan produk & pemilik agar dibuat roll baru saat finalisasi (kosongkan = tetap exception)</p>
      {lines.map((ln) => (
        <div key={ln.id} className="flex flex-wrap items-center gap-2 text-[11.5px]" data-testid={`unknown-roll-${ln.code}`}>
          <span className="font-mono w-36 truncate">{ln.code}</span>
          <KNSelect data-testid={`unknown-roll-product-${ln.code}`} className="field flex-1 min-w-48" value={specs[ln.id]?.product_id || ""} placeholder="Produk"
            onValueChange={(v) => set(ln.id, { product_id: v })} options={products.map((p) => ({ value: p.id, label: `${p.sku} — ${p.name}` }))} />
          <KNSelect data-testid={`unknown-roll-owner-${ln.code}`} className="field w-40" value={specs[ln.id]?.owner_entity_id || ""} placeholder="Pemilik"
            onValueChange={(v) => set(ln.id, { owner_entity_id: v })} options={owners} />
          <input className="field w-24" type="number" min="0" placeholder={ln.measured_qty ?? "Qty"} value={specs[ln.id]?.qty ?? ""}
            data-testid={`unknown-roll-qty-${ln.code}`} onChange={(e) => set(ln.id, { qty: e.target.value })} />
        </div>
      ))}
    </div>
  );
}
