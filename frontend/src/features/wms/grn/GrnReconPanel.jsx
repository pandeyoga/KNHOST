import { useState } from "react";
import { CheckCircle2, Lock } from "lucide-react";
import { askReason } from "../../../services/confirmService";
import { ErrorBox } from "./GrnBits";
import { ACTION_LABEL, KIND_LABEL, allowedActions, errText, grnApi } from "./grnApi";

const BLOCK_TONE = "border-[#F5C2C0] bg-[#FDECEC] text-[#B4231F]";

function Discrepancy({ grn, d, run, canReview }) {
  const resolve = async (action) => {
    const reason = await askReason({ title: ACTION_LABEL[action], message: d.detail, reasonLabel: "Alasan (tercatat di audit)", confirmLabel: ACTION_LABEL[action] });
    if (reason) run(() => grnApi.post(grn.id, `discrepancies/${encodeURIComponent(d.key)}/resolve`, { expected_version: grn.version, action, reason }));
  };
  const tone = d.resolution ? "border-[#BFE3DC] bg-[#E7F6F3] text-[#0F766E]" : d.blocking ? BLOCK_TONE : "border-[#FFE3B3] bg-[#FFF9EE] text-[#B26A00]";
  return (
    <div data-testid={`grn-disc-${d.key}`} className={`rounded-lg border px-3 py-2 text-[11px] ${tone}`}>
      <div className="flex items-center justify-between gap-2">
        <p><b>Baris {d.line_no} · {KIND_LABEL[d.kind] || d.kind}</b>{d.blocking && !d.resolution ? " · pemblokir" : ""} — {d.detail}</p>
        {!d.resolution && canReview && grn.status === "reconcile" && (
          <div className="flex shrink-0 gap-1">
            {allowedActions(d.kind, grn.partner_type).map((a) => (
              <button key={a} data-testid={`grn-disc-${d.key}-${a}`} onClick={() => resolve(a)}
                className="rounded-md border border-current bg-white px-2 py-0.5 text-[10.5px] font-semibold">{ACTION_LABEL[a]}</button>
            ))}
          </div>
        )}
      </div>
      {d.resolution && <p className="mt-0.5 text-[10.5px]">{ACTION_LABEL[d.resolution.action]} oleh {d.resolution.by}: {d.resolution.reason}</p>}
    </div>
  );
}

export default function GrnReconPanel({ grn, onChange, canReview, canClose }) {
  const [err, setErr] = useState("");
  const [results, setResults] = useState(null);
  const run = async (fn) => {
    setErr("");
    try { const r = await fn(); if (r?.results) setResults(r.results); onChange(r?.grn || r); } catch (e) { setErr(errText(e)); }
  };
  const discs = (grn.discrepancies || []).filter((d) => !d.superseded);
  const open = discs.filter((d) => d.blocking && !d.resolution);
  const lines = (grn.lines || []).filter((ln) => !ln.is_non_stock);
  return (
    <div className="space-y-3" data-testid="grn-recon-panel">
      <div className="overflow-x-auto rounded-xl border border-[#EFF0F2]">
        <table className="w-full text-left text-[11px]" data-testid="grn-recon-table">
          <thead className="bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73]">
            <tr>{["No", "Barang", "Surat jalan", "Dihitung", "Sisa PO setelah ini", "Selisih", "Kelas", "Posting"].map((h) => <th key={h} className="px-2 py-1.5">{h}</th>)}</tr>
          </thead>
          <tbody>
            {lines.map((ln) => {
              const u = ln.target?.unit || "", rc = ln.recon || {};
              return (
                <tr key={ln.line_no} data-testid={`grn-recon-row-${ln.line_no}`} className="border-t border-[#EFF0F2]">
                  <td className="px-2 py-1.5">{ln.line_no}</td>
                  <td className="px-2">{ln.target?.product_name || ln.read?.description}</td>
                  <td className="px-2 tabular-nums">{ln.converted ? `${ln.converted.qty} ${u}` : "-"}{ln.declared?.rolls ? ` · ${ln.declared.rolls} roll` : ""}</td>
                  <td className="px-2 font-semibold tabular-nums">{ln.counted?.qty || 0} {u} · {ln.counted?.rolls || 0} roll</td>
                  <td className="px-2 tabular-nums">{rc.vs_remaining ?? "-"}</td>
                  <td className="px-2 tabular-nums">{rc.diff_qty ?? "-"}{rc.diff_pct != null ? ` (${rc.diff_pct}%)` : ""}</td>
                  <td className="px-2">{(rc.classes || []).map((c) => (
                    <span key={c} className={`mr-1 rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${c === "match" ? "bg-[#E7F6F3] text-[#0F766E]" : "bg-[#FFF6E5] text-[#B26A00]"}`}>{KIND_LABEL[c] || c}</span>
                  ))}</td>
                  <td className="px-2" data-testid={`grn-recon-posted-${ln.line_no}`}>{ln.posted?.status === "done" ? "Terposting" : ln.posted?.status === "failed" ? <span className="text-[#B4231F]">Gagal: {ln.posted.error}</span> : ln.posted?.status === "skipped" ? "Tidak diposting" : "-"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="space-y-1.5" data-testid="grn-disc-list">
        {discs.length ? discs.map((d) => <Discrepancy key={d.key} grn={grn} d={d} run={run} canReview={canReview} />)
          : <p className="flex items-center gap-1 text-[11px] text-[#0F766E]"><CheckCircle2 size={13} /> Tidak ada selisih — surat jalan cocok dengan hitungan fisik.</p>}
      </div>
      {results && (
        <ul data-testid="grn-close-results" className="rounded-lg bg-[#FAFBFC] p-2 text-[11px]">
          {results.map((r) => (
            <li key={r.lines.join(",")}>Baris {r.lines.join(", ")}: {r.status === "done" ? "terposting" : `gagal — ${r.error}`}
              {r.remainder?.created ? ` · tugas sisa ${r.remainder.remaining} dibuat` : ""}</li>
          ))}
        </ul>
      )}
      <ErrorBox text={err} />
      {["reconcile", "closing"].includes(grn.status) && (
        <div className="flex items-center justify-end gap-2">
          {grn.status === "reconcile" && canReview && (
            <button data-testid="grn-reopen-count" className="secondary-button" onClick={() => run(() => grnApi.post(grn.id, "reopen-count", { expected_version: grn.version }))}>Hitung ulang</button>
          )}
          {canClose && (
            <button data-testid="grn-close" className="primary-button" disabled={open.length > 0}
              title={open.length ? `${open.length} selisih pemblokir belum diselesaikan` : ""}
              onClick={() => run(() => grnApi.post(grn.id, "close", { expected_version: grn.version }))}>
              {open.length > 0 && <Lock size={12} />} {grn.status === "closing" ? "Ulangi posting" : "Tutup Penerimaan"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
