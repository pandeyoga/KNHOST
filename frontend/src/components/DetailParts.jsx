/** Kerangka halaman rincian seragam (gaya rincian Pesanan Khusus): kepala, kartu panel, sel angka, riwayat. */
import { ArrowLeft } from "lucide-react";

export const K = ({ children }) => <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">{children}</p>;

export function DetailHeader({ onBack, backLabel = "Kembali", backTestId, icon: Icon, iconClass = "text-[#0058CC]",
  title, titleTestId, badges, subtitle, actions }) {
  return (
    <>
      {onBack && (
        <button className="back-button" onClick={onBack} data-testid={backTestId}>
          <ArrowLeft size={14} /> {backLabel}
        </button>
      )}
      <div className="detail-header">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="detail-title flex items-center gap-2" data-testid={titleTestId}>
              {Icon && <Icon size={18} className={iconClass} />} {title}
            </h2>
            {badges}
          </div>
          {subtitle && <p className="detail-subtitle">{subtitle}</p>}
        </div>
        {actions && <div className="detail-actions">{actions}</div>}
      </div>
    </>
  );
}

export function Panel({ icon: Icon, title, right, children, testId, className = "" }) {
  return (
    <section className={`section-card !p-3 ${className}`} data-testid={testId}>
      {(title || right) && (
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="flex items-center gap-1 text-[10.5px] font-bold uppercase tracking-wide text-[#8E8E93]">{Icon && <Icon size={12} />} {title}</p>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function Cell({ label, children, testId, sub, tone }) {
  return (
    <div className="rounded-lg border border-[#EFF0F2] bg-white p-2" data-testid={testId}>
      <K>{label}</K>
      <div className="mt-0.5 text-[12px] font-semibold tabular-nums" style={tone ? { color: tone } : undefined}>{children}</div>
      {sub && <p className="text-[10px] text-[#9A9BA3]">{sub}</p>}
    </div>
  );
}

export function Timeline({ items, testId, empty = "Belum ada aktivitas." }) {
  if (!items?.length) return <p className="text-[11px] italic text-[#9A9BA3]" data-testid={testId}>{empty}</p>;
  return (
    <ol className="grid gap-1.5" data-testid={testId}>
      {items.map((it, i) => {
        const Icon = it.icon;
        return (
          <li key={i} className="flex items-start gap-2 text-[11.5px]">
            {Icon ? <Icon size={13} className="mt-0.5 shrink-0 text-[#8E8E93]" /> : <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#0058CC]" />}
            <div className="min-w-0 flex-1">
              <p className="font-semibold">{it.title}{it.note && <span className="font-normal text-[#3C3C43]"> — {it.note}</span>}</p>
              {it.meta && <p className="text-[10.5px] text-[#8E8E93]">{it.meta}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
