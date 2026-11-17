/**
 * ChartOfAccounts (EPIC7-C) — Bagan Akun / Chart of Accounts.
 * Akses admin/manager (permission "accounting"). Sumber: /api/gl/accounts.
 *
 * Fase 3 · P4 (L-03) — form Tambah Akun (dulu inline di atas tabel), Ubah Akun & Detail Akun kini pop-up baku
 * (FormModal/DetailModal) di `ChartOfAccountsParts.jsx`; banner "paling nyaman di desktop" di HP (L-04 kelas C).
 *
 * Pola UI 16 Nov (04_POLA_UI §2.A · masukan pemilik M36/M37):
 *  · Kepala SATU baris "Bagan Akun · {lingkup}" — penjelasan lingkup (dulu bilah ungu panjang) di ikon ?.
 *  · Lingkup MENGIKUTI PT di bilah atas (prinsip §1.7): satu PT → bagan PT itu; "Semua PT" → Template Global. Deret chip
 *    Lingkup (ungu, PT dobel dengan bilah atas) dicabut; "Template Global" saat satu PT dipilih = satu pilihan dropdown
 *    di bilah daftar.
 *  · Kartu angka = saringan cepat (klik → daftar tersaring; klik lagi → semua). Kartu gabungan "Aset / Beban" &
 *    "Kewajiban / Ekuitas" (tidak bisa ditindak) dicabut — jumlah per tipe kini di dropdown Tipe.
 *  · SATU bilah daftar: cari · tipe · lingkup · jumlah · muat ulang · + Tambah Akun.
 */
import { apiErrorText } from "../../utils/apiError";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  RefreshCw, Plus, BookOpen, Pencil, Trash2, X, Layers, Building2, ToggleLeft, ToggleRight, CheckCircle2, History,
  PowerOff,
} from "lucide-react";
import { can } from "../../config/roles";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import KNSelect from "../../components/KNSelect";
import StatusBadge from "../../components/StatusBadge";
import DesktopOnlyNotice from "../../components/DesktopOnlyNotice";
import { ListToolbar, MetricRow, PageHeader, SearchInput } from "../../components/ListPageParts";
import { entityShortById } from "../../utils/entityLabel";
import {
  TYPE_META, TYPE_ORDER, AddAccountModal, EditAccountModal, AccountDetailModal,
} from "./ChartOfAccountsParts";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyDelete, moneyPatch } from "../../utils/moneyRequest";

// Dropdown bilah daftar selebar isinya (bukan selebar layar) — sama dengan contoh pola (Retur Pelanggan).
const SELECT_CLS = "!h-auto !w-auto min-w-[150px] rounded-lg border border-kn-field-border bg-white !px-2 !py-1.5 text-fs-13";
const GLOBAL_LABEL = "Template Global";

/** Penjelasan lingkup (dulu bilah ungu permanen) — kini di ikon ? kepala halaman. */
export function teksLingkup(scopeEntityId, scopeLabel) {
  if (!scopeEntityId) {
    return `${GLOBAL_LABEL}: bagan akun bersama seluruh grup. Akun yang ditambah di sini dipakai semua PT. Pilih satu PT `
      + "di bilah atas untuk melihat bagan PT itu — akun khusus PT dan akun yang dimatikan hanya untuk PT itu.";
  }
  return `Bagan ${scopeLabel}: akun berlencana "global" adalah warisan template grup (dipakai apa adanya); akun berlencana `
    + `"khusus PT" hanya untuk ${scopeLabel}. Tombol "Dipakai ${scopeLabel}" menyalakan/mematikan akun hanya untuk PT ini — `
    + "PT lain tidak terpengaruh, dan kode akun tetap bersama sehingga jurnal lama tetap sah. Template Global bisa dibuka "
    + "dari dropdown Lingkup di bilah daftar.";
}

