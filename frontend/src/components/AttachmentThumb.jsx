/**
 * UAT 24 Okt (P17) — thumbnail lampiran yang bisa dipratinjau di halaman yang sama (tanpa unduh):
 *  · AttachmentThumb  — satu kotak thumbnail (foto: gambar; video/PDF/berkas: ikon + nama).
 *  · AttachmentGallery — deret thumbnail + MediaLightbox bersama (klik → lightbox, ←/→ antar-lampiran).
 * Berkas dimuat lewat axios (header badan usaha) — tidak ada `href` mentah / token di URL.
 * items: [{ url, filename?, content_type?, caption? }]
 */
import { useState } from "react";
import { FileText, Film, ImageOff, Loader2 } from "lucide-react";
import MediaLightbox from "./MediaLightbox";
import { fileNameOf, kindOf, useBlobUrl } from "../hooks/useBlobUrl";

export function AttachmentThumb({ item, size = 56, onOpen, testId, showName = false, fill = false }) {
  const kind = kindOf(item);
  const { src, status } = useBlobUrl(item?.url, kind === "image");
  const box = fill ? { width: "100%", height: "100%" } : { width: size, height: size };
  let inner;
  if (kind === "image" && status === "ok") inner = <img src={src} alt={fileNameOf(item)} className="h-full w-full object-cover" loading="lazy" />;
  else if (kind === "image" && status === "loading") inner = <Loader2 size={14} className="animate-spin text-[#B5B5BC]" />;
  else if (kind === "image") inner = <ImageOff size={14} className="text-[#C4361D]" />;
  else if (kind === "video") inner = <Film size={18} className="text-[#3C3C43]" />;
  else inner = <FileText size={18} className="text-[#3C3C43]" />;
  return (
    <button type="button" onClick={onOpen} title={fileNameOf(item)} data-testid={testId} data-url={item?.url || ""}
      className={`group ${fill ? "block h-full w-full" : "inline-flex flex-col items-center gap-0.5 align-top"}`}>
      <span style={box} className={`flex items-center justify-center overflow-hidden bg-[#F7F8FA] ${fill ? "" : "rounded-md border border-[#E5E5EA] group-hover:border-[#0058CC]"}`}>{inner}</span>
      {showName && <span className="max-w-[88px] truncate text-[10px] text-[#6B6B73]">{fileNameOf(item)}</span>}
    </button>
  );
}

export default function AttachmentGallery({ items, size = 56, showName = false, testId = "att", emptyText = "" }) {
  const [open, setOpen] = useState(-1);
  const list = (items || []).filter((x) => x && x.url);
  if (!list.length) return emptyText ? <span className="text-[11px] text-[#8E8E93]">{emptyText}</span> : null;
  return (
    <>
      <span className="inline-flex flex-wrap gap-1.5" data-testid={`${testId}-gallery`}>
        {list.map((it, i) => (
          <AttachmentThumb key={`${it.url}-${i}`} item={it} size={size} showName={showName} onOpen={(e) => { e?.stopPropagation?.(); setOpen(i); }}
            testId={`${testId}-thumb-${i}`} />
        ))}
      </span>
      {open >= 0 && <MediaLightbox items={list} index={open} onClose={() => setOpen(-1)} testId={`${testId}-lightbox`} />}
    </>
  );
}
