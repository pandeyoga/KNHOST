/**
 * SampleGalleryPanel — mode **Galeri** layar Sample R&D (fase 3 · P6, D-24b).
 *
 * Isi galeri per jenis lama (`SampleTypeGalleryView`: kartu bersampul foto bukti + saringan hasil · bukti ·
 * skor · supplier) kini menjadi satu mode tampilan di `RndSamplesView`. Chip jenis, tujuan, status, revisi,
 * lini & pencarian ada di layar induk; panel ini hanya memegang saringan khusus galeri (dilipat di HP).
 */
import { useMemo, useState } from "react";
import { Filter, FlaskConical, X } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import SampleTypeCard from "./SampleTypeCard";
import {
  cardTypeOf, EMPTY_GALLERY_FILTER, galleryMatch, PROOF_OPTS, RESULT_OPTS, SCORE_OPTS, suppliersOf,
} from "./sampleViewUtils";

// Di HP saringan lanjutan dilipat dulu; di layar lebar tetap terbuka seperti galeri lama.
const wideScreen = () => (typeof window === "undefined" || !window.matchMedia ? true : window.matchMedia("(min-width: 768px)").matches);

export default function SampleGalleryPanel({ rows, code = "", label = "", loading = false, emptyNode = null, onOpen }) {
  const [g, setG] = useState(EMPTY_GALLERY_FILTER);
  const [showFilters, setShowFilters] = useState(wideScreen);
  const set = (k, v) => setG((p) => ({ ...p, [k]: v }));
  const suppliers = useMemo(() => suppliersOf(rows), [rows]);
  const shown = useMemo(() => (rows || []).filter((s) => galleryMatch(s, code, g)), [rows, code, g]);
  const active = Object.values(g).filter(Boolean).length;
  const what = label ? `sample ${label.toLowerCase()}` : "sample";

  return (
    <div className="section-card" data-testid="sample-gallery-panel">
      <div className="section-body space-y-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className="secondary-button" onClick={() => setShowFilters((s) => !s)} data-testid="sample-gallery-toggle-filters">
            <Filter size={13} /> Saring hasil &amp; bukti {active ? `(${active})` : ""}
          </button>
          {active > 0 && (
            <button type="button" className="link-button text-[11px]" onClick={() => setG(EMPTY_GALLERY_FILTER)} data-testid="sample-gallery-reset-filter">
              <X size={10} className="inline" /> reset
            </button>
          )}
          <span className="ml-auto text-[11px] text-[#6B6B73]" data-testid="sample-gallery-count"><b>{shown.length}</b> dari {(rows || []).length} {what}</span>
        </div>
        {showFilters && (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4" data-testid="sample-gallery-filters">
            <KNSelect data-testid="sample-gallery-filter-supplier" className="field" value={g.supplier} searchable
              options={[{ value: "", label: "Semua supplier" }, ...suppliers.map(([id, name]) => ({ value: id, label: name }))]} onValueChange={(v) => set("supplier", v)} />
            <KNSelect data-testid="sample-gallery-filter-result" className="field" value={g.result} options={RESULT_OPTS} onValueChange={(v) => set("result", v)} />
            <KNSelect data-testid="sample-gallery-filter-score" className="field" value={g.score} options={SCORE_OPTS} onValueChange={(v) => set("score", v)} />
            <KNSelect data-testid="sample-gallery-filter-proof" className="field" value={g.proof} options={PROOF_OPTS} onValueChange={(v) => set("proof", v)} />
          </div>
        )}
        {loading ? (
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => <div key={i} className="h-[230px] animate-pulse rounded-lg bg-[#F5F5F7]" />)}
          </div>
        ) : shown.length === 0 ? (
          active > 0 && (rows || []).length > 0 ? (
            <div className="py-12 text-center text-[12px] text-[#6B6B73]" data-testid="sample-gallery-empty">
              <FlaskConical className="mx-auto mb-2 text-gray-300" size={28} />
              <p>Tidak ada {what} yang cocok dengan saringan hasil &amp; bukti.{" "}
                <button type="button" className="link-button" data-testid="sample-gallery-clear" onClick={() => setG(EMPTY_GALLERY_FILTER)}>Hapus saringan</button></p>
            </div>
          ) : <div data-testid="sample-gallery-empty">{emptyNode}</div>
        ) : (
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-4" data-testid="sample-gallery-grid">
            {shown.map((s) => <SampleTypeCard key={s.id} s={s} code={cardTypeOf(s, code)} onOpen={() => onOpen(s.id, cardTypeOf(s, code))} />)}
          </div>
        )}
      </div>
    </div>
  );
}
