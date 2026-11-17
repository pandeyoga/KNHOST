/**
 * GeneralLedger (EPIC7-C) — Jurnal Umum, Neraca Saldo, Buku Besar.
 * Akses admin/manager (permission "accounting"). Sumber: /api/gl/*.
 * PK-16 — SATU banner PT (`scope_meta` /gl/summary) di atas KPI berlaku untuk tab Jurnal, Neraca Saldo & Buku Besar
 * (cakupan ketiganya sama: header PT); gagal memuat ringkasan → KPI dikosongkan.
 * PK-43 (UX-13, `02` L8) — preset navigasi (`useViewPreset`): `{tab, code, start, end, from, fromTab}`. Dari Laporan
 * Keuangan (`from: "financial-statements"`) tampil tombol **← Kembali ke Laporan Keuangan** di atas tab (tab & periode
 * asal). Baris buku besar membuka rincian jurnal; rincian jurnal membuka dokumen sumbernya (`onOpenDocument`) dan
 * bilah kembali dokumen itu membawa preset buku besar yang sama.
 * MN-T2 — tab "Rekonsiliasi Persediaan" dan "Suspense" pindah ke Tutup Buku (seksi lipat "Persediaan vs buku besar" dan
 * "Akun sementara"); layar ini tinggal Jurnal · Neraca Saldo · Buku Besar + satu tautan ke Tutup Buku. Preset lama
 * `{tab: "recon" | "suspense"}` dialihkan ke `closing` `{seksi}` (bila peran boleh membuka Tutup Buku).
 */
import { apiErrorText } from "../../utils/apiError";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  RefreshCw, FileStack, Scale, BookOpen, Plus, RotateCcw, X, CheckCircle2, Search, ArrowLeft, ArrowRight,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import PaginationBar from "../../components/PaginationBar";
import { usePagedList } from "../../hooks/usePagedList";
import KNSelect from "../../components/KNSelect";
import { formatCurrency, formatDate } from "../../utils/formatters";
import JournalEntryModal from "./JournalEntryModal";
import JournalDetailModal from "./JournalDetailModal";
import { Kpi, BalancedKpi } from "./GeneralLedgerParts";
import { TrialBalanceTab, LedgerTab } from "./GeneralLedgerTabs";
import DesktopOnlyNotice from "../../components/DesktopOnlyNotice";
import EntityScopeBanner from "../../components/EntityScopeBanner";
import PageTabs from "../../components/PageTabs";
import { SOURCE_LABELS, sourceLabel } from "./glSourceLabels";
import { askConfirm } from "../../services/confirmService";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyPost } from "../../utils/moneyRequest";
import useViewPreset from "../../hooks/useViewPreset";
import { useAppNav } from "../../context/AppNavContext";
import useJournalActions, { izinAkuntansi } from "./useJournalActions";   // PK-43 — anulir/balik dari tab Jurnal & Buku Besar
import JournalProposalsPanel, { JournalProposalBanner } from "./JournalProposalsPanel";   // KF-T6
import FilterSelect from "../../components/FilterSelect";   // pola UI 16 Nov — saringan dropdown (dulu FilterChips)
import EntityGatedButton, { EntityGateNote } from "../../components/EntityGatedButton";   // PK-42 (UX-05)

const TONE_GRAY = "bg-gray-100 text-gray-600";
const SOURCE_META_BASE = {
  manual: { label: "Manual", tone: "bg-[#F3EAFB] text-[#6B219A]" },
  sales_order: { label: "Penjualan", tone: "bg-[#E6F6EC] text-[#1B7F4B]" },
  cash_transaction: { label: "Kas", tone: "bg-[#E7F0FF] text-[#0058CC]" },
  reversal: { label: "Pembalik", tone: "bg-[#FFF4E5] text-[#B45309]" },
};
// Audit UI 24 Okt (069): kolom Sumber dulu menampilkan kode mentah ("shipment_cogs", …). Peta label kini di
// glSourceLabels.js (G1-07: dipakai juga panel "Kenapa berselisih?"); kode baru tetap dibaca manusiawi.
const SOURCE_META = {
  ...Object.fromEntries(Object.entries(SOURCE_LABELS).map(([k, label]) => [k, { label, tone: TONE_GRAY }])),
  ...SOURCE_META_BASE,
};
const sourceMeta = (code) => SOURCE_META[code] || { label: sourceLabel(code), tone: TONE_GRAY };
const TABS = [
  { id: "journal", label: "Jurnal", icon: FileStack },
  { id: "trial", label: "Neraca Saldo", icon: Scale },
  { id: "ledger", label: "Buku Besar", icon: BookOpen },
];
/** MN-T2 — preset tab lama → seksi di layar Tutup Buku. */
export const TAB_PINDAH_KE_TUTUP_BUKU = { recon: "persediaan", suspense: "akun-sementara" };
export const TEKS_PINDAH = "Rekonsiliasi persediaan dan akun sementara kini di Tutup Buku";

