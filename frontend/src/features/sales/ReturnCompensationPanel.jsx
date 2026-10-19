import { useCallback, useEffect, useState } from "react";
import { Scissors, BadgePercent, Trash2 } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import { canCurrent } from "../../config/roles";
import CutlossSplitPanel from "./CutlossSplitPanel";

const rp = (v) => `Rp ${Number(v || 0).toLocaleString("id-ID")}`;
const errText = (e) => e.response?.data?.detail?.message || e.response?.data?.detail || e.message;
const TERMINAL = ["refund_settled", "credit_settled", "nego_settled", "rejected", "cancelled"];

function CutlossForm({ ret, onDone }) {
  const opts = (ret.items || []).map((it) => ({ value: it.product_id, label: it.product_name || it.product_id }));
  const [f, setF] = useState({ product_id: opts[0]?.value || "", defect_yard: "", roll_id: "", note: "", defect_from: "", defect_to: "", treatment: "" });
  const [err, setErr] = useState("");
  const submit = async () => {
    setErr("");
    const pos = f.defect_from !== "" && f.defect_to !== "" ? { defect_from: Number(f.defect_from), defect_to: Number(f.defect_to) } : { defect_from: null, defect_to: null };
    try { await axios.post(`${API}/sales-returns/${ret.id}/cutloss`, { ...f, ...pos, defect_yard: Number(f.defect_yard) || 0 }); setF({ ...f, defect_yard: "", note: "", defect_from: "", defect_to: "" }); onDone(); }
    catch (e) { setErr(errText(e)); }
  };
  return (
    <div className="flex flex-wrap items-end gap-2 text-xs" data-testid="cutloss-record-form">
      <div className="w-56"><KNSelect data-testid="cutloss-product" value={f.product_id} options={opts} searchable={false} onValueChange={(v) => setF({ ...f, product_id: v })} /></div>
      <label className="flex flex-col gap-1">Qty cacat (yard)
        <input data-testid="cutloss-defect-yard" type="number" min={0} step="0.01" className="field w-28" value={f.defect_yard} onChange={(e) => setF({ ...f, defect_yard: e.target.value })} /></label>
      <label className="flex flex-col gap-1">Posisi cacat yard awal–akhir (opsional)
        <span className="flex gap-1"><input data-testid="cutloss-defect-from" type="number" min={0} className="field w-20" placeholder="dari" value={f.defect_from} onChange={(e) => setF({ ...f, defect_from: e.target.value })} />
        <input data-testid="cutloss-defect-to" type="number" min={0} className="field w-20" placeholder="sampai" value={f.defect_to} onChange={(e) => setF({ ...f, defect_to: e.target.value })} /></span></label>
      <fieldset className="flex flex-col gap-1" data-testid="cutloss-treatment">Potongan cacat
        <span className="flex gap-2">{[["bs", "Masuk stok BS"], ["dispose", "Dibuang"]].map(([v, l]) => (
          <label key={v} className="flex items-center gap-1"><input type="radio" name="cutloss-treatment" data-testid={`cutloss-treatment-${v}`} checked={f.treatment === v} onChange={() => setF({ ...f, treatment: v })} />{l}</label>))}</span></fieldset>
      <label className="flex flex-col gap-1">No. roll (opsional)
        <input data-testid="cutloss-roll" className="field w-32" value={f.roll_id} onChange={(e) => setF({ ...f, roll_id: e.target.value })} /></label>
      <input data-testid="cutloss-note" className="field w-48" placeholder="Catatan QC" value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} />
      <button type="button" data-testid="cutloss-record-submit" onClick={submit} className="primary-button text-xs">Catat qty cacat</button>
      {err && <p className="w-full text-[#C62828]" data-testid="cutloss-record-error">{err}</p>}
    </div>
  );
}

