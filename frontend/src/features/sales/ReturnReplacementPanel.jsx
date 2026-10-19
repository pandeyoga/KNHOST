import { useCallback, useEffect, useState } from "react";
import { Repeat } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { canCurrent } from "../../config/roles";

const rp = (v) => `Rp ${Number(v || 0).toLocaleString("id-ID")}`;
const errText = (e) => e.response?.data?.detail?.message || e.response?.data?.detail || e.message;

// LN-090 — pesanan pengganti nyata: qty dari QC (yard), harga transaksi asal, saldo retur → selisih.
export default function ReturnReplacementPanel({ ret, onChanged, onNavigate }) {
  const [pv, setPv] = useState(null);
  const [qty, setQty] = useState({});
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => axios.get(`${API}/sales-returns/${ret.id}/replacement`).then((r) => {
    setPv(r.data);
    setQty(Object.fromEntries(r.data.obligation.map((o) => [o.product_id, o.qty_yard ?? ""])));
  }).catch(() => setPv(null)), [ret.id]);
  useEffect(() => { if (ret.return_type === "penggantian") load(); }, [load, ret.return_type, ret.updated_at]);
  if (ret.return_type !== "penggantian" || !pv) return null;
  const s = pv.summary || {};
  const create = async () => {
    setErr(""); setBusy(true);
    try {
      const items = Object.entries(qty).filter(([, v]) => Number(v) > 0).map(([product_id, v]) => ({ product_id, qty_yard: Number(v) }));
      await axios.post(`${API}/sales-returns/${ret.id}/replacement-order`, { items });
      load(); onChanged?.();
    } catch (e) { setErr(errText(e)); } finally { setBusy(false); }
  };
  const canCreate = !pv.order_id && ret.status === "credit_settled" && canCurrent("order", "create");
  return (
    <div className="mb-3 rounded-lg border border-[#EDEEF1] bg-white px-3 py-2.5 space-y-2 text-xs" data-testid="return-replacement-panel">
      <div className="flex items-center gap-2 text-sm font-semibold"><Repeat size={14} className="text-[#0058CC]" /> Pesanan pengganti
        <span className="text-xs font-normal text-[#6B6B73]">Kewajiban = qty aktual QC (yard) · harga transaksi asal</span></div>
      <table className="min-w-full" data-testid="replacement-obligation-table">
        <thead className="text-left text-[#6B6B73]"><tr>{["Produk", "Grade wajib", "Qty QC", "Kewajiban (yd)", "Harga asal", "Nilai", "Pengganti (yd)"].map((h) => <th key={h} className="py-1 pr-3">{h}</th>)}</tr></thead>
        <tbody>{pv.obligation.map((o) => (
          <tr key={o.product_id} data-testid={`replacement-row-${o.product_id}`}>
            <td className="pr-3">{o.product_name}</td>
            <td className="pr-3" data-testid={`replacement-grade-${o.product_id}`}>{o.sold_grade || "—"}</td>
            <td className="pr-3">{o.qty_base} {o.unit_base}</td>
            <td className="pr-3">{o.qty_yard ?? <span className="text-[#8A5A00]" title={o.conversion_error} data-testid={`replacement-conv-missing-${o.product_id}`}>Faktor yard↔{o.unit_base} belum diatur di master produk</span>}</td>
            <td className="pr-3">{rp(o.unit_price_base)}/{o.unit_base}</td><td className="pr-3">{rp(o.value)}</td>
            <td>{canCreate && !o.conversion_error ? <input data-testid={`replacement-qty-${o.product_id}`} type="number" className="field w-24" value={qty[o.product_id] ?? ""}
                                    onChange={(e) => setQty({ ...qty, [o.product_id]: e.target.value })} /> : "—"}</td>
          </tr>))}</tbody>
      </table>
      {pv.order_id ? (
        <div className="rounded-md bg-[#F2F7FF] p-2 space-y-0.5" data-testid="replacement-summary">
          <p>Pesanan pengganti: <button type="button" className="font-semibold text-[#0058CC]" data-testid="replacement-order-link"
             onClick={() => onNavigate?.("orders")}>{pv.order_number}</button></p>
          <p>Nilai pengganti {rp(s.replacement_total)} · saldo retur dipakai {rp(s.credit_applied)} · <b data-testid="replacement-to-bill">ditagih {rp(s.to_bill)}</b> · sisa saldo customer {rp(s.remaining_credit)}</p>
          {s.credit_error && <p className="text-[#B45309]">Saldo belum terpakai otomatis: {s.credit_error}</p>}
          <p className="text-[#6B6B73]">{s.rule}</p>
        </div>
      ) : (
        <>
          {ret.status !== "credit_settled" && <p className="text-[#8A4B08]" data-testid="replacement-hint">Selesaikan retur sebagai Store Credit setelah QC; nilainya menjadi saldo untuk pesanan pengganti.</p>}
          {canCreate && <button type="button" data-testid="replacement-create" disabled={busy} onClick={create} className="primary-button text-xs">Buat pesanan pengganti</button>}
        </>
      )}
      {err && <p className="text-[#C62828]" data-testid="replacement-error">{err}</p>}
    </div>
  );
}
