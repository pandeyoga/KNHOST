/** P03 IMP-26 — transfer untuk memenuhi SO: pilih SO yang punya roll berkomitmen di gudang asal. */
import { useEffect, useState } from "react";
import axios, { API } from "../../../services/apiClient";
import KNSelect from "../../../components/KNSelect";

export default function TransferSoPicker({ sourceWarehouseId, soId, onSoChange, onAddRolls }) {
  const [options, setOptions] = useState([]);
  const [rolls, setRolls] = useState([]);
  const [sel, setSel] = useState({});

  useEffect(() => {
    if (!sourceWarehouseId) { setOptions([]); return; }
    axios.get(`${API}/transfers/so-options`, { params: { source_warehouse_id: sourceWarehouseId } })
      .then((r) => setOptions(r.data || [])).catch(() => setOptions([]));
  }, [sourceWarehouseId]);
  useEffect(() => {
    setSel({});
    if (!soId || !sourceWarehouseId) { setRolls([]); return; }
    axios.get(`${API}/transfers/so-rolls`, { params: { sales_order_id: soId, source_warehouse_id: sourceWarehouseId } })
      .then((r) => setRolls(r.data || [])).catch(() => setRolls([]));
  }, [soId, sourceWarehouseId]);

  const add = () => {
    const chosen = rolls.filter((r) => sel[r.roll_id]);
    const byProd = {};
    chosen.forEach((r) => {
      const it = byProd[r.product_id] || (byProd[r.product_id] = { product_id: r.product_id, roll_ids: [], rolls: [], qty: 0, unit: r.unit });
      it.roll_ids.push(r.roll_id); it.rolls.push(r); it.qty = Math.round((it.qty + r.length) * 100) / 100;
    });
    onAddRolls(Object.values(byProd));
    setSel({});
  };
  if (!sourceWarehouseId) return null;
  return (
    <div data-testid="transfer-so-picker" className="rounded-xl border border-[#D7E3F7] bg-[#F7FAFF] p-3 mb-4">
      <label className="block text-sm font-medium text-[#3C3C43] mb-1">Untuk memenuhi SO (opsional)</label>
      <KNSelect data-testid="transfer-so-select" value={soId} onValueChange={onSoChange} searchable
        options={[{ value: "", label: options.length ? "Tidak terkait SO" : "Tidak ada SO dengan roll berkomitmen di gudang ini" },
          ...options.map((s) => ({ value: s.id, label: `${s.number} · ${s.customer_name || ""} (${s.rolls_here} roll di sini)` }))]} />
      {soId && (
        <div className="mt-2 space-y-1">
          <p className="text-[11px] text-[#3C3C43]">Roll berkomitmen ke SO ini ikut pindah tanpa reservasi baru dan tetap terkunci untuk SO selama perjalanan.</p>
          <div className="max-h-40 overflow-y-auto rounded border border-[#E5E5EA] bg-white">
            {rolls.map((r) => (
              <label key={r.roll_id} data-testid={`so-roll-${r.roll_no}`} className={`flex items-center gap-2 px-2 py-1 text-[11px] ${r.in_transfer ? "opacity-50" : ""}`}>
                <input type="checkbox" disabled={!!r.in_transfer} checked={!!sel[r.roll_id]} onChange={(e) => setSel({ ...sel, [r.roll_id]: e.target.checked })} />
                <span className="font-mono">{r.roll_no}</span><span>{r.sku}</span><span className="ml-auto tabular-nums">{r.length} {r.unit}</span>
                {r.in_transfer && <span className="text-[#B4231F]">di {r.in_transfer}</span>}
              </label>
            ))}
          </div>
          <button data-testid="transfer-so-add" disabled={!Object.values(sel).some(Boolean)} onClick={add}
            className="rounded-full bg-[#007AFF] px-3 py-1 text-xs text-white disabled:opacity-40">Tambahkan roll SO terpilih</button>
        </div>
      )}
    </div>
  );
}
