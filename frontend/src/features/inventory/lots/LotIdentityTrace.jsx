import { useState } from "react";
import { Search } from "lucide-react";
import { lotApi } from "./lotApi";

const errText = (e) => e.response?.data?.detail || e.message;

// LN-014 — telusur lewat nomor lot internal / lot supplier / dye lot / alias: kedua identitas tetap dibedakan.
export default function LotIdentityTrace({ onOpen }) {
  const [code, setCode] = useState("");
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const run = async () => {
    setErr("");
    try { setData(await lotApi.identityTrace(code)); } catch (e) { setErr(errText(e)); setData(null); }
  };
  return (
    <div className="rounded-md border border-[#EFF0F2] bg-white" data-testid="lot-identity-trace">
      <div className="flex flex-wrap items-center gap-2 border-b border-[#EFF0F2] bg-[#FAFBFC] px-2.5 py-1.5">
        <span className="text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Telusur identitas lot</span>
        <input data-testid="lot-trace-input" className="field !py-1 text-[11px] w-64" value={code} placeholder="lot internal / lot supplier (mis. 234) / alias"
          onChange={(e) => setCode(e.target.value)} onKeyDown={(e) => e.key === "Enter" && run()} />
        <button type="button" data-testid="lot-trace-submit" onClick={run} className="secondary-button !py-1 text-[11px]">
          <span className="flex items-center gap-1"><Search size={11} /> Telusur</span></button>
        {err && <span className="text-[11px] text-[#C62828]" data-testid="lot-trace-error">{err}</span>}
      </div>
      {data && (
        <div className="overflow-x-auto">
          {!data.rows.length && <p className="px-2.5 py-2 text-[11px] text-[#8E8E93]" data-testid="lot-trace-empty">Tidak ada lot dengan acuan “{data.code}”.</p>}
          {data.rows.length > 0 && (
            <table className="w-full text-[11px]" data-testid="lot-trace-table">
              <thead className="bg-[#FAFBFC] text-[10px] uppercase text-[#8E8E93]"><tr>
                <th className="px-2 py-1.5 text-left">Lot internal</th><th className="px-2 py-1.5 text-left">Lot supplier</th><th className="px-2 py-1.5 text-left">Dye / alias</th>
                <th className="px-2 py-1.5 text-left">Cocok di</th><th className="px-2 py-1.5 text-left">PO / SJ asal</th><th className="px-2 py-1.5 text-left">Roll / retur</th></tr></thead>
              <tbody className="divide-y divide-[#F2F2F5]">
                {data.rows.map((r) => (
                  <tr key={r.lot_id} data-testid={`lot-trace-row-${r.lot_id}`}>
                    <td className="px-2 py-1.5"><button type="button" className="font-mono font-semibold text-[#0058CC]" onClick={() => onOpen(r.lot_id)}>{r.lot_number}</button>
                      <span className="block text-[10px] text-[#8E8E93]">{r.product_name}</span></td>
                    <td className="px-2 py-1.5 font-mono">{r.supplier_lot || "—"}<span className="block font-sans text-[10px] text-[#8E8E93]">{r.supplier_name}</span></td>
                    <td className="px-2 py-1.5">{r.dye_lot || "—"}{r.internal_alias ? <span className="block">alias {r.internal_alias}</span> : null}</td>
                    <td className="px-2 py-1.5">{r.matched_on.join(", ")}</td>
                    <td className="px-2 py-1.5">{r.origin.po_number || r.origin.ref_number || "—"}
                      {r.origin.supplier_dn_numbers.length ? <span className="block text-[10px]">SJ {r.origin.supplier_dn_numbers.join(", ")}</span> : null}</td>
                    <td className="px-2 py-1.5">{r.roll_count} roll{r.return_rolls.length ? <span className="block text-[10px] text-[#9A6700]">retur: {r.return_rolls.map((x) => x.roll_no).join(", ")}</span> : null}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="px-2.5 py-1.5 text-[10px] text-[#6B6B73]">{data.note}</p>
        </div>
      )}
    </div>
  );
}
