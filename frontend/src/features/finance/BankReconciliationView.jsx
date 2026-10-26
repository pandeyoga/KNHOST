/**
 * FASE G-8 — BankReconciliationView: Rekonsiliasi Bank (parser multi-bank, skor
 * berbobot, split 1:N & N:1, aturan pembelajaran, titipan dana belum teridentifikasi).
 *
 * Akses: izin `cash` (admin/manager). Sumber data: /api/bank-reconciliation/*.
 * Layar ini TIDAK mengubah jurnal terposting; satu-satunya jalur yang menerbitkan
 * jurnal baru adalah TITIPAN DANA & alokasinya (karena di situ ada uang nyata).
 *
 * Fase 4 · R2 — L-02: kepala halaman (ikon + h2 langsung di latar) → `PageHeader`; tab & isi dalam `.section-card`.
 * L-01: tab buatan sendiri → `PageTabs` (`recon-tab-*` tetap); saringan status (tab bertingkat ke-3) →
 * `FilterChips` (`recon-filter-status-*` tetap); jumlah baris di posisi tetap (tidak melompat saat "Bersihkan filter"
 * muncul). L-03: panel impor yang diselipkan → pop-up `ReconImportPanel` (FormModal).
 */
import KNDatePicker from "@/components/KNDatePicker";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  RefreshCw, Landmark, Wand2, Upload, CheckCircle2, AlertTriangle, PiggyBank,
  Sparkles, FileCog, ListChecks, FilterX,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import { apiErrorText } from "../../utils/apiError";
import { KNSelect } from "../../components/KNSelect";
import FilterChips from "../../components/FilterChips";
import PageTabs from "../../components/PageTabs";
import { PageHeader } from "../../components/ListPageParts";
import { formatCurrency } from "../../utils/formatters";
import ReconImportPanel from "./bank/ReconImportPanel";
import ReconLinesTable from "./bank/ReconLinesTable";
import ReconMatchModal from "./bank/ReconMatchModal";
import ReconHoldingPanel from "./bank/ReconHoldingPanel";
import DesktopOnlyNotice from "../../components/DesktopOnlyNotice";

const TABS = [
  { id: "lines", label: "Mutasi & Pencocokan", icon: ListChecks },
  { id: "holding", label: "Dana Titipan", icon: PiggyBank },
];

// Status baris mutasi (SSOT status ada di backend: unmatched|matched|ignored|holding).
const STATUS_FILTERS = [
  { value: "", label: "Semua status" },
  { value: "unmatched", label: "Perlu keputusan" },
  { value: "matched", label: "Tercocok" },
  { value: "holding", label: "Dititipkan" },
  { value: "ignored", label: "Diabaikan" },
];

