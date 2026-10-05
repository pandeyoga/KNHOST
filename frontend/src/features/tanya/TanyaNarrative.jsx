import { useEffect, useState } from "react";
import { Bot, Calculator, Loader2 } from "lucide-react";
import { fetchNarrative } from "./tanyaApi";
import { TanyaMarkdown } from "./TanyaMarkdown";

/** Ringkasan di atas grafik template: otomatis dari angka server, diganti narasi AI bila AI aktif. */
export function TanyaNarrative({ data, aiEnabled }) {
  const mode = data.template?.narrative || "none";
  const [narr, setNarr] = useState({ text: data.narrative, source: data.narrative_source || "auto" });
  const [loading, setLoading] = useState(false);
  const ids = Object.keys(data.results || {}).join(",");
  useEffect(() => {
    setNarr({ text: data.narrative, source: data.narrative_source || "auto" });
    if (!aiEnabled || mode === "none" || !ids || data.narrative_source === "ai") return;
    let alive = true;
    setLoading(true);
    fetchNarrative(data.template.id, ids.split(","))
      .then((r) => { if (alive && r?.text) setNarr(r); })
      .catch(() => {})
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [ids, aiEnabled, mode, data.template?.id, data.narrative, data.narrative_source]);
  if (mode === "none" || !narr.text) return null;
  const ai = narr.source === "ai";
  return (
    <div className="tanya-narr" data-testid="tanya-narrative">
      <div className="tanya-narr-tag" data-testid="tanya-narrative-source">
        {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : ai ? <Bot className="h-3.5 w-3.5" /> : <Calculator className="h-3.5 w-3.5" />}
        {loading ? "Menyusun ringkasan AI…" : ai ? `Ringkasan AI${narr.model ? ` · ${narr.model}` : ""}` : "Ringkasan otomatis dari angka server"}
      </div>
      <TanyaMarkdown text={narr.text} testId="tanya-narrative-text" />
    </div>
  );
}
