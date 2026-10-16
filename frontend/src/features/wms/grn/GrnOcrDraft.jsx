/** Draf roll hasil OCR — langsung terlihat setelah foto SJ dibaca (HP gudang & admin). Hitung buta tetap dihormati. */
import { AlertTriangle, FileText } from "lucide-react";

const RAGU = (r) => r.doc_status && r.doc_status !== "ok";

export default function GrnOcrDraft({ grn }) {
  if (!["review", "counting"].includes(grn.status)) return null;
  const lines = (grn.lines || []).filter((ln) => !ln.is_non_stock && (ln.expected_rolls || []).length);
  if (grn.blind) {
    if (grn.status !== "review") return null;
    return <p className="rounded-lg bg-[#EEF4FF] px-3 py-2 text-[11px] text-[#0058CC]" data-testid="grn-ocr-draft-blind">Surat jalan sudah dibaca otomatis dan menunggu dicek admin. Hitung buta aktif — ukur roll apa adanya saat tahap hitung dimulai.</p>;
  }
  if (!lines.length) return null;
  return (
    <div className="space-y-2 rounded-xl border border-[#E3E8F4] bg-[#F8FAFF] p-3" data-testid="grn-ocr-draft">
      <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-[#0058CC]"><FileText size={12} /> Draf roll dari surat jalan{grn.status === "review" ? " · belum disimpan, menunggu dicek" : ""}</p>
      {lines.map((ln) => {
        const rolls = ln.expected_rolls;
        const unit = rolls[0]?.length_unit || ln.declared?.unit || "";
        const total = Math.round(rolls.reduce((a, r) => a + (Number(r.length) || 0), 0) * 100) / 100;
        const ragu = rolls.filter(RAGU).length;
        return (
          <div key={ln.line_no} data-testid={`grn-ocr-draft-line-${ln.line_no}`}>
            <p className="text-[12px] font-bold">{ln.target?.product_name || ln.read?.description || `Baris ${ln.line_no}`}</p>
            <p className="text-[11px] text-[#6B6B73]" data-testid={`grn-ocr-draft-total-${ln.line_no}`}>{rolls.length} roll · {total} {unit}{ragu ? ` · ${ragu} roll ragu` : ""}</p>
            <div className="mt-1 grid grid-cols-4 gap-1 sm:grid-cols-6">
              {rolls.map((r) => (
                <span key={r.seq} data-testid={`grn-ocr-draft-roll-${ln.line_no}-${r.seq}`}
                  className={`rounded-md px-1.5 py-1 text-center text-[11px] tabular-nums ${RAGU(r) ? "bg-[#FFF6E5] font-bold text-[#B26A00]" : r.status === "counted" ? "bg-[#E7F6F3] text-[#0F766E]" : "bg-white text-[#1C1C1E]"}`}>
                  #{r.seq} {r.length ?? "?"}{RAGU(r) && <AlertTriangle size={10} className="ml-0.5 inline" />}
                </span>
              ))}
            </div>
          </div>
        );
      })}
      {lines.some((ln) => ln.expected_rolls.some(RAGU)) && <p className="text-[10.5px] text-[#B26A00]" data-testid="grn-ocr-draft-ragu-note">Angka bertanda kuning tidak terbaca jelas — wajib dicek/diukur ulang.</p>}
    </div>
  );
}
