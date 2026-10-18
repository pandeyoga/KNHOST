/** L04 LN-043 — buku bahan makloon: cadangan vs fisik vs di mitra vs terpakai/kembali/susut, plus penjelasan. */
import { useEffect, useState } from "react";
import { Scale } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { Panel } from "../../../components/DetailParts";
import { formatQty } from "../../../utils/formatters";

const CELLS = [["forecast_need", "Kebutuhan (estimasi)"], ["reserved", "Dicadangkan"], ["issued", "Dikirim ke mitra"],
  ["at_partner", "Masih di mitra"], ["consumed", "Terpakai jadi hasil"], ["returned", "Kembali ke gudang"], ["lost", "Susut/hilang"]];

export default function MakloonMaterialLedger({ mkoId, version }) {
  const [d, setD] = useState(null);
  useEffect(() => {
    axios.get(`${API}/makloon-orders/${mkoId}/material-ledger`).then(({ data }) => setD(data)).catch(() => setD(null));
  }, [mkoId, version]);
  if (!d || !d.material_product_id) return null;
  const vals = { forecast_need: d.forecast_need, reserved: d.reservation.active, ...d.material };
  return (
    <Panel icon={Scale} title={`Buku bahan · ${d.material_name}`} testId="mko-material-ledger" className="max-sm:!pb-14"
      right={<span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${d.reconciled ? "bg-[#E7F6F3] text-[#0F766E]" : "bg-[#FDECEC] text-[#B4231F]"}`} data-testid="mko-ledger-reconciled">{d.reconciled ? "Seimbang" : "Ada selisih"}</span>}>
      <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4 lg:grid-cols-7">
        {CELLS.map(([k, label]) => (
          <div key={k} className="rounded-lg bg-[#FAFBFC] p-1.5">
            <p className="text-[9.5px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p>
            <p className="text-[12.5px] font-bold tabular-nums" data-testid={`mko-ledger-${k}`}>{formatQty(vals[k] || 0)} {d.unit}</p>
          </div>
        ))}
      </div>
      {d.reservation.shortage > 0 && <p className="mt-1.5 text-[11px] text-[#B26A00]" data-testid="mko-ledger-shortage">Kekurangan cadangan {formatQty(d.reservation.shortage)} {d.unit} — stok bebas tidak cukup saat komitmen dibuat.</p>}
      {d.stock_now && <p className="mt-1.5 text-[11px] text-[#6B6B73]" data-testid="mko-ledger-stock">Stok gudang sekarang: fisik {formatQty(d.stock_now.available_physical)} · dicadangkan semua order {formatQty(d.stock_now.reserved_all_orders)} · bebas untuk komitmen baru {formatQty(d.stock_now.free_for_new_commitment)} {d.unit}</p>}
      <ul className="mt-1.5 space-y-0.5 text-[11px] text-[#3C3C43]" data-testid="mko-ledger-explain">
        {d.explain.map((x, i) => <li key={`ex${i}`}>• {x}</li>)}
      </ul>
      {d.steps.filter((s) => s.actual_output != null).map((s) => (
        <p key={s.seq} className="mt-1 text-[11px] text-[#6B6B73]" data-testid={`mko-ledger-output-${s.seq}`}>
          Langkah {s.seq}: hasil aktual {formatQty(s.actual_output)} {s.output_unit} vs estimasi {formatQty(s.forecast_output)} ({s.output_variance >= 0 ? "+" : ""}{formatQty(s.output_variance)}) — stok & nilai memakai hasil aktual.
        </p>
      ))}
      {d.steps.filter((s) => !s.reconciled).map((s) => (
        <p key={`u${s.seq}`} className="mt-1 text-[11px] font-semibold text-[#B4231F]" data-testid={`mko-ledger-gap-${s.seq}`}>Langkah {s.seq}: {formatQty(s.unexplained)} {s.input_unit} belum dijelaskan.</p>
      ))}
    </Panel>
  );
}
