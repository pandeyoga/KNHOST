import { useEffect, useState } from "react";
import { HandCoins, RefreshCw } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { formatCurrency } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";

/** Laporan Hutang Reimburse Karyawan (2-1650): saldo terbuka per karyawan + umur sejak LPJ disetujui. */
const BUCKET_TONE = { "0-7": "#15803D", "8-14": "#B45309", "15-30": "#C2410C", ">30": "#B91C1C" };

export default function ReimbursePayablesView({ selectedEntity = "all", entities = [] }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [emp, setEmp] = useState("");

  async function load() {
    setLoading(true);
    try {
      const params = selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {};
      const r = await axios.get(`${API}/cash-advance-settlements/reimburse-payables`, { params });
      setData(r.data); setError("");
    } catch (e) { setError(e.response?.data?.detail || "Gagal memuat hutang reimburse."); } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, [selectedEntity]); // eslint-disable-line react-hooks/exhaustive-deps

  const buckets = data?.buckets || ["0-7", "8-14", "15-30", ">30"];
  const entityName = (id) => entities.find((e) => e.id === id)?.short_name || id || "—";
  const items = (data?.items || []).filter((r) => !emp || r.employee === emp);

  return (
    <div data-testid="reimburse-payables-view" className="grid gap-4">
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="rp-error" />
      <section className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2 min-w-0">
            <HandCoins size={15} className="text-[#0058CC]" />
            <span className="kicker">Kas & Petty Cash</span>
            <h2 data-testid="rp-title">Hutang Reimburse Karyawan (2-1650)</h2>
          </div>
          <button data-testid="rp-refresh" className="icon-button" onClick={load} aria-label="Muat ulang">
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
        </div>
        <div className="grid gap-3 p-3 sm:grid-cols-2 lg:grid-cols-5">
          <Kpi label="Total Terbuka" value={formatCurrency(data?.total_outstanding || 0)} testId="rp-total" />
          {buckets.map((b) => (
            <Kpi key={b} label={`${b} hari`} value={formatCurrency(data?.aging?.[b] || 0)} tone={BUCKET_TONE[b]}
              testId={`rp-bucket-${b.replace(">", "gt")}`} />
          ))}
        </div>
      </section>

      <section className="section-card">
        <div className="section-head"><h2 className="text-[13px] font-bold">Per Karyawan</h2></div>
        <div className="overflow-x-auto">
          <div className="min-w-[720px]">
            <Head cols={["Karyawan", "LPJ", "Terlama", ...buckets.map((b) => `${b} hr`), "Total"]} />
            {!loading && (data?.by_employee || []).length === 0 && (
              <p data-testid="rp-empty" className="py-10 text-center text-[12px] text-[#6B6B73]">Tidak ada hutang reimburse terbuka.</p>)}
            {(data?.by_employee || []).map((e) => (
              <button key={e.employee} data-testid={`rp-emp-${e.employee}`} onClick={() => setEmp(emp === e.employee ? "" : e.employee)}
                className={`grid w-full ${EMP_GRID} items-center px-3 py-2 text-left text-[12px] border-t border-[#F4F5F7] hover:bg-[#FAFBFC] ${emp === e.employee ? "bg-[#EEF4FF]" : ""}`}>
                <span className="font-semibold truncate">{e.employee}</span>
                <span className="tabular-nums">{e.count}</span>
                <span className="tabular-nums font-semibold" style={{ color: e.oldest_days > 30 ? "#B91C1C" : undefined }}>{e.oldest_days} hr</span>
                {buckets.map((b) => <span key={b} className="tabular-nums text-right">{e.aging[b] ? formatCurrency(e.aging[b]) : "—"}</span>)}
                <span className="tabular-nums text-right font-bold">{formatCurrency(e.outstanding)}</span>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="section-card">
        <div className="section-head"><h2 className="text-[13px] font-bold">Rincian LPJ {emp && `· ${emp}`}</h2></div>
        <div className="overflow-x-auto">
          <div className="min-w-[720px]">
            <Head grid={ITEM_GRID} cols={["LPJ", "Karyawan", "Ref PD", "Entitas", "Disetujui", "Umur", "Jumlah"]} />
            {items.map((r) => (
              <div key={r.id} data-testid={`rp-item-${r.id}`}
                className={`grid ${ITEM_GRID} items-center px-3 py-2 text-[12px] border-t border-[#F4F5F7]`}>
                <span className="font-bold text-[#0058CC]">{r.number}</span>
                <span className="truncate">{r.employee}</span>
                <span className="truncate">{r.cash_advance_number || "—"}</span>
                <span className="truncate">{entityName(r.entity_id)}</span>
                <span>{(r.approved_at || "").slice(0, 10) || "—"}</span>
                <span className="font-semibold" style={{ color: BUCKET_TONE[r.bucket] }}>{r.days} hr</span>
                <span className="tabular-nums text-right font-semibold">{formatCurrency(r.amount)}</span>
              </div>
            ))}
          </div>
        </div>
        <p className="px-3 py-2 text-[11px] text-[#6B6B73]">Bayar lewat detail LPJ (tombol <b>Bayar Reimburse</b>) di tab Pertanggungjawaban.</p>
      </section>
    </div>
  );
}

const EMP_GRID = "grid-cols-[1.4fr_60px_80px_repeat(4,1fr)_1fr]";
const ITEM_GRID = "grid-cols-[1.2fr_1.2fr_1fr_1fr_110px_80px_1fr]";

function Head({ cols, grid = EMP_GRID }) {
  return (
    <div className={`grid ${grid} bg-[#FAFBFC] px-3 py-1.5 text-[10px] font-bold uppercase text-[#6B6B73]`}>
      {cols.map((c, i) => <span key={c} className={i >= cols.length - (grid === EMP_GRID ? 5 : 1) ? "text-right" : ""}>{c}</span>)}
    </div>
  );
}

function Kpi({ label, value, tone, testId }) {
  return (
    <div data-testid={testId} className="metric-card">
      <div className="min-w-0">
        <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p>
        <p className="text-[15px] font-bold tabular-nums truncate" style={tone ? { color: tone } : {}}>{value}</p>
      </div>
    </div>
  );
}
