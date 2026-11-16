/** Kerangka halaman rincian seragam (gaya rincian Pesanan Khusus): kepala, kartu panel, sel angka, riwayat. */
import { useEffect } from "react";
import { ArrowLeft } from "lucide-react";
import { useAppNav } from "../context/AppNavContext";

export const K = ({ children }) => <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">{children}</p>;

/** "Kembali ke Daftar Order Makloon" → "Daftar Order Makloon"; "Kembali ke daftar" → "Daftar". */
export const listLabelOf = (label) => {
  const t = String(label || "").replace(/^Kembali(\s+ke)?\s*/i, "").trim() || "daftar";
  return t.charAt(0).toUpperCase() + t.slice(1);
};

/**
 * DetailBack — SATU tombol kembali rincian dokumen. Tanpa layar asal: "← {label}" ke daftar (seperti dulu, kelas
 * `className`). Sesudah melompat dari layar lain (PK-44, `useAppNav().origin`): satu baris "← Kembali ke {asal}"
 * (utama, `back-to-origin`) + tautan kecil "{Daftar …}" (`testId`), dan bilah asal di atas layar tidak dirender
 * (cek layar 16 Nov: dua "Kembali" bertumpuk).
 */
export function DetailBack({ onBack, label = "Kembali", testId, className = "back-button", iconSize = 14 }) {
  const { origin, goBack, registerDetailBack } = useAppNav();
  const active = Boolean(onBack && origin);
  useEffect(() => (active ? registerDetailBack() : undefined), [active, registerDetailBack]);
  if (!onBack) return null;
  if (!origin) {
    return (
      <button type="button" className={className} onClick={onBack} data-testid={testId}>
        <ArrowLeft size={iconSize} /> {label}
      </button>
    );
  }
  return (
    <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1" data-testid="detail-back-row">
      <button type="button" className="link-button" data-testid="back-to-origin" onClick={goBack}>
        <ArrowLeft size={14} aria-hidden="true" /> Kembali ke {origin.label || "layar sebelumnya"}
      </button>
      <span className="text-kn-text-2" aria-hidden="true">·</span>
      <button type="button" className="link-button text-fs-12 text-kn-text-2" data-testid={testId} onClick={onBack}>
        {listLabelOf(label)}
      </button>
    </div>
  );
}

/**
 * DetailHeader — kepala halaman DETAIL SEBARIS baku (object page): bilah "← Kembali ke daftar …" + judul + lencana +
 * aksi. FIX-8 (B1b UI-60, B4 §3.7) — pola tunggal untuk dokumen kerja bertahap (GRN, Perbaikan, Retur, Makloon);
 * `dangerActions` (batalkan/tolak) dirender TERPISAH di ujung kanan bergaris pemisah, tidak bersebelahan dengan aksi
 * utama atau "Tanya KN".
 */
export function DetailHeader({ onBack, backLabel = "Kembali", backTestId, icon: Icon, iconClass = "text-[#0058CC]",
  title, titleTestId, badges, subtitle, actions, dangerActions }) {
  return (
    <>
      <DetailBack onBack={onBack} label={backLabel} testId={backTestId} />
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
        {(actions || dangerActions) && (
          <div className="detail-actions">
            {actions}
            {dangerActions && <span className="kn-detail-danger" data-testid="detail-danger-actions">{dangerActions}</span>}
          </div>
        )}
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
