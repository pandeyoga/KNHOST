import { useEffect, useState } from "react";
import { AlertCircle, ArrowDownRight, ArrowUpRight, ChevronRight, RefreshCw, Users } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { formatCompactIDR, formatCurrency, formatPct } from "../../../utils/formatters";
import LoadingLine from "../../../components/LoadingLine";

const TONE = { waiting: "#B45309", processing: "#0058CC", shipped: "#7A3FA0", done: "#1B7F4B" };
const KIND_TONE = { rejected: "#C62828", waiting: "#B45309", draft: "#6B6B73", unpaid: "#A05000" };
// UAT 24 Okt (audit UI tahap 2) — P-06: label batang memakai formatter bersama (dulu toFixed → "1.5 jt").
const short = (n) => formatCompactIDR(n);

/** Dasbor Pesanan HP — hanya data pesanan milik sales yang login (GET /api/sales/order-dashboard). */
export default function MobileOrderDashboard({ selectedEntity, onOpenOrder }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const load = () => {
    setErr("");
    const params = selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {};
    axios.get(`${API}/sales/order-dashboard`, { params }).then((r) => setD(r.data))
      .catch((e) => setErr(e.response?.data?.detail || "Gagal memuat dasbor."));
  };
  useEffect(load, [selectedEntity]); // eslint-disable-line react-hooks/exhaustive-deps
  if (err) return <div className="notice-bar danger m-3 text-xs" data-testid="m-odash-error">{err}</div>;
  if (!d) return <LoadingLine className="justify-center p-6" />;
  const maxW = Math.max(1, ...d.weekly.map((w) => w.amount));
  const up = (d.growth_pct ?? 0) >= 0;
  return (
    <div className="space-y-2.5 p-3" data-testid="m-odash">
      {/* Audit UI 24 Okt (HP Dasbor Pesanan) — dasbor hanya menghitung SO dengan pengguna ini sebagai SALES PEMILIK;
          dulu tanpa keterangan sehingga Admin Sales melihat semua angka nol tanpa tahu sebabnya. */}
      <p className="text-[11px] m-muted" data-testid="m-odash-scope">Hanya pesanan dengan Anda sebagai sales pemilik. Semua pesanan PT ada di tab Pesanan.</p>
      <div className="m-card p-3" data-testid="m-odash-revenue">
        <div className="flex items-start justify-between">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-[#6B6B73]">Omzet bulan ini</p>
          <button onClick={load} aria-label="Muat ulang" data-testid="m-odash-refresh"><RefreshCw size={14} className="text-[#8E8E93]" /></button>
        </div>
        <p className="text-[22px] font-bold tabular-nums" data-testid="m-odash-revenue-this">{formatCurrency(d.revenue_this_month)}</p>
        <p className="flex items-center gap-1 text-[11.5px]" data-testid="m-odash-revenue-last">
          <span className="m-muted">Bulan lalu {formatCurrency(d.revenue_last_month)}</span>
          {d.growth_pct !== null && (
            <span className={`ml-auto inline-flex items-center font-semibold ${up ? "text-[#1B7F4B]" : "text-[#C62828]"}`} data-testid="m-odash-growth">
              {up ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}{formatPct(Math.abs(d.growth_pct), 1, { trim: true })}</span>
          )}
        </p>
      </div>

      <div className="grid grid-cols-4 gap-1.5" data-testid="m-odash-status">
        {d.status_counts.map((s) => (
          <div key={s.key} className="m-card px-1.5 py-2 text-center" data-testid={`m-odash-status-${s.key}`}>
            <p className="text-[18px] font-bold tabular-nums" style={{ color: TONE[s.key] }}>{s.count}</p>
            <p className="text-[10px] font-semibold leading-tight text-[#6B6B73]">{s.label}</p>
          </div>
        ))}
      </div>

      <div className="m-card p-3" data-testid="m-odash-weekly">
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-[#6B6B73]">Tren 8 minggu</p>
        <div className="flex h-28 items-end gap-1.5">
          {d.weekly.map((w, i) => (
            <div key={w.week_start} className="flex flex-1 flex-col items-center gap-1" data-testid={`m-odash-week-${i}`}>
              <span className="text-[8.5px] tabular-nums text-[#6B6B73]">{w.amount ? short(w.amount) : ""}</span>
              <div className="w-full rounded-t bg-[#0058CC]" style={{ height: `${Math.max(3, (w.amount / maxW) * 80)}px`, opacity: i === 7 ? 1 : 0.45 }} />
              <span className="text-[8.5px] m-muted">{w.week_start.slice(8, 10)}/{w.week_start.slice(5, 7)}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="m-card p-3" data-testid="m-odash-top">
        <p className="mb-1.5 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-[#6B6B73]"><Users size={11} /> 5 pelanggan teratas · 90 hari</p>
        {!d.top_customers.length && <p className="text-[11.5px] m-muted">Belum ada pesanan.</p>}
        {d.top_customers.map((c, i) => (
          <p key={c.customer_id || i} className="flex justify-between py-0.5 text-[12px]" data-testid={`m-odash-top-${i}`}>
            <span className="truncate"><b className="mr-1 text-[#8E8E93]">{i + 1}.</b>{c.customer_name} <span className="m-muted">· {c.orders} SO</span></span>
            <span className="shrink-0 font-semibold tabular-nums">{formatCurrency(c.amount)}</span>
          </p>
        ))}
      </div>

      <div className="m-card p-3" data-testid="m-odash-action">
        <p className="mb-1.5 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-[#6B6B73]"><AlertCircle size={11} /> Butuh tindakan ({d.action_total})</p>
        {!d.action_needed.length && <p className="text-[11.5px] m-muted" data-testid="m-odash-action-empty">Tidak ada pesanan yang perlu ditindaklanjuti.</p>}
        {d.action_needed.map((a) => (
          <button key={a.order_id} className="flex w-full items-center gap-2 border-t border-[#F2F3F5] py-2 text-left first:border-t-0" onClick={() => onOpenOrder?.(a.order_id)} data-testid={`m-odash-action-${a.order_id}`}>
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: KIND_TONE[a.kind] || "#8E8E93" }} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[12px] font-semibold">{a.number} · {a.customer_name}</span>
              <span className="block text-[10.5px]" style={{ color: KIND_TONE[a.kind] }}>{a.reason} · {formatCurrency(a.amount)}</span>
            </span>
            <ChevronRight size={14} className="text-[#C7C7CC]" />
          </button>
        ))}
      </div>
    </div>
  );
}
