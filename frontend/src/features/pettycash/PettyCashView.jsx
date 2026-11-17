/**
 * PettyCashView (MN-T2) — Keuangan › Kas & Bank › **Kas Kecil**: SATU daftar bertahap (dulu tiga layar daftar:
 * Pengajuan Dana, Pertanggungjawaban, Hutang Reimburse — dibungkus chip oleh MN-T1).
 *
 * Sumber: `GET /api/petty-cash/worklist?stage&q&page&page_size` (izin `cash_advance.view` atau `cash_settlement.view`) —
 * satu baris per pengajuan dana (PD) beserta pertanggungjawabannya (LPJ), tahap turunan server, jumlah per tahap.
 * Chip tahap: Semua · Diajukan · Dicairkan · Dipertanggungjawabkan · Selesai (dengan jumlah). Membuka baris = SATU
 * panel berisi rincian PD (`CashAdvanceDetail`) dan, bila ada, rincian LPJ-nya (`SettlementDetail`); aksi di dalamnya
 * (ajukan, setujui, cairkan, pertanggungjawabkan, bayar reimburse, terima sisa) memakai tombol komponen lama. "Ajukan
 * dana" = pop-up baku `CashAdvanceForm`; "Pertanggungjawabkan" = pop-up baku `SettlementForm` dengan PD terpilih.
 *
 * Kolom aksi = satu tombol: "Bayar" (hutang reimburse terbuka, pemegang `cash_settlement.pay` — pop-up
 * `SettlementCashModal`, sama dengan rincian LPJ; dulu tombol per baris di daftar Hutang Reimburse PK-24), selain itu "Buka".
 *
 * Alamat lama (`cash-advances`, `settlements`, `reimburse-payables`) = alias dengan `preset.bagian` → chip tahap
 * (`BAGIAN_KE_TAHAP`); rute cadangannya merender layar ini (`bagianAwal`). Tautan dokumen PD/LPJ (PK-44) membuka panelnya.
 *
 * Lebar tabel (cek layar MN-T2, kartu ±740 px di 1024 / ±1010 px di 1280, sidebar 220 px): Nomor (nomor + tanggal
 * diperbarui; di < 1280 px + keperluan · pemohon) ±136 · Keperluan · Pemohon (≥ 1280 px saja) ±204 · Jumlah ±118 ·
 * Tahap ±203 · Pertanggungjawaban (nomor LPJ + status + sisa kembali / hutang reimburse, dua baris) ±172 · Aksi
 * (menempel kanan) ±88 → 1024: ±717 px · 1280: ±900 px.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Banknote, CheckCheck, FileText, FolderOpen, HandCoins, Plus, ReceiptText, RefreshCw, Send, Wallet } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatDate } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";
import FilterSelect from "../../components/FilterSelect";   // pola UI 16 Nov — saringan dropdown (dulu FilterChips)
import ResponsiveTable from "../../components/ResponsiveTable";
import KNPager from "../../components/KNPager";
import { SearchBox } from "../../components/ListControls";
import DetailModal from "../../components/DetailModal";
import EntityBadge from "../../components/EntityBadge";
import EntityScopeBanner from "../../components/EntityScopeBanner";
import EntityGatedButton, { EntityGateNote } from "../../components/EntityGatedButton";
import FocusNotice from "../../components/FocusNotice";
import useFocusDoc from "../../hooks/useFocusDoc";
import useViewPreset from "../../hooks/useViewPreset";
import { can } from "../../config/roles";
import { CA_STATUS, STL_STATUS, StatusPill } from "./pettyCashShared";
import CashAdvanceForm from "./CashAdvanceForm";
import CashAdvanceDetail from "./CashAdvanceDetail";
import SettlementForm from "./SettlementForm";
import SettlementDetail from "./SettlementDetail";
import SettlementCashModal from "./SettlementCashModal";   // PK-24 — Bayar per baris (pop-up yang sama dengan rincian LPJ)

export const PAGE_SIZE = 25;
/** Tahap kas kecil (kunci = `stage` server). Status = ikon + teks + warna (`status-pill` dengan kelas yang ada). */
export const STAGES = [
  { key: "diajukan", label: "Diajukan", cls: "status-draft", icon: Send },
  { key: "dicairkan", label: "Dicairkan", cls: "status-shipped", icon: Banknote },
  { key: "dipertanggungjawabkan", label: "Dipertanggungjawabkan", cls: "status-pending", icon: ReceiptText },
  { key: "selesai", label: "Selesai", cls: "status-done", icon: CheckCheck },
];
const STAGE_OF = Object.fromEntries(STAGES.map((s) => [s.key, s]));
/** `preset.bagian` alias lama (MN-T1) → chip tahap. "" = Semua. */
export const BAGIAN_KE_TAHAP = { pengajuan: "", pertanggungjawaban: "dipertanggungjawabkan",
  reimburse: "dipertanggungjawabkan" };
