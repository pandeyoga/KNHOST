import { useEffect, useState } from "react";
import { TrendingDown } from "lucide-react";
import axios, { API } from "../../services/apiClient";

const rp = (n) => `Rp ${Number(n || 0).toLocaleString("id-ID", { maximumFractionDigits: 0 })}`;

// LN-091-T02 — kerugian turun grade, terpisah dari kredit pelanggan (invoice lama tidak berubah).
export default function ReturnGradeLossPanel({ ret }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    axios.get(`${API}/sales-returns/${ret.id}/grade-impairments`).then((r) => setData(r.data)).catch(() => setData(null));
  }, [ret.id, ret.quarantine_released]);
  if (!data?.items?.length) return null;
  return (
    <div className="section-card" data-testid="return-grade-loss-panel">
      <div className="section-header flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5"><TrendingDown size={14} /> Kerugian turun grade</span>
        <b className="text-[#C62828]" data-testid="grade-loss-total">{rp(data.total)}</b>
      </div>
      <p className="px-1 text-[11px] text-[#6E6E73]">Dicatat sebagai beban kerugian persediaan (Dr 5-9500 / Cr 1-1300) — terpisah dari kredit pelanggan, invoice lama tidak diubah.</p>
      <div className="overflow-x-auto">
        <table className="w-full text-[11px]" data-testid="grade-loss-table">
          <thead className="bg-[#FAFBFC] text-[10px] uppercase text-[#8E8E93]"><tr>
            <th className="px-2 py-1.5 text-left">Roll</th><th className="px-2 py-1.5 text-left">Grade</th><th className="px-2 py-1.5 text-right">Qty</th>
            <th className="px-2 py-1.5 text-right">Harga daftar</th><th className="px-2 py-1.5 text-right">Selisih/satuan</th><th className="px-2 py-1.5 text-right">Kerugian</th><th className="px-2 py-1.5 text-left">Jurnal</th></tr></thead>
          <tbody className="divide-y divide-[#F2F2F5]">
            {data.items.map((x) => (
              <tr key={x.id} data-testid={`grade-loss-row-${x.roll_id}`}>
                <td className="px-2 py-1.5">{x.roll_no || x.roll_id}</td>
                <td className="px-2 py-1.5">{x.grade_before} ({x.factor_before}%) → {x.grade_after} ({x.factor_after}%)</td>
                <td className="px-2 py-1.5 text-right tabular-nums">{x.qty} {x.unit}</td>
                <td className="px-2 py-1.5 text-right tabular-nums">{rp(x.list_price)}</td>
                <td className="px-2 py-1.5 text-right tabular-nums">{rp(x.unit_loss)}{x.capped_to_book ? <span className="block text-[10px] text-[#8E8E93]">dibatasi nilai buku</span> : null}</td>
                <td className="px-2 py-1.5 text-right tabular-nums font-semibold">{rp(x.amount)}</td>
                <td className="px-2 py-1.5 font-mono text-[10.5px]">{x.je_number || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
