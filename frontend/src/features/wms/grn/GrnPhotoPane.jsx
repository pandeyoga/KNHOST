import { useEffect, useState } from "react";
import { RotateCw, ZoomIn, ZoomOut } from "lucide-react";
import { grnApi } from "./grnApi";

/** Putar gambar lewat canvas (bukan CSS) supaya foto yang diputar tetap utuh di dalam panel. */
function useRotated(url, rot) {
  const [out, setOut] = useState("");
  useEffect(() => {
    if (!url || !rot) { setOut(url); return undefined; }
    let alive = true, obj = "";
    const img = new Image();
    img.onload = () => {
      const c = document.createElement("canvas");
      const side = rot % 180 !== 0;
      c.width = side ? img.height : img.width; c.height = side ? img.width : img.height;
      const ctx = c.getContext("2d");
      ctx.translate(c.width / 2, c.height / 2); ctx.rotate((rot * Math.PI) / 180); ctx.drawImage(img, -img.width / 2, -img.height / 2);
      c.toBlob((b) => { if (alive && b) { obj = URL.createObjectURL(b); setOut(obj); } }, "image/jpeg", 0.9);
    };
    img.src = url;
    return () => { alive = false; if (obj) URL.revokeObjectURL(obj); };
  }, [url, rot]);
  return out;
}

/** Foto SJ (kiri layar Review): dimuat lewat axios (header auth + entitas), zoom & putar. */
export default function GrnPhotoPane({ grn }) {
  const files = grn.files || [];
  const [page, setPage] = useState(1);
  const [url, setUrl] = useState("");
  const [zoom, setZoom] = useState(1);
  const [rot, setRot] = useState(0);
  const autoRot = (grn.extraction?.orientation || []).find((o) => o.page === page)?.rotate_cw || 0;
  useEffect(() => { setRot(autoRot); }, [autoRot, page]);
  useEffect(() => {
    if (!files.length) return undefined;
    let obj = "";
    grnApi.fileBlob(grn.id, page).then((b) => { obj = URL.createObjectURL(b); setUrl(obj); }).catch(() => setUrl(""));
    return () => { if (obj) URL.revokeObjectURL(obj); };
  }, [grn.id, page, files.length]);
  const shown = useRotated(url, rot);
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
        {autoRot > 0 && <span data-testid="grn-photo-auto-rotated" className="mr-1 rounded bg-[#EAF1FF] px-1.5 py-0.5 text-[10px] font-semibold text-[#0058CC]">diputar otomatis</span>}
        <button onClick={() => setRot((r) => (r + 90) % 360)} aria-label="Putar" data-testid="grn-photo-rotate"><RotateCw size={14} /></button>
      </div>
      <div className="max-h-[55vh] overflow-auto p-2 lg:h-[60vh] lg:max-h-none">
        {cur?.content_type === "application/pdf"
          ? <iframe title="SJ" src={url} className="h-full w-full" />
          : shown && <img data-testid="grn-photo-img" src={shown} alt={`Surat jalan halaman ${page}`} style={{ transform: `scale(${zoom})`, transformOrigin: "top left" }} className="max-w-full transition-transform" />}
      </div>
    </div>
  );
}
