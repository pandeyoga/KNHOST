import { useEffect, useState } from "react";
import axios, { API } from "../services/apiClient";
import { formatQty } from "../utils/formatters";
import { unitShort } from "./RollPicker";

/** Panjang tiap roll tersedia (beli per yard/kg) — sales tahu isi roll sebelum menentukan qty. */
export default function RollLengthStrip({ productId, entityId, baseUnit, rollCount = 0, testId = "roll-length-strip" }) {
  const [rows, setRows] = useState(null);
  useEffect(() => {
    if (!productId || rollCount <= 0) { setRows([]); return; }
    let live = true;
    axios.get(`${API}/inventory/rolls/available`, {
      params: { product_id: productId, entity_id: entityId && entityId !== "all" ? entityId : "", all_entities: true, sort: "fefo", skip: 0, limit: 30 },
    }).then((r) => live && setRows(r.data?.items || [])).catch(() => live && setRows([]));
    return () => { live = false; };
  }, [productId, entityId, rollCount]);
  if (!rows || !rows.length) return rollCount > 0 ? <p className="mt-1 text-[10px] text-[#9A9BA3]" data-testid={testId}>{rollCount} roll</p> : null;
  const u = unitShort(baseUnit);
  return (
    <div className="mt-1.5" data-testid={testId}>
      <p className="text-[10px] font-semibold text-[#6B6B73]">Isi per roll ({rows.length}{rollCount > rows.length ? ` dari ${rollCount}` : ""}):</p>
      <div className="mt-0.5 flex flex-wrap gap-1">
        {rows.map((r) => (
          <span key={r.id} className="rounded-md border border-[#E5E5EA] bg-white px-1.5 py-0.5 text-[10.5px] font-semibold tabular-nums text-[#3C3C43]" data-testid={`${testId}-${r.id}`}>
            {formatQty(r.length_remaining)} {u}
          </span>
        ))}
      </div>
    </div>
  );
}
