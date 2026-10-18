/** RollHoldControl — QC-06: tombol Tahan / Lepas Tahan satu roll + dialog alasan. */
import { useState } from "react";
import { PauseCircle, PlayCircle, X } from "lucide-react";
import axios, { API } from "../../../services/apiClient";

const HOLDABLE = ["available", "quarantine"];

export function RollHoldControl({ roll, onChanged, size = "sm" }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const held = roll.status === "blocked" && roll.hold?.held;
  const inspHeld = !!roll.inspection?.hold?.held;
  const mode = held || inspHeld ? "release" : HOLDABLE.includes(roll.status) ? "hold" : null;
  if (!mode) return null;

  async function submit() {
    setBusy(true); setError("");
    try {
      const body = mode === "hold" ? { reason: text } : { note: text };
      await axios.post(`${API}/inventory/rolls/${roll.id}/${mode}`, body);
      setOpen(false); setText("");
      onChanged?.();
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally { setBusy(false); }
  }

  const isHold = mode === "hold";
  const btnCls = isHold
    ? "border-[#F5D9A8] text-[#9A5B00] hover:bg-[#FFF8EC]"
    : "border-[#BFE6CF] text-[#1B7F4B] hover:bg-[#EEFAF3]";
  return (
    <>
      <button data-testid={`roll-${mode}-btn-${roll.id}`} onClick={() => setOpen(true)}
        className={`mr-1.5 inline-flex items-center gap-1 rounded-md border bg-white px-2 py-1 font-semibold ${size === "sm" ? "text-[10.5px]" : "text-[11px]"} ${btnCls}`}>
        {isHold ? <PauseCircle size={10} /> : <PlayCircle size={10} />} {isHold ? "Tahan" : "Lepas Tahan"}
      </button>
      {open && (
        <div className="fixed inset-0 z-[130] flex items-center justify-center bg-black/40 p-4" data-testid="roll-hold-dialog"
          onClick={() => !busy && setOpen(false)}>
          <div className="w-full max-w-md rounded-xl bg-white p-4 text-left shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-2 flex items-center justify-between">
              <p className="text-[13px] font-bold">{isHold ? "Tahan roll" : "Lepas tahanan roll"} {roll.roll_no}</p>
              <button data-testid="roll-hold-dialog-close" className="icon-button" onClick={() => setOpen(false)}><X size={15} /></button>
            </div>
            <p className="mb-2 text-[11.5px] text-[#6B6B73]" data-testid="roll-hold-dialog-info">
              {isHold
                ? "Roll akan berstatus Diblokir: tidak tersedia untuk dijual/dialokasikan dan keputusan QC tertahan sampai dilepas."
                : `Alasan ditahan: ${roll.hold?.reason || roll.inspection?.hold?.reason || "—"}. Roll kembali ke status ${roll.hold?.prev_status || roll.status}.`}
            </p>
            <textarea data-testid="roll-hold-reason-input" className="field w-full text-[12px]" rows={3}
              placeholder={isHold ? "Alasan menahan (wajib)" : "Catatan pelepasan (wajib)"}
              value={text} onChange={(e) => setText(e.target.value)} />
            {error && <p className="mt-1.5 rounded bg-[#FBE9E7] px-2 py-1 text-[11px] text-[#C0341D]" data-testid="roll-hold-error">{error}</p>}
            <div className="mt-3 flex justify-end gap-2">
              <button className="secondary-button text-[11.5px]" onClick={() => setOpen(false)} disabled={busy}>Batal</button>
              <button data-testid={`roll-${mode}-submit`} className="primary-button text-[11.5px]" disabled={busy || text.trim().length < 3}
                onClick={submit}>{busy ? "…" : isHold ? "Tahan roll" : "Lepas tahanan"}</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default RollHoldControl;
