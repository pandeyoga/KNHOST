import { useEffect, useState } from "react";
import { RotateCw, ZoomIn, ZoomOut } from "lucide-react";
import { grnApi } from "./grnApi";

/** Foto SJ (kiri layar Review): dimuat lewat axios (header auth + entitas), zoom & putar. */
export default function GrnPhotoPane({ grn }) {
  const files = grn.files || [];
  const [page, setPage] = useState(1);
  const [url, setUrl] = useState("");
  const [zoom, setZoom] = useState(1);
  const [rot, setRot] = useState(0);
  useEffect(() => {
    if (!files.length) return undefined;
    let obj = "";
    grnApi.fileBlob(grn.id, page).then((b) => { obj = URL.createObjectURL(b); setUrl(obj); }).catch(() => setUrl(""));
    return () => { if (obj) URL.revokeObjectURL(obj); };
  }, [grn.id, page, files.length]);
  if (!files.length) return <div data-testid="grn-photo-empty" className="flex h-64 items-center justify-center rounded-xl border border-dashed border-[#E5E5EA] text-[11px] text-[#6B6B73]">Belum ada foto surat jalan.</div>;
  const cur = files.find((f) => f.page === page) || files[0];
  return (
    <div data-testid="grn-photo-pane" className="rounded-xl border border-[#EFF0F2] bg-[#FAFBFC]">
      <div className="flex items-center gap-1 border-b border-[#EFF0F2] px-2 py-1.5 text-[11px]">
        {files.map((f) => (
          <button key={f.page} data-testid={`grn-photo-page-${f.page}`} onClick={() => setPage(f.page)}
            className={`rounded px-2 py-0.5 font-semibold ${f.page === page ? "bg-[#0058CC] text-white" : "text-[#3C3C43]"}`}>{f.page}</button>
        ))}
        <span className="flex-1" />
        <button onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))} aria-label="Perkecil"><ZoomOut size={14} /></button>
        <button onClick={() => setZoom((z) => Math.min(3, z + 0.25))} aria-label="Perbesar" data-testid="grn-photo-zoom"><ZoomIn size={14} /></button>
        <button onClick={() => setRot((r) => (r + 90) % 360)} aria-label="Putar" data-testid="grn-photo-rotate"><RotateCw size={14} /></button>
      </div>
      <div className="h-[60vh] overflow-auto p-2">
        {cur?.content_type === "application/pdf"
          ? <iframe title="SJ" src={url} className="h-full w-full" />
          : url && <img src={url} alt={`Surat jalan halaman ${page}`} style={{ transform: `rotate(${rot}deg) scale(${zoom})`, transformOrigin: "top left" }} className="max-w-full transition-transform" />}
      </div>
    </div>
  );
}
