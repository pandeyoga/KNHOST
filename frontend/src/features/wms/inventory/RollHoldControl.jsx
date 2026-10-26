/** RollHoldControl — QC-06: tombol Tahan / Lepas Tahan satu roll + dialog alasan.
 *  Fase 4 · R3 (L-03) — dialog `fixed inset-0` buatan sendiri → FormModal (layar penuh di HP, Esc berlapis, galat di
 *  pop-up). Testid `roll-hold-dialog`, `roll-hold-dialog-close`, `roll-hold-reason-input`, `roll-{mode}-submit` tetap. */
import { useState } from "react";
import { PauseCircle, PlayCircle } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import FormModal from "../../../components/FormModal";

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
      <button type="button" data-testid={`roll-${mode}-btn-${roll.id}`} onClick={() => { setError(""); setOpen(true); }}
        className={`mr-1.5 inline-flex items-center gap-1 rounded-md border bg-white px-2 py-1 font-semibold ${size === "sm" ? "text-[10.5px]" : "text-[11px]"} ${btnCls}`}>
        {isHold ? <PauseCircle size={10} /> : <PlayCircle size={10} />} {isHold ? "Tahan" : "Lepas Tahan"}
      </button>
      <FormModal open={open} onClose={() => setOpen(false)} size="sm" busy={busy} error={error}
        icon={isHold ? PauseCircle : PlayCircle} testId="roll-hold-dialog"
        title={`${isHold ? "Tahan roll" : "Lepas tahanan roll"} ${roll.roll_no || ""}`.trim()}
        onSubmit={submit} submitDisabled={text.trim().length < 5} submitTestId={`roll-${mode}-submit`}
        submitLabel={busy ? "…" : isHold ? "Tahan roll" : "Lepas tahanan"}>
        <p className="mb-2 text-[11.5px] text-[#6B6B73]" data-testid="roll-hold-dialog-info">
          {isHold
            ? "Roll akan berstatus Diblokir: tidak tersedia untuk dijual/dialokasikan dan keputusan QC tertahan sampai dilepas."
            : `Alasan ditahan: ${roll.hold?.reason || roll.inspection?.hold?.reason || "—"}. Roll kembali ke status ${roll.hold?.prev_status || roll.status}.`}
        </p>
        <textarea data-testid="roll-hold-reason-input" className="field w-full text-[12px]" rows={3}
          placeholder={isHold ? "Alasan menahan (wajib)" : "Catatan pelepasan (wajib)"}
          value={text} onChange={(e) => setText(e.target.value)} />
      </FormModal>
    </>
  );
}

export default RollHoldControl;
