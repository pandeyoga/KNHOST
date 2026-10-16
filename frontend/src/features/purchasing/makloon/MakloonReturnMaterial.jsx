import { useState } from "react";
import { Undo2 } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { formatCurrency, formatQty } from "../../../utils/formatters";

/** P05 DEC-13 + L00 — order batal: bahan tetap di mitra sampai retur (seluruh/sebagian roll) dicatat. */
export function MakloonReturnHistory({ step }) {
  const returns = step.material_returns || [];
  if (!returns.length) return null;
  return (
    <ul className="mt-1 text-[11px] text-[#3C3C43]" data-testid={`mko-return-history-${step.seq}`}>
      {returns.map((r, i) => <li key={i}>Retur {i + 1}: {formatQty(r.qty)} {step.input_unit} · {r.rolls} roll · {formatCurrency(r.value)} — {r.reason}</li>)}
    </ul>
  );
}

export default function MakloonReturnMaterial({ mkoId, step, canAct, canLoss, canTol, onDone, onError }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [rolls, setRolls] = useState([]);
  const [picked, setPicked] = useState({});
  const [tol, setTol] = useState(null);
  const [ctol, setCtol] = useState(null);
  const [tolEdit, setTolEdit] = useState("");
  const returns = step.material_returns || [];
  const valueLeft = Number(step.material_value || 0) - returns.reduce((a, r) => a + Number(r.value || 0), 0);

  async function openForm() {
    setOpen(true);
    try {
      const { data } = await axios.get(`${API}/makloon-orders/${mkoId}/steps/${step.seq}/partner-rolls`);
      setRolls(data.rolls || []);
      setTol(data.tolerance_pct ?? null);
      setCtol(data.contract_tolerance_pct ?? null);
      setTolEdit((cur) => (cur === "" ? String(data.tolerance_pct ?? "") : cur));
      setPicked(Object.fromEntries((data.rolls || []).map((r) => [r.id, true])));
    } catch (e) { onError?.(e.response?.data?.detail || "Gagal memuat roll di mitra."); }
  }

  const ids = Object.keys(picked).filter((k) => picked[k]);
  const qty = rolls.filter((r) => picked[r.id]).reduce((a, r) => a + Number(r.length_remaining || 0), 0);

  async function saveTol(value) {
    setBusy(true);
    try {
      const n = parseFloat(String(value).replace(",", "."));
      if (Number.isNaN(n) || n < 0 || n > 100) { onError?.("Toleransi harus angka 0–100%."); return; }
      await axios.post(`${API}/makloon-orders/${mkoId}/steps/${step.seq}/tolerance`, { tolerance_pct: n, reason: reason.trim() || "Penyesuaian toleransi susut" });
      setTol(n);
      await onDone?.();
    } catch (e) { onError?.(e.response?.data?.detail || "Gagal mengubah toleransi."); }
    finally { setBusy(false); }
  }

  async function submit(kind = "return") {
    setBusy(true);
    try {
      await axios.post(`${API}/makloon-orders/${mkoId}/steps/${step.seq}/${kind === "loss" ? "material-loss" : "return-material"}`, { reason: reason.trim(), roll_ids: ids });
      setOpen(false); setReason(""); await onDone?.();
    } catch (e) { onError?.(e.response?.data?.detail || (kind === "loss" ? "Gagal mencatat susut." : "Gagal mencatat retur bahan.")); }
    finally { setBusy(false); }
  }

  return (
    <div className="mt-2 rounded-lg border border-[#F5D9A8] bg-[#FFF8EC] p-2.5 text-[11px]" data-testid={`mko-await-return-${step.seq}`}>
      <p className="text-[#8A5A00]">
        Order dibatalkan, tetapi bahan <b>{formatQty(step.subcon_qty)} {step.input_unit}</b> ({formatCurrency(valueLeft)}) masih di
        {" "}{step.makloon_name || "mitra"}. WIP tetap tercatat sampai retur bahan dicatat.
      </p>
      <MakloonReturnHistory step={step} />
      {(canAct || canLoss) && !open && (
        <button data-testid={`mko-return-open-${step.seq}`} onClick={openForm} className="secondary-button mt-2 !py-1.5 text-[11.5px]">
          <Undo2 size={12} /> Catat Retur / Susut Bahan
        </button>
      )}
      {(canAct || canLoss) && open && (
        <div className="mt-2 space-y-2">
          <div className="max-h-40 overflow-auto rounded border border-[#F0E0C0] bg-white p-1.5" data-testid={`mko-return-rolls-${step.seq}`}>
            {rolls.map((r) => (
              <label key={r.id} className="flex items-center gap-2 py-0.5">
                <input type="checkbox" checked={!!picked[r.id]} data-testid={`mko-return-roll-${r.id}`}
                  onChange={(e) => setPicked({ ...picked, [r.id]: e.target.checked })} />
                <span>{r.roll_no || r.id}{r.lot ? ` · LOT ${r.lot}` : ""} — {formatQty(r.length_remaining)} {r.unit || step.input_unit}</span>
              </label>
            ))}
            {!rolls.length && <p className="text-[#6B6B73]">Memuat roll…</p>}
          </div>
          <p data-testid={`mko-return-summary-${step.seq}`}>Dipilih {ids.length}/{rolls.length} roll · {formatQty(qty)} {step.input_unit}. Roll yang tidak dipilih tetap tercatat di mitra.</p>
          {canLoss && <p className="text-[#6B6B73]" data-testid={`mko-loss-tolerance-${step.seq}`}>Toleransi susut wajar (kontrak mitra × proses): <b>{tol ?? "—"}%</b> dari bahan dikirim → dibebankan perusahaan. Kelebihannya butuh persetujuan lalu diklaim ke mitra.</p>}
          {canLoss && canTol && (
            <div className="flex flex-wrap items-center gap-1.5" data-testid={`mko-tol-editor-${step.seq}`}>
              <span>Ubah toleransi langkah ini:</span>
              <input className="field !w-16 !py-0.5 text-[11px]" inputMode="decimal" value={tolEdit} data-testid={`mko-tol-input-${step.seq}`} onChange={(e) => setTolEdit(e.target.value)} />
              <span>%</span>
              <button type="button" disabled={busy || tolEdit === String(tol)} className="secondary-button !py-0.5 text-[11px]" data-testid={`mko-tol-save-${step.seq}`} onClick={() => saveTol(tolEdit)}>Simpan</button>
              {ctol != null && ctol !== tol && (
                <button type="button" disabled={busy} className="secondary-button !py-0.5 text-[11px]" data-testid={`mko-tol-contract-${step.seq}`} onClick={() => { setTolEdit(String(ctol)); saveTol(ctol); }}>Pakai kontrak sekarang ({ctol}%)</button>
              )}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <input data-testid={`mko-return-reason-${step.seq}`} className="field !py-1.5 text-[11.5px] min-w-[220px] flex-1"
              placeholder="Keterangan retur (mis. no. SJ retur mitra)" value={reason} onChange={(e) => setReason(e.target.value)} />
            {canAct && <button data-testid={`mko-return-submit-${step.seq}`} disabled={busy || reason.trim().length < 5 || !ids.length} onClick={() => submit("return")}
              className="primary-button !py-1.5 text-[11.5px]">{busy ? "Menyimpan…" : "Simpan Retur"}</button>}
            {canLoss && <button data-testid={`mko-loss-submit-${step.seq}`} disabled={busy || reason.trim().length < 5 || !ids.length} onClick={() => submit("loss")}
              className="secondary-button !py-1.5 text-[11.5px] !text-[#A8221A]">Catat Susut / Hilang</button>}
            <button data-testid={`mko-return-cancel-${step.seq}`} onClick={() => setOpen(false)} className="secondary-button !py-1.5 text-[11.5px]">Batal</button>
          </div>
        </div>
      )}
    </div>
  );
}
