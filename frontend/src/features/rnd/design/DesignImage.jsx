/** DesignImage — gambar berkas desain dimuat lewat axios (membawa sesi/Authorization), bukan <img src> polos yang 401. */
import { useState } from "react";
import { ImageOff, Loader2 } from "lucide-react";
import { useProofBlob } from "../ProofImage";

export const IMAGE_FAIL_TEXT = "Gambar tidak dapat dimuat";

// UAT 24 Okt (audit UI tahap 2) — G5-39/G5-05/G5-06: gagal muat dulu hanya ikon 14px tanpa teks (berbeda dengan
// kartu tanpa sampul "Tanpa gambar"); berkas yang terunduh tetapi bukan gambar sah tampil sebagai ikon rusak
// bawaan peramban / teks alt tumpah. Sekarang: ikon + teks fallback mengikuti wadah; `compact` = ikon saja
// (thumbnail mungil) dengan teks di tooltip & pembaca layar.
export default function DesignImage({ src, alt = "", className = "", loading, compact = false, "data-testid": testId }) {
  const { src: blob, status } = useProofBlob(src, !!src);
  const [broken, setBroken] = useState("");
  if (src && status === "loading") return <span className={`flex items-center justify-center bg-[#F5F5F7] text-[#B5B5BC] ${className}`} data-testid={testId}><Loader2 size={14} className="animate-spin" /></span>;
  if (!src || status === "error" || !blob || broken === blob) {
    return (
      <span className={`flex flex-col items-center justify-center gap-0.5 overflow-hidden bg-[#F5F5F7] px-1 text-center text-[#9A9BA3] ${className}`}
        title={IMAGE_FAIL_TEXT} role="img" aria-label={IMAGE_FAIL_TEXT} data-testid={testId} data-image-failed="true">
        <ImageOff size={compact ? 12 : 16} className="shrink-0" />
        {!compact && <span className="text-[9.5px] font-medium leading-tight" data-testid={testId ? `${testId}-fail` : undefined}>{IMAGE_FAIL_TEXT}</span>}
      </span>
    );
  }
  return <img src={blob} alt={alt} className={className} loading={loading} data-testid={testId} onError={() => setBroken(blob)} />;
}
