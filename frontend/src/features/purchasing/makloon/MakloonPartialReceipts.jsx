/** Riwayat kiriman makloon bertahap per langkah: ditahan → digabung / dibatalkan (dengan alasan). */
import { useState } from "react";
import { Layers, Undo2 } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { formatQty } from "../../../utils/formatters";

const fmtDT = (v) => (v ? new Date(v).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" }) : "—");

function CancelPartial({ mkoId, seq, row, onChanged }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const key = row.grn_number || row.grn_id;
  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await axios.post(`${API}/makloon-orders/${mkoId}/steps/${seq}/partial-receipts/${row.grn_id}/cancel`, { reason });
      setOpen(false); setReason("");
      onChanged && onChanged();
    } catch (e) {
      setErr(e?.response?.data?.detail || "Gagal membatalkan.");
    } finally { setBusy(false); }
  };
  if (!open) {
    return (
      <button type="button" data-testid={`mko-partial-cancel-btn-${seq}-${key}`} onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 rounded border border-[#E5C4C4] px-1.5 text-[#B42318] hover:bg-[#FDECEC]">
        <Undo2 size={10} /> Batalkan
      </button>
    );
  }
  return (
    <div className="mt-1 flex w-full flex-wrap items-center gap-1.5" data-testid={`mko-partial-cancel-form-${seq}-${key}`}>
      <input data-testid={`mko-partial-cancel-reason-${seq}-${key}`} value={reason} onChange={(e) => setReason(e.target.value)}
        placeholder="Alasan pembatalan (wajib, min. 5 huruf)" className="field-input min-w-[220px] flex-1 !py-1 !text-[11px]" />
      <button type="button" data-testid={`mko-partial-cancel-confirm-${seq}-${key}`} disabled={busy || reason.trim().length < 5}
        onClick={submit} className="rounded bg-[#B42318] px-2 py-1 text-[10.5px] font-semibold text-white disabled:opacity-50">
        {busy ? "Membatalkan…" : "Batalkan kiriman"}
      </button>
      <button type="button" onClick={() => { setOpen(false); setErr(""); }} className="text-[10.5px] text-[#6E6E73]">Tutup</button>
      {err && <span data-testid={`mko-partial-cancel-error-${seq}-${key}`} className="w-full text-[#B42318]">{err}</span>}
    </div>
  );
}

export default function MakloonPartialReceipts({ step, mkoId, onChanged }) {
  const rows = step.partial_receipts || [];
  const gone = step.cancelled_partials || [];
  if (!rows.length && !gone.length) return null;
  const abs = step.partial_absorption;
  const unit = step.output_unit || "";
  const held = rows.filter((r) => !r.posted);
  return (
    <div data-testid={`mko-step-partials-${step.seq}`} className="mt-2 rounded-lg border border-[#DCE7F7] bg-[#F5F9FF] p-2.5 text-[10.5px]">
      <p className="flex items-center gap-1.5 font-semibold text-[#0058CC]">
        <Layers size={12} /> Kiriman bertahap ({rows.length})
        {held.length > 0 && <span className="rounded bg-[#FFF1DB] px-1.5 text-[#B26A00]" data-testid={`mko-step-partials-held-${step.seq}`}>
          {held.length} ditahan · {formatQty(held.reduce((s, r) => s + (r.out_qty || 0), 0))} {unit}</span>}
      </p>
      <ul className="mt-1.5 space-y-1">
        {rows.map((r) => (
          <li key={r.grn_id} data-testid={`mko-step-partial-${step.seq}-${r.grn_number || r.grn_id}`} className="flex flex-wrap items-center gap-x-2 text-[#3C3C43]">
            <b>{r.grn_number || r.grn_id}</b>
            {r.dn_number && <span>SJ {r.dn_number}</span>}
            <span className="tabular-nums">{formatQty(r.out_qty)} {unit} · {(r.rolls || []).length} roll</span>
            <span className="text-[#9A9BA3]">{r.by} · {fmtDT(r.at)}</span>
            {r.posted
              ? <span className="rounded bg-[#E6F4EA] px-1.5 font-semibold text-[#1B7F4B]">Digabung ke {r.absorbed_by || "penerimaan akhir"}</span>
              : <>
                  <span className="rounded bg-[#FFF1DB] px-1.5 font-semibold text-[#B26A00]">Ditahan — menunggu kiriman terakhir</span>
                  {step.status === "issued" && <CancelPartial mkoId={mkoId} seq={step.seq} row={r} onChanged={onChanged} />}
                </>}
          </li>
        ))}
        {gone.map((r) => (
          <li key={`x-${r.grn_id}-${r.cancelled_at}`} data-testid={`mko-step-partial-cancelled-${step.seq}-${r.grn_number || r.grn_id}`}
            className="flex flex-wrap items-center gap-x-2 text-[#9A9BA3]">
            <b className="line-through">{r.grn_number || r.grn_id}</b>
            <span className="line-through tabular-nums">{formatQty(r.out_qty)} {unit}</span>
            <span className="rounded bg-[#FDECEC] px-1.5 font-semibold text-[#B42318]">Dibatalkan</span>
            <span className="text-[#3C3C43]">“{r.cancel_reason}” — {r.cancelled_by} · {fmtDT(r.cancelled_at)}</span>
          </li>
        ))}
      </ul>
      {abs && (
        <p data-testid={`mko-step-partial-absorption-${step.seq}`} className="mt-1.5 border-t border-[#DCE7F7] pt-1.5 text-[#3C3C43]">
          Penerimaan akhir <b>{abs.final_ref}</b>{abs.final_dn ? ` (SJ ${abs.final_dn})` : ""} menyerap {abs.count} kiriman sebagian:
          {" "}{formatQty(abs.partial_qty)} + {formatQty(abs.final_qty)} = <b>{formatQty(abs.total_qty)} {unit}</b> — satu tagihan jasa & satu posting stok · {fmtDT(abs.at)}
        </p>
      )}
    </div>
  );
}
