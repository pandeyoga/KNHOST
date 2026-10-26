/**
 * DesignCards — kartu layar **Desain & Pattern** (fase 3 · P6, D-09).
 *  · `DesignCard`   — kartu mode Master (kode, ronde, ditahan, proofing, berkas final).
 *  · `ShowcaseCard` — kartu mode Galeri (sampul besar, kepemilikan, sudah diproduksi) — dulu milik layar
 *    showcase `DesignGalleryView`; kini klik kartu membuka rincian desain yang SAMA dengan mode Master.
 * Diekstrak dari `RndDesignsView.jsx` / `hr/DesignGalleryView.jsx` supaya layar gabungan tetap < 500 baris.
 */
import { Award, ImageOff } from "lucide-react";
import DesignImage from "./DesignImage";
import { ScoreBadge } from "./ScoreInput";
import { RoundBadge } from "./RoundsProgress";
import { HoldBadge, OriginBadge, ProofingBadge } from "./DesignBadges";
import { designFileUrl } from "../rndApi";
import { DESIGN_STATUS_META, PROOFING_STATE_META, fmtScore } from "../rndMeta";
import { OwnershipBadge } from "../../hr/DesignOwnershipPanel";
import { formatDate } from "../../../utils/formatters";
import { actorLabel } from "../../../utils/actorLabel";
import { ACC_STATUSES } from "./designFilters";

const artworkCover = (d, version) => (d.files || []).find((x) => (x.kind || "artwork") === "artwork" && (x.version || 1) === version)
  || (d.files || []).find((x) => (x.kind || "artwork") === "artwork");

export function DesignCard({ d, onOpen }) {
  const meta = DESIGN_STATUS_META[d.status || "draft"] || DESIGN_STATUS_META.draft;
  const cover = artworkCover(d, d.version);
  const fin = d.final || {};
  const acc = ACC_STATUSES.includes(d.status);
  return (
    <button type="button" onClick={onOpen} data-testid={`design-card-${d.id}`}
      className={`overflow-hidden rounded-lg border bg-white text-left transition-shadow hover:shadow-md focus:outline-none focus:ring-2 focus:ring-[#0058CC]/40 ${d.on_hold ? "border-[#F2B48A]" : "border-[#E5E5EA]"}`}>
      <div className="relative flex h-28 items-center justify-center bg-[#F5F5F7]">
        {cover ? <DesignImage src={designFileUrl(d.id, cover.id)} alt={d.title} data-testid={`design-cover-${d.id}`} className={`h-full w-full object-cover ${d.on_hold ? "opacity-70" : ""}`} loading="lazy" />
          : <span className="text-[10.5px] text-[#9A9BA3]">belum ada berkas</span>}
        <span className="absolute inset-x-1.5 top-1.5 flex flex-wrap items-start justify-between gap-1">
          <span className="flex flex-wrap gap-1"><RoundBadge design={d} testId={`design-round-${d.id}`} /><HoldBadge design={d} testId={`design-hold-${d.id}`} />{d.origin && d.origin !== "internal" && <OriginBadge design={d} testId={`design-origin-${d.id}`} />}</span>
          {acc && (
            <span className="rounded bg-white/90 px-1.5 py-0.5 text-[10px] font-bold text-[#0058CC]" data-testid={`design-final-${d.id}`}>
              final {fin.mockup_files ?? 0}/1 mockup · {fin.source_files ?? 0}/1 file asli
            </span>
          )}
        </span>
      </div>
      <div className="space-y-1 p-2">
        <div className="flex flex-wrap items-center justify-between gap-1">
          <span className="min-w-0 break-all font-mono text-[11.5px] font-bold" data-testid={`design-code-${d.id}`}>{d.code || "tanpa kode"}</span>
          <ScoreBadge value={acc ? d.final_score : null} acc={acc} testId={`design-score-${d.id}`} />
        </div>
        <p className="truncate text-[11px] text-[#1C1C1E]">{d.title}</p>
        <p className="truncate text-[10.5px] text-[#8E8E93]" data-testid={`design-meta-${d.id}`}>
          {[d.category_name || d.category_code, d.design_category_name || d.design_category_code, d.created_by && actorLabel(d.created_by)]
            .filter(Boolean).join(" · ") || "—"}
        </p>
        <div className="flex flex-wrap items-center justify-between gap-1">
          <span className={`status-pill ${meta.cls}`} data-testid={`design-status-${d.id}`}>{meta.label}</span>
          <span className="text-[10.5px] text-[#8E8E93]">{d.artwork_count || 0} berkas</span>
        </div>
        {d.rounds_total > 0 && (
          <p className={`text-[11px] font-semibold ${d.paper_rounds_done >= d.rounds_total ? "text-[#1A5C2E]" : "text-[#6B6B73]"}`} data-testid={`design-paper-count-${d.id}`}>
            Print paper {d.paper_rounds_done || 0}/{d.rounds_total} ronde
          </p>
        )}
        <ProofingBadge design={d} testId={`design-proofing-${d.id}`} showDetail />
        {d.proofing?.master_product && (
          <p className="truncate text-[10.5px] font-semibold text-[#0058CC]" data-testid={`design-master-${d.id}`}>
            master: <span className="font-mono">{d.proofing.master_product.sku}</span>{d.proofing.master_product.name ? ` — ${d.proofing.master_product.name}` : ""}
          </p>
        )}
        {(d.recommended_products || []).length > 0 && (
          <p className="truncate text-[10.5px] text-[#0058CC]">untuk: {d.recommended_products.map((p) => p.sku).join(", ")}</p>
        )}
        <p className="text-[10.5px] text-[#8E8E93]" data-testid={`design-dates-${d.id}`}>
          {d.approved_at ? `ACC ${formatDate(d.approved_at)} · ` : ""}update {formatDate(d.updated_at)}
        </p>
      </div>
    </button>
  );
}

