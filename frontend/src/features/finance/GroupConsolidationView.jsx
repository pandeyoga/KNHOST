/**
 * GroupConsolidationView (FINANCE) — Konsolidasi Grup + Eliminasi Intercompany.
 * Matriks Per-PT + Eliminasi + Konsolidasi untuk Laba-Rugi (tahun) & Neraca (as_of).
 * Eliminasi manual + auto-deteksi kandidat intercompany.
 * Sumber: /api/finance/consolidation/*. Gaya ikut finance existing.
 *
 * Fase 3 · P4 — D-10: angka laba-rugi di sini DIBERI LABEL "setelah eliminasi antar-PT" (beda dengan Laporan
 * Keuangan per PT/gabungan yang belum dieliminasi). L-01: pil ungu tab → PageTabs (testid `cons-tab-*` tetap).
 * L-07: matriks → `.data-table`. L-03/L-08: pop-up & bilah alat di GroupConsolidationParts.jsx. L-04 kelas C:
 * DesktopOnlyNotice di HP.
 */
import { apiErrorText } from "../../utils/apiError";
import KNDatePicker from "@/components/KNDatePicker";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  RefreshCw, Building2, Scale, TrendingUp, Layers, X, CheckCircle2, AlertTriangle, ScissorsLineDashed,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import KNSelect from "../../components/KNSelect";
import PageTabs from "../../components/PageTabs";
import DesktopOnlyNotice from "../../components/DesktopOnlyNotice";
import { formatCurrency, formatDate } from "../../utils/formatters";
import { askConfirm, askReason } from "@/services/confirmService";
import { stripInternalCodes } from "../../utils/cleanText";
import { EliminationsPanel, EliminationModal, DetectModal } from "./GroupConsolidationParts";

const NOW = new Date();
const YEARS = Array.from({ length: 6 }, (_, i) => {
  const y = String(NOW.getFullYear() - i);
  return { value: y, label: y };
});
const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

const PNL_ROWS = [
  { key: "revenue", label: "Pendapatan" },
  { key: "cogs", label: "HPP" },
  { key: "opex", label: "Beban Operasional" },
  { key: "expense", label: "Total Beban", muted: true },
  { key: "gross_profit", label: "Laba Kotor", strong: true },
  { key: "net_income", label: "Laba Bersih", strong: true },
];
const BS_ROWS = [
  { key: "assets", label: "Total Aset", strong: true },
  { key: "liabilities", label: "Total Kewajiban" },
  { key: "equity", label: "Total Ekuitas" },
];

const TABS = [
  { id: "pnl", label: "Laba-Rugi", icon: TrendingUp },
  { id: "bs", label: "Neraca", icon: Scale },
  { id: "elim", label: "Eliminasi", icon: ScissorsLineDashed },
];

