import { Loader2 } from "lucide-react";

/**
 * LoadingLine — baris "sedang memuat" baku: ikon berputar + teks.
 * 23 Okt — layar yang menarik datanya sendiri menulis "Memuat…" polos dengan gaya berbeda-beda (sebagian tanpa
 * penanda apa pun); satu komponen supaya keadaan memuat terlihat sama di semua layar (aturan UX E1).
 */
export default function LoadingLine({ text = "Memuat…", className = "", testId = "loading-line" }) {
  return (
    <p className={`flex items-center gap-1.5 text-[12px] text-[#6B6B73] ${className}`} role="status" aria-live="polite" data-testid={testId}>
      <Loader2 size={13} className="animate-spin" /> {text}
    </p>
  );
}
