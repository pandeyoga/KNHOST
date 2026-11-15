/**
 * financeShared (FINANCE) — UI kit bersama untuk modul analitik keuangan baru
 * (Arus Kas, Profitabilitas, Proyeksi Kas, Anggaran, Control Tower).
 * Konsisten dgn gaya existing (section-card, #6B219A, recharts, formatCurrency).
 */
import { formatCurrency, formatCompactIDR, formatPct } from "../../utils/formatters";
import { ChevronRight } from "lucide-react";
import { isZeroMetric } from "../../components/ListPageParts";

export const FC = {
  revenue: "#1B7F4B", cogs: "#C77700", expense: "#C0392B", net: "#6B219A",
  margin: "#0F766E", cash: "#0058CC", inflow: "#1B7F4B", outflow: "#C0392B",
  purple: "#6B219A", purpleBg: "#F3EAFB", grid: "#EFF0F2", muted: "#8E8E93",
  ink: "#1C1C1E", amber: "#C77700", blue: "#0058CC", teal: "#0F766E",
};
export const PIE = ["#6B219A", "#0058CC", "#1B7F4B", "#C77700", "#0F766E", "#C0392B", "#8E44AD", "#2E86DE"];

export const NOW = new Date();
export const YEARS = Array.from({ length: 6 }, (_, i) => {
  const y = String(NOW.getFullYear() - i);
  return { value: y, label: y };
});
export const MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

const pad = (n) => String(n).padStart(2, "0");
export const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

// UAT 24 Okt (audit UI tahap 2) — G1-14: sumbu/ringkas & persen keuangan dulu "150.0 jt", "1.4 M", "32.4%".
// Kini satu sumber id-ID (utils/formatters G0-14): "150 jt", "1,4 M", "32,4%".
export const compactIDR = (v) => formatCompactIDR(Number(v || 0));

export const entityParam = (se) => (se && se !== "all" ? { entity_id: se } : {});
export const fmtPct = (v, d = 1) => (v == null ? "—" : formatPct(Number(v), d));

export function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

export const chartTooltip = {
  contentStyle: { fontSize: 12, borderRadius: 10, border: "1px solid #EFF0F2", boxShadow: "0 4px 14px rgba(0,0,0,.06)" },
};

/**
 * KPI card: chip ikon + angka.
 * Fase 3 · P4 (L-08) — garis kiri warna-warni DIHAPUS (gaya baku = kartu berbingkai seperti `MetricRow`), dan nilai
 * nol tampil NETRAL abu (dulu "Rp 0" merah/hijau/ungu terbaca sebagai peringatan). `accent` kini hanya mewarnai ikon.
 */
/** Pecah "Rp 1.234.567" menjadi awalan + angka utuh (tidak dipatah); nilai lain dikembalikan apa adanya. */
export function kpiValueParts(value) {
  if (typeof value !== "string") return value;
  const m = value.match(/^(-?\s*Rp)[\s\u00a0]+(.+)$/);
  if (!m) return <span className="whitespace-nowrap">{value}</span>;
  // Tanda minus + "Rp" dikunci satu baris (cek layar MN-T2: "-" sempat patah sendiri di saldo negatif); awalan positif
  // tetap teks biasa.
  const awal = m[1].startsWith("-") ? <span className="kpi-neg-prefix whitespace-nowrap">{m[1]}</span> : m[1];
  return (<>{awal}{" "}<span className="whitespace-nowrap">{m[2]}</span></>);
}

/** PK-41 — sub-teks kartu: angka rupiah ("Rp 1.234.567", "Rp 1,2 jt") utuh satu baris; teks lain boleh turun baris. */
export function kpiSubParts(sub) {
  if (typeof sub !== "string") return sub;
  const parts = sub.split(/(-?Rp[\s\u00a0]+[\d.,]+(?:[\s\u00a0](?:rb|jt|M|T)\b)?)/);
  return parts.map((p, i) => (i % 2 === 1 ? <span key={i} className="whitespace-nowrap">{p}</span> : p));
}

