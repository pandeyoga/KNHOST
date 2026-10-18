import { useState } from "react";
import { Check, Pencil, X } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { formatQty } from "../../../utils/formatters";

/** L01 — ubah toleransi susut kontrak (mitra × proses) langsung dari daftar kontrak. */
export default function ContractToleranceInline({ contract, canEdit, onSaved, onError }) {
  const [edit, setEdit] = useState(false);
  const [val, setVal] = useState("");
  const [busy, setBusy] = useState(false);
  const shown = contract.tolerance_pct == null ? "kebijakan" : `${formatQty(contract.tolerance_pct)}%`;
  const save = async () => {
    const empty = String(val).trim() === "";
    const n = parseFloat(String(val).replace(",", "."));
    if (!empty && (Number.isNaN(n) || n < 0 || n > 100)) { onError?.("Toleransi harus 0–100% (kosongkan = ikut kebijakan global)."); return; }
    setBusy(true);
    try {
      await axios.patch(`${API}/supplier-contracts/${contract.id}`, empty ? { reset_tolerance: true } : { tolerance_pct: n });
      setEdit(false);
      await onSaved?.();
    } catch (e) { onError?.(e.response?.data?.detail || "Gagal menyimpan toleransi."); }
    finally { setBusy(false); }
  };
  if (!edit) {
    return (
      <span className="inline-flex items-center gap-1 text-[11.5px] tabular-nums" data-testid={`contract-tol-${contract.id}`}>
        {formatQty(contract.shrinkage_pct || 0)}% / {shown}
        {canEdit && (
          <button type="button" className="icon-button text-[#0058CC]" title="Ubah toleransi susut"
            data-testid={`contract-tol-edit-${contract.id}`}
            onClick={(e) => { e.stopPropagation(); setVal(contract.tolerance_pct ?? ""); setEdit(true); }}><Pencil size={11} /></button>
        )}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
      <input className="field !w-16 !py-0.5 text-[11px]" autoFocus value={val} inputMode="decimal" placeholder="global"
        data-testid={`contract-tol-input-${contract.id}`} onChange={(e) => setVal(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") setEdit(false); }} />
      <span className="text-[11px]">%</span>
      <button type="button" disabled={busy} className="icon-button text-[#1F7A3A]" data-testid={`contract-tol-save-${contract.id}`} onClick={save}><Check size={12} /></button>
      <button type="button" className="icon-button" data-testid={`contract-tol-cancel-${contract.id}`} onClick={() => setEdit(false)}><X size={12} /></button>
    </span>
  );
}
