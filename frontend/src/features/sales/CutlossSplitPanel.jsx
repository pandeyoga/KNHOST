import { useState } from "react";
import { Scissors, Truck } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { canCurrent } from "../../config/roles";

const TREAT = { bs: "Masuk stok BS", dispose: "Dibuang" };
const errText = (e) => e.response?.data?.detail?.message || e.response?.data?.detail || e.message;

// CUT-01/04/05 — pratinjau & proses pecah roll cutloss setelah QC, lalu SJ potongan baik.
export default function CutlossSplitPanel({ ret, c, onDone }) {
  const [pv, setPv] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const split = c.split || {};
  const can = canCurrent("sales_return", "split_cutloss");
  const call = async (fn) => { setBusy(true); setErr(""); try { await fn(); } catch (e) { setErr(errText(e)); } finally { setBusy(false); } };
  const preview = () => call(async () => setPv((await axios.get(`${API}/sales-returns/${ret.id}/cutloss/${c.id}/split-preview`)).data));
  const run = () => call(async () => { await axios.post(`${API}/sales-returns/${ret.id}/cutloss/${c.id}/split`); setPv(null); onDone(); });
  const sj = () => call(async () => { await axios.post(`${API}/sales-returns/${ret.id}/cutloss/${c.id}/return-shipment`); onDone(); });
  return (
    <div className="text-[11px] space-y-1" data-testid={`cutloss-split-${c.id}`}>
      {c.treatment && <span className="rounded bg-[#FFF4E5] px-1.5 py-0.5 font-semibold text-[#8A4B08]" data-testid={`cutloss-treatment-badge-${c.id}`}>{TREAT[c.treatment]}</span>}
      {split.status === "done" ? (
        <div data-testid={`cutloss-split-done-${c.id}`}>
          <p className="font-semibold">Dipecah: {split.summary}</p>
          <p className="text-[#6B6B73]">{split.pieces.map((p) => p.roll_no).join(", ")}</p>
          {split.shipment_no ? <p data-testid={`cutloss-sj-${c.id}`} className="text-[#1A7F37] font-semibold">SJ {split.shipment_no}</p>
            : can && split.pieces.some((p) => p.kind === "good") && <button type="button" disabled={busy} className="secondary-button text-[11px]" data-testid={`cutloss-sj-button-${c.id}`} onClick={sj}><Truck size={11} /> Buat SJ potongan baik</button>}
        </div>
      ) : c.roll_id && can && (
        <div className="space-y-1">
          {!pv && <button type="button" disabled={busy} className="secondary-button text-[11px]" data-testid={`cutloss-preview-${c.id}`} onClick={preview}><Scissors size={11} /> Pratinjau potongan</button>}
          {pv && <div className="rounded border border-[#EDEEF1] p-1.5" data-testid={`cutloss-preview-box-${c.id}`}>
            <p className="font-semibold">{pv.roll_no}: {pv.summary}</p>
            <div className="flex gap-1 my-1">{pv.pieces.map((p, i) => (
              <span key={i} style={{ flexGrow: p.qty }} className={`h-2 rounded ${p.kind === "good" ? "bg-[#1A7F37]" : p.treatment === "bs" ? "bg-[#F5A524]" : "bg-[#E5484D]"}`} title={`${p.from}–${p.to}: ${p.label}`} />))}</div>
            <button type="button" disabled={busy} className="primary-button text-[11px]" data-testid={`cutloss-split-confirm-${c.id}`} onClick={run}>Proses potongan</button>
            <button type="button" className="secondary-button text-[11px] ml-1" onClick={() => setPv(null)} data-testid={`cutloss-split-cancel-${c.id}`}>Batal</button>
          </div>}
        </div>
      )}
      {err && <p className="text-[#C62828]" data-testid={`cutloss-split-error-${c.id}`}>{err}</p>}
    </div>
  );
}