/** Tahap awal dari preset navigasi (`tahap`, atau `bagian` alias lama) / rute cadangan id lama. */
export const tahapAwal = (preset, bagianAwal = "") => (preset?.tahap !== undefined ? preset.tahap
  : BAGIAN_KE_TAHAP[preset?.bagian || bagianAwal] ?? "");
export const TEKS_KOSONG = "Belum ada pengajuan dana.";
const TEKS_TANPA_AKSES = "Anda belum punya akses untuk melihat kas kecil. Minta Admin menambahkan akses 'Kas Kecil "
  + "(pengajuan dana & pertanggungjawaban)'.";

export function StagePill({ stage, testId }) {
  const s = STAGE_OF[stage] || { label: stage || "—", cls: "status-draft", icon: FileText };
  const Icon = s.icon;
  return (
    <span className={`status-pill ${s.cls}`} data-testid={testId}>
      <Icon size={12} aria-hidden="true" />{s.label}
    </span>
  );
}

/** Teks sisa per baris: "Sisa kembali Rp …" / "Hutang reimburse Rp …" / "" (tidak ada sisa atau tidak berizin). */
export function sisaText(stl) {
  if (!stl) return "";
  const parts = [];
  if (Number(stl.refund_due) > 0) parts.push(`Sisa kembali ${formatCurrency(stl.refund_due)}`);
  if (stl.reimburse_due !== null && stl.reimburse_due !== undefined && Number(stl.reimburse_due) > 0) {
    parts.push(`Hutang reimburse ${formatCurrency(stl.reimburse_due)}`);
  }
  return parts.join(" · ");
}

