import { useEffect, useState } from "react";
import { Truck } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import LogisticsCostRow from "./LogisticsCostRow";
import { Panel } from "../../components/DetailParts";
import { formatCurrency } from "../../utils/formatters";

const TERMINAL = ["refund_settled", "credit_settled", "nego_settled", "settled", "rejected", "cancelled"];

// LN-091 KLR-11 + GL-01 — cara kirim, penanggung, akun pembayaran (Finance), PT pembeban; jurnal otomatis.
export default function ReturnLogisticsPanel({ ret, onChanged }) {
  const [ctx, setCtx] = useState(null);
  const [f, setF] = useState({});
  const [msg, setMsg] = useState("");
  const locked = TERMINAL.includes(ret.status);
  useEffect(() => {
    axios.get(`${API}/sales-returns/${ret.id}/logistics`).then((r) => {
      setCtx(r.data);
      const cur = Object.fromEntries(((r.data.logistics_costs || {}).costs || []).map((c) => [c.type, c]));
      setF(Object.fromEntries(Object.keys(r.data.types).map((t) => [t, {
        mode: cur[t]?.mode || "third_party", bearer: cur[t]?.bearer || "company", amount: cur[t]?.amount ?? "",
        vat_amount: cur[t]?.vat_amount || "", pay_account_code: cur[t]?.pay_account_code || "",
        charged_entity_id: cur[t]?.charged_entity_id || r.data.default_entity_id, note: cur[t]?.note || "",
        journal_entry_number: cur[t]?.journal_entry_number || "", filled: !!cur[t] }])));
    }).catch((e) => setMsg(e.response?.data?.detail || e.message));
  }, [ret.id, ret.status]);
  if (!ctx) return (
    <Panel icon={Truck} title="Biaya logistik retur" testId="return-logistics-panel">
      <p className={`text-[11.5px] ${msg ? "font-semibold text-[#A8221A]" : "text-[#6B6B73]"}`}>{msg || "Memuat biaya logistik…"}</p>
    </Panel>
  );
  const save = async () => {
    setMsg("");
    const costs = Object.entries(f).filter(([, v]) => v.filled || v.mode === "pickup" || v.amount !== "")
      .map(([type, v]) => ({ type, mode: v.mode, bearer: v.bearer, amount: Number(v.amount) || 0, vat_amount: Number(v.vat_amount) || 0,
        pay_account_code: v.pay_account_code, charged_entity_id: v.charged_entity_id, note: v.note }));
    try {
      const r = await axios.put(`${API}/sales-returns/${ret.id}/logistics`, { costs });
      const je = Object.fromEntries(r.data.costs.map((c) => [c.type, c.journal_entry_number]));
      setF(Object.fromEntries(Object.entries(f).map(([t, v]) => [t, { ...v, journal_entry_number: je[t] || "" }])));
      setMsg("Tersimpan — jurnal ongkir diperbarui."); onChanged?.();
    } catch (e) { setMsg(e.response?.data?.detail || e.message); }
  };
  const lc = ctx.logistics_costs || {};
  return (
    <Panel icon={Truck} title="Biaya logistik retur" testId="return-logistics-panel"
      right={lc.costs?.length > 0 && <span className="text-[11px] tabular-nums text-[#6B6B73]" data-testid="logistics-totals">pelanggan {formatCurrency(lc.customer_total)} · perusahaan {formatCurrency(lc.company_total)}</span>}>
      <div className="space-y-2 text-xs">
      <p className="text-[11px] text-[#6B6B73]">Dicatat saat awal pengiriman. Ongkir ditanggung KN langsung dijurnal; akun pembayaran dipilih Finance. Ongkir armada KN yang dibayar pelanggan ditagih terpisah.</p>
      {Object.entries(ctx.types).map(([t, label]) => f[t] && (
        <LogisticsCostRow key={t} type={t} label={label} v={f[t]} ctx={ctx} locked={locked}
          onChange={(nv) => setF({ ...f, [t]: { ...nv, filled: true } })} />))}
      <div className="flex flex-wrap items-center gap-2 border-t border-[#F2F3F5] pt-2.5">
        {!locked && <button type="button" data-testid="logistics-save" onClick={save} className="secondary-button text-xs">Simpan biaya logistik</button>}
        {msg && <span className="text-[11.5px] text-[#3C3C43]" data-testid="logistics-msg">{msg}</span>}
      </div>
      </div>
    </Panel>
  );
}
