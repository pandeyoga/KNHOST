/** L03 LN-031 — checklist print paper per ronde (aktivitas Designer, bukan persetujuan). */
import { useState } from "react";
import { Printer } from "lucide-react";
import { setRoundPaper } from "../rndApi";
import { errMsg } from "../rndMeta";
import { formatDateTime } from "../../../utils/formatters";

const fmtAt = (iso) => (iso ? formatDateTime(iso) : "");   // 23 Okt — baku WIB

export default function RoundPaperCheck({ design, version, canPaper, onDone, onError }) {
  const rnd = (design.rounds || []).find((x) => x.version === version.version) || {};
  const paper = rnd.paper || {};
  const history = rnd.paper_history || [];
  const [busy, setBusy] = useState(false);
  const archived = ["archived", "retired"].includes(design.status);
  const toggle = async () => {
    setBusy(true);
    try {
      await setRoundPaper(design.id, version.version, !paper.checked);
      onDone?.(!paper.checked ? "Print paper ronde ini dicatat." : "Centang print paper dibatalkan.");
    } catch (e) { onError?.(errMsg(e, "Gagal menyimpan checklist paper.")); } finally { setBusy(false); }
  };
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]" data-testid={`design-round-paper-${version.version}`}>
      <label className={`inline-flex items-center gap-1.5 ${canPaper && !archived ? "cursor-pointer" : "opacity-80"}`}>
        <input type="checkbox" checked={!!paper.checked} disabled={!canPaper || archived || busy} onChange={toggle}
          data-testid={`design-round-paper-toggle-${version.version}`} />
        <Printer size={12} className="text-[#6B6B73]" />
        <span className="font-semibold">Print paper</span>
      </label>
      {paper.checked ? (
        <span className="text-[#1A5C2E]" data-testid={`design-round-paper-info-${version.version}`}>dicentang {paper.by} · {fmtAt(paper.at)}</span>
      ) : (
        <span className="text-[#9A9BA3]">belum dicetak{history.length ? ` · dibatalkan ${paper.by || ""} ${fmtAt(paper.at)}` : ""}</span>
      )}
      <span className="text-[10px] text-[#9A9BA3]">(catatan aktivitas — tidak menyetujui desain/proofing)</span>
    </div>
  );
}
