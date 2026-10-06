import { useEffect, useMemo, useState } from "react";
import { Trash2, RotateCcw, Plus } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { formatCurrency } from "../../utils/formatters";

/** Baris SO yang bisa di-override: qty (non-roll), harga/diskon (butuh persetujuan), hapus, tambah. */
export function OverrideLinesEditor({ items, lines, setLines, adds, setAdds }) {
  const set = (pid, patch) => setLines((cur) => ({ ...cur, [pid]: { ...(cur[pid] || {}), ...patch } }));
  return (
    <div className="space-y-1.5" data-testid="override-lines">
      {items.map((it) => {
        const v = lines[it.product_id] || {};
        const removed = !!v.remove;
        const roll = it.purchase_mode === "roll";
        return (
          <div key={it.product_id} data-testid={`override-line-${it.product_id}`}
            className={`rounded-md border px-2.5 py-2 ${removed ? "border-[#F5C2C0] bg-[#FDF2F1] opacity-70" : "border-[#EFF0F2] bg-white"}`}>
            <div className="flex items-center justify-between gap-2">
              <p className="min-w-0 truncate text-[12px] font-semibold">{it.product_name} <span className="font-normal text-[#8E8E93]">· {it.sku}</span></p>
              <button type="button" data-testid={`override-remove-${it.product_id}`} className="icon-button"
                onClick={() => set(it.product_id, { remove: !removed })} title={removed ? "Batalkan hapus" : "Hapus baris"}>
                {removed ? <RotateCcw size={13} /> : <Trash2 size={13} className="text-[#C0392B]" />}
              </button>
            </div>
            {!removed && (
              <div className="mt-1.5 grid grid-cols-3 gap-2">
                <Field label={`Qty (${it.unit})`} testId={`override-qty-${it.product_id}`} disabled={roll}
                  value={v.quantity ?? it.quantity} onChange={(x) => set(it.product_id, { quantity: x })} />
                <Field label="Harga satuan" testId={`override-price-${it.product_id}`}
                  value={v.price ?? it.price} onChange={(x) => set(it.product_id, { price: x })} />
                <Field label="Diskon %" testId={`override-disc-${it.product_id}`}
                  value={v.discount_percent ?? (it.discount_percent || 0)} onChange={(x) => set(it.product_id, { discount_percent: x })} />
              </div>
            )}
            {roll && !removed && <p className="mt-1 text-[10px] text-[#8E8E93]">Baris per-roll — qty mengikuti roll; ubah lewat tombol "Ganti Roll".</p>}
          </div>
        );
      })}
      <AddItemRow items={items} adds={adds} setAdds={setAdds} />
    </div>
  );
}

function Field({ label, value, onChange, testId, disabled = false }) {
  return (
    <label className="block">
      <span className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</span>
      <input data-testid={testId} type="number" min="0" className="field" disabled={disabled} value={value}
        onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

function AddItemRow({ items, adds, setAdds }) {
  const [products, setProducts] = useState([]);
  const [q, setQ] = useState("");
  useEffect(() => {
    axios.get(`${API}/products`, { params: { orderable_only: true } })
      .then((r) => setProducts(Array.isArray(r.data) ? r.data : [])).catch(() => setProducts([]));
  }, []);
  const taken = useMemo(() => new Set([...items.map((i) => i.product_id), ...adds.map((a) => a.product_id)]), [items, adds]);
  const hits = q.trim().length < 2 ? [] : products.filter((p) => !taken.has(p.id)
    && `${p.name} ${p.sku}`.toLowerCase().includes(q.trim().toLowerCase())).slice(0, 6);
  return (
    <div className="rounded-md border border-dashed border-[#CBDFFF] bg-[#F7FAFF] p-2" data-testid="override-add">
      <p className="text-[10px] font-bold uppercase tracking-wide text-[#0058CC]">Tambah barang</p>
      {adds.map((a, i) => (
        <div key={a.product_id} className="mt-1 flex items-center gap-2 text-[11.5px]" data-testid={`override-add-row-${a.product_id}`}>
          <span className="min-w-0 flex-1 truncate">{a.name} <span className="text-[#8E8E93]">· {formatCurrency(a.price)}/{a.unit}</span></span>
          <input type="number" min="0" className="field !w-24" data-testid={`override-add-qty-${a.product_id}`} value={a.quantity}
            onChange={(e) => setAdds((cur) => cur.map((x, j) => (j === i ? { ...x, quantity: e.target.value } : x)))} />
          <button type="button" className="icon-button" onClick={() => setAdds((cur) => cur.filter((_, j) => j !== i))}><Trash2 size={12} /></button>
        </div>
      ))}
      <input data-testid="override-add-search" className="field mt-1.5" placeholder="Cari nama / SKU (min. 2 huruf)" value={q} onChange={(e) => setQ(e.target.value)} />
      {hits.map((p) => (
        <button key={p.id} type="button" data-testid={`override-add-pick-${p.id}`}
          onClick={() => { setAdds((cur) => [...cur, { product_id: p.id, name: p.name, price: p.price, unit: p.base_unit || "meter", quantity: 1 }]); setQ(""); }}
          className="mt-1 flex w-full items-center gap-1 rounded px-2 py-1 text-left text-[11.5px] hover:bg-white">
          <Plus size={11} className="text-[#0058CC]" /> {p.name} <span className="text-[#8E8E93]">· {p.sku}</span>
        </button>
      ))}
    </div>
  );
}
