/**
 * L02 LN-023-T02 — rekonsiliasi PO ditutup-kurang: sisa order, tagihan supplier, kelebihan bayar.
 */
import { useEffect, useState } from "react";
import axios, { API } from "../../../services/apiClient";
import { formatCurrency } from "../../../utils/formatters";

const ROWS = [
  ["ordered_value", "Nilai order"], ["received_value", "Nilai diterima"], ["cancelled_value", "Sisa dibatalkan"],
  ["billed_total", "Sudah ditagih supplier"], ["paid_total", "Sudah dibayar"],
];

export const POCloseSettlementPanel = ({ po }) => {
  const [data, setData] = useState(null);
  useEffect(() => {
    axios.get(`${API}/purchase-orders/${po.id}/close-settlement`).then((r) => setData(r.data)).catch(() => setData(null));
  }, [po.id, po.status]);
  const s = data?.current;
  if (!s) return null;
  return (
    <div data-testid="po-close-settlement" className="rounded-md border border-stone-200 bg-white p-2.5 text-[11px] space-y-1.5">
      <p className="font-bold text-stone-700">Rekonsiliasi tutup-kurang
        <span data-testid="po-close-settlement-balanced" className={`ml-2 rounded px-1.5 text-[10px] ${s.balanced ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
          {s.balanced ? "seimbang" : "tidak seimbang"}
        </span>
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-1.5">
        {ROWS.map(([k, label]) => (
          <div key={k}><p className="text-stone-500">{label}</p>
            <p className="font-semibold tabular-nums" data-testid={`po-close-${k}`}>{formatCurrency(s[k] || 0)}</p></div>
        ))}
      </div>
      {s.follow_ups.length > 0 && (
        <ul className="space-y-0.5">
          {s.follow_ups.map((f) => (
            <li key={f.code} data-testid={`po-close-follow-${f.code}`} className="text-amber-800">
              • {f.label} <b className="tabular-nums">{formatCurrency(f.amount)}</b> ({f.owner === "finance" ? "Finance" : "MD"})
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