export default function PettyCashView({ currentUser, selectedEntity = "all", entities = [], focusDoc, onClearFocus,
  bagianAwal = "" }) {
  const perms = currentUser?.permissions || {};
  const bolehLihat = can(perms, "cash_advance", "view") || can(perms, "cash_settlement", "view");
  const lihatLpj = can(perms, "cash_settlement", "view");
  const canCreate = can(perms, "cash_advance", "create");
  const canSettle = can(perms, "cash_settlement", "create");
  const canPay = can(perms, "cash_settlement", "pay");
  const [pilihan, setPilihan] = useState(null);   // null = belum memilih chip → ikut preset / rute cadangan
  const [q, setQ] = useState("");
  const [qDebounced, setQDebounced] = useState("");
  const [page, setPage] = useState(1);
  const preset = useViewPreset("petty-cash", (p) => {
    if (p.tahap !== undefined || p.bagian !== undefined) { setPilihan(tahapAwal(p)); setPage(1); }
  });
  const stage = pilihan !== null ? pilihan : tahapAwal(preset, bagianAwal);
  const setStage = setPilihan;
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading");   // loading | ready | error
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [panel, setPanel] = useState(null);        // { ca, stl, stlError }
  const [form, setForm] = useState(null);          // { kind: "pd"|"lpj", record?, preselectPd?, resubmit? }
  const [categories, setCategories] = useState([]);
  const [bayar, setBayar] = useState(null);         // baris yang hutang reimburse-nya sedang dibayar

  useEffect(() => { const t = setTimeout(() => setQDebounced(q.trim()), 300); return () => clearTimeout(t); }, [q]);

  const load = useCallback(async () => {
    if (!bolehLihat) return;
    setState("loading");
    try {
      const params = { page, page_size: PAGE_SIZE };
      if (stage) params.stage = stage;
      if (qDebounced) params.q = qDebounced;
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      const r = await axios.get(`${API}/petty-cash/worklist`, { params });
      setData(r.data || null); setError(""); setState("ready");
    } catch (e) {
      setError(apiErrorText(e, "Daftar kas kecil tidak bisa dimuat.")); setState("error");
    }
  }, [bolehLihat, page, stage, qDebounced, selectedEntity]);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!lihatLpj) return;
    axios.get(`${API}/expense-categories`).then((r) => setCategories(Array.isArray(r.data) ? r.data : [])).catch(() => {});
  }, [lihatLpj, selectedEntity]);
  const catLabels = useMemo(() => Object.fromEntries(categories.map((c) => [c.code, c.label])), [categories]);

  function flash(msg) { setToast(msg); setTimeout(() => setToast(""), 4000); }

  /** Satu panel: PD + LPJ-nya (LPJ dibaca hanya bila berizin `cash_settlement.view`). */
  const openPanel = useCallback(async (caId, stlId) => {
    const ca = (await axios.get(`${API}/cash-advances/${caId}`)).data;
    let stl = null; let stlError = "";
    if (stlId && lihatLpj) {
      try { stl = (await axios.get(`${API}/cash-advance-settlements/${stlId}`)).data; }
      catch (e) { stlError = apiErrorText(e, "Rincian pertanggungjawaban tidak bisa dimuat."); }
    }
    setPanel({ ca, stl, stlError, stlId: stlId || "" });
  }, [lihatLpj]);
  const bukaBaris = (r) => openPanel(r.id, r.settlement?.id).catch((e) => flash(apiErrorText(e, "Gagal memuat rincian.")));
  const muatUlangPanel = () => panel && openPanel(panel.ca.id, panel.stl?.id || panel.stlId).catch(() => {});

  // PK-44 — tautan dokumen PD (Jejak Dokumen / rincian jurnal) membuka panelnya; LPJ membuka panel PD induknya.
  const fokus = useFocusDoc(focusDoc, ["cash_advance", "cash_settlement"], async (id, fd) => {
    if (fd.focus_type === "cash_settlement") {
      const stl = (await axios.get(`${API}/cash-advance-settlements/${id}`)).data;
      await openPanel(stl.cash_advance_id, stl.id);
    } else {
      await openPanel(id, "");
    }
  }, onClearFocus);

  if (!bolehLihat) {
    return <div className="empty-state" data-testid="petty-cash-no-access">{TEKS_TANPA_AKSES}</div>;
  }

  const counts = data?.stage_counts || {};
  const semua = STAGES.reduce((s, x) => s + (Number(counts[x.key]) || 0), 0);
  const rows = data?.items || [];
  const showEntity = selectedEntity === "all";
  const kosong = qDebounced ? `Tidak ada pengajuan dana yang cocok dengan “${qDebounced}”.`
    : stage ? `Tidak ada pengajuan dana di tahap ${STAGE_OF[stage]?.label || stage}.` : TEKS_KOSONG;
  const pdTanpaLpj = panel && panel.ca.status === "disbursed" && !panel.stl && !panel.stlId;

  return (
    <div className="grid gap-3" data-testid="petty-cash-view">
      {toast && <div className="notice-bar success" data-testid="pc-toast"><span>{toast}</span><button type="button" onClick={() => setToast("")} aria-label="Tutup">×</button></div>}
      <FocusNotice {...fokus} testId="pc-focus-notice" />
      <EntityScopeBanner testId="pc-scope" />

      <section className="section-card">
        <div className="section-head">
          <div className="flex min-w-0 items-center gap-2">
            <Wallet size={15} aria-hidden="true" className="text-kn-action" />
            <h2 data-testid="pc-title">Kas Kecil</h2>
          </div>
          <div className="flex items-center gap-2">
            <button type="button" data-testid="pc-refresh" className="icon-button" onClick={load} aria-label="Muat ulang">
              <RefreshCw size={14} className={state === "loading" ? "animate-spin" : ""} /></button>
            {canCreate && (
              <EntityGatedButton selectedEntity={selectedEntity} what="mengajukan dana" hint={false}
                aria-describedby="pc-create-scope-note" data-testid="pc-create-btn"
                className="primary-button btn-sm whitespace-nowrap" onClick={() => setForm({ kind: "pd" })}>
                <Plus size={14} aria-hidden="true" /> Ajukan dana</EntityGatedButton>
            )}
          </div>
        </div>
        <div className="section-body grid gap-3">
          {canCreate && <EntityGateNote selectedEntity={selectedEntity} what="mengajukan dana" testId="pc-create-scope-note" />}
          <SearchBox value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Cari nomor PD/LPJ, keperluan, pemohon…"
            testId="pc-search" />
          <FilterSelect testId="pc-stage" ariaLabel="Tahap kas kecil" value={stage || "all"}
            onChange={(k) => { setStage(k === "all" ? "" : k); setPage(1); }}
            options={[{ key: "all", label: "Semua", count: data ? semua : undefined },
              ...STAGES.map((s) => ({ key: s.key, label: s.label, icon: s.icon, count: data ? Number(counts[s.key]) || 0 : undefined }))]} />
        </div>
      </section>

      {state === "error" && <ErrorNotice testId="pc-error" message={error} onRetry={load} />}
      {state !== "error" && (
        <section className="section-card" data-testid="pc-list">
          <ResponsiveTable testId="pc-table" rows={rows} rowKey="id" rowTestId={(r) => `pc-row-${r.id}`}
            loading={state === "loading" && !data} empty={<span data-testid="pc-empty">{kosong}</span>}
            onRowClick={bukaBaris} stickyActions
            columns={[
              { key: "number", header: "Nomor", mobile: "title", render: (r) => (
                <span className="block min-w-0">
                  <span className="block whitespace-nowrap font-bold text-kn-action">{r.number}</span>
                  <span className="block whitespace-nowrap text-fs-12 text-kn-text-2">{formatDate(r.updated_at) || "—"}</span>
                  <span className="block max-w-[112px] truncate text-fs-12 text-kn-text-2 xl:hidden" title={`${r.purpose || ""} · ${r.requester || ""}`}>
                    {r.purpose || "—"} · {r.requester || "—"}</span>
                  {showEntity && r.entity_id && <span className="mt-0.5 block"><EntityBadge entityId={r.entity_id} /></span>}
                </span>) },
              { key: "purpose", header: "Keperluan · Pemohon", mobile: "hidden", className: "hidden xl:table-cell",
                headerClassName: "hidden xl:table-cell", render: (r) => (
                  <span className="block min-w-0">
                    <span className="block max-w-[180px] truncate font-semibold text-kn-text" title={r.purpose}>{r.purpose || "—"}</span>
                    <span className="block max-w-[180px] truncate text-fs-12 text-kn-text-2">{r.requester || "—"}{r.divisi ? ` · ${r.divisi}` : ""}</span>
                  </span>) },
              { key: "amount", header: "Jumlah", align: "right", mobile: "field", priority: 1,
                render: (r) => <span className="tabular-nums font-semibold whitespace-nowrap">{formatCurrency(r.amount)}</span> },
              { key: "stage", header: "Tahap", mobile: "badge", render: (r) => (
                <span className="block">
                  <StagePill stage={r.stage} testId={`pc-row-stage-${r.id}`} />
                  {r.stage === "diajukan" && CA_STATUS[r.status] && (
                    <span className="mt-0.5 block whitespace-nowrap text-fs-12 text-kn-text-2">{CA_STATUS[r.status].label}</span>)}
                </span>) },
              { key: "settlement", header: "Pertanggungjawaban", mobile: "field", priority: 2, render: (r) => {
                const s = r.settlement;
                if (!s) return <span className="text-fs-12 text-kn-text-2">Belum ada</span>;
                const sisa = sisaText(s);
                return (
                  <span className="block min-w-0" data-testid={`pc-stl-${r.id}`}>
                    <span className="block whitespace-nowrap font-semibold">{s.number}</span>
                    <span className="mt-0.5 block"><StatusPill status={s.status} map={STL_STATUS} testId={`pc-stl-status-${r.id}`} /></span>
                    {sisa && <span className="block text-fs-12 font-semibold text-kn-warning-text" data-testid={`pc-sisa-${r.id}`}>{sisa}</span>}
                  </span>);
              } },
            ]}
            actions={(r) => (canPay && Number(r.settlement?.reimburse_due) > 0 ? (
              <button type="button" data-testid={`pc-pay-${r.id}`} className="primary-button btn-sm whitespace-nowrap"
                onClick={() => setBayar(r)}><HandCoins size={13} aria-hidden="true" /> Bayar</button>
            ) : (
              <button type="button" data-testid={`pc-open-${r.id}`} className="secondary-button btn-sm whitespace-nowrap"
                onClick={() => bukaBaris(r)}><FolderOpen size={13} aria-hidden="true" /> Buka</button>
            ))}
            footer={data && data.total > 0 ? (
              <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-fs-12 text-kn-text-2">
                <span data-testid="pc-total">{data.total} pengajuan dana</span>
                <KNPager page={page} pageSize={PAGE_SIZE} total={data.total} onChange={setPage} testId="pc-pager" />
              </div>
            ) : null}
          />
        </section>
      )}

      {panel && (
        <DetailModal framed size="xl" label={`Rincian ${panel.ca.number || "Pengajuan Dana"}`} testId="pc-detail-modal"
          onClose={() => { setPanel(null); load(); }}>
          <div className="grid gap-4">
          <CashAdvanceDetail ca={panel.ca} currentUser={currentUser} entities={entities} flash={flash}
            onEdit={(rec) => setForm({ kind: "pd", record: rec })}
            onChanged={(rec) => { setPanel((p) => ({ ...p, ca: rec })); load(); }} />
          {pdTanpaLpj && (
            <div className="section-card section-pad flex flex-wrap items-center gap-2" data-testid="pc-settle-bar">
              <ReceiptText size={15} aria-hidden="true" className="text-kn-text-2" />
              <span className="text-fs-13 text-kn-text">Dana sudah dicairkan dan belum dipertanggungjawabkan.</span>
              {canSettle ? (
                <button type="button" data-testid="pc-settle-btn" className="primary-button btn-sm ml-auto whitespace-nowrap"
                  onClick={() => setForm({ kind: "lpj", preselectPd: panel.ca })}>
                  <ReceiptText size={13} aria-hidden="true" /> Pertanggungjawabkan</button>
              ) : (
                <span className="text-fs-12 text-kn-text-2" data-testid="pc-settle-no-perm">
                  Pertanggungjawaban dibuat pemegang izin membuat LPJ kas kecil.</span>
              )}
            </div>
          )}
          {panel.stlId && !lihatLpj && (
            <p className="section-card section-pad text-fs-12 text-kn-text-2" data-testid="pc-stl-no-perm">
              Rincian pertanggungjawaban hanya untuk pemegang izin lihat pertanggungjawaban kas kecil.</p>
          )}
          {panel.stlError && <ErrorNotice testId="pc-stl-error" message={panel.stlError} onRetry={muatUlangPanel} />}
          {panel.stl && (
            <SettlementDetail stl={panel.stl} currentUser={currentUser} entities={entities} catLabels={catLabels} flash={flash}
              onChanged={(rec) => { setPanel((p) => ({ ...p, stl: rec })); load(); }}
              onEdit={(rec, opt) => setForm({ kind: "lpj", record: rec, resubmit: !!opt?.resubmit })} />
          )}
          </div>
        </DetailModal>
      )}

      {bayar && (
        <SettlementCashModal mode="reimburse" entities={entities} onClose={() => setBayar(null)}
          stl={{ id: bayar.settlement.id, number: bayar.settlement.number, entity_id: bayar.entity_id,
            employee: bayar.requester, amount: bayar.settlement.reimburse_due }}
          onDone={() => { flash(`Kelebihan LPJ ${bayar.settlement.number} dibayar ke ${bayar.requester}.`); setBayar(null); load(); }} />
      )}

      {form?.kind === "pd" && (
        <CashAdvanceForm record={form.record || null} entities={entities} selectedEntity={selectedEntity}
          onCancel={() => setForm(null)}
          onSaved={(rec, isEdit) => {
            setForm(null); flash(`${rec.number} ${isEdit ? "diperbarui" : "dibuat"}.`);
            setPanel((p) => (p ? { ...p, ca: rec } : { ca: rec, stl: null, stlError: "", stlId: "" })); load();
          }} />
      )}
      {form?.kind === "lpj" && (
        <SettlementForm categories={categories} selectedEntity={selectedEntity} record={form.record || null}
          preselectPd={form.preselectPd} resubmit={!!form.resubmit} onCancel={() => setForm(null)}
          onSaved={(rec) => {
            setForm(null);
            flash(form.resubmit ? `${rec.number} diperbaiki dan diajukan lagi.` : `${rec.number} disimpan.`);
            openPanel(rec.cash_advance_id, rec.id).catch(() => {}); load();
          }} />
      )}
    </div>
  );
}
