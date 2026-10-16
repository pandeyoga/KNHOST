import { useState } from "react";
import { CheckCircle2, ChevronDown, Loader2, XCircle } from "lucide-react";

const LABEL = { dn_number: "Nomor SJ", dn_date: "Tanggal", qty: "Qty", unit: "Satuan", rolls: "Roll/pcs", po_ref: "No. PO baris" };
const pct = (v) => (v == null ? "—" : `${Math.round(v * 1000) / 10}%`);
const fmtLine = (x) => (x ? `${x.qty ?? "—"} ${x.unit || ""}${x.rolls != null ? ` · ${x.rolls} roll` : ""}${x.po_ref ? ` · PO ${x.po_ref}` : ""}` : "—");

function SampleResult({ r }) {
  const [open, setOpen] = useState(false);
  const s = r.score;
  const ok = s ? Object.values(s.checks).flat().filter(Boolean).length : 0;
  const tot = s ? Object.values(s.checks).flat().length : 0;
  return (
    <li data-testid={`ocr-run-result-${r.sample_id}`} className="rounded-lg border border-[#EFF0F2] bg-white">
      <button className="flex w-full items-center gap-2 px-3 py-2 text-left text-[11px]" onClick={() => setOpen((o) => !o)} disabled={!s}>
        {r.status === "pending" ? <Loader2 size={13} className="animate-spin text-[#8E8E93]" /> : r.status === "failed" ? <XCircle size={13} className="text-[#B4231F]" />
          : <CheckCircle2 size={13} className={ok === tot ? "text-[#0F766E]" : "text-[#B26A00]"} />}
        <span className="flex-1 truncate font-semibold">{r.label}</span>
        {r.status === "failed" && <span className="text-[#B4231F]">{r.error_code}</span>}
        {s && <span className="font-mono">{ok}/{tot} benar</span>}
        {(r.orientation || []).some(Boolean) && <span className="rounded bg-[#EAF1FF] px-1.5 text-[10px] text-[#0058CC]">diputar</span>}
        {s && <ChevronDown size={13} className={`transition-transform ${open ? "rotate-180" : ""}`} />}
      </button>
      {open && s && (
        <div className="space-y-1 border-t border-[#EFF0F2] px-3 py-2 text-[10.5px]">
          {Object.entries(s.header).filter(([, v]) => v.ok !== undefined).map(([k, v]) => (
            <p key={k} className={v.ok ? "text-[#0F766E]" : "text-[#B4231F]"}>{LABEL[k]}: dibaca <b className="font-mono">{v.got || "—"}</b>{!v.ok && <> · benar <b className="font-mono">{v.expected}</b></>}</p>
          ))}
          {s.lines.map((l) => (
            <p key={l.line_no} className={l.status === "ok" ? "text-[#0F766E]" : "text-[#B4231F]"}>
              Baris {l.line_no}: {l.status === "missing" ? "tidak terbaca" : l.status === "extra" ? `baris tambahan "${l.got}"` : <>dibaca <b className="font-mono">{fmtLine(l.got)}</b>{l.status !== "ok" && <> · benar <b className="font-mono">{fmtLine(l.expected)}</b></>}</>}
            </p>
          ))}
        </div>
      )}
    </li>
  );
}

/** Ringkasan uji: akurasi per field vs target + hasil per sampel. */
export default function GrnOcrRunReport({ run }) {
  const sum = run.summary || {};
  const acc = sum.accuracy || {};
  const gate = sum.gate || {};
  return (
    <div data-testid="ocr-run-report" className="space-y-3 rounded-xl border border-[#EFF0F2] bg-[#FAFBFC] p-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
        <p className="font-bold">Uji {(run.created_at || "").slice(0, 16).replace("T", " ")} · {run.model}{run.orient_model ? " + putar otomatis" : ""}</p>
        <p data-testid="ocr-run-status" className="text-[#6B6B73]">
          {run.status === "running" ? <span className="inline-flex items-center gap-1 text-[#0058CC]"><Loader2 size={12} className="animate-spin" /> {run.done}/{run.total} sampel…</span> : `${run.total} sampel`} · biaya US${(run.cost_usd || 0).toFixed(3)}
          {run.status === "done" && <b data-testid="ocr-run-gate" className={`ml-2 ${sum.gate_pass ? "text-[#0F766E]" : "text-[#B4231F]"}`}>{sum.gate_pass ? "LULUS target" : "Belum lulus target"}</b>}
        </p>
      </div>
      <div className="grid grid-cols-3 gap-2 md:grid-cols-6">
        {Object.keys(LABEL).map((k) => {
          const bad = gate[k] != null && acc[k] != null && acc[k] < gate[k];
          return (
            <div key={k} data-testid={`ocr-run-acc-${k}`} className={`rounded-lg border bg-white p-2 ${bad ? "border-[#F5C2C0]" : "border-[#EFF0F2]"}`}>
              <p className="text-[9.5px] font-bold uppercase text-[#6B6B73]">{LABEL[k]}</p>
              <p className={`font-mono text-[16px] font-bold ${bad ? "text-[#B4231F]" : "text-[#1C1C1E]"}`}>{pct(acc[k])}</p>
              <p className="text-[9.5px] text-[#8E8E93]">{(sum.counts?.[k] || [0, 0]).join("/")}{gate[k] ? ` · target ${gate[k] * 100}%` : ""}</p>
            </div>
          );
        })}
      </div>
      <ul className="space-y-1.5">{(run.results || []).map((r) => <SampleResult key={r.sample_id} r={r} />)}</ul>
    </div>
  );
}
