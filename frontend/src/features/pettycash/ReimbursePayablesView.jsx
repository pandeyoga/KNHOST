import { apiErrorText } from "../../utils/apiError";
import { useEffect, useState } from "react";
import { HandCoins, RefreshCw } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { formatCurrency, formatDate } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";
import ResponsiveTable from "../../components/ResponsiveTable";
import { SearchBox } from "../../components/ListControls";
import { can } from "../../config/roles";
import { entityShortById } from "../../utils/entityLabel";
import SettlementCashModal from "./SettlementCashModal";   // PK-24 — pop-up bayar yang sama dengan rincian LPJ

/**
 * Laporan Hutang Reimburse Karyawan (2-1650): saldo terbuka per karyawan + umur sejak LPJ disetujui.
 * PK-24 (IA-05) — data berizin `cash_settlement.view` (dulu `accounting.view`); rincian LPJ = tabel baku dengan kotak
 * cari dan kolom aksi menempel kanan: tombol **Bayar** per baris untuk pemegang `cash_settlement.pay` (pop-up
 * `SettlementCashModal`, sama dengan rincian LPJ).
 */
const BUCKET_TONE = { "0-7": "#15803D", "8-14": "#B45309", "15-30": "#C2410C", ">30": "#B91C1C" };
const BUCKET_CLS = { "0-7": "text-kn-success-text", "8-14": "text-kn-warning-text", "15-30": "text-kn-warning-text", ">30": "text-kn-danger-text" };

