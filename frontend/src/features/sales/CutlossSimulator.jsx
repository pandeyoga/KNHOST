import { useState } from "react";
import { Scissors } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { formatCurrency } from "../../utils/formatters";

// 23 Okt — formatter baku (dulu toLocaleString tanpa batas desimal → "Rp 20.998,967").
const rp = (v) => formatCurrency(v);

// LN-092 — hitung contoh cutloss (KLR-01/02) & diskon nominal (KLR-06/07). Tidak memposting.
export default function CutlossSimulator() {
  const [c, setC] = useState({ roll_length: 120, defect_from: 46, defect_to: 60, unit_price: 50000 });
  const [d, setD] = useState({ qty_affected: 15, amount: 250000 });
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
      <p className="flex items-center gap-2 text-[13px] font-semibold"><Scissors size={14} /> Contoh hitung cutloss & diskon (tidak memposting)</p>
      <div className="flex flex-wrap items-end gap-3">
        {num(c, setC, "roll_length", "Panjang roll (yd)", "cutloss-length")}
        {num(c, setC, "defect_from", "Cacat dari yd", "cutloss-from")}
        {num(c, setC, "defect_to", "Cacat s/d yd", "cutloss-to")}
        {num(c, setC, "unit_price", "Harga transaksi/yd", "cutloss-price")}
        <span className="w-px h-8 bg-[#E5E5EA]" />
        {num(d, setD, "qty_affected", "Qty cacat diskon", "discount-qty")}
        {num(d, setD, "amount", "Nominal diskon (Rp)", "discount-amount")}
        <button type="button" data-testid="cutloss-simulate" onClick={run} className="primary-button">Hitung</button>
      </div>
      {err && <p className="text-[12px] text-[#C62828]">{String(err)}</p>}
      {res && (
        <div className="space-y-1 text-[12px]" data-testid="cutloss-result">
          <p data-testid="cutloss-pieces">Customer menerima potongan baik: <b>{res.customer_pieces.join(" yd + ")} yd</b> · qty cacat {res.defect_qty} yd · kompensasi <b>{rp(res.compensation_value)}</b> {res.reconciles ? "✓ seimbang" : "✗"}</p>
          <p className="text-[#8A4B08]" data-testid="cutloss-note">{res.note}</p>
          {disc && <p data-testid="discount-result">Diskon: <b>{rp(disc.discount_value)}</b> untuk {disc.qty_affected} qty cacat · stok tidak bergerak · {disc.note}</p>}
        </div>
      )}
    </div>
  );
}