// UAT 24 Okt (audit UI tahap 2) — G1-15: tanggal tampilan satu format ("25 Okt 2026", WIB) via formatDate.
const fmtDate = (iso) => formatDate(iso);

// FASE P6 — kolom Unduh CSV jurnal. Label "Sumber" & "Status" memakai kata yang SAMA
// dengan yang terbaca di tabel (bukan kode mentah `void`/`sales_order`), supaya berkasnya
// bisa dibaca orang yang tidak menghafal kode internal.
const JOURNAL_CSV_COLUMNS = [
  { key: "number", header: "No Jurnal" },
  { key: "date", header: "Tanggal", type: "date" },
  { header: "Sumber", get: (je) => (je.source_type ? sourceMeta(je.source_type).label : "") },
  { key: "source_label", header: "Rujukan Sumber" },
  { key: "description", header: "Keterangan" },
  { key: "total_debit", header: "Nilai", type: "num" },
  { header: "Status", get: (je) => (je.status === "void" ? "Anulir" : "Terposting") },
];

const TAB_IDS = TABS.map((t) => t.id);
// PK-43 — asal "Laporan Keuangan": tab & periode laporan untuk tombol kembali. MN-T3 — juga Arus Kas & Perubahan Ekuitas.
const REPORT_LABEL = { pl: "Laba-Rugi", bs: "Neraca", cf: "Arus Kas", eq: "Perubahan Ekuitas" };
const reportOrigin = (p) => (p?.from === "financial-statements"
  ? { tab: p.fromTab || "pl", start: p.fromTab === "bs" ? "" : (p.start || ""), end: p.end || "" } : null);

