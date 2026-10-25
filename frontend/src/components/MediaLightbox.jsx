/**
 * UAT 24 Okt (P17) — lightbox bersama untuk lampiran (foto, video, PDF): dimuat sebagai blob (header badan usaha),
 * panah ←/→, klik foto = perbesar, Esc menutup (tumpukan lapisan bersama), tombol "Unduh asli" eksplisit.
 * items: [{ url, filename?, content_type?, caption? }]
 */
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronLeft, ChevronRight, Download, FileText, ImageOff, Loader2, X, ZoomIn, ZoomOut } from "lucide-react";
import { useEscapeClose } from "@/utils/escapeLayers";
import { overlayDismiss } from "@/utils/overlayDismiss";
import { downloadFile, fileNameOf, kindOf, useBlobUrl } from "../hooks/useBlobUrl";

// UAT 24 Okt (audit UI tahap 2) — G0-18 · P-09: gambar yang gagal dimuat (unduhan gagal ATAU berkas rusak) kini
// melapor ke induk lewat `onStatus` sehingga tombol "Perbesar" disembunyikan; pesannya teks yang jelas.
function Media({ item, zoom, onZoom, onStatus }) {
  const kind = kindOf(item);
  const { src, status } = useBlobUrl(item.url, kind !== "file");
  const [broken, setBroken] = useState(false);
  useEffect(() => { setBroken(false); }, [item.url]);
  const effective = broken ? "error" : status;
  useEffect(() => { if (onStatus) onStatus(effective); }, [effective]); // eslint-disable-line react-hooks/exhaustive-deps
  if (kind === "file") {
    return <div className="flex flex-col items-center gap-2 rounded-lg bg-white/10 p-8 text-white"><FileText size={42} /><p className="text-[12px]">Pratinjau tidak tersedia untuk jenis berkas ini — gunakan "Unduh asli".</p></div>;
  }
  if (status === "loading") return <Loader2 size={28} className="animate-spin text-white" />;
  if (effective === "error") {
    return (
      <div className="flex flex-col items-center gap-2 text-white" data-testid="media-lightbox-error">
        <ImageOff size={32} /><p className="text-[12px]">{kind === "image" ? "Gambar tidak dapat dimuat." : "Berkas tidak dapat dimuat."}</p>
      </div>
    );
  }
  if (kind === "video") return <video src={src} controls className="max-h-[74vh] max-w-full rounded-lg bg-black" data-testid="media-lightbox-video" />;
  if (kind === "pdf") return <iframe src={src} title={fileNameOf(item)} className="h-[74vh] w-[min(900px,92vw)] rounded-lg bg-white" data-testid="media-lightbox-pdf" />;
  return (
    <img src={src} alt={fileNameOf(item)} onClick={onZoom} onError={() => setBroken(true)} data-testid="media-lightbox-image"
      className={`rounded-lg shadow-2xl ${zoom ? "max-w-none cursor-zoom-out" : "max-h-[74vh] max-w-full cursor-zoom-in object-contain"}`} />
  );
}

export default function MediaLightbox({ items, index = 0, onClose, testId = "media-lightbox" }) {
  const [i, setI] = useState(index);
  const [zoom, setZoom] = useState(false);
  const [busy, setBusy] = useState(false);
  const [mediaStatus, setMediaStatus] = useState("");
  useEscapeClose(true, onClose);
  const n = (items || []).length;
  const step = (d) => { setZoom(false); setMediaStatus(""); setI((x) => (x + d + n) % n); };
  useEffect(() => {
    const onKey = (e) => { if (n > 1 && e.key === "ArrowRight") step(1); if (n > 1 && e.key === "ArrowLeft") step(-1); };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }); // eslint-disable-line react-hooks/exhaustive-deps
  const it = (items || [])[i];
  if (!it) return null;
  const download = async () => { setBusy(true); try { await downloadFile(it.downloadUrl || it.url, fileNameOf(it)); } finally { setBusy(false); } };
  return createPortal(
    // Fase 3 · P1 — INV-UI-01: latar menutup hanya lewat gestur utuh DI LATAR (overlayDismiss), bukan onClick mentah.
    <div className="fixed inset-0 z-[180] flex items-center justify-center bg-black/85 p-3 sm:p-6" data-testid={testId} {...overlayDismiss(onClose)} role="dialog" aria-modal="true">
      <button type="button" className="absolute right-3 top-3 rounded-full bg-white/10 p-2 text-white hover:bg-white/20" onClick={onClose} aria-label="Tutup" data-testid={`${testId}-close`}><X size={18} /></button>
      {n > 1 && (<>
        <button type="button" className="absolute left-2 top-1/2 z-10 rounded-full bg-white/10 p-2 text-white hover:bg-white/20" onClick={(e) => { e.stopPropagation(); step(-1); }} aria-label="Sebelumnya" data-testid={`${testId}-prev`}><ChevronLeft size={20} /></button>
        <button type="button" className="absolute right-2 top-1/2 z-10 rounded-full bg-white/10 p-2 text-white hover:bg-white/20" onClick={(e) => { e.stopPropagation(); step(1); }} aria-label="Berikutnya" data-testid={`${testId}-next`}><ChevronRight size={20} /></button>
      </>)}
      <div className="flex max-h-full max-w-full flex-col items-center gap-3" onClick={(e) => e.stopPropagation()}>
        <div className={zoom ? "max-h-[78vh] max-w-[94vw] overflow-auto" : ""}><Media item={it} zoom={zoom} onZoom={() => setZoom((z) => !z)} onStatus={setMediaStatus} /></div>
        <div className="flex flex-wrap items-center justify-center gap-2 text-[12px] text-white" data-testid={`${testId}-caption`}>
          {it.caption && <b>{it.caption}</b>}
          <span className="max-w-[60vw] truncate text-white/80">{fileNameOf(it)}</span>
          {kindOf(it) === "image" && mediaStatus === "ok" && (
            <button type="button" className="inline-flex items-center gap-1 rounded-md bg-white/10 px-2 py-0.5 hover:bg-white/20" onClick={() => setZoom((z) => !z)}>
              {zoom ? <ZoomOut size={12} /> : <ZoomIn size={12} />} {zoom ? "Ukuran layar" : "Perbesar"}
            </button>
          )}
          <button type="button" className="inline-flex items-center gap-1 rounded-md bg-white/10 px-2 py-0.5 hover:bg-white/20" disabled={busy} onClick={download} data-testid={`${testId}-download`}>
            {busy ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />} Unduh asli
          </button>
          {n > 1 && <span className="text-white/60">{i + 1}/{n}</span>}
        </div>
      </div>
    </div>,
    document.body,
  );
}
