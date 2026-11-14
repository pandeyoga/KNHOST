/**
 * BudgetView (R6.3 — Budget Control penuh) — Anggaran vs Komitmen vs Realisasi.
 * Dua dimensi: **Akun COA** & **Kategori Beban**. Sumber: /api/finance/budget-vs-actual,
 * CRUD /api/finance/budgets, /api/finance/budget-keys, GET|PUT /api/finance/budget-rules.
 * Komitmen = PO terbuka + LPJ petty cash pending · Realisasi = jurnal GL / LPJ terposting.
 *
 * Fase 3 · P4 (L-03) — "Tambah Anggaran" kini membuka pop-up FormModal (dulu form inline di atas tabel);
 * banner "paling nyaman di desktop" di HP (L-04 kelas C).
 * PK-16 — banner PT (`scope_meta`) di atas KPI; gagal memuat → data dikosongkan.
 * PK-39 — mode gabungan: kolom PT + pita "penjumlahan, belum dieliminasi"; ubah pagu lewat pop-up beralasan,
 * hapus meminta alasan (opsional), tombol Riwayat per baris; mode pemeriksaan dibaca dari Pusat Pengaturan.
 */
import { apiErrorText } from "../../utils/apiError";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import {
  RefreshCw, Target, Wallet, TrendingDown, ClipboardList, Plus, ShieldCheck, AlertTriangle, Info,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import EntityGatedButton from "../../components/EntityGatedButton";   // PK-42 (UX-05)
import DesktopOnlyNotice from "../../components/DesktopOnlyNotice";
import KNSelect from "../../components/KNSelect";
import { todayWib } from "../../utils/formatters";
import {
  FC, yearOptions, compactIDR, entityParam, chartTooltip, fmtPct,
  KpiCard, Panel, EmptyState, formatCurrency,
} from "./financeShared";
import {
  DIM_TABS, BudgetFormModal, BudgetTable, BudgetRulesPanel, AlertsStrip, UnbudgetedPanel, MODE_LABEL,
} from "./BudgetParts";
import { BudgetEditModal, BudgetHistoryModal } from "./BudgetDialogs";
import { can } from "../../config/roles";
import { moneyMessage } from "../../utils/moneyConfirm";
import { askReason } from "../../services/confirmService";
import { useEntityScope } from "../../context/EntityScopeContext";
import EntityScopeBanner from "../../components/EntityScopeBanner";
import { SearchBox } from "../../components/ListControls";
import { TraceNotice, useLedgerTrace } from "./traceLedger";   // MN-T3 — realisasi per akun → buku besar

export default function BudgetView({ selectedEntity, currentUser }) {
  const { entities } = useEntityScope();
  const [year, setYear] = useState(() => todayWib().slice(0, 4));   // tahun berjalan WIB
  const years = useMemo(() => yearOptions(), []);
  const tr = useLedgerTrace({ from: { view: "budget" }, selectedEntity });
  const [tab, setTab] = useState("account");
  const [data, setData] = useState(null);
  const [keys, setKeys] = useState({ accounts: [], categories: [], default_po_account: "" });
  const [rules, setRules] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [formBusy, setFormBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const [editRow, setEditRow] = useState(null);       // PK-39 — pop-up ubah pagu (nominal + alasan)
  const [editBusy, setEditBusy] = useState(false);
  const [editError, setEditError] = useState("");
  const [historyRow, setHistoryRow] = useState(null);  // PK-39 — pop-up "Riwayat Pagu"
  const [search, setSearch] = useState("");             // PK-39 — puluhan baris (gabungan 2× PT) → kotak cari
  const canConfigRules = can(currentUser?.permissions, "budget", "configure");   // Sisir gerbang peran (2026-10-20) — PUT /finance/budget-rules

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [rep, rl] = await Promise.all([
        axios.get(`${API}/finance/budget-vs-actual`, { params: { year, ...entityParam(selectedEntity) } }),
        axios.get(`${API}/finance/budget-rules`, { params: entityParam(selectedEntity) }).catch(() => ({ data: null })),
      ]);
      setData(rep.data || null);
      setRules(rl.data || rep.data?.rules || null);
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat anggaran."));
      setData(null);   // PK-16 (RP-04) — tidak ada angka dari permintaan sebelumnya
    } finally { setLoading(false); }
  }, [year, selectedEntity]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    axios.get(`${API}/finance/budget-keys`, { params: entityParam(selectedEntity) })
      .then((r) => setKeys(r.data || {}))
      .catch(() => { /* opsional */ });
  }, [selectedEntity]);

  const notify = (m) => { setMsg(m); setTimeout(() => setMsg(""), 6000); };

  const tot = data?.totals || {};
  const allRows = data?.rows || [];
  const tabRows = useMemo(() => allRows.filter((r) => r.dimension === tab), [allRows, tab]);
  const rows = useMemo(() => {
    const k = search.trim().toLowerCase();
    if (!k) return tabRows;
    return tabRows.filter((r) => [r.key, r.label, r.entity_name].some((v) => String(v || "").toLowerCase().includes(k)));
  }, [tabRows, search]);
  const dimSum = data?.by_dimension?.[tab] || {};
  const unbudgeted = useMemo(
    () => (data?.unbudgeted_commitments || []).filter((u) => u.dimension === tab), [data, tab]);
  // G1-19 — KPI Komitmen hanya menjumlah baris yang punya pagu; komitmen tanpa anggaran disebut di sub-teks
  // supaya KPI "Rp 0" tidak bertentangan dengan kartu "Komitmen Tanpa Anggaran".
  const unbudgetedTotal = useMemo(() => unbudgeted.reduce((s, u) => s + Number(u.committed || 0), 0), [unbudgeted]);

  // PK-39 — mode gabungan: batang diberi nama PT supaya dua PT dengan akun sama tidak tampak sebagai dua batang kembar.
  const combined = !!data?.is_combined;
  const chartData = useMemo(() => rows.slice(0, 8).map((r) => {
    const base = (r.label || r.key || "").length > 14 ? `${(r.label || r.key).slice(0, 13)}\u2026` : (r.label || r.key);
    return { name: combined && r.entity_name ? `${base} · ${r.entity_name}` : base,
      Anggaran: r.budget, Komitmen: r.committed, Realisasi: r.actual };
  }), [rows, combined]);

  async function submitForm(form) {
    if (!form.key || !form.amount) { setFormError("Pilih akun/kategori dan isi nominal anggaran."); return false; }
    setFormBusy(true); setFormError("");
    try {
      const res = await axios.post(`${API}/finance/budgets`, {
        ...entityParam(selectedEntity), year: Number(year), month: Number(form.month),
        dimension: tab, key: form.key, amount: Number(form.amount), note: form.note,
      });
      notify(`Anggaran ${res.data?.label || form.key} tersimpan (${formatCurrency(res.data?.amount)}).`);
      setShowForm(false); await load();
      return true;
    } catch (e) {
      setFormError(apiErrorText(e, "Gagal menyimpan anggaran."));
      return false;
    } finally { setFormBusy(false); }
  }

  async function saveEdit(row, amount, reason) {
    setEditBusy(true); setEditError("");
    try {
      await axios.patch(`${API}/finance/budgets/${row.id}`, { amount: Number(amount), reason });
      setEditRow(null); notify("Nominal anggaran diperbarui."); await load();
    } catch (e) { setEditError(apiErrorText(e, "Gagal memperbarui anggaran.")); }
    finally { setEditBusy(false); }
  }

  // PK-13 (FY-17) — hapus pagu bertanya dulu (nominal pagu baris & PT pagu). PK-39 — alasan (opsional) ke riwayat.
  async function removeBudget(row) {
    const reason = await askReason({
      title: `Hapus anggaran ${row.label || row.key}?`,
      message: moneyMessage({
        effect: "Pagu baris ini dihapus. Realisasi tidak berubah, tetapi perbandingan anggarannya hilang.",
        amount: row.budget, entityId: row.entity_id || selectedEntity, entities }),
      reasonLabel: "Alasan perubahan (opsional)", reasonRequired: false,
      confirmLabel: "Hapus Anggaran", danger: true, testId: "budget-delete-confirm",
    });
    if (reason === null) return;
    try {
      await axios.delete(`${API}/finance/budgets/${row.id}`, { params: reason.trim() ? { reason: reason.trim() } : {} });
      notify("Anggaran dihapus."); await load();
    } catch (e) { setError(apiErrorText(e, "Gagal menghapus anggaran.")); }
  }

  async function saveRules(patch) {
    try {
      const res = await axios.put(`${API}/finance/budget-rules`, { ...entityParam(selectedEntity), ...patch });
      setRules(res.data);
      notify("Sakelar anggaran disimpan.");
      await load();
      return true;
    } catch (e) {
      setError(apiErrorText(e, "Gagal menyimpan kebijakan anggaran."));
      return false;
    }
  }

  return (
    <div data-testid="budget-view">
      <DesktopOnlyNotice testId="budget-desktop-notice" what="Anggaran vs Realisasi" />
      <EntityScopeBanner meta={data?.scope_meta} />
      {/* KPI */}
      {/* Cek layar 14 Nov — lima kartu sebaris hanya di ≥1536 px; di 1024–1535 px 3+2 supaya angka rupiah utuh sebaris. */}
      <div className="grid grid-cols-2 md:grid-cols-3 2xl:grid-cols-5 gap-3 mb-3">
        <KpiCard testId="budget-kpi-total" label={`Anggaran ${year}`} value={formatCurrency(tot.budget)}
          icon={Target} accent={FC.purple} sub={`${allRows.length} baris anggaran`} />
        <KpiCard testId="budget-kpi-commitment" label="Komitmen (PO/LPJ)" value={formatCurrency(tot.commitment)}
          icon={ClipboardList} accent={FC.amber} tone="text-[#C77700]"
          sub={unbudgetedTotal > 0
            ? `belanja terikat dalam pagu · + ${formatCurrency(unbudgetedTotal)} di luar pagu`
            : "belanja terikat belum realisasi"} />
        <KpiCard testId="budget-kpi-actual" label="Realisasi" value={formatCurrency(tot.actual)}
          icon={Wallet} accent={FC.cash} tone="text-[#0058CC]" sub={`Terpakai ${fmtPct(tot.used_pct)}`} />
        <KpiCard testId="budget-kpi-remaining" label="Sisa (Tersedia)" value={formatCurrency(tot.remaining)}
          icon={TrendingDown} accent={(tot.remaining ?? 0) >= 0 ? FC.revenue : FC.expense}
          tone={(tot.remaining ?? 0) >= 0 ? "text-[#1B7F4B]" : "text-[#C0392B]"}
          sub={`Anggaran − komitmen − realisasi (${fmtPct(tot.spent_pct)})`} />
        <KpiCard testId="budget-kpi-over" label="Pos Over-Budget" value={`${tot.over_count || 0}`}
          icon={AlertTriangle} accent={FC.expense}
          tone={(tot.over_count || 0) > 0 ? "text-[#C0392B]" : "text-[#1B7F4B]"}
          sub={`Bila melampaui: ${rules?.mode_label || MODE_LABEL[rules?.mode || "warn"]}`} />
      </div>

      {/* Toolbar: tahun + tab dimensi + aksi */}
      <div className="rounded-lg border border-[#EFF0F2] p-3 mb-3 bg-[#FCFCFD] flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-[10px] font-bold uppercase text-[#8E8E93] mb-1">Tahun</label>
          <div className="w-[110px]">
            <KNSelect data-testid="budget-year" className="field py-1.5 text-[12px]" value={year}
              onValueChange={setYear} options={years} />
          </div>
        </div>
        <div>
          <label className="block text-[10px] font-bold uppercase text-[#8E8E93] mb-1">Dimensi Anggaran</label>
          <div className="flex items-center gap-1.5" data-testid="budget-dim-tabs">
            {DIM_TABS.map((t) => (
              <button key={t.value} data-testid={`budget-tab-${t.value}`}
                onClick={() => { setTab(t.value); setShowForm(false); }}
                className={`text-[11.5px] font-semibold rounded-md px-3 py-1.5 border transition-colors ${
                  tab === t.value ? "bg-[#F3EAFB] border-[#D9C4EC] text-[#6B219A]"
                    : "bg-white border-[#EFF0F2] text-[#6B6B73] hover:border-[#D9C4EC]"}`}>
                {t.label}
              </button>
            ))}
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <EntityGatedButton selectedEntity={selectedEntity} what="menambah anggaran" data-testid="budget-add-toggle"
            onClick={() => { setFormError(""); setShowForm(true); }} className="primary-button">
            <Plus size={13} /> Tambah Anggaran
          </EntityGatedButton>
          <button data-testid="budget-refresh" className="icon-button" onClick={load} aria-label="Muat ulang" title="Muat ulang">
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {showForm && (
        <BudgetFormModal open dimension={tab} keys={keys} busy={formBusy} error={formError}
          onSubmit={submitForm} onCancel={() => setShowForm(false)} />
      )}

      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="budget-error" />
      {msg && (
        <div className="notice-bar success mb-3" data-testid="budget-notice">
          <span>{msg}</span><button onClick={() => setMsg("")} aria-label="Tutup">×</button>
        </div>
      )}

      <BudgetRulesPanel rules={rules} isAdmin={canConfigRules} onSave={saveRules}
        defaultAccount={keys.default_po_account} />

      <AlertsStrip alerts={data?.alerts || []} showEntity={!!data?.is_combined} />

      {data?.is_combined && (   /* PK-39 (N3, K-15) — angka gabungan berlabel belum dieliminasi */
        <div className="notice-bar info mb-3" role="note" data-testid="budget-combined-note">
          <Info size={14} className="shrink-0" /><span>{data.combined_note}</span>
        </div>
      )}

      {loading ? (
        <div className="h-[280px] bg-[#F5F5F7] rounded animate-pulse" data-testid="budget-loading" />
      ) : !data && error ? null /* PK-16 — gagal memuat: hanya galat + "Coba lagi", bukan "belum ada anggaran" */
        : tabRows.length === 0 ? (
        <Panel title={`Anggaran vs Realisasi — ${DIM_TABS.find((t) => t.value === tab)?.label}`} icon={Target}>
          <EmptyState icon={Target} title="Belum ada anggaran untuk dimensi & tahun ini"
            hint="Klik ‘Tambah Anggaran’ untuk menetapkan pagu per akun COA atau per kategori beban."
            testId="budget-empty" />
        </Panel>
      ) : (
        <>
          <Panel title={`Anggaran · Komitmen · Realisasi (${DIM_TABS.find((t) => t.value === tab)?.label})`}
            icon={Target} testId="budget-chart" className="mb-3"
            actions={<span className="text-[10.5px] text-[#8E8E93]">
              Pagu {formatCurrency(dimSum.budget)} · Terikat {formatCurrency(dimSum.committed)} ·
              Realisasi {formatCurrency(dimSum.actual)} · Sisa {formatCurrency(dimSum.remaining)}
            </span>}>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartData} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={FC.grid} />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-12} textAnchor="end" height={50} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={compactIDR} width={52} />
                <Tooltip formatter={(v, n) => [formatCurrency(v), n]} {...chartTooltip} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="Anggaran" fill={FC.purple} radius={[4, 4, 0, 0]} maxBarSize={18} />
                <Bar dataKey="Komitmen" fill={FC.amber} radius={[4, 4, 0, 0]} maxBarSize={18} />
                <Bar dataKey="Realisasi" fill={FC.cash} radius={[4, 4, 0, 0]} maxBarSize={18} />
              </BarChart>
            </ResponsiveContainer>
          </Panel>

          <Panel title="Rincian Anggaran" icon={ClipboardList} testId="budget-table-panel"
            actions={<SearchBox value={search} onChange={setSearch} placeholder="Cari akun / kategori / PT…"
              testId="budget-search" />}>
            {rows.length === 0 ? (
              <p className="py-4 text-center text-fs-12 text-kn-text-2" data-testid="budget-search-empty">
                Tidak ada pagu yang cocok dengan “{search}”.</p>
            ) : (
              <>
              <TraceNotice notice={tr.notice} onDismiss={tr.clear} testId="budget-trace-notice" />
              <BudgetTable rows={rows} showEntity={combined}
                onTrace={tab === "account" && tr.enabled
                  ? (r) => tr.trace(r.key, { start: `${year}-01-01`, end: `${year}-12-31` }, r.entity_id || "", r.entity_name || "") : null}
                onEdit={(r) => { setEditError(""); setEditRow({ ...r, year: Number(year) }); }}
                onHistory={(r) => setHistoryRow({ ...r, year: Number(year) })} onDelete={removeBudget} />
              </>
            )}
          </Panel>
        </>
      )}

      <UnbudgetedPanel items={unbudgeted} dimension={tab} keys={keys} showEntity={!!data?.is_combined} />

      {editRow && (
        <BudgetEditModal row={editRow} busy={editBusy} error={editError} onSubmit={saveEdit}
          onCancel={() => setEditRow(null)} />
      )}
      {historyRow && <BudgetHistoryModal row={historyRow} onClose={() => setHistoryRow(null)} />}

      <p className="mt-2 text-fs-12 text-kn-text-2 flex items-start gap-1.5">
        <ShieldCheck size={12} className="mt-0.5 shrink-0" />
        <span>
          {/* Cek layar 14 Nov — arti Komitmen/Realisasi sudah tertulis di bawah tabel; di sini hanya yang belum. */}
          Nilai PO = DPP; PO tanpa tanda anggaran masuk akun {keys.default_po_account || "persediaan"}.
          <b> Sisa</b> = Anggaran − Komitmen − Realisasi. Tiap PT dibandingkan dengan pagunya sendiri; semua angka
          diturunkan langsung dari sumber (tanpa cache).
        </span>
      </p>
    </div>
  );
}