export function ShowcaseCard({ g, onOpen }) {
  const cover = artworkCover(g, g.approved_version || g.version);
  const st = DESIGN_STATUS_META[g.status] || DESIGN_STATUS_META.approved;
  const pm = PROOFING_STATE_META[g.proofing?.state || "none"] || PROOFING_STATE_META.none;
  const prods = g.recommended_products || [];
  return (
    <button type="button" onClick={onOpen} data-testid={`gallery-card-${g.id}`}
      className="section-card flex flex-col overflow-hidden !p-0 text-left transition-shadow hover:shadow-md focus:outline-none focus:ring-2 focus:ring-[#0058CC]/40">
      <div className="relative aspect-[4/3] bg-[#F2F3F5]">
        {cover ? <DesignImage src={designFileUrl(g.id, cover.id)} alt={g.title} className="h-full w-full object-cover" loading="lazy" />
          : <div className="flex h-full w-full flex-col items-center justify-center text-[#C7C9CF]"><ImageOff size={26} /><span className="mt-1 text-[11px]">Tanpa gambar</span></div>}
        <span className={`status-pill absolute left-2 top-2 ${st.cls}`} data-testid={`gallery-card-status-${g.id}`}>{st.label}</span>
        {g.final_score != null && (
          <span className="absolute right-2 top-2 inline-flex items-center gap-1 rounded bg-white/95 px-1.5 py-0.5 text-[10px] font-bold text-[#1A7A3A]" data-testid={`gallery-card-score-${g.id}`}>
            <Award size={10} /> {fmtScore(g.final_score)}/2
          </span>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-1.5 p-3">
        <p className="font-mono text-[10.5px] text-[#6B6B73]">{g.code}</p>
        <div className="flex flex-wrap gap-1">
          <OwnershipBadge d={g} testId={`gallery-card-ownership-${g.id}`} />
          <span data-testid={`gallery-card-produced-${g.id}`}
            className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${g.produced ? "bg-[#E8F6EE] text-[#1B7F4B]" : "bg-[#F2F2F5] text-[#6B6B73]"}`}>
            {g.produced ? "Sudah diproduksi" : "Belum diproduksi"}
          </span>
        </div>
        <h3 className="truncate text-[13px] font-bold leading-tight">{g.title}</h3>
        <p className="text-[10.5px] text-[#6B6B73]" data-testid={`gallery-card-meta-${g.id}`}>
          {[g.category_name || g.category_code, g.design_category_name || g.design_category_code, g.created_by && actorLabel(g.created_by)]
            .filter(Boolean).join(" · ") || "—"}
        </p>
        <div className="flex flex-wrap gap-1">
          {(g.tags || []).slice(0, 4).map((t) => <span key={t} className="rounded bg-[#EAF2FF] px-1.5 py-0.5 text-[10px] text-[#0058CC]">{t}</span>)}
          {(g.tags || []).length > 4 && <span className="text-[10px] text-[#9A9BA3]">+{g.tags.length - 4}</span>}
        </div>
        <div className="mt-auto flex flex-wrap items-center justify-between gap-1 pt-1.5 text-[10.5px]">
          <span className="rounded px-1.5 py-0.5 font-semibold" style={{ background: pm.bg, color: pm.fg }} data-testid={`gallery-card-rnd-${g.id}`}>{pm.label}</span>
          <span className="text-[#6B6B73]">{prods.length ? `${prods.length} produk` : "belum ada produk"}</span>
        </div>
      </div>
    </button>
  );
}

export function FilterField({ label, children }) {
  return (
    <div className="min-w-0">
      <p className="mb-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#6B6B73]">{label}</p>
      {children}
    </div>
  );
}

export function Kpi({ label, value, tone = "#1C1C1E", testId, onClick, active = false }) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag type={onClick ? "button" : undefined} onClick={onClick} data-testid={testId}
      className={`rounded-lg border p-2 text-left ${active ? "border-[#0058CC] bg-[#EAF2FF]" : "border-[#EFF0F2] bg-[#FAFBFC]"} ${onClick ? "hover:border-[#0058CC]" : ""}`}>
      <p className="text-[10.5px] font-bold uppercase text-[#8E8E93]">{label}</p>
      <p className="text-[14px] font-bold tabular-nums leading-tight" style={{ color: value ? tone : "#8E8E93" }}>{value}</p>
    </Tag>
  );
}