export default function GeneralLedger({ selectedEntity, entities = [], focusDoc, onClearFocus, onOpenDocument }) {
  const { go, canOpen } = useAppNav();
  const bukaTutupBuku = canOpen("closing");
  const preset = useViewPreset("general-ledger", (p) => {
    if (TAB_PINDAH_KE_TUTUP_BUKU[p.tab] && bukaTutupBuku) {
      go("closing", { preset: { seksi: TAB_PINDAH_KE_TUTUP_BUKU[p.tab] } });
      return;
    }
    if (TAB_IDS.includes(p.tab)) setTab(p.tab);
    if (p.code) { setLedgerCode(p.code); setLedgerRange({ start: p.start || "", end: p.end || "" }); }
    setFromReport(reportOrigin(p));
  });
  const [tab, setTab] = useState(() => (TAB_IDS.includes(preset?.tab) ? preset.tab : "journal"));
  const [fromReport, setFromReport] = useState(() => reportOrigin(preset));
  const [focusJe, setFocusJe] = useState(null);
  // Dibuka dari Jejak Dokumen → langsung tampilkan jurnal yang diklik.
  useEffect(() => {
    if (!focusDoc?.focus_id) return;
    setTab("journal");
    axios.get(`${API}/gl/journal/${focusDoc.focus_id}`)
      .then((r) => setFocusJe({ ...r.data, _from_trace: focusDoc.from_trace || null }))
      .catch((e) => setError(apiErrorText(e, "Jurnal tidak ditemukan / di luar badan usaha aktif.")))
      .finally(() => onClearFocus && onClearFocus());
  }, [focusDoc?.focus_id]); // eslint-disable-line react-hooks/exhaustive-deps
  const [summary, setSummary] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [error, setError] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [notice, setNotice] = useState("");
  const [ledgerCode, setLedgerCode] = useState(() => preset?.code || "");
  const [ledgerRange, setLedgerRange] = useState(() => ({ start: preset?.code ? preset.start || "" : "",
    end: preset?.code ? preset.end || "" : "" }));
  // PK-43 — buka dokumen sumber; bilah "← Kembali ke …" di layar dokumen membawa preset buku besar yang sedang dilihat.
  const openSource = onOpenDocument ? (link) => onOpenDocument({ ...link, origin: { view: "general-ledger",
    preset: tab === "ledger" && ledgerCode ? { tab: "ledger", code: ledgerCode, ...ledgerRange,
      ...(fromReport ? { from: "financial-statements", fromTab: fromReport.tab } : {}) } : { tab } } }) : undefined;
  // PK-12 — kunci idempotensi untuk tulis ke /gl/ (kirim ulang setelah koneksi putus diputar ulang server).
  const syncIntent = useIntentKey("glsync");

  // PK-36 — bagan akun PT yang sedang dibuka: tanda `manual_allowed` (akun kontrol) mengikuti pengaturan & pemetaan
  // PT itu; "Semua PT" → lapisan global.
  const accEntity = selectedEntity && selectedEntity !== "all" ? selectedEntity : "";
  const loadMeta = useCallback(async () => {
    try {
      const [s, a] = await Promise.all([
        axios.get(`${API}/gl/summary`),
        axios.get(`${API}/gl/accounts`, accEntity ? { params: { entity_id: accEntity } } : undefined),
      ]);
      setSummary(s.data || null);
      setAccounts(Array.isArray(a.data) ? a.data : []);
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat data GL."));
      setSummary(null);   // PK-16 (RP-04) — KPI tidak menyisakan angka permintaan sebelumnya
    }
  }, [accEntity]);

  useEffect(() => { loadMeta(); }, [loadMeta]);

  const [refreshKey, setRefreshKey] = useState(0);
  const refreshAll = () => { setRefreshKey((k) => k + 1); loadMeta(); };

  const runSync = async () => {
    // G1-16 — Sinkronkan memposting jurnal otomatis untuk transaksi yang belum berjurnal → konfirmasi dulu.
    if (!(await askConfirm({
      title: "Sinkronkan jurnal otomatis?",
      message: "Penjualan & transaksi kas yang belum berjurnal akan diposting ke buku besar sekarang. "
        + "Jurnal yang sudah ada tidak diubah.",
      confirmLabel: "Sinkronkan",
    }))) return;
    setSyncing(true); setError(""); setNotice("");
    try {
      const res = await syncIntent.send({ aksi: "sync" }, (k) => moneyPost(`${API}/gl/sync`, undefined, k));
      const r = res.data || {};
      setNotice(`Sinkron selesai: ${r.total || 0} jurnal baru (penjualan ${r.sales_orders || 0}, kas ${r.cash_transactions || 0}).`);
      refreshAll();
    } catch (e) {
      setError(apiErrorText(e, "Gagal sinkronisasi jurnal."));
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div data-testid="gl-view">
      {/* Fase 3 · P4 (L-04 kelas C) — akuntansi: cukup pemberitahuan "paling nyaman di desktop" di HP. */}
      <DesktopOnlyNotice testId="gl-desktop-notice" what="Jurnal & Buku Besar" />
      {fromReport && (
        <div className="mb-3 flex flex-wrap items-center gap-2" data-testid="gl-back-bar">
          <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="gl-back-to-report"
            onClick={() => go("financial-statements", { preset: { tab: fromReport.tab, start: fromReport.start,
              end: fromReport.end } })}>
            <ArrowLeft size={13} aria-hidden="true" /> Kembali ke Laporan Keuangan
          </button>
          <span className="text-fs-12 text-kn-text-2">Mutasi akun dari {REPORT_LABEL[fromReport.tab] || "Laba-Rugi"}.</span>
        </div>
      )}
      <EntityScopeBanner meta={summary?.scope_meta} />
      {/* Cek layar 15 Nov — empat kartu sebaris hanya di ≥1280 px; di 1024 px 2+2 supaya total rupiah utuh sebaris. */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3 mb-3">
        <Kpi testId="gl-kpi-count" label={summary?.void_count ? "Total Jurnal (tanpa anulir)" : "Total Jurnal"} value={summary?.journal_count ?? "—"} icon={FileStack} />
        <Kpi testId="gl-kpi-debit" label="Total Debit" value={formatCurrency(summary?.total_debit)} icon={Scale} tone="text-[#0058CC]" />
        <Kpi testId="gl-kpi-credit" label="Total Kredit" value={formatCurrency(summary?.total_credit)} icon={Scale} tone="text-[#1B7F4B]" />
        <BalancedKpi balanced={summary?.balanced} />
      </div>

      <div className="section-card">
        <div className="section-head flex-wrap gap-2">
          {/* Fase 4 · R2 (L-01) — pil ungu buatan sendiri → PageTabs baku (testid `gl-tab-*` tetap). */}
          <PageTabs testId="gl-tabs" ariaLabel="Jurnal & Buku Besar" className="min-w-0" value={tab} onChange={setTab}
            tabs={TABS.map((t) => ({ key: t.id, label: t.label, icon: t.icon, testId: `gl-tab-${t.id}` }))} />
          <div className="flex items-center gap-2 ml-auto">
            {/* Pelatihan 18 Nov (F16) — Finance (lihat saja, K-09) tidak lagi melihat tombol yang pasti ditolak 403. */}
            {tab === "journal" && (
              <>
                {izinAkuntansi("create") && (
                  <EntityGatedButton selectedEntity={selectedEntity} what="membuat jurnal" hint={false} aria-describedby="gl-new-journal-scope-note"
                    data-testid="gl-new-journal" className="primary-button" onClick={() => setShowModal(true)}><Plus size={14} /> Jurnal Baru</EntityGatedButton>
                )}
                {izinAkuntansi("manage") && (
                  <button type="button" data-testid="gl-sync" className="secondary-button" onClick={runSync} disabled={syncing}><RotateCcw size={13} className={syncing ? "animate-spin" : ""} /> Sinkronkan</button>
                )}
              </>
            )}
            <button data-testid="gl-refresh" className="icon-button" onClick={refreshAll} aria-label="Muat ulang" title="Muat ulang"><RefreshCw size={14} /></button>
          </div>
        </div>
        <div className="section-body">
          {/* PK-42 — kepala kartu sudah berisi lima tab + tiga tombol: alasan tombol Jurnal Baru yang mati di bilah sendiri. */}
          {tab === "journal" && izinAkuntansi("create") && <EntityGateNote selectedEntity={selectedEntity} what="membuat jurnal" testId="gl-new-journal-scope-note" />}
          {/* MN-T2 — dua tab lama kini seksi di Tutup Buku (tautan hanya bila peran boleh membukanya). */}
          {bukaTutupBuku && (
            <p className="mb-2 text-fs-12 text-kn-text-2" data-testid="gl-moved-note">
              <button type="button" className="link-button inline-flex items-center gap-1" data-testid="gl-moved-link"
                onClick={() => go("closing")}>{TEKS_PINDAH} <ArrowRight size={12} aria-hidden="true" /></button>
            </p>
          )}
          <ErrorNotice message={error} onRetry={refreshAll} onDismiss={() => setError("")} testId="gl-error" />
          {notice && (
            <div data-testid="gl-notice" className="mb-3 rounded-md bg-[#E6F6EC] border border-[#BDE5CC] text-[#1B7F4B] text-[12px] px-3 py-2 flex items-center gap-2">
              <CheckCircle2 size={14} />{notice}
              <button className="ml-auto" onClick={() => setNotice("")} aria-label="Tutup"><X size={13} /></button>
            </div>
          )}

          {tab === "journal" && <JournalTab refreshKey={refreshKey} onChanged={refreshAll} onError={setError} entities={entities} selectedEntity={selectedEntity}
            sources={summary?.sources} voidCount={summary?.void_count || 0} onNotice={setNotice}
            focusJe={focusJe} onFocusShown={() => setFocusJe(null)} onOpenDocument={openSource} />}
          {tab === "trial" && <TrialBalanceTab refreshKey={refreshKey} onError={setError} selectedEntity={selectedEntity}
            onDrill={(p) => { setTab("ledger"); setLedgerCode(p.code); setLedgerRange({ start: p.start || "", end: p.end || "" }); }} />}
          {tab === "ledger" && <LedgerTab accounts={accounts} refreshKey={refreshKey} code={ledgerCode} setCode={setLedgerCode} onError={setError}
            range={ledgerRange} setRange={setLedgerRange} entities={entities} selectedEntity={selectedEntity}
            sourceMeta={sourceMeta} onChanged={refreshAll} onOpenDocument={openSource} />}
        </div>
      </div>

      {showModal && (
        <JournalEntryModal accounts={accounts} onClose={() => setShowModal(false)}
          onSaved={async (res) => {
            setShowModal(false);
            // KF-T6 — aturan dua orang: jurnal tersimpan sebagai usulan (202), belum masuk buku.
            setNotice(res?.status === "menunggu_orang_kedua"
              ? "Jurnal manual tersimpan sebagai usulan — menunggu persetujuan orang kedua."
              : "Jurnal manual berhasil diposting.");
            refreshAll();
          }} />
      )}
    </div>
  );
}

// ─── JURNAL TAB ──────────────────────────────────────────────────────────────
function JournalTab({ refreshKey, onChanged, onError, entities = [], selectedEntity, focusJe, onFocusShown,
  sources = null, voidCount = 0, onNotice, onOpenDocument }) {
  // KF-T6 — saringan "Menunggu persetujuan": usulan jurnal manual yang menunggu orang kedua.
  const [pendingView, setPendingView] = useState(false);
  // G1-26 — opsi sumber dari jenis yang benar-benar ada di buku (dulu hanya Manual/Penjualan/Kas).
  const sourceOptions = [{ value: "", label: "Semua sumber" },
    ...(sources && sources.length ? sources : ["manual", "sales_order", "cash_transaction"])
      .map((s) => ({ value: s, label: sourceLabel(s) }))];
  const [sourceFilter, setSourceFilter] = useState("");
  const [search, setSearch] = useState("");
  const [detail, setDetail] = useState(null);
  useEffect(() => {
    if (!focusJe) return;
    setDetail(focusJe);
    setSearch(focusJe.number || "");
    onFocusShown && onFocusShown();
  }, [focusJe]); // eslint-disable-line react-hooks/exhaustive-deps

  // P2 — jurnal dipaginasi di server. Sebelumnya daftarnya dipotong keras di 500 baris
  // TANPA halaman berikutnya, jadi entri ke-501 tidak bisa dijangkau dari layar sama
  // sekali — dan `journal_entries` justru koleksi yang tumbuh paling cepat (setiap
  // transaksi memposting entri).
  const params = useMemo(
    () => (sourceFilter ? { source: sourceFilter } : {}), [sourceFilter]);
  const paged = usePagedList("/gl/journal", { params, search, pageSize: 20 });
  const entries = paged.items;
  const loading = paged.loading;

  useEffect(() => { paged.refresh(); }, [refreshKey]); // eslint-disable-line
  useEffect(() => { if (paged.error) onError(paged.error); }, [paged.error]); // eslint-disable-line

  // PK-12 — satu kunci per niat (anulir / balik); Fase 4 · R2 — galat DILEMPAR ke pop-up rincian. PK-43 — `useJournalActions`.
  const { voidEntry, reverseEntry, bolehBatal } = useJournalActions(() => { setDetail(null); onChanged(); });

  return (
    <div>
      {!pendingView && <JournalProposalBanner refreshKey={refreshKey} onOpen={() => setPendingView(true)} />}
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <FilterSelect testId="gl-journal-view" ariaLabel="Saringan jurnal" value={pendingView ? "pending" : "posted"}
          onChange={(k) => setPendingView(k === "pending")}
          options={[{ key: "posted", label: "Buku jurnal" },
            { key: "pending", label: "Menunggu persetujuan", testId: "gl-journal-pending-filter" }]} />
        {pendingView ? null : <>
        <div className="w-[200px]">
          <KNSelect data-testid="gl-journal-source-filter" className="field py-1 text-[12px]" value={sourceFilter} onValueChange={setSourceFilter}
            placeholder="Semua sumber" searchable options={sourceOptions} />
        </div>
        <div className="flex min-w-[220px] flex-1 items-center gap-2 rounded-md border border-[#EFF0F2] bg-white px-2.5 py-1.5">
          <Search size={13} className="text-[#8E8E93]" />
          <input data-testid="gl-journal-search" value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Cari nomor jurnal / keterangan…"
            className="flex-1 bg-transparent text-[12px] outline-none placeholder:text-[#9A9BA3]" />
          {search && (
            <button onClick={() => setSearch("")} aria-label="Kosongkan pencarian"
              className="text-[#8E8E93] hover:text-[#1C1C1E]"><X size={12} /></button>
          )}
        </div>
        <span className="text-[11px] text-[#9A9BA3] tabular-nums" data-testid="gl-journal-total">
          {paged.total} jurnal{voidCount > 0 && !sourceFilter && !search ? ` (termasuk ${voidCount} dianulir)` : ""}
        </span>
        </>}
      </div>
      {pendingView ? (
        <JournalProposalsPanel refreshKey={refreshKey} entities={entities} onChanged={onChanged} onNotice={onNotice} />
      ) : loading ? (
        <div className="grid gap-2" data-testid="gl-journal-loading">{[0, 1, 2, 3].map((i) => <div key={i} className="h-10 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
      ) : entries.length === 0 ? (
        <div data-testid="gl-journal-empty" className="py-12 text-center text-[12px] text-[#8E8E93]">
          <FileStack size={26} className="mx-auto mb-2 text-gray-300" />
          {search.trim()
            ? `Tidak ada jurnal yang cocok dengan “${search.trim()}”.`
            : "Belum ada jurnal. Klik “Sinkronkan” untuk posting otomatis dari transaksi."}
        </div>
      ) : (
        <div className="overflow-auto rounded-md border border-[#EFF0F2]">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-left text-[10px] font-bold uppercase text-[#8E8E93] bg-[#FAFBFC] border-b border-[#EFF0F2]">
                <th className="px-3 py-2">No</th>
                <th className="px-3 py-2">Tanggal</th>
                <th className="px-3 py-2">Sumber</th>
                <th className="px-3 py-2">Keterangan</th>
                <th className="px-3 py-2 text-right">Nilai</th>
                <th className="px-3 py-2 text-center">Status</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((je) => {
                const sm = sourceMeta(je.source_type);
                return (
                  <tr key={je.id} data-testid={`gl-journal-row-${je.id}`} onClick={() => setDetail(je)}
                    className="border-b border-[#F5F5F7] last:border-0 cursor-pointer hover:bg-[#FBF8FE]">
                    <td className="px-3 py-2 font-mono text-[11px] font-semibold text-[#3C3C43]">{je.number}</td>
                    <td className="px-3 py-2 text-[#3C3C43]">{fmtDate(je.date)}</td>
                    <td className="px-3 py-2"><span className={`text-[10px] font-bold rounded px-1.5 py-0.5 ${sm.tone}`}>{sm.label}</span>{je.source_label ? <span className="ml-1 text-[10px] text-[#9A9BA3]">{je.source_label}</span> : null}</td>
                    <td className="px-3 py-2 text-[#1C1C1E] max-w-[280px] truncate">{je.description}</td>
                    <td className="px-3 py-2 text-right tabular-nums font-semibold">{formatCurrency(je.total_debit)}</td>
                    <td className="px-3 py-2 text-center">
                      {je.status === "void"
                        ? <span className="text-[10px] font-bold rounded-full px-2 py-0.5 bg-[#FDEDE7] text-[#C0392B]">Anulir</span>
                        : <span className="text-[11px] font-bold rounded-full px-2 py-0.5 bg-[#E6F6EC] text-[#1B7F4B]">Terposting</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {/* P2 — kontrol halaman jurnal */}
      {!pendingView && !loading && entries.length > 0 && (
        <div className="mt-2">
          <PaginationBar
            page={paged.page} pageSize={paged.pageSize} total={paged.total}
            hasMore={paged.hasMore} loading={paged.loading}
            onPrev={paged.prev} onNext={paged.next} onPageSize={paged.setPageSize}
            testId="gl-journal-pager" label="jurnal"
            exportConfig={{ columns: JOURNAL_CSV_COLUMNS, rows: entries,
              fetchAll: paged.fetchAll, filename: "jurnal-umum" }}
          />
        </div>
      )}
      {detail && <JournalDetailModal je={detail} sourceMeta={sourceMeta} entities={entities} selectedEntity={selectedEntity} onClose={() => setDetail(null)} onVoid={bolehBatal ? voidEntry : undefined} onReverse={bolehBatal ? reverseEntry : undefined} onOpenDocument={onOpenDocument} />}
    </div>
  );
}
