import { useState } from "react";
import { Truck } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";

const BEARER_OPTS = [{ value: "company", label: "Ditanggung perusahaan" }, { value: "customer", label: "Ditanggung customer" }];

const TYPES = [["customer_return", "Ongkir retur dari customer"], ["qc_trip", "Perjalanan Jakarta–Rancamalang (QC)"],
  ["replacement_shipping", "Kirim barang pengganti"]];
const TERMINAL = ["refund_settled", "credit_settled", "nego_settled", "rejected", "cancelled"];
const rp = (v) => `Rp ${Number(v || 0).toLocaleString("id-ID")}`;

// LN-091 KLR-11 — penanggung biaya logistik dipilih per kasus.
export default function ReturnLogisticsPanel({ ret, onChanged }) {
  const cur = Object.fromEntries(((ret.logistics_costs || {}).costs || []).map((c) => [c.type, c]));
  const [f, setF] = useState(() => Object.fromEntries(TYPES.map(([t]) => [t, { bearer: cur[t]?.bearer || "company", amount: cur[t]?.amount ?? "", note: cur[t]?.note || "" }])));
  const [msg, setMsg] = useState("");
  const locked = TERMINAL.includes(ret.status);
  const save = async () => {
    setMsg("");
    const costs = TYPES.filter(([t]) => f[t].amount !== "").map(([t]) => ({ type: t, bearer: f[t].bearer, amount: Number(f[t].amount) || 0, note: f[t].note }));
    try { await axios.put(`${API}/sales-returns/${ret.id}/logistics`, { costs }); setMsg("Tersimpan."); onChanged?.(); }
    catch (e) { setMsg(e.response?.data?.detail || e.message); }
  };
  const lc = ret.logistics_costs || {};
  return (
    <div className="mb-3 rounded-lg border border-[#EDEEF1] bg-white px-3 py-2.5 space-y-2 text-xs" data-testid="return-logistics-panel">
      <div className="flex items-center gap-2 text-sm font-semibold"><Truck size={14} className="text-[#0058CC]" /> Biaya logistik retur
        {lc.costs?.length > 0 && <span className="text-xs font-normal text-[#6B6B73]" data-testid="logistics-totals">customer {rp(lc.customer_total)} · perusahaan {rp(lc.company_total)}</span>}</div>
      {TYPES.map(([t, label]) => (
        <div key={t} className="flex flex-wrap items-center gap-2">
          <span className="w-60">{label}</span>
          <div className="w-52"><KNSelect data-testid={`logistics-bearer-${t}`} disabled={locked} className="field text-xs" value={f[t].bearer}
            options={BEARER_OPTS} onValueChange={(v) => setF({ ...f, [t]: { ...f[t], bearer: v } })} /></div>
          <input data-testid={`logistics-amount-${t}`} disabled={locked} type="number" min={0} placeholder="Rp" className="field w-28" value={f[t].amount}
                 onChange={(e) => setF({ ...f, [t]: { ...f[t], amount: e.target.value } })} />
          <input data-testid={`logistics-note-${t}`} disabled={locked} className="field w-48" placeholder="Catatan" value={f[t].note}
                 onChange={(e) => setF({ ...f, [t]: { ...f[t], note: e.target.value } })} />
        </div>
      ))}
      {!locked && <button type="button" data-testid="logistics-save" onClick={save} className="secondary-button text-xs">Simpan penanggung biaya</button>}
      {msg && <span className="ml-2" data-testid="logistics-msg">{msg}</span>}
    </div>
  );
}
