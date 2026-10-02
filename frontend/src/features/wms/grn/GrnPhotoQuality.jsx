import { AlertTriangle, CheckCircle2, Loader2, RefreshCcw } from "lucide-react";
import { pageBad, pageIssues } from "./photoQuality";

/** Hasil cek mutu satu foto SJ + tombol foto ulang (ganti halaman ini). */
export default function GrnPhotoQuality({ page, index, onRetake }) {
  if (!page.preview) return null;
  const issues = pageIssues(page);
  const bad = pageBad(page);
  const checking = page.ai?.status === "checking";
  const n = index + 1;
  return (
    <div data-testid={`grn-photo-quality-${n}`} className="space-y-1">
      {!issues.length && !checking && (
        <p data-testid={`grn-photo-ok-${n}`} className="flex items-center gap-1 text-[10.5px] font-semibold text-[#0F766E]"><CheckCircle2 size={12} /> Foto bagus — tajam, terang, utuh</p>
      )}
      {issues.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {issues.map((x) => (
            <span key={x.code} data-testid={`grn-photo-issue-${n}-${x.code}`} className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${x.bad ? "bg-[#FDECEC] text-[#B4231F]" : "bg-[#FFF6E5] text-[#8A5300]"}`}>
              <AlertTriangle size={10} /> {x.label}
            </span>
          ))}
        </div>
      )}
      {checking && <p data-testid={`grn-photo-ai-checking-${n}`} className="flex items-center gap-1 text-[10px] text-[#6B6B73]"><Loader2 size={11} className="animate-spin" /> AI memeriksa apakah terpotong / terbaca…</p>}
      {page.ai?.advice && <p data-testid={`grn-photo-advice-${n}`} className="text-[10.5px] text-[#3C3C43]">{page.ai.advice}</p>}
      {(bad || issues.length > 0) && (
        <label data-testid={`grn-photo-retake-${n}`} className={`inline-flex cursor-pointer items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px] font-semibold ${bad ? "bg-[#0058CC] text-white" : "border border-[#CFE0FF] text-[#0058CC]"}`}>
          <RefreshCcw size={12} /> Foto ulang halaman ini
          <input data-testid={`grn-photo-retake-input-${n}`} type="file" accept="image/*" capture="environment" className="hidden"
            onChange={(e) => { if (e.target.files?.[0]) onRetake(e.target.files[0]); e.target.value = ""; }} />
        </label>
      )}
    </div>
  );
}