export default function ChartOfAccounts({ entities = [], currentUser, selectedEntity = "all" }) {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filterType, setFilterType] = useState("");
  const [kind, setKind] = useState("");   // saringan cepat dari kartu angka: "" | postable | inactive | override
  const [q, setQ] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editAcc, setEditAcc] = useState(null);
  const [detailAcc, setDetailAcc] = useState(null);
  const canAudit = can(currentUser?.permissions, "audit", "view");
  // M37 — lingkup mengikuti PT di bilah atas (`selectedEntity`: id PT atau "all"); `globalView` = pilihan
  // "Template Global" di dropdown Lingkup saat satu PT dipilih. Ganti PT di bilah atas → kembali ke bagan PT itu.
  const ptId = typeof selectedEntity === "string"
    ? (selectedEntity === "all" ? "" : selectedEntity)
    : (selectedEntity?.id || "");
  const [globalView, setGlobalView] = useState(false);
  useEffect(() => { setGlobalView(false); setKind(""); }, [ptId]);
  const scopeEntityId = ptId && !globalView ? ptId : "";
  // FASE E-4 (E4.4) — pemakaian akun per badan usaha
  const [togglingCode, setTogglingCode] = useState("");
  // PK-12 — tulis ke /api/gl/ ber-Idempotency-Key; tombol hapus mati selama menunggu jawaban.
  const [deletingCode, setDeletingCode] = useState("");
  const deleteIntent = useIntentKey("coad");
  const toggleIntent = useIntentKey("coat");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = scopeEntityId ? { entity_id: scopeEntityId } : {};
      const res = await axios.get(`${API}/gl/accounts`, { params });
      setAccounts(Array.isArray(res.data) ? res.data : []);
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat bagan akun."));
    } finally {
      setLoading(false);
    }
  }, [scopeEntityId]);

  useEffect(() => { load(); }, [load]);

  const ptLabel = useMemo(() => (ptId ? entityShortById(entities, ptId, "PT ini") : ""), [ptId, entities]);
  const scopeLabel = scopeEntityId ? ptLabel : GLOBAL_LABEL;

  const parentOptions = useMemo(
    () => [{ value: "", label: "— Tanpa induk (root) —" },
      ...accounts.map((a) => ({ value: a.code, label: `${a.code} — ${a.name}` }))],
    [accounts]);

  const stats = useMemo(() => {
    const byType = {};
    TYPE_ORDER.forEach((t) => { byType[t] = 0; });
    accounts.forEach((a) => { byType[a.type] = (byType[a.type] || 0) + 1; });
    return {
      total: accounts.length,
      postable: accounts.filter((a) => a.is_postable).length,
      inactive: accounts.filter((a) => a.is_active === false).length,
      override: scopeEntityId ? accounts.filter((a) => a.entity_id === scopeEntityId).length : 0,
      byType,
    };
  }, [accounts, scopeEntityId]);

  const grouped = useMemo(() => {
    const t = q.trim().toLowerCase();
    const pass = {
      postable: (a) => a.is_postable,
      inactive: (a) => a.is_active === false,
      override: (a) => Boolean(scopeEntityId) && a.entity_id === scopeEntityId,
    }[kind] || (() => true);
    const rows = accounts.filter((a) => (!filterType || a.type === filterType) && pass(a)
      && (!t || `${a.code} ${a.name}`.toLowerCase().includes(t)));
    const g = {};
    TYPE_ORDER.forEach((tp) => { g[tp] = []; });
    rows.forEach((a) => { (g[a.type] = g[a.type] || []).push(a); });
    TYPE_ORDER.forEach((tp) => g[tp].sort((x, y) => (x.code > y.code ? 1 : -1)));
    return { g, count: rows.length };
  }, [accounts, filterType, q, kind, scopeEntityId]);

  const removeAccount = async (acc) => {
    if (deletingCode) return;
    setError(""); setDeletingCode(acc.code);
    try {
      // Kalau kita di scope PT dan akun yg dihapus punya entity_id = scope → hapus override.
      // Kalau template global (entity_id null) → hapus dari template global.
      const params = acc.entity_id ? { entity_id: acc.entity_id } : {};
      await deleteIntent.send({ id: acc.code, aksi: "delete", ...params },
        (k) => moneyDelete(`${API}/gl/accounts/${acc.code}`, k, { params }));
      await load();
    } catch (err) {
      setError(apiErrorText(err, "Gagal menghapus akun."));
    } finally { setDeletingCode(""); }
  };

  // FASE E-4 (E4.4) — nyalakan/matikan akun HANYA untuk badan usaha yang sedang dibuka.
  // Sebelumnya pengguna harus membuka modal dan menebak bahwa mencentang "aktif" akan
  // melahirkan override; sekarang satu tombol dengan akibat yang tertulis jelas.
  const toggleEntityActive = async (acc) => {
    if (!scopeEntityId) return;
    setError(""); setTogglingCode(acc.code);
    try {
      const next = acc.is_active === false;
      const body = { name: acc.name, is_active: next };
      await toggleIntent.send({ id: acc.code, entity_id: scopeEntityId, ...body },
        (k) => moneyPatch(`${API}/gl/accounts/${acc.code}`, body, k, { params: { entity_id: scopeEntityId } }));
      setNotice(next
        ? `Akun ${acc.code} sekarang dipakai ${scopeLabel}.`
        : `Akun ${acc.code} tidak dipakai ${scopeLabel} lagi (badan usaha lain tidak terpengaruh).`);
      setTimeout(() => setNotice(""), 4000);
      await load();
    } catch (err) {
      setError(apiErrorText(err, "Gagal mengubah pemakaian akun di badan usaha ini."));
    } finally { setTogglingCode(""); }
  };

  // Kartu angka = saringan cepat (pola UI §1.5): klik → daftar tersaring, klik lagi → semua.
  const cards = [
    { k: "total", label: "Total akun", value: stats.total, icon: BookOpen, kind: "" },
    { k: "postable", label: "Akun detail (bisa diposting)", value: stats.postable, icon: Layers, kind: "postable" },
    ...(scopeEntityId
      ? [{ k: "override", label: `Khusus ${scopeLabel}`, value: stats.override, icon: Building2, kind: "override" },
        { k: "inactive", label: `Tidak dipakai ${scopeLabel}`, value: stats.inactive, icon: PowerOff, kind: "inactive" }]
      : [{ k: "inactive", label: "Nonaktif", value: stats.inactive, icon: PowerOff, kind: "inactive" }]),
  ];

  return (
    <div data-testid="coa-view">
      <DesktopOnlyNotice testId="coa-desktop-notice" what="Bagan Akun" />
      <PageHeader icon={BookOpen} testId="coa-header" help={teksLingkup(scopeEntityId, scopeLabel)}
        title={<span data-testid="coa-title">Bagan Akun <span className="font-normal text-kn-text-2">· {scopeLabel}</span></span>} />

      <MetricRow testId="coa-kpis" items={cards.map((c) => ({
        label: c.label, value: c.value, icon: c.icon, testId: `coa-kpi-${c.k}`,
        active: Boolean(c.kind) && kind === c.kind,
        onClick: () => setKind(kind === c.kind ? "" : c.kind),
      }))} />

      {notice && (
        <div className="notice-bar success mt-3" data-testid="coa-notice">
          <CheckCircle2 size={14} /> {notice}
          <button type="button" onClick={() => setNotice("")} aria-label="Tutup"><X size={12} /></button>
        </div>
      )}
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="coa-error" />

      <div className="mt-3">
        <ListToolbar testId="coa-toolbar" count={loading ? null : `${grouped.count} akun`}
          actions={(
            <>
              <button type="button" data-testid="coa-refresh" className="icon-button" onClick={load} aria-label="Muat ulang"
                title="Muat ulang"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
              <button type="button" data-testid="coa-add-toggle" className="primary-button whitespace-nowrap"
                onClick={() => setShowForm(true)}>
                <Plus size={14} /> Tambah Akun
              </button>
            </>
          )}>
          <SearchInput testId="coa-search" placeholder="Cari kode / nama akun…" value={q} onChange={setQ}
            className="min-w-[200px] flex-1 sm:max-w-[300px]" />
          <KNSelect data-testid="coa-filter-type" aria-label="Tipe akun" className={SELECT_CLS} value={filterType}
            onValueChange={(v) => setFilterType(v || "")} placeholder="Semua tipe"
            options={[{ value: "", label: `Semua tipe (${stats.total})` },
              ...TYPE_ORDER.map((t) => ({ value: t, label: `${TYPE_META[t].label} (${stats.byType[t] || 0})` }))]} />
          {/* M37 — satu PT di bilah atas: lingkup = PT itu; Template Global = satu pilihan di sini (bukan deret chip). */}
          {ptId && (
            <KNSelect data-testid="coa-scope" aria-label="Lingkup" className={SELECT_CLS}
              value={globalView ? "global" : "pt"} onValueChange={(v) => { setGlobalView(v === "global"); setKind(""); }}
              options={[{ value: "pt", label: `Bagan ${ptLabel}` }, { value: "global", label: GLOBAL_LABEL }]} />
          )}
        </ListToolbar>
      </div>

      <div className="section-card">
        <div className="section-body">
          {loading ? (
            <div className="grid gap-2" data-testid="coa-loading">{[0, 1, 2, 3].map((i) => <div key={i} className="h-9 rounded bg-kn-neutral-soft animate-pulse" />)}</div>
          ) : accounts.length === 0 ? (
            <div data-testid="coa-empty" className="py-12 text-center text-fs-12 text-kn-text-2">
              <BookOpen size={26} className="mx-auto mb-2 text-kn-neutral" />Belum ada akun.
            </div>
          ) : grouped.count === 0 ? (
            <div data-testid="coa-empty-filter" className="py-8 text-center text-fs-12 text-kn-text-2">
              Tidak ada akun yang cocok dengan saringan.
            </div>
          ) : (
            <div className="space-y-4" data-testid="coa-groups">
              {TYPE_ORDER.filter((t) => grouped.g[t] && grouped.g[t].length > 0).map((t) => (
                <div key={t} data-testid={`coa-group-${t}`}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className={`text-[11px] font-bold uppercase tracking-wide rounded px-2 py-0.5 ${TYPE_META[t].tone}`}>{TYPE_META[t].label}</span>
                    <span className="text-fs-12 text-kn-text-2">{grouped.g[t].length} akun</span>
                  </div>
                  {/* Audit UI 24 Okt (070 HP): tabel digulir di dalam kotak; kode akun tidak patah. */}
                  <div className="overflow-x-auto rounded-md border border-[#EFF0F2]">
                    <table className="w-full min-w-[560px] text-[12px]">
                      <thead>
                        <tr className="whitespace-nowrap border-b border-[#EFF0F2] bg-[#FAFBFC] text-left text-[11px] font-bold uppercase tracking-wide text-[#8E8E93]">
                          <th className="w-[110px] px-3 py-1.5">Kode</th>
                          <th className="px-3 py-1.5">Nama Akun</th>
                          {scopeEntityId && <th className="w-[190px] px-3 py-1.5">Dipakai Entitas</th>}
                          <th className="px-3 py-1.5 text-right">Jenis · Saldo Normal</th>
                          <th className="w-[104px] px-3 py-1.5"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {grouped.g[t].map((a) => {
                          const isOverride = scopeEntityId && a.entity_id === scopeEntityId;
                          const usedHere = a.is_active !== false;
                          return (
                          <tr key={a.code + "|" + (a.entity_id || "g")} data-testid={`coa-row-${a.code}`} className={`border-b border-[#F5F5F7] last:border-0 ${a.is_postable ? "" : "bg-[#FAFBFC]"} ${scopeEntityId && !usedHere ? "opacity-60" : ""}`}>
                            <td className="px-3 py-2 w-[110px]"><span className="whitespace-nowrap font-mono font-semibold text-[#3C3C43] tabular-nums">{a.code}</span></td>
                            <td className="px-3 py-2">
                              <span className={a.is_postable ? "text-[#1C1C1E]" : "font-bold text-[#3C3C43] uppercase text-[11px] tracking-wide"}>{a.name}</span>
                              {a.is_active === false && !scopeEntityId && <span className="ml-2 text-fs-12 text-kn-danger-text">nonaktif</span>}
                              {/* M37 — lencana baku (token), bukan ungu buatan sendiri. */}
                              {isOverride && (
                                <StatusBadge testId={`coa-badge-override-${a.code}`} tone="info" icon="tag" label="khusus PT"
                                  className="ml-2" title={`Akun/penyesuaian khusus ${scopeLabel}`} />
                              )}
                              {scopeEntityId && !isOverride && (
                                <StatusBadge testId={`coa-badge-global-${a.code}`} tone="neutral" icon="circle" label="global"
                                  className="ml-2" title="Warisan Template Global (dipakai apa adanya)" />
                              )}
                              {/* PK-36 (IC-06) — akun kontrol: saldonya hanya berubah lewat dokumen buku pembantunya. */}
                              {a.is_control && (
                                <StatusBadge testId={`coa-badge-control-${a.code}`} tone="warning" icon="lock" label="Akun kontrol"
                                  className="ml-2" title={`Hanya berubah lewat dokumen ${a.control_ledger_label || ""}`.trim()} />
                              )}
                            </td>
                            {/* FASE E-4 (E4.4) — kolom "dipakai badan usaha ini" */}
                            {scopeEntityId && (
                              <td className="px-3 py-2 w-[190px]">
                                <button type="button" data-testid={`coa-toggle-entity-active-${a.code}`}
                                  disabled={togglingCode === a.code}
                                  onClick={() => toggleEntityActive(a)}
                                  title={usedHere
                                    ? `Berhenti memakai akun ini di ${scopeLabel} (badan usaha lain tidak terpengaruh)`
                                    : `Pakai akun ini di ${scopeLabel}`}
                                  className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold transition-colors ${
                                    usedHere
                                      ? "border-[#BDE5CC] bg-[#E6F6EC] text-[#1B7F4B] hover:border-[#1B7F4B]"
                                      : "border-[#E5E5EA] bg-[#FAFBFC] text-[#8E8E93] hover:border-[#0058CC]"}`}>
                                  {usedHere ? <ToggleRight size={13} /> : <ToggleLeft size={13} />}
                                  {usedHere ? `Dipakai ${scopeLabel}` : `Tidak dipakai ${scopeLabel}`}
                                </button>
                              </td>
                            )}
                            <td className="whitespace-nowrap px-3 py-2 text-right text-[11px] text-[#6B6B73]">{a.is_postable ? "Detail" : "Kelompok"} · {a.normal_balance === "debit" ? "Debit" : "Kredit"}</td>
                            <td className="px-3 py-2 w-[104px] text-right">
                              <div className="inline-flex items-center gap-1">
                                <button data-testid={`coa-detail-${a.code}`} className="icon-button" onClick={() => setDetailAcc(a)} aria-label="Detail akun" title="Detail & riwayat perubahan"><History size={13} /></button>
                                <button data-testid={`coa-edit-${a.code}`} className="icon-button" onClick={() => setEditAcc(a)} aria-label="Ubah"><Pencil size={13} /></button>
                                {(!a.system || scopeEntityId) && (
                                  <button data-testid={`coa-delete-${a.code}`} className="icon-button text-[#C0392B]" onClick={() => removeAccount(a)} disabled={deletingCode === a.code} aria-label="Hapus"><Trash2 size={13} /></button>
                                )}
                              </div>
                            </td>
                          </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <AddAccountModal open={showForm} scopeEntityId={scopeEntityId} scopeLabel={scopeLabel}
        parentOptions={parentOptions} onClose={() => setShowForm(false)}
        onSaved={async () => { setShowForm(false); await load(); }} />
      {editAcc && (
        <EditAccountModal acc={editAcc} scopeEntityId={scopeEntityId} scopeLabel={scopeLabel}
          onClose={() => setEditAcc(null)}
          onSaved={async () => { setEditAcc(null); await load(); }} />
      )}
      {detailAcc && (
        <AccountDetailModal acc={detailAcc} canAudit={canAudit} scopeLabel={scopeLabel} entities={entities} onClose={() => setDetailAcc(null)} />
      )}
    </div>
  );
}
