/**
 * SampleProofGallery — **galeri bukti per jenis** (Labdip/Handfeel/Proofing): satu kolom per
 * supplier, thumbnail tiap round berdampingan → membandingkan hasil supplier secara visual.
 * Klik thumbnail → lightbox (panah kiri/kanan, Esc menutup).
 *
 * Fase 4 · R4 (L-03) — lightbox = `components/MediaLightbox` bersama (dulu lapisan `fixed inset-0` sendiri dengan
 * klik-latar mentah): latar lewat `overlayDismiss`, Esc lewat tumpukan lapisan, "Unduh asli" eksplisit, pratinjau
 * memuat blob ber-header badan usaha (sama dengan lampiran round). Keterangan supplier · round · hasil · skor di
 * baris keterangan lightbox.
 */
import { useMemo, useState } from "react";
import { Images } from "lucide-react";
import MediaLightbox from "../../components/MediaLightbox";
import { roundProofUrl } from "./rndApi";
import { ROUND_RESULT_META } from "./rndMeta";
import { roundTypeOf } from "./sampleTypeMeta";
import ProofImage from "./ProofImage";

/** Keterangan lightbox: "Supplier · Round 2 · Lolos · skor 86". */
function captionOf(it) {
  const rm = ROUND_RESULT_META[it.round.result || ""] || ROUND_RESULT_META[""];
  return [it.supplierName, `Round ${it.round.round_no}`, rm.label, it.round.score != null ? `skor ${it.round.score}` : ""]
    .filter(Boolean).join(" · ");
}

export default function SampleProofGallery({ sample, code }) {
  const [openIdx, setOpenIdx] = useState(-1);
  const cols = useMemo(() => (sample.participants || []).map((p) => {
    const rounds = (sample.rounds || []).filter((r) => r.supplier_id === p.supplier_id && roundTypeOf(r, sample) === code);
    const items = rounds.flatMap((round) => (round.attachments || []).map((a) => ({
      a, round, url: roundProofUrl(sample.id, round.id, a.id), supplierName: p.supplier_name,
    })));
    return { p, rounds, items };
  }).filter((c) => c.rounds.length > 0), [sample, code]);
  const all = useMemo(() => cols.flatMap((c) => c.items), [cols]);
  if (cols.length === 0) return null;
  const openFile = (fileId) => setOpenIdx(all.findIndex((x) => x.a.id === fileId));

  return (
    <div className="rounded-lg border border-[#EFF0F2]" data-testid={`sample-proof-gallery-${code}`}>
      <p className="flex items-center gap-1.5 border-b border-[#EFF0F2] bg-[#FAFBFC] px-3 py-1.5 text-[10.5px] font-bold uppercase text-[#8E8E93]">
        <Images size={12} /> Galeri bukti · {all.length} berkas
      </p>
      {all.length === 0 ? (
        <p className="px-3 py-3 text-[11px] text-[#8E8E93]" data-testid={`sample-proof-empty-${code}`}>Belum ada foto bukti untuk jenis ini — unggah dari round yang sedang terbuka.</p>
      ) : (
        <div className="grid gap-px bg-[#EFF0F2]" style={{ gridTemplateColumns: `repeat(${Math.min(cols.length, 4)}, minmax(0, 1fr))` }}>
          {cols.map(({ p, rounds, items }) => {
            const best = rounds.reduce((a, r) => (r.score != null ? Math.max(a ?? 0, Number(r.score)) : a), null);
            const last = rounds[rounds.length - 1] || {};
            const rm = ROUND_RESULT_META[last.result || ""] || ROUND_RESULT_META[""];
            return (
              <div key={p.supplier_id} className="bg-white p-2.5" data-testid={`sample-proof-col-${code}-${p.supplier_id}`}>
                <div className="mb-2 flex items-center justify-between gap-2">
                  <p className="truncate text-[11.5px] font-bold text-[#1C1C1E]">{p.supplier_name}</p>
                  <span className="shrink-0 text-[10px] font-semibold" style={{ color: rm.tone }}>{rm.label}{best != null ? ` · ${best}` : ""}</span>
                </div>
                {items.length === 0 ? (
                  <p className="rounded-md border border-dashed border-[#E5E5EA] px-2 py-4 text-center text-[10.5px] text-[#9A9BA3]">belum ada bukti</p>
                ) : (
                  <div className="grid grid-cols-[repeat(auto-fill,minmax(84px,1fr))] gap-1.5">
                    {items.map((it) => {
                      const irm = ROUND_RESULT_META[it.round.result || ""] || ROUND_RESULT_META[""];
                      return (
                        <button key={it.a.id} type="button" onClick={() => openFile(it.a.id)} title={`Round ${it.round.round_no} · ${it.a.filename}`}
                          data-testid={`sample-proof-thumb-${it.a.id}`}
                          className="group relative aspect-square overflow-hidden rounded-md border border-[#EFF0F2] transition-[transform,box-shadow] hover:-translate-y-0.5 hover:shadow-md">
                          <ProofImage url={it.url} attachment={it.a} alt={it.a.filename} className="h-full w-full" />
                          <span className="absolute left-1 top-1 rounded bg-black/60 px-1 text-[9px] font-bold text-white">R{it.round.round_no}</span>
                          <span className="absolute bottom-1 right-1 h-2 w-2 rounded-full ring-2 ring-white" style={{ background: irm.tone }} />
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
      {openIdx >= 0 && (
        <MediaLightbox index={openIdx} onClose={() => setOpenIdx(-1)} testId="sample-proof-lightbox"
          items={all.map((it) => ({ url: it.url, filename: it.a.filename, content_type: it.a.content_type, caption: captionOf(it) }))} />
      )}
    </div>
  );
}