export default function ReimbursePayablesView({ currentUser, selectedEntity = "all", entities = [] }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [emp, setEmp] = useState("");
  const [q, setQ] = useState("");
  const [bayar, setBayar] = useState(null);   // baris yang sedang dibayar
  const [toast, setToast] = useState("");
  const canPay = can(currentUser?.permissions, "cash_settlement", "pay");

  async function load() {
    setLoading(true);
    try {
      const params = selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {};
      const r = await axios.get(`${API}/cash-advance-settlements/reimburse-payables`, { params });
      setData(r.data); setError("");
    } catch (e) { setError(apiErrorText(e, "Gagal memuat hutang reimburse.")); } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, [selectedEntity]); // eslint-disable-line react-hooks/exhaustive-deps

  const buckets = data?.buckets || ["0-7", "8-14", "15-30", ">30"];
  const entityName = (id) => entityShortById(entities, id);
  const ada = (data?.items || []).length > 0;
  const cari = q.trim().toLowerCase();
  const items = (data?.items || []).filter((r) => (!emp || r.employee === emp)
    && (!cari || [r.number, r.employee, r.cash_advance_number, r.divisi].some((v) => String(v || "").toLowerCase().includes(cari))));

  return (
    <div data-testid="reimburse-payables-view" className="grid gap-4">
      {toast && <div className="notice-bar success" data-testid="rp-toast"><span>{toast}</span><button onClick={() => setToast("")}>×</button></div>}
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="rp-error" />
      <section className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2 min-w-0">
            <HandCoins size={15} className="text-[#0058CC]" />
            <span className="kicker">Kas & Petty Cash</span>
            <h2 data-testid="rp-title">Hutang Reimburse Karyawan</h2>
          </div>
          <button data-testid="rp-refresh" className="icon-button" onClick={load} aria-label="Muat ulang">
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
        </div>
        <div className="grid gap-3 p-3 sm:grid-cols-2 lg:grid-cols-5">
          <Kpi label="Total Terbuka" value={formatCurrency(data?.total_outstanding || 0)} testId="rp-total" />
          {/* PK-24 — tanpa hutang terbuka, empat kotak umur bernilai 0 tidak ditampilkan (satu angka cukup). */}
          {ada && buckets.map((b) => (
            <Kpi key={b} label={`${b} hari`} value={formatCurrency(data?.aging?.[b] || 0)} tone={BUCKET_TONE[b]}
              testId={`rp-bucket-${b.replace(">", "gt")}`} />
          ))}
        </div>
      </section>

      <section className="section-card">
        <div className="section-head"><h2 className="text-[13px] font-bold">Per Karyawan</h2></div>
        <div className="overflow-x-auto">
          <div className="min-w-[720px]">
            <Head cols={["Karyawan", "LPJ", "Terlama", ...buckets.map((b) => `${b} hari`), "Total"]} />
            {!loading && (data?.by_employee || []).length === 0 && (
              <p data-testid="rp-empty" className="py-10 text-center text-[12px] text-[#6B6B73]">Tidak ada hutang reimburse terbuka.</p>)}
            {(data?.by_employee || []).map((e) => (
              <button key={e.employee} data-testid={`rp-emp-${e.employee}`} onClick={() => setEmp(emp === e.employee ? "" : e.employee)}
                className={`grid w-full ${EMP_GRID} items-center px-3 py-2 text-left text-[12px] border-t border-[#F4F5F7] hover:bg-[#FAFBFC] ${emp === e.employee ? "bg-[#EEF4FF]" : ""}`}>
                <span className="font-semibold truncate">{e.employee}</span>
                <span className="tabular-nums">{e.count}</span>
                <span className="tabular-nums font-semibold" style={{ color: e.oldest_days > 30 ? "#B91C1C" : undefined }}>{e.oldest_days} hari</span>
                {buckets.map((b) => <span key={b} className="tabular-nums text-right">{e.aging[b] ? formatCurrency(e.aging[b]) : "—"}</span>)}
                <span className="tabular-nums text-right font-bold">{formatCurrency(e.outstanding)}</span>
              </button>
            ))}
          </div>
        </div>
      </section>

      {ada && <section className="section-card" data-testid="rp-items-section">
        <div className="section-head">
          <h2 className="text-fs-13 font-bold">Rincian LPJ {emp && `· ${emp}`}</h2>
          <div className="w-full sm:w-auto"><SearchBox value={q} onChange={setQ} placeholder="Cari LPJ, karyawan, PD…" testId="rp-search" /></div>
        </div>
        <div className="section-body grid gap-2">
          <ResponsiveTable testId="rp-items" rows={items} rowKey="id" rowTestId={(r) => `rp-item-${r.id}`} stickyActions
            loading={loading && !data}
            empty={cari || emp ? "Tidak ada LPJ yang cocok dengan pencarian." : "Tidak ada hutang reimburse terbuka."}
            columns={[
              { key: "number", header: "LPJ", mobile: "title", render: (r) => <span className="font-bold text-kn-action whitespace-nowrap">{r.number}</span> },
              { key: "employee", header: "Karyawan", mobile: "subtitle" },
              { key: "pd", header: "Ref PD", priority: 3, render: (r) => r.cash_advance_number || "—" },
              { key: "entity", header: "PT", priority: 4, render: (r) => entityName(r.entity_id) },
              { key: "approved_at", header: "Disetujui", priority: 2, render: (r) => formatDate(r.approved_at) || "—" },
              { key: "days", header: "Umur", align: "right", priority: 1, render: (r) => <span className={`font-semibold whitespace-nowrap ${BUCKET_CLS[r.bucket] || ""}`}>{r.days} hari</span> },
              { key: "amount", header: "Jumlah", align: "right", mobile: "badge", render: (r) => <span className="tabular-nums font-semibold whitespace-nowrap">{formatCurrency(r.amount)}</span> },
            ]}
            actions={canPay ? (r) => (
              <button type="button" data-testid={`rp-pay-${r.id}`} className="btn-primary btn-sm whitespace-nowrap"
                onClick={() => setBayar(r)}><HandCoins size={13} /> Bayar</button>
            ) : undefined}
          />
          <p className="text-fs-12 text-kn-text-2">
            {canPay ? "Bayar per baris, atau lewat rincian LPJ di bagian Pertanggungjawaban."
              : "Pembayaran dicatat pemegang izin bayar kas kecil (Bayar reimburse & terima pengembalian sisa uang muka)."}
          </p>
        </div>
      </section>}

      {bayar && (
        <SettlementCashModal mode="reimburse" entities={entities} onClose={() => setBayar(null)}
          stl={{ id: bayar.id, number: bayar.number, entity_id: bayar.entity_id, employee: bayar.employee, amount: bayar.amount }}
          onDone={() => { setToast(`Kelebihan LPJ ${bayar.number} dibayar ke ${bayar.employee}.`); setBayar(null); load(); }} />
      )}
    </div>
  );
}

const EMP_GRID = "grid-cols-[1.4fr_60px_80px_repeat(4,1fr)_1fr]";

function Head({ cols }) {
  return (
    <div className={`grid ${EMP_GRID} bg-[#FAFBFC] px-3 py-1.5 text-[10px] font-bold uppercase text-[#6B6B73]`}>
      {cols.map((c, i) => <span key={c} className={i >= cols.length - 5 ? "text-right" : ""}>{c}</span>)}
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