export default function GroupConsolidationView({ entities = [] }) {
  const [tab, setTab] = useState("pnl");
  const [year, setYear] = useState(String(NOW.getFullYear()));
  const [asOf, setAsOf] = useState(ymd(NOW));
  const [data, setData] = useState(null);
  const [elims, setElims] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [modal, setModal] = useState(null); // {lines?, name?}
  const [detect, setDetect] = useState(null); // ic-candidates result
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [s, e] = await Promise.all([
        axios.get(`${API}/finance/consolidation/summary`, { params: { year, as_of: asOf } }),
        axios.get(`${API}/finance/consolidation/eliminations`),
      ]);
      setData(s.data); setElims(Array.isArray(e.data) ? e.data : []);
    } catch (err) {
      setError(apiErrorText(err, "Gagal memuat konsolidasi."));
    } finally { setLoading(false); }
  }, [year, asOf]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    axios.get(`${API}/gl/accounts`).then((r) => {
      const opts = (r.data || [])
        .filter((a) => !/-0000$/.test(a.code) && !/-\d000$/.test(a.code))
        .map((a) => ({ value: a.code, label: `${a.code} — ${a.name}` }));
      setAccounts(opts);
    }).catch(() => {});
  }, []);

  const removeElim = async (el) => {
    // Berdampak UANG (laporan konsolidasi grup) → alasan wajib & ikut tercatat di audit.
    const reason = await askReason({
      title: `Hapus entri eliminasi "${el.name}"?`,
      message: "Laporan konsolidasi grup akan berubah karena pasangan transaksi ini tidak "
        + "lagi dieliminasi.",
      reasonLabel: "Alasan penghapusan",
      confirmLabel: "Hapus Eliminasi",
      danger: true,
      testId: "elim-delete-confirm",
    });
    if (reason === null) return;
    setBusy(true); setError("");
    try { await axios.delete(`${API}/finance/consolidation/eliminations/${el.id}`, { params: { reason } }); setNotice("Eliminasi dihapus."); load(); }
    catch (e) { setError(apiErrorText(e, "Gagal menghapus eliminasi.")); }
    finally { setBusy(false); }
  };

  const runDetect = async () => {
    setBusy(true); setError("");
    try {
      const r = await axios.get(`${API}/finance/consolidation/ic-candidates`, { params: { as_of: asOf } });
      setDetect(r.data);
    } catch (e) { setError(apiErrorText(e, "Gagal mendeteksi kandidat.")); }
    finally { setBusy(false); }
  };

  /**
   * FASE G-6 (US7) — sinkronkan eliminasi transaksi antar-PT.
   *
   * Eliminasi ini SUDAH dijaga otomatis setiap transaksi antar-PT dikonfirmasi /
   * dilunasi / dibatalkan. Tombol ini untuk **data lama (backfill)** dan untuk
   * memastikan angkanya masih pas — laporan ini kehilangan artinya kalau margin
   * antar-PT masih ikut terhitung sebagai laba grup.
   */
  const syncG6 = async () => {
    if (!(await askConfirm({
      title: "Sinkronkan eliminasi antar-PT?",
      message: `Entri eliminasi otomatis per ${formatDate(asOf)} dibuat/diperbarui/dihapus mengikuti transaksi antar-PT. `
        + "Laporan konsolidasi grup ikut berubah; jurnal per-PT tidak tersentuh.",
      confirmLabel: "Sinkronkan",
    }))) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const r = await axios.post(`${API}/consolidation/sync-g6`, {}, { params: { as_of: asOf } });
      const d = r.data || {};
      setNotice(
        `Eliminasi antar-PT tersinkron: ${d.created || 0} baru · ` +
        `${d.updated || 0} diperbarui · ${d.removed || 0} dihapus · ` +
        `${d.skipped_existing || 0} sudah pas — dari ${d.pairs_seen || 0} transaksi antar-PT.`);
      load();
    } catch (e) {
      setError(stripInternalCodes(e.response?.data?.detail) || "Gagal menyinkronkan eliminasi antar-PT.");
    } finally { setBusy(false); }
  };

  /** M-3 — eliminasi dari PASANGAN jurnal transfer antar-PT lama (at-cost). */
  const syncPairs = async () => {
    if (!(await askConfirm({
      title: "Sinkronkan eliminasi dari pasangan jurnal?",
      message: `Entri eliminasi baru dibuat dari pasangan jurnal transfer antar-PT lama (per ${formatDate(asOf)}). `
        + "Laporan konsolidasi grup ikut berubah; jurnal per-PT tidak tersentuh.",
      confirmLabel: "Sinkronkan",
    }))) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const r = await axios.post(`${API}/finance/consolidation/eliminations/sync-from-pairs`,
                                 {}, { params: { as_of: asOf } });
      const d = r.data || {};
      setNotice(
        `Eliminasi pasangan jurnal: ${d.created || 0} baru · ` +
        `${d.skipped_existing || 0} sudah ada — dari ${d.pairs_seen || 0} pasangan.`);
      load();
    } catch (e) {
      setError(apiErrorText(e, "Gagal menyinkronkan eliminasi pasangan jurnal."));
    } finally { setBusy(false); }
  };

  const useCandidatesAsDraft = () => {
    const lines = (detect?.suggested_lines || []).map((l) => ({
      account_code: l.account_code, debit: l.debit || 0, credit: l.credit || 0, description: l.description || "",
    }));
    setDetect(null);
    setModal({ name: "Eliminasi antar-PT (dari deteksi otomatis)", lines: lines.length ? lines : undefined });
  };

  const entityCols = data?.entities || [];
  const colClass = "text-right tabular-nums whitespace-nowrap";

  const renderMatrix = (rows) => (
    <div className="table-wrap" data-testid={`cons-matrix-${tab}`}>
      <table className="data-table">
        <thead>
          <tr>
            <th className="sticky left-0 z-[2]">Pos</th>
            {entityCols.map((e) => <th key={e.entity_id} className="text-right">{e.short_name}</th>)}
            <th className="text-right !text-[#C0392B]">Eliminasi</th>
            <th className="text-right !text-[#0058CC]" title="Σ per-PT + eliminasi antar-PT">Konsolidasi</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const elimV = data?.elimination?.[row.key] ?? 0;
            const consV = data?.consolidated?.[row.key] ?? 0;
            return (
              <tr key={row.key} data-testid={`cons-row-${row.key}`} className={row.strong ? "bg-[#F5F8FF] font-bold" : row.muted ? "bg-[#FCFCFD]" : ""}>
                <td className={`sticky left-0 ${row.strong ? "bg-[#F5F8FF] font-bold" : "bg-white"} text-[#1C1C1E]`}>{row.label}</td>
                {entityCols.map((e) => <td key={e.entity_id} className={`${colClass} text-[#3C3C43] tabular-nums`}>{formatCurrency(e[row.key])}</td>)}
                <td className={`${colClass} tabular-nums ${Math.abs(elimV) > 0.005 ? "text-[#C0392B]" : "text-[#C9C9CE]"}`} data-testid={`cons-elim-${row.key}`}>{formatCurrency(elimV)}</td>
                <td className={`${colClass} font-bold text-[#0058CC] tabular-nums`} data-testid={`cons-consolidated-${row.key}`}>{formatCurrency(consV)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );

  return (
    <div data-testid="group-consolidation-view">
      <DesktopOnlyNotice testId="cons-desktop-notice" what="Konsolidasi grup" />
      <div className="section-card">
        <div className="section-head flex-wrap gap-2">
          <PageTabs testId="cons-tab" ariaLabel="Laporan konsolidasi" value={tab} onChange={setTab}
            tabs={TABS.map((t) => ({ key: t.id, label: t.label, icon: t.icon, count: t.id === "elim" ? elims.length : undefined }))} />
          <div className="flex items-center gap-2 ml-auto">
            {tab === "pnl" && <div className="w-[110px]"><KNSelect data-testid="cons-year" className="field py-1.5 text-[12px]" value={year} onValueChange={setYear} options={YEARS} /></div>}
            {tab !== "pnl" && <KNDatePicker data-testid="cons-asof" className="w-[170px] text-[12px]" clearable={false} value={asOf} onChange={setAsOf} />}
            <button data-testid="cons-refresh" className="icon-button" onClick={load} aria-label="Refresh"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
          </div>
        </div>

        <div className="section-body">
          <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="cons-error" />
          {notice && (
            <div data-testid="cons-notice" className="mb-3 rounded-md bg-[#E6F6EC] border border-[#BDE5CC] text-[#1B7F4B] text-[12px] px-3 py-2 flex items-center gap-2">
              <CheckCircle2 size={14} />{notice}<button className="ml-auto" onClick={() => setNotice("")}><X size={13} /></button>
            </div>
          )}

          {loading ? (
            <div className="h-64 bg-[#F5F5F7] rounded animate-pulse" data-testid="cons-loading" />
          ) : tab === "pnl" ? (
            <>
              <div className="flex flex-wrap items-center gap-2 mb-2 text-[11px] text-[#8E8E93]" data-testid="cons-pnl-caption"><Layers size={13} className="text-[#0058CC]" /> Laba-Rugi Konsolidasi Tahun {year} — {entityCols.length} entitas · <b className="text-[#3C3C43]">kolom Konsolidasi = setelah eliminasi antar-PT</b></div>
              {renderMatrix(PNL_ROWS)}
            </>
          ) : tab === "bs" ? (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                <div className="flex items-center gap-2 text-[11px] text-[#8E8E93]"><Building2 size={13} className="text-[#0058CC]" /> Neraca Konsolidasi per {formatDate(asOf)} · setelah eliminasi antar-PT</div>
                <span data-testid="cons-balanced" className={`text-[11px] font-bold rounded-full px-2 py-0.5 inline-flex items-center gap-1 ${data?.balanced ? "bg-[#E6F6EC] text-[#1B7F4B]" : "bg-[#FDEDE7] text-[#C0392B]"}`}>
                  {data?.balanced ? <CheckCircle2 size={11} /> : <AlertTriangle size={11} />}{data?.balanced ? "Seimbang" : "Tidak Seimbang"}
                </span>
              </div>
              {renderMatrix(BS_ROWS)}
            </>
          ) : (
            <EliminationsPanel elims={elims} onAdd={() => setModal({})} onDetect={runDetect}
                               onDelete={removeElim} onSyncG6={syncG6} onSyncPairs={syncPairs} busy={busy} />
          )}
          <p className="mt-2 text-[11px] text-[#9A9BA3]">Konsolidasi = Σ Per-PT + Eliminasi. Eliminasi bersifat adjustment grup (tidak mengubah jurnal per-PT). Neraca konsolidasi tetap seimbang bila entri eliminasi balanced.</p>
        </div>
      </div>

      {modal && (
        <EliminationModal initial={modal} accounts={accounts} entities={entities}
          onClose={() => setModal(null)} onSaved={() => { setModal(null); load(); setNotice("Eliminasi tersimpan."); }} />
      )}
      {detect && (
        <DetectModal detect={detect} onClose={() => setDetect(null)} onUse={useCandidatesAsDraft} />
      )}
    </div>
  );
}
