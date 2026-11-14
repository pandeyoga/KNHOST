/**
 * R6.2 — FixedAssetsView — Aset Tetap: registrasi, penyusutan straight-line & disposal.
 * Akses admin/manager (permission "fixed_asset"). Sumber: /api/fixed-assets*.
 * GL: Dr 6-6000 Beban Penyusutan / Cr 1-2900 Akumulasi Penyusutan.
 * Disposal: gain/loss = proceeds − nilai buku (append-only; aset → status disposed).
 *
 * PK-23 — daftar memakai tabel baku (`data-table head-wrap`, kolom Aksi `col-sticky-end`, token `kn-*`, tombol
 * `btn-sm`); kartu ringkasan tidak memotong angka (grid 2 → 3+2 → 5, `kpiValueParts`). Tombol Pindah PT & Lepas mati
 * BERALASAN TERTULIS untuk aset yang sudah dipindahkan, sedang diproses, atau belum berjurnal (server menolak hal yang
 * sama). Hasil Jalankan Penyusutan menyebut jumlah yang gagal dijurnal + tautan ke Posting Gagal.
 */
import { apiErrorText } from "../../utils/apiError";
import KNMonthPicker from "@/components/KNMonthPicker";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  RefreshCw, Building2, Plus, PlayCircle, CalendarClock, PackageMinus,
  Layers3, TrendingDown, Wallet, Scale, CheckCircle2, AlertTriangle, ChevronRight,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import EntityGatedButton, { EntityGateNote } from "../../components/EntityGatedButton";   // PK-42 (UX-05)
import FocusNotice from "../../components/FocusNotice";
import FilterChips from "../../components/FilterChips";
import { SearchBox } from "../../components/ListPageParts";
import useFocusDoc from "../../hooks/useFocusDoc";
import DesktopOnlyNotice from "../../components/DesktopOnlyNotice";
import { formatCurrency, formatPeriod } from "../../utils/formatters";
import { askConfirm } from "../../services/confirmService";
import {
  AssetStatusPill, FaKpi, AddAssetDialog, ScheduleDialog, DisposeDialog, TransferAssetDialog, fmtDate,
  assetActionBlock,
} from "./FixedAssetsParts";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyPost } from "../../utils/moneyRequest";
import { confirmMoney } from "../../utils/moneyConfirm";
import { entityFullById } from "../../utils/entityLabel";
import { useAppNav } from "../../context/AppNavContext";
import { canCurrent } from "../../config/roles";

const thisPeriod = () => new Date().toISOString().slice(0, 7);
// Saringan daftar (bukan tab): status kepemilikan aset.
const OWNED = ["active", "fully_depreciated", "transferring", "disposing"];
const FILTERS = [
  { key: "all", label: "Semua", match: () => true },
  { key: "owned", label: "Dimiliki", match: (a) => OWNED.includes(a.status) },
  { key: "transferred", label: "Pindah PT", match: (a) => a.status === "transferred" },
  { key: "disposed", label: "Dilepas", match: (a) => a.status === "disposed" },
];

