import { useEffect, useState, useCallback } from "react";
import {
  Wallet, TrendingUp, Target, Banknote, ShoppingBag, RefreshCw,
  ArrowUpRight, AlertTriangle, Users, ChevronRight, Receipt, Sparkles,
} from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import axios, { API } from "../../../services/apiClient";
import WaitingQueueBoard from "../../../components/WaitingQueueBoard";
import { boardLook, selectWaitingBoards } from "../../../config/waitingBoards";
import ErrorNotice from "../../../components/ErrorNotice";
import { formatCurrency } from "../../../utils/formatters";
import { getStage, stageMeta } from "../../../utils/soStatus";

function MiniKpi({ icon: Icon, label, value, sub, color = "#007AFF", loading }) {
  return (
    <div className="m-card p-3" data-testid={`m-kpi-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <div className="flex items-center gap-2">
        <span className="grid h-7 w-7 place-items-center rounded-lg" style={{ background: `${color}1A` }}>
          <Icon size={15} style={{ color }} />
        </span>
        <span className="text-[11px] font-semibold m-muted leading-tight">{label}</span>
      </div>
      {loading ? (
        <div className="mt-2 h-6 animate-pulse rounded bg-[#F1F2F4]" />
      ) : (
        <p className="mt-1.5 text-[18px] font-bold tabular-nums text-[#1C1C1E] leading-tight">{value}</p>
      )}
      {sub && <p className="mt-0.5 text-[10.5px] m-muted">{sub}</p>}
    </div>
  );
}

// Papan "giliran Anda" menunjuk view desktop → di HP dibuka layar HP bila ada, selain itu tampilan penuh.
const BOARD_SUB = { "price-approvals": "price-status", "special-orders": "special", "internal-requests": "internal", returns: "returns", amendments: "amendments", "customers-crm": "crm" };
const CREDIT_TONE = { ok: ["Aman", "#1B7F4B", "#E6F6EC"], warning: ["Waspada", "#8A5300", "#FFF4E5"], blocked: ["Blokir", "#C0392B", "#FDEDE7"] };

export default function MobileSalesHome({ token, user, onNewOrder, onOpenTab, onAskKn, onOpenSub, onOpenFull }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/home/sales`);
      setData(res.data);
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat performa. Coba lagi.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const comm = data?.commission || {};
  const target = data?.target || {};
  const kpi = data?.kpi || {};
  const achievement = Math.min(target.achievement_pct || 0, 100);
  const recent = data?.recent_orders || [];
  const collections = data?.collections || [];
  const customers = data?.customers || [];
  const history = (data?.history || []).map((h) => ({ period: (h.period || "").slice(5), incentive: h.total_incentive ?? h.commission ?? 0 }));
  const boardsUnreadable = !loading && (!data || !!error);
  const boards = selectWaitingBoards(data, boardsUnreadable);
  const goBoard = (view) => {
    if (view === "orders") return onOpenTab?.("orders");
    if (BOARD_SUB[view]) return onOpenSub?.(BOARD_SUB[view]);
    return onOpenFull?.(view, view);
  };

  return (
    <div className="space-y-3" data-testid="mobile-sales-home">
      <button data-testid="m-home-new-order" onClick={onNewOrder}
        className="primary-button m-press w-full justify-center py-3 text-[14px]">
        <ShoppingBag size={16} /> Buat Pesanan Baru
      </button>

      {onAskKn && (
        <button data-testid="m-home-ask-kn" onClick={onAskKn} className="m-card m-press flex w-full items-center gap-3 p-3 text-left">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-[#6B219A1A]"><Sparkles size={17} className="text-[#6B219A]" /></span>
          <span className="min-w-0 flex-1">
            <span className="block text-[13px] font-bold">Tanya KN</span>
            <span className="block truncate text-[11px] m-muted">Laporan penjualan, pelanggan terbesar, piutang — langsung dari HP</span>
          </span>
          <ChevronRight size={16} className="text-[#C7C7CC]" />
        </button>
      )}

      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="m-home-error" />

      {boards.length > 0 && (
        <div className="space-y-2" data-testid="m-home-boards">
          {boards.map((b) => {
            const look = boardLook(b.key);
            return (
              <WaitingQueueBoard key={b.key} board={b} loading={loading && !data} unreadable={boardsUnreadable} onRetry={load}
                onNavigate={goBoard} onActed={load} icon={look.icon} accent={look.accent} gotoLabel={look.goto}
                emptyText={look.empty} title={look.title} testIdBase={`m-home-board-${b.key}`} rowTestIdBase={`m-home-board-${b.key}-row`} />
            );
          })}
        </div>
      )}

      <div className="flex items-center justify-between px-0.5">
        <h2 className="m-section-title">Performa Saya{data?.period ? ` — ${data.period}` : ""}</h2>
        <button onClick={load} className="text-[#6B6B73]" data-testid="m-home-refresh" aria-label="Muat ulang">
          <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2.5">
        <MiniKpi icon={Wallet} label="Komisi MTD" value={formatCurrency(comm.mtd_accrual)} sub="Akrual berjalan" color="#34C759" loading={loading} />
        <MiniKpi icon={TrendingUp} label="Proyeksi" value={formatCurrency(comm.projection_month_end)} sub="Akhir bulan" color="#007AFF" loading={loading} />
        <MiniKpi icon={Banknote} label="Penjualan MTD" value={formatCurrency(kpi.total_sales)} sub={`${kpi.orders_count || 0} pesanan`} color="#FF9500" loading={loading} />
        <MiniKpi icon={ArrowUpRight} label="Tertagih" value={formatCurrency(kpi.total_collected)} sub={`${Math.round((kpi.collection_rate || 0) * 1000) / 10}% tertagih`} color="#30D158" loading={loading} />
        <MiniKpi icon={Receipt} label="Piutang Belum Lunas" value={formatCurrency(kpi.ar_outstanding)} sub="Piutang berjalan" color="#007AFF" loading={loading} />
        <MiniKpi icon={AlertTriangle} label="Lewat Jatuh Tempo" value={formatCurrency(kpi.overdue_amount)} sub="Lewat jatuh tempo" color="#FF3B30" loading={loading} />
        <MiniKpi icon={Users} label="Pelanggan Saya" value={kpi.customers_count || 0} sub={`${kpi.new_customers || 0} baru bulan ini`} color="#8E8E93" loading={loading} />
        <MiniKpi icon={Target} label="Capaian Target" value={`${target.achievement_pct || 0}%`} sub={formatCurrency(target.amount)} color="#5856D6" loading={loading} />
      </div>

      {/* Target progress */}
      <div className="m-card p-4">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-[13px] font-bold">Capaian Target Penagihan</h3>
          <span className="text-[12px] font-bold tabular-nums text-[#5856D6]">{target.achievement_pct || 0}%</span>
        </div>
        <div className="h-2.5 overflow-hidden rounded-full bg-[#EFF0F2]">
          <div className="h-full rounded-full bg-[#5856D6] transition-all" style={{ width: `${achievement}%` }} />
        </div>
        <div className="mt-2 flex items-center justify-between text-[11px] m-muted">
          <span>Tertagih {formatCurrency(kpi.total_collected)}</span>
          <span>Target {formatCurrency(target.amount)}</span>
        </div>
      </div>

      {/* Rincian komisi per SKU + tren (setara desktop) */}
      {comm.strategy === "per_sku" && (
        <div className="m-card" data-testid="m-home-commission-breakdown">
          <div className="flex items-center justify-between border-b border-[#EFF0F2] px-4 py-2.5">
            <h3 className="text-[13px] font-bold">Rincian Komisi per SKU</h3>
            <span className="text-[10.5px] m-muted">saat tertagih</span>
          </div>
          <div className="px-4 py-1">
            {(comm.breakdown || []).length === 0 ? (
              <p className="py-5 text-center text-[12px] m-muted">Belum ada komisi bulan ini. Komisi terbentuk saat pembayaran masuk.</p>
            ) : comm.breakdown.map((b, i) => (
              <div key={`${b.sku}-${i}`} className="m-list-row" data-testid={`m-home-commission-row-${i}`}>
                <div className="min-w-0 flex-1"><p className="truncate text-[12.5px] font-semibold">{b.name}</p><p className="text-[10.5px] m-muted">{b.category || "—"} · {b.sku} · {Number(b.qty_base || 0).toLocaleString("id-ID")} terbayar</p></div>
                <span className="text-[12px] font-bold tabular-nums text-[#1B7F4B]">{formatCurrency(b.commission)}</span>
              </div>
            ))}
            <div className="flex justify-between py-2 text-[12px] font-bold"><span>Total akrual MTD</span><span className="tabular-nums text-[#1B7F4B]" data-testid="m-home-commission-total">{formatCurrency(comm.mtd_accrual)}</span></div>
          </div>
        </div>
      )}
      <div className="m-card p-4" data-testid="m-home-trend">
        <h3 className="mb-2 text-[13px] font-bold">Tren Komisi (6 bulan)</h3>
        {loading ? <div className="h-28 animate-pulse rounded bg-[#F1F2F4]" /> : history.length > 0 ? (
          <ResponsiveContainer width="100%" height={130}>
            <LineChart data={history} margin={{ top: 4, right: 6, left: -18, bottom: 0 }}>
              <XAxis dataKey="period" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 9 }} tickFormatter={(v) => `${Math.round(v / 1000)}k`} />
              <Tooltip formatter={(v) => [formatCurrency(v), "Insentif"]} />
              <Line type="monotone" dataKey="incentive" stroke="#34C759" strokeWidth={2} dot={{ r: 2 }} />
            </LineChart>
          </ResponsiveContainer>
        ) : <p className="py-6 text-center text-[12px] m-muted">Belum ada riwayat komisi.</p>}
      </div>

      {/* Recent orders */}
      <div className="m-card">
        <div className="flex items-center justify-between border-b border-[#EFF0F2] px-4 py-2.5">
          <h3 className="text-[13px] font-bold">Pesanan Terbaru</h3>
          <button onClick={() => onOpenTab && onOpenTab("orders")} className="inline-flex items-center gap-0.5 text-[12px] font-semibold text-[#0058CC]" data-testid="m-home-see-orders">
            Semua <ChevronRight size={14} />
          </button>
        </div>
        <div className="px-4 py-1">
          {loading ? (
            <div className="py-6 text-center text-[12px] m-muted">Memuat…</div>
          ) : recent.length === 0 ? (
            <div className="py-6 text-center text-[12px] m-muted">Belum ada pesanan.</div>
          ) : recent.slice(0, 5).map((o) => (
            <div key={o.id} className="m-list-row">
              <div className="min-w-0 flex-1">
                <p className="truncate text-[12.5px] font-semibold">{o.number}</p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className={`status-pill ${stageMeta(getStage(o)).cls}`}>{stageMeta(getStage(o)).label}</span>
                  <p className="truncate text-[10.5px] m-muted">{o.customer_name}</p>
                </div>
              </div>
              <span className="text-[12px] font-bold tabular-nums text-[#0058CC]">{formatCurrency(o.grand_total)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Overdue collections */}
      {collections.length > 0 && (
        <div className="m-card">
          <div className="flex items-center gap-2 border-b border-[#EFF0F2] px-4 py-2.5">
            <Banknote size={15} className="text-[#FF3B30]" />
            <h3 className="text-[13px] font-bold">Penagihan (Lewat Tempo)</h3>
          </div>
          <div className="px-4 py-1">
            {collections.slice(0, 5).map((c) => (
              <div key={c.id} className="m-list-row">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[12.5px] font-semibold">{c.name}</p>
                  <p className="text-[10.5px] m-muted">AR {formatCurrency(c.ar_outstanding)}</p>
                </div>
                <span className="text-[12px] font-bold tabular-nums text-[#C0392B]">{formatCurrency(c.overdue_amount)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Pelanggan saya & kredit */}
      {customers.length > 0 && (
        <div className="m-card" data-testid="m-home-customers">
          <div className="flex items-center justify-between border-b border-[#EFF0F2] px-4 py-2.5">
            <div className="flex items-center gap-2"><Users size={15} className="text-[#5856D6]" /><h3 className="text-[13px] font-bold">Pelanggan Saya & Kredit</h3></div>
            {onOpenSub && <button onClick={() => onOpenSub("crm")} className="inline-flex items-center gap-0.5 text-[12px] font-semibold text-[#0058CC]" data-testid="m-home-see-customers">Semua <ChevronRight size={14} /></button>}
          </div>
          <div className="px-4 py-1">
            {customers.slice(0, 6).map((c) => {
              const [label, fg, bg] = CREDIT_TONE[c.status] || CREDIT_TONE.ok;
              return (
                <div key={c.id} className="m-list-row" data-testid={`m-home-customer-${c.id}`}>
                  <div className="min-w-0 flex-1"><p className="truncate text-[12.5px] font-semibold">{c.name}</p><p className="text-[10.5px] m-muted">AR {formatCurrency(c.ar_outstanding)}{c.overdue_amount > 0 ? ` · lewat ${formatCurrency(c.overdue_amount)}` : ""}</p></div>
                  <span className="rounded px-1.5 py-0.5 text-[10px] font-bold" style={{ color: fg, background: bg }}>{label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
