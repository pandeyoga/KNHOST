/** UAT 23 Okt — riwayat PENYELESAIAN PER ROLL: tiap penyelesaian (P1, P2, …) dengan Nota Kredit, outcome & qty per roll,
 *  pembagian dana. Penyelesaian yang terhenti → [Lengkapi]; roll Diskon/Tolak klaim yang sempat diterima gudang →
 *  [Buat SJ kirim balik]. */
import { useState } from "react";
import axios, { API } from "../../services/apiClient";
import { Layers, Truck, RefreshCw } from "lucide-react";
import { Panel } from "../../components/DetailParts";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { apiErrorText } from "../../utils/apiError";
import { fmtDateTime } from "./ReturnShared";

export default function ReturnRollSettlementsPanel({ ret, canApprove, canShip, onChanged }) {
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const events = ret.settlements || [];
  if (!events.length) return null;
  const rollNo = Object.fromEntries(events.flatMap((e) => (e.plan?.rolls || []).map((r) => [r.roll_id, r])));
  const back = Object.entries(ret.roll_outcomes || {}).filter(([, o]) => o.back_pending).map(([id]) => id);
  const run = async (key, fn) => {
    setBusy(key); setMsg("");
    try { await fn(); if (onChanged) await onChanged(); } catch (e) { setMsg(apiErrorText(e, "Gagal.")); } finally { setBusy(""); }
  };
  return (
    <Panel icon={Layers} title={`Penyelesaian per roll · ${events.length}`} testId="return-roll-settlements">
      <div className="space-y-2.5 text-[12px]">
        {events.map((e) => (
          <div key={e.id} className="rounded-lg border border-[#E4ECF7] p-2.5" data-testid={`roll-settlement-${e.seq}`}>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="font-semibold">P{e.seq} · {e.status === "done" ? (e.credit_note_number || "tanpa Nota Kredit") : "Belum tuntas"}</span>
              <span className="text-[11px] text-[#6B6B73]">{fmtDateTime(e.at)} · {e.by}{e.decision_note ? ` · ${e.decision_note}` : ""}</span>
            </div>
            <ul className="mt-1 space-y-0.5">
              {(e.plan?.rolls || []).map((r) => (
                <li key={r.roll_id} className="flex flex-wrap justify-between gap-2">
                  <span><b className="font-mono">{r.roll_no}</b> · {r.outcome_label}
                    {r.qty_stock ? ` · ke stok ${formatQty(r.qty_stock)} ${r.unit}` : ""}
                    {r.qty_cut ? ` · dipotong ${formatQty(r.qty_cut)} ${r.unit}` : ""}
                    {r.qty_back ? ` · kembali ke pelanggan ${formatQty(r.qty_back)} ${r.unit}` : ""}</span>
                  <span className="tabular-nums">{formatCurrency(r.credit_amount)}</span>
                </li>))}
            </ul>
            {(e.plan?.split || []).length > 0 && (
              <p className="mt-1 text-[11px] text-[#3F4652]">
                Nota Kredit {formatCurrency(e.plan.gross_amount)} → {e.plan.split.map((x) => `${x.label} ${formatCurrency(x.amount)}`).join(" · ")}
              </p>
            )}
            {e.status !== "done" && canApprove && (
              <button type="button" className="secondary-button mt-1.5 text-xs" data-testid={`roll-settlement-complete-${e.seq}`} disabled={!!busy}
                onClick={() => run(e.id, () => axios.post(`${API}/sales-returns/${ret.id}/roll-settlement/${e.id}/complete`))}>
                <RefreshCw size={12} /> Lengkapi penyelesaian P{e.seq}
              </button>
            )}
          </div>
        ))}
        {back.length > 0 && (
          <div className="rounded-lg border border-[#F5D9A8] bg-[#FFF8EC] p-2.5" data-testid="roll-settlement-back">
            <p>Roll menunggu dikirim balik ke pelanggan: {back.map((id) => `${rollNo[id]?.roll_no || id} (${rollNo[id]?.outcome_label || ""})`).join(", ")}</p>
            {canShip && (
              <button type="button" className="primary-button mt-1.5 text-xs" data-testid="roll-settlement-back-btn" disabled={!!busy}
                onClick={() => run("back", () => axios.post(`${API}/sales-returns/${ret.id}/roll-settlement/back-shipment`, { roll_ids: back }))}>
                <Truck size={12} /> Buat SJ kirim balik
              </button>
            )}
          </div>
        )}
        {msg && <p className="text-[#A8221A]" data-testid="roll-settlement-error">{msg}</p>}
      </div>
    </Panel>
  );
}