export default function FixedAssetsView({ selectedEntity, entities = [], focusDoc, onClearFocus }) {
  const { go } = useAppNav();
  const [assets, setAssets] = useState([]);
  const [summary, setSummary] = useState(null);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [depResult, setDepResult] = useState(null);       // PK-23 — hasil penyusutan yang punya kegagalan
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("all");
  const [period, setPeriod] = useState(thisPeriod());
  const [showAdd, setShowAdd] = useState(false);
  const [scheduleFor, setScheduleFor] = useState(null);   // detail aset (schedule)
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [disposeFor, setDisposeFor] = useState(null);     // aset yang akan dilepas
  // FASE E-7 (E7g) — pindah aset tetap ANTAR BADAN USAHA (nilai buku + masa manfaat sisa).
  // Fase 3 · P4 (L-03) — isian pindah PT kini milik `TransferAssetDialog` (FormModal) di FixedAssetsParts.
  const [transferFor, setTransferFor] = useState(null);
  // PK-12 — satu kunci idempotensi per aksi aset (kirim ulang isi sama setelah koneksi putus tidak menggandakan jurnal).
  const createIntent = useIntentKey("fa");
  const runIntent = useIntentKey("fadep");
  const disposeIntent = useIntentKey("fadsp");
  const transferIntent = useIntentKey("fatrf");
  const settleIntent = useIntentKey("fastl");
  const canSeeFailures = canCurrent("accounting", "view");

  async function submitTransfer({ to_entity_id, transfer_price, reason }) {
    if (!transferFor) return;
    setBusy("transfer"); setError("");
    try {
      const body = { to_entity_id, transfer_price, reason };
      const res = await transferIntent.send({ id: transferFor.id, ...body },
        (k) => moneyPost(`${API}/fixed-assets/${transferFor.id}/transfer`, body, k));
      setMsg(`${transferFor.number} dipindah → ${res.data.new_asset.number} `
        + `(harga ${formatCurrency(res.data.price)}, nilai buku ${formatCurrency(res.data.book_value)}`
        + `${res.data.gain > 0 ? `, laba ${formatCurrency(res.data.gain)} dieliminasi di konsolidasi` : ""}). `
        + "Utang antar-PT terbentuk — catat pembayarannya bila uangnya sudah pindah.");
      setTransferFor(null);
      await load();
    } catch (e) {
      setError(apiErrorText(e, "Gagal memindahkan aset."));
      await load();   // PK-23 — pindah yang tertahan di jurnal tampil sebagai "Sedang Dipindah"
    } finally { setBusy(""); }
  }

  async function settleTransfer(a) {
    // PK-13 (FY-17) — kas dua PT berpindah: tanya dulu dengan nominal & PT penerima (pihak yang kasnya keluar).
    const tr = a.transfer || {};
    const ok = await confirmMoney({
      title: `Catat pembayaran pindah aset ${a.number}?`,
      effect: `Kas keluar dari ${tr.to_entity_name || entityFullById(entities, tr.to_entity_id)} dan masuk ke `
        + `${tr.from_entity_name || entityFullById(entities, tr.from_entity_id)}; utang antar-PT atas aset ini dilunasi.`,
      amount: tr.price, entityId: tr.to_entity_id, entities,
      confirmLabel: "Catat Pembayaran", testId: "asset-settle-confirm",
    });
    if (!ok) return;
    setBusy(`settle-${a.id}`); setError("");
    try {
      const body = { note: "" };
      const res = await settleIntent.send({ id: a.id, aksi: "settle", ...body },
        (k) => moneyPost(`${API}/fixed-assets/${a.id}/transfer/settle`, body, k));
      setMsg(`Pembayaran pindah aset ${a.number} dicatat (${formatCurrency(res.data.paid)}) — `
        + `kas berpindah: ${(res.data.cash || []).join(" · ")}.`);
      await load();
    } catch (e) {
      setError(apiErrorText(e, "Gagal mencatat pembayaran pindah aset."));
    } finally { setBusy(""); }
  }

  const entParam = useMemo(
    () => (selectedEntity && selectedEntity !== "all" ? selectedEntity : ""),
    [selectedEntity],
  );

  const entityName = useCallback(
    (id) => {
      const e = (entities || []).find((x) => x.id === id);
      return e ? (e.short_name || e.legal_name || id) : (id || "—");
    },
    [entities],
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = entParam ? { entity_id: entParam } : {};
      const [ls, sm, mt] = await Promise.all([
        axios.get(`${API}/fixed-assets`, { params }),
        axios.get(`${API}/fixed-assets/summary`, { params }),
        axios.get(`${API}/fixed-assets/meta`, { params }),
      ]);
      setAssets(Array.isArray(ls.data) ? ls.data : []);
      setSummary(sm.data || null);
      setMeta(mt.data || null);
      setError("");
      setLoaded(true);
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat data aset tetap."));
    } finally {
      setLoading(false);
    }
  }, [entParam]);

  useEffect(() => { load(); }, [load]);

  const notify = (m) => { setMsg(m); setTimeout(() => setMsg(""), 6000); };

  async function createAsset(payload) {
    setBusy("create");
    try {
      const res = await createIntent.send(payload, (k) => moneyPost(`${API}/fixed-assets`, payload, k));
      // PK-23 — jawaban memuat status jurnal perolehan: gagal = aset tersimpan, jurnalnya diulang dari Posting Gagal.
      const d = res.data || {};
      notify(d.gl_status === "failed"
        ? `Aset ${d.number || ""} tersimpan, tetapi jurnal perolehannya gagal: ${d.gl_error || "galat tidak diketahui"}. `
          + "Ulangi di Keuangan › Posting Gagal."
        : `Aset ${d.number || ""} dibuat. Jurnal perolehan: ${d.acquisition_je || "—"}.`);
      setShowAdd(false);
      await load();
      return true;
    } catch (e) {
      setError(apiErrorText(e, "Gagal membuat aset."));
      return false;
    } finally { setBusy(""); }
  }

  // G1-25 — aset yang masih bisa disusutkan + perkiraan beban sebulan (garis lurus) untuk dialog konfirmasi.
  // PK-23 — hanya aset aktif yang jurnal perolehannya terbit (server melewati yang lain beserta alasannya).
  const depreciable = useMemo(() => assets.filter((a) => a.status === "active" && !assetActionBlock(a)
    && Number(a.depreciated_months || 0) < Number(a.useful_life_months || 0)), [assets]);
  const estMonthly = useMemo(() => depreciable.reduce((s, a) => s
    + Math.max(0, Number(a.acquisition_cost || 0) - Number(a.salvage_value || 0)) / Math.max(1, Number(a.useful_life_months || 1)), 0),
  [depreciable]);

  async function runDepreciation() {
    if (!/^\d{4}-\d{2}$/.test(period)) { setError("Format periode harus YYYY-MM (contoh 2026-07)."); return; }
    // UAT 24 Okt (audit UI tahap 2) — G1-25: menerbitkan jurnal → konfirmasi periode, jumlah aset & perkiraan nilai.
    const ok = await askConfirm({
      danger: true,
      title: `Jalankan penyusutan ${formatPeriod(period)} untuk ${depreciable.length} aset?`,
      message: `Jurnal Beban Penyusutan / Akumulasi Penyusutan diterbitkan ± ${formatCurrency(estMonthly)} `
        + "(perkiraan garis lurus; aset yang sudah disusutkan pada periode ini dilewati).",
      confirmLabel: "Jalankan Penyusutan",
    });
    if (!ok) return;
    setBusy("run"); setDepResult(null);
    try {
      const body = { period, entity_id: entParam };
      const res = await runIntent.send(body, (k) => moneyPost(`${API}/fixed-assets/run-depreciation`, body, k));
      const d = res.data || {};
      const gagal = (d.failed || []).length;
      const teks = `Penyusutan ${formatPeriod(d.period)}: ${d.posted} aset dijurnal (${formatCurrency(d.total_amount)}), `
        + `${d.skipped} dilewati${gagal ? `, ${gagal} gagal dijurnal` : ""}.`;
      if (gagal) setDepResult({ text: teks, failed: d.failed });
      else notify(teks);
      await load();
    } catch (e) {
      setError(apiErrorText(e, "Gagal menjalankan penyusutan."));
    } finally { setBusy(""); }
  }

  async function openSchedule(asset) {
    setScheduleFor({ ...asset, schedule: [], depreciation_entries: [] });
    setScheduleLoading(true);
    try {
      const res = await axios.get(`${API}/fixed-assets/${asset.id}`);
      setScheduleFor(res.data || null);
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat jadwal penyusutan."));
      setScheduleFor(null);
    } finally { setScheduleLoading(false); }
  }

  async function submitDispose({ proceeds, date, note }) {
    setBusy("dispose");
    try {
      const body = { proceeds, date, note };
      const res = await disposeIntent.send({ id: disposeFor.id, ...body },
        (k) => moneyPost(`${API}/fixed-assets/${disposeFor.id}/dispose`, body, k));
      const d = res.data?.disposal || {};
      const label = d.result === "gain" ? "Laba" : d.result === "loss" ? "Rugi" : "Impas";
      notify(`${res.data?.number || "Aset"} dilepas. ${label} pelepasan ${formatCurrency(Math.abs(d.gain_loss || 0))} · Jurnal ${d.je_number || "—"}.`);
      setDisposeFor(null);
      await load();
      return true;
    } catch (e) {
      setError(apiErrorText(e, "Gagal melepas aset."));
      return false;
    } finally { setBusy(""); }
  }

  const counts = useMemo(() => Object.fromEntries(FILTERS.map((f) => [f.key, assets.filter(f.match).length])),
    [assets]);
  const rows = useMemo(() => {
    const term = q.trim().toLowerCase();
    const f = FILTERS.find((x) => x.key === filter) || FILTERS[0];
    return assets.filter((a) => f.match(a)
      && (!term || `${a.number} ${a.name} ${a.category}`.toLowerCase().includes(term)));
  }, [assets, q, filter]);

  const s = summary || {};
  // PK-44 (IA-10) — tautan dokumen (Jejak Dokumen / rincian jurnal penyusutan) membuka rincian aset ber-id itu.
  const fokus = useFocusDoc(focusDoc, "fixed_asset", async (id) => {
    setScheduleFor((await axios.get(`${API}/fixed-assets/${id}`)).data || null);
  }, onClearFocus);

  const toneOf = (v, tone) => (Number(v || 0) === 0 ? "text-kn-text-2" : tone);
  return (
    <div data-testid="fixed-assets-view">
      {/* Fase 3 · P4 (L-04 kelas C) — akuntansi aset: cukup pemberitahuan di HP, layar tetap bisa dipakai. */}
      <DesktopOnlyNotice testId="fa-desktop-notice" what="Aset Tetap" />
      {/* KPI ringkasan — PK-23: 2 kolom (HP) → 3+2 (≥768 px, termasuk 1024) → 5 sebaris (≥1536 px); angka tidak
          dipotong ("Rp" saja yang boleh turun baris). */}
      <div className="grid grid-cols-2 md:grid-cols-3 2xl:grid-cols-5 gap-3 mb-3">
        <FaKpi testId="summary-count" label="Jumlah Aset" icon={Layers3}
          value={`${s.count || 0}`}
          hint={`${s.active || 0} dimiliki · ${s.transferred || 0} pindah PT · ${s.disposed || 0} dilepas`} />
        <FaKpi testId="summary-gross-cost" label="Nilai Perolehan" icon={Building2}
          value={formatCurrency(s.gross_cost)} hint="aset yang masih dimiliki" />
        <FaKpi testId="summary-accumulated" label="Akumulasi Penyusutan" icon={TrendingDown}
          value={formatCurrency(s.accumulated_depreciation)} tone={toneOf(s.accumulated_depreciation, "text-kn-warning-text")}
          hint="akun Akumulasi Penyusutan" />
        <FaKpi testId="summary-net-book-value" label="Nilai Buku (Net)" icon={Wallet}
          value={formatCurrency(s.net_book_value)} tone={toneOf(s.net_book_value, "text-kn-success-text")}
          hint="perolehan − akumulasi" />
        {(s.transferred || 0) > 0 ? (
          <FaKpi testId="summary-transferred" label="Pindah ke PT Lain" icon={Building2}
            value={formatCurrency(s.transferred_book_value)} tone="text-kn-action"
            hint={(s.transferred_unsettled || 0) > 0
              ? `${s.transferred} aset · ${s.transferred_unsettled} belum dibayar`
              : `${s.transferred} aset · semua sudah dibayar`} />
        ) : (
          <FaKpi testId="summary-disposal-gain-loss" label="Laba/Rugi Pelepasan" icon={Scale}
            value={formatCurrency(s.disposal_gain_loss)}
            tone={toneOf(s.disposal_gain_loss, (s.disposal_gain_loss || 0) < 0 ? "text-kn-danger-text" : "text-kn-success-text")}
            hint="akumulasi pelepasan" />
        )}
      </div>

      {/* Kontrol penyusutan */}
      <div className="section-card section-pad mb-3">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex items-center gap-2 mr-auto min-w-0">
            <div className="w-9 h-9 rounded-lg bg-kn-action-soft flex items-center justify-center shrink-0">
              <CalendarClock size={17} className="text-kn-action" aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <p className="text-fs-13 font-bold text-kn-text">Jalankan Penyusutan Bulanan</p>
              <p className="text-fs-12 text-kn-text-2">Metode garis lurus; aman dijalankan ulang (satu kali per aset per periode). Dicatat ke Beban Penyusutan / Akumulasi Penyusutan.</p>
            </div>
          </div>
          <label className="grid gap-1">
            <span className="field-label">Periode</span>
            <KNMonthPicker data-testid="fa-period-input" className="w-[170px]" value={period} onChange={setPeriod} />
          </label>
          <div className="grid gap-1 justify-items-end">
            <button data-testid="run-depreciation-btn" className="primary-button whitespace-nowrap"
              disabled={busy === "run" || depreciable.length === 0} onClick={runDepreciation}>
              {busy === "run" ? <RefreshCw size={14} className="animate-spin" /> : <PlayCircle size={14} />}
              Jalankan Penyusutan
            </button>
            {loaded && depreciable.length === 0 && (
              <p className="text-fs-12 text-kn-text-2" data-testid="run-depreciation-reason">
                Tidak ada aset aktif berjurnal yang perlu disusutkan.
              </p>
            )}
          </div>
        </div>
        {depResult && (
          <div className="notice-bar warning mt-3" data-testid="fa-dep-failed">
            <AlertTriangle size={14} aria-hidden="true" />
            <span>
              {depResult.text} Gagal: {depResult.failed.map((f) => f.number).join(", ")}.
              {" "}Jurnalnya tersimpan untuk diulang.
            </span>
            {canSeeFailures && (
              <button type="button" className="link-button whitespace-nowrap" data-testid="fa-dep-failed-open"
                onClick={() => go("posting-failures")}>
                Buka Posting Gagal <ChevronRight size={12} aria-hidden="true" />
              </button>
            )}
            <button type="button" onClick={() => setDepResult(null)} aria-label="Tutup">×</button>
          </div>
        )}
      </div>

      {/* Daftar aset */}
      <div className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2 min-w-0">
            <Building2 size={16} className="text-kn-action" aria-hidden="true" />
            <h2 data-testid="fixed-assets-title" className="whitespace-nowrap">Daftar Aset Tetap</h2>
            <span className="whitespace-nowrap text-fs-12 text-kn-text-2">{rows.length} aset</span>
          </div>
          <div className="flex items-center gap-2 ml-auto">
            <EntityGatedButton selectedEntity={selectedEntity} what="menambah aset tetap" data-testid="add-asset-btn"
              hint={false} aria-describedby="add-asset-btn-scope-note"
              className="primary-button btn-sm whitespace-nowrap" onClick={() => { setError(""); setShowAdd(true); }}>
              <Plus size={14} /> Tambah Aset
            </EntityGatedButton>
            <button data-testid="fa-refresh" className="icon-button" onClick={load} aria-label="Muat ulang">
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            </button>
          </div>
        </div>
        <div className="section-body">
          {/* PK-42 — kepala kartu hanya judul, jumlah, dan dua tombol; alasan, cari, saringan di badan. */}
          <EntityGateNote selectedEntity={selectedEntity} what="menambah aset tetap" testId="add-asset-btn-scope-note" />
          <SearchBox testId="fa-search" value={q} onChange={setQ} placeholder="Cari nomor / nama / kategori…">
            <FilterChips testId="fa-filter" value={filter} onChange={(k) => setFilter(k || "all")} ariaLabel="Status aset"
              options={FILTERS.map((f) => ({ key: f.key, label: f.label, count: counts[f.key],
                hidden: f.key !== "all" && f.key !== filter && !counts[f.key] }))} />
          </SearchBox>
          <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="fixed-assets-error" />
          <FocusNotice {...fokus} testId="fa-focus-notice" />
          {msg && (
            <div className="notice-bar success mb-2" data-testid="fa-notice">
              <CheckCircle2 size={14} /> <span>{msg}</span>
              <button onClick={() => setMsg("")} aria-label="Tutup">×</button>
            </div>
          )}

          {loading && !loaded ? (
            <div className="grid gap-2" data-testid="fa-loading">
              {[0, 1, 2, 3].map((i) => <div key={i} className="h-10 bg-kn-neutral-soft rounded animate-pulse" />)}
            </div>
          ) : !loaded ? null : rows.length === 0 ? (
            <div className="py-12 text-center text-fs-12 text-kn-text-2" data-testid="fa-empty">
              <Building2 size={26} className="mx-auto mb-2 text-kn-text-2" aria-hidden="true" />
              {q || filter !== "all" ? "Tidak ada aset yang cocok dengan pencarian atau saringan."
                : "Belum ada aset tetap terdaftar. Klik “Tambah Aset” untuk registrasi aset pertama."}
            </div>
          ) : (
            <div className="table-wrap">
              <table className="data-table head-wrap" data-testid="fa-table">
                <thead>
                  <tr>
                    <th>Nomor</th>
                    <th>Nama Aset</th>
                    <th>Kategori</th>
                    <th className="text-right">Harga Perolehan</th>
                    <th className="text-right">Akumulasi Penyusutan</th>
                    <th className="text-right">Nilai Buku</th>
                    <th>Status</th>
                    <th className="col-sticky-end text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((a) => {
                    const block = assetActionBlock(a);
                    const tr = a.transfer || {};
                    return (
                      <tr key={a.id} data-testid={`asset-row-${a.id}`}>
                        <td className="font-mono whitespace-nowrap font-semibold text-kn-action">{a.number}</td>
                        <td>
                          <p className="font-semibold text-kn-text">{a.name}</p>
                          <p className="text-fs-12 text-kn-text-2">
                            {fmtDate(a.acquisition_date)} · {a.useful_life_months} bln · {entityName(a.entity_id)}
                            {a.gl_account_asset ? ` · ${a.gl_account_asset}` : ""}
                          </p>
                        </td>
                        <td className="text-kn-neutral">{a.category}</td>
                        <td className="text-right tabular-nums">{formatCurrency(a.acquisition_cost)}</td>
                        <td className="text-right tabular-nums text-kn-warning-text">
                          {formatCurrency(a.accumulated_depreciation)}
                          <span className="block text-fs-12 text-kn-text-2">{a.depreciated_months || 0}/{a.useful_life_months} bln</span>
                        </td>
                        <td className="text-right tabular-nums font-bold" data-testid={`asset-bv-${a.id}`}>
                          {formatCurrency(a.book_value)}
                        </td>
                        <td><AssetStatusPill asset={a} /></td>
                        <td className="col-sticky-end">
                          {/* Tombol boleh turun baris (bukan labelnya) supaya tabel muat di 1280 px; alasan tombol mati
                              ditulis di bawahnya, tidak hanya di petunjuk. */}
                          <div className="flex flex-wrap items-center justify-end gap-1.5 max-w-[230px] ml-auto">
                            <button data-testid={`schedule-btn-${a.id}`} className="secondary-button btn-sm whitespace-nowrap"
                              onClick={() => openSchedule(a)}>
                              <CalendarClock size={12} aria-hidden="true" /> Jadwal
                            </button>
                            {a.status !== "disposed" && (
                              <>
                                <button data-testid={`transfer-btn-${a.id}`} className="secondary-button btn-sm whitespace-nowrap"
                                  disabled={!!block} aria-describedby={block ? `asset-block-${a.id}` : undefined}
                                  onClick={() => { setError(""); setTransferFor(a); }}>
                                  <Building2 size={12} aria-hidden="true" /> Pindah PT
                                </button>
                                <button data-testid={`dispose-btn-${a.id}`}
                                  className="secondary-button btn-sm whitespace-nowrap text-kn-danger-text"
                                  disabled={!!block} aria-describedby={block ? `asset-block-${a.id}` : undefined}
                                  onClick={() => { setError(""); setDisposeFor(a); }}>
                                  <PackageMinus size={12} aria-hidden="true" /> Lepas
                                </button>
                              </>
                            )}
                            {a.status === "transferred" && tr.to_entity_id && !tr.settled && (
                              <button data-testid={`settle-transfer-${a.id}`} className="primary-button btn-sm whitespace-nowrap"
                                disabled={busy === `settle-${a.id}`} onClick={() => settleTransfer(a)}>
                                Catat Pembayaran
                              </button>
                            )}
                            {block && (
                              <p id={`asset-block-${a.id}`} data-testid={`asset-block-${a.id}`}
                                className="w-full text-right text-fs-12 text-kn-text-2">
                                {block}
                                {a.status === "transferred" && tr.new_asset_number ? ` Aset penggantinya ${tr.new_asset_number}.` : ""}
                                {a.status === "transferred" && tr.settled ? " Pembayarannya sudah dicatat." : ""}
                              </p>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <p className="text-fs-12 text-kn-text-2 mt-2">
            Metode <b>garis lurus</b>: penyusutan bulanan = (perolehan − nilai residu) / masa manfaat; bulan terakhir
            mengambil seluruh sisanya. Perolehan dicatat ke akun aset dengan lawan sesuai sumber dananya. Aset yang dilepas
            atau dipindah tidak dihapus — statusnya berubah dan riwayatnya tetap tersimpan.
          </p>
        </div>
      </div>

      {/* Fase 3 · P4 (L-03) — semua pop-up lewat FormModal/DetailModal; galat server tampil DI DALAM pop-up
          (dulu tertutup lapisan di belakangnya). */}
      {showAdd && (
        <AddAssetDialog
          meta={meta} entities={entities} selectedEntity={selectedEntity} busy={busy === "create"} error={error}
          onCancel={() => setShowAdd(false)} onSubmit={createAsset}
        />
      )}
      {scheduleFor && (
        <ScheduleDialog asset={scheduleFor} loading={scheduleLoading} onClose={() => setScheduleFor(null)} />
      )}
      {disposeFor && (
        <DisposeDialog asset={disposeFor} busy={busy === "dispose"} error={error}
          onCancel={() => setDisposeFor(null)} onSubmit={submitDispose} />
      )}
      {/* FASE E-7 (E7g) — pindah aset tetap antar badan usaha */}
      {transferFor && (
        <TransferAssetDialog asset={transferFor} entities={entities} busy={busy === "transfer"} error={error}
          onCancel={() => setTransferFor(null)} onSubmit={submitTransfer} />
      )}
    </div>
  );
}
