import { useState } from "react";
import { Scissors } from "lucide-react";
import axios, { API } from "../../services/apiClient";

const rp = (v) => `Rp ${Number(v || 0).toLocaleString("id-ID")}`;

// LN-092 — simulasi cutloss & diskon; posting dikunci selama KLR-01/02/06/07 pending.
export default function CutlossSimulator() {
  const [c, setC] = useState({ roll_length: 120, defect_from: 46, defect_to: 60, unit_price: 50000 });
  const [d, setD] = useState({ qty_affected: 120, unit_price: 50000, pct: 10 });
  const [res, setRes] = useState(null);
  const [disc, setDisc] = useState(null);
  const [err, setErr] = useState("");
  const run = async () => {
    setErr("");
    try {
      const [a, b] = await Promise.all([axios.post(`${API}/sales-returns/cutloss/simulate`, c), axios.post(`${API}/sales-returns/discount/simulate`, d)]);
      setRes(a.data); setDisc(b.data);
    } catch (e) { setErr(e.response?.data?.detail || e.message); }
  };
  const num = (obj, set, k, label, tid) => (
    <label className="flex flex-col gap-1 text-[12px]">{label}
      <input data-testid={tid} type="number" value={obj[k]} onChange={(e) => set({ ...obj, [k]: Number(e.target.value) })} className="field w-28" /></label>
  );
  return (
    <div className="mb-4 rounded-xl border border-[#E5E5EA] bg-white p-3 space-y-3" data-testid="cutloss-simulator">
      <p className="flex items-center gap-2 text-[13px] font-semibold"><Scissors size={14} /> Simulasi cutloss & diskon (tidak memposting)</p>
      <div className="flex flex-wrap items-end gap-3">
        {num(c, setC, "roll_length", "Panjang roll", "cutloss-length")}
        {num(c, setC, "defect_from", "Cacat dari", "cutloss-from")}
        {num(c, setC, "defect_to", "Cacat s/d", "cutloss-to")}
        {num(c, setC, "unit_price", "Harga/satuan", "cutloss-price")}
        <span className="w-px h-8 bg-[#E5E5EA]" />
        {num(d, setD, "qty_affected", "Qty diskon", "discount-qty")}
        {num(d, setD, "pct", "Diskon %", "discount-pct")}
        <button type="button" data-testid="cutloss-simulate" onClick={run} className="primary-button">Hitung</button>
      </div>
      {err && <p className="text-[12px] text-[#C62828]">{String(err)}</p>}
      {res && (
        <div className="space-y-1.5" data-testid="cutloss-result">
          <p className="text-[12px] text-[#8A4B08]" data-testid="cutloss-note">{res.note}</p>
          <table className="min-w-full text-[12px]">
            <thead className="text-left text-[#6B6B73]"><tr>{["Skenario", "Customer simpan", "Dikembalikan", "Masuk stok (baik)", "Cacat/waste", "Nilai kompensasi", "Rekonsiliasi"].map((h) => <th key={h} className="py-1 pr-3">{h}</th>)}</tr></thead>
            <tbody>
              {res.scenarios.map((s) => (
                <tr key={s.code} data-testid={`cutloss-row-${s.code}`} className={res.selected === s.code ? "font-semibold" : ""}>
                  <td className="py-1 pr-3">{s.label}{res.selected === s.code ? " (asumsi aktif)" : ""}</td>
                  <td className="pr-3">{s.customer_keeps}</td><td className="pr-3">{s.returned_qty}</td>
                  <td className="pr-3">{s.restock_good_qty}</td><td className="pr-3">{s.waste_qty}</td>
                  <td className="pr-3">{rp(s.compensation_value)}</td><td>{s.reconciles ? "✓ seimbang" : "✗"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {disc && <p className="text-[12px]" data-testid="discount-result">Diskon tanpa barang kembali: <b>{rp(disc.discount_value)}</b> · stok tidak bertambah · {disc.note}</p>}
        </div>
      )}
    </div>
  );
}