export default function BankReconciliationView() {
  const [accounts, setAccounts] = useState([]);
  const [acctId, setAcctId] = useState("");
  const [tab, setTab] = useState("lines");
  const [lines, setLines] = useState([]);
  const [summary, setSummary] = useState(null);
  const [holding, setHolding] = useState(null);
  const [rules, setRules] = useState([]);
  const [formats, setFormats] = useState([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [showImport, setShowImport] = useState(false);
  const [matchFor, setMatchFor] = useState(null);
  // Penutupan FASE G-8 — rekening koran nyata bisa ratusan baris per bulan. Backend sudah
  // menerima filter status & periode sejak awal, tetapi layar belum memakainya sehingga
  // pengguna harus memindai semuanya dengan mata. Filter ini juga dipakai ringkasan supaya
  // angka kartu selalu bercerita tentang periode yang sedang dilihat.
  const [fStatus, setFStatus] = useState("");
  const [fStart, setFStart] = useState("");
  const [fEnd, setFEnd] = useState("");

  const notify = (m) => { setMsg(m); setTimeout(() => setMsg(""), 5000); };
  // KN-G9-ERR-SILENT — semua penolakan backend dinormalkan ke KALIMAT sebelum
  // ditampilkan, supaya tidak ada objek axios mentah yang masuk ke <ErrorNotice>.
  const fail = (e) => setErr(apiErrorText(e));

  const loadAccounts = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/bank-accounts`);
      const list = Array.isArray(r.data) ? r.data : (r.data?.items || []);
      setAccounts(list);
      setAcctId((cur) => cur || (list[0]?.id ?? ""));
    } catch (e) { fail(e); }
  }, []);

  const loadData = useCallback(async () => {
    if (!acctId) return;
    setLoading(true); setErr("");
    try {
      const period = { ...(fStart ? { start: fStart } : {}), ...(fEnd ? { end: fEnd } : {}) };
      const [ln, sm, hd, rl, fm] = await Promise.all([
        axios.get(`${API}/bank-reconciliation/lines`,
          { params: { bank_account_id: acctId, ...period,
            ...(fStatus ? { status: fStatus } : {}) } }),
        axios.get(`${API}/bank-reconciliation/summary`,
          { params: { bank_account_id: acctId, ...period } }),
        axios.get(`${API}/bank-reconciliation/holding`, { params: { bank_account_id: acctId } }),
        axios.get(`${API}/bank-reconciliation/rules`, { params: { bank_account_id: acctId } }),
        axios.get(`${API}/bank-reconciliation/formats`),
      ]);
      setLines(Array.isArray(ln.data) ? ln.data : []);
      setSummary(sm.data);
      setHolding(hd.data);
      setRules(Array.isArray(rl.data) ? rl.data : []);
      setFormats(Array.isArray(fm.data) ? fm.data : []);
    } catch (e) { fail(e); }
    finally { setLoading(false); }
  }, [acctId, fStatus, fStart, fEnd]);

  useEffect(() => { loadAccounts(); }, [loadAccounts]);
  useEffect(() => { loadData(); }, [loadData]);

  async function doAutoMatch() {
    setBusy("auto"); setErr("");
    try {
      const r = await axios.post(`${API}/bank-reconciliation/auto-match`,
        { bank_account_id: acctId });
      const d = r.data || {};
      notify(`Pencocokan otomatis: ${d.matched} tertaut (skor ≥ ${d.auto_min}), `
        + `${d.suggested} usulan (skor ≥ ${d.suggest_min}), ${d.unmatched_lines} baris tersisa.`);
      await loadData();
    } catch (e) { fail(e); } finally { setBusy(""); }
  }

  async function lineAction(lineId, action, body, successMsg) {
    setBusy(lineId + action); setErr("");
    try {
      await axios.post(`${API}/bank-reconciliation/lines/${lineId}/${action}`, body || {});
      notify(successMsg || "Perubahan tersimpan.");
      setMatchFor(null);
      await loadData();
      return true;
    } catch (e) { fail(e); return false; } finally { setBusy(""); }
  }

  const suggestedRules = useMemo(
    () => rules.filter((r) => r.status === "suggested").length, [rules]);
  // UAT 24 Okt (audit UI tahap 2) — G1-18: akun nonaktif dulu tercampur tanpa tanda (dua "TEST_Bank Updated" kembar).
  // Aktif dulu, nonaktif diberi label & ditaruh paling bawah; nomor rekening membedakan nama kembar.
  const acctOptions = useMemo(
    () => [...accounts]
      .sort((a, b) => Number(a.is_active === false) - Number(b.is_active === false))
      .map((a) => ({
        value: a.id,
        label: [a.name || a.bank_name || a.id, a.account_number].filter(Boolean).join(" · ")
          + (a.is_active === false ? " (nonaktif)" : ""),
      })),
    [accounts]);
  const filterOn = !!(fStatus || fStart || fEnd);
  // Audit UI 24 Okt (062): sebelum ada mutasi diimpor, "Selisih rekening vs buku" dulu
  // menampilkan −(seluruh saldo buku) berwarna merah — menyesatkan. Tanpa mutasi rekening,
  // selisih belum bisa dihitung → tampil "—" netral dengan petunjuk impor.
  const noStatement = !!summary && !Number(summary.statement?.lines || 0);

  return (
    <div className="view-container" data-testid="bank-reconciliation-view">
      {/* Fase 3 · P4 (L-04 kelas C) — rekonsiliasi = pekerjaan akuntansi: pemberitahuan desktop di HP. */}
      <DesktopOnlyNotice testId="recon-desktop-notice" what="Rekonsiliasi Bank" />
      <PageHeader icon={Landmark} title="Rekonsiliasi Bank" testId="recon-head"
        subtitle={"Baca mutasi rekening koran bank apa pun, cocokkan dengan transaksi kas (buku), "
          + "dan tampung dana yang belum teridentifikasi tanpa mengubah jurnal."}
        actions={(
          <>
            <div className="w-full sm:w-[240px]">
              <KNSelect data-testid="recon-account-select" value={acctId}
                onValueChange={setAcctId} options={acctOptions} placeholder="Pilih akun bank" />
            </div>
            <button type="button" data-testid="recon-refresh" className="secondary-button" onClick={loadData}>
              <RefreshCw size={14} className={loading ? "spin" : ""} /> Muat ulang
            </button>
          </>
        )} />

      {err && <ErrorNotice message={err} onRetry={loadData} onDismiss={() => setErr("")}
        testId="recon-error" />}
      {msg && (
        <div className="notice-bar success !mb-0" data-testid="recon-notice">
          <CheckCircle2 size={14} /> {msg}
        </div>
      )}

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3" data-testid="recon-summary">
          <div className="stat-card">
            <p className="stat-label">Rekening (bersih)</p>
            <p className="stat-value tabular-nums whitespace-nowrap">{noStatement ? "—" : formatCurrency(summary.statement.net)}</p>
            <p className="text-[11px] text-[#8E8E93]">{noStatement ? "belum ada mutasi diimpor" : `${summary.statement.lines} baris mutasi`}</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Buku (bersih)</p>
            <p className="stat-value tabular-nums whitespace-nowrap">{formatCurrency(summary.book.net)}</p>
            {/* K-02 (26 Okt) — kolam "buku" di sini ikut memuat transaksi kas TANPA rekening berjenis kas sama, jadi bisa
                lebih banyak dari jumlah transaksi di kartu Rekening & Saldo. Disebut terang. */}
            <p className="text-[11px] text-[#8E8E93]" data-testid="recon-unmatched-book"
              title="Transaksi buku rekening ini + transaksi kas tanpa rekening berjenis kas sama yang belum dicocokkan ke mutasi bank.">
              {summary.unmatched_book_txns} transaksi belum tertaut · termasuk kas tanpa rekening
            </p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Tercocok</p>
            <p className="stat-value text-[#1B7F4B]" data-testid="recon-matched">{summary.matched}</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Perlu keputusan</p>
            <p className="stat-value text-[#B26A00]" data-testid="recon-unmatched">
              {summary.unmatched_lines}
            </p>
            <p className="text-[11px] text-[#8E8E93]">{summary.suggested} punya usulan</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Dana titipan</p>
            <p className="stat-value text-[#0058CC] whitespace-nowrap" data-testid="recon-holding-balance">
              {formatCurrency(summary.holding?.balance || 0)}
            </p>
            <p className="text-[11px] text-[#8E8E93]">
              {summary.holding?.count || 0} baris
              {summary.holding?.needs_action ? ` · ${summary.holding.needs_action} perlu tindakan` : ""}
            </p>
          </div>
          <div className={`stat-card ${noStatement || Math.abs(summary.difference) < 0.5 ? "" : "ring-1 ring-[#F3C9C7]"}`}>
            <p className="stat-label">Selisih rekening vs buku</p>
            <p className={`stat-value whitespace-nowrap tabular-nums ${noStatement ? "text-[#8E8E93]" : Math.abs(summary.difference) < 0.5 ? "text-[#1B7F4B]" : "text-[#C0392B]"}`}
              data-testid="recon-difference">{noStatement ? "—" : formatCurrency(summary.difference)}</p>
            {noStatement ? (
              <p className="text-[11px] text-[#8E8E93]" data-testid="recon-difference-hint">dihitung setelah mutasi rekening diimpor</p>
            ) : summary.fully_reconciled && (
              <p className="text-[11px] text-[#1B7F4B] font-semibold">Terekonsiliasi penuh ✓</p>
            )}
          </div>
        </div>
      )}

      <div className="section-card">
        <div className="section-head flex-wrap gap-2">
          <PageTabs testId="recon-tabs" ariaLabel="Rekonsiliasi bank" className="min-w-0" value={tab} onChange={setTab}
            tabs={TABS.map((t) => ({
              key: t.id, label: t.label, icon: t.icon, testId: `recon-tab-${t.id}`,
              count: t.id === "holding" && holding?.needs_action ? holding.needs_action : undefined,
            }))} />
          <p className="ml-auto text-[11px] text-[#6B6B73]" data-testid="recon-rules-moved">
            Aturan pembelajaran & template bank kini di <a className="font-semibold text-[#0058CC] underline" href="?view=bank-recon-rules" data-testid="recon-rules-link">Pengaturan › Keuangan</a>
            {suggestedRules ? <span className="ml-1 rounded-full bg-[#FFF4E5] px-1.5 text-[10px] font-bold text-[#B26A00]">{suggestedRules} usulan menunggu</span> : null}
          </p>
        </div>
        <div className="section-body">
          {tab === "lines" && (
            <>
              <div className="flex items-center gap-2 flex-wrap mb-3">
                {/* Fase 4 · R2 (L-03) — impor kini pop-up (dulu panel diselipkan; tombol bergantian "Tutup panel impor"). */}
                <button type="button" data-testid="recon-import-toggle" className="secondary-button"
                  onClick={() => setShowImport(true)}>
                  <Upload size={14} /> Impor mutasi bank
                </button>
                <button type="button" data-testid="recon-auto-match" className="primary-button"
                  disabled={busy === "auto" || !acctId} onClick={doAutoMatch}>
                  {busy === "auto" ? <RefreshCw size={14} className="spin" /> : <Wand2 size={14} />}
                  Cocokkan otomatis
                </button>
                <span className="text-[11px] text-[#8E8E93]">
                  Ambang & bobot skor diatur di Pengaturan → Rekonsiliasi Bank (tanpa perlu rilis baru).
                </span>
              </div>

              <div className="mb-3 grid grid-cols-1 gap-2 rounded-lg border border-[#E5E5EA] bg-[#FAFBFC] px-3 py-2"
                data-testid="recon-filter-bar">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <span className="text-[11px] font-semibold text-[#6B6B73]">Tampilkan status</span>
                  <FilterChips ariaLabel="Saring status mutasi" className="min-w-0" testId="recon-filter-status"
                    value={fStatus || "all"} onChange={(k) => setFStatus(k === "all" ? "" : k)}
                    options={STATUS_FILTERS.map((o) => ({ key: o.value || "all", label: o.label }))} />
                </div>
                <div className="flex flex-wrap items-end gap-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-[#6B6B73] mb-1">
                      Mutasi dari tanggal
                    </label>
                    <KNDatePicker data-testid="recon-filter-start" placeholder="Dari"
                      value={fStart} onChange={setFStart} />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-[#6B6B73] mb-1">
                      sampai tanggal
                    </label>
                    <KNDatePicker data-testid="recon-filter-end" placeholder="Sampai" min={fStart}
                      value={fEnd} onChange={setFEnd} />
                  </div>
                  {filterOn && (
                    <button type="button" data-testid="recon-filter-clear" className="secondary-button"
                      onClick={() => { setFStatus(""); setFStart(""); setFEnd(""); }}>
                      <FilterX size={14} /> Bersihkan filter
                    </button>
                  )}
                  <span className="ml-auto self-center text-[11px] text-[#6B6B73]" data-testid="recon-filter-count">
                    {loading ? "Memuat…" : `${lines.length} baris ditampilkan`}
                    {filterOn ? " · kartu ringkasan mengikuti periode yang dipilih" : ""}
                  </span>
                </div>
              </div>

              <ReconLinesTable lines={lines} busy={busy} onAction={lineAction}
                onOpenMatch={(l) => setMatchFor(l)} onReload={loadData} onError={fail}
                onNotify={notify} />
            </>
          )}

          {tab === "holding" && (
            <ReconHoldingPanel holding={holding} busy={busy}
              onAction={lineAction} onReload={loadData} onError={fail} onNotify={notify} />
          )}
        </div>
      </div>

      {showImport && (
        <ReconImportPanel accountId={acctId} formats={formats} onClose={() => setShowImport(false)}
          onDone={async (info) => { setShowImport(false); notify(info); await loadData(); }} />
      )}

      {matchFor && (
        <ReconMatchModal line={matchFor} onClose={() => setMatchFor(null)}
          onDone={async (m) => { setMatchFor(null); notify(m); await loadData(); }}
          onError={fail} />
      )}

      <p className="text-[11px] text-[#9A9BA3] flex items-center gap-1">
        <AlertTriangle size={11} className="shrink-0" /> Pencocokan bersifat tambah-saja: ia hanya menautkan mutasi ke
        transaksi kas. Jurnal baru terbit hanya pada tiga jalur berlabel: dana dititipkan
        (Dr Bank / Cr Titipan), titipan dialokasikan (Dr Titipan / Cr Piutang), dan biaya ·
        bunga bank yang dibukukan langsung dari layar ini (Dr Beban Adm Bank / Cr Bank atau
        sebaliknya untuk bunga).
      </p>
    </div>
  );
}
