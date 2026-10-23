/** P03 — tabel roll transfer (status aktual per roll) + hasil penerimaan terakhir. */
import { STATE_TXT } from "./transferConstants";
import KNSelect from "../../../components/KNSelect";

const TONE = {
  in_transit: "bg-orange-100 text-orange-700", received: "bg-green-100 text-green-700",
  received_damaged: "bg-red-100 text-red-700", received_hold: "bg-yellow-100 text-yellow-800",
  returned: "bg-gray-200 text-gray-700",
};

export function ReceiptRollTable({ rows = [], picked, setPicked, editable }) {
  const set = (id, patch) => setPicked({ ...picked, [id]: { ...(picked[id] || {}), ...patch } });
  return (
    <div className="max-h-64 overflow-y-auto rounded-lg border border-[#E5E5EA] bg-white">
      <table className="w-full text-[11px]" data-testid="transfer-receipt-table">
        <thead className="sticky top-0 bg-[#F2F2F7] text-[#6B6B73]">
          <tr><th className="w-6 p-1" /><th className="p-1 text-left">Roll</th><th className="text-left">Barang</th>
            <th className="text-right">Ukuran</th><th className="text-left pl-2">Status</th><th className="text-left">Kondisi tiba</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const can = editable && r.state === "in_transit";
            const p = picked[r.roll_id] || {};
            return (
              <tr key={r.roll_id} data-testid={`receipt-row-${r.roll_no}`} className="border-t border-[#F0F0F3]">
                <td className="p-1 text-center">
                  {can && <input type="checkbox" data-testid={`receipt-pick-${r.roll_no}`} checked={!!p.on}
                    onChange={(e) => set(r.roll_id, { on: e.target.checked })} />}
                </td>
                <td className="p-1 font-mono">{r.roll_no}{r.lot ? <span className="block text-[9.5px] text-[#8E8E93]">{r.lot}</span> : null}</td>
                <td>{r.sku}{r.committed_so ? <span className="ml-1 rounded bg-[#E8F0FE] px-1 text-[9.5px] text-[#0058CC]">SO</span> : null}</td>
                <td className="text-right tabular-nums">{r.length} {r.unit}</td>
                <td className="pl-2"><span data-testid={`receipt-state-${r.roll_no}`} className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${TONE[r.state] || "bg-gray-100 text-gray-600"}`}>{STATE_TXT[r.state] || r.state}</span>
                  {r.bin_code && <span className="ml-1 text-[9.5px] text-[#6B6B73]">{r.bin_code}</span>}</td>
                <td className="pr-1">
                  {can && p.on && (
                    <div className="flex items-center gap-1">
                      <KNSelect data-testid={`receipt-outcome-${r.roll_no}`} value={p.outcome || "received"} aria-label="Hasil terima"
                        onValueChange={(v) => set(r.roll_id, { outcome: v })} className="!h-auto !w-auto rounded border border-gray-200 text-[10.5px]"
                        options={[{ value: "received", label: "Baik" }, { value: "damaged", label: "Rusak" }]} />
                      {p.outcome === "damaged" && <input data-testid={`receipt-note-${r.roll_no}`} value={p.note || ""} placeholder="Keterangan rusak"
                        onChange={(e) => set(r.roll_id, { note: e.target.value })} className="w-28 rounded border border-gray-200 px-1 text-[10.5px]" />}
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const RES_TXT = { received: "Diterima", damaged: "Diterima rusak", hold: "Diterima ditahan (pengecualian)", already: "Sudah diterima",
  blocked_rules: "Ditolak aturan gudang", wrong_roll: "Roll salah", not_in_transit: "Bukan dalam perjalanan" };

export function ReceiptResults({ results = [] }) {
  if (!results.length) return null;
  return (
    <ul data-testid="transfer-receipt-results" className="space-y-0.5 text-[11px]">
      {results.map((x, i) => (
        <li key={i} data-testid={`receipt-result-${x.roll_no || x.ref}`} className={["received", "already"].includes(x.result) ? "text-[#0F766E]" : "text-[#B4231F]"}>
          <b>{x.roll_no || x.ref}</b>: {RES_TXT[x.result] || x.result}{x.bin_code ? ` → ${x.bin_code}` : ""}
          {x.placement_error ? ` (gagal simpan ke bin: ${x.placement_error})` : ""}
          {x.violations ? ` — ${x.violations[0]}` : x.message && !["received"].includes(x.result) ? ` — ${x.message}` : ""}
        </li>
      ))}
    </ul>
  );
}
