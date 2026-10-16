import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { ErrorBox } from "./GrnBits";
import { KIND_LABEL, errText, grnApi } from "./grnApi";

const RANGES = [["90", "3 bulan"], ["180", "6 bulan"], ["365", "12 bulan"], ["", "Semua"]];
const sinceOf = (days) => (days ? new Date(Date.now() - Number(days) * 864e5).toISOString() : "");

/** Riwayat selisih per mitra dari kedatangan yang DITUTUP — siapa yang sering kirim kurang. */
export default function SupplierVariancePanel({ onOpenGrn }) {
  const [range, setRange] = useState("180");
  const [rows, setRows] = useState([]);
  const [err, setErr] = useState("");
  useEffect(() => { grnApi.variance(sinceOf(range)).then(setRows).catch((e) => setErr(errText(e))); }, [range]);
  return (
    <div className="space-y-3" data-testid="grn-variance-panel">
      <div className="flex items-center gap-1 text-[11px] font-semibold">
        {RANGES.map(([v, l]) => (
          <button key={l} data-testid={`grn-variance-range-${v || "all"}`} onClick={() => setRange(v)}
            className={`rounded-full border px-2.5 py-1 ${range === v ? "border-[#0058CC] bg-[#EEF4FF] text-[#0058CC]" : "border-[#E5E5EA]"}`}>{l}</button>
        ))}
      </div>
      <ErrorBox text={err} />
      <div className="overflow-x-auto rounded-xl border border-[#EFF0F2] bg-white">
        <table className="w-full text-left text-[11px]" data-testid="grn-variance-table">
          <thead className="bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73]">
            <tr>{["Mitra", "Kedatangan", "Bermasalah", "Baris kurang", "Total kurang", "Roll beda", "Tidak datang", "Lebih PO", "Klaim", "Terakhir"].map((h) => <th key={h} className="px-2 py-1.5">{h}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.partner_id} data-testid={`grn-variance-row-${r.partner_id}`} className="border-t border-[#EFF0F2] align-top">
                <td className="px-2 py-1.5">
                  <p className="font-semibold">{r.partner_name}</p>
                  {r.recent.map((g) => (
                    <button key={g.id} data-testid={`grn-variance-open-${g.id}`} onClick={() => onOpenGrn(g.id)} className="block text-[10px] text-[#0058CC]">
                      {g.number} · SJ {g.dn_number} · {g.kinds.map((k) => KIND_LABEL[k] || k).join(", ")}
                    </button>
                  ))}
                </td>
                <td className="px-2 tabular-nums">{r.grn_count}</td>
                <td className="px-2 tabular-nums">
                  <span className={r.issue_rate_pct >= 30 ? "inline-flex items-center gap-1 font-bold text-[#B4231F]" : ""}>
                    {r.issue_rate_pct >= 30 && <AlertTriangle size={11} />}{r.issue_rate_pct}%
                  </span>
                </td>
                <td className="px-2 tabular-nums">{r.short_lines}</td>
                <td className="px-2 font-semibold tabular-nums">{r.short_qty}</td>
                <td className="px-2 tabular-nums">{r.rolls_mismatch}</td>
                <td className="px-2 tabular-nums">{r.not_arrived}</td>
                <td className="px-2 tabular-nums">{r.over_remaining}</td>
                <td className="px-2 tabular-nums">{r.claims}</td>
                <td className="px-2 text-[10px]">{(r.last_closed_at || "").slice(0, 10)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <p className="p-3 text-[11px] text-[#6B6B73]" data-testid="grn-variance-empty">Belum ada kedatangan yang ditutup pada periode ini.</p>}
      </div>
    </div>
  );
}