export function KpiCard({ label, value, icon: Icon, tone, sub, accent = "#6B219A", testId, onClick, actionLabel = "Lihat rincian" }) {
  const zero = isZeroMetric(value);
  return (
    <div className="rounded-xl border border-[#EFF0F2] bg-white p-3.5" data-testid={testId}>
      <div className="flex items-start gap-3">
        {/* Audit UI 24 Okt (071–074/092 HP): nilai rupiah dulu `truncate` → "Rp 45.71…".
            Di HP ikon disembunyikan & angka boleh turun baris — tidak pernah dipotong. */}
        {Icon && (
          <div className="hidden w-9 h-9 rounded-lg items-center justify-center shrink-0 sm:flex"
               style={{ background: `${accent}14` }}>
            <Icon size={17} style={{ color: accent }} />
          </div>
        )}
        <div className="min-w-0">
          <p className="text-[11px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p>
          {/* Cek layar 14 Nov — angka tidak pernah dipatah di tengah ("Rp 155.000.0|00"): hanya awalan "Rp" yang boleh
              turun baris; angkanya utuh satu baris. */}
          <p className={`text-[15px] sm:text-[17px] font-bold tabular-nums ${zero ? "text-[#8E8E93]" : (tone || "text-[#1C1C1E]")}`}
             data-testid={testId ? `${testId}-value` : undefined}>{kpiValueParts(value)}</p>
          {/* PK-41 — sub-teks tidak lagi dipotong "…": angka rupiah di dalamnya utuh (kpiSubParts), teks lain turun baris. */}
          {sub && <p className="text-[10px] text-[#9A9BA3] mt-0.5 break-words" title={typeof sub === "string" ? sub : undefined}
                     data-testid={testId ? `${testId}-sub` : undefined}>{kpiSubParts(sub)}</p>}
          {/* PK-44 (IA-11) — kartu bertujuan: tombol tautan baku (bukan seluruh kartu sebagai tombol buatan sendiri). */}
          {onClick && (
            <button type="button" className="link-button mt-1" onClick={onClick}
              data-testid={testId ? `${testId}-open` : undefined}>
              {actionLabel} <ChevronRight size={12} aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function Panel({ title, icon: Icon, actions, children, testId, className = "" }) {
  return (
    <div className={`rounded-xl border border-[#EFF0F2] bg-white ${className}`} data-testid={testId}>
      <div className="flex items-center gap-2 px-3.5 py-2.5 border-b border-[#F2F2F5]">
        {Icon && <Icon size={14} className="text-[#6B219A]" />}
        <h4 className="text-[12px] font-bold text-[#1C1C1E]">{title}</h4>
        {actions && <div className="ml-auto flex items-center gap-2">{actions}</div>}
      </div>
      <div className="p-3.5">{children}</div>
    </div>
  );
}

export function EmptyState({ icon: Icon, title, hint, testId }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-10" data-testid={testId}>
      {Icon && <Icon size={22} className="text-[#C7C7CC] mb-2" />}
      <p className="text-[12px] font-semibold text-[#1C1C1E]">{title}</p>
      {hint && <p className="text-[11px] text-[#8E8E93] mt-1 max-w-sm">{hint}</p>}
    </div>
  );
}

export function Progress({ pct, color = "#6B219A" }) {
  const w = Math.max(0, Math.min(100, Number(pct || 0)));
  return (
    <div className="h-1.5 rounded-full bg-[#F0F0F3] overflow-hidden">
      <div className="h-full rounded-full" style={{ width: `${w}%`, background: color }} />
    </div>
  );
}

export function Badge({ tone = "neutral", children, testId }) {
  const map = {
    ok: "bg-[#EAF6EF] text-[#1B7F4B]", warning: "bg-[#FBF3E5] text-[#C77700]",
    over: "bg-[#FDECEC] text-[#C0392B]", neutral: "bg-[#F2F2F5] text-[#6B6B73]",
    purple: "bg-[#F3EAFB] text-[#6B219A]",
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold ${map[tone] || map.neutral}`}
          data-testid={testId}>{children}</span>
  );
}

export { formatCurrency };