function DecideForm({ ret, pv, onDone }) {
  const photos = (ret.attachments || []).filter((a) => !a.is_deleted && /^(image|video)\//.test(a.content_type || ""));
  const [disc, setDisc] = useState({});
  const [ev, setEv] = useState([]);
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");
  const cutPids = [...new Set(pv.cutloss.map((c) => c.product_id))];
  const submit = async () => {
    setErr("");
    const lines = [...cutPids.map((pid) => ({ kind: "cutloss", product_id: pid })),
      ...Object.entries(disc).filter(([, v]) => Number(v.qty) > 0 || Number(v.amount) > 0)
        .map(([pid, v]) => ({ kind: "discount", product_id: pid, qty: Number(v.qty), amount: Number(v.amount), evidence_ids: ev }))];
    try { await axios.post(`${API}/sales-returns/${ret.id}/compensation`, { lines, note }); onDone(); }
    catch (e) { setErr(errText(e)); }
  };
  return (
    <div className="space-y-2 text-xs" data-testid="compensation-decide-form">
      {(ret.items || []).map((it) => (
        <div key={it.product_id} className="flex flex-wrap items-end gap-2">
          <span className="w-48 font-semibold">{it.product_name || it.product_id}</span>
          <label className="flex flex-col gap-1">Qty cacat diskon ({it.unit})
            <input data-testid={`discount-qty-${it.product_id}`} type="number" className="field w-24" value={disc[it.product_id]?.qty || ""}
                   onChange={(e) => setDisc({ ...disc, [it.product_id]: { ...disc[it.product_id], qty: e.target.value } })} /></label>
          <label className="flex flex-col gap-1">Nominal diskon (Rp)
            <input data-testid={`discount-amount-${it.product_id}`} type="number" className="field w-32" value={disc[it.product_id]?.amount || ""}
                   onChange={(e) => setDisc({ ...disc, [it.product_id]: { ...disc[it.product_id], amount: e.target.value } })} /></label>
        </div>
      ))}
      {photos.length > 0 && (
        <div className="flex flex-wrap gap-3"><span className="font-semibold">Bukti foto/video:</span>
          {photos.map((a) => (
            <label key={a.id} className="inline-flex items-center gap-1">
              <input type="checkbox" data-testid={`compensation-evidence-${a.id}`} checked={ev.includes(a.id)}
                     onChange={() => setEv(ev.includes(a.id) ? ev.filter((i) => i !== a.id) : [...ev, a.id])} /> {a.filename}
            </label>))}
        </div>
      )}
      <input data-testid="compensation-note" className="field w-full" placeholder="Catatan keputusan Finance (wajib)" value={note} onChange={(e) => setNote(e.target.value)} />
      <button type="button" data-testid="compensation-decide-submit" onClick={submit} className="primary-button text-xs">Putuskan nilai</button>
      {err && <p className="text-[#C62828]" data-testid="compensation-decide-error">{err}</p>}
    </div>
  );
}

// LN-092 — cutloss (qty cacat dari QC) & diskon nominal; nilai diputus Finance, selesai sebagai Nego.
export default function ReturnCompensationPanel({ ret, canApprove, onChanged }) {
  const [pv, setPv] = useState(null);
  const [msg, setMsg] = useState("");
  const [payout, setPayout] = useState("store_credit");
  const load = useCallback(() => axios.get(`${API}/sales-returns/${ret.id}/compensation`).then((r) => setPv(r.data)).catch(() => setPv(null)), [ret.id]);
  useEffect(() => { load(); }, [load, ret.updated_at]);
  if (!pv) return null;
  const terminal = TERMINAL.includes(ret.status);
  const comp = pv.compensation || {};
  const decided = comp.status === "decided";
  const refresh = () => { load(); onChanged?.(); };
  const photoOnly = decided && comp.lines.every((x) => x.kind === "discount" && x.evidence_ids?.length) && ret.status === "approved";
  const settle = async () => {
    setMsg("");
    try { await axios.post(`${API}/sales-returns/${ret.id}/settle`, { outcome: "nego", decision_note: comp.note, payout }); refresh(); }
    catch (e) { setMsg(errText(e)); }
  };
  const revoke = async () => { setMsg(""); try { await axios.delete(`${API}/sales-returns/${ret.id}/compensation`); refresh(); } catch (e) { setMsg(errText(e)); } };
  return (
    <div className="mb-3 rounded-lg border border-[#EDEEF1] bg-white px-3 py-2.5 space-y-2" data-testid="return-compensation-panel">
      <div className="flex items-center gap-2 text-sm font-semibold"><Scissors size={14} className="text-[#8A4B08]" /> Cutloss & diskon
        <span className="text-xs font-normal text-[#6B6B73]">{pv.basis}</span></div>
      {pv.cutloss.length > 0 && (
        <table className="min-w-full text-xs" data-testid="cutloss-table">
          <thead className="text-left text-[#6B6B73]"><tr>{["Produk", "Roll", "Cacat (yd)", "Qty kompensasi", "Harga neto", "Nilai", "Dicatat", "Potongan roll"].map((h) => <th key={h} className="py-1 pr-3">{h}</th>)}</tr></thead>
          <tbody>{pv.cutloss.map((c) => (
            <tr key={c.id} data-testid={`cutloss-row-${c.id}`}>
              <td className="pr-3">{c.product_name}</td><td className="pr-3">{c.roll_id || "—"}</td><td className="pr-3">{c.defect_yard}</td>
              <td className="pr-3">{c.qty} {c.unit_base}{c.converted ? " (konversi otomatis)" : ""}</td>
              <td className="pr-3">{rp(c.unit_price)}</td><td className="pr-3 font-semibold">{rp(c.amount)}</td><td>{c.recorded_by}</td>
              <td className="pl-2"><CutlossSplitPanel ret={ret} c={c} onDone={refresh} /></td>
            </tr>))}</tbody>
        </table>
      )}
      {!terminal && !decided && canCurrent("sales_return", "record_cutloss") && <CutlossForm ret={ret} onDone={refresh} />}
      {decided ? (
        <div className="rounded-md bg-[#F4FAF6] p-2 text-xs space-y-1" data-testid="compensation-decided">
          <p className="flex items-center gap-1 font-semibold"><BadgePercent size={12} /> Diputus Finance: {rp(comp.total)} · {comp.decided_by}</p>
          {comp.lines.map((x, i) => <p key={i}>{x.kind === "cutloss" ? "Cutloss" : "Diskon"} · {x.product_name} · {x.qty} {x.unit} · {rp(x.amount)}</p>)}
          <p className="text-[#6B6B73]">{comp.note}</p>
          {!terminal && (
            <div className="flex flex-wrap gap-2">
              {photoOnly && canApprove && (
                <select data-testid="compensation-payout" className="field text-xs" value={payout} onChange={(e) => setPayout(e.target.value)}>
                  <option value="store_credit">Jadi saldo</option><option value="refund">Refund tunai</option><option value="">Kurangi piutang SO asal</option>
                </select>)}
              {photoOnly && canApprove && <button type="button" data-testid="compensation-settle-photo" onClick={settle} className="primary-button text-xs">Selesaikan diskon (tanpa barang kembali)</button>}
              {canCurrent("sales_return", "decide_compensation") && <button type="button" data-testid="compensation-revoke" onClick={revoke} className="secondary-button text-xs"><Trash2 size={12} /> Batalkan keputusan</button>}
            </div>
          )}
          {!terminal && !photoOnly && <p className="text-[#6B6B73]">Selesaikan lewat tombol "Selesaikan" → outcome Nego setelah QC.</p>}
        </div>
      ) : (!terminal && canCurrent("sales_return", "decide_compensation") && <DecideForm ret={ret} pv={pv} onDone={refresh} />)}
      {msg && <p className="text-xs text-[#C62828]" data-testid="compensation-msg">{msg}</p>}
    </div>
  );
}
