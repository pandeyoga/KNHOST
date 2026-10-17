import { useState } from "react";
import { changeCatalogueSoft } from "./sampleApi";
import { apiErrorText } from "../../utils/apiError";

/** L06 LN-060 — komponen catalogue: dasar 1 yd per warna (tetap) + soft 2 yd (bisa diganti sebelum ke gudang). */
export default function CatalogueComponents({ order, canEdit, onChanged }) {
  const cat = order.catalogue;
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  if (!cat) return null;
  const editable = canEdit && ["waiting_approval", "approved"].includes(order.status);
  const change = async (pid) => {
    setBusy(true); setErr("");
    try { await changeCatalogueSoft(order.id, pid); onChanged?.(); } catch (e) { setErr(apiErrorText(e, "Gagal mengganti warna soft.")); } finally { setBusy(false); }
  };
  return (
    <div data-testid="catalogue-components" className="rounded-md border border-[#F3D9A4] bg-[#FFF9EC] p-2.5 text-[11.5px]">
      <p className="text-[10px] font-bold uppercase tracking-wide text-[#9A5B00]">Catalogue · {cat.base.length} warna × 1 yd + soft 2 yd = {cat.total_qty} yd</p>
      <p className="mt-1">Dasar: {cat.base.map((c) => c.color || c.product_name).join(", ")}</p>
      <div className="mt-1 flex items-center gap-2">
        <span>Soft:</span>
        {editable ? (
          <select data-testid="catalogue-soft-select" className="field !h-7 !w-auto text-[11px]" disabled={busy} value={cat.soft?.product_id || ""} onChange={(e) => change(e.target.value)}>
            {cat.base.map((c) => <option key={c.product_id} value={c.product_id}>{c.color || c.product_name}</option>)}
          </select>
        ) : <b data-testid="catalogue-soft-label">{cat.soft?.color || "—"}</b>}
      </div>
      {err && <p className="mt-1 text-[#B23B14]">{err}</p>}
    </div>
  );
}
